#!/usr/bin/env python3
"""
Line/size stats for every Python and bash file in PrizmForge.

Writes Markdown under report/ (same tree export_project_zip.py packs).

Usage:
  python utils/loc_stats.py
  python utils/loc_stats.py --out report/loc_stats.md
  python utils/loc_stats.py --top 30 --no-stamp
  python utils/loc_stats.py --root /path/to/PrizmForge
"""

from __future__ import annotations

import argparse
import statistics
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

SKIP_DIR_NAMES = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".PrizmForge",
    "htmlcov",
    "node_modules",
    "dist",
    "build",
    "exports",
}

EXTENSIONS = {".py": "python", ".sh": "bash", ".bash": "bash"}

LINE_BUCKETS = (
    (0, 50),
    (51, 100),
    (101, 200),
    (201, 400),
    (401, 800),
    (801, 1600),
    (1601, 10_000),
)


def _should_skip(path: Path, root: Path) -> bool:
    try:
        parts = path.relative_to(root).parts
    except ValueError:
        return True
    return any(part in SKIP_DIR_NAMES for part in parts)


def _collect(root: Path) -> list[dict]:
    rows: list[dict] = []
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix not in EXTENSIONS:
            continue
        if _should_skip(path, root):
            continue
        data = path.read_bytes()
        text = data.decode("utf-8", errors="replace")
        lines = text.splitlines()
        nlines = len(lines)
        nonempty = sum(1 for ln in lines if ln.strip())
        lengths = [len(ln) for ln in lines]
        rel = path.relative_to(root).as_posix()
        top = rel.split("/", 1)[0] if "/" in rel else "(root)"
        rows.append(
            {
                "path": rel,
                "kind": EXTENSIONS[path.suffix],
                "bytes": len(data),
                "lines": nlines,
                "nonempty": nonempty,
                "max_line": max(lengths, default=0),
                "avg_line": (sum(lengths) / nlines) if nlines else 0.0,
                "top": top,
            }
        )
    rows.sort(key=lambda r: (-r["lines"], r["path"]))
    return rows


def _fmt_int(n: int) -> str:
    return f"{n:,}"


def _fmt_bytes(n: int) -> str:
    if n >= 1024 * 1024:
        return f"{n / (1024 * 1024):.2f} MiB ({_fmt_int(n)} B)"
    if n >= 1024:
        return f"{n / 1024:.1f} KiB ({_fmt_int(n)} B)"
    return f"{_fmt_int(n)} B"


def _percentile(values: list[int], p: int) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return float(values[0])
    pct = max(1, min(99, p))
    return float(statistics.quantiles(values, n=100)[pct - 1])


def _sum(rows: list[dict], key: str) -> int:
    return sum(int(r[key]) for r in rows)


