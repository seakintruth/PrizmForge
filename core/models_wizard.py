"""Interactive configure session for models + agent prompts.

Input is injected (`ask`) so tests never touch stdin.
Every prompt prints the current value first; empty input means no change.
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


def _default_model(raw: dict[str, Any]) -> str | None:
    dm = raw.get("default_model")
    return dm if isinstance(dm, str) and dm else None


def _tier_snapshot(raw: dict[str, Any], tier: str) -> dict[str, str]:
    assignments = list_assignments(raw)
    return {agent: assignments[agent] for agent in TIER_AGENTS[tier] if agent in assignments}


def print_current(title: str, rows: dict[str, str] | None = None, extra: str | None = None) -> None:
    print(f"\n-- {title} --")
    if extra:
        print(f"  {extra}")
    if rows is not None:
        if not rows:
            print("  (none)")
        else:
            for key, value in sorted(rows.items()):
                print(f"  {key:<22} {value}")


def print_numbered(refs: list[str]) -> None:
    print("\nAvailable models (registered first, then fetch-cache only):")
    if not refs:
        print("  (none — fetch a catalog or add endpoints.*.models)")
        return
    for i, ref in enumerate(refs, start=1):
        print(f"  {i:>3}  {ref}")


def print_resulting_config(raw: dict[str, Any], prompts: dict[str, Any] | None = None) -> None:
    """Dump the config the wizard just produced."""
    assignments = list_assignments(raw)
    default_model = _default_model(raw)
    print("\n" + "=" * 60)
    print("Resulting configuration")
    print("=" * 60)
    print(f"default_model          {default_model or '(unset)'}")
    print("\nagent_model_preferences:")
    if not assignments:
        print("  (none)")
    else:
        for agent, ref in sorted(assignments.items()):
            print(f"  {agent:<22} {ref}")

    cheap_refs = set(_tier_snapshot(raw, "cheap").values())
    crit_refs = set(_tier_snapshot(raw, "critical").values())
    if cheap_refs:
        print(f"\ncheap-tier models:    {', '.join(sorted(cheap_refs))}")
    if crit_refs:
        print(f"critical-tier models: {', '.join(sorted(crit_refs))}")

    if prompts:
        names = sorted(k for k in prompts if not str(k).startswith("_"))
        print(f"\nagent prompts ({len(names)}):")
        for name in names:
            try:
                text = prompt_text(prompts, name)
            except KeyError:
                text = ""
            preview = text.replace("\n", " ").strip()[:80]
            print(f"  {name:<22} {len(text):>5} chars  {preview}{'\u2026' if len(text) > 80 else ''}")
    print("=" * 60)


def _pick(ask: Ask, label: str, numbered: list[str], current: str | None) -> str | None:
    print(f"  current: {current or '(unset)'}")
    raw = ask(f"{label} [enter = no change]: ")
    if not raw.strip():
        return None
    try:
        return resolve_choice(raw, numbered)
    except ValueError as exc:
        print(f"  ⚠️  {exc}")
        return _pick(ask, label, numbered, current)


def run_configure(  # noqa: C901
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
    print_current(
        "current configuration",
        list_assignments(raw),
        extra=f"default_model = {_default_model(raw) or '(unset)'}",
    )

    cached_at = catalog.get("fetched_at") if isinstance(catalog, dict) else None
    print_current(
        "model catalog cache",
        extra=f"fetched_at = {cached_at or '(none)'} — enter keeps cache, does not refetch",
    )
    if fetch is None:
        fetch = _truthy(ask("Fetch live /v1/models catalogs? [y/N] "), False)
    if fetch:
        print("Fetching…")
        catalog = fetch_catalog(runtime, fetcher=fetcher, persist=True)
        for ep, entry in (catalog.get("endpoints") or {}).items():
            status = f"{len(entry.get('models') or [])} models" if entry.get("ok") else f"FAIL {entry.get('error')}"
            print(f"  {ep}: {status}")

    numbered = available_refs(runtime, catalog)
    print_numbered(numbered)

    print_current("critical-tier (orchestrator/developer/reviewer/…)", _tier_snapshot(raw, "critical"))
    print_current("default_model", extra=_default_model(raw) or "(unset)")
    crit = _pick(ask, "Critical-tier model", numbered, _default_model(raw))

    print_current("cheap-tier (jr_reviewer/archivist/…)", _tier_snapshot(raw, "cheap"))
    cheap_vals = list(dict.fromkeys(_tier_snapshot(raw, "cheap").values()))
    cheap_current = cheap_vals[0] if len(cheap_vals) == 1 else (", ".join(cheap_vals) if cheap_vals else None)
    cheap = _pick(ask, "Cheap-tier model", numbered, cheap_current)

    register = bool(catalog_refs(catalog))
    dirty = False
    if crit:
        assign_tier(raw, "critical", crit, register=register, also_default=True, catalog=catalog)
        print(f"  set critical + default_model → {crit}")
        dirty = True
    else:
        print("  critical-tier unchanged")
    if cheap:
        assign_tier(raw, "cheap", cheap, register=register, catalog=catalog)
        print(f"  set cheap → {cheap}")
        dirty = True
    else:
        print("  cheap-tier unchanged")

    print_current("per-agent overrides", list_assignments(raw))
    if _truthy(ask("Override individual agents? [y/N] "), False):
        known = sorted({*TIER_AGENTS["critical"], *TIER_AGENTS["cheap"], *list_assignments(raw)})
        print("  agents: " + ", ".join(known))
        while True:
            name = ask("  agent name [enter = no more]: ").strip()
            if not name:
                break
            current_ref = list_assignments(raw).get(name)
            print_current(f"agent {name}", extra=f"current model = {current_ref or '(unset)'}")
            ref = _pick(ask, f"Model for {name}", numbered, current_ref)
            if not ref:
                print("  unchanged")
                continue
            assign_agents(raw, [name], ref, register=register, catalog=catalog)
            print(f"    {name} → {ref}")
            dirty = True

    prompts_path = prompts_file_path(cfg_path)
    prompts = load_raw_json(prompts_path) if prompts_path.exists() else {}
    prompt_names = sorted(k for k in prompts if not str(k).startswith("_"))
    print_current("agent prompts", extra=", ".join(prompt_names) if prompt_names else "(none)")
    if _truthy(ask("Edit an agent system prompt? [y/N] "), False):
        while True:
            name = ask("  agent to edit [enter = no more]: ").strip()
            if not name:
                break
            try:
                current = prompt_text(prompts, name)
            except KeyError:
                current = ""
                print("  (new agent — no existing prompt)")
            preview = current.replace("\n", " ")[:160]
            print_current(
                f"prompt {name}",
                extra=f"{len(current)} chars: {preview}{'\u2026' if len(current) > 160 else ''}",
            )
            path = ask("  replacement file [enter = no change, '.' = paste]: ").strip()
            if not path:
                print("  unchanged")
                continue
            if path == ".":
                print("  Paste prompt. End with a line containing only END")
                lines: list[str] = []
                while True:
                    line = ask("")
                    if line.strip() == "END":
                        break
                    lines.append(line)
                text = "\n".join(lines).strip() + "\n"
            else:
                text = Path(path).read_text(encoding="utf-8")
            if not text.strip():
                print("  empty — unchanged")
                continue
            set_prompt_text(prompts, name, text)
            print(f"    updated {name} ({len(text)} chars)")
            dirty = True

    problems = validate_assignments(raw, prompts=prompts if prompts else None)
    if problems:
        print("Validation notes:")
        for p in problems:
            print(f"  - {p}")
    else:
        print("Validation: ok")

    print_current(
        "write files",
        extra=f"{cfg_path.name} + {prompts_path.name}" + (" (changes pending)" if dirty else " (no changes)"),
    )
    do_write = write and _truthy(ask("Write files? [y/N] "), False)
    if do_write:
        save_raw_json(cfg_path, raw)
        if prompts:
            save_raw_json(prompts_path, prompts)
        print(f"Wrote {cfg_path}")
        if prompts:
            print(f"Wrote {prompts_path}")
    elif not write:
        print("[dry-run] skipped write")
    else:
        print("Not written — working copy only")

    print_resulting_config(raw, prompts if prompts else None)
    return raw
