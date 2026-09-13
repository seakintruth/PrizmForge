"""Harness evolution decision artifacts (§12.4, docs/HARNESS_EVOLUTION_DESIGN.md).

Change manifests persist what the Evolve Agent intended for an iteration
(per-edit `predicted_fixes` / `predicted_regressions`); task outcomes record
what actually happened per task. `edit_verdicts` implements the §5.2 verdict
SQL (prediction ∩ observed deltas), and `revert_candidates` applies the §5.3
rollback rule so failing edits become falsifiable contracts, reverted before
the next distillation.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.db_connection import get_db_connection

DEFAULT_MANIFEST_DIR = "harness/manifest"


def _manifest_dir(base: str | Path | None) -> Path:
    base = Path(base) if base else Path(DEFAULT_MANIFEST_DIR)
    base.mkdir(parents=True, exist_ok=True)
    return base


def record_change_manifest(iteration: int, payload: dict[str, Any]) -> bool:
    """Upsert the iteration's change-manifest JSON (schema §5.1)."""
    with get_db_connection() as conn:
        conn.execute(
            """
            INSERT INTO harness_change_manifest (iteration, payload) VALUES (?, ?)
            ON CONFLICT(iteration) DO UPDATE SET payload = excluded.payload
            """,
            (int(iteration), json.dumps(payload, sort_keys=True)),
        )
    return True


def read_change_manifest(iteration: int) -> dict[str, Any] | None:
    """Return the stored manifest payload for an iteration, or None."""
    with get_db_connection() as conn:
        row = conn.execute(
            "SELECT payload FROM harness_change_manifest WHERE iteration = ?",
            (int(iteration),),
        ).fetchone()
    if not row:
        return None
    return json.loads(row[0])


def write_manifest_file(iteration: int, payload: dict[str, Any], base: str | Path | None = None) -> Path:
    """Write `harness/manifest/iteration-<t>.json` (plus record it in the DB)."""
    record_change_manifest(iteration, payload)
    path = _manifest_dir(base) / f"iteration-{iteration}.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def record_task_outcomes(iteration: int, outcomes: list[dict[str, Any]]) -> int:
    """Upsert per-task outcomes: `{task_id, passed, tokens, result?}`.

    `passed` is 1 when at least one trial passed (the §5.2 `fixed this round`
    definition); `tokens` sums the trial tokens for cost attribution.
    """
    rows = 0
    with get_db_connection() as conn:
        for o in outcomes:
            conn.execute(
                """
                INSERT INTO task_outcomes (iteration, task_id, passed, tokens, result)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(iteration, task_id) DO UPDATE SET
                    passed = excluded.passed,
                    tokens = excluded.tokens,
                    result = excluded.result
                """,
                (
                    int(iteration),
                    o["task_id"],
                    int(o.get("passed", 0)),
                    int(o.get("tokens", 0)),
                    o.get("result"),
                ),
            )
            rows += 1
    return rows


def outcomes_from_results(results: dict[str, Any]) -> list[dict[str, Any]]:
    """Translate a `run_benchmark` results dict into task_outcomes rows.

    `passed` is 1 when at least one trial passed; `tokens` sums trial tokens.
    """
    outcomes: list[dict[str, Any]] = []
    for task in results.get("tasks", []):
        trials = task.get("trials", [])
        passed = 1 if task.get("passed", 0) > 0 else 0
        tokens = sum((t.get("tokens") or 0) for t in trials)
        result = "passed" if passed else ("infra_aborted" if task.get("infra_aborted", 0) else "failed")
        outcomes.append(
            {
                "task_id": task.get("task_id"),
                "passed": passed,
                "tokens": tokens,
                "result": result,
            }
        )
    return outcomes


def record_iteration_outcomes(iteration: int, results: dict[str, Any]) -> int:
    """Record an iteration's task outcomes straight from its benchmark results."""
    return record_task_outcomes(iteration, outcomes_from_results(results))


def load_task_outcomes(iteration: int) -> list[dict[str, Any]]:
    """All recorded task outcomes for an iteration."""
    with get_db_connection() as conn:
        rows = conn.execute(
            "SELECT iteration, task_id, passed, tokens, result FROM task_outcomes WHERE iteration = ?",
            (int(iteration),),
        ).fetchall()
    return [
        {
            "iteration": int(r[0]),
            "task_id": str(r[1]),
            "passed": int(r[2]),
            "tokens": int(r[3]),
            "result": r[4],
        }
        for r in rows
    ]


