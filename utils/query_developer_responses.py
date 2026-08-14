#!/usr/bin/env python3
"""
Query and display raw agent responses + diagnostic data from the PrizmForge database.

Useful for debugging JSON parsing failures, inspecting edit proposals,
materialization results, errors, and events.
"""

from __future__ import annotations

import argparse
import csv
import sys
import traceback
from pathlib import Path
from typing import Any

# Project root must be on sys.path before package imports.
# Required when invoking this file directly (not only via `python -m utils...`).
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from cli.commands import cmd_export_db
from core.db import get_db_path
from core.db_connection import get_db_connection

# ---------------------------------------------------------------------------
# Original helper functions (kept intact)
# ---------------------------------------------------------------------------


def list_recent_developer_responses(
    task_id=None,
    limit=10,
    agent_name="developer",
    file_filter=None,
    modified_only=False,
):
    """List recent developer responses with summary info, file filtering, and exact Reviewer approval matching."""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        query_conditions = ["r.agent_name = ?"]
        params = [agent_name]

        if task_id:
            query_conditions.append("r.task_id = ?")
            params.append(task_id)

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
                    AND rev.response LIKE '%\"decision\": \"APPROVE\"%'
                    AND rev.response NOT LIKE '%\"decision\": \"REJECT\"%'
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

    if not responses:
        file_msg = f" mentioning '{file_filter}'" if file_filter else ""
        mod_msg = " that resulted in file changes" if modified_only else ""
        print(f"\n❌ No {agent_name} responses found{file_msg}{mod_msg}")
        return []

    print(f"\n{'=' * 80}")
    filter_msgs = []
    if file_filter:
        filter_msgs.append(f"Filtered by file: '{file_filter}'")
    if modified_only:
        filter_msgs.append("Modified Files Only")

    filter_str = f" ({', '.join(filter_msgs)})" if filter_msgs else ""
    print(f"📋 Recent {agent_name.upper()} Responses ({len(responses)} found){filter_str}")
    print(f"{'=' * 80}\n")

    for row in responses:
        resp_id, timestamp, _agent, task, parse_ok, prompt_len, resp_len, mod_file = row
        status = "✅ Parsed" if parse_ok else "❌ Parse Failed"
        if mod_file:
            status += f" (File Modified: {mod_file})"

        print(f"ID: {resp_id}")
        print(f"   Time: {timestamp}")
        print(f"   Task: {task}")
        print(f"   Status: {status}")
        print(f"   Prompt: {prompt_len:,} chars")
        print(f"   Response: {resp_len:,} chars")
        print()

    return [r[0] for r in responses]


