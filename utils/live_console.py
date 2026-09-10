#!/usr/bin/env python3
"""
Live operator console for PrizmForge (Part 1: operator console substrate).

A stdlib-only, read-only TUI that redraws a pane layout on a short poll so an
operator can watch an unattended run without ever writing to agents.db. See
core/operator_view.py for the read model; every connection there is opened in
sqlite mode=ro and closed immediately, so this loop cannot block a worker.

No third-party dependencies (curses is optional and replaced by a plain ANSI
fallback). Terminate with Ctrl-C; --once prints a single frame and exits.

Examples:
  python3 utils/live_console.py                      # live loop, default DB
  python3 utils/live_console.py --db ./other/.PrizmForge/agents.db
  python3 utils/live_console.py --once --task task_001
"""

from __future__ import annotations

import argparse
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core import operator_view as ov  # noqa: E402

try:
    from core.db import get_db_path as _default_db_path
except Exception:  # pragma: no cover

    def _default_db_path() -> str:  # type: ignore
        return str(Path.cwd() / ".PrizmForge" / "agents.db")


# ---------------------------------------------------------------------------
# ANSI helpers
# ---------------------------------------------------------------------------
_RESET = "\x1b[0m"
_BOLD = "\x1b[1m"
_DIM = "\x1b[2m"
_RED = "\x1b[31m"
_GREEN = "\x1b[32m"
_YELLOW = "\x1b[33m"
_CYAN = "\x1b[36m"
_MAGENTA = "\x1b[35m"
_CLEAR = "\x1b[2J\x1b[H"
_CLEAR_LINE = "\x1b[K"


def _status_color(text: str) -> str:
    t = text.lower()
    if t in ("finished", "ok", "healthy", "available"):
        return f"{_GREEN}{text}{_RESET}"
    if any(k in t for k in ("in_flight", "model_call", "unavailable", "error", "failed", "misconfigured", "stalled", "limit")):
        return f"{_RED}{text}{_RESET}"
    if any(k in t for k in ("idle", "probe", "transition")):
        return f"{_YELLOW}{text}{_RESET}"
    return text


def _colored(col: str, text: str) -> str:
    return f"{col}{text}{_RESET}"


def _fmt_s(seconds: int | None) -> str:
    if seconds is None:
        return "-"
    if seconds < 90:
        return f"{seconds}s"
    if seconds < 5400:
        return f"{seconds // 60}m{seconds % 60:02d}s"
    return f"{seconds // 3600}h{(seconds % 3600) // 60:02d}m"


def _fmt_ts(value: str | None) -> str:
    if not value:
        return "-"
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return value[:19]
    return dt.astimezone().strftime("%H:%M:%S")


def _trunc(text: str, width: int) -> str:
    text = " ".join(str(text).split())
    if len(text) <= width:
        return text
    if width <= 3:
        return text[:width]
    return text[: width - 3] + "..."


# ---------------------------------------------------------------------------
# Render
# ---------------------------------------------------------------------------
def _render_header(width: int) -> list[str]:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return [f"{_BOLD}{_CYAN}PrizmForge — operator console{_RESET}  {_DIM}{ts}{_RESET}", ""]


def _render_tasks(tasks: list[dict[str, Any]]) -> list[str]:
    out = [f"{_BOLD}TASKS{_RESET}"]
    if not tasks:
        out.append(f"  {_DIM}(none){_RESET}")
        return out
    for t in tasks[:10]:
        age = _fmt_s(t.get("age_s"))
        status = _status_color(t.get("status") or "?")
        desc = _trunc(t.get("description") or "", 46)
        out.append(f"  {status:<12} {_DIM}age {age:<8}{_RESET} {t.get('id', '')[:14]:<14} {desc}")
    return out


def _render_endpoints(endpoints: list[dict[str, Any]]) -> list[str]:
    out = [_colored(_BOLD, "ENDPOINTS                                                            LATENCY/T0KEN")]
    if not endpoints:
        out.append(f"  {_DIM}(none recorded){_RESET}")
        return out
    for e in endpoints:
        name = e.get("endpoint_name", "?")
        status = _status_color(e.get("status") or "unknown")
        fails = e.get("consecutive_failures") or 0
        unavailable_in = e.get("unavailable_in_s")
        token_state = "-"
        rem = e.get("tokens_remaining_minute")
        tpm = e.get("tokens_per_minute")
        if rem is not None or tpm is not None:
            token_state = f"tpm={tpm or 0} rem={rem or 0}"
        lock = f"  {_RED}latched {_fmt_s(unavailable_in)}{_RESET}" if unavailable_in and unavailable_in > 0 else ""
        out.append(f"  {name:<12} {status:<14} fails={fails} {token_state}{lock}")
    return out


def _render_backlog(backlog: dict[str, Any]) -> list[str]:
    open_ = backlog.get("open", 0)
    high = backlog.get("high", 0)
    stuck = backlog.get("stuck", 0)
    color = _GREEN if open_ == 0 else _YELLOW if high == 0 else _RED
    open_label = _colored(color, f"{open_} open")
    stuck_bit = f"{_RED}stuck={stuck}{_RESET}" if stuck else f"stuck={stuck}"
    return [
        f"{_BOLD}FEEDBACK BACKLOG{_RESET}  {open_label}  high={high}  {stuck_bit}",
        "",
    ]


