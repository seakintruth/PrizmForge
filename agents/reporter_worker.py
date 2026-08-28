"""Project Reporter Worker — generates human-readable audit reports"""

import json
import threading
from datetime import datetime, timedelta
from pathlib import Path

from agents.base import call_agent
from agents.worker_utils import interruptible_sleep
from core.config import get_config
from core.db_connection import get_db_connection


class ProjectReporterWorker:
    """Periodic reporter that produces human-readable project audit reports."""

    def __init__(self):
        self.running = False
        self.worker_thread: threading.Thread | None = None
        self.task_id: str | None = None
        self.last_report_time: datetime | None = None
        self.last_file_count: int = 0
        self.last_line_delta: int = 0
        self.config = get_config().get("reporter", {})
        project_dir = Path(get_config().get("project_directory", "./project"))
        self.output_dir = project_dir / ".PrizmForge" / "reports"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def start(self, task_id: str):
        if self.running:
            return
        self.running = True
        self.task_id = task_id
        self._load_last_state()

        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True, name="project-reporter-worker")
        self.worker_thread.start()
        print(f"    📊 Started Project Reporter worker (interval: {self.config.get('interval_minutes', 60)} min)")

    def stop(self):
        self.running = False
        if self.worker_thread:
            self.worker_thread.join(timeout=2.0)
            self.worker_thread = None
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
        except Exception as e:
            print(f"    ⚠️  Exception handled in reporter_worker.py: {e}")

    def _save_state(self):
        try:
            with get_db_connection() as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO reporter_state (id, last_report_time, last_report_file_count, last_report_line_delta)
                    VALUES (1, ?, ?, ?)
                """,
                    (
                        (self.last_report_time.isoformat() if self.last_report_time else None),
                        self.last_file_count,
                        self.last_line_delta,
                    ),
                )
        except Exception as e:
            print(f"    ⚠️  Failed to save reporter state: {e}")

    def _worker_loop(self):
        while self.running:
            try:
                # Was time.sleep(300) — blocked stop() for up to 5 minutes
                interruptible_sleep(300, lambda: self.running)
                if not self.running:
                    break

                if self._should_generate_report():
                    self._generate_report()

            except Exception as e:
                print(f"    ⚠️  Project Reporter error: {e}")
                interruptible_sleep(60, lambda: self.running)

    def _should_generate_report(self) -> bool:
        now = datetime.now()

        interval = self.config.get("interval_minutes", 60)
        if self.last_report_time is None:
            return True
        if (now - self.last_report_time).total_seconds() >= interval * 60:
            return True

        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()

                if self.last_report_time:
                    cursor.execute(
                        """
                        SELECT COUNT(DISTINCT file_path), COALESCE(SUM(ABS(LENGTH(content_after) - LENGTH(content_before))), 0)
                        FROM file_modifications
                        WHERE timestamp > ?
                    """,
                        (self.last_report_time.isoformat(),),
                    )
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
            return 100

    def _generate_report(self):
        print("    📊 Generating project report...")

        try:
            report_data = self._gather_report_data()

            prompt = self._build_prompt(report_data)
            response = call_agent("project_reporter", prompt, self.task_id or "global")

            if not response:
                print("    ⚠️  Reporter agent returned no response")
                return

            report_path = self._save_report(response, report_data)

            self._record_report(report_path, report_data, response)

            self.last_report_time = datetime.now()
            self._save_state()

            print(f"    ✅ Project report saved: {report_path}")

            self._notify_orchestrator(report_path)

        except Exception as e:
            print(f"    ❌ Failed to generate report: {e}")

    def _gather_report_data(self) -> dict:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            start_time = self.last_report_time or (datetime.now() - timedelta(hours=24))
            end_time = datetime.now()

            cursor.execute(
                """
                SELECT file_path, operation, changed_by, timestamp
                FROM file_modifications
                WHERE timestamp BETWEEN ? AND ?
                ORDER BY timestamp DESC
                LIMIT 50
            """,
                (start_time.isoformat(), end_time.isoformat()),
            )
            modifications = cursor.fetchall()

            git_commits = []
            if self.config.get("include_git_commits", True):
                try:
                    import subprocess

                    config = get_config()
                    project_dir = config.get("project_directory")
                    result = subprocess.run(
                        [
                            "git",
                            "log",
                            f"--since={start_time.isoformat()}",
                            "--oneline",
                            "-20",
                        ],
                        cwd=project_dir,
                        capture_output=True,
                        text=True,
                        timeout=10,
                    )
                    if result.returncode == 0:
                        git_commits = result.stdout.strip().split("\n")[:10]
                except Exception as e:
                    print(f"    ⚠️  Exception handled in reporter_worker.py: {e}")

            cursor.execute(
                """
                SELECT agent_name, file_path, priority, message, addressed_at
                FROM agent_feedback
                WHERE addressed = 1 AND addressed_at BETWEEN ? AND ?
                ORDER BY addressed_at DESC
                LIMIT 20
            """,
                (start_time.isoformat(), end_time.isoformat()),
            )
            addressed_feedback = cursor.fetchall()

            # Backlog health metrics (Workstream B §4.6): unaddressed,
            # posted_this_hour, addressed_this_hour, stuck_ids.
            from core.db_helpers import backlog_metrics

            metrics = backlog_metrics(conn, task_id=self.task_id)

            # Always-on run counters (Workstream F §8.3): materialize success
            # ratio, fallback rate, git-failure count since last report.
            cursor.execute(
                """
                SELECT COUNT(*) AS total,
                       COALESCE(SUM(CASE WHEN status IN ('applied', 'materialized') THEN 1 ELSE 0 END), 0) AS ok,
                       COALESCE(SUM(CASE WHEN status IN ('git_failed', 'error', 'failed') THEN 1 ELSE 0 END), 0) AS err,
                       COALESCE(SUM(CASE WHEN fallback_used = 1 THEN 1 ELSE 0 END), 0) AS fallback
                FROM edit_proposals
                WHERE created_at >= ?
                """,
                (start_time.isoformat(),),
            )
            funnel = cursor.fetchone()
            total = funnel[0] or 0
            ok = funnel[1] or 0
            fallback = funnel[3] or 0
            cursor.execute(
                "SELECT COUNT(*) FROM events WHERE type = 'edit.git_failed' AND ts >= ?",
                (start_time.isoformat(),),
            )
            git_fail_count = cursor.fetchone()[0] or 0
            cursor.execute(
                "SELECT COUNT(*) FROM events WHERE type = 'prioritizer.circuit_open' AND ts >= ?",
                (start_time.isoformat(),),
            )
            circuit_open_count = cursor.fetchone()[0] or 0
            run_metrics = {
                "materialize_total": total,
                "materialize_success": ok,
                "materialize_success_ratio": (ok / total) if total else 0.0,
                "fallback_rate": (fallback / total) if total else 0.0,
                "git_fail_count": git_fail_count,
                "circuit_open_count": circuit_open_count,
            }

        return {
            "start_time": start_time,
            "end_time": end_time,
            "modifications": modifications,
            "git_commits": git_commits,
            "addressed_feedback": addressed_feedback,
            "total_files_changed": len(set(m[0] for m in modifications)),
            "backlog_metrics": metrics,
            "run_metrics": run_metrics,
            "trigger": ("time" if (datetime.now() - start_time).total_seconds() >= self.config.get("interval_minutes", 60) * 60 else "change"),
        }

    def _build_prompt(self, data: dict) -> str:
        mods = "\n".join([f"- {m[0]} ({m[1]}) by {m[2]} at {m[3][:16]}" for m in data["modifications"][:15]])
        commits = "\n".join([f"- {c}" for c in data["git_commits"][:8]]) if data["git_commits"] else "No git commits recorded"
        feedback = "\n".join([f"- [{f[2]}] {f[1]}: {f[3][:80]} (by {f[0]})" for f in data["addressed_feedback"][:10]])
        m = data.get("backlog_metrics") or {}
        backlog = (
            f"Unaddressed: {m.get('unaddressed')} | "
            f"Posted this hour: {m.get('posted_this_hour')} | "
            f"Addressed this hour: {m.get('addressed_this_hour')} | "
            f"Stuck ids: {m.get('stuck_ids') or []}"
        )
        rm = data.get("run_metrics") or {}
        run_metrics = (
            f"Proposals: {rm.get('materialize_total', 0)} | "
            f"Materialize success ratio: {rm.get('materialize_success_ratio', 0.0):.0%} "
            f"({rm.get('materialize_success', 0)}/{rm.get('materialize_total', 0)}) | "
            f"Fallback rate: {rm.get('fallback_rate', 0.0):.0%} | "
            f"Git failures: {rm.get('git_fail_count', 0)} | "
            f"Circuit opens: {rm.get('circuit_open_count', 0)}"
        )

        return f"""
