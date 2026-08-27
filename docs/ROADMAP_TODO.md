# PrizmForge Roadmap / TODO

Single source of truth for open work items. Detailed design lives in the
linked documents; this file tracks status. Tick checkboxes as items land and
note the PR/commit.

**Last updated:** 2026-08-22

---

## 1. Gitignore-aware file filtering (from `todo-db_init` proposal)

**Design:** `docs/todo-db_init_should_ignore_gitignore_patterns.md` (full spec: new `core/gitignore.py`, integration patches, verification steps)

Goal: file indexing, truncation candidates, and consolidation must respect `.gitignore`
so caches (`__pycache__`, `.pytest_cache`, …), reports, and secrets (`api_key.json`)
are never treated as edit/truncation targets.

Related: `UNATTENDED_CLOSED_LOOP_PLAN.md` §7 Workstream E (repo policy awareness).

- [x] Add `core/gitignore.py` (`load_gitignore_spec`, `should_ignore_by_gitignore`, gitwildmatch via `pathspec`)
- [x] Integrate into `core/file_operations.py` — `should_ignore_file()` applies hardcoded ignores + `.gitignore`; `sync_file_to_database()` short-circuits on ignored paths
- [x] Integrate into `core/symbol_index.py` — `rebuild_project_symbols()` skips gitignored files
- [x] Integrate into `utils/consolidate.py` — `_is_ignored_path()` also consults `.gitignore`
- [x] Add `pathspec>=0.12.1` to `requirements.txt` and `requirements-dev.txt`
- [x] Tests: `tests/unit/test_gitignore.py` (19 passed)

## 2. Test isolation: remove live `config.json` dependency

Fixed (2026-08-22): extended `tests/conftest.py` so `get_config` is patched at
every import site (core/*, agents/*, workflow, cli.commands, interactive),
added a safe `token_budget` default, and reset `interactive._shutdown_requested`
per test. Full suite now passes with no `config.json` present: **602 passed**.

- [x] Audit which tests call `core.config.get_config()` / `load_config()` against disk
- [x] Patch all local-binding sites in `_GET_CONFIG_PATCH_TARGETS`
- [x] Full `pytest tests` green with no `config.json` present

## 3. Unattended closed-loop hardening

**Plan:** `docs/UNATTENDED_CLOSED_LOOP_PLAN.md` (workstreams A–F with acceptance criteria; none shipped yet)

Delivery order per §9:

- [ ] Phase 0 — Stabilize copy under test (operator)
- [ ] Phase 1 — Workstream A: git/pre-commit closed loop (capture hook outcome → events/errors/feedback; highest ROI)
- [ ] Phase 2 — Workstream D: edit payload / developer-phase validation alignment
- [ ] Phase 3 — Workstream B: backlog backpressure & consolidation tiers
- [ ] Phase 4 — Workstream C: post-materialize targeted re-verify + feedback auto-address
- [ ] Phase 5 — Workstream E + F: repo policy awareness & observability polish (gitignore item above is part of E)
- [ ] Workstream F: API/network error-storm resilience

## 3. Documentation upkeep (continuous)

- [x] docs/CONFIGURATION.md / docs/architecture.md updated for `endpoint/model` reference resolution (2026-08-22)
- [ ] Keep UNATTENDED_CLOSED_LOOP_PLAN status header current as phases land
