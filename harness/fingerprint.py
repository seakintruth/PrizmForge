"""Harness-evolution P0 substrate: rollout fingerprints + infra-abort classifier.

Implements §12.1 (docs/TODO.md): every rollout carries a harness fingerprint
(harness git tag, hash of the resolved agent prompts, model) so harness-edit
verdict claims stay verifiable, and infrastructure-aborted rollouts — the model
call died on endpoint infra (``empty_body`` / ``no_alternate_endpoint`` /
``misconfigured`` / rate-limit latches, from ``model_health_events`` and
``endpoint_health``) — are labeled so the Debugger's ``component_hint`` never
blames the harness for a flaky endpoint (Soak18 exact confound).

Design: docs/HARNESS_EVOLUTION_DESIGN.md §3 / §7. Zero new runtime deps
(stdlib + existing sqlite / config / model-health machinery).
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.config import get_agent_prompts, get_config
from core.db_connection import get_db_connection

#: model_health kinds meaning "endpoint infra, not model or harness" (§12.1).
INFRA_ABORT_KINDS = frozenset(
    {
        "empty_body",
        "no_alternate_endpoint",
        "misconfig",
        "rate_limited",
        "key_locked",
        "unauthorized",
        "token_budget",
        "token_exhausted",
    }
)

#: endpoint_health statuses that mean "latched / not available" (§12.1).
ENDPOINT_LATCH_STATUSES = frozenset(
    {
        "rate_limited",
        "token_exhausted",
        "key_locked",
        "server_error",
        "unavailable",
        "misconfigured",
    }
)

#: Rollout statuses that count as failures for pass@1 (design §7).
PASS1_FAILURE_STATUSES = frozenset({"failed", "stalled", "timed_out", "infra_aborted"})

#: Terminal task status -> rollout status (design §7 pass@1 binary).
_TASK_STATUS_TO_ROLLOUT = {
    "completed": "passed",
    "no_change_required": "passed",
    "failed": "failed",
    "stalled": "stalled",
    "timed_out": "timed_out",
    "cancelled": "cancelled",
    "deferred": "cancelled",
}
#: statuses eligible for infra-abort reclassification.
_ABORTABLE_STATUSES = frozenset({"failed", "stalled", "timed_out"})

_ROLLOUT_COLS = (
    "rollout_id",
    "task_id",
    "iteration",
    "harness_tag",
    "prompt_hash",
    "model",
    "status",
    "infra_abort",
    "tokens",
    "created_at",
    "completed_at",
    "contract_hash",
    "verdict",
    "verdict_note",
)


def _harness_repo_root() -> Path | None:
    """Best-effort git top-level for the harness (PrizmForge repo)."""
    here = Path(__file__).resolve().parent.parent
    try:
        out = subprocess.run(
            ["git", "-C", str(here), "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except Exception:
        return None
    path = (out.stdout or "").strip()
    return Path(path) if path else None


def _harness_tag() -> str:
    """``git describe`` tag (or short SHA) for the harness workspace."""
    root = _harness_repo_root()
    if root is None:
        return "unknown"
    for args in (["describe", "--tags", "--always", "--dirty"], ["rev-parse", "--short", "HEAD"]):
        try:
            out = subprocess.run(
                ["git", "-C", str(root), *args],
                capture_output=True,
                text=True,
                timeout=5,
            )
        except Exception:
            continue
        tag = (out.stdout or "").strip()
        if tag:
            return tag
    return "unknown"


def _prompt_hash() -> str:
    """SHA-256 over the resolved agent prompts dict (sorted, stable JSON)."""
    prompts = get_agent_prompts()
    blob = json.dumps(
        prompts,
        sort_keys=True,
        default=str,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def _rollout_model() -> str:
    """Model used for the developer role at rollout time (best effort)."""
    try:
        from core.endpoint_manager import get_endpoint_manager

        choice = get_endpoint_manager().resolve_agent_model("developer")
        if choice.endpoint_name and choice.model_name:
            return f"{choice.endpoint_name}/{choice.model_name}"
    except Exception:
        pass
    return str((get_config() or {}).get("default_model", ""))


def compute_harness_fingerprint() -> dict[str, str]:
    """Return ``{harness_tag, prompt_hash, model}`` for the current harness."""
    return {
        "harness_tag": _harness_tag(),
        "prompt_hash": _prompt_hash(),
        "model": _rollout_model(),
    }


def create_rollout(
    task_id: str,
    *,
    iteration: int = 0,
    fingerprint: dict[str, str] | None = None,
) -> int | None:
    """Record a new rollout row; returns its id (None on failure, never raises)."""
    fp = fingerprint or compute_harness_fingerprint()
    try:
        with get_db_connection() as conn:
            cur = conn.execute(
                """
                INSERT INTO rollouts
                    (task_id, iteration, harness_tag, prompt_hash, model, status, created_at)
                VALUES (?, ?, ?, ?, ?, 'in_progress', ?)
                """,
                (
                    str(task_id)[:200],
                    int(iteration),
                    fp.get("harness_tag") or "unknown",
                    fp.get("prompt_hash") or "",
                    (fp.get("model") or "")[:200],
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            return int(cur.lastrowid)
    except Exception as e:
        print(f"   ⚠️  Could not record rollout for {task_id}: {e}")
        return None


def latest_rollout(task_id: str) -> dict[str, Any] | None:
    """Return the most recent rollout row for a task (or None)."""
    try:
        with get_db_connection() as conn:
            conn.row_factory = None
            row = conn.execute(
                "SELECT * FROM rollouts WHERE task_id = ? ORDER BY rollout_id DESC LIMIT 1",
                (str(task_id)[:200],),
            ).fetchone()
            if not row:
                return None
            return dict(zip(_ROLLOUT_COLS, row, strict=False))
    except Exception:
        return None


def classify_infra_abort(task_id: str, start_ts: str | None, end_ts: str | None) -> tuple[bool, str]:
    """Label a rollout that died on endpoint infra rather than harness/task work.

    True when (a) the last model-health event inside the window is a failure of
    an infra kind, or (b) an endpoint was still latched (``unavailable_until``
    beyond the window) at rollout end. Never raises — degrades to False.
    """
    if not start_ts or not end_ts:
        return False, "no_health_window"
    try:
        with get_db_connection() as conn:
            events = conn.execute(
                """
                SELECT ok, kind, endpoint FROM model_health_events
                WHERE datetime(ts) >= datetime(?) AND datetime(ts) <= datetime(?)
                ORDER BY ts ASC
                """,
                (start_ts, end_ts),
            ).fetchall()

            latched = conn.execute(
                """
                SELECT endpoint_name, status, unavailable_until FROM endpoint_health
                """,
            ).fetchall()
    except Exception:
        return False, "no_health_data"

    if events:
        last_ok, last_kind, _endpoint = events[-1]
        if last_ok == 0 and str(last_kind or "").lower() in INFRA_ABORT_KINDS:
            return True, f"infra_tail:{last_kind}"

    for _name, status, unavailable_until in latched:
        if str(status or "").lower() not in ENDPOINT_LATCH_STATUSES or not unavailable_until:
            continue
        try:
            latch_until = datetime.fromisoformat(unavailable_until)
        except (ValueError, TypeError):
            continue
        try:
            end_dt = datetime.fromisoformat(end_ts)
        except (ValueError, TypeError):
            continue
        if latch_until > end_dt and (latch_until - end_dt).total_seconds() > 60:
            return True, f"endpoint_latched:{_name}:{status}"

    return False, "no_infra_abort"


def finalize_rollout(
    task_id: str,
    task_status: str,
    *,
    tokens: int | None = None,
) -> dict[str, Any] | None:
    """Close the latest in_progress rollout for a task; never raises.

    Maps the terminal task status to a rollout status, classifies
    infra aborts, and back-fills token usage from ``token_log`` when not given.
    Returns the updated row on success, else None.
    """
    existing = latest_rollout(task_id)
    if existing is None:
        return None
    if existing.get("completed_at"):
        return existing

    # The canonical terminal status lives on the task row (the runner may have
    # completed via complete_task/mark_task_status without _finalize_task).
    db_status = None
    try:
        with get_db_connection() as conn:
            row = conn.execute("SELECT status FROM tasks WHERE id = ?", (str(task_id)[:200],)).fetchone()
            if row:
                db_status = str(row[0])
    except Exception:
        pass

    terminal = db_status or task_status
    rollout_status = _TASK_STATUS_TO_ROLLOUT.get(terminal, "failed")
    completed_at = datetime.now(timezone.utc).isoformat()
    infra_abort = 0
    infra_reason = ""
    if rollout_status in _ABORTABLE_STATUSES:
        is_abort, infra_reason = classify_infra_abort(task_id, existing.get("created_at"), completed_at)
        if is_abort:
            infra_abort = 1
            rollout_status = "infra_aborted"
    if tokens is None:
        tokens = _tokens_in_window(existing.get("created_at"), completed_at)

    try:
        with get_db_connection() as conn:
            conn.execute(
                """
                UPDATE rollouts
                SET status = ?, infra_abort = ?, tokens = ?, completed_at = ?
                WHERE rollout_id = ?
                """,
                (rollout_status, infra_abort, tokens, completed_at, existing["rollout_id"]),
            )
    except Exception as e:
        print(f"   ⚠️  Could not finalize rollout for {task_id}: {e}")
        return None

    if infra_abort:
        print(f"   🧯 Rollout {task_id} infra-aborted ({infra_reason})")
    return latest_rollout(task_id)


def _tokens_in_window(start_ts: str | None, end_ts: str | None) -> int | None:
    """Sum token_log usage inside [start, end]; None on any failure."""
    if not start_ts or not end_ts:
        return None
    try:
        with get_db_connection() as conn:
            row = conn.execute(
                "SELECT COALESCE(SUM(tokens_used), 0) FROM token_log WHERE datetime(timestamp) >= datetime(?) AND datetime(timestamp) <= datetime(?)",
                (start_ts, end_ts),
            ).fetchone()
        return int(row[0])
    except Exception:
        return None


def failure_mode_mix(iteration: int | None = None) -> dict[str, Any]:
    """Aggregate rollout statuses by infra vs non-infra (design §12.1/§7)."""
    mix: dict[str, Any] = {
        "rollouts": 0,
        "passed": 0,
        "failed": 0,
        "stalled": 0,
        "timed_out": 0,
        "cancelled": 0,
        "infra_aborted": 0,
        "pass@1": 0.0,
        "non_infra_failures": 0,
    }
    try:
        sql_iter = ""
        params: list[Any] = []
        if iteration is not None:
            sql_iter = "WHERE iteration = ?"
            params = [int(iteration)]
        with get_db_connection() as conn:
            rows = conn.execute(
                f"SELECT status, COUNT(*) AS n, COALESCE(SUM(infra_abort), 0) AS infra FROM rollouts {sql_iter} GROUP BY status",  # noqa: S608 - static SQL
                params,
            ).fetchall()
    except Exception:
        return mix

    total = 0
    passed = 0
    for status, n, infra in rows:
        mix["rollouts"] += n
        total += n
        is_infra = bool(infra) or status == "infra_aborted"
        if status == "passed":
            passed += n
            mix["passed"] += n
        elif is_infra:
            mix["infra_aborted"] += n
        elif status == "stalled":
            mix["stalled"] += n
        elif status == "timed_out":
            mix["timed_out"] += n
        elif status == "cancelled":
            mix["cancelled"] += n
        else:
            mix["failed"] += n
        if status in PASS1_FAILURE_STATUSES and not is_infra:
            mix["non_infra_failures"] += n
    if total:
        mix["pass@1"] = round(passed / total, 4)
    return mix
