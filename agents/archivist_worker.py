"""Background archivist - monitors, archives, and restores context"""
import threading
import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional

from agents.base import call_agent
from core.db_helpers import post_message
from core.config import get_config
from core.db_connection import get_db_connection

class ArchivistWorker:
    """
    Background worker that manages message bus and conversation history archival
    
    DOES NOT TOUCH:
    - project_files (file contents in database)
    - file_summaries (file metadata)
    - file_metadata_bus (file change notifications)
    - Actual files on disk
    
    ONLY MANAGES:
    - messages (message bus between agents)
    - conversation_history (agent conversation logs)
    """
    
    def __init__(self):
        self.running = False
        self.worker_thread = None
        self.current_task_id = None
        self.last_archive_check = time.time()
        self.last_restore_check = time.time()
        self.archive_interval = 300  # 5 minutes
        self.restore_interval = 60   # 1 minute
    
    def start(self, task_id: str):
        """Start the archivist worker"""
        if self.running:
            return
        
        self.running = True
        self.current_task_id = task_id
        self.worker_thread = threading.Thread(
            target=self._worker_loop,
            daemon=True,
            name="archivist-worker"
        )
        self.worker_thread.start()
        print(f"    📚 Started archivist worker (message bus & conversation only)")
    
    def stop(self):
        """Stop the archivist worker"""
        self.running = False
        if self.worker_thread:
            self.worker_thread.join(timeout=2.0)
        print(f"    📚 Stopped archivist worker")
    
    def _worker_loop(self):
        """Main worker loop"""
        while self.running:
            try:
                current_time = time.time()
                
                # Archive old messages periodically
                if current_time - self.last_archive_check >= self.archive_interval:
                    self._archive_old_messages()
                    self._archive_old_conversations()
                    self.last_archive_check = current_time
                
                # Check if we need to restore context periodically
                if current_time - self.last_restore_check >= self.restore_interval:
                    self._check_for_restore_requests()
                    self.last_restore_check = current_time
                
                # Sleep to avoid busy waiting
                time.sleep(30)  # Check every 30 seconds
                
            except Exception as e:
                print(f"    ⚠️  Archivist error: {e}")
                time.sleep(60)
    
    def _archive_old_messages(self):
        """
        Archive old READ messages from the message bus ONLY
        Does NOT touch file_metadata_bus or file-related tables
        """
        try:

            with get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Find old read messages from MESSAGE BUS only (older than 10 minutes)
                cutoff_time = (datetime.now() - timedelta(minutes=10)).isoformat()
                
                cursor.execute("""
                    SELECT id, from_agent, to_agent, content, timestamp, priority, task_id
                    FROM messages
                    WHERE read = 1 AND timestamp < ? AND task_id = ?
                    ORDER BY timestamp
                """, (cutoff_time, self.current_task_id))
                
                old_messages = cursor.fetchall()
                
                if len(old_messages) < 5:  # Only archive if we have enough messages
                    return
                
                print(f"    📦 Archiving {len(old_messages)} read messages from message bus...")
                
                # Build messages list
                messages = []
                for msg in old_messages:
                    messages.append({
                        "id": msg[0],
                        "from": msg[1],
                        "to": msg[2],
                        "content": msg[3],
                        "timestamp": msg[4],
                        "priority": msg[5],
                        "task_id": msg[6]
                    })
                
                # Build summary prompt
                summary_prompt = self._build_message_archive_prompt(messages)
                
                # Call archivist agent
                response = call_agent("archivist", summary_prompt, self.current_task_id)
                
                if response:
                    # Save archive
                    self._save_message_archive(self.current_task_id, messages, response)
                    
                    # Delete archived messages from bus
                    message_ids = [msg["id"] for msg in messages]
                    placeholders = ','.join('?' * len(message_ids))
                    cursor.execute(f"DELETE FROM messages WHERE id IN ({placeholders})", message_ids)
                    
                    print(f"    ✅ Archived and cleaned {len(messages)} messages from bus")
                
                
            
        except Exception as e:
            print(f"    ❌ Message archive error: {e}")
    
    def _archive_old_conversations(self):
        """
        Archive old conversation_history entries ONLY
        Does NOT touch file contents or metadata
        """
        try:

            with get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Count conversation entries for this task
                cursor.execute("""
                    SELECT COUNT(*) FROM conversation_history WHERE task_id = ?
                """, (self.current_task_id,))
                
                count = cursor.fetchone()[0]
                
                # ============= FIX: Only archive if we have MANY entries =============
                if count < 30:  # Raised threshold from 20 to 30
                    return
                
                # Keep last 15 entries active, archive older ones
                # But only if we haven't archived recently
                cursor.execute("""
                    SELECT MAX(archived_at) FROM archived_context WHERE task_id = ?
                """, (self.current_task_id,))
                
                last_archive = cursor.fetchone()[0]
                
                # Don't archive more than once per 10 minutes
                if last_archive:
                    from datetime import datetime, timedelta
                    last_time = datetime.fromisoformat(last_archive)
                    if datetime.now() - last_time < timedelta(minutes=10):
                        return
                # =====================================================================
                
                # Keep last 15 entries, archive the rest IN ONE BATCH
                cursor.execute("""
                    SELECT id, agent, role, content, timestamp
                    FROM conversation_history
                    WHERE task_id = ?
                    ORDER BY timestamp
                    LIMIT ?
                """, (self.current_task_id, max(0, count - 15)))
                
                old_conversations = cursor.fetchall()
                
                if len(old_conversations) < 10:  # Must have at least 10 to archive
                    return
                
                print(f"    📦 Archiving {len(old_conversations)} old conversation entries...")
                
                # Build conversations list
                conversations = []
                for conv in old_conversations:
                    conversations.append({
                        "id": conv[0],
                        "agent": conv[1],
                        "role": conv[2],
                        "content": conv[3][:200],  # Truncate for archival
                        "timestamp": conv[4]
                    })
                
                # Build summary prompt
                summary_prompt = self._build_conversation_archive_prompt(conversations)
                
                # Call archivist agent
                response = call_agent("archivist", summary_prompt, self.current_task_id)
                
                if response:
                    # Save archive
                    self._save_conversation_archive(self.current_task_id, conversations, response)
                    print(f"    ✅ Archived {len(conversations)} conversation entries")
                          
        except Exception as e:
            print(f"    ❌ Conversation archive error: {e}")
    
    def _check_for_restore_requests(self):
        """
        Check if orchestrator needs archived MESSAGE/CONVERSATION context restored
        Does NOT restore file contents - those stay in database
        """
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Look for recent orchestrator messages asking about previous context
                recent_time = (datetime.now() - timedelta(minutes=5)).isoformat()
                
                cursor.execute("""
                    SELECT id, content, task_id
                    FROM messages
                    WHERE to_agent = 'orchestrator' 
                    AND timestamp > ?
                    AND task_id = ?
                    AND read = 0
                """, (recent_time, self.current_task_id))
                
                messages = cursor.fetchall()
                
                for msg_id, content, task_id in messages:
                    # Check if message asks about previous decisions or context
                    # NOT about files (files are always available in database)
                    if self._needs_context_restore(content):
                        print(f"    🔍 Detected context restore need in message {msg_id}")
                        self._restore_relevant_context(task_id, content)
                
                
        except Exception as e:
            print(f"    ❌ Restore check error: {e}")
    
    def _needs_context_restore(self, content: str) -> bool:
        """
        Determine if message asks for previous decisions/context
        NOT for file contents (those are always in database)
        """
        keywords = [
            "previous decision", "earlier decision", "what did we decide",
            "before", "last time", "already discussed",
            "why did we", "reason for", "rationale",
            "conversation history", "what happened"
        ]
        
        # Exclude file-related queries (those use database directly)
        exclude_keywords = [
            "what files", "file content", "read file", "show file"
        ]
        
        content_lower = content.lower()
        
        # Don't restore for file queries
        if any(keyword in content_lower for keyword in exclude_keywords):
            return False
        
        return any(keyword in content_lower for keyword in keywords)
    
    def _restore_relevant_context(self, task_id: str, query: str):
        """
        Restore relevant archived CONVERSATION/DECISION context to message bus
        Does NOT restore file contents (those are always in database)
        """
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Get archived conversation summaries for this task
                cursor.execute("""
                    SELECT id, summary, key_decisions, turn_range
                    FROM archived_context
                    WHERE task_id = ?
                    ORDER BY archived_at DESC
                    LIMIT 5
                """, (task_id,))
                
                archives = cursor.fetchall()
                
                if not archives:
                    return
                
                # Build restoration message (CONVERSATION CONTEXT ONLY)
                restoration = "📚 **Restored Conversation Context from Archives:**\n\n"
                restoration += "*(Note: File contents are always available in database)*\n\n"
                
                for archive_id, summary, key_decisions, turn_range in archives:
                    restoration += f"**Period: {turn_range}**\n"
                    restoration += f"Summary: {summary}\n"
                    
                    try:
                        decisions = json.loads(key_decisions)
                        if decisions:
                            restoration += f"Key Decisions: {', '.join(decisions[:3])}\n"
                    except:
                        pass
                    
                    restoration += "\n"
                
                # Post restoration to orchestrator
                post_message(
                    "archivist", "orchestrator",
                    restoration, task_id, "HIGH"
                )
                
                print(f"    ✅ Restored {len(archives)} archived context(s) to message bus")
                
            
        except Exception as e:
            print(f"    ❌ Restore error: {e}")
    
    def _build_message_archive_prompt(self, messages: List[Dict]) -> str:
        """Build prompt for archiving MESSAGE BUS content"""
        prompt = "Archive and summarize these agent messages from the message bus:\n\n"
        prompt += "*(These are inter-agent communications, NOT file contents)*\n\n"
        
        for msg in messages:
            prompt += f"[{msg['timestamp'][:19]}] {msg['from']} → {msg['to']} ({msg['priority']})\n"
            prompt += f"{msg['content'][:200]}...\n\n"
        
        prompt += "\nCreate a compact summary of decisions and communications. "
        prompt += "Do NOT summarize file contents - only agent conversations."
        
        return prompt
    
    def _build_conversation_archive_prompt(self, conversations: List[Dict]) -> str:
        """Build prompt for archiving CONVERSATION HISTORY"""
        prompt = "Archive and summarize this conversation history:\n\n"
        prompt += "*(These are agent responses, NOT file contents)*\n\n"
        
        for conv in conversations:
            prompt += f"[{conv['timestamp'][:19]}] {conv['agent']} ({conv['role']})\n"
            prompt += f"{conv['content'][:200]}...\n\n"
        
        prompt += "\nCreate a compact summary of what was discussed and decided. "
        prompt += "Do NOT include file content summaries - focus on decisions and context."
        
        return prompt
    
    def _save_message_archive(self, task_id: str, messages: List[Dict], archivist_response: str):
        """Save message bus archive to database"""
        try:
            # Parse archivist response
            if "```json" in archivist_response:
                json_str = archivist_response.split("```json")[1].split("```")[0].strip()
            elif "{" in archivist_response:
                start = archivist_response.find("{")
                end = archivist_response.rfind("}") + 1
                json_str = archivist_response[start:end]
            else:
                json_str = archivist_response
            
            data = json.loads(json_str)
            summary = data.get("summary", "Archived messages")
            key_decisions = json.dumps(data.get("key_decisions", []))
            files_modified = "[]"  # Not tracking files in message archive
            
        except:
            summary = "Archived messages (parse failed)"
            key_decisions = "[]"
            files_modified = "[]"
        
        # Get time range
        timestamps = [msg["timestamp"] for msg in messages]
        turn_range = f"{timestamps[0][:19]} to {timestamps[-1][:19]}"

        with get_db_connection() as conn:
            conn.execute("""
                INSERT INTO archived_context
                (task_id, turn_range, summary, key_decisions, files_modified, archived_at, original_message_count)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (task_id, turn_range, summary, key_decisions, files_modified,
                datetime.now().isoformat(), len(messages)))
    
    def _save_conversation_archive(self, task_id: str, conversations: List[Dict], archivist_response: str):
        """Save conversation history archive to database"""
        # Same as message archive but marks it as conversation type
        self._save_message_archive(task_id, conversations, archivist_response)


# Global singleton
_archivist_worker = None

def get_archivist_worker() -> ArchivistWorker:
    """Get global archivist worker"""
    global _archivist_worker
    if _archivist_worker is None:
        _archivist_worker = ArchivistWorker()
    return _archivist_worker