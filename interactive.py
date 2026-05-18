"""Interactive CLI loop with multiple operating modes"""
import signal
import sys
import time
from datetime import datetime
from typing import Optional 
from cli.commands import *
from workflow.task_runner import run_task_cycle
from core.db_helpers import post_message
from core.db_connection import get_db_connection
from core.cli_modes import CLIMode, UnattendedConfig, CLIState

# Global flag for graceful shutdown
_shutdown_requested = False

def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully"""
    global _shutdown_requested
    if not _shutdown_requested:
        print("\n\n⚠️  Shutdown requested (Ctrl+C). Finishing current iteration...")
        print("   Press Ctrl+C again to force quit (may lose data)\n")
        _shutdown_requested = True
    else:
        print("\n❌ Force quit!")
        sys.exit(1)

def should_continue_unattended(state: CLIState, config: UnattendedConfig) -> bool:
    """Check if unattended mode should continue"""
    global _shutdown_requested
    
    if _shutdown_requested:
        return False
    
    # Check time limit
    elapsed = state.elapsed_hours()
    if elapsed >= config.max_duration_hours:
        print(f"\n⏰ Unattended duration reached ({config.max_duration_hours}h)")
        return False
    
    return True

def generate_next_task(state: CLIState, config: UnattendedConfig) -> str:
    """Generate next task based on project state"""
    
    # Priority 1: Critical/High issues from background agents
    if config.prioritize_critical_issues:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT COUNT(*), priority, category
                FROM agent_feedback
                WHERE addressed = 0 AND priority IN ('CRITICAL', 'HIGH')
                GROUP BY priority, category
                ORDER BY 
                    CASE priority WHEN 'CRITICAL' THEN 1 ELSE 2 END,
                    COUNT(*) DESC
                LIMIT 1
            """)
            
            feedback = cursor.fetchone()
            if feedback and feedback[0] > 0:
                count, priority, category = feedback
                return f"Address {count} {priority} {category} issue(s) identified by background agents"
    
    # Priority 2: Recent file modifications needing review
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT file_path, COUNT(*) as mod_count
            FROM file_modifications
            WHERE timestamp > datetime('now', '-2 hours')
            GROUP BY file_path
            ORDER BY mod_count DESC
            LIMIT 1
        """)
        
        recent = cursor.fetchone()
        if recent and recent[1] > 1:
            return f"Review and consolidate {recent[1]} recent changes to {recent[0]}"
    
    # Priority 3: Files with unaddressed feedback
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT file_path, COUNT(*) as issue_count
            FROM agent_feedback
            WHERE addressed = 0
            GROUP BY file_path
            ORDER BY issue_count DESC
            LIMIT 1
        """)
        
        issues = cursor.fetchone()
        if issues and issues[1] > 0:
            return f"Resolve {issues[1]} issue(s) in {issues[0]}"
    
    # Priority 4: Unreviewed files
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT pf.file_path
            FROM project_files pf
            WHERE pf.is_binary = 0
            AND NOT EXISTS (
                SELECT 1 FROM agent_review_tracking art
                WHERE art.file_path = pf.file_path
            )
            ORDER BY pf.last_modified DESC
            LIMIT 1
        """)
        
        unreviewed = cursor.fetchone()
        if unreviewed:
            return f"Initial comprehensive review of {unreviewed[0]}"
    
    # Priority 5: General code quality improvements
    return "Scan project for code quality improvements, refactoring opportunities, and technical debt"

def save_checkpoint(state: CLIState):
    """Save checkpoint to database"""
    try:
        with get_db_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cli_checkpoints (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    mode TEXT,
                    start_time TEXT,
                    task_counter INTEGER,
                    total_files_modified INTEGER,
                    total_iterations INTEGER,
                    current_task_id TEXT,
                    checkpoint_time TEXT
                )
            """)
            
            conn.execute("""
                INSERT OR REPLACE INTO cli_checkpoints
                (id, mode, start_time, task_counter, total_files_modified, 
                 total_iterations, current_task_id, checkpoint_time)
                VALUES (1, ?, ?, ?, ?, ?, ?, ?)
            """, (
                state.mode.value,
                state.start_time.isoformat(),
                state.task_counter,
                state.total_files_modified,
                state.total_iterations,
                state.current_task_id,
                datetime.now().isoformat()
            ))
        
        state.update_checkpoint()
        elapsed = state.elapsed_hours()
        print(f"\n💾 Checkpoint saved: Task {state.task_counter}, {state.total_files_modified} files modified, {elapsed:.1f}h elapsed")
    except Exception as e:
        print(f"⚠️  Checkpoint save failed: {e}")

