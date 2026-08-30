#!/usr/bin/env python3
"""List, fetch, assign, and validate agent models; show/set agent prompts.

Usage (from the repo root, next to config.json):

  python utils/models_cli.py                      # interactive configure
  python utils/models_cli.py configure
  python utils/models_cli.py models list
  python utils/models_cli.py models fetch
  python utils/models_cli.py models assign developer openrouter/stealth/ox-alpha
  python utils/models_cli.py models assign-tier cheap openrouter/foo --register
  python utils/models_cli.py models validate
  python utils/models_cli.py agents prompt show reviewer
  python utils/models_cli.py agents prompt set reviewer --file notes.md
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.config import load_config  # noqa: E402
from core.models_catalog import (  # noqa: E402
    TIER_AGENTS,
    assign_agents,
    assign_tier,
    catalog_path,
    config_file_path,
    fetch_catalog,
    list_assignments,
    list_registered,
    load_catalog,
    load_raw_json,
    prompt_text,
    prompts_file_path,
    save_raw_json,
    set_prompt_text,
    validate_assignments,
)
from core.models_wizard import run_configure  # noqa: E402


def _load_runtime(config_override: str | None) -> tuple[Path, dict]:
    cfg_path = config_file_path(config_override)
    runtime = load_config(str(cfg_path))
    return cfg_path, runtime


def cmd_configure(args: argparse.Namespace) -> int:
    cfg_path, runtime = _load_runtime(args.config)
    raw = load_raw_json(cfg_path)
    catalog = load_catalog(runtime)
    try:
        run_configure(
            cfg_path=cfg_path,
            raw=raw,
            runtime=runtime,
            catalog=catalog,
            ask=input,
            fetch=None if not getattr(args, "no_fetch", False) else False,
            write=not getattr(args, "dry_run", False),
        )
    except (KeyboardInterrupt, EOFError):
        print("\nAborted.")
        return 130
    return 0


def cmd_models_list(args: argparse.Namespace) -> int:
    _cfg_path, runtime = _load_runtime(args.config)
    refs = list_registered(runtime)
    print(f"Registered models ({len(refs)}):")
    for ref in refs:
        print(f"  {ref}")
    prefs = list_assignments(runtime)
    print(f"\nAgent assignments ({len(prefs)}):")
    if not prefs:
        print("  (none)")
    for agent, ref in sorted(prefs.items()):
        mark = "" if ref in refs or any(ref == r or r.endswith("/" + ref) for r in refs) else "  ⚠️ unregistered"
        print(f"  {agent:<22} {ref}{mark}")
    dm = runtime.get("default_model")
    if dm:
        print(f"\ndefault_model: {dm}")
    return 0


def cmd_models_fetch(args: argparse.Namespace) -> int:
    _cfg_path, runtime = _load_runtime(args.config)
    catalog = fetch_catalog(runtime, persist=not args.no_save)
    print(f"Fetched at {catalog.get('fetched_at')}")
    for ep, entry in (catalog.get("endpoints") or {}).items():
        if entry.get("ok"):
            print(f"  {ep}: {len(entry.get('models') or [])} models  ({entry.get('url')})")
            shown = list(entry.get("models") or [])
            limit = None if args.all else 40
            for mid in shown[: limit or len(shown)]:
                print(f"    {ep}/{mid}")
            extra = len(shown) - (limit or len(shown))
            if extra > 0:
                print(f"    ... +{extra} more (pass --all)")
        else:
            print(f"  {ep}: FAIL {entry.get('error')}  ({entry.get('url')})")
    if not args.no_save:
        print(f"\nCached → {catalog_path(runtime)}")
    ok_all = all(e.get("ok") for e in (catalog.get("endpoints") or {}).values()) or not catalog.get("endpoints")
    return 0 if ok_all else 1


def cmd_models_assign(args: argparse.Namespace) -> int:
    cfg_path, runtime = _load_runtime(args.config)
    raw = load_raw_json(cfg_path)
    catalog = load_catalog(runtime)
    agents = [a.strip() for a in args.agent.split(",") if a.strip()]
    try:
        assign_agents(
            raw,
            agents,
            args.reference,
            register=args.register,
            also_default=args.also_default,
            catalog=catalog,
        )
    except ValueError as exc:
        print(f"❌ {exc}", file=sys.stderr)
        return 2
    if not args.dry_run:
        save_raw_json(cfg_path, raw)
        print(f"Wrote {cfg_path}")
    else:
        print("[dry-run] would write:")
    for agent in agents:
        print(f"  {agent} → {raw.get('agent_model_preferences', {}).get(agent)}")
    if args.also_default:
        print(f"  default_model → {raw.get('default_model')}")
    return 0


def cmd_models_assign_tier(args: argparse.Namespace) -> int:
    cfg_path, runtime = _load_runtime(args.config)
    raw = load_raw_json(cfg_path)
    catalog = load_catalog(runtime)
    try:
        assign_tier(
            raw,
            args.tier,
            args.reference,
            register=args.register,
            also_default=args.also_default,
            catalog=catalog,
        )
    except ValueError as exc:
        print(f"❌ {exc}", file=sys.stderr)
        return 2
    agents = TIER_AGENTS[args.tier.strip().lower()]
    if not args.dry_run:
        save_raw_json(cfg_path, raw)
        print(f"Wrote {cfg_path}")
    else:
        print("[dry-run] would write:")
    for agent in agents:
        print(f"  {agent} → {raw.get('agent_model_preferences', {}).get(agent)}")
    return 0


def cmd_models_validate(args: argparse.Namespace) -> int:
    cfg_path, runtime = _load_runtime(args.config)
    prompts_path = prompts_file_path(cfg_path)
    prompts = load_raw_json(prompts_path) if prompts_path.exists() else {}
    problems = validate_assignments(runtime, prompts=prompts)
    if not problems:
        print(f"✅ models + prompts ok ({cfg_path})")
        return 0
    print(f"❌ {len(problems)} problem(s):")
    for p in problems:
        print(f"  - {p}")
    return 1


def cmd_prompt_show(args: argparse.Namespace) -> int:
    cfg_path, _runtime = _load_runtime(args.config)
    prompts = load_raw_json(prompts_file_path(cfg_path))
    try:
        text = prompt_text(prompts, args.agent)
    except KeyError as exc:
        print(f"❌ {exc}", file=sys.stderr)
        return 2
    print(f"# {args.agent}")
    print(text)
    return 0


def cmd_prompt_set(args: argparse.Namespace) -> int:
    cfg_path, _runtime = _load_runtime(args.config)
    prompts_path = prompts_file_path(cfg_path)
    prompts = load_raw_json(prompts_path)
    if args.file:
        text = Path(args.file).read_text(encoding="utf-8")
    elif args.text is not None:
        text = args.text
    else:
        print("❌ pass --file PATH or --text STRING", file=sys.stderr)
        return 2
    set_prompt_text(prompts, args.agent, text)
    if args.dry_run:
        print(f"[dry-run] would write {prompts_path} ({len(text)} chars)")
        return 0
    save_raw_json(prompts_path, prompts)
    print(f"Wrote {prompts_path} agent={args.agent} ({len(text)} chars)")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Assign models and edit agent prompts without hand-editing JSON.")
    p.add_argument("--config", help="Path to config.json (default: discover)")
    sub = p.add_subparsers(dest="cmd")

    cfg = sub.add_parser("configure", help="Interactive prompts for models + agent instructions")
    cfg.add_argument("--no-fetch", action="store_true", help="Skip the live /v1/models prompt and use cache only")
    cfg.add_argument("--dry-run", action="store_true", help="Walk the prompts but do not write files")

    models = sub.add_parser("models", help="Fetch / list / assign / validate models")
    msub = models.add_subparsers(dest="models_cmd", required=True)

    msub.add_parser("list", help="Registered models and current agent assignments")

    pf = msub.add_parser("fetch", help="GET /v1/models for each endpoint")
    pf.add_argument("--no-save", action="store_true", help="Do not write the catalog cache")
    pf.add_argument("--all", action="store_true", help="Print every model id")

    pa = msub.add_parser("assign", help="Set agent_model_preferences.<agent>")
    pa.add_argument("agent", help="Agent name, or comma-separated list")
    pa.add_argument("reference", help="endpoint/model (or a registered bare id)")
    pa.add_argument("--register", action="store_true", help="Add a stub under endpoints.*.models if only in fetch cache")
    pa.add_argument("--also-default", action="store_true", help="Also set default_model")
    pa.add_argument("--dry-run", action="store_true")

    pt = msub.add_parser("assign-tier", help="Assign a model to the cheap or critical agent set")
    pt.add_argument("tier", choices=sorted(TIER_AGENTS))
    pt.add_argument("reference")
    pt.add_argument("--register", action="store_true")
    pt.add_argument("--also-default", action="store_true")
    pt.add_argument("--dry-run", action="store_true")

    msub.add_parser("validate", help="Every preference + downgrade resolves; prompts exist")

    agents = sub.add_parser("agents", help="Show or replace one agent's system prompt")
    asub = agents.add_subparsers(dest="agents_cmd", required=True)
    prompt = asub.add_parser("prompt")
    psub = prompt.add_subparsers(dest="prompt_cmd", required=True)
    ps = psub.add_parser("show")
    ps.add_argument("agent")
    pst = psub.add_parser("set")
    pst.add_argument("agent")
    pst.add_argument("--file", help="Read replacement text from a file")
    pst.add_argument("--text", help="Replacement text on the command line")
    pst.add_argument("--dry-run", action="store_true")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.cmd:
        return cmd_configure(args)
    if args.cmd == "configure":
        return cmd_configure(args)
    if args.cmd == "models":
        dispatch = {
            "list": cmd_models_list,
            "fetch": cmd_models_fetch,
            "assign": cmd_models_assign,
            "assign-tier": cmd_models_assign_tier,
            "validate": cmd_models_validate,
        }
        return dispatch[args.models_cmd](args)
    if args.cmd == "agents" and args.agents_cmd == "prompt":
        if args.prompt_cmd == "show":
            return cmd_prompt_show(args)
        return cmd_prompt_set(args)
    return 2


if __name__ == "__main__":
    sys.exit(main())
