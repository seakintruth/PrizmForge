"""CLI command handlers"""
import os
import json
import csv
from pathlib import Path
from datetime import datetime

from core.config import get_config
from core.db import get_db_path
from core.db_helpers import get_unaddressed_feedback
from core.token_budget import TokenBudget
from core.file_operations import (
    should_ignore_file,
    is_text_file,
    sync_file_to_database,
    generate_file_summary,
    save_file_summary
)
from core.db_connection import get_db_connection

def cmd_init():
    """Initialize and index project"""
    print(f"\\n{'='*60}")
    print(f"📂 Indexing Project")
    print(f"{'='*60}\\n")
    
    config = get_config()
    project_dir = Path(config.get("project_directory", "./project"))
    project_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"Scanning: {project_dir.absolute()}\\n")
    
    indexed = 0
    skipped = 0
    errors = 0
    
    # Use os.walk() instead of rglob()
    for root, dirs, files in os.walk(project_dir):
        # Remove ignored directories from dirs list (modifies in-place to prune walk)
        dirs[:] = [d for d in dirs if not should_ignore_file(d)]
        
        for filename in files:
            full_path = Path(root) / filename
            
            try:
                rel_path = full_path.relative_to(project_dir)
                rel_path_str = str(rel_path).replace('\\\\', '/')  # Normalize path separators
                
                if should_ignore_file(rel_path_str):
                    skipped += 1
                    continue
                
                if not is_text_file(rel_path_str):
                    print(f"  ⏭️  Skipped (binary): {rel_path_str}")
                    skipped += 1
                    continue
                
                content = full_path.read_text(encoding='utf-8')
                
                # Sync to database
                if sync_file_to_database(rel_path_str, content):
                    # Generate summary
                    summary = generate_file_summary(rel_path_str, content)
                    save_file_summary(rel_path_str, summary)
                    indexed += 1
                    print(f"  ✅ {rel_path_str}")
                else:
                    print(f"  ⚠️  Failed to sync: {rel_path_str}")
                    errors += 1
                    
            except Exception as e:
                print(f"  ❌ Error: {filename}: {e}")
                errors += 1
    
    print(f"\\n{'='*60}")
    print(f"📊 Indexing Results:")
    print(f"   ✅ Indexed: {indexed}")
    print(f"   ⏭️  Skipped: {skipped}")
    if errors > 0:
        print(f"   ❌ Errors: {errors}")
    print(f"{'='*60}\\n")

def cmd_files():
    """List indexed files"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT file_path, size_bytes, file_type, indexed_at
            FROM project_files
            WHERE is_binary = 0
            ORDER BY file_path
        """)
        files = cursor.fetchall()

    print(f"\\n📂 Indexed Files ({len(files)}):")
    print("-" * 60)
    for path, size, ftype, indexed in files:
        print(f"  {path} ({size} bytes, {ftype})")
    print()

def cmd_status():
    """Show system status"""
    config = get_config()
    budget = TokenBudget(get_db_path(), config["token_budget"]["max_tokens_per_4h"])
    budget.load_from_db()
    budget.print_status()

def cmd_history(limit: int = 10):
    """Show recent tasks"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, description, status, started_at, completed_at
            FROM tasks
            ORDER BY started_at DESC
            LIMIT ?
        """, (limit,))
        tasks = cursor.fetchall()
    
    if not tasks:
        print(f"\\n📋 No tasks yet\\n")
        return
    
    print(f"\\n📋 Recent Tasks:")
    print("-" * 60)
    for task_id, desc, status, started, completed in tasks:
        icon = "✅" if status == "completed" else "🔄"
        print(f"{icon} {task_id}: {desc[:50]}")
        print(f"   Started: {started}")
        if completed:
            print(f"   Completed: {completed}")
    print()

def cmd_feedback(task_id: str):
    """Show feedback for task"""
    feedback = get_unaddressed_feedback(task_id)
    
    if not feedback:
        print(f"\\n✅ No unaddressed feedback for {task_id}\\n")
        return
    
    print(f"\\n📝 Unaddressed Feedback for {task_id}:")
    print("-" * 60)
    for fb in feedback:
        print(f"[{fb['priority']}] {fb['agent']} - {fb['file_path']}")
        print(f"  {fb['message']}")
        if fb['suggestion']:
            print(f"  💡 {fb['suggestion'][:100]}")
        print()