def edit_verdicts(prior_iter: int, cur_iter: int) -> list[dict[str, Any]]:
    """§5.2 verdict: intersect each prior edit's predicted_fixes with the tasks
    that flipped from failing → passing this round.

    Returns per-edit `{edit_id, fixes_confirmed, fixes_predicted, precision}`
    (precision 0.0 when nothing was predicted).
    """
    if cur_iter <= prior_iter:
        return []
    manifest = read_change_manifest(prior_iter)
    if not manifest:
        return []
    edits = manifest.get("edits", []) if isinstance(manifest, dict) else []
    if not edits:
        return []

    fixed: set[str] = set()
    with get_db_connection() as conn:
        rows = conn.execute(
            """
            SELECT o_cur.task_id
            FROM task_outcomes o_cur
            JOIN task_outcomes o_prev ON o_cur.task_id = o_prev.task_id
            WHERE o_cur.iteration = ? AND o_prev.iteration = ?
              AND o_cur.passed = 1 AND o_prev.passed = 0
            """,
            (int(cur_iter), int(prior_iter)),
        ).fetchall()
    fixed = {r[0] for r in rows}

    verdicts: list[dict[str, Any]] = []
    for edit in edits:
        predicted = [str(t) for t in (edit.get("predicted_fixes") or [])]
        confirmed = [t for t in predicted if t in fixed]
        total = len(predicted)
        verdicts.append(
            {
                "edit_id": edit.get("edit_id"),
                "fixes_confirmed": len(confirmed),
                "fixes_predicted": total,
                "precision": round(len(confirmed) / total, 4) if total else 0.0,
                "confirmed": confirmed,
            }
        )
    return verdicts


def revert_candidates(prior_iter: int, cur_iter: int) -> list[dict[str, Any]]:
    """§5.3 rollback rule: an edit is reverted when it confirms no predicted fix
    AND a regression it flagged landed (or regressions outnumber confirms).

    Returns the offending edits with the revert action (`git revert <commit>`
    on the harness workspace, or `undo_proposal` for governed edits).
    """
    manifest = read_change_manifest(prior_iter)
    if not manifest:
        return []
    edits = manifest.get("edits", []) if isinstance(manifest, dict) else []
    if not edits:
        return []

    with get_db_connection() as conn:
        flagged_rows = conn.execute(
            """
            SELECT fix_reg.value
            FROM (
                SELECT payload FROM harness_change_manifest WHERE iteration = ?
            ) m,
            json_each(m.payload -> 'edits') AS edit_json,
            json_each(edit_json.value -> 'predicted_regressions') AS fix_reg
            """,
            (int(prior_iter),),
        ).fetchall()
    {r[0] for r in flagged_rows}

    cur_by_task = {o["task_id"]: o for o in load_task_outcomes(cur_iter)}
    prior_by_task = {o["task_id"]: o for o in load_task_outcomes(prior_iter)}

    verdicts = {v["edit_id"]: v for v in edit_verdicts(prior_iter, cur_iter)}
    candidates: list[dict[str, Any]] = []
    for edit in edits:
        edit_id = edit.get("edit_id")
        v = verdicts.get(edit_id, {"fixes_confirmed": 0, "fixes_predicted": 0, "confirmed": []})
        confirms = v["fixes_confirmed"]

        # Regressions that landed this round relative to prior: passing -> failing,
        # excluding rows absent from either iteration.
        regressions = {tid for tid in set(cur_by_task) & set(prior_by_task) if prior_by_task[tid]["passed"] == 1 and cur_by_task[tid]["passed"] == 0}
        predicted_regressions = set(str(t) for t in (edit.get("predicted_regressions") or []))
        flagged_landed = bool(predicted_regressions & regressions)
        regressions_outnumber = len(regressions) > confirms

        if confirms == 0 and (flagged_landed or regressions_outnumber):
            candidates.append(
                {
                    "edit_id": edit_id,
                    "target_file": edit.get("target_file"),
                    "commit": edit.get("commit"),
                    "action": f"git revert {edit.get('commit')}" if edit.get("commit") else "undo_proposal",
                    "fixes_confirmed": confirms,
                    "regressions_landed": sorted(regressions),
                    "flagged_regressions_landed": sorted(predicted_regressions & regressions),
                }
            )
    return candidates