def show_response_detail(response_id, show_full=False, max_chars=2000):
    """Show detailed view of a specific response."""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT timestamp, agent_name, task_id, prompt, response,
                   parse_success, parse_error
            FROM agent_responses_archive
            WHERE id = ?
        """,
            (response_id,),
        )

        row = cursor.fetchone()

    if not row:
        print(f"\n❌ Response ID {response_id} not found\n")
        return

    timestamp, agent, task, prompt, response, parse_ok, parse_error = row

    print(f"\n{'=' * 80}")
    print(f"📄 Response Detail - ID: {response_id}")
    print(f"{'=' * 80}")
    print(f"Time: {timestamp}")
    print(f"Agent: {agent}")
    print(f"Task: {task}")
    print(f"Parse Success: {'✅ Yes' if parse_ok else '❌ No'}")
    if parse_error:
        print(f"Parse Error: {parse_error}")
    print(f"{'=' * 80}\n")

    # PROMPT
    print(f"📥 PROMPT ({len(prompt):,} chars):")
    print("-" * 80)
    if show_full or len(prompt) <= max_chars:
        print(prompt)
    else:
        print(prompt[:max_chars])
        print(f"\n... +{len(prompt) - max_chars:,} more chars (use --full to see all)")
    print()

    # RESPONSE
    print(f"📤 RESPONSE ({len(response):,} chars):")
    print("-" * 80)

    if not response or response.strip() == "":
        print("⚠️  EMPTY RESPONSE - This is the source of the JSON parse error!")
    elif show_full or len(response) <= max_chars:
        print(response)
    else:
        half = max_chars // 2
        print(response[:half])
        print(f"\n... +{len(response) - max_chars:,} more chars ...\n")
        print(response[-half:])
        print(f"\n(use --full to see all {len(response):,} chars)")

    print("\n" + "=" * 80 + "\n")

    # Diagnostic info
    if not parse_ok:
        print("🔍 DIAGNOSTIC INFO:")
        print("-" * 80)

        if not response or response.strip() == "":
            print("❌ Response is empty or whitespace only")
            print("   → This causes 'Expecting value: line 1 column 1' error")
            print("\n💡 Possible causes:")
            print("   1. LLM returned nothing (timeout, content filter, error)")
            print("   2. Network/API error (check endpoint_health table)")
            print("   3. Response was lost in transmission")
        elif not response.strip().startswith("{") and not response.strip().startswith("["):
            print(f"⚠️  Response doesn't start with '{{' or '[' (starts with: {response.strip()[:50]})")
            print("   → Response may be wrapped in markdown or conversational text")
        elif response.count("{") != response.count("}") or response.count("[") != response.count("]"):
            print("⚠️  Unmatched brackets or braces in JSON")
            print("   → Response may be truncated")
        else:
            print("⚠️  Response looks like JSON but parser failed")
            print("   → May have syntax errors inside the JSON")

        print()


def show_failed_parses(task_id=None, limit=10, file_filter=None):
    """Show only responses that failed to parse with optional file filtering."""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        query_conditions = ["parse_success = 0"]
        params = []

        if task_id:
            query_conditions.append("task_id = ?")
            params.append(task_id)

        if file_filter:
            query_conditions.append("(prompt LIKE ? OR response LIKE ?)")
            file_pattern = f"%{file_filter}%"
            params.extend([file_pattern, file_pattern])

        where_clause = " AND ".join(query_conditions)
        query = f"""
            SELECT id, timestamp, agent_name, task_id, parse_error,
                   LENGTH(prompt) as prompt_len,
                   LENGTH(response) as response_len
            FROM agent_responses_archive
            WHERE {where_clause}
            ORDER BY timestamp DESC
            LIMIT ?
        """
        params.append(limit)

        cursor.execute(query, params)
        failures = cursor.fetchall()

    if not failures:
        file_msg = f" mentioning '{file_filter}'" if file_filter else ""
        print(f"\n✅ No parse failures found{file_msg}!\n")
        return

    filter_msg = f" (Filtered by file: '{file_filter}')" if file_filter else ""
    print(f"\n{'=' * 80}")
    print(f"❌ Parse Failures ({len(failures)} found){filter_msg}")
    print(f"{'=' * 80}\n")

    for row in failures:
        resp_id, timestamp, agent, task, error, _prompt_len, resp_len = row

        print(f"ID: {resp_id} | {timestamp}")
        print(f"   Agent: {agent} | Task: {task}")
        print(f"   Response: {resp_len:,} chars")
        print(f"   Error: {error}")
        print()


# ---------------------------------------------------------------------------
# New diagnostic helpers
# ---------------------------------------------------------------------------


def _print_table(headers: list[str], rows: list[tuple], max_col_width: int = 60):
    """Simple pretty-printer for query results."""
    if not rows:
        print("  (no rows)")
        return

    # Truncate long cells for readability
    def trunc(val, width=max_col_width):
        s = str(val) if val is not None else ""
        return s if len(s) <= width else s[: width - 3] + "..."

    col_widths = []
    for i, h in enumerate(headers):
        max_len = len(h)
        for r in rows:
            max_len = max(max_len, len(trunc(r[i])))
        col_widths.append(min(max_len, max_col_width))

    # Header
    header_line = " | ".join(h.ljust(col_widths[i]) for i, h in enumerate(headers))
    print(header_line)
    print("-+-".join("-" * w for w in col_widths))

    for row in rows:
        print(" | ".join(trunc(row[i]).ljust(col_widths[i]) for i in range(len(headers))))


def show_edit_proposals(
    task_id: str | None = None,
    limit: int = 50,
    full_replace_only: bool = False,
    status: str | None = None,
    csv_output: bool = False,
):
    """Show edit proposals, optionally filtered to full_replace / fallback cases."""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Discover available columns (schema may vary slightly)
        cursor.execute("PRAGMA table_info(edit_proposals)")
        columns = [row[1] for row in cursor.fetchall()]

        select_cols = [
            "proposal_id",
            "target_file_path",
            "status",
            "selected_mode",
            "fallback_used",
            "final_mode",
            "created_at",
            "rationale",
        ]
        # Keep only columns that actually exist
        select_cols = [c for c in select_cols if c in columns]
        if not select_cols:
            print("❌ edit_proposals table has unexpected schema")
            return

        where = []
        params: list[Any] = []

        if task_id:
            # Some schemas store task_id, some do not
            if "task_id" in columns:
                where.append("task_id = ?")
                params.append(task_id)

        if full_replace_only:
            # Match either final_mode or selected_mode containing full_replace,
            # or fallback_used truthy
            fr_conditions = []
            if "final_mode" in columns:
                fr_conditions.append("final_mode LIKE '%full_replace%'")
            if "selected_mode" in columns:
                fr_conditions.append("selected_mode LIKE '%full_replace%'")
            if "fallback_used" in columns:
                fr_conditions.append("fallback_used IN (1, '1', 'true', 'True')")
            if fr_conditions:
                where.append("(" + " OR ".join(fr_conditions) + ")")

        if status:
            where.append("status = ?")
            params.append(status)

        where_clause = ("WHERE " + " AND ".join(where)) if where else ""

        query = f"""
            SELECT {", ".join(select_cols)}
            FROM edit_proposals
            {where_clause}
            ORDER BY created_at DESC
            LIMIT ?
        """
        params.append(limit)

        cursor.execute(query, params)
        rows = cursor.fetchall()

    title = "Edit Proposals"
    if full_replace_only:
        title += " (full_replace / fallback only)"
    if status:
        title += f" [status={status}]"

    print(f"\n{'=' * 80}")
    print(f"📦 {title} — {len(rows)} rows")
    print(f"{'=' * 80}\n")

    if csv_output:
        writer = csv.writer(sys.stdout)
        writer.writerow(select_cols)
        writer.writerows(rows)
    else:
        _print_table(select_cols, rows, max_col_width=70)


def show_file_write_log(task_id: str | None = None, limit: int = 100, csv_output: bool = False):
    """Show the file_write_log table."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(file_write_log)")
        columns = [row[1] for row in cursor.fetchall()]

        if not columns:
            print("❌ file_write_log table not found")
            return

        # Prefer the most useful columns
        preferred = ["log_id", "proposal_id", "file_id", "status", "started_at", "completed_at"]
        select_cols = [c for c in preferred if c in columns] or columns

        query = f"SELECT {', '.join(select_cols)} FROM file_write_log ORDER BY log_id DESC LIMIT ?"
        cursor.execute(query, (limit,))
        rows = cursor.fetchall()

    print(f"\n{'=' * 80}")
    print(f"📝 file_write_log — {len(rows)} rows")
    print(f"{'=' * 80}\n")

    if csv_output:
        writer = csv.writer(sys.stdout)
        writer.writerow(select_cols)
        writer.writerows(rows)
    else:
        _print_table(select_cols, rows)


