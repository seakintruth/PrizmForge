"""Project Reporter Worker — generates human-readable audit reports"""
import threading
import time
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, List

from agents.base import call_agent
from core.db import get_db_path
from core.config import get_config
from core.db_connection import get_db_connection


class ProjectReporterWorker:
    """Periodic reporter that produces human-readable project audit reports."""

    def __init__(self):
        self.running = False
        self.worker_thread: Optional[threading.Thread] = None
        self.task_id: Optional[str] = None
        self.last_report_time: Optional[datetime] = None
        self.last_file_count: int = 0
        self.last_line_delta: int = 0
        self.config = get_config().get("reporter", {})
        self.output_dir = Path(self.config.get("output_directory", ".PrizmForge/reports"))
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def start(self, task_id: str):
        if self.running:
            return
        self.running = True
        self.task_id = task_id
        self._load_last_state()

        self.worker_thread = threading.Thread(
            target=self._worker_loop,
            daemon=True,
            name="project-reporter-worker"
        )
        self.worker_thread.start()
        print(f"    📊 Started Project Reporter worker (interval: {self.config.get('interval_minutes', 60)} min)")

    def stop(self):
        self.running = False
        if self.worker_thread:
            self.worker_thread.join(timeout=5.0)
        print("    🛑 Stopped Project Reporter worker")

    def _load_last_state(self):
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT last_report_time, last_report_file_count, last_report_line_delta
                    FROM reporter_state WHERE id = 1
                """)
                row = cursor.fetchone()
                if row:
                    if row[0]:
                        self.last_report_time = datetime.fromisoformat(row[0])
                    self.last_file_count = row[1] or 0
                    self.last_line_delta = row[2] or 0
        except Exception:
            pass

    def _save_state(self):
        try:
            with get_db_connection() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO reporter_state (id, last_report_time, last_report_file_count, last_report_line_delta)
                    VALUES (1, ?, ?, ?)
                """, (
                    self.last_report_time.isoformat() if self.last_report_time else None,
                    self.last_file_count,
                    self.last_line_delta
                ))
                conn.commit()
                conn.close()
        except Exception as e:
            print(f"    ⚠️  Failed to save reporter state: {e}")

    def _worker_loop(self):
        while self.running:
            try:
                time.sleep(300)  # Check every 5 minutes
                if not self.running:
                    break

                if self._should_generate_report():
                    self._generate_report()

            except Exception as e:
                print(f"    ⚠️  Project Reporter error: {e}")
                time.sleep(600)

    def _should_generate_report(self) -> bool:
        now = datetime.now()

        # Time-based trigger
        interval = self.config.get("interval_minutes", 60)
        if self.last_report_time is None:
            return True
        if (now - self.last_report_time).total_seconds() >= interval * 60:
            return True

        # Change-based trigger
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()

                # Count files modified since last report
                if self.last_report_time:
                    cursor.execute("""
                        SELECT COUNT(DISTINCT file_path), COALESCE(SUM(ABS(LENGTH(content_after) - LENGTH(content_before))), 0)
                        FROM file_modifications
                        WHERE timestamp > ?
                    """, (self.last_report_time.isoformat(),))
                else:
                    cursor.execute("""
                        SELECT COUNT(DISTINCT file_path), COALESCE(SUM(ABS(LENGTH(content_after) - LENGTH(content_before))), 0)
                        FROM file_modifications
                    """)

                row = cursor.fetchone()

            file_count = row[0] or 0
            line_delta = row[1] or 0

            threshold_pct = self.config.get("change_threshold_percent", 5.0)
            threshold_lines = self.config.get("change_threshold_lines", 200)

            # Simple heuristic: if > threshold % of files changed or > threshold lines
            total_files = self._get_total_indexed_files()
            pct_changed = (file_count / max(total_files, 1)) * 100

            if pct_changed >= threshold_pct or line_delta >= threshold_lines:
                self.last_file_count = file_count
                self.last_line_delta = line_delta
                return True

        except Exception as e:
            print(f"    ⚠️  Error checking change threshold: {e}")

        return False

    def _get_total_indexed_files(self) -> int:
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM project_files WHERE is_binary = 0")
                count = cursor.fetchone()[0]
            return count
        except Exception:
            return 100  # fallback

    def _generate_report(self):
        print("    📊 Generating project report...")

        try:
            # Gather data
            report_data = self._gather_report_data()

            # Call the agent
            prompt = self._build_prompt(report_data)
            response = call_agent("project_reporter", prompt, self.task_id or "global")

            if not response:
                print("    ⚠️  Reporter agent returned no response")
                return

            # Save report
            report_path = self._save_report(response, report_data)

            # Record in database
            self._record_report(report_path, report_data, response)

            # Update state
            self.last_report_time = datetime.now()
            self._save_state()

            print(f"    ✅ Project report saved: {report_path}")

            # Optional: notify orchestrator
            self._notify_orchestrator(report_path)

        except Exception as e:
            print(f"    ❌ Failed to generate report: {e}")

    def _gather_report_data(self) -> Dict:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            start_time = self.last_report_time or (datetime.now() - timedelta(hours=24))
            end_time = datetime.now()

            # File modifications
            cursor.execute("""
                SELECT file_path, operation, changed_by, timestamp
                FROM file_modifications
                WHERE timestamp BETWEEN ? AND ?
                ORDER BY timestamp DESC
                LIMIT 50
            """, (start_time.isoformat(), end_time.isoformat()))
            modifications = cursor.fetchall()

            # Git commits (if available)
            git_commits = []
            if self.config.get("include_git_commits", True):
                try:
                    import subprocess
                    config = get_config()
                    project_dir = config.get("project_directory")
                    result = subprocess.run(
                        ["git", "log", f"--since={start_time.isoformat()}", "--oneline", "-20"],
                        cwd=project_dir, capture_output=True, text=True, timeout=10
                    )
                    if result.returncode == 0:
                        git_commits = result.stdout.strip().split("\n")[:10]
                except Exception:
                    pass

            # Addressed feedback
            cursor.execute("""
                SELECT agent_name, file_path, priority, message, addressed_at
                FROM agent_feedback
                WHERE addressed = 1 AND addressed_at BETWEEN ? AND ?
                ORDER BY addressed_at DESC
                LIMIT 20
            """, (start_time.isoformat(), end_time.isoformat()))
            addressed_feedback = cursor.fetchall()

        return {
            "start_time": start_time,
            "end_time": end_time,
            "modifications": modifications,
            "git_commits": git_commits,
            "addressed_feedback": addressed_feedback,
            "total_files_changed": len(set(m[0] for m in modifications)),
            "trigger": "time" if (datetime.now() - start_time).total_seconds() >= self.config.get("interval_minutes", 60) * 60 else "change"
        }

    def _build_prompt(self, data: Dict) -> str:
        mods = "\n".join([f"- {m[0]} ({m[1]}) by {m[2]} at {m[3][:16]}" for m in data["modifications"][:15]])
        commits = "\n".join([f"- {c}" for c in data["git_commits"][:8]]) if data["git_commits"] else "No git commits recorded"
        feedback = "\n".join([f"- [{f[2]}] {f[1]}: {f[3][:80]} (by {f[0]})" for f in data["addressed_feedback"][:10]])

        return f"""Generate a human-readable project report for the period {data['start_time'].strftime('%Y-%m-%d %H:%M')} to {data['end_time'].strftime('%Y-%m-%d %H:%M')}.

**Files Modified ({data['total_files_changed']}):**
{mods}

**Git Commits:**
{commits}

**Addressed High-Priority Feedback:**
{feedback}

**Trigger:** {data['trigger']}

Please produce the full Markdown report following the exact structure defined in your system prompt."""

    def _save_report(self, response: str, data: Dict) -> str:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        filename = f"project_report_{timestamp}.md"
        
        # Get absolute path
        from core.config import get_config
        config = get_config()
        project_dir = Path(config.get("project_directory", "./project"))
        reports_dir = project_dir / ".PrizmForge" / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        
        filepath = reports_dir / filename

        # Clean up old reports
        self._cleanup_old_reports(reports_dir)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(response)

        return str(filepath)

    def _cleanup_old_reports(self, reports_dir: Path):
        try:
            max_keep = self.config.get("max_reports_to_keep", 30)
            reports = sorted(reports_dir.glob("project_report_*.md"), reverse=True)
            for old_report in reports[max_keep:]:
                old_report.unlink()
        except Exception:
            pass

    def _record_report(self, filepath: str, data: Dict, response: str):
        try:
            with get_db_connection() as conn:
                conn.execute("""
                    INSERT INTO project_reports
                    (report_start, report_end, trigger_type, file_path, summary, stats_json, generated_at, task_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    data["start_time"].isoformat(),
                    data["end_time"].isoformat(),
                    data["trigger"],
                    filepath,
                    response[:200] + "..." if len(response) > 200 else response,
                    json.dumps({
                        "files_changed": data["total_files_changed"],
                        "modifications_count": len(data["modifications"])
                    }),
                    datetime.now().isoformat(),
                    self.task_id
                ))
        except Exception as e:
            print(f"    ⚠️  Failed to record report in DB: {e}")

    def _notify_orchestrator(self, report_path: str):
        try:
            from core.db_helpers import post_message
            post_message(
                "project_reporter",
                "orchestrator",
                f"New project report generated: {report_path}",
                self.task_id or "global",
                "MEDIUM"
            )
        except Exception:
            pass

# Global singleton
_reporter_worker = None

def get_reporter_worker() -> ProjectReporterWorker:
    global _reporter_worker
    if _reporter_worker is None:
        _reporter_worker = ProjectReporterWorker()
    return _reporter_worker