def _render_spend(spend: dict[str, Any]) -> list[str]:
    win = spend.get("window_tokens", 0)
    total = spend.get("total_tokens", 0)
    win_s = spend.get("window_seconds", 14400)
    return [
        f"{_BOLD}TOKENS{_RESET}  {_CYAN}{win:,}{_RESET} in last {_fmt_s(win_s)}  |  {_DIM}{total:,} total{_RESET}",
        "",
    ]


def _render_developer(snap: dict[str, Any], task_ids: list[str]) -> list[str]:
    out = [f"{_BOLD}LIVE DEVELOPER SESSION{_RESET}"]
    if not task_ids:
        out.append(f"  {_DIM}(no active shell task){_RESET}")
        return out
    for tid in task_ids[:3]:
        live = snap["sessions"].get(tid)
        if not live:
            out.append(f"  {tid[:16]}  {_DIM}(no session data){_RESET}")
            continue
        in_flight = live.get("in_flight", False)
        if in_flight:
            w = _colored(_RED, "⏳ model call in flight")
            w += f"  {_fmt_s(live.get('in_flight_s'))}       "
        else:
            w = _colored(_GREEN, "idle") + f"{'':<8}"
        step = live.get("last_step_number")
        cmd = _trunc(live.get("last_command") or "-", 52)
        cfg = _colored(_GREEN, "ok") if live.get("last_exit_code") == 0 else _colored(_RED, f"exit {live.get('last_exit_code')}")
        ts = _fmt_ts(live.get("last_step_ts"))
        last_evt = live.get("last_event") or "-"
        out.append(f"  {tid[:16]:<16} {w} step={step} {cfg} {_DIM}{ts}{_RESET}")
        out.append(f"  {'':<16} cmd: {cmd}")
        out.append(f"  {'':<16} last event: {_trunc(last_evt, 40)}")
    return out


def _render_health(snap: dict[str, Any]) -> list[str]:
    h = snap["snapshot"].get("health", {})
    out = [f"{_BOLD}MODEL HEALTH (last {h.get('calls', 0)} events){_RESET}"]
    line = f"  ok={_colored(_GREEN, str(h.get('ok', 0)))}  calls={h.get('calls', 0)}  avg_latency={_fmt_s(int(h.get('avg_latency_ms') or 0))}"
    out.append(line)
    recent = snap.get("recent", [])
    if recent:
        last = recent[-1]
        kind = last.get("kind") or "?"
        ok = last.get("ok")
        color = _GREEN if ok else _RED
        out.append(f"  last: {_colored(color, kind)} {_DIM}{_fmt_ts(last.get('ts'))}{_RESET} {_trunc(last.get('model_ref') or '', 40)}")
    return out


def render_frame(snap: dict[str, Any], width: int) -> list[str]:
    lines: list[str] = []
    lines += _render_header(width)
    lines += _render_tasks(snap["snapshot"].get("tasks", []))
    lines.append("")
    lines += _render_developer(snap, snap.get("session_ids", []))
    lines.append("")
    lines += _render_endpoints(snap["snapshot"].get("endpoints", []))
    lines.append("")
    lines += _render_spend(snap["snapshot"].get("spend", {}))
    lines += _render_backlog(snap["snapshot"].get("backlog", {}))
    lines += _render_health(snap)
    return lines


# ---------------------------------------------------------------------------
# Loop
# ---------------------------------------------------------------------------
def _gather(db_path: str, now: datetime | None = None) -> dict[str, Any]:
    snap = ov.snapshot(db_path=db_path)
    session_ids = [t["id"] for t in snap.get("tasks", []) if (t.get("status") or "").lower() in ("in_progress", "running")]
    live: dict[str, Any] = {}
    for tid in session_ids:
        live[tid] = ov.developer_session_live(tid, db_path=db_path)
    recent = ov.health_summary(db_path=db_path, limit=8).get("recent", [])
    return {"snapshot": snap, "session_ids": session_ids, "sessions": live, "recent": recent}


def _draw(db_path: str, width: int, height: int, once: bool) -> None:
    snap = _gather(db_path)
    lines = render_frame(snap, width)
    sys.stdout.write(_CLEAR)
    # Respect terminal height loosely; scroll if needed (never clip mid-block).
    block = "\n".join(lines)
    sys.stdout.write(block)
    sys.stdout.write("\n" + _DIM + "Ctrl-C to quit" + _RESET)
    sys.stdout.flush()
    return


def run(db_path: str, interval: float, once: bool = False) -> int:
    try:
        while True:
            cols, rows = shutil.get_terminal_size(fallback=(120, 40))
            _draw(db_path, cols, rows, once)
            if once:
                print("", file=sys.stderr)
                return 0
            time.sleep(interval)
    except KeyboardInterrupt:
        print("", file=sys.stderr)
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Live operator console for PrizmForge (read-only)")
    parser.add_argument("--db", default=None, help="Path to agents.db (default: project default)")
    parser.add_argument("--interval", type=float, default=2.0, help="Poll interval seconds (default 2.0)")
    parser.add_argument("--once", action="store_true", help="Render one frame and exit (non-TTY safe)")
    args = parser.parse_args()

    db_path = args.db or _default_db_path()
    if not Path(db_path).is_file():
        print(f"❌ Database not found: {db_path}", file=sys.stderr)
        return 2
    return run(db_path, args.interval, once=args.once)


if __name__ == "__main__":
    sys.exit(main())