def show_errors(
    level: str | None = None,
    keyword: str | None = None,
    limit: int = 50,
    csv_output: bool = False,
):
    """Show errors, optionally filtered by level and/or keyword."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(errors)")
        columns = [row[1] for row in cursor.fetchall()]

        preferred = ["id", "level", "message", "context", "file_path", "function_name", "task_id", "agent_name", "timestamp"]
        select_cols = [c for c in preferred if c in columns] or columns

        where = []
        params: list[Any] = []

        if level:
            where.append("UPPER(level) = ?")
            params.append(level.upper())

        if keyword:
            # Search across several text columns
            text_cols = [c for c in ["message", "context", "file_path", "function_name"] if c in columns]
            if text_cols:
                like_parts = " OR ".join(f"{c} LIKE ?" for c in text_cols)
                where.append(f"({like_parts})")
                params.extend([f"%{keyword}%"] * len(text_cols))

        where_clause = ("WHERE " + " AND ".join(where)) if where else ""

        query = f"""
            SELECT {", ".join(select_cols)}
            FROM errors
            {where_clause}
            ORDER BY timestamp DESC
            LIMIT ?
        """
        params.append(limit)

        cursor.execute(query, params)
        rows = cursor.fetchall()

    title = "Errors"
    if level:
        title += f" [{level.upper()}]"
    if keyword:
        title += f" (keyword: {keyword})"

    print(f"\n{'=' * 80}")
    print(f"🚨 {title} — {len(rows)} rows")
    print(f"{'=' * 80}\n")

    if csv_output:
        writer = csv.writer(sys.stdout)
        writer.writerow(select_cols)
        writer.writerows(rows)
    else:
        _print_table(select_cols, rows, max_col_width=80)


def show_edit_events(limit: int = 80, csv_output: bool = False):
    """Show events related to the edit / proposal lifecycle."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(events)")
        columns = [row[1] for row in cursor.fetchall()]

        preferred = ["id", "ts", "type", "source", "task_id", "proposal_id", "payload_json"]
        select_cols = [c for c in preferred if c in columns] or columns

        # Filter to the interesting event types
        interesting = [
            "edit.materialized",
            "edit.fallback_used",
            "edit.failed",
            "proposal.created",
            "proposal.approved",
            "proposal.rejected",
        ]
        placeholders = ",".join("?" * len(interesting))

        query = f"""
            SELECT {", ".join(select_cols)}
            FROM events
            WHERE type IN ({placeholders})
            ORDER BY ts DESC
            LIMIT ?
        """
        cursor.execute(query, (*interesting, limit))
        rows = cursor.fetchall()

    print(f"\n{'=' * 80}")
    print(f"📡 Edit / Proposal Lifecycle Events — {len(rows)} rows")
    print(f"{'=' * 80}\n")

    if csv_output:
        writer = csv.writer(sys.stdout)
        writer.writerow(select_cols)
        writer.writerows(rows)
    else:
        _print_table(select_cols, rows, max_col_width=70)


