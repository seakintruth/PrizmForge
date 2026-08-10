#!/usr/bin/env python3
"""
Query and display raw agent responses from the database.
Useful for debugging JSON parsing failures and seeing what the LLM actually returned.
"""

import argparse
import sys
import traceback
from pathlib import Path

from cli.commands import cmd_export_db
from core.db import get_db_path
from core.db_connection import get_db_connection

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


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

        # 🎯 PHASE 4 INJECTION: Exact SQL Linking between Developer (N) and Reviewer (N+1 / N+2) APPROVE
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


def main():
    parser = argparse.ArgumentParser(
        description="Query and display raw agent responses from the database",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Export database tables to CSV files
  python query_developer_responses.py --export

  # Export database tables for a specific task
  python query_developer_responses.py --export --task task_001

  # List all developer responses that resulted in actual file modifications
  python query_developer_responses.py --list -m

  # List responses that modified app.py
  python query_developer_responses.py --list --file app.py -m -n 50

  # Show full detail for response ID 84
  python query_developer_responses.py --show 84 --full
        """,
    )

    parser.add_argument("--list", action="store_true", help="List recent developer responses")
    parser.add_argument("--show", type=int, metavar="ID", help="Show detailed view of response by ID")
    parser.add_argument("--latest", action="store_true", help="Show latest developer response")
    parser.add_argument(
        "--failures",
        action="store_true",
        help="Show only responses that failed to parse",
    )
    parser.add_argument(
        "-e",
        "--export",
        action="store_true",
        help="Export database tables to CSV files using cli.commands.cmd_export_db",
    )
    parser.add_argument(
        "-m",
        "--modified-files",
        "--modified",
        action="store_true",
        dest="modified_only",
        help="Only show responses that resulted in an applied edit / file modification",
    )
    parser.add_argument("--task", metavar="TASK_ID", help="Filter by task ID")
    parser.add_argument("-f", "--file", metavar="FILE_PATH", help="Filter responses mentioning specific file path (e.g. app.py)")
    parser.add_argument("--agent", default="developer", help="Agent name to query (default: developer)")
    parser.add_argument(
        "-n",
        "--number",
        "--limit",
        type=int,
        default=10,
        dest="limit",
        help="Number of responses to show (default: 10)",
    )
    parser.add_argument("--full", action="store_true", help="Show full response (no truncation)")
    parser.add_argument(
        "--max-chars",
        type=int,
        default=2000,
        help="Max chars to show when not using --full (default: 2000)",
    )

    args = parser.parse_args()

    # Validate at least one action specified
    if not any([args.list, args.show, args.latest, args.failures, args.export]):
        parser.print_help()
        sys.exit(1)

    print(f"\n🔍 Querying database: {get_db_path()}\n")

    try:
        if args.export:
            cmd_export_db(task_id=args.task)

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
