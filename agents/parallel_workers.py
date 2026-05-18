"""Parallel background agent workers with continuous file feeding"""
import threading
import queue
import time
import uuid
import random
import sqlite3
from typing import Optional, List, Dict
from dataclasses import dataclass
from datetime import datetime

from core.agent_schemas import get_schema, validate_agent_response, is_using_fallback
from core.db import get_db_path
from core.db_helpers import save_agent_feedback, post_message
from core.file_operations import get_file_content_from_db, format_file_for_agent, compute_file_hash
        
@dataclass
class FileChangeEvent:
    """File change event"""
    event_id: str
    file_path: str
    operation: str
    content: Optional[str]
    content_hash: Optional[str]
    metadata: Optional[Dict]
    task_id: str
    timestamp: str
    priority: int = 5  # 1=highest, 10=lowest

class BackgroundAgentPool:
    def __init__(self):
        from core.config import get_config

        self.event_queue = queue.Queue()
        self.workers = []
        self.feeder_thread = None
        self.running = False
        self.task_id = None
        self.recently_queued = {}
        self.active_agents_filter = None  # None = all active        
        
        # ✅ Load agent configurations from config
        config = get_config()
        
        self.agent_configs = config.get("background_agents", {})
        self.feeder_config = config.get("background_feeder", {})
        self.feeder_interval = self.feeder_config.get("interval_seconds", 30)
        self.base_feeder_interval = self.feeder_interval  # Store original
        
        # ✅ Categorize agents by behavior
        self.modification_agents = []      # Review on every file change
        self.random_review_agents = []     # Periodic random review
        
        for agent_name, agent_config in self.agent_configs.items():
            if not agent_config.get("enabled", True):
                continue
            
            if agent_config.get("on_modification", False):
                self.modification_agents.append(agent_name)
            
            if agent_config.get("random_review", False):
                self.random_review_agents.append(agent_name)

    def start(self, task_id: str):
        """Start background workers with granular configuration"""
        if self.running:
            return
        
        self.running = True
        self.task_id = task_id
        
        # Get all unique agents (modification + random review)
        all_agents = set(self.modification_agents + self.random_review_agents)
        
        if not all_agents:
            print("    ⚠️  No background agents enabled")
            return
        
        # Initialize tracking
        self.recently_queued = {agent: set() for agent in all_agents}
        
        # Start workers
        for agent_name in all_agents:
            worker = threading.Thread(
                target=self._worker_loop,
                args=(agent_name,),
                daemon=True,
                name=f"{agent_name}-worker"
            )
            worker.start()
            self.workers.append(worker)
            
            config = self.agent_configs.get(agent_name, {})
            mod_flag = "on_mod" if config.get("on_modification") else ""
            random_flag = "random" if config.get("random_review") else ""
            flags = f"[{mod_flag}+{random_flag}]" if mod_flag and random_flag else f"[{mod_flag or random_flag}]"
            
            print(f"    🤖 Started {agent_name} worker {flags}")
        
        # Start support workers
        self._start_support_workers(task_id)
        
        # Queue all files for initial review
        self._queue_all_files_for_initial_review()
        
        # Queue modified files (only to modification_agents)
        self._queue_modified_files()
        
        # Start random file feeder (only if agents want it)
        if self.random_review_agents:
            self.feeder_thread = threading.Thread(
                target=self._file_feeder_loop,
                daemon=True,
                name="file-feeder"
            )
            self.feeder_thread.start()
            print(f"    🔄 Started continuous file feeder for {len(self.random_review_agents)} agent(s)")

    def stop(self):
        """Stop all workers including feeder, archivist, prioritizer, reporter, and resource controller"""
        self.running = False
        
        # Stop file feeder
        if self.feeder_thread:
            self.feeder_thread.join(timeout=2.0)
        
        # Stop file analysis workers
        for worker in self.workers:
            worker.join(timeout=2.0)
        self.workers.clear()

        # circular references require lazy loading here instead of top of file
        from agents.archivist_worker import get_archivist_worker
        from agents.prioritizer_worker import get_prioritizer_worker
        from agents.reporter_worker import get_reporter_worker
        from agents.resource_controller_worker import get_resource_controller

        # Stop support workers
        get_archivist_worker().stop()
        get_prioritizer_worker().stop()
        get_reporter_worker().stop()
        get_resource_controller().stop()
        
        # Clear tracking
        self.recently_queued.clear()
        
        print(f"    🛑 Stopped background workers")

    def _start_support_workers(self, task_id: str):
        """Start archivist, prioritizer, reporter, resource controller"""     
        # circular references require lazy loading here instead of top of file
        from agents.archivist_worker import get_archivist_worker
        from agents.prioritizer_worker import get_prioritizer_worker
        from agents.reporter_worker import get_reporter_worker
        from agents.resource_controller_worker import get_resource_controller


        get_archivist_worker().start(task_id)
        get_prioritizer_worker().start(task_id)
        get_reporter_worker().start(task_id)
        get_resource_controller().start(task_id)

    def _queue_all_files_for_initial_review(self):
        """Queue ALL project files for initial review when task starts"""
        try:
            conn = sqlite3.connect(get_db_path())
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT 
                    pf.file_path,
                    pf.content,
                    pf.content_hash,
                    pf.last_modified,
                    pf.size_bytes,
                    pf.file_type,
                    fs.summary,
                    fs.purpose,
                    fs.line_count
                FROM project_files pf
                LEFT JOIN file_summaries fs ON pf.file_path = fs.file_path
                WHERE pf.is_binary = 0
                ORDER BY pf.last_modified DESC
            """)
            
            all_files = cursor.fetchall()
            conn.close()
            
            if not all_files:
                print(f"    ⚠️  No files found for initial review")
                return
            
            queued_count = 0
            
            # Queue all files for each agent
            for agent_name in (self.modification_agents + self.random_review_agents):
                for file_data in all_files:
                    event = self._create_file_event(file_data, "initial_review", priority=3)
                    self.event_queue.put(event)
                    queued_count += 1
            
            print(f"    🔍 Queued {queued_count} files for initial peer review")
            
        except Exception as e:
            print(f"    ⚠️  Error queuing files for initial review: {e}")

    def _queue_modified_files(self):
        """Queue files modified since last review - only to modification_agents"""
        try:
            conn = sqlite3.connect(get_db_path())
            cursor = conn.cursor()
            
            queued_count = 0
            
            # ✅ Only queue to modification_agents
            for agent_name in self.modification_agents:
                cursor.execute("""
                    SELECT 
                        pf.file_path,
                        pf.content,
                        pf.content_hash,
                        pf.last_modified,
                        pf.size_bytes,
                        pf.file_type,
                        fs.summary,
                        fs.purpose,
                        fs.line_count,
                        art.last_reviewed_at,
                        art.content_hash_reviewed
                    FROM project_files pf
                    LEFT JOIN file_summaries fs ON pf.file_path = fs.file_path
                    LEFT JOIN agent_review_tracking art ON pf.file_path = art.file_path 
                        AND art.agent_name = ?
                    WHERE pf.is_binary = 0
                    AND (
                        art.last_reviewed_at IS NULL
                        OR pf.last_modified > art.last_reviewed_at
                        OR pf.content_hash != art.content_hash_reviewed
                    )
                    ORDER BY pf.last_modified DESC
                """, (agent_name,))
                
                modified_files = cursor.fetchall()
                
                for file_data in modified_files:
                    event = self._create_file_event(file_data, "modified_since_review", priority=1)
                    self.event_queue.put(event)
                    self.recently_queued[agent_name].add(file_data[0])
                    queued_count += 1
            
            conn.close()
            
            if queued_count > 0:
                print(f"    🔥 Queued {queued_count} modified file(s) for {len(self.modification_agents)} agent(s)")
        
        except Exception as e:
            print(f"    ⚠️  Error queuing modified files: {e}")

    def _file_feeder_loop(self):
        """Feed random files to agents that want them"""
        while self.running:
            try:
                # ✅ NEW: Dynamic interval based on queue size
                queue_size = self.event_queue.qsize()
                self._adjust_feeder_interval(queue_size)
                
                time.sleep(self.feeder_interval)
                
                if not self.running:
                    break
                
                # ✅ Only feed to random_review_agents
                self._feed_random_files()
                
            except Exception as e:
                print(f"    ⚠️  File feeder error: {e}")
                time.sleep(60)

    def _adjust_feeder_interval(self, queue_size: int):
        """
        ✅ NEW: Adjust feeding interval based on queue backlog
        Implements backpressure to prevent overwhelming agents
        """
        if queue_size < 10:
            # Normal operation
            self.feeder_interval = self.base_feeder_interval
        elif queue_size < 50:
            # Slight slowdown
            self.feeder_interval = self.base_feeder_interval * 1.5
        elif queue_size < 100:
            # Significant slowdown
            self.feeder_interval = self.base_feeder_interval * 3
        else:
            # Heavy backlog - pause feeding
            self.feeder_interval = self.base_feeder_interval * 10
            if queue_size > 150:
                print(f"    ⚠️  Queue backlog: {queue_size} items. Slowing feeder to {self.feeder_interval}s")

    def _feed_random_files(self):
        """Feed random files to agents with random_review=true"""
        try:
            conn = sqlite3.connect(get_db_path())
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT 
                    pf.file_path,
                    pf.content,
                    pf.content_hash,
                    pf.last_modified,
                    pf.size_bytes,
                    pf.file_type,
                    fs.summary,
                    fs.purpose,
                    fs.line_count
                FROM project_files pf
                LEFT JOIN file_summaries fs ON pf.file_path = fs.file_path
                WHERE pf.is_binary = 0
            """)
            
            all_files = cursor.fetchall()
            conn.close()
            
            if not all_files:
                return
            
            # ✅ Feed to each random_review agent with its configured file count
            for agent_name in self.random_review_agents:
                agent_config = self.agent_configs.get(agent_name, {})
                files_per_cycle = agent_config.get(
                    "random_files_per_cycle",
                    self.feeder_config.get("files_per_agent_default", 3)
                )
                
                available_files = [
                    f for f in all_files 
                    if f[0] not in self.recently_queued.get(agent_name, set())
                ]
                
                if not available_files:
                    self.recently_queued[agent_name].clear()
                    available_files = all_files
                
                selected_files = random.sample(
                    available_files, 
                    min(files_per_cycle, len(available_files))
                )
                
                for file_data in selected_files:
                    event = self._create_file_event(file_data, "random_review", priority=7)
                    self.event_queue.put(event)
                    self.recently_queued[agent_name].add(file_data[0])
            
            print(f"    🎲 Fed random files to {len(self.random_review_agents)} agent(s)")
            
        except Exception as e:
            print(f"    ⚠️  Error feeding random files: {e}")

    def _create_file_event(self, file_data: tuple, operation: str, priority: int) -> FileChangeEvent:
        """Helper to create file event from database row"""
        return FileChangeEvent(
            event_id=str(uuid.uuid4()),
            file_path=file_data[0],
            operation=operation,
            content=file_data[1],
            content_hash=file_data[2],
            metadata={
                "last_modified": file_data[3],
                "size_bytes": file_data[4],
                "file_type": file_data[5],
                "summary": file_data[6],
                "purpose": file_data[7],
                "line_count": file_data[8]
            },
            task_id=self.task_id,
            timestamp=datetime.now().isoformat(),
            priority=priority
        )

    def queue_file_change(self, file_path: str, operation: str, content: Optional[str]):
        """Queue a file change for immediate processing - only to modification_agents"""
        try:
            content_hash = compute_file_hash(content) if content else None
            
            conn = sqlite3.connect(get_db_path())
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    pf.last_modified, pf.size_bytes, pf.file_type,
                    fs.summary, fs.purpose, fs.line_count
                FROM project_files pf
                LEFT JOIN file_summaries fs ON pf.file_path = fs.file_path
                WHERE pf.file_path = ?
            """, (file_path,))
            
            result = cursor.fetchone()
            conn.close()
            
            if result:
                metadata = {
                    "last_modified": result[0],
                    "size_bytes": result[1],
                    "file_type": result[2],
                    "summary": result[3],
                    "purpose": result[4],
                    "line_count": result[5]
                }
            else:
                metadata = None
        except:
            content_hash = None
            metadata = None
        
        event = FileChangeEvent(
            event_id=str(uuid.uuid4()),
            file_path=file_path,
            operation=operation,
            content=content,
            content_hash=content_hash,
            metadata=metadata,
            task_id=self.task_id,
            timestamp=datetime.now().isoformat(),
            priority=1  # HIGHEST priority
        )
        
        # ✅ Only queue to modification_agents
        self.event_queue.put(event)
        
        # Mark as recently queued for modification agents only
        for agent_name in self.modification_agents:
            if agent_name in self.recently_queued:
                self.recently_queued[agent_name].add(file_path)
        
        print(f"    📤 Queued {file_path} for {len(self.modification_agents)} modification agent(s)")

    def _worker_loop(self, agent_name: str):
        """Main worker loop for an agent"""
        while self.running:
            # ✅ CHECK IF AGENT IS ACTIVE
            if self.active_agents_filter is not None:
                if agent_name not in self.active_agents_filter:
                    time.sleep(5)  # Sleep and check again
                    continue
            
            try:
                event = self.event_queue.get(timeout=1.0)
            except queue.Empty:
                continue
            
            if event.content is None:
                continue
            
            self._process_file(agent_name, event)
    def _process_file(self, agent_name: str, event: FileChangeEvent):
        from agents.base import call_agent

        """Process a file with an agent"""
        try:
            # Format file with metadata
            file_formatted = format_file_for_agent(event.file_path, event.content)
            
            # Build metadata context
            metadata_str = ""
            if event.metadata:
                metadata_str = f"\n**File Metadata:**\n"
                if event.metadata.get("purpose"):
                    metadata_str += f"- Purpose: {event.metadata['purpose']}\n"
                if event.metadata.get("line_count"):
                    metadata_str += f"- Lines: {event.metadata['line_count']}\n"
                if event.metadata.get("last_modified"):
                    metadata_str += f"- Modified: {event.metadata['last_modified'][:19]}\n"
            
            # Build operation description
            op_descriptions = {
                "modified_since_review": "modified since your last review",
                "random_review": "selected for periodic review",
                "initial_review": "initial review",
                "create": "newly created",
                "modify": "just modified"
            }
            operation_desc = op_descriptions.get(event.operation, event.operation)
            
            prompt = f"""File {operation_desc}: {event.file_path}
        {metadata_str}
        {file_formatted}

        Analyze and provide feedback in JSON format."""
            
            # ✅ Get model from agent config
            agent_config = self.agent_configs.get(agent_name, {})
            model_override = agent_config.get("model")  # optional
            
            response = call_agent(agent_name, prompt, event.task_id, 
                                model_override=model_override)
            
            if not response:
                return
            
            # Parse and save feedback
            self._parse_and_save_feedback(agent_name, event, response)
            
            # Update review tracking
            self._update_review_tracking(agent_name, event)
            
        except Exception as e:
            print(f"    ⚠️  {agent_name} error on {event.file_path}: {e}")

    def _parse_and_save_feedback(self, agent_name: str, event: FileChangeEvent, response: str):
        """Parse response and save feedback - FLEXIBLE version"""
        from core.json_parser import parse_json_response

        try:
            # Parse JSON with non-strict mode
            data = parse_json_response(
                response,
                expected_keys=None,  # ✅ Don't require specific keys
                strict=False,
                agent_name=agent_name
            )
            
            if not data:
                return  # Logged by parser
            
            # ✅ FLEXIBLE: Try multiple possible field names for arrays
            items = None
            array_field_names = [
                # Try schema-defined name first
                "findings", "suggestions", "documentation_issues", "issues", "security_findings",
                # Then try generic names
                "items", "results", "feedback", "observations", "recommendations"
            ]
            
            for field_name in array_field_names:
                if field_name in data and isinstance(data[field_name], list):
                    items = data[field_name]
                    print(f"    ℹ️  {agent_name}: Found items in '{field_name}' field")
                    break
            
            # ✅ FALLBACK: If no array found, wrap entire response as single item
            if items is None or len(items) == 0:
                # Check if response has fields that look like a single finding
                if any(key in data for key in ["priority", "message", "issue", "finding"]):
                    items = [data]  # Treat entire response as one item
                    print(f"    ℹ️  {agent_name}: Treating entire response as single item")
                else:
                    print(f"    ⚠️  {agent_name}: No actionable items found in response")
                    return
            
            # ✅ FLEXIBLE: Extract fields with multiple possible names
            saved_count = 0
            for item in items:
                if not isinstance(item, dict):
                    continue
                
                # Extract priority (try multiple field names)
                priority = (
                    item.get("priority") or 
                    item.get("severity") or 
                    item.get("level") or 
                    "MEDIUM"
                ).upper()
                
                # Normalize priority values
                priority_map = {
                    "CRITICAL": "CRITICAL",
                    "URGENT": "CRITICAL",
                    "HIGH": "HIGH",
                    "IMPORTANT": "HIGH",
                    "MEDIUM": "MEDIUM",
                    "MODERATE": "MEDIUM",
                    "LOW": "LOW",
                    "MINOR": "LOW",
                    "INFO": "LOW"
                }
                priority = priority_map.get(priority, "MEDIUM")
                
                # Extract category (try multiple field names)
                category = (
                    item.get("category") or 
                    item.get("type") or 
                    item.get("kind") or 
                    "other"
                ).lower()
                
                # Extract message (try multiple field names)
                message = (
                    item.get("message") or 
                    item.get("issue") or 
                    item.get("description") or 
                    item.get("finding") or 
                    item.get("observation") or
                    str(item)  # Last resort: stringify the item
                )
                
                # Extract suggestion (optional, try multiple field names)
                suggestion = (
                    item.get("suggestion") or 
                    item.get("fix") or 
                    item.get("recommendation") or 
                    item.get("solution") or
                    ""
                )
                
                # ✅ REQUIRE: Must have at least a message
                if not message or len(str(message)) < 10:
                    continue
                
                # Save to database
                save_agent_feedback(
                    agent_name, event.file_path, priority, category,
                    str(message)[:1000],  # Truncate if too long
                    str(suggestion)[:1000] if suggestion else None,
                    event.task_id, event.event_id
                )
                saved_count += 1
                
                # Post high priority to orchestrator immediately
                if priority in ["CRITICAL", "HIGH"]:
                    post_message(
                        agent_name, "orchestrator",
                        f"[{priority}] {event.file_path}: {str(message)[:100]}",
                        event.task_id, priority
                    )
            
            if saved_count > 0:
                print(f"    ✅ {agent_name} posted {saved_count} feedback item(s)")
            else:
                print(f"    ℹ️  {agent_name}: Response parsed but no valid items extracted")
                        
        except Exception as e:
            print(f"    ⚠️  {agent_name}: Error processing response: {e}")
            import traceback
            traceback.print_exc()
                    
    def _update_review_tracking(self, agent_name: str, event: FileChangeEvent):
        """Update when this agent last reviewed this file"""
        try:
            conn = sqlite3.connect(get_db_path())
            conn.execute("""
                INSERT INTO agent_review_tracking 
                (agent_name, file_path, last_reviewed_at, content_hash_reviewed, feedback_count)
                VALUES (?, ?, ?, ?, 1)
                ON CONFLICT(agent_name, file_path) DO UPDATE SET
                    last_reviewed_at = excluded.last_reviewed_at,
                    content_hash_reviewed = excluded.content_hash_reviewed,
                    feedback_count = feedback_count + 1
            """, (agent_name, event.file_path, datetime.now().isoformat(), event.content_hash))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"    ⚠️  Error updating review tracking: {e}")


# Global pool
_agent_pool = None

def get_agent_pool() -> BackgroundAgentPool:
    """Get global agent pool"""
    global _agent_pool
    if _agent_pool is None:
        _agent_pool = BackgroundAgentPool()
    return _agent_pool

def set_feeder_interval(self, interval: int):
    """Dynamically adjust feeder interval (called by resource controller)"""
    self.feeder_interval = interval
    print(f"    🎛️  Feeder interval adjusted to {interval}s")

def set_active_agents(self, active_agents: List[str]):
    """Enable/disable specific agents (called by resource controller)"""
    # Disable agents not in active list
    for agent_name in self.recently_queued.keys():
        if agent_name not in active_agents and agent_name != "prioritizer":
            print(f"    🔇 Disabled {agent_name} (resource conservation)")
            # Stop feeding this agent
            # (Implementation: add a self.disabled_agents set)
    
    # Re-enable agents in active list
    for agent_name in active_agents:
        if agent_name in self.recently_queued:
            print(f"    🔊 Re-enabled {agent_name}")

    self.active_agents_filter = set(active_agents)

def force_review_cycle(self, file_limit: int = 8):
    """
    Force background agents to review files immediately.
    
    This is typically called when the orchestrator yields control 
    (`next_agent == "background"`). It:
    - Temporarily lifts resource restrictions
    - Actively queues files for review by all background agents
    - Uses higher priority so agents process them quickly
    """
    print("🔄 Forcing background review cycle...")

    if not self.running:
        print("    ⚠️  Background agents are not running")
        return

    try:
        # 1. Temporarily lift resource controller restrictions
        try:
            from agents.resource_controller_worker import get_resource_controller
            rc = get_resource_controller()
            rc.temporarily_disable_throttling(duration_seconds=45)
            print("    🔓 Resource restrictions temporarily lifted for this cycle")
        except Exception:
            pass  # Resource controller may not be active

        # 2. Fetch files to review (modified files first, then random)
        conn = sqlite3.connect(get_db_path())
        cursor = conn.cursor()

        # Get recently modified files (higher value)
        cursor.execute("""
            SELECT file_path, content, content_hash, last_modified, size_bytes, file_type
            FROM project_files 
            WHERE is_binary = 0
            ORDER BY last_modified DESC
            LIMIT ?
        """, (file_limit // 2 + 1,))
        modified_files = cursor.fetchall()

        # Get random files for broader coverage
        cursor.execute("""
            SELECT file_path, content, content_hash, last_modified, size_bytes, file_type
            FROM project_files 
            WHERE is_binary = 0
            ORDER BY RANDOM()
            LIMIT ?
        """, (file_limit // 2,))
        random_files = cursor.fetchall()
        conn.close()

        all_files = modified_files + random_files

        if not all_files:
            print("    ⚠️  No files available to review")
            return

        # 3. Queue files for all active background agents
        queued_count = 0
        all_agents = list(set(self.modification_agents + self.random_review_agents))

        for file_data in all_files:
            event = FileChangeEvent(
                event_id=str(uuid.uuid4()),
                file_path=file_data[0],
                operation="forced_review",
                content=file_data[1],
                content_hash=file_data[2],
                metadata={
                    "last_modified": file_data[3],
                    "size_bytes": file_data[4],
                    "file_type": file_data[5]
                },
                task_id=self.task_id,
                timestamp=datetime.now().isoformat(),
                priority=2  # High priority (1 = highest)
            )
            self.event_queue.put(event)
            queued_count += 1

        print(f"    ✅ Queued {queued_count} files for forced review by background agents")
        print(f"    📤 Background agents will now analyze and post suggestions to the message bus")

    except Exception as e:
        print(f"    ❌ Error during forced review cycle: {e}")