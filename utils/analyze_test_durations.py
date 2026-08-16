#!/usr/bin/env python3
"""
Analyze per-test duration reports and suggest slow/normal marker moves.

Reports are written by tests/conftest.py on every pytest session:
  .PrizmForge/reports/test-durations-<batch>-<stamp>.json
  .PrizmForge/reports/test-durations-latest.json   (merged across batches)

Usage:
  python utils/analyze_test_durations.py
  python utils/analyze_test_durations.py --report .PrizmForge/reports/test-durations-latest.json
  python utils/analyze_test_durations.py --promote-above 2.0 --demote-below 0.5
  python utils/analyze_test_durations.py --top 40
  python utils/analyze_test_durations.py --glob '.PrizmForge/reports/test-durations-*.json'
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_LATEST = REPO_ROOT / ".PrizmForge" / "reports" / "test-durations-latest.json"


def _load_report(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    tests = data.get("tests") if isinstance(data, dict) else data
    if not isinstance(tests, list):
        raise ValueError(f"No tests list in {path}")
    return [t for t in tests if isinstance(t, dict) and "nodeid" in t]


def _merge_reports(paths: list[Path]) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for path in paths:
        for t in _load_report(path):
            by_id[t["nodeid"]] = t
    return sorted(by_id.values(), key=lambda r: float(r.get("duration_s", 0)), reverse=True)


def _fmt(seconds: float) -> str:
    if seconds < 1:
        return f"{seconds * 1000:.0f}ms"
    return f"{seconds:.2f}s"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--report",
        type=Path,
        default=None,
        help="Single report JSON (default: test-durations-latest.json)",
    )
    p.add_argument(
        "--glob",
        default=None,
        help="Glob of reports to merge (relative to repo root)",
    )
    p.add_argument(
        "--promote-above",
        type=float,
        default=2.0,
        help="Suggest @pytest.mark.slow when duration >= this and not marked (default: 2.0)",
    )
    p.add_argument(
        "--demote-below",
        type=float,
        default=0.5,
        help="Suggest removing slow when duration < this and marked (default: 0.5)",
    )
    p.add_argument("--top", type=int, default=30, help="Show top N slowest tests")
    p.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable suggestions only",
    )
    args = p.parse_args(argv)

    tests: list[dict[str, Any]]
    if args.glob:
        paths = sorted(REPO_ROOT.glob(args.glob))
        if not paths:
            print(f"No reports matched: {args.glob}", file=sys.stderr)
            return 1
        tests = _merge_reports(paths)
        sources = [str(x.relative_to(REPO_ROOT)) for x in paths]
    elif args.report:
        path = args.report if args.report.is_absolute() else REPO_ROOT / args.report
        if not path.exists():
            print(f"Report not found: {path}", file=sys.stderr)
            return 1
        tests = _load_report(path)
        sources = [str(path)]
    else:
        if not DEFAULT_LATEST.exists():
            print(
                f"No duration report at {DEFAULT_LATEST}\n"
                "Run the suite first, e.g.:\n"
                "  ./utils/run_tests.sh --full --batched -j 2\n"
                "Then re-run this analyzer.",
                file=sys.stderr,
            )
            return 1
        tests = _load_report(DEFAULT_LATEST)
        sources = [str(DEFAULT_LATEST)]

    promote = [t for t in tests if float(t.get("duration_s", 0)) >= args.promote_above and not t.get("slow")]
    demote = [t for t in tests if float(t.get("duration_s", 0)) < args.demote_below and t.get("slow")]
    slow_marked = [t for t in tests if t.get("slow")]
    normal = [t for t in tests if not t.get("slow")]

    if args.json:
        out = {
            "sources": sources,
            "count": len(tests),
            "promote_to_slow": [{"nodeid": t["nodeid"], "duration_s": t.get("duration_s")} for t in promote],
            "demote_from_slow": [{"nodeid": t["nodeid"], "duration_s": t.get("duration_s")} for t in demote],
            "slowest": [
                {
                    "nodeid": t["nodeid"],
                    "duration_s": t.get("duration_s"),
                    "slow": bool(t.get("slow")),
                    "outcome": t.get("outcome"),
                }
                for t in tests[: args.top]
            ],
        }
        print(json.dumps(out, indent=2))
        return 0

    print("Sources:")
    for s in sources:
        print(f"  {s}")
    print(f"Tests: {len(tests)}  (slow-marked={len(slow_marked)}, normal={len(normal)})")
    print(f"Thresholds: promote >= {args.promote_above}s  demote < {args.demote_below}s")
    print()

    print(f"=== Top {min(args.top, len(tests))} slowest ===")
    for t in tests[: args.top]:
        tag = "SLOW" if t.get("slow") else "    "
        print(f"  {_fmt(float(t.get('duration_s', 0))):>8}  [{tag}]  {t.get('outcome', '?'):7}  {t['nodeid']}")
    print()

    print(f"=== Promote to @pytest.mark.slow  ({len(promote)}) ===")
    if not promote:
        print("  (none)")
    else:
        for t in promote:
            print(f"  {_fmt(float(t.get('duration_s', 0))):>8}  {t['nodeid']}")
    print()

    print(f"=== Demote from @pytest.mark.slow  ({len(demote)}) ===")
    if not demote:
        print("  (none)")
    else:
        for t in demote:
            print(f"  {_fmt(float(t.get('duration_s', 0))):>8}  {t['nodeid']}")
    print()

    if slow_marked:
        slow_total = sum(float(t.get("duration_s", 0)) for t in slow_marked)
        print(f"Slow-marked wall time (sum of call durations): {_fmt(slow_total)} across {len(slow_marked)} tests")
    if normal:
        normal_total = sum(float(t.get("duration_s", 0)) for t in normal)
        print(f"Normal wall time (sum of call durations): {_fmt(normal_total)} across {len(normal)} tests")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
