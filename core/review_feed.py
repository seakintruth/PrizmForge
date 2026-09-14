"""
§16.1 map-first peer review feed.

A reviewer cycle is fed a compact structural **map** of the target repo,
never the full body of arbitrary files:

* ``build_reviewer_map`` — ≤ ``MAX_MAP_ROWS`` rows from ``file_summaries``
  plus the top symbols from ``file_symbols`` (the symbol_index JSON source).
  Source bodies are never pasted into the initial prompt.
* ``extract_need_files`` / ``extract_covered`` — fail-closed parse of the
  reviewer's JSON ``need_files`` and ``covered`` fields. Malformed entries are
  dropped, never turned into blind slice pulls.
* ``serve_need_files`` — serves the requested slices from the **governed DB**
  (``file_lines`` join ``files``), bounded to ``MAX_SLICES`` windows of at
  most ``MAX_LINES_PER_SLICE`` lines each and a hard total-line cap.
* ``blast_radius_paths`` — replaces pick-a-random-sibling with the blast
  radius around a changed/served file: the changed path itself, then depth ≤2
  neighbors discovered from symbol_index (same-symbol consumers) and a cheap,
  capped import scan. Binaries, logos, lockfiles and ``docs/TODO.md`` are
  skipped unless the seed named them.

Deliberately dependency-free: sqlite only, no code-index dependency.
"""

from __future__ import annotations

import logging
import re
from collections import deque
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

MAX_MAP_ROWS = 80
MAX_MAP_SYMBOLS_PER_FILE = 6
MAX_SLICES = 3
MAX_LINES_PER_SLICE = 200
MAX_SLICE_TOTAL_LINES = 500
BLAST_MAX_PATHS = 5
BLAST_MAX_DEPTH = 2
BLAST_MAX_IMPORT_SCAN = 300
_IMPORT_SCAN_HEAD_LINES = 200

_JUNK_EXTENSIONS = frozenset(
    {
        "." + s
        for s in (
            "png",
            "jpg",
            "jpeg",
            "gif",
            "svg",
            "ico",
            "webp",
            "bmp",
            "tif",
            "tiff",
            "woff",
            "woff2",
            "ttf",
            "otf",
            "eot",
            "mp3",
            "mp4",
            "mov",
            "avi",
            "mkv",
            "pdf",
            "zip",
            "gz",
            "tgz",
            "tar",
            "bz2",
            "xz",
            "7z",
            "rar",
            "so",
            "dll",
            "o",
            "a",
            "exe",
        )
    }
)
_JUNK_SUFFIXES = (".min.js", ".min.css", ".map")
_JUNK_NAMES = frozenset(
    {
        "poetry.lock",
        "package-lock.json",
        "yarn.lock",
        "pnpm-lock.yaml",
        "Cargo.lock",
        "go.sum",
        "Gemfile.lock",
        "composer.lock",
    }
)
_TODO_PATH = "docs/TODO.md"


@dataclass(frozen=True)
class SliceSpec:
    """A reviewer-requested line window of a governed file."""

    file_path: str
    start: int
    end: int
    why: str = ""


@dataclass(frozen=True)
class CoveredRange:
    """A line range the reviewer explicitly acknowledged reading."""

    file_path: str
    lines_lo: int = 0
    lines_hi: int = 0


def _norm_path(path: str) -> str:
    return path.replace("\\", "/")


def should_skip_review_path(path: str, *, seed_named: bool = False) -> bool:
    """True when a path must never be fed to a reviewer on its own.

    Binaries and logos are always skipped (a reviewer cannot read them, even
    when seed-named). Lockfiles and ``docs/TODO.md`` are skipped unless
    ``seed_named`` (an explicit seed item named them).
    """
    p = Path(_norm_path(path))
    name = p.name.lower()
    suffix = p.suffix.lower()
    if name.endswith(".lock") and not seed_named:
        return True
    if name.endswith(_JUNK_SUFFIXES):
        return True
    if name in _JUNK_NAMES and not seed_named:
        return True
    if suffix in _JUNK_EXTENSIONS:
        # Reviewers cannot read binaries in any mode; seed naming never
        # makes a .png or .so reviewable.
        return True
    if _norm_path(path).endswith(_TODO_PATH) and not seed_named:
        return True
    return False


def _as_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(str(value).strip())
        except ValueError:
            return None
    if isinstance(value, (float,)):
        try:
            return int(value)
        except (TypeError, ValueError):
            return None
    return None