def show_file_line_counts(limit: int = 40):
    """Show approximate current line counts per file (proxy for truncation)."""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Prefer the governed files + file_lines tables
        cursor.execute(
            """
            SELECT f.file_path, COUNT(fl.line_guid) as line_count
            FROM files f
            LEFT JOIN file_lines fl ON fl.file_id = f.file_id AND fl.is_deleted = 0
            WHERE f.is_deleted = 0
            GROUP BY f.file_id, f.file_path
            ORDER BY line_count ASC
            LIMIT ?
        """,
            (limit,),
        )
        rows = cursor.fetchall()

    print(f"\n{'=' * 80}")
    print(f"📏 Current line counts (lowest first — potential truncation candidates) — {len(rows)} files")
    print(f"{'=' * 80}\n")
    _print_table(["file_path", "line_count"], rows)


def run_full_diagnostic(task_id: str | None = None, limit: int = 40):
    """Convenience command that dumps the most useful diagnostic views."""
    print("\n" + "=" * 80)
    print("🔬 FULL DIAGNOSTIC DUMP")
    print("=" * 80)

    show_edit_proposals(task_id=task_id, limit=limit, full_replace_only=True)
    show_file_write_log(limit=limit)
    show_errors(level="HIGH", limit=30)
    show_errors(level="CRITICAL", limit=20)
    show_errors(keyword="full_replace", limit=20)
    show_errors(keyword="materialize", limit=20)
    show_edit_events(limit=60)
    show_file_line_counts(limit=30)

    print("\n" + "=" * 80)
    print("Diagnostic dump complete.")
    print("=" * 80 + "\n")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():  # noqa: C901
    parser = argparse.ArgumentParser(
        description="Query agent responses and diagnostic tables from the PrizmForge database",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Simple functionality
  python query_developer_responses.py --list -m
  python query_developer_responses.py --show 84 --full
  python query_developer_responses.py --failures
  python query_developer_responses.py --export

  # Diagnostic commands
  python query_developer_responses.py --proposals --full-replace
  python query_developer_responses.py --proposals --status applied -n 30
  python query_developer_responses.py --write-log
  python query_developer_responses.py --errors-high
  python query_developer_responses.py --errors-edit
  python query_developer_responses.py --events-edit
  python query_developer_responses.py --line-counts
  python query_developer_responses.py --diagnostic          # full useful dump
  python query_developer_responses.py --diagnostic --task task_001

  # Windows bash call
  PYTHONIOENCODING=utf-8 "$USERPROFILE\\AppData\\Local\\Python3129\\python.exe" -m utils.query_developer_responses --diagnostic > ./report/diag.txt
        """,
    )

    # Original actions
    parser.add_argument("--list", action="store_true", help="List recent developer responses")
    parser.add_argument("--show", type=int, metavar="ID", help="Show detailed view of response by ID")
    parser.add_argument("--latest", action="store_true", help="Show latest developer response")
    parser.add_argument("--failures", action="store_true", help="Show only responses that failed to parse")
    parser.add_argument("-e", "--export", action="store_true", help="Export database tables to CSV")

    # New diagnostic actions
    parser.add_argument("--proposals", action="store_true", help="Show edit_proposals")
    parser.add_argument("--full-replace", action="store_true", help="When used with --proposals, show only full_replace / fallback proposals")
    parser.add_argument("--status", metavar="STATUS", help="Filter proposals by status (pending/approved/applied/rejected/...)")
    parser.add_argument("--write-log", action="store_true", help="Show file_write_log")
    parser.add_argument("--errors-high", action="store_true", help="Show HIGH level errors")
    parser.add_argument("--errors-critical", action="store_true", help="Show CRITICAL level errors")
    parser.add_argument("--errors-edit", action="store_true", help="Show errors containing editing-related keywords")
    parser.add_argument("--events-edit", action="store_true", help="Show edit/proposal lifecycle events")
    parser.add_argument("--line-counts", action="store_true", help="Show current line counts per file (lowest first)")
    parser.add_argument("--diagnostic", action="store_true", help="Run a full diagnostic dump of the most useful tables")

    # Common options
    parser.add_argument(
        "-m", "--modified-files", "--modified", action="store_true", dest="modified_only", help="Only show responses that resulted in an applied edit"
    )
    parser.add_argument("--task", metavar="TASK_ID", help="Filter by task ID")
    parser.add_argument("-f", "--file", metavar="FILE_PATH", help="Filter responses mentioning specific file path")
    parser.add_argument("--agent", default="developer", help="Agent name (default: developer)")
    parser.add_argument("-n", "--number", "--limit", type=int, default=10, dest="limit", help="Number of rows to show (default: 10)")
    parser.add_argument("--full", action="store_true", help="Show full response (no truncation)")
    parser.add_argument("--max-chars", type=int, default=2000, help="Max chars when not using --full (default: 2000)")
    parser.add_argument("--csv", action="store_true", help="Output results as CSV instead of a formatted table")

    args = parser.parse_args()

    # Validate that at least one action was requested
    actions = [
        args.list,
        args.show,
        args.latest,
        args.failures,
        args.export,
        args.proposals,
        args.write_log,
        args.errors_high,
        args.errors_critical,
        args.errors_edit,
        args.events_edit,
        args.line_counts,
        args.diagnostic,
    ]
    if not any(actions):
        parser.print_help()
        sys.exit(1)

    print(f"\n🔍 Database: {get_db_path()}\n")

    try:
        if args.export:
            cmd_export_db(task_id=args.task)

        elif args.diagnostic:
            run_full_diagnostic(task_id=args.task, limit=max(args.limit, 30))

        elif args.proposals:
            show_edit_proposals(
                task_id=args.task,
                limit=args.limit,
                full_replace_only=args.full_replace,
                status=args.status,
                csv_output=args.csv,
            )

        elif args.write_log:
            show_file_write_log(task_id=args.task, limit=args.limit, csv_output=args.csv)

        elif args.errors_high:
            show_errors(level="HIGH", limit=args.limit, csv_output=args.csv)

        elif args.errors_critical:
            show_errors(level="CRITICAL", limit=args.limit, csv_output=args.csv)

        elif args.errors_edit:
            # Multiple keyword passes for the most relevant editing problems
            for kw in ["full_replace", "materialize", "initialize_file_lines", "validation", "GUID", "conflicted"]:
                show_errors(keyword=kw, limit=15, csv_output=args.csv)

        elif args.events_edit:
            show_edit_events(limit=args.limit, csv_output=args.csv)

        elif args.line_counts:
            show_file_line_counts(limit=args.limit)

        elif args.failures:
            show_failed_parses(task_id=args.task, limit=args.limit, file_filter=args.file)

        elif args.list:
            list_recent_developer_responses(
                task_id=args.task,
                limit=args.limit,
                agent_name=args.agent,
                file_filter=args.file,
                modified_only=args.modified_only,
            )

        elif args.show:
            show_response_detail(args.show, show_full=args.full, max_chars=args.max_chars)

        elif args.latest:
            response_ids = list_recent_developer_responses(
                task_id=args.task,
                limit=1,
                agent_name=args.agent,
                file_filter=args.file,
                modified_only=args.modified_only,
            )
            if response_ids:
                show_response_detail(response_ids[0], show_full=args.full, max_chars=args.max_chars)

    except KeyboardInterrupt:
        print("\n\n👋 Interrupted\n")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error: {e}\n")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