def _md_table(headers: list[str], body: list[list[str]], align_right: set[int] | None = None) -> str:
    align_right = align_right or set()
    sep = []
    for i, _ in enumerate(headers):
        sep.append("---:" if i in align_right else "---")
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(sep) + " |",
    ]
    for row in body:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def _render(rows: list[dict], *, root: Path, top_n: int, generated: str) -> str:
    py = [r for r in rows if r["kind"] == "python"]
    sh = [r for r in rows if r["kind"] == "bash"]
    prod = [r for r in rows if not r["path"].startswith("tests/")]
    tests = [r for r in rows if r["path"].startswith("tests/")]
    line_counts = [r["lines"] for r in rows]

    packages: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        packages[r["top"]].append(r)

    out: list[str] = []
    out.append("# PrizmForge Python + bash LOC stats")
    out.append("")
    out.append(f"- Generated: `{generated}`")
    out.append(f"- Root: `{root}`")
    out.append("- Extensions: `.py`, `.sh`, `.bash`")
    out.append("- Excluded dirs: " + ", ".join(f"`{name}`" for name in sorted(SKIP_DIR_NAMES)))
    out.append("- Lines are physical (blanks + comments included). Nonempty ignores whitespace-only lines.")
    out.append("")

    out.append("## Totals")
    out.append("")
    out.append(
        _md_table(
            ["Set", "Files", "Lines", "Nonempty", "Size"],
            [
                [
                    "**Python**",
                    _fmt_int(len(py)),
                    _fmt_int(_sum(py, "lines")),
                    _fmt_int(_sum(py, "nonempty")),
                    _fmt_bytes(_sum(py, "bytes")),
                ],
                [
                    "**Bash**",
                    _fmt_int(len(sh)),
                    _fmt_int(_sum(sh, "lines")),
                    _fmt_int(_sum(sh, "nonempty")),
                    _fmt_bytes(_sum(sh, "bytes")),
                ],
                [
                    "**All**",
                    _fmt_int(len(rows)),
                    _fmt_int(_sum(rows, "lines")),
                    _fmt_int(_sum(rows, "nonempty")),
                    _fmt_bytes(_sum(rows, "bytes")),
                ],
                [
                    "Production (non-`tests/`)",
                    _fmt_int(len(prod)),
                    _fmt_int(_sum(prod, "lines")),
                    _fmt_int(_sum(prod, "nonempty")),
                    _fmt_bytes(_sum(prod, "bytes")),
                ],
                [
                    "Tests",
                    _fmt_int(len(tests)),
                    _fmt_int(_sum(tests, "lines")),
                    _fmt_int(_sum(tests, "nonempty")),
                    _fmt_bytes(_sum(tests, "bytes")),
                ],
            ],
            align_right={1, 2, 3, 4},
        )
    )
    out.append("")
    if rows:
        test_share = 100.0 * _sum(tests, "lines") / _sum(rows, "lines")
        out.append(
            f"Tests are **{test_share:.0f}% of lines** and "
            f"**{100.0 * len(tests) / len(rows):.0f}% of files**. "
            f"Mean file = **{statistics.mean(line_counts):.1f}** lines; "
            f"median = **{statistics.median(line_counts):.0f}**; "
            f"max = **{max(line_counts):,}** (`{rows[0]['path']}`)."
        )
        out.append("")

    out.append("## By package")
    out.append("")
    pkg_rows = []
    for name, group in sorted(packages.items(), key=lambda kv: (-_sum(kv[1], "lines"), kv[0])):
        pkg_rows.append(
            [
                f"`{name}/`" if name != "(root)" else "repo root",
                _fmt_int(len(group)),
                _fmt_int(_sum(group, "lines")),
                _fmt_int(_sum(group, "nonempty")),
                _fmt_bytes(_sum(group, "bytes")),
            ]
        )
    out.append(
        _md_table(
            ["Package", "Files", "Lines", "Nonempty", "Size"],
            pkg_rows,
            align_right={1, 2, 3, 4},
        )
    )
    out.append("")

    out.append("## Bash only")
    out.append("")
    if sh:
        out.append(
            _md_table(
                ["File", "Lines", "Nonempty", "Bytes", "Longest line"],
                [
                    [
                        f"`{r['path']}`",
                        _fmt_int(r["lines"]),
                        _fmt_int(r["nonempty"]),
                        _fmt_int(r["bytes"]),
                        _fmt_int(r["max_line"]),
                    ]
                    for r in sh
                ]
                + [
                    [
                        "**Total**",
                        _fmt_int(_sum(sh, "lines")),
                        _fmt_int(_sum(sh, "nonempty")),
                        _fmt_int(_sum(sh, "bytes")),
                        "",
                    ]
                ],
                align_right={1, 2, 3, 4},
            )
        )
    else:
        out.append("_No `.sh` / `.bash` files found._")
    out.append("")

    out.append(f"## Largest files (top {top_n})")
    out.append("")
    out.append(
        _md_table(
            ["Lines", "Nonempty", "Bytes", "Kind", "File"],
            [
                [
                    _fmt_int(r["lines"]),
                    _fmt_int(r["nonempty"]),
                    _fmt_int(r["bytes"]),
                    r["kind"],
                    f"`{r['path']}`",
                ]
                for r in rows[:top_n]
            ],
            align_right={0, 1, 2},
        )
    )
    out.append("")

    out.append("## Size distribution")
    out.append("")
    bucket_rows = []
    for lo, hi in LINE_BUCKETS:
        group = [r for r in rows if lo <= r["lines"] <= hi]
        bucket_rows.append(
            [
                f"{lo}-{hi}",
                _fmt_int(len(group)),
                _fmt_int(_sum(group, "lines")),
            ]
        )
    out.append(
        _md_table(
            ["Line range", "Files", "Combined lines"],
            bucket_rows,
            align_right={1, 2},
        )
    )
    out.append("")

    if len(line_counts) >= 2:
        out.append("Percentiles (lines per file):")
        out.append("")
        out.append(", ".join(f"p{p} **{_percentile(line_counts, p):.0f}**" for p in (50, 75, 90, 95, 99)))
        out.append("")

    long_files = [r for r in rows if r["max_line"] >= 120]
    out.append("## Longest source lines")
    out.append("")
    out.append(f"{len(long_files)} files have at least one line >= 120 characters.")
    out.append("")
    longest = sorted(rows, key=lambda r: (-r["max_line"], r["path"]))[:12]
    out.append(
        _md_table(
            ["Max line", "File"],
            [[_fmt_int(r["max_line"]), f"`{r['path']}`"] for r in longest],
            align_right={0},
        )
    )
    out.append("")

    out.append("## All files")
    out.append("")
    out.append(
        _md_table(
            ["File", "Kind", "Lines", "Nonempty", "Bytes", "Max line", "Avg line"],
            [
                [
                    f"`{r['path']}`",
                    r["kind"],
                    _fmt_int(r["lines"]),
                    _fmt_int(r["nonempty"]),
                    _fmt_int(r["bytes"]),
                    _fmt_int(r["max_line"]),
                    f"{r['avg_line']:.1f}",
                ]
                for r in rows
            ],
            align_right={2, 3, 4, 5, 6},
        )
    )
    out.append("")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        default=None,
        help="Project root (default: parent of utils/)",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="Markdown path (default: report/loc_stats.md)",
    )
    parser.add_argument("--top", type=int, default=20, help="How many largest files to highlight")
    parser.add_argument(
        "--no-stamp",
        action="store_true",
        help="Do not also write report/loc_stats-<timestamp>.md",
    )
    args = parser.parse_args(argv)

    root = Path(args.root).resolve() if args.root else REPO_ROOT
    out_path = Path(args.out).resolve() if args.out else (root / "report" / "loc_stats.md")
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    rows = _collect(root)
    markdown = _render(rows, root=root, top_n=max(1, args.top), generated=generated)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(markdown, encoding="utf-8")
    written = [out_path]

    if not args.no_stamp:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        stamped = out_path.with_name(f"{out_path.stem}-{stamp}{out_path.suffix}")
        stamped.write_text(markdown, encoding="utf-8")
        written.append(stamped)

    print(f"Files scanned: {len(rows)}")
    print(f"Lines: {_sum(rows, 'lines'):,}  nonempty: {_sum(rows, 'nonempty'):,}  bytes: {_sum(rows, 'bytes'):,}")
    for path in written:
        try:
            rel = path.relative_to(root)
        except ValueError:
            rel = path
        print(f"Wrote {rel}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