def _entry_path(entry: dict) -> str | None:
    for key in ("file_path", "file", "path"):
        val = entry.get(key)
        if val and isinstance(val, str):
            return val
    range_key = entry.get("range")
    if isinstance(range_key, dict):
        for key in ("file_path", "file", "path"):
            val = range_key.get(key)
            if val and isinstance(val, str):
                return val
    return None


def _first_int(entry: dict, keys: Sequence[str]) -> int | None:
    """First present integer among keys; ``0`` is a valid answer."""
    for key in keys:
        if key in entry:
            val = _as_int(entry.get(key))
            if val is not None:
                return val
    return None


def _range_from_entry(entry: dict) -> tuple[int, int] | None:
    """Best-effort (start, end) extraction (1-based inclusive)."""
    start = _first_int(entry, ("start", "from", "lines_lo", "line_start", "begin"))
    end = _first_int(entry, ("end", "to", "lines_hi", "line_end"))
    range_key = entry.get("range")
    if isinstance(range_key, dict):
        if start is None:
            start = _first_int(range_key, ("start", "from"))
        if end is None:
            end = _first_int(range_key, ("end", "to"))
    if start is None:
        return None
    if end is None:
        # A start-only request covers a single line; a whole-file
        # acknowledgment is expressed with start=end=0.
        end = start
    if start < 0 or end < 0:
        return None
    if start == 0 and end == 0:
        return (0, 0)
    if end < start:
        start, end = end, start
    if start == 0:
        start = 1
    return (start, end)


def extract_need_files(data: dict) -> list[SliceSpec]:
    """Extract reviewer-requested slices, fail-closed.

    An absent/empty ``need_files`` yields ``[]``. Anything non-list, or an
    entry without a usable path or a non-negative line start, is dropped —
    never coerced into a blind full-file pull.
    """
    if not isinstance(data, dict):
        return []
    raw = data.get("need_files")
    if raw is None:
        return []
    if not isinstance(raw, list):
        logger.warning("Review response need_files is not a list; ignoring (fail-closed)")
        return []

    specs: list[SliceSpec] = []
    for entry in raw:
        if len(specs) >= MAX_SLICES:
            break
        if not isinstance(entry, dict):
            logger.warning("Review response need_files entry is not an object; dropping")
            continue
        path = _entry_path(entry)
        if not path:
            logger.warning("Review response need_files entry missing path; dropping")
            continue
        ranges = _range_from_entry(entry)
        if ranges is None:
            logger.warning("Review response need_files entry for %s missing line range; dropping", path)
            continue
        start, end = ranges
        if start == 0 and end == 0:
            continue
        why = str(entry.get("why") or entry.get("reason") or "")[:200]
        specs.append(SliceSpec(file_path=_norm_path(path), start=start, end=end, why=why))
    return specs


def extract_covered(data: dict) -> list[CoveredRange]:
    """Extract reviewer line-range acknowledgments, fail-closed."""
    if not isinstance(data, dict):
        return []
    raw = data.get("covered")
    if raw is None:
        return []
    if not isinstance(raw, list):
        logger.warning("Review response covered is not a list; ignoring (fail-closed)")
        return []

    covered: list[CoveredRange] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        path = _entry_path(entry)
        if not path:
            continue
        ranges = _range_from_entry(entry)
        if ranges is None:
            continue
        lo, hi = ranges
        covered.append(CoveredRange(file_path=_norm_path(path), lines_lo=lo, lines_hi=hi))
    return covered


