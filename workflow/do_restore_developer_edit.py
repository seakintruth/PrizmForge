#!/usr/bin/env python3
"""Restore developer_edit.py from known-good blob and apply PR83 fixes."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] if (Path(__file__).parent.name == "workflow") else Path.cwd()
target = ROOT / "workflow" / "developer_edit.py"

# Prefer git show from known-good commit; fall back to raw URL
try:
    content = subprocess.check_output(
        ["git", "show", "7cdabba2834bc1404503f0299b824a5d365b1e37:workflow/developer_edit.py"],
        text=True,
    )
except Exception:
    import urllib.request

    url = "https://raw.githubusercontent.com/seakintruth/PrizmForge/7cdabba2834bc1404503f0299b824a5d365b1e37/workflow/developer_edit.py"
    content = urllib.request.urlopen(url, timeout=30).read().decode()

old = "from core.index_context import load_symbol_json_context\nfrom file_editing.undo import snapshot_before_apply"
new = "from core.index_context import load_symbol_json_context\nfrom core.json_parser import parse_json_response\nfrom file_editing.undo import snapshot_before_apply"
if old not in content:
    print("ERROR: import anchor not found", file=sys.stderr)
    sys.exit(1)
content = content.replace(old, new, 1)

old2 = (
    "        try:\n"
    "            decision_data = json.loads(reviewer_response)\n"
    '            decision_result = str(decision_data.get("decision", "REJECT")).upper()\n'
    '            reason = decision_data.get("reason", "")\n'
    '            suggestions = decision_data.get("suggestions") or []\n'
    "        except Exception:\n"
    '            decision_result = "REJECT"\n'
    '            reason = "reviewer response not JSON; failing closed to REJECT"\n'
)
new2 = (
    "        decision_data = parse_json_response(\n"
    "            reviewer_response,\n"
    "            expected_keys=None,\n"
    "            strict=False,\n"
    '            agent_name="reviewer",\n'
    "        )\n"
    "        if decision_data and isinstance(decision_data, dict):\n"
    '            decision_result = str(decision_data.get("decision", "REJECT")).upper()\n'
    '            reason = str(decision_data.get("reason", "") or "")\n'
    '            suggestions = decision_data.get("suggestions") or []\n'
    "            if not isinstance(suggestions, list):\n"
    "                suggestions = []\n"
    "        else:\n"
    '            decision_result = "REJECT"\n'
    '            reason = "reviewer response not JSON; failing closed to REJECT"\n'
)
if old2 not in content:
    print("ERROR: json.loads block not found", file=sys.stderr)
    sys.exit(1)
content = content.replace(old2, new2, 1)

target.write_text(content)
print(f"Wrote {target} ({len(content.splitlines())} lines)")
assert "parse_json_response" in content
assert "def run_developer_mutation" in content
print("OK")
