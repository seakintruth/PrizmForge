#!/usr/bin/env python3
"""
Query and display raw agent responses from the database.
Useful for debugging JSON parsing failures and seeing what the LLM actually returned.
"""

import sys
import argparse
from pathlib import Path
from datetime import datetime

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.db import get_db_path
from core.db_connection import get_db_connection


def list_recent_developer_responses(task_id=None, limit=10, agent_name="developer"):
    """List recent developer responses with summary info."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        if task_id:
            cursor.execute("""
                SELECT id, timestamp, agent_name, parse_success, 
                       LENGTH(prompt) as prompt_len,
                       LENGTH(response) as response_len
                FROM agent_responses_archive
                WHERE agent_name = ? AND task_id = ?
                ORDER BY timestamp DESC
                LIMIT ?
            """, (agent_name, task_id, limit))
        else:
            cursor.execute("""
                SELECT id, timestamp, agent_name, task_id, parse_success,
                       LENGTH(prompt) as prompt_len,
                       LENGTH(response) as response_len
                FROM agent_responses_archive
                WHERE agent_name = ?
                ORDER BY timestamp DESC
                LIMIT ?
            """, (agent_name, limit))
        
        responses = cursor.fetchall()
    
    if not responses:
        print(f"\n❌ No {agent_name} responses found")
        return []
    
    print(f"\n{'='*80}")
    print(f"📋 Recent {agent_name.upper()} Responses ({len(responses)} found)")
    print(f"{'='*80}\n")
    
    for row in responses:
        if task_id:
            resp_id, timestamp, agent, parse_ok, prompt_len, resp_len = row
            task = task_id
        else:
            resp_id, timestamp, agent, task, parse_ok, prompt_len, resp_len = row
        
        status = "✅ Parsed" if parse_ok else "❌ Parse Failed"
        
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
        
        cursor.execute("""
            SELECT timestamp, agent_name, task_id, prompt, response, 
                   parse_success, parse_error
            FROM agent_responses_archive
            WHERE id = ?
        """, (response_id,))
        
        row = cursor.fetchone()
    
    if not row:
        print(f"\n❌ Response ID {response_id} not found\n")
        return
    
    timestamp, agent, task, prompt, response, parse_ok, parse_error = row
    
    print(f"\n{'='*80}")
    print(f"📄 Response Detail - ID: {response_id}")
    print(f"{'='*80}")
    print(f"Time: {timestamp}")
    print(f"Agent: {agent}")
    print(f"Task: {task}")
    print(f"Parse Success: {'✅ Yes' if parse_ok else '❌ No'}")
    if parse_error:
        print(f"Parse Error: {parse_error}")
    print(f"{'='*80}\n")
    
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
        # Show first and last parts
        half = max_chars // 2
        print(response[:half])
        print(f"\n... +{len(response) - max_chars:,} more chars ...\n")
        print(response[-half:])
        print(f"\n(use --full to see all {len(response):,} chars)")
    
    print("\n" + "="*80 + "\n")
    
    # Diagnostic info
    if not parse_ok:
        print("🔍 DIAGNOSTIC INFO:")
        print("-" * 80)
        
        # Check response characteristics
        if not response or response.strip() == "":
            print("❌ Response is empty or whitespace only")
            print("   → This causes 'Expecting value: line 1 column 1' error")
            print("\n💡 Possible causes:")
            print("   1. LLM returned nothing (timeout, content filter, error)")
            print("   2. Network/API error (check endpoint_health table)")
            print("   3. Response was lost in transmission")
        elif not response.strip().startswith('{'):
            print(f"⚠️  Response doesn't start with '{{' (starts with: {response.strip()[:50]})")
            print("   → Response may be wrapped in markdown or text")
        elif response.count('{') != response.count('}'):
            print(f"⚠️  Unmatched braces: {response.count('{')} open, {response.count('}')} close")
            print("   → Response may be truncated")
        else:
            print("⚠️  Response looks like JSON but parser failed")
            print("   → May have syntax errors inside the JSON")
        
        print()


def show_failed_parses(task_id=None, limit=10):
    """Show only responses that failed to parse."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        if task_id:
            cursor.execute("""
                SELECT id, timestamp, agent_name, parse_error,
                       LENGTH(prompt) as prompt_len,
                       LENGTH(response) as response_len
                FROM agent_responses_archive
                WHERE parse_success = 0 AND task_id = ?
                ORDER BY timestamp DESC
                LIMIT ?
            """, (task_id, limit))
        else:
            cursor.execute("""
                SELECT id, timestamp, agent_name, task_id, parse_error,
                       LENGTH(prompt) as prompt_len,
                       LENGTH(response) as response_len
                FROM agent_responses_archive
                WHERE parse_success = 0
                ORDER BY timestamp DESC
                LIMIT ?
            """, (limit,))
        
        failures = cursor.fetchall()
    
    if not failures:
        print(f"\n✅ No parse failures found!\n")
        return
    
    print(f"\n{'='*80}")
    print(f"❌ Parse Failures ({len(failures)} found)")
    print(f"{'='*80}\n")
    
    for row in failures:
        if task_id:
            resp_id, timestamp, agent, error, prompt_len, resp_len = row
            task = task_id
        else:
            resp_id, timestamp, agent, task, error, prompt_len, resp_len = row
        
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
  # List recent developer responses
  python query_developer_responses.py --list
  
  # List for specific task
  python query_developer_responses.py --list --task task_001
  
  # Show full detail for response ID 42
  python query_developer_responses.py --show 42 --full
  
  # Show only failed parses
  python query_developer_responses.py --failures
  
  # Show latest response
  python query_developer_responses.py --latest --full
        """
    )
    
    parser.add_argument('--list', action='store_true', 
                       help='List recent developer responses')
    parser.add_argument('--show', type=int, metavar='ID',
                       help='Show detailed view of response by ID')
    parser.add_argument('--latest', action='store_true',
                       help='Show latest developer response')
    parser.add_argument('--failures', action='store_true',
                       help='Show only responses that failed to parse')
    parser.add_argument('--task', metavar='TASK_ID',
                       help='Filter by task ID')
    parser.add_argument('--agent', default='developer',
                       help='Agent name to query (default: developer)')
    parser.add_argument('--limit', type=int, default=10,
                       help='Number of responses to show (default: 10)')
    parser.add_argument('--full', action='store_true',
                       help='Show full response (no truncation)')
    parser.add_argument('--max-chars', type=int, default=2000,
                       help='Max chars to show when not using --full (default: 2000)')
    
    args = parser.parse_args()
    
    # Validate at least one action specified
    if not any([args.list, args.show, args.latest, args.failures]):
        parser.print_help()
        sys.exit(1)
    
    print(f"\n🔍 Querying database: {get_db_path()}\n")
    
    try:
        if args.failures:
            show_failed_parses(task_id=args.task, limit=args.limit)
        
        elif args.list:
            list_recent_developer_responses(
                task_id=args.task, 
                limit=args.limit,
                agent_name=args.agent
            )
        
        elif args.show:
            show_response_detail(
                args.show, 
                show_full=args.full,
                max_chars=args.max_chars
            )
        
        elif args.latest:
            # Get latest ID
            response_ids = list_recent_developer_responses(
                task_id=args.task,
                limit=1,
                agent_name=args.agent
            )
            if response_ids:
                show_response_detail(
                    response_ids[0],
                    show_full=args.full,
                    max_chars=args.max_chars
                )
    
    except KeyboardInterrupt:
        print("\n\n👋 Interrupted\n")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error: {e}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
    