def build_reviewer_map(
    conn,
    *,
    max_rows: int = MAX_MAP_ROWS,
    focus_path: str | None = None,
) -> str:
    """Compact structural map of the governed project (symbol_index + summaries).

    One row per file: path, one-line summary, line count and the top few
    symbols. Never includes source bodies. ``focus_path`` (the event file)
    sorts first and is always included within ``max_rows``.
    """
    focus = _norm_path(focus_path) if focus_path else None
    rows = conn.execute("""
        SELECT
            s.file_path, s.summary, s.purpose, s.line_count,
            COALESCE(p.is_binary, 0) AS is_binary
        FROM file_summaries s
        LEFT JOIN project_files p ON p.file_path = s.file_path
        WHERE COALESCE(p.is_binary, 0) = 0
        ORDER BY s.file_path
        """).fetchall()

    map_paths: list[str] = []
    if focus:
        map_paths.append(focus)
    for row in rows:
        path = row[0]
        if path == focus:
            continue
        if should_skip_review_path(path):
            continue
        map_paths.append(path)
        if len(map_paths) >= max_rows:
            break

    symbols: dict[str, list[str]] = {}
    if map_paths:
        placeholders = ",".join("?" * len(map_paths))
        symbol_rows = conn.execute(
            f"""
            SELECT file_path, kind, name
            FROM file_symbols
            WHERE file_path IN ({placeholders})
            ORDER BY file_path, lineno
            """,
            tuple(map_paths),
        ).fetchall()
        for fpath, _kind, name in symbol_rows:
            bucket = symbols.setdefault(fpath, [])
            if len(bucket) < MAX_MAP_SYMBOLS_PER_FILE:
                bucket.append(name)

    by_path = {path: row for row in rows for path in (row[0],)}
    lines: list[str] = []
    for path in map_paths:
        row = by_path.get(path)
        if row is None:
            summary = ""
            line_count = "?"
        else:
            summary = (row[1] or row[2] or "")[:120].replace("\n", " ")
            line_count = row[3] if row[3] is not None else "?"
        syms = ", ".join(symbols.get(path, []))
        row_text = f"- {path} | {line_count} lines"
        if summary:
            row_text += f" | {summary}"
        if syms:
            row_text += f" | Symbols: {syms}"
        lines.append(row_text)

    if not lines:
        return ""
    body = "\n".join(lines)
    if len(map_paths) >= max_rows:
        body += f"\n- ... ({len(map_paths)} of {max_rows} map rows shown)"
    return f"**Target repository map (structural, {len(map_paths)} files):**\n{body}"


def serve_need_files(
    conn,
    specs: Sequence[SliceSpec],
    *,
    max_slices: int = MAX_SLICES,
    max_lines_per_slice: int = MAX_LINES_PER_SLICE,
    max_total_lines: int = MAX_SLICE_TOTAL_LINES,
) -> str:
    """Serve requested line slices from the governed DB (file_lines/files).

    Bound the window to ``max_lines_per_slice`` and hard-stop at
    ``max_total_lines`` lines. Binary/junk paths are refused. Returns "" when
    nothing could be served.
    """
    if not specs:
        return ""
    blocks: list[str] = []
    total_served = 0
    for spec in specs[:max_slices]:
        if should_skip_review_path(spec.file_path, seed_named=True):
            continue
        lo = max(1, int(spec.start))
        hi = int(spec.end)
        if hi < lo:
            continue
        span = hi - lo + 1
        window = min(span, max_lines_per_slice)
        remaining = max_total_lines - total_served
        if remaining <= 0:
            break
        window = min(window, remaining)

        lines = conn.execute(
            """
            SELECT l.content
            FROM file_lines l
            JOIN files f ON f.file_id = l.file_id
            WHERE f.file_path = ?
              AND l.is_deleted = 0
              AND l.sort_order BETWEEN ? AND ?
            ORDER BY l.sort_order
            """,
            (spec.file_path, lo, lo + window - 1),
        ).fetchall()
        if not lines:
            continue

        header = f"**{spec.file_path}** (lines {lo}-{lo + len(lines) - 1})"
        if spec.why:
            header += f" — requested for: {spec.why}"
        body_lines = [f"{line_no}: {content}" for line_no, (content,) in enumerate(lines, start=lo)]
        blocks.append(f"{header}\n```\n" + "\n".join(body_lines) + "\n```")
        total_served += len(lines)

    if not blocks:
        return ""
    joined = "\n\n".join(blocks)
    if total_served >= max_total_lines:
        joined += f"\n\n_Note: at the total line cap ({max_total_lines}); further slices unavailable in this cycle._"
    return joined


def _module_id(path: str) -> str:
    """Importable module id of a path (core/db_helpers.py → core.db_helpers)."""
    p = Path(_norm_path(path))
    if p.suffix and p.suffix.lower() in {".py", ".pyi"}:
        return ".".join(p.with_suffix("").parts)
    return ".".join(p.parts)


def _refs_target(content: str, module_id: str) -> bool:
    """Cheap textual import check: does the head of ``content`` import module_id?"""
    base = module_id.rsplit(".", 1)[-1]
    head = "\n".join(content.splitlines()[:_IMPORT_SCAN_HEAD_LINES])
    if re.search(rf"^\s*(import|from)\s+{re.escape(module_id)}\b", head, flags=re.MULTILINE):
        return True
    if re.search(rf"^\s*(import|from)\s+\S*\.{re.escape(base)}\b", head, flags=re.MULTILINE):
        return True
    return False