def load_checkpoint() -> Optional[CLIState]:
    """Load checkpoint from database"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT mode, start_time, task_counter, total_files_modified,
                       total_iterations, current_task_id, checkpoint_time
                FROM cli_checkpoints
                WHERE id = 1
            """)
            
            row = cursor.fetchone()
            if row:
                mode = CLIMode(row[0])
                start_time = datetime.fromisoformat(row[1])
                checkpoint_time = datetime.fromisoformat(row[6]) if row[6] else None
                
                state = CLIState(
                    mode=mode,
                    start_time=start_time,
                    task_counter=row[2],
                    total_files_modified=row[3],
                    total_iterations=row[4],
                    current_task_id=row[5],
                    last_checkpoint=checkpoint_time
                )
                
                return state
        
        return None
    except Exception:
        return None

def run_unattended_mode(config: UnattendedConfig):
    """Run unattended mode loop"""
    global _shutdown_requested
    
    # Try to load checkpoint
    state = load_checkpoint()
    
    if state and state.mode == CLIMode.UNATTENDED:
        elapsed = state.elapsed_hours()
        print("\n📂 Checkpoint found - resuming from previous session")
        print(f"   Previous start: {state.start_time.strftime('%Y-%m-%d %H:%M')}")
        print(f"   Tasks completed: {state.task_counter - 1}")
        print(f"   Files modified: {state.total_files_modified}")
        print(f"   Elapsed: {elapsed:.1f}h")
        
        # Check if should continue
        if elapsed >= config.max_duration_hours:
            print(f"\n⏰ Previous session already completed {config.max_duration_hours}h run")
            print("   Starting fresh session...\n")
            state = None
    else:
        state = None
    
    # Create new state if no valid checkpoint
    if state is None:
        state = CLIState(
            mode=CLIMode.UNATTENDED,
            start_time=datetime.now()
        )
    
    end_time = config.get_end_time(state.start_time)
    
    print("\n" + "="*60)
    print("🤖 UNATTENDED MODE ACTIVE")
    print("="*60)
    print(f"Duration: {config.max_duration_hours}h")
    print(f"Start: {state.start_time.strftime('%Y-%m-%d %H:%M')}")
    print(f"End: {end_time.strftime('%Y-%m-%d %H:%M')}")
    print(f"Checkpoint interval: {config.checkpoint_interval_minutes}m")
    print(f"Max iterations per task: {config.max_iterations_per_task}")
    print(f"\nPress Ctrl+C for graceful shutdown")
    print("="*60 + "\n")
    
    # Main unattended loop
    while should_continue_unattended(state, config):
        try:
            # Generate task
            if config.auto_generate_tasks:
                task_description = generate_next_task(state, config)
            else:
                task_description = "Continue development based on project state and feedback"
            
            task_id = f"task_{state.task_counter:03d}"
            state.task_counter += 1
            state.current_task_id = task_id
            
            elapsed = state.elapsed_hours()
            remaining = config.max_duration_hours - elapsed
            
            print(f"\n{'='*60}")
            print(f"🎯 AUTO-GENERATED TASK: {task_id}")
            print(f"   {task_description}")
            print(f"   Elapsed: {elapsed:.1f}h | Remaining: {remaining:.1f}h")
            print(f"{'='*60}\n")
            
            # Run task cycle
            run_task_cycle(
                task_id, 
                task_description,
                max_turns=config.max_iterations_per_task
            )
            
            state.total_iterations += 1
            
            # Count files modified in this task
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT COUNT(DISTINCT file_path)
                    FROM file_modifications
                    WHERE task_id = ?
                """, (task_id,))
                files_changed = cursor.fetchone()[0] or 0
            
            state.total_files_modified += files_changed
            
            if files_changed > 0:
                print(f"\n✅ Task {task_id}: {files_changed} file(s) modified")
            else:
                print(f"\n⚠️  Task {task_id}: No files modified")
            
            # Checkpoint if needed
            if state.should_checkpoint(config.checkpoint_interval_minutes):
                save_checkpoint(state)
            
            # Brief pause between tasks (unless shutting down)
            if not _shutdown_requested and should_continue_unattended(state, config):
                idle_minutes = config.min_idle_minutes
                print(f"\n⏸️  Pausing {idle_minutes:.1f}m before next task...")
                
                # Sleep in small intervals to check shutdown flag
                sleep_intervals = int(idle_minutes * 60 / 10)  # Check every 10 seconds
                for _ in range(sleep_intervals):
                    if _shutdown_requested:
                        break
                    time.sleep(10)
        
        except KeyboardInterrupt:
            # Graceful shutdown
            if not _shutdown_requested:
                _shutdown_requested = True
            save_checkpoint(state)
            break
        
        except Exception as e:
            print(f"\n❌ Error in unattended loop: {e}")
            import traceback
            traceback.print_exc()
            
            # Save checkpoint and recover
            save_checkpoint(state)
            
            if not _shutdown_requested:
                print(f"\n⏸️  Recovering... pausing 2 minutes before retry")
                time.sleep(120)
            else:
                break
    
    # Final summary
    print(f"\n{'='*60}")
    print("📊 UNATTENDED MODE SUMMARY")
    print("="*60)
    elapsed = state.elapsed_hours()
    print(f"Duration: {elapsed:.1f}h / {config.max_duration_hours}h")
    print(f"Tasks completed: {state.task_counter - 1}")
    print(f"Total iterations: {state.total_iterations}")
    print(f"Files modified: {state.total_files_modified}")
    print(f"Checkpoints saved: {state.total_iterations // config.checkpoint_interval_minutes + 1}")
    
    if _shutdown_requested:
        print(f"\nStatus: Gracefully shutdown by user")
    else:
        print(f"\nStatus: Completed full duration")
    
    print("="*60 + "\n")
    
    # Save final checkpoint
    save_checkpoint(state)

def run_semi_attended_mode():
    """Run semi-attended mode loop (original behavior)"""
    global _shutdown_requested
    
    print("\n" + "="*60)
    print("🚀 SEMI-ATTENDED MODE")
    print("="*60)
    print("\nType 'help' for commands or describe a task to begin.")
    print("Type 'quit' to exit.")
    print("="*60 + "\n")
    
    task_counter = 1
    
    while not _shutdown_requested:
        try:
            cmd = input("👤 Human> ").strip()
            
            if not cmd:
                continue
            
            # ============= QUIT COMMAND =============
            if cmd.lower() in ["quit", "exit", "q"]:
                print("\n👋 Goodbye!\n")
                break
            
            # ============= HELP COMMAND =============
            if cmd.lower() == "help":
                cmd_help()
                continue
            
            # ============= EXPORT COMMANDS (NO API) =============
            if cmd.lower() == "export":
                cmd_export_db()
                continue
            
            if cmd.lower().startswith("export "):
                parts = cmd.split()
                if len(parts) == 2:
                    cmd_export_task(parts[1])
                elif len(parts) == 3:
                    cmd_export_task(parts[1], parts[2])
                else:
                    print("Usage: export [task_id] [output_dir]")
                continue
            
            if cmd.lower() == "list_exports":
                cmd_list_exports()
                continue
            
            if cmd.lower().startswith("export_tables "):
                parts = cmd.split(maxsplit=2)
                tables = parts[1].split(',')
                task_id = parts[2] if len(parts) > 2 else None
                cmd_export_specific_tables(tables, task_id=task_id)
                continue
            
            # ============= PROJECT COMMANDS (NO API) =============
            if cmd.lower() == "init":
                cmd_init()
                continue
            
            if cmd.lower() == "files":
                cmd_files()
                continue
            
            if cmd.lower() == "project":
                print("\n📂 Project information")
                print("-" * 60)
                from core.config import get_config
                config = get_config()
                print(f"Directory: {config.get('project_directory')}")
                print(f"Git enabled: {config.get('git')}")
                print(f"Background agents: {config.get('background_agents_enabled')}")
                print(f"CLI Mode: {config.get('cli_mode', {}).get('mode', 'semi_attended')}")
                print()
                continue
            
            if cmd.lower() == "changes":
                with get_db_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT file_path, operation, changed_by, task_id, timestamp
                        FROM file_modifications
                        ORDER BY timestamp DESC
                        LIMIT 10
                    """)
                    modifications = cursor.fetchall()
                
                if not modifications:
                    print("\n📝 No file modifications yet\n")
                else:
                    print("\n📝 Recent File Modifications:")
                    print("-" * 60)
                    for file_path, operation, changed_by, task_id, timestamp in modifications:
                        print(f"  {timestamp[:19]} | {operation.upper():8} | {file_path}")
                        print(f"    By: {changed_by} (Task: {task_id})")
                        print()
                continue
            
            # ============= ENDPOINT COMMANDS =============
            if cmd.lower() == "endpoints":
                cmd_endpoints()
                continue
            
            if cmd.lower() == "health":
                cmd_endpoint_health()
                continue

            if cmd.lower() == "fallbacks":
                cmd_fallback_stats()
                continue

            if cmd.lower().startswith("reset"):
                parts = cmd.split()
                if len(parts) == 1:
                    cmd_reset_endpoint()
                elif len(parts) == 2:
                    cmd_reset_endpoint(parts[1])
                else:
                    print("Usage: reset [endpoint_name]")
                continue

            # ============= HISTORY COMMANDS (NO API) =============
            if cmd.lower() == "status":
                cmd_status()
                continue
            
            if cmd.lower() == "history":
                cmd_history()
                continue
            
            if cmd.lower().startswith("feedback "):
                task_id = cmd.split()[1] if len(cmd.split()) > 1 else "task_001"
                cmd_feedback(task_id)
                continue
            
            if cmd.lower().startswith("show_prompt "):
                parts = cmd.split()
                task_id = parts[1] if len(parts) > 1 else "task_001"
                agent_name = parts[2] if len(parts) > 2 else None
                cmd_show_prompt(task_id, agent_name)
                continue
            
            if cmd.lower() == "conversation" or cmd.lower().startswith("conversation "):
                parts = cmd.split()
                task_id = parts[1] if len(parts) > 1 else "task_001"
                with get_db_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT timestamp, agent, role, content
                        FROM conversation_history
                        WHERE task_id = ?
                        ORDER BY timestamp
                        LIMIT 50
                    """, (task_id,))
                    results = cursor.fetchall()
                
                if not results:
                    print(f"\n📋 No conversation history for {task_id}\n")
                else:
                    print(f"\n📜 Conversation History: {task_id}")
                    print("="*60)
                    for timestamp, agent, role, content in results:
                        print(f"\n[{timestamp[:19]}] {agent.upper()} ({role})")
                        print("-"*60)
                        print(content[:500])
                        if len(content) > 500:
                            print(f"... +{len(content)-500} chars")
                        print()
                continue
            
            if cmd.lower() == "archives" or cmd.lower().startswith("archives "):
                parts = cmd.split()
                task_id = parts[1] if len(parts) > 1 else None
                cmd_archives(task_id)
                continue
            
            if cmd.lower() == "review_status":
                cmd_review_status()
                continue
            
            # ============= REPORTS COMMANDS =============
            if cmd.lower() == "reports":
                cmd_reports()
                continue

            if cmd.lower() == "json_stats":
                cmd_json_parse_stats()
                continue

            if cmd.lower().startswith("progress "):
                task_id = cmd.split()[1]
                cmd_task_progress(task_id)
                continue

            if cmd.lower() == "report" or cmd.lower().startswith("report "):
                parts = cmd.split(maxsplit=1)
                report_name = parts[1] if len(parts) > 1 else None
                cmd_show_report(report_name)
                continue
            
            if cmd.lower() == "resource_status":
                cmd_resource_status()
                continue
            
            if cmd.lower() == "git":
                from utils.git_operations import git_status, git_log
                print("\n📦 Git Status:")
                print(git_status())
                print("\n📦 Recent Commits:")
                commits = git_log(10)
                if commits:
                    for commit in commits:
                        print(f"  {commit['hash']} - {commit['when']}")
                        print(f"    {commit['message']}")
                        print()
                continue
            
            # =============HUMAN AS HIGH-BIAS AGENT =============
            # Check if there's an active task - if so, treat input as human feedback
            if task_counter > 1:  # Not first command
                with get_db_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT id FROM tasks 
                        WHERE status = 'in_progress' 
                        ORDER BY started_at DESC 
                        LIMIT 1
                    """)
                    active_task = cursor.fetchone()
                    
                if active_task:
                    # Post as human feedback with high bias
                    print(f"\n💬 Posting as human feedback to active task {active_task[0]}...")
                    post_message(
                        from_agent="human",
                        to_agent="orchestrator",
                        content=cmd,
                        task_id=active_task[0],
                        priority="CRITICAL"  # Human input always CRITICAL
                    )
                    print(f"   ✅ Posted to {active_task[0]}")
                    print(f"   🎯 Prioritizer will process and elevate to orchestrator\n")
                    continue
            # ==========================================================
            
            # ============= FALLTHROUGH TO TASK EXECUTION =============
            # No active task - start new one
            task_id = f"task_{task_counter:03d}"
            task_counter += 1
            
            print(f"\n🚀 Starting {task_id}...")
            run_task_cycle(task_id, cmd)
        
        except KeyboardInterrupt:
            print("\n\n⚠️  Interrupted. Type 'quit' to exit.\n")
            continue
        except Exception as e:
            print(f"\n❌ Error: {e}\n")
            import traceback
            traceback.print_exc()

def interactive_loop(mode: CLIMode = CLIMode.SEMI_ATTENDED, 
                    unattended_config: UnattendedConfig = None):
    """Main interactive loop - routes to appropriate mode"""
    
    # Setup signal handler for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    
    if mode == CLIMode.UNATTENDED:
        # Unattended mode - continuous operation
        if unattended_config is None:
            from core.config import get_config
            config = get_config()
            unattended_config = UnattendedConfig.from_config(config)
        
        run_unattended_mode(unattended_config)
    else:
        # Semi-attended mode - wait for human input
        run_semi_attended_mode()