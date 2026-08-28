"""
Background archivist
 - monitors, archives, and restores context
"""

import json
import threading
import time
from datetime import datetime, timedelta
from typing import Any

from agents.base import call_agent
from agents.worker_utils import interruptible_sleep
from core.db_connection import get_db_connection
from core.db_helpers import post_message


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
        self.restore_interval = 60  # 1 minute

    def start(self, task_id: str):
        """Start the archivist worker"""
        if self.running:
            return

        self.running = True
        self.current_task_id = task_id
        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True, name="archivist-worker")
        self.worker_thread.start()
        print("    📚 Started archivist worker (message bus & conversation only)")

    def stop(self):
        """Stop the archivist worker"""
        self.running = False
        if self.worker_thread:
            self.worker_thread.join(timeout=2.0)
            self.worker_thread = None
        print("    📚 Stopped archivist worker")

    def _worker_loop(self):
        """Main worker loop"""
        while self.running:
            try:
                current_time = time.time()

                if current_time - self.last_archive_check >= self.archive_interval:
                    self._archive_old_messages()
                    self._archive_old_conversations()
                    self.last_archive_check = current_time

                if current_time - self.last_restore_check >= self.restore_interval:
                    self._check_for_restore_requests()
                    self.last_restore_check = current_time

                # Was time.sleep(30) — blocked stop() for up to 30s
                interruptible_sleep(30, lambda: self.running)

            except Exception as e:
                print(f"    ⚠️  Archivist error: {e}")
                interruptible_sleep(60, lambda: self.running)

    def _archive_old_messages(self) -> None:
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cutoff_time = (datetime.now() - timedelta(minutes=10)).isoformat()
                cursor.execute(
                    """
                    SELECT id, from_agent, to_agent, content, timestamp, priority, task_id
                    FROM messages
                    WHERE read = 1 AND timestamp < ? AND task_id = ?
                    ORDER BY timestamp
                """,
                    (cutoff_time, self.current_task_id),
                )
                old_messages = cursor.fetchall()
                if len(old_messages) < 5:
                    return
                print(f"    📦 Archiving {len(old_messages)} read messages from message bus...")
                messages = []
                for msg in old_messages:
                    messages.append(
                        {
                            "id": msg[0],
                            "from": msg[1],
                            "to": msg[2],
                            "content": msg[3],
                            "timestamp": msg[4],
                            "priority": msg[5],
                            "task_id": msg[6],
                        }
                    )
                summary_prompt = self._build_message_archive_prompt(messages)
                response = call_agent("archivist", summary_prompt, self.current_task_id)
                if response:
                    saved = self._save_message_archive(self.current_task_id, messages, response, conn=conn)
                    if not saved:
                        # Keep originals on the bus; never swap real context
                        # for an unparseable summary.
                        return
                    message_ids = [msg["id"] for msg in messages]
                    placeholders = ",".join("?" * len(message_ids))
                    cursor.execute(
                        f"DELETE FROM messages WHERE id IN ({placeholders})",  # noqa: S608
                        message_ids,
                    )
                    print(f"    ✅ Archived and cleaned {len(messages)} messages from bus")
        except Exception as e:
            print(f"    ❌ Message archive error: {e}")

    def _archive_old_conversations(self):
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT COUNT(*) FROM conversation_history WHERE task_id = ?",
                    (self.current_task_id,),
                )
                count = cursor.fetchone()[0]
                if count < 30:
                    return
                cursor.execute(
                    "SELECT MAX(archived_at) FROM archived_context WHERE task_id = ?",
                    (self.current_task_id,),
                )
                last_archive = cursor.fetchone()[0]
                if last_archive:
                    last_time = datetime.fromisoformat(last_archive)
                    if datetime.now() - last_time < timedelta(minutes=10):
                        return
                cursor.execute(
                    """
                    SELECT id, agent, role, content, timestamp
                    FROM conversation_history
                    WHERE task_id = ?
                    ORDER BY timestamp
                    LIMIT ?
                """,
                    (self.current_task_id, max(0, count - 15)),
                )
                old_conversations = cursor.fetchall()
                if len(old_conversations) < 10:
                    return
                print(f"    📦 Archiving {len(old_conversations)} old conversation entries...")
                conversations = []
                for conv in old_conversations:
                    conversations.append(
                        {
                            "id": conv[0],
                            "agent": conv[1],
                            "role": conv[2],
                            "content": conv[3][:200],
                            "timestamp": conv[4],
                        }
                    )
                summary_prompt = self._build_conversation_archive_prompt(conversations)
                response = call_agent("archivist", summary_prompt, self.current_task_id)
                if response and self._save_conversation_archive(self.current_task_id, conversations, response):
                    print(f"    ✅ Archived {len(conversations)} conversation entries")
        except Exception as e:
            print(f"    ❌ Conversation archive error: {e}")

    def _check_for_restore_requests(self):
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                recent_time = (datetime.now() - timedelta(minutes=5)).isoformat()
                cursor.execute(
                    """
                    SELECT id, content, task_id
                    FROM messages
                    WHERE to_agent = 'orchestrator'
                    AND timestamp > ?
                    AND task_id = ?
                    AND read = 0
                """,
                    (recent_time, self.current_task_id),
                )
                messages = cursor.fetchall()
                for msg_id, content, task_id in messages:
                    if self._needs_context_restore(content):
                        print(f"    🔍 Detected context restore need in message {msg_id}")
                        self._restore_relevant_context(task_id, content)
        except Exception as e:
            print(f"    ❌ Restore check error: {e}")

    def _needs_context_restore(self, content: str) -> bool:
        keywords = [
            "previous decision",
            "earlier decision",
            "what did we decide",
            "before",
            "last time",
            "already discussed",
            "why did we",
            "reason for",
            "rationale",
            "conversation history",
            "what happened",
        ]
        exclude_keywords = ["what files", "file content", "read file", "show file"]
        content_lower = content.lower()
        if any(keyword in content_lower for keyword in exclude_keywords):
            return False
        return any(keyword in content_lower for keyword in keywords)

    def _restore_relevant_context(self, task_id: str, query: str):
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT id, summary, key_decisions, turn_range
                    FROM archived_context
                    WHERE task_id = ?
                    ORDER BY archived_at DESC
                    LIMIT 5
                """,
                    (task_id,),
                )
                archives = cursor.fetchall()
                if not archives:
                    return
                restoration = "📚 **Restored Conversation Context from Archives:**\n\n"
                restoration += "*(Note: File contents are always available in database)*\n\n"
                for _archive_id, summary, key_decisions, turn_range in archives:
                    restoration += f"**Period: {turn_range}**\n"
                    restoration += f"Summary: {summary}\n"
                    try:
                        decisions = json.loads(key_decisions)
                        if decisions:
                            restoration += f"Key Decisions: {', '.join(decisions[:3])}\n"
                    except Exception as e:
                        print(f"    ⚠️  Failed to parse archived key decisions: {e}")
                    restoration += "\n"
                post_message("archivist", "orchestrator", restoration, task_id, "HIGH")
                print(f"    ✅ Restored {len(archives)} archived context(s) to message bus")
        except Exception as e:
            print(f"    ❌ Restore error: {e}")

    def _build_message_archive_prompt(self, messages: list[dict]) -> str:
        prompt = "Archive and summarize these agent messages from the message bus:\n\n"
        prompt += "*(These are inter-agent communications, NOT file contents)*\n\n"
        for msg in messages:
            prompt += f"[{msg['timestamp'][:19]}] {msg['from']} → {msg['to']} ({msg['priority']})\n"
            prompt += f"{msg['content'][:200]}...\n\n"
        prompt += "\nCreate a compact summary of decisions and communications. "
        prompt += "Do NOT summarize file contents - only agent conversations."
        return prompt

    def _build_conversation_archive_prompt(self, conversations: list[dict]) -> str:
        prompt = "Archive and summarize this conversation history:\n\n"
        prompt += "*(These are agent responses, NOT file contents)*\n\n"
        for conv in conversations:
            prompt += f"[{conv['timestamp'][:19]}] {conv['agent']} ({conv['role']})\n"
            prompt += f"{conv['content'][:200]}...\n\n"
        prompt += "\nCreate a compact summary of what was discussed and decided. "
        prompt += "Do NOT include file content summaries - focus on decisions and context."
        return prompt

    @staticmethod
    def _parse_archive_response(archivist_response: str) -> tuple[bool, str, str]:
        """Return (parsed, summary, key_decisions) from an archivist response.

        On failure returns (False, "", "") so callers can keep originals
        instead of writing a "parse failed" placeholder row. Soak evidence
        (2026-08-28): 35/36 archive batches produced junk summaries that were
        then restored as context, so unparseable output must not be archived.
        """
        try:
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
            return True, str(summary), key_decisions
        except Exception as e:
            print(f"    ⚠️  Failed to parse archivist response: {e}")
            return False, "", ""

    def _save_message_archive(
        self,
        task_id: str,
        messages: list[dict],
        archivist_response: str,
        conn: Any = None,
    ) -> bool:
        """Insert an archived-context row; False when the response was unparseable.

        Returning False tells the caller to keep the original messages (the
        message-bus path deletes them only after a row is actually written).
        """
        parsed, summary, key_decisions = self._parse_archive_response(archivist_response)
        if not parsed:
            print(f"    ⚠️  Skipping archive: unparseable archivist response ({len(messages)} messages kept)")
            return False
        files_modified = "[]"
        timestamps = [msg["timestamp"] for msg in messages]
        turn_range = f"{timestamps[0][:19]} to {timestamps[-1][:19]}" if timestamps else "N/A"
        query = """
            INSERT INTO archived_context
            (task_id, turn_range, summary, key_decisions, files_modified, archived_at, original_message_count)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            task_id,
            turn_range,
            summary,
            key_decisions,
            files_modified,
            datetime.now().isoformat(),
            len(messages),
        )
        if conn is not None:
            conn.execute(query, params)
        else:
            with get_db_connection() as db_conn:
                db_conn.execute(query, params)
        return True

    def _save_conversation_archive(self, task_id: str, conversations: list[dict], archivist_response: str):
        return self._save_message_archive(task_id, conversations, archivist_response)


_archivist_worker = None


def get_archivist_worker() -> ArchivistWorker:
    global _archivist_worker
    if _archivist_worker is None:
        _archivist_worker = ArchivistWorker()
    return _archivist_worker