def _sort_candidates(candidates: list[tuple], changed_path: str) -> list[tuple]:
    """Order candidates for the import scan: same dir, then tests, then rest."""
    p = Path(_norm_path(changed_path))
    parent_dirs = "/".join(p.parts[:-1]) if len(p.parts) > 1 else ""
    parent_root = parent_dirs.split("/")[0] if parent_dirs else ""

    def sort_key(row: tuple) -> tuple[int, int, str]:
        path = row[0]
        prefix = "/".join(_norm_path(path).split("/")[:-1])
        if prefix == parent_dirs:
            dir_rank = 0
        elif parent_root and prefix == parent_root:
            dir_rank = 1
        elif parent_root and parent_dirs.startswith(parent_root):
            dir_rank = 2
        else:
            dir_rank = 3
        base = path.rsplit("/", 1)[-1]
        is_test = int("/tests/" in path or base.startswith("test_") or base.endswith("_test.py"))
        priority = 0 if is_test else 1
        return (dir_rank, priority, path)

    return sorted(candidates, key=sort_key)


def blast_radius_paths(
    conn,
    changed_path: str,
    *,
    depth: int = BLAST_MAX_DEPTH,
    max_paths: int = BLAST_MAX_PATHS,
    candidates: Sequence[tuple[str, str | None]] | None = None,
) -> list[str]:
    """Blast radius of a changed/served file: changed + callers/callees/tests.

    Discovery is depth-≤2 BFS:
      1. symbol_index consumers — files whose ``file_symbols`` rows share an
         exported symbol name with the changed file (callers/callees);
      2. a capped, cheap import scan (first 200 lines) of nearby files and the
         tests/ trees that import the changed file's module (tests + callers).

    ``candidates`` pre-loads the ``(file_path, content)`` import-scan pool so
    it can be shared across multiple radius probes in one pass.

    Returns ``[changed_path, *radius]`` (changed first), or ``[]`` when the
    changed path itself is a junk file that must not be fed.
    """
    changed = _norm_path(changed_path)
    if should_skip_review_path(changed, seed_named=False):
        return []

    visited = {changed}
    radius: list[str] = []

    module_id = _module_id(changed)
    exported = {
        row[0]
        for row in conn.execute(
            """
            SELECT name FROM file_symbols
            WHERE file_path = ? AND kind IN ('FUNCTION', 'CLASS', 'METHOD')
            """,
            (changed,),
        ).fetchall()
    }

    queue: deque = deque([(changed, 0)])
    while queue and len(radius) < max_paths:
        current, current_depth = queue.popleft()
        if current != changed and current not in radius:
            radius.append(current)
        if len(radius) >= max_paths:
            break
        if current_depth >= depth:
            continue

        neighbors = _neighbors_for(
            conn,
            current=current,
            changed=changed,
            module_id=module_id,
            exported=exported if current == changed else set(),
            candidates=candidates,
            visited=visited,
        )

        seen_local: set[str] = set()
        for npath in neighbors:
            npath = _norm_path(npath)
            if npath in visited or npath in seen_local:
                continue
            if should_skip_review_path(npath):
                continue
            seen_local.add(npath)
            visited.add(npath)
            queue.append((npath, current_depth + 1))

    order: list[str] = [changed]
    order.extend(sorted(set(radius), key=lambda p: (_norm_path(p).count("/"), _norm_path(p))))
    return order[:max_paths]


def _neighbors_for(
    conn,
    *,
    current: str,
    changed: str,
    module_id: str,
    exported: set[str],
    candidates: Sequence[tuple[str, str | None]] | None,
    visited: set[str],
) -> list[str]:
    """Symbol-consumer + import-scan neighbors of ``current`` (blast radius)."""
    neighbors: list[str] = []
    if exported:
        # symbol_index consumers of the changed file's exports.
        placeholders = ",".join("?" * len(exported))
        nbr_rows = conn.execute(
            f"""
            SELECT DISTINCT s.file_path
            FROM file_symbols s
            WHERE s.file_path <> ?
              AND s.kind IN ('FUNCTION', 'CLASS', 'METHOD')
              AND s.name IN ({placeholders})
            """,
            (current, *tuple(exported)),
        ).fetchall()
        neighbors.extend(row[0] for row in nbr_rows)

    if candidates is None:
        rows = conn.execute("""
            SELECT file_path, content FROM project_files
            WHERE is_binary = 0
            """).fetchall()
        rows = _sort_candidates(rows, current)[:BLAST_MAX_IMPORT_SCAN]
    else:
        rows = _sort_candidates(
            [(c[0], c[1]) for c in candidates if c[1] is not None],
            current,
        )[:BLAST_MAX_IMPORT_SCAN]

    module_target = module_id if current == changed else _module_id(current)
    for path, content in rows:
        if path in visited:
            continue
        if content and _refs_target(content, module_target):
            neighbors.append(path)
        if len(neighbors) >= BLAST_MAX_PATHS:
            break
    return neighbors