def cmd_reset_endpoint(endpoint_name: str = None):
    """Reset endpoint health status"""
    from core.endpoint_manager import get_endpoint_manager, EndpointStatus
    
    endpoint_mgr = get_endpoint_manager()
    
    if endpoint_name:
        # Reset specific endpoint
        if endpoint_name in endpoint_mgr.endpoints:
            endpoint = endpoint_mgr.endpoints[endpoint_name]
            endpoint.health.mark_success()
            print(f"✅ Reset {endpoint_name} to healthy status")
        else:
            print(f"❌ Unknown endpoint: {endpoint_name}")
            print(f"   Available: {', '.join(endpoint_mgr.endpoints.keys())}")
    else:
        # Reset all endpoints
        for name, endpoint in endpoint_mgr.endpoints.items():
            endpoint.health.mark_success()
        print(f"✅ Reset all endpoints to healthy status")

def cmd_fallback_stats():
    """Show fallback statistics"""
    from core.fallback_stats import get_fallback_stats
    
    stats = get_fallback_stats()
    
    print(f"\n📊 Endpoint Fallback Statistics")
    print("=" * 80)
    print(f"\nTotal fallbacks: {stats['total']}")
    
    if stats['by_reason']:
        print(f"\n📋 Fallbacks by Reason:")
        for reason, count in stats['by_reason'].items():
            print(f"   {reason:<30} {count:>5} times")
    
    if stats['by_endpoint']:
        print(f"\n🔄 Most Affected Endpoints:")
        for endpoint, count in stats['by_endpoint'].items():
            print(f"   {endpoint:<30} {count:>5} fallbacks")
    
    if stats['recent']:
        print(f"\n⏰ Recent Fallbacks:")
        print("-" * 80)
        for timestamp, agent, orig, fallback, reason in stats['recent']:
            print(f"{timestamp[:19]} | {agent:<15}")
            print(f"  {orig} → {fallback} (reason: {reason})")
    
    print()