Generate a human-readable project report for the period
{data["start_time"].strftime("%Y-%m-%d %H:%M")} to {data["end_time"].strftime("%Y-%m-%d %H:%M")}.

**Files Modified ({data["total_files_changed"]}):**
{mods}

**Git Commits:**
{commits}

**Addressed High-Priority Feedback:**
{feedback}

**Backlog Health:**
{backlog}

**Run Metrics:**
{run_metrics}

**Trigger:** {data["trigger"]}

Please produce the full Markdown report following the exact structure defined in your system prompt."""

    def _save_report(self, response: str, data: dict) -> str:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        filename = f"project_report_{timestamp}.md"

        from core.config import get_config

        config = get_config()
        project_dir = Path(config.get("project_directory", "./project"))
        reports_dir = project_dir / ".PrizmForge" / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)

        filepath = reports_dir / filename

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
        except Exception as e:
            print(f"    ⚠️  Exception handled in reporter_worker.py: {e}")

    def _record_report(self, filepath: str, data: dict, response: str):
        try:
            with get_db_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO project_reports
                    (report_start, report_end, trigger_type, file_path, summary, stats_json, generated_at, task_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        data["start_time"].isoformat(),
                        data["end_time"].isoformat(),
                        data["trigger"],
                        filepath,
                        response[:200] + "..." if len(response) > 200 else response,
                        json.dumps(
                            {
                                "files_changed": data["total_files_changed"],
                                "modifications_count": len(data["modifications"]),
                                "backlog_metrics": data.get("backlog_metrics") or {},
                                "run_metrics": data.get("run_metrics") or {},
                            }
                        ),
                        datetime.now().isoformat(),
                        self.task_id,
                    ),
                )
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
                "MEDIUM",
            )
        except Exception as e:
            print(f"    ⚠️  Exception handled in reporter_worker.py: {e}")


# Global singleton
_reporter_worker = None


def get_reporter_worker() -> ProjectReporterWorker:
    global _reporter_worker
    if _reporter_worker is None:
        _reporter_worker = ProjectReporterWorker()
    return _reporter_worker