# ---------------------------------------------------------------------------
# §16.2 coverage ledger: sweep target selection + operator diagnostics.
# ---------------------------------------------------------------------------

SWEEP_CHUNK_MIN = 80
SWEEP_CHUNK_MAX = 120


def _covered_intervals(conn, *, agent_name: str, file_path: str, line_count: int) -> list[tuple[int, int]]:
    """Validated coverage intervals for one agent/file (hash still current)."""
    if not line_count or line_count <= 0:
        return []
    rows = conn.execute(
        """
        SELECT rc.lines_lo, rc.lines_hi, rc.content_hash, pf.content_hash
        FROM review_coverage rc
        LEFT JOIN project_files pf ON pf.file_path = rc.file_path
        WHERE rc.agent_name = ? AND rc.file_path = ?
        ORDER BY rc.lines_lo, rc.lines_hi
        """,
        (agent_name, file_path),
    ).fetchall()
    intervals: list[tuple[int, int]] = []
    for lo, hi, rc_hash, pf_hash in rows:
        if rc_hash is not None and pf_hash is not None and rc_hash != pf_hash:
            # A later write invalidates this chunk only; do not count it.
            continue
        if lo == 0 and hi == 0:
            intervals.append((1, line_count))
            continue
        intervals.append((max(1, int(lo)), min(line_count, int(hi))))
    return intervals


def _coverage_ratio(intervals: list[tuple[int, int]], line_count: int) -> float:
    if not line_count:
        return 0.0
    covered = sum(max(0, hi - lo + 1) for lo, hi in intervals)
    return min(1.0, covered / line_count)


def _first_uncovered_chunk(
    intervals: list[tuple[int, int]],
    line_count: int,
    *,
    chunk_min: int = SWEEP_CHUNK_MIN,
    chunk_max: int = SWEEP_CHUNK_MAX,
) -> tuple[int, int] | None:
    """First uncovered [start, end] window (1-based inclusive), or None."""
    if not line_count:
        return None
    merged: list[tuple[int, int]] = []
    for lo, hi in sorted(intervals):
        if not merged or lo > merged[-1][1] + 1:
            merged.append((lo, hi))
        else:
            merged[-1] = (merged[-1][0], max(merged[-1][1], hi))

    cursor = 1
    for lo, hi in merged:
        if cursor < lo:
            size = min(chunk_max, lo - cursor)
            return (cursor, cursor + size - 1)
        cursor = max(cursor, hi + 1)
    if cursor <= line_count:
        size = min(chunk_max, line_count - cursor + 1)
        return (cursor, cursor + size - 1)
    return None


def _sweep_candidates(conn, *, agent_name: str, limit: int = 40) -> list[tuple[str, int, int]]:
    """Ordered candidate files (path, line_count, priority) for the sweep.

    Priority 1: hash-miss (reviewed before, content changed since).
    Priority 2: never reviewed.
    Priority 3: high fan-in (symbol-heavy) files not fully covered.
    """
    rows = conn.execute(
        """
        SELECT
            fs.file_path,
            COALESCE(fs.line_count, 0) AS line_count,
            art.content_hash_reviewed,
            pf.content_hash,
            art.last_reviewed_at,
            COALESCE((
                SELECT COUNT(*) FROM file_symbols sy
                WHERE sy.file_path = fs.file_path
            ), 0) AS symbol_count
        FROM file_summaries fs
        JOIN project_files pf ON pf.file_path = fs.file_path AND pf.is_binary = 0
        LEFT JOIN agent_review_tracking art
            ON art.file_path = fs.file_path AND art.agent_name = ?
        WHERE COALESCE(fs.line_count, 0) > 0
        """,
        (agent_name,),
    ).fetchall()

    hash_miss: list[tuple[str, int, int]] = []
    never_seen: list[tuple[str, int, int]] = []
    fan_in: list[tuple[str, int, int]] = []

    for path, line_count, reviewed_hash, current_hash, reviewed_at, symbol_count in rows:
        if reviewed_hash and current_hash and reviewed_hash != current_hash:
            hash_miss.append((path, line_count, symbol_count))
        elif not reviewed_at and not reviewed_hash:
            never_seen.append((path, line_count, symbol_count))
        else:
            fan_in.append((path, line_count, symbol_count))

    def order(candidates: list[tuple[str, int, int]]) -> list[tuple[str, int, int]]:
        return sorted(candidates, key=lambda item: -item[2])[:limit]

    return order(hash_miss) + order(never_seen) + order(fan_in)