def cmd_show_prompt(task_id: str, agent_name: str = None):
    """Show prompts sent to agents"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        if agent_name:
            cursor.execute("""
                SELECT timestamp, agent_name, prompt, response, parse_success
                FROM agent_responses_archive
                WHERE task_id = ? AND agent_name = ?
                ORDER BY timestamp DESC
                LIMIT 5
            """, (task_id, agent_name))
        else:
            cursor.execute("""
                SELECT timestamp, agent_name, prompt, response, parse_success
                FROM agent_responses_archive
                WHERE task_id = ?
                ORDER BY timestamp DESC
                LIMIT 10
            """, (task_id,))
        
        responses = cursor.fetchall()
    
    if not responses:
        print(f"\n📋 No prompts found for {task_id}\n")
        return
    
    print(f"\n📋 Agent Prompts for {task_id}:")
    print("=" * 60)
    
    for timestamp, agent, prompt, response, success in responses:
        print(f"\n⏰ {timestamp[:19]} | {agent} | {'✅' if success else '❌'}")
        print("-" * 60)
        print(f"PROMPT ({len(prompt)} chars):")
        print(prompt[:500])
        if len(prompt) > 500:
            print(f"... +{len(prompt)-500} more chars")
        print(f"\nRESPONSE ({len(response) if response else 0} chars):")
        print(response[:300] if response else "NO RESPONSE")
        if response and len(response) > 300:
            print(f"... +{len(response)-300} more chars")
        print()

def cmd_export_db(output_dir: str = None, task_id: str = None):
    """Export all database tables to CSV files"""
    
    # Set output directory
    if output_dir is None:
        from core.config import get_config
        config = get_config()
        project_dir = Path(config.get("project_directory", "./project"))
        prizmfoundry_dir = project_dir / ".PrizmForge"
        prizmfoundry_dir.mkdir(parents=True, exist_ok=True)
        output_dir = prizmfoundry_dir / "agents_exports" / datetime.now().strftime("%Y%m%d_%H%M%S")

    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"\n📦 Exporting Database to CSV")
    print("=" * 60)
    print(f"Output Directory: {output_dir.absolute()}")
    if task_id:
        print(f"Filtering by task_id: {task_id}")
    print()
    with get_db_connection() as conn:    
        cursor = conn.cursor()
        
        # Get all table names
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' 
            ORDER BY name
        """)
        tables = [row[0] for row in cursor.fetchall()]
        
        exported_count = 0
        total_rows = 0
        
        for table_name in tables:
            try:
                # Build query with optional task_id filter
                if task_id and table_has_task_id(cursor, table_name):
                    query = f"SELECT * FROM {table_name} WHERE task_id = ?"
                    cursor.execute(query, (task_id,))
                else:
                    query = f"SELECT * FROM {table_name}"
                    cursor.execute(query)
                
                rows = cursor.fetchall()
                
                if not rows:
                    print(f"  ⏭️  {table_name}: (empty)")
                    continue
                
                # Get column names
                column_names = [description[0] for description in cursor.description]
                
                # Write to CSV
                csv_file = output_dir / f"{table_name}.csv"
                with open(csv_file, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(column_names)
                    writer.writerows(rows)
                
                exported_count += 1
                total_rows += len(rows)
                print(f"  ✅ {table_name}: {len(rows)} rows → {csv_file.name}")
                
            except Exception as e:
                print(f"  ❌ {table_name}: Error - {e}")
        
    
    print()
    print("=" * 60)
    print(f"📊 Export Summary:")
    print(f"   Tables exported: {exported_count}/{len(tables)}")
    print(f"   Total rows: {total_rows:,}")
    print(f"   Location: {output_dir.absolute()}")
    print("=" * 60)
    print()
    
    return output_dir


def table_has_task_id(cursor, table_name: str) -> bool:
    """Check if a table has a task_id column"""
    try:
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = [row[1] for row in cursor.fetchall()]
        return 'task_id' in columns
    except:
        return False


def cmd_export_task(task_id: str, output_dir: str = None):
    """Export all data for a specific task"""
    if output_dir is None:
        from core.config import get_config
        config = get_config()
        project_dir = Path(config.get("project_directory", "./project"))
        prizmfoundry_dir = project_dir / ".PrizmForge"
        prizmfoundry_dir.mkdir(parents=True, exist_ok=True)
        output_dir = prizmfoundry_dir / "agents_exports" / f"task_{task_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    cmd_export_db(output_dir, task_id)


def cmd_list_exports():
    """List available export directories"""
    from core.config import get_config
    config = get_config()
    project_dir = Path(config.get("project_directory", "./project"))
    exports_dir = project_dir / ".PrizmForge" / "agents_exports"

    if not exports_dir.exists():
        print("\n📦 No exports directory found\n")
        return
    
    exports = sorted([d for d in exports_dir.iterdir() if d.is_dir()], reverse=True)
    
    if not exports:
        print("\n📦 No exports found\n")
        return
    
    print(f"\n📦 Available Exports:")
    print("-" * 60)
    
    for export_dir in exports:
        # Count CSV files
        csv_files = list(export_dir.glob("*.csv"))
        
        # Get total size
        total_size = sum(f.stat().st_size for f in csv_files)
        size_mb = total_size / (1024 * 1024)
        
        print(f"\n📁 {export_dir.name}")
        print(f"   Files: {len(csv_files)}")
        print(f"   Size: {size_mb:.2f} MB")
        print(f"   Path: {export_dir.absolute()}")
    
    print()




def cmd_export_specific_tables(tables: list, output_dir: str = None, task_id: str = None):
    """Export specific tables to CSV"""
    
    if output_dir is None:
        from core.config import get_config
        config = get_config()
        project_dir = Path(config.get("project_directory", "./project"))
        prizmfoundry_dir = project_dir / ".PrizmForge"
        prizmfoundry_dir.mkdir(parents=True, exist_ok=True)
        output_dir = prizmfoundry_dir / "agents_exports" / f"custom_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"\n📦 Exporting Selected Tables")
    print("=" * 60)
    print(f"Tables: {', '.join(tables)}")
    print(f"Output: {output_dir.absolute()}")
    if task_id:
        print(f"Task ID: {task_id}")
    print()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        exported_count = 0
        total_rows = 0
        
        for table_name in tables:
            try:
                # Check if table exists
                cursor.execute("""
                    SELECT name FROM sqlite_master 
                    WHERE type='table' AND name=?
                """, (table_name,))
                
                if not cursor.fetchone():
                    print(f"  ⚠️  {table_name}: Table not found")
                    continue
                
                # Build query
                if task_id and table_has_task_id(cursor, table_name):
                    query = f"SELECT * FROM {table_name} WHERE task_id = ?"
                    cursor.execute(query, (task_id,))
                else:
                    query = f"SELECT * FROM {table_name}"
                    cursor.execute(query)
                
                rows = cursor.fetchall()
                
                if not rows:
                    print(f"  ⏭️  {table_name}: (empty)")
                    continue
                
                # Get column names
                column_names = [description[0] for description in cursor.description]
                
                # Write to CSV
                csv_file = output_dir / f"{table_name}.csv"
                with open(csv_file, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(column_names)
                    writer.writerows(rows)
                
                exported_count += 1
                total_rows += len(rows)
                print(f"  ✅ {table_name}: {len(rows)} rows")
                
            except Exception as e:
                print(f"  ❌ {table_name}: {e}")
            
    print()
    print(f"✅ Exported {exported_count} table(s), {total_rows:,} total rows")
    print(f"📁 {output_dir.absolute()}")
    print()

def cmd_archives(task_id: str = None):
    """Show archived context summaries"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        if task_id:
            cursor.execute("""
                SELECT turn_range, summary, key_decisions, files_modified, original_message_count, archived_at
                FROM archived_context
                WHERE task_id = ?
                ORDER BY archived_at
            """, (task_id,))
        else:
            cursor.execute("""
                SELECT task_id, turn_range, summary, key_decisions, files_modified, original_message_count, archived_at
                FROM archived_context
                ORDER BY archived_at DESC
                LIMIT 20
            """)
        
        archives = cursor.fetchall()
    
    if not archives:
        print(f"\n📚 No archived context found\n")
        return
    
    print(f"\n📚 Archived Context:")
    print("-" * 60)
    
    for archive in archives:
        if task_id:
            turn_range, summary, key_decisions, files_modified, msg_count, archived_at = archive
            print(f"\n⏰ {turn_range}")
        else:
            task, turn_range, summary, key_decisions, files_modified, msg_count, archived_at = archive
            print(f"\n📋 Task: {task} | {turn_range}")
        
        print(f"   Summary: {summary}")
        print(f"   Messages archived: {msg_count}")
        print(f"   Archived at: {archived_at[:19]}")
        
        try:
            decisions = json.loads(key_decisions)
            if decisions:
                print(f"   Key decisions: {', '.join(decisions[:3])}")
        except:
            pass
        
        try:
            files = json.loads(files_modified)
            if files:
                print(f"   Files: {', '.join(files[:5])}")
        except:
            pass
    
    print()

def cmd_review_status():
    """Show background agent review status"""
    with get_db_connection() as conn:
            
        cursor = conn.cursor()
        
        print(f"\n📊 Background Agent Review Status")
        print("=" * 60)
        
        for agent_name in ['jr_reviewer', 'jr_researcher', 'tech_writer']:
            print(f"\n🤖 {agent_name}:")
            
            # Get review statistics
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_reviews,
                    COUNT(DISTINCT file_path) as unique_files,
                    SUM(feedback_count) as total_feedback
                FROM agent_review_tracking
                WHERE agent_name = ?
            """, (agent_name,))
            
            stats = cursor.fetchone()
            total_reviews = stats[0]
            unique_files = stats[1]
            total_feedback = stats[2] or 0
            
            print(f"   Files reviewed: {unique_files}")
            print(f"   Total reviews: {total_reviews}")
            print(f"   Feedback items: {total_feedback}")
            
            # Get recently reviewed files
            cursor.execute("""
                SELECT file_path, last_reviewed_at, feedback_count
                FROM agent_review_tracking
                WHERE agent_name = ?
                ORDER BY last_reviewed_at DESC
                LIMIT 5
            """, (agent_name,))
            
            recent = cursor.fetchall()
            if recent:
                print(f"   Recent reviews:")
                for file_path, reviewed_at, count in recent:
                    print(f"     • {file_path} ({reviewed_at[:19]}, {count}x)")
        
        # Files never reviewed
        cursor.execute("""
            SELECT pf.file_path
            FROM project_files pf
            WHERE pf.is_binary = 0
            AND NOT EXISTS (
                SELECT 1 FROM agent_review_tracking art
                WHERE art.file_path = pf.file_path
            )
            LIMIT 10
        """)
        
        unreviewed = cursor.fetchall()
        if unreviewed:
            print(f"\n⚠️  Files never reviewed: {len(unreviewed)}")
            for file_path, in unreviewed[:5]:
                print(f"   • {file_path}")
        
    print()

def cmd_endpoints():
    """Show available endpoints and models"""
    from core.endpoint_manager import get_endpoint_manager
    
    endpoint_mgr = get_endpoint_manager()
    
    print(f"\n🌐 Available Endpoints:")
    print("=" * 60)
    
    for name, endpoint in endpoint_mgr.endpoints.items():
        print(f"\n📡 {name.upper()}")
        print(f"   URL: {endpoint.base_url}")
        print(f"   API Key: {endpoint.api_key_name}")
        print(f"   Description: {endpoint.description}")
        print(f"   Includes model in payload: {endpoint.include_model_in_payload}")
    
    print(f"\n\n📦 Available Models:")
    print("=" * 60)
    
    for model_name, model_info in endpoint_mgr.models.items():
        endpoint = model_info["endpoint"]
        config = model_info["config"]
        print(f"\n🤖 {model_name}")
        print(f"   Endpoint: {endpoint.name}")
        print(f"   Max tokens: {config.get('max_output_tokens')}")
        print(f"   Temperature: {config.get('temperature')}")
        print(f"   Description: {config.get('description')}")
    
    print(f"\n\n👥 Agent Assignments:")
    print("=" * 60)
    
    from core.config import get_config
    config = get_config()
    agent_prefs = config.get("agent_model_preferences", {})
    
    for agent_name, model_name in agent_prefs.items():
        model_info = endpoint_mgr.models.get(model_name)
        if model_info:
            endpoint = model_info["endpoint"]
            print(f"   {agent_name:<20} → {model_name:<30} ({endpoint.name})")
        else:
            print(f"   {agent_name:<20} → {model_name:<30} (⚠️ unknown)")
    
    print()

def cmd_endpoint_health():
    """Show endpoint health status"""
    from core.endpoint_manager import get_endpoint_manager
    
    endpoint_mgr = get_endpoint_manager()
    health_summary = endpoint_mgr.get_health_summary()
    
    print(f"\n🏥 Endpoint Health Status")
    print("=" * 80)
    
    for endpoint_name, health in health_summary.items():
        status_emoji = {
            "healthy": "✅",
            "rate_limited": "⏳",
            "token_exhausted": "💰",
            "key_locked": "🔒",
            "server_error": "⚠️",
            "unavailable": "❌"
        }.get(health["status"], "❓")
        
        available_text = "AVAILABLE" if health["available"] else "UNAVAILABLE"
        
        print(f"\n{status_emoji} {endpoint_name.upper()}: {available_text}")
        print(f"   Status: {health['status']}")
        print(f"   Error count: {health['error_count']}")
        print(f"   Consecutive failures: {health['consecutive_failures']}")
        
        if health['last_success']:
            from datetime import datetime
            last_success = datetime.fromisoformat(health['last_success'])
            time_since = datetime.now() - last_success
            minutes_ago = int(time_since.total_seconds() / 60)
            print(f"   Last success: {minutes_ago} minutes ago")
        
        if not health['available']:
            wait_seconds = health['seconds_until_available']
            wait_minutes = wait_seconds // 60
            print(f"   ⏰ Available in: {wait_minutes}m {wait_seconds % 60}s")
            
            if health['unavailable_until']:
                print(f"   Unavailable until: {health['unavailable_until'][:19]}")
    
    print("\n" + "=" * 80)
    
    # Show recommendations
    available_endpoints = endpoint_mgr.get_available_endpoints()
    if available_endpoints:
        print(f"\n✅ {len(available_endpoints)} endpoint(s) currently available:")
        for ep in available_endpoints:
            print(f"   • {ep.name} (priority: {ep.priority})")
    else:
        print(f"\n❌ NO ENDPOINTS CURRENTLY AVAILABLE")
        print(f"   All endpoints are experiencing issues or in cooldown")
    
    print()

def cmd_reports(task_id: str = None):
    """List generated reports"""
    from core.config import get_config
    config = get_config()
    project_dir = Path(config.get("project_directory", "./project"))
    reports_dir = project_dir / ".PrizmForge" / "reports"
    
    if not reports_dir.exists():
        print("\n📊 No reports directory found\n")
        return
    
    reports = sorted(reports_dir.glob("project_report_*.md"), reverse=True)
    
    if not reports:
        print("\n📊 No reports found\n")
        return
    
    print(f"\n📊 Available Reports ({len(reports)}):")
    print("-" * 60)
    
    for report in reports[:20]:  # Show last 20
        # Get file stats
        stat = report.stat()
        size_kb = stat.st_size / 1024
        modified = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")
        
        print(f"\n📄 {report.name}")
        print(f"   Modified: {modified}")
        print(f"   Size: {size_kb:.1f} KB")
        print(f"   Path: {report}")
    
    print()

def cmd_show_report(report_name: str = None):
    """Show a specific report or the latest"""
    from core.config import get_config
    config = get_config()
    project_dir = Path(config.get("project_directory", "./project"))
    reports_dir = project_dir / ".PrizmForge" / "reports"
    
    if not reports_dir.exists():
        print("\n📊 No reports directory found\n")
        return
    
    if report_name:
        report_path = reports_dir / report_name
    else:
        # Get latest report
        reports = sorted(reports_dir.glob("project_report_*.md"), reverse=True)
        if not reports:
            print("\n📊 No reports found\n")
            return
        report_path = reports[0]
    
    if not report_path.exists():
        print(f"\n❌ Report not found: {report_path.name}\n")
        return
    
    print(f"\n{'='*60}")
    print(f"📊 {report_path.name}")
    print(f"{'='*60}\n")
    
    content = report_path.read_text(encoding='utf-8')
    print(content)
    print()


def cmd_resource_status():
    """Show resource controller status"""
    from agents.resource_controller_worker import get_resource_controller
    
    try:
        rc = get_resource_controller()
        
        print(f"\n⚖️  Resource Controller Status")
        print("=" * 70)
        
        # Current decision
        decision = rc.get_current_decision()
        if decision:
            print(f"\nCurrent Mode: {decision.level}")
            print(f"  Active agents: {', '.join(decision.active_agents)}")
            print(f"  Feeder interval: {decision.background_feeder_interval}s")
            print(f"  Rate limit: {decision.rate_limit_per_minute} calls/min")
            if decision.model_downgrades:
                print(f"  Model downgrades: {len(decision.model_downgrades)}")
            print(f"\n  Reasoning: {decision.reasoning}")
        else:
            print("\n  No decision made yet (waiting for first check)")
        
        # Agent statistics (learned performance)
        stats = rc.get_agent_statistics()
        if stats:
            print(f"\n📊 Agent Performance (Learned):")
            print(f"{'Agent':<20} {'Calls':>6} {'Feedback':>9} {'Per Call':>9} {'Tokens':>8} {'Value':>6}")
            print("-" * 70)
            
            # Sort by value score descending
            sorted_agents = sorted(stats.items(), key=lambda x: x[1]['value_score'], reverse=True)
            
            for agent_name, agent_stats in sorted_agents:
                print(f"{agent_name:<20} {agent_stats['calls']:>6} "
                      f"{agent_stats['feedback_generated']:>9} "
                      f"{agent_stats['feedback_per_call']:>9.2f} "
                      f"{agent_stats['avg_tokens']:>8} "
                      f"{agent_stats['value_score']:>6.2f}")
        
        # Recent decisions
        history = rc.get_decision_history(limit=5)
        if len(history) > 1:
            print(f"\n📜 Recent Decisions:")
            for i, dec in enumerate(reversed(history), 1):
                print(f"  {i}. {dec.level}: {', '.join(dec.active_agents)}")
        
        print()
        
    except Exception as e:
        print(f"\n❌ Error getting resource status: {e}\n")

def cmd_json_parse_stats():
    """Show JSON parsing statistics"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Get parse failures
        cursor.execute("""
            SELECT agent_name, COUNT(*) as failures
            FROM agent_responses_archive
            WHERE parse_success = 0
            GROUP BY agent_name
            ORDER BY failures DESC
        """)
        failures = cursor.fetchall()
        
        # Get total responses
        cursor.execute("""
            SELECT agent_name, COUNT(*) as total
            FROM agent_responses_archive
            GROUP BY agent_name
        """)
        totals = dict(cursor.fetchall())
    
    print(f"\n📊 JSON Parsing Statistics")
    print("=" * 60)
    
    if not failures:
        print("✅ No parse failures detected\n")
        return
    
    print(f"\n{'Agent':<20} {'Failures':>10} {'Total':>10} {'Rate':>10}")
    print("-" * 60)
    
    for agent_name, failure_count in failures:
        total = totals.get(agent_name, failure_count)
        rate = (failure_count / total) * 100 if total > 0 else 0
        print(f"{agent_name:<20} {failure_count:>10} {total:>10} {rate:>9.1f}%")
    
    print()

def cmd_task_progress(task_id: str):
    """Show real-time task progress"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Recent file modifications
        cursor.execute("""
            SELECT file_path, operation, changed_by, timestamp
            FROM file_modifications
            WHERE task_id = ?
            ORDER BY timestamp DESC
            LIMIT 10
        """, (task_id,))
        mods = cursor.fetchall()
        
        # Agent activity
        cursor.execute("""
            SELECT agent_name, COUNT(*) as calls
            FROM agent_responses_archive
            WHERE task_id = ?
            GROUP BY agent_name
        """, (task_id,))
        activity = cursor.fetchall()
        
        # Unaddressed critical issues
        cursor.execute("""
            SELECT COUNT(*) FROM agent_feedback
            WHERE task_id = ? AND addressed = 0 
            AND priority IN ('CRITICAL', 'HIGH')
        """, (task_id,))
        critical_count = cursor.fetchone()[0]
    
    print(f"\n📊 Task Progress: {task_id}")
    print("=" * 60)
    
    print(f"\n📝 Recent File Changes:")
    if mods:
        for file_path, operation, changed_by, timestamp in mods:
            print(f"  {timestamp[:19]} | {operation:6} | {file_path}")
            print(f"                      by {changed_by}")
    else:
        print("  ⚠️  No files changed yet")
    
    print(f"\n🤖 Agent Activity:")
    if activity:
        for agent, calls in activity:
            print(f"  {agent:20} {calls:3} calls")
    
    print(f"\n⚠️  Unaddressed Issues: {critical_count} CRITICAL/HIGH")
    print()

def cmd_help():
    """Show help"""
    print("""
╔════════════════════════════════════════════════════════════════╗
║  MULTI-AGENT GEMINI SYSTEM - HELP                              ║
╚════════════════════════════════════════════════════════════════╝

📁 PROJECT COMMANDS:
  init              - Scan and index project files
  files             - List all indexed files
  project           - Show project info
  endpoints         - Show available API endpoints and models
  health            - Show endpoint health status and availability
  
🤖 TASK COMMANDS:
  <describe task>   - Start a new task
  feedback <id>     - Show feedback for task
  show_prompt <id>  - Show prompts sent to agents
  show_prompt <id> <agent> - Show prompts for specific agent
  
📊 REPORTS & MONITORING:
  reports           - List all generated reports
  report            - Show latest report
  report <name>     - Show specific report
  resource_status   - Show resource controller status
  review_status     - Show background agent activity
  
📊 SYSTEM COMMANDS:
  status            - Show token usage
  history [N]       - Show recent tasks
  help              - Show this help
  quit              - Exit

📦 EXPORT COMMANDS:
  export                    - Export all tables to CSV (timestamped)
  export <task_id>          - Export all data for specific task
  export <task_id> <dir>    - Export task data to specific directory
  export_tables <tables>    - Export specific tables (comma-separated)
  export_tables <tables> <task_id> - Export tables filtered by task
  list_exports              - List available export directories

💡 EXAMPLES:
  • init
  • build a Flask REST API
  • feedback task_001
  • reports
  • report
  • resource_status
  • show_prompt task_001 reviewer
  • export task_001
  • export_tables messages,agent_feedback task_001
  • list_exports
""")
    
# Append dynamic token URLs
from core.config import get_config
config = get_config()
print("🌐 Where to get your tokens:")
for ep_name, ep_config in config.get("endpoints", {}).items():
    key_name = ep_config.get("api_key_name", ep_name)
    key_url = ep_config.get("key_management_url", "Contact system administrator")
    print(f"  • {key_name}: {key_url}")
print("\n")