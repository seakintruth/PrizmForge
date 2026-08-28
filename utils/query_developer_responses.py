#!/usr/bin/env python3
"""
Query and display raw agent responses + diagnostic data from the PrizmForge database.

Useful for debugging JSON parsing failures, inspecting edit proposals,
materialization results, errors, and events.

All connections are opened READ-ONLY (sqlite URI mode=ro), so this tool can run
against a live unattended session without interfering with it. Use --db to point
at another project's database (e.g. a scratch repo running a smoke test).

Ad-hoc queries: --sql "SELECT ..." executes any single read query and prints the
result table; writes fail by virtue of the read-only connection.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    import sqlite3
except ImportError:
    sqlite3 = None  # type: ignore

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Set by --db; when empty, fall back to core.db.get_db_path() or CWD/.PrizmForge.
_DB_PATH_OVERRIDE: str | None = None


def _db_file() -> str:
    """Resolve the target database path (--db override > core config > CWD default)."""
    if _DB_PATH_OVERRIDE:
        return str(Path(_DB_PATH_OVERRIDE).resolve())
    try:
        from core.db import get_db_path

        return str(get_db_path())
    except Exception:
        return str(Path.cwd() / ".PrizmForge" / "agents.db")


def _connect_ro() -> sqlite3.Connection:
    """Open the DB read-only (WAL-aware); never writes or blocks the live loop."""
    path = _db_file()
    if not Path(path).is_file():
        raise SystemExit(f"❌ Database not found: {path}\n   Pass --db /path/to/project/.PrizmForge/agents.db")
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=5.0)
    conn.row_factory = sqlite3.Row
    return conn


def list_recent_developer_responses(
    task_id: str | None = None,
    limit: int = 10,
    agent_name: str = "developer",
    file_filter: str | None = None,
    modified_only: bool = False,
):
    """List recent developer responses with summary info, file filtering, and exact Reviewer approval matching."""
    conn = _connect_ro()
    try:
        cursor = conn.cursor()

        query_conditions = ["r.agent_name = ?"]
        params = [agent_name]

        if task_id:
            query_conditions.append("r.task_id = ?")
            params.append(str(task_id))

        if file_filter:
            query_conditions.append("(r.prompt LIKE ? OR r.response LIKE ? OR p.target_file_path LIKE ?)")
            file_pattern = f"%{file_filter}%"
            params.extend([file_pattern, file_pattern, file_pattern])

        where_clause = " AND ".join(query_conditions)

        if modified_only:
            query = f"""
                SELECT DISTINCT
                    r.id, r.timestamp, r.agent_name, r.task_id, r.parse_success,
                    LENGTH(r.prompt) as prompt_len,
                    LENGTH(r.response) as response_len,
                    p.target_file_path as modified_file
                FROM agent_responses_archive r
                JOIN agent_responses_archive rev ON (rev.id = r.id + 1 OR rev.id = r.id + 2)
                    AND rev.agent_name = 'reviewer'
                    AND rev.response LIKE '%"decision": "APPROVE"%'
                    AND rev.response NOT LIKE '%"decision": "REJECT"%'
                JOIN edit_proposals p ON p.task_id = r.task_id AND p.status = 'applied'
                WHERE {where_clause}
                ORDER BY r.timestamp DESC
                LIMIT ?
            """
        else:
            query = f"""
                SELECT DISTINCT
                    r.id, r.timestamp, r.agent_name, r.task_id, r.parse_success,
                    LENGTH(r.prompt) as prompt_len,
                    LENGTH(r.response) as response_len,
                    NULL as modified_file
                FROM agent_responses_archive r
                WHERE {where_clause}
                ORDER BY r.timestamp DESC
                LIMIT ?
            """

        params.append(limit)
        cursor.execute(query, params)
        responses = cursor.fetchall()
    finally:
        conn.close()

    file_msg = f" mentioning '{file_filter}'" if file_filter else ""
    mod_msg = " that resulted in file changes" if modified_only else ""

    if not responses:
        print(f"No {agent_name} responses found{file_msg}{mod_msg}.")
        return []

    print(f"\n{'=' * 80}")
    print(f"📋 Recent {agent_name} responses{file_msg}{mod_msg} — {len(responses)} rows")
    print(f"{'=' * 80}\n")

    headers = ["id", "timestamp", "agent", "task_id", "parse_ok", "prompt_len", "resp_len", "modified_file"]
    table_rows = []
    for r in responses:
        table_rows.append(
            [
                r["id"],
                r["timestamp"],
                r["agent_name"],
                r["task_id"],
                "✓" if r["parse_success"] else "✗",
                r["prompt_len"],
                r["response_len"],
                r["modified_file"] or "",
            ]
        )

    _print_table(headers, table_rows)

    return [r["id"] for r in responses]


def _print_table(headers, rows):
    """Print a simple aligned table to stdout."""
    if not rows:
        print("  (no rows)")
        return

    col_widths = [len(h) for h in headers]
    for row in rows:
        for i, val in enumerate(row):
            col_widths[i] = max(col_widths[i], len(str(val)))

    fmt = "  ".join(f"{{:<{w}}}" for w in col_widths)
    print(fmt.format(*headers))
    print(fmt.format(*("-" * w for w in col_widths)))
    for row in rows:
        print(fmt.format(*[str(v) for v in row]))


def _get_db(task_id: str | None = None):
    """Open read-only DB connection with row_factory and return (conn, cur, task_filter, tparam)."""
    conn = _connect_ro()
    cur = conn.cursor()
    task_filter = "AND task_id = ?" if task_id else ""
    tparam = (task_id,) if task_id else ()
    return conn, cur, task_filter, tparam


def _q(cur, sql, params=()):
    return cur.execute(sql, list(params)).fetchall()


# ---------------------------------------------------------------------------
# Diagnostic commands
# ---------------------------------------------------------------------------


def show_edit_proposals(task_id: str | None = None, limit: int = 40, full_replace_only: bool = False):
    """Show edit proposals with status, mode, fallback info."""
    conn, cur, task_filter, tparam = _get_db(task_id)

    where = ["1=1"]
    params = list(tparam)
    if full_replace_only:
        where.append("selected_mode = 'full_replace'")
    if task_filter:
        where.append(task_filter.lstrip("AND ").strip())
    where_clause = "WHERE " + " AND ".join(where)

    rows = _q(
        cur,
        f"""SELECT proposal_id, target_file_path, status, selected_mode,
                   fallback_used, final_mode, created_at, rationale
            FROM edit_proposals
            {where_clause}
            ORDER BY created_at DESC
            LIMIT ?""",
        [*params, limit],
    )

    headers = ["proposal_id", "target_file_path", "status", "selected_mode", "fallback_used", "final_mode", "created_at", "rationale"]
    table_rows = [
        [
            r["proposal_id"],
            r["target_file_path"],
            r["status"],
            r["selected_mode"] or "",
            r["fallback_used"] or 0,
            r["final_mode"] or "",
            r["created_at"],
            (r["rationale"] or "")[:60],
        ]
        for r in rows
    ]

    print(f"\n{'=' * 80}")
    print(f"📦 Edit Proposals — {len(rows)} rows")
    print(f"{'=' * 80}\n")
    _print_table(headers, table_rows)
    conn.close()


def show_file_write_log(limit: int = 40):
    conn, cur, _, _ = _get_db()
    rows = _q(
        cur,
        """SELECT log_id, proposal_id, file_id, status, started_at, completed_at
           FROM file_write_log
           ORDER BY log_id DESC
           LIMIT ?""",
        (limit,),
    )
    print(f"\n{'=' * 80}")
    print(f"📝 file_write_log — {len(rows)} rows")
    print(f"{'=' * 80}\n")
    _print_table(["log_id", "proposal_id", "file_id", "status", "started_at", "completed_at"], rows)
    conn.close()


def show_errors(level: str | None = None, keyword: str | None = None, limit: int = 30):
    conn, cur, _, _ = _get_db()

    where = []
    params = []

    if level:
        where.append("level = ?")
        params.append(level.upper())
    if keyword:
        text_cols = [c for c in ["message", "context", "file_path", "function_name"]]
        like_parts = " OR ".join(f"{c} LIKE ?" for c in text_cols)
        where.append(f"({like_parts})")
        params.extend([f"%{keyword}%"] * len(text_cols))

    where_clause = ("WHERE " + " AND ".join(where)) if where else ""

    rows = _q(
        cur,
        f"""SELECT id, level, message, context, file_path, function_name, task_id, agent_name, timestamp
            FROM errors
            {where_clause}
            ORDER BY timestamp DESC
            LIMIT ?""",
        [*params, limit],
    )

    title = "Errors"
    if level:
        title += f" [{level.upper()}]"
    if keyword:
        title += f" (keyword: {keyword})"

    print(f"\n{'=' * 80}")
    print(f"🚨 {title} — {len(rows)} rows")
    print(f"{'=' * 80}\n")
    _print_table(["id", "level", "message", "context", "file_path", "function_name", "task_id", "agent_name", "timestamp"], rows)
    conn.close()


def show_edit_events(limit: int = 60):
    conn, cur, _, _ = _get_db()
    rows = _q(
        cur,
        """SELECT id, ts, type, source, task_id, proposal_id, payload_json
           FROM events
           ORDER BY ts DESC
           LIMIT ?""",
        (limit,),
    )
    print(f"\n{'=' * 80}")
    print(f"📡 Edit / Proposal Lifecycle Events — {len(rows)} rows")
    print(f"{'=' * 80}\n")
    _print_table(["id", "ts", "type", "source", "task_id", "proposal_id", "payload_json"], rows)
    conn.close()


def show_file_line_counts(limit: int = 30):
    conn, cur, _, _ = _get_db()
    rows = _q(
        cur,
        """SELECT f.file_path, COUNT(fl.line_guid) as line_count
           FROM files f
           LEFT JOIN file_lines fl ON fl.file_id = f.file_id AND fl.is_deleted = 0
           WHERE f.is_deleted = 0
           GROUP BY f.file_id, f.file_path
           ORDER BY line_count ASC""",
    )
    # Exclude secrets / ignored cache (Workstream E §7.2): these are the
    # agent truncation candidates, so api_key.json / .ruff_cache must not leak.
    filtered = [r for r in rows if not _is_sensitive_or_ignored(r[0])]
    rows = filtered[:limit]
    print(f"\n{'=' * 80}")
    print(f"📏 Current line counts (lowest first — potential truncation candidates) — {len(rows)} files")
    print(f"{'=' * 80}\n")
    _print_table(["file_path", "line_count"], rows)
    conn.close()


def _is_sensitive_or_ignored(path: str) -> bool:
    """True for secret files and git/cache-ignored paths (Workstream E §7.2)."""
    if not path:
        return True
    try:
        from core.file_operations import is_secret_path, should_ignore_file

        return bool(should_ignore_file(path) or is_secret_path(path))
    except Exception:
        return False


def show_git_failures(limit: int = 20):
    """Dump git/hook failure outcomes: events + linked CRITICAL feedback."""
    conn, cur, _, _ = _get_db()
    events = _q(
        cur,
        """SELECT ts, proposal_id, source, payload_json
           FROM events
           WHERE type = 'edit.git_failed'
           ORDER BY ts DESC
           LIMIT ?""",
        (limit,),
    )
    print(f"\n{'=' * 80}")
    print(f"🔴 GIT / HOOK OUTCOMES (edit.git_failed) — {len(events)} rows")
    print(f"{'=' * 80}\n")
    if not events:
        print("   No git-failure events recorded.")
    for ts, proposal_id, _source, payload_json in events:
        payload = {}
        try:
            payload = json.loads(payload_json) if payload_json else {}
        except (json.JSONDecodeError, TypeError):
            pass
        stage = payload.get("stage", "?")
        code = payload.get("code", "?")
        file_path = payload.get("file_path", "")
        excerpt = (payload.get("stderr") or "")[:80].replace("\n", " ")
        print(f"   {ts} | proposal {proposal_id} | {stage} exit={code} | {file_path} | {excerpt}")
    conn.close()


def show_run_effectiveness(task_id: str | None = None):  # noqa: C901
    """Answer: is the loop making real progress, or just churning?

    Sections:
      1. Mutation pipeline funnel (proposals -> approved -> materialized)
      2. Edit mode effectiveness (selected vs final, fallback rate)
      3. Real-work evidence (files changed, line-count deltas)
      4. Feedback backlog health (addressed vs open, dupes, aging)
      5. Task lifecycle honesty (in_progress accumulation)
      6. Error budget burn (HIGH errors per hour, by agent/category)
      7. Token spend vs outcomes
    """
    conn = _connect_ro()
    cur = conn.cursor()
    task_filter = "AND task_id = ?" if task_id else ""
    tparam = (task_id,) if task_id else ()

    def q(sql, params=()):
        return cur.execute(sql, list(params)).fetchall()

    print(f"\n{'=' * 80}")
    print("📊 RUN EFFECTIVENESS")
    print("=" * 80)

    # --- 1. Mutation funnel -------------------------------------------------
    total_proposals = q(f"SELECT COUNT(*) c FROM edit_proposals WHERE 1=1 {task_filter}", tparam)[0]["c"]
    by_status = q(
        f"SELECT status, COUNT(*) c FROM edit_proposals WHERE 1=1 {task_filter} GROUP BY status ORDER BY c DESC",
        tparam,
    )
    writes_ok = q(
        f"""SELECT COUNT(*) c FROM file_write_log w
           JOIN edit_proposals p ON w.proposal_id = p.proposal_id
           WHERE w.status='success' {task_filter.replace("task_id", "p.task_id")}""",
        tparam,
    )[0]["c"]
    print("\n1️⃣  MUTATION FUNNEL")
    print(f"   proposals created : {total_proposals}")
    for row in by_status:
        print(f"   ├─ {row['status']:<12}: {row['c']}")
    print(f"   writes succeeded  : {writes_ok}")
    if total_proposals:
        rate = writes_ok / total_proposals * 100
        print(f"   proposal→applied conversion: {rate:.0f}%")

    # --- 2. Edit mode effectiveness ------------------------------------------
    modes = q(
        f"""SELECT selected_mode, final_mode, fallback_used, COUNT(*) c
            FROM edit_proposals WHERE selected_mode IS NOT NULL {task_filter}
            GROUP BY selected_mode, final_mode, fallback_used ORDER BY c DESC""",
        tparam,
    )
    print("\n2️⃣  EDIT MODE EFFECTIVENESS (selected → final, count)")
    if not modes:
        print("   (no proposals with mode data)")
    sel_total = sum(m["c"] for m in modes)
    fb_total = sum(m["c"] for m in modes if m["fallback_used"])
    for m in modes:
        arrow = f"{m['selected_mode']} → {m['final_mode']}"
        flag = "  ⚠️ FALLBACK" if m["fallback_used"] and m["selected_mode"] != m["final_mode"] else ""
        print(f"   {arrow:<40} {m['c']}{flag}")
    if sel_total:
        print(f"   fallback rate: {fb_total}/{sel_total} ({fb_total / sel_total * 100:.0f}%)")

    # --- 3. Real-work evidence ------------------------------------------------
    mods = q(
        f"""SELECT target_file_path AS fp,
                  MIN(created_at) first_edit, MAX(created_at) last_edit,
                  COUNT(*) edits
           FROM edit_proposals WHERE status='applied' {task_filter}
           GROUP BY target_file_path ORDER BY edits DESC LIMIT 15""",
        tparam,
    )
    print("\n3️⃣  FILES ACTUALLY MUTATED (by applied proposals)")
    if not mods:
        print("   (none — the loop has not changed any files)")
    for m in mods:
        n_lines = None
        try:
            fid = cur.execute("SELECT file_id FROM files WHERE file_path = ?", (m["fp"],)).fetchone()
            if fid:
                n_lines = cur.execute("SELECT COUNT(*) FROM file_lines WHERE file_id=?", (fid[0],)).fetchone()[0]
        except sqlite3.Error as e:
            print(f"   (line count unavailable for {m['fp']}: {e})")
        extra = f", ~{n_lines} lines now" if n_lines else ""
        print(f"   {m['fp']:<36} {m['edits']} edits{extra}")

    # --- 4. Feedback backlog health -------------------------------------------
    fb_open = q(
        f"SELECT priority, COUNT(*) c FROM agent_feedback WHERE addressed=0 {task_filter} GROUP BY priority",
        tparam,
    )
    fb_done = q(f"SELECT COUNT(*) c FROM agent_feedback WHERE addressed=1 {task_filter}", tparam)[0]["c"]
    fb_dupes = q(
        f"""SELECT substr(message,1,50) msg, COUNT(*) c FROM agent_feedback
           WHERE 1=1 {task_filter} GROUP BY substr(message,1,50) HAVING c > 1 ORDER BY c DESC LIMIT 5""",
        tparam,
    )
    total_fb = sum(r["c"] for r in fb_open) + fb_done
    print("\n4️⃣  FEEDBACK BACKLOG HEALTH")
    if task_id:
        print(f"   (scoped to task {task_id})")
    print(f"   addressed: {fb_done} / {total_fb}")
    for r in sorted(fb_open, key=lambda x: -x["c"]):
        print(f"   open {r['priority']:<8}: {r['c']}")
    if fb_dupes:
        print("   ⚠️  possible duplicate findings (agents re-reporting):")
        for d in fb_dupes:
            print(f"      ×{d['c']}  {d['msg']}...")

    # --- 5. Task lifecycle honesty ---------------------------------------------
    if task_id:
        task = q("SELECT status, started_at FROM tasks WHERE id = ?", (task_id,))
        if task:
            print("\n5️⃣  TASK LIFECYCLE")
            t = task[0]
            age_hr = None
            try:
                from datetime import datetime

                started = datetime.fromisoformat(t["started_at"].replace("Z", "+00:00"))
                age_hr = (datetime.now() - started).total_seconds() / 3600
            except (ValueError, AttributeError):
                pass
            age_str = f"  ({age_hr:.1f}h old)" if age_hr else ""
            print(f"   {t['status']:<12}: 1{age_str}")
            if t["status"] == "in_progress" and age_hr and age_hr > 1:
                print("   ⚠️  task 'in_progress' for over an hour — never closed out")
        else:
            print("\n5️⃣  TASK LIFECYCLE")
            print(f"   (task {task_id} not found)")
    else:
        tasks_status = q("SELECT status, COUNT(*) c FROM tasks GROUP BY status ORDER BY c DESC")
        print("\n5️⃣  TASK LIFECYCLE")
        for r in tasks_status:
            print(f"   {r['status']:<12}: {r['c']}")
        stuck = q("""SELECT COUNT(*) c FROM tasks
                   WHERE status='in_progress' AND started_at < datetime('now', '-1 hour')""")[0]["c"]
        if stuck:
            print(f"   ⚠️  {stuck} task(s) 'in_progress' for over an hour — never closed out")

    # --- 6. Error budget burn ---------------------------------------------------
    err_hours = q(
        f"""SELECT substr(timestamp, 1, 13) hr, COUNT(*) c FROM errors
               WHERE level IN ('HIGH','CRITICAL') {task_filter} GROUP BY hr ORDER BY hr""",
        tparam,
    )
    err_agents = q(
        f"""SELECT COALESCE(agent_name,'(none)') a, message, COUNT(*) c FROM errors
               WHERE level='HIGH' {task_filter} GROUP BY a, message ORDER BY c DESC LIMIT 5""",
        tparam,
    )
    print("\n6️⃣  ERROR BURN (HIGH+CRITICAL per hour)")
    if task_id:
        print(f"   (scoped to task {task_id})")
    for r in err_hours:
        bar = "#" * min(60, r["c"] // 20 or (1 if r["c"] else 0))
        print(f"   {r['hr']}  {r['c']:>5}  {bar}")
    print("   top error signatures:")
    for r in err_agents:
        print(f"      ×{r['c']:<4} [{r['a']}] {r['message'][:60]}")

    # --- 7. Token spend vs outcomes ----------------------------------------------
    if task_id:
        print("\n7️⃣  SPEND VS OUTCOMES")
        print("   (token_log has no task_id — global spend only)")
        print("   (run without --task for token breakdown)")
    else:
        try:
            tok = cur.execute("SELECT MIN(timestamp), MAX(timestamp), SUM(tokens_used) FROM token_log").fetchone()
            if tok and tok[2]:
                applied = cur.execute("SELECT COUNT(*) c FROM edit_proposals WHERE status='applied'").fetchone()[0]
                print("\n7️⃣  SPEND VS OUTCOMES")
                print(f"   tokens spent : {tok[2]:,}")
                print(f"   first/last   : {tok[0][:16]} → {(tok[1] or '')[:16]}")
                if applied:
                    print(f"   cost per applied edit: {tok[2] // applied:,} tokens")
        except Exception as e:
            print(f"\n7️⃣  SPEND VS OUTCOMES: unavailable ({e})")

    conn.close()


def run_adhoc_sql(sql: str):
    """Execute one ad-hoc read query and print the result table to stdout.

    The connection is read-only, so writes fail at the SQLite level regardless
    of the statement text — safe against a live unattended run.
    """
    conn = _connect_ro()
    try:
        cur = conn.cursor()
        try:
            rows = cur.execute(sql).fetchall()
        except sqlite3.Error as e:
            print(f"❌ SQL error: {e}")
            return 1
    finally:
        conn.close()

    print(f"\n{'=' * 80}")
    print(f"🗄️  Ad-hoc query on {_db_file()}")
    print(f"{'=' * 80}\n")

    if not rows:
        print("✅ executed — 0 rows")
        return 0

    headers = list(rows[0].keys())
    table_rows = [["NULL" if v is None else (v.decode("utf-8", "replace") if isinstance(v, bytes) else v) for v in r] for r in rows]
    _print_table(headers, table_rows)
    print(f"\n{len(rows)} row(s)")
    return 0


def run_model_health(limit: int = 30):
    """Per-model flakiness report from core.model_health (recency-weighted)."""
    try:
        from core import model_health as mh
    except ImportError:
        print("❌ core.model_health unavailable — run from the PrizmForge repo root.")
        return 1

    rows = mh.health_report(limit=limit)
    print(f"\n{'=' * 80}")
    print(f"🩺 MODEL HEALTH (recency-weighted, half-life {mh._setting('half_life_minutes')}m) — {_db_file()}")
    print(f"{'=' * 80}\n")

    if not rows:
        print("No outcome events recorded yet.")
        return 0

    _print_table(
        ["model_ref", "attempts", "fail_ratio", "streak", "avg_ms", "demoted", "until", "reason"],
        [[r["model_ref"], r["attempts"], r["fail_ratio"], r["streak"], r["avg_ms"], r["demoted"], r["until"], r["reason"]] for r in rows],
    )
    demoted = [r["model_ref"] for r in rows if r["demoted"]]
    if demoted:
        print(f"\n⬇️  demoted (deprioritized in fallback): {', '.join(demoted)}")
    return 0


def _print_data_window() -> None:
    """Print the newest timestamp recorded in the diagnostic tables.

    Guards against stale/copied DB snapshots: a dump whose funnel diverges
    from the live DB is immediately visible because the record watermark is
    printed up front.
    """
    conn, cur, _, _ = _get_db()
    newest = "N/A"
    for table, col in (
        ("errors", "timestamp"),
        ("events", "timestamp"),
        ("edit_proposals", "created_at"),
        ("file_write_log", "log_id"),
        ("tasks", "updated_at"),
    ):
        try:
            row = cur.execute(f"SELECT MAX({col}) FROM {table}").fetchone()
        except sqlite3.Error:
            continue
        if row and row[0] and (newest == "N/A" or str(row[0]) > newest):
            newest = str(row[0])
    conn.close()
    print(f"   📆 data window: latest record seen {newest}")


def run_full_diagnostic(task_id: str | None = None, limit: int = 40):
    """Convenience command that dumps the most useful diagnostic views."""
    print("\n" + "=" * 80)
    print("🔬 FULL DIAGNOSTIC DUMP")
    print("=" * 80)
    _print_data_window()

    show_run_effectiveness(task_id=task_id)
    show_edit_proposals(task_id=task_id, limit=limit)
    show_file_write_log(limit=limit)
    show_errors(level="HIGH", limit=30)
    show_errors(level="CRITICAL", limit=20)
    show_errors(keyword="full_replace", limit=20)
    show_errors(keyword="materialize", limit=20)
    show_edit_events(limit=60)
    show_git_failures(limit=20)
    show_file_line_counts(limit=30)

    print("\n" + "=" * 80)
    print("Diagnostic dump complete.")
    print("=" * 80 + "\n")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description="Query agent responses and diagnostic tables from the PrizmForge database (read-only)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --diagnostic                     # full dump (default limit 40)
  %(prog)s --diagnostic --task task_001     # scoped to one task
  %(prog)s --responses                      # recent developer LLM responses
  %(prog)s --responses --agent reviewer     # any agent's responses
  %(prog)s --responses --file app.py --modified-only
  %(prog)s --proposals                      # just edit proposals
  %(prog)s --events --limit 100             # lifecycle events
  %(prog)s --errors HIGH --limit 10         # recent HIGH errors
  %(prog)s --errors --keyword materialize   # search error text
  %(prog)s --write-log                      # materialization log
  %(prog)s --line-counts                    # file sizes
  %(prog)s --sql "SELECT * FROM agent_feedback WHERE addressed=0"
  %(prog)s --model-health                    # per-model flakiness (recency-weighted)
  %(prog)s --db /path/to/other/repo/.PrizmForge/agents.db --diagnostic
        """,
    )
    parser.add_argument("--db", help="Path to an agents.db (default: this project's .PrizmForge/agents.db)")
    parser.add_argument("--diagnostic", action="store_true", help="Run full diagnostic dump")
    parser.add_argument("--task", help="Scope diagnostic to a specific task_id")
    parser.add_argument("--limit", type=int, default=40, help="Row limit for list views (default 40)")
    parser.add_argument("--responses", action="store_true", help="List recent agent responses from agent_responses_archive")
    parser.add_argument("--agent", default="developer", help="Agent name for --responses (default: developer)")
    parser.add_argument("--file", help="Filter --responses by text/file mention")
    parser.add_argument("--modified-only", action="store_true", help="--responses: only ones tied to applied proposals + reviewer approval")
    parser.add_argument("--sql", help='Ad-hoc read query, e.g. --sql "SELECT category, COUNT(*) FROM agent_feedback GROUP BY category"')
    parser.add_argument("--model-health", action="store_true", help="Per-model flakiness report (recency-weighted)")
    parser.add_argument("--proposals", action="store_true", help="Show edit proposals")
    parser.add_argument("--full-replace", action="store_true", help="Only show full_replace/fallback proposals (with --proposals)")
    parser.add_argument("--events", action="store_true", help="Show edit/proposal lifecycle events")
    parser.add_argument("--errors", nargs="?", const="all", help="Show errors (optional level: HIGH, CRITICAL, all)")
    parser.add_argument("--keyword", help="Filter errors by keyword in message/context/file/function")
    parser.add_argument("--write-log", action="store_true", help="Show file_write_log")
    parser.add_argument("--line-counts", action="store_true", help="Show file line counts")

    args = parser.parse_args()

    global _DB_PATH_OVERRIDE
    if args.db:
        _DB_PATH_OVERRIDE = args.db

    if args.sql:
        return run_adhoc_sql(args.sql)

    if args.model_health:
        return run_model_health(limit=args.limit)

    if args.diagnostic:
        run_full_diagnostic(task_id=args.task, limit=args.limit)
        return 0

    if args.responses:
        list_recent_developer_responses(
            task_id=args.task,
            limit=args.limit,
            agent_name=args.agent,
            file_filter=args.file,
            modified_only=args.modified_only,
        )
        return 0

    if args.proposals:
        show_edit_proposals(task_id=args.task, limit=args.limit, full_replace_only=args.full_replace)
        return 0

    if args.events:
        show_edit_events(limit=args.limit)
        return 0

    if args.errors is not None:
        level = args.errors if args.errors != "all" else None
        show_errors(level=level, keyword=args.keyword, limit=args.limit)
        return 0

    if args.write_log:
        show_file_write_log(limit=args.limit)
        return 0

    if args.line_counts:
        show_file_line_counts(limit=args.limit)
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