def coverage_sweep_next(
    conn,
    *,
    agent_name: str,
    chunk_min: int = SWEEP_CHUNK_MIN,
    chunk_max: int = SWEEP_CHUNK_MAX,
) -> SliceSpec | None:
    """Next uncovered chunk for one agent (hash-miss → never-seen → fan-in).

    Returns a ``SliceSpec`` (path + 1-based inclusive window) or None when the
    whole project is covered for that agent.
    """
    if not agent_name:
        return None
    for path, line_count, _symbol_count in _sweep_candidates(conn, agent_name=agent_name):
        intervals = _covered_intervals(conn, agent_name=agent_name, file_path=path, line_count=line_count)
        chunk = _first_uncovered_chunk(intervals, line_count, chunk_min=chunk_min, chunk_max=chunk_max)
        if chunk is None:
            continue
        start, end = chunk
        return SliceSpec(file_path=path, start=start, end=end, why="coverage sweep")
    return None


def coverage_diagnostic(conn) -> dict:
    """Per-agent '% lines covered' plus oldest uncovered path. Operator-facing."""
    agents = [
        row[0]
        for row in conn.execute("""
            SELECT DISTINCT agent_name FROM agent_review_tracking
            UNION
            SELECT DISTINCT agent_name FROM review_coverage
            ORDER BY agent_name
            """).fetchall()
    ]
    source_rows = conn.execute("""
        SELECT fs.file_path, COALESCE(fs.line_count, 0)
        FROM file_summaries fs
        JOIN project_files pf ON pf.file_path = fs.file_path AND pf.is_binary = 0
        WHERE COALESCE(fs.line_count, 0) > 0
        """).fetchall()
    total_lines = sum(line_count for _, line_count in source_rows)

    per_agent: dict[str, dict] = {}
    for agent in agents:
        covered_lines = 0
        fully_covered_files = 0
        oldest_uncovered: tuple[str, int] | None = None
        for path, line_count in source_rows:
            intervals = _covered_intervals(conn, agent_name=agent, file_path=path, line_count=line_count)
            ratio = _coverage_ratio(intervals, line_count)
            covered_lines += int(ratio * line_count)
            if ratio >= 0.999:
                fully_covered_files += 1
            elif oldest_uncovered is None:
                oldest_uncovered = (path, line_count)
        pct = (covered_lines / total_lines) * 100 if total_lines else 0.0
        per_agent[agent] = {
            "covered_lines": covered_lines,
            "total_lines": total_lines,
            "percent": round(pct, 2),
            "fully_covered_files": fully_covered_files,
            "total_source_files": len(source_rows),
            "oldest_uncovered_path": oldest_uncovered[0] if oldest_uncovered else None,
            "oldest_uncovered_lines": oldest_uncovered[1] if oldest_uncovered else 0,
        }

    return {
        "total_source_lines": total_lines,
        "total_source_files": len(source_rows),
        "per_agent": per_agent,
        "has_receipts": any(a["covered_lines"] for a in per_agent.values()),
    }


def format_coverage_diagnostic(stats: dict) -> str:
    """Render the operator diagnostic as text."""
    lines = ["Coverage ledger (review_coverage + agent_review_tracking)", ""]
    if not stats["total_source_lines"]:
        return "Coverage ledger: no indexed source lines yet."
    if not stats.get("has_receipts"):
        lines.append("No receipts yet — run background reviewers to accumulate coverage.")
        return "\n".join(lines)
    for agent, info in sorted(stats["per_agent"].items()):
        lines.append(
            f"- {agent}: {info['percent']:.2f}% "
            f"({info['covered_lines']:,}/{info['total_lines']:,} lines, "
            f"{info['fully_covered_files']}/{info['total_source_files']} files fully covered)"
        )
        if info["oldest_uncovered_path"]:
            lines.append(f"    oldest uncovered: {info['oldest_uncovered_path']} ({info['oldest_uncovered_lines']} lines)")
        else:
            lines.append("    oldest uncovered: (none)")
    return "\n".join(lines)
