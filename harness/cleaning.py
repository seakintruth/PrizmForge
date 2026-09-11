"""Cleaning pass for the §12.3 trajectory corpus (HARNESS_EVOLUTION_DESIGN §4.2).

Turns the raw ``shell_trajectories`` JSON into a distilled
``cleaned/<task_id>.jsonl`` — one frame per JSON line — by dropping base64
payload blobs and collapsing identical consecutive tool-result frames. Raw
trajectory files are never modified; they stay the untouched source of truth
(``runs/<iter>/raw`` in the §4.1 layout).

Pure and stdlib-only so the cleaner is reusable outside the LLM loop (and unit
testable without a model or a database).
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

#: data-URI base64 blobs, e.g. ``data:text/plain;base64,aGVsbG8=``.
_DATA_URI_RE = re.compile(r"data:[^;]{0,64};base64,[A-Za-z0-9+/]{8,}={0,2}")
#: long standalone base64 runs (>= 120 chars) that are encoded payloads, not
#: source text (real paths contain ``/``/``.``/``-`` and will not match).
_BASE64_RUN_RE = re.compile(r"[A-Za-z0-9+/]{120,}={0,2}")
_BASE64_DROPPED = "[base64 payload dropped]"

_TURN_BOUNDARY_RE = re.compile(r"-turn\d+-")


def drop_base64(content: str) -> str:
    """Replace base64-encoded payload blobs with an elision marker."""
    if not content:
        return content
    out = _DATA_URI_RE.sub(_BASE64_DROPPED, content)
    return _BASE64_RUN_RE.sub(_BASE64_DROPPED, out)


def turn_number_from_source(source: str) -> int:
    """Parse the ``-turn<N>-`` marker from a trajectory filename (0 if absent)."""
    matches = list(_TURN_BOUNDARY_RE.finditer(str(source)))
    if not matches:
        return 0
    token = matches[-1].group(0)
    digits = "".join(ch for ch in token if ch.isdigit())
    return int(digits) if digits else 0


def task_id_from_source(source: str) -> str:
    """Strip the ``-turn<N>-<stamp>.json`` suffix to the rollout task id."""
    matches = list(_TURN_BOUNDARY_RE.finditer(str(source)))
    if not matches:
        return Path(str(source)).stem
    return str(source)[: matches[-1].start()]


def extract_frames(raw: dict[str, Any], *, source: str = "") -> list[dict[str, Any]]:
    """Turn one raw trajectory dict into an ordered frame list (never raises)."""
    frames: list[dict[str, Any]] = []
    finished_at = raw.get("finished_at") or ""
    turn = turn_number_from_source(source)
    for msg in raw.get("messages") or []:
        if not isinstance(msg, dict):
            continue
        role = str(msg.get("role") or "")
        content = msg.get("content")
        if not isinstance(content, str):
            content = json.dumps(content, default=str) if content is not None else ""
        if not role or not content.strip():
            continue
        frames.append(
            {
                "role": role,
                "content": content,
                "turn": turn,
                "source": str(source),
                "ts": finished_at,
            }
        )
    return frames


def clean_frames(frames: list[dict[str, Any]], *, dedup: bool = True) -> list[dict[str, Any]]:
    """Apply base64-drop and consecutive-frame dedup to ordered frames.

    Frames must already be in chronological order. Identical adjacent frames
    (same role + same content after cleaning) collapse into a single frame with
    ``dup_count`` set to the number of merged copies.
    """
    cleaned: list[dict[str, Any]] = []
    for frame in frames:
        out = dict(frame)
        out.pop("_seq", None)
        out["content"] = drop_base64(out.get("content") or "")
        if not out["content"].strip():
            continue
        cleaned.append(out)
    if not dedup:
        return cleaned
    merged: list[dict[str, Any]] = []
    for frame in cleaned:
        if merged and merged[-1]["role"] == frame["role"] and merged[-1]["content"] == frame["content"]:
            merged[-1]["dup_count"] = int(merged[-1].get("dup_count", 1)) + 1
            continue
        frame = dict(frame)
        frame.setdefault("dup_count", 1)
        merged.append(frame)
    return merged


def clean_task_into(
    task_id: str,
    raw_files: list[str | Path],
    out_dir: str | Path,
    *,
    dedup: bool = True,
) -> list[dict[str, Any]]:
    """Aggregate + clean every turn file for a task; write ``out_dir/<task_id>.jsonl``.

    Frames from all turns are merged in chronological order (turn number first,
    then finished-at), cleaned, and deduped, then appended one-per-line as JSON.
    Returns the cleaned frame list (empty when nothing could be read).
    """
    frames: list[dict[str, Any]] = []
    for path in sorted(raw_files, key=lambda p: turn_number_from_source(str(p))):
        try:
            raw = json.loads(Path(path).read_text(encoding="utf-8"))
        except Exception:
            continue
        for _seq, frame in enumerate(extract_frames(raw, source=Path(path).name)):
            frame["_seq"] = _seq
            frames.append(frame)
    frames.sort(key=lambda f: (int(f.get("turn") or 0), str(f.get("ts") or ""), int(f.get("_seq") or 0)))
    cleaned = clean_frames(frames, dedup=dedup)

    out_dir_path = Path(out_dir)
    out_dir_path.mkdir(parents=True, exist_ok=True)
    with (out_dir_path / f"{task_id}.jsonl").open("w", encoding="utf-8") as fh:
        for frame in cleaned:
            fh.write(json.dumps(frame, sort_keys=True) + "\n")
    return cleaned


def group_raw_by_task(raw_dir: str | Path) -> dict[str, list[Path]]:
    """Map each trajectory filename's rollout task id to its turn files."""
    grouped: dict[str, list[Path]] = {}
    for path in sorted(Path(raw_dir).glob("*-turn*.json")):
        grouped.setdefault(task_id_from_source(path.name), []).append(path)
    return grouped
