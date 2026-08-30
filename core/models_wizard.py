"""Interactive configure session for models + agent prompts.

Input is injected (`ask`) so tests never touch stdin.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from core.models_catalog import (
    TIER_AGENTS,
    assign_agents,
    assign_tier,
    available_refs,
    catalog_refs,
    fetch_catalog,
    list_assignments,
    load_raw_json,
    prompt_text,
    prompts_file_path,
    resolve_choice,
    save_raw_json,
    set_prompt_text,
    validate_assignments,
)

Ask = Callable[[str], str]


def _truthy(raw: str, default: bool) -> bool:
    text = raw.strip().lower()
    if not text:
        return default
    return text in {"y", "yes", "1", "true"}


def print_numbered(refs: list[str], assignments: dict[str, str], default_model: str | None) -> None:
    print("\nAvailable models (registered first, then fetch-cache only):")
    if not refs:
        print("  (none — fetch a catalog or add endpoints.*.models)")
        return
    for i, ref in enumerate(refs, start=1):
        print(f"  {i:>3}  {ref}")
    print("\nCurrent assignments:")
    if not assignments:
        print("  (none)")
    for agent, ref in sorted(assignments.items()):
        print(f"  {agent:<22} {ref}")
    if default_model:
        print(f"  {'default_model':<22} {default_model}")


def _pick(ask: Ask, label: str, numbered: list[str], current: str | None) -> str | None:
    hint = f" [enter keeps {current}]" if current else " [enter skips]"
    raw = ask(f"{label}{hint}: ")
    if not raw.strip():
        return None
    try:
        return resolve_choice(raw, numbered)
    except ValueError as exc:
        print(f"  ⚠️  {exc}")
        return _pick(ask, label, numbered, current)


def run_configure(
    *,
    cfg_path: Path,
    raw: dict[str, Any],
    runtime: dict[str, Any],
    catalog: dict[str, Any],
    ask: Ask,
    fetch: bool | None = None,
    write: bool = True,
    fetcher: Callable | None = None,
) -> dict[str, Any]:
    """Drive the wizard. Returns the mutated raw config."""
    print(f"Config: {cfg_path}")

    if fetch is None:
        fetch = _truthy(ask("Fetch live /v1/models catalogs now? [Y/n] "), True)
    if fetch:
        print("Fetching…")
        catalog = fetch_catalog(runtime, fetcher=fetcher, persist=True)
        for ep, entry in (catalog.get("endpoints") or {}).items():
            status = f"{len(entry.get('models') or [])} models" if entry.get("ok") else f"FAIL {entry.get('error')}"
            print(f"  {ep}: {status}")

    numbered = available_refs(runtime, catalog)
    default_model = raw.get("default_model") if isinstance(raw.get("default_model"), str) else None
    print_numbered(numbered, list_assignments(raw), default_model)

    crit = _pick(ask, "Critical-tier model (orchestrator/developer/reviewer/…)", numbered, default_model)
    cheap = _pick(ask, "Cheap-tier model (jr_reviewer/archivist/…)", numbered, None)

    register = bool(catalog_refs(catalog))
    if crit:
        assign_tier(raw, "critical", crit, register=register, also_default=True, catalog=catalog)
        print(f"  critical + default_model → {crit}")
    if cheap:
        assign_tier(raw, "cheap", cheap, register=register, catalog=catalog)
        print(f"  cheap → {cheap}")

    if _truthy(ask("Override individual agents? [y/N] "), False):
        known = sorted({*TIER_AGENTS["critical"], *TIER_AGENTS["cheap"], *list_assignments(raw)})
        print("  agents: " + ", ".join(known))
        while True:
            name = ask("  agent name (empty to stop): ").strip()
            if not name:
                break
            ref = _pick(ask, f"  model for {name}", numbered, list_assignments(raw).get(name))
            if not ref:
                continue
            assign_agents(raw, [name], ref, register=register, catalog=catalog)
            print(f"    {name} → {ref}")

    prompts_path = prompts_file_path(cfg_path)
    prompts = load_raw_json(prompts_path) if prompts_path.exists() else {}
    if _truthy(ask("Edit an agent system prompt? [y/N] "), False):
        names = sorted(k for k in prompts if not str(k).startswith("_"))
        print("  prompts: " + ", ".join(names) if names else "  (none yet)")
        while True:
            name = ask("  agent to edit (empty to stop): ").strip()
            if not name:
                break
            try:
                current = prompt_text(prompts, name)
            except KeyError:
                current = ""
                print("  (new agent — no existing prompt)")
            preview = current.replace("\n", " ")[:160]
            print(f"  current: {preview}{'\u2026' if len(current) > 160 else ''}")
            path = ask("  replacement file path (empty to paste, '.' to skip): ").strip()
            if path == ".":
                continue
            if path:
                text = Path(path).read_text(encoding="utf-8")
            else:
                print("  Paste prompt. End with a line containing only END")
                lines: list[str] = []
                while True:
                    line = ask("")
                    if line.strip() == "END":
                        break
                    lines.append(line)
                text = "\n".join(lines).strip() + "\n"
            if not text.strip():
                print("  empty — skipped")
                continue
            set_prompt_text(prompts, name, text)
            print(f"    updated {name} ({len(text)} chars)")

    problems = validate_assignments(raw, prompts=prompts if prompts else None)
    if problems:
        print("Validation notes:")
        for p in problems:
            print(f"  - {p}")
    else:
        print("Validation: ok")

    if write and _truthy(ask(f"Write {cfg_path.name} and agent_prompts.json? [Y/n] "), True):
        save_raw_json(cfg_path, raw)
        if prompts:
            save_raw_json(prompts_path, prompts)
        print(f"Wrote {cfg_path}")
        if prompts:
            print(f"Wrote {prompts_path}")
    elif not write:
        print("[dry-run] skipped write")
    else:
        print("Aborted — nothing written")

    return raw
