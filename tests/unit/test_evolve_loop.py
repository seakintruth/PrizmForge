"""Tests for the §12.5 harness Evolve loop.

Covers: harness mount loader (system_prompt/*.md runtime assembly + legacy
fallback), target guardrails (harness/-only, read-only paths, non-deletable
seed prompts), the RC-style edit budget, the governed-pipeline round-trip
(propose → mandatory reviewer gate → materialize → manifest), rollback
selection execution, the iter-<t> git commit tag, and the session orchestrator.
"""

from __future__ import annotations

from workflow.reviewer_gate import ReviewerVerdict

# ---------------------------------------------------------------------------
# Budget + guardrails (pure, no DB)
# ---------------------------------------------------------------------------


class TestEvolveBudget:
    def test_gates_on_max_edits(self):
        from harness.evolve_loop import EvolveBudget

        b = EvolveBudget(max_edits=1, max_tokens=10_000)
        assert b.exhausted is False
        b.spend(tokens=5)
        assert b.exhausted is True

    def test_gates_on_max_tokens(self):
        from harness.evolve_loop import EvolveBudget

        b = EvolveBudget(max_edits=50, max_tokens=100)
        b.spend(tokens=99)
        assert b.exhausted is False
        b.spend(tokens=1)
        assert b.exhausted is True

    def test_zero_dollar_limits_are_unlimited(self):
        from harness.evolve_loop import EvolveBudget

        b = EvolveBudget(max_edits=0, max_tokens=0)
        b.spend(tokens=999)
        assert b.exhausted is False


class TestEvolveGuardrails:
    def test_harness_target_is_editable(self):
        from harness.evolve_loop import validate_evolve_target

        ok, _ = validate_evolve_target("harness/benchmark/driver.py")
        assert ok is True

    def test_non_harness_target_is_blocked(self):
        from harness.evolve_loop import validate_evolve_target

        for bad in ("src/app.py", "workflow/task_runner.py", "core/config.py", "main.py"):
            ok, reason = validate_evolve_target(bad)
            assert ok is False
            assert "harness/" in reason

    def test_escaping_path_is_blocked(self):
        from harness.evolve_loop import validate_evolve_target

        for bad in ("../../etc/passwd", "/etc/passwd", "harness/../core/db.py", ""):
            ok, _ = validate_evolve_target(bad)
            assert ok is False

    def test_readonly_paths_are_blocked(self):
        from harness.evolve_loop import is_evolve_readonly_path, validate_evolve_target

        assert is_evolve_readonly_path("runs/1/output.txt")
        assert is_evolve_readonly_path("config.json")
        assert validate_evolve_target("runs/1/output.txt")[0] is False
        assert validate_evolve_target("config.json")[0] is False

    def test_seed_prompt_editable_but_not_deletable(self):
        from harness.evolve_loop import validate_evolve_target

        seed = "harness/system_prompt/evolve.md"
        assert validate_evolve_target(seed)[0] is True
        assert validate_evolve_target(seed, deleting=True)[0] is False
        assert validate_evolve_target("harness/system_prompt/developer.md", deleting=True)[0] is False


# ---------------------------------------------------------------------------
# Harness mount loader (bullet 2)
# ---------------------------------------------------------------------------


class TestMountLoader:
    def test_assembles_seed_with_placeholders_and_include(self, tmp_path):
        from harness.evolve_loop import resolve_harness_prompt

        (tmp_path / "tools.md").write_text("TOOL-LIST", encoding="utf-8")
        (tmp_path / "evolve.md").write_text(
            "ROLE {{evidence}} {{budget}}\n{{include:tools.md}}",
            encoding="utf-8",
        )
        text = resolve_harness_prompt(
            "evolve",
            context={"evidence": "E1", "budget": "B1", "iteration": 7},
            prompt_root=tmp_path,
        )
        assert text == "ROLE E1 B1\nTOOL-LIST"

    def test_missing_include_inlines_empty(self, tmp_path):
        from harness.evolve_loop import resolve_harness_prompt

        (tmp_path / "evolve.md").write_text("{{include:absent.md}}", encoding="utf-8")
        assert resolve_harness_prompt("evolve", prompt_root=tmp_path).strip() == ""

    def test_falls_back_to_legacy_prompts_when_no_seed(self, tmp_path, monkeypatch):
        import harness.evolve_loop as evo

        monkeypatch.setattr(evo, "get_agent_prompts", lambda: {"evolve": {"system_prompt": "LEGACY {{evidence}}"}})
        text = evo.resolve_harness_prompt("evolve", context={"evidence": "X"}, prompt_root=tmp_path)
        assert text.strip() == "LEGACY X"


# ---------------------------------------------------------------------------
# Evidence + prompt assembly
# ---------------------------------------------------------------------------


class TestEvidenceContext:
    def test_digests_results(self):
        from harness.evolve_loop import build_evidence_context

        results = {
            "tasks": [
                {"task_id": "task-a", "passed": 1, "trials": [{"tokens": 50}]},
                {"task_id": "task-b", "passed": 0, "trials": [{"tokens": 30}]},
            ]
        }
        text = build_evidence_context(3, results)
        assert "1 passed, 1 failed" in text
        assert "task-a" in text and "task-b" in text

    def test_builds_evolve_prompt_from_seed(self, tmp_path):
        from harness.evolve_loop import build_evolve_prompt

        (tmp_path / "evolve.md").write_text(
            "PROMPT {{evidence}} | {{budget}} | iter={{iteration}}",
            encoding="utf-8",
        )
        prompt = build_evolve_prompt(4, results={"tasks": []}, prompt_root=tmp_path)
        assert "iter=4" in prompt
        assert "unlimited" in prompt


# ---------------------------------------------------------------------------
# Governed pipeline round trip (real DB)
# ---------------------------------------------------------------------------


def _approve_reviewer(**kwargs):
    return ReviewerVerdict(decision="APPROVE", reason="scoped harness edit")


def _reject_reviewer(**kwargs):
    return ReviewerVerdict(decision="REJECT", reason="too broad")


def _harness_edit_payload(target, *, fixes=("task-a",), regressions=("task-b",)):
    return {
        "developer_output": {
            "target_file_path": target,
            "summary": "evolve harness",
            "rationale": "make failing task-a green",
            "operations": [{"type": "create_file", "target_file_path": target, "initial_content": ["pass"]}],
        },
        "target_file_path": target,
        "rationale": "make failing task-a green",
        "predicted_fixes": list(fixes),
        "predicted_regressions": list(regressions),
        "inferred_root_cause": "driver ignores fails",
    }


class TestRunEvolveIteration:
    def test_applies_and_records_manifest(self, temp_db, monkeypatch):
        import harness.evolve_loop as evo

        target = "harness/benchmark/new_feature.py"
        monkeypatch.setattr(evo, "_latest_commit_sha", lambda: "cafe1234")

        results = {
            "tasks": [
                {"task_id": "task-a", "passed": 1, "trials": [{"tokens": 40}]},
                {"task_id": "task-b", "passed": 0, "trials": []},
            ]
        }

        res = evo.run_evolve_iteration(
            1,
            results=results,
            propose=lambda **kw: _harness_edit_payload(target),
            reviewer=_approve_reviewer,
        )

        assert res.status == "applied"
        assert res.proposal_id
        assert res.target_file_path == target
        assert res.reviewer_decision == "APPROVE"
        assert res.commit == "cafe1234"
        assert res.manifest_recorded is True
        assert res.budget.edits_used == 1

        from harness.evolve import read_change_manifest

        manifest = read_change_manifest(1)
        assert manifest["edits"][0]["edit_id"] == res.proposal_id
        assert manifest["edits"][0]["predicted_fixes"] == ["task-a"]
        assert manifest["edits"][0]["target_file"] == target

    def test_harness_ownership_enforced_on_proposal(self, temp_db, monkeypatch):
        import harness.evolve_loop as evo

        created = {"called": False}

        def fake_create(*args, **kwargs):
            created["called"] = True
            return {"status": "success", "proposal_id": "p-1"}

        monkeypatch.setattr(evo, "create_proposal_from_developer_output", fake_create)

        res = evo.run_evolve_iteration(
            1,
            results={"tasks": []},
            propose=lambda **kw: _harness_edit_payload("src/leak.py"),
            reviewer=_approve_reviewer,
        )
        assert res.status == "blocked"
        assert "harness/" in res.message
        assert created["called"] is False

    def test_rejected_proposal_goes_fail_closed(self, temp_db, monkeypatch):
        import harness.evolve_loop as evo

        res = evo.run_evolve_iteration(
            1,
            results={"tasks": []},
            propose=lambda **kw: _harness_edit_payload("harness/benchmark/x.py"),
            reviewer=_reject_reviewer,
        )
        assert res.status == "rejected"
        assert res.reviewer_decision == "REJECT"
        assert res.proposal_id

    def test_budget_exhausted_skips_work(self, temp_db, monkeypatch):
        import harness.evolve_loop as evo

        budget = evo.EvolveBudget(max_edits=1)
        budget.spend()
        called = {"n": 0}

        def propose(**kw):
            called["n"] += 1
            return _harness_edit_payload("harness/benchmark/x.py")

        res = evo.run_evolve_iteration(1, results={"tasks": []}, propose=propose, reviewer=_approve_reviewer, budget=budget)
        assert res.status == "budget_exhausted"
        assert called["n"] == 0

    def test_no_target_from_proposer(self, temp_db):
        import harness.evolve_loop as evo

        res = evo.run_evolve_iteration(1, results={"tasks": []}, propose=lambda **kw: None, reviewer=_approve_reviewer)
        assert res.status == "no_target"


# ---------------------------------------------------------------------------
# Rollback execution (§5.3)
# ---------------------------------------------------------------------------


class TestRunEvolveReverts:
    def test_executes_candidates_with_injected_executor(self, temp_db, monkeypatch):
        import harness.evolve_loop as evo

        monkeypatch.setattr(
            evo,
            "revert_candidates",
            lambda *a, **k: [{"edit_id": "iter-1-01", "target_file": "harness/x.py", "commit": "deadbeef", "action": "git revert deadbeef"}],
        )
        events = []

        def executor(candidate):
            events.append(candidate)
            return False

        out = evo.run_evolve_reverts(1, 2, executor=executor, workspace=str(evo.__file__))
        assert out[0]["edit_id"] == "iter-1-01"
        assert out[0]["action"] == "git revert deadbeef"
        assert out[0]["ok"] is False
        assert events

    def test_non_git_action_unwired_is_ok_false(self, temp_db, monkeypatch, tmp_path):
        import harness.evolve_loop as evo

        monkeypatch.setattr(
            evo,
            "revert_candidates",
            lambda *a, **k: [{"edit_id": "iter-1-01", "target_file": "harness/x.py", "commit": None, "action": "undo_proposal"}],
        )
        out = evo.run_evolve_reverts(1, 2, workspace=str(tmp_path))
        assert out[0]["action"] == "undo_proposal"
        assert out[0]["ok"] is False
        assert out[0]["detail"] == "undo_proposal executor not wired"


# ---------------------------------------------------------------------------
# Session orchestrator (bench t → evolve → bench t+1 → reverts)
# ---------------------------------------------------------------------------


class TestRunEvolveSession:
    def test_respects_enabled_gate(self, temp_db):
        from harness.evolve_loop import run_evolve_session

        out = run_evolve_session([1], enabled_check=True)
        assert out["status"] == "disabled"

    def test_full_session_records_verdict_and_picks_reverts(self, temp_db, monkeypatch):
        import harness.evolve_loop as evo

        def fake_runner(iteration):
            if iteration == 1:
                return {
                    "tasks": [
                        {"task_id": "task-a", "passed": 0, "trials": []},
                        {"task_id": "task-b", "passed": 1, "trials": []},
                    ]
                }
            return {
                "tasks": [
                    {"task_id": "task-a", "passed": 0, "trials": []},
                    {"task_id": "task-b", "passed": 0, "trials": []},
                ]
            }

        out = evo.run_evolve_session(
            [1, 2],
            run_benchmark_fn=fake_runner,
            propose=lambda **kw: _harness_edit_payload(f"harness/benchmark/session_edit_{kw['iteration']}.py"),
            reviewer=_approve_reviewer,
            budget=evo.EvolveBudget(max_edits=10, max_tokens=1_000_000),
            enabled_check=False,
        )

        assert out["status"] == "ok"
        statuses = [s["status"] for s in out["steps"]]
        assert statuses == ["applied", "applied"]

        # task-a never flipped and flagged regression task-b landed → §5.3 fires.
        assert len(out["reverts"]) == 1
        rev = out["reverts"][0]
        assert "task-b" in rev["flagged_regressions_landed"]
        assert rev["fixes_confirmed"] == 0

        from harness.evolve import read_change_manifest

        manifest = read_change_manifest(1)
        assert len(manifest["edits"]) == 1
        assert manifest["edits"][0]["predicted_regressions"] == ["task-b"]


# ---------------------------------------------------------------------------
# iter-<t> git commit tag on harness edit commits
# ---------------------------------------------------------------------------


class TestIterCommitTag:
    def test_harness_edit_commit_carries_tag(self, temp_db, monkeypatch, tmp_path):
        from file_editing.db import get_db_connection
        from workflow.proposal_builder import create_proposal_from_developer_output

        target = "harness/benchmark/tagme.py"
        prop = create_proposal_from_developer_output(
            {
                "target_file_path": target,
                "summary": "tagged harness edit",
                "rationale": "exercise iter tag",
                "operations": [{"type": "create_file", "target_file_path": target, "initial_content": ["pass"]}],
            },
            1,
            target,
        )
        assert prop["status"] == "success", prop
        with get_db_connection() as conn:
            conn.execute("UPDATE edit_proposals SET status = 'approved' WHERE proposal_id = ?", (prop["proposal_id"],))

        project_dir = tmp_path / "proj"
        project_dir.mkdir()
        cfg = {
            "project_directory": str(project_dir),
            "background_agents_enabled": False,
            "git": True,
            "git_auto_commit": True,
            "git_commit_tag": "iter-3",
            "token_budget": {"max_tokens_per_4h": 1_000_000},
        }
        from core import config as core_config

        for site in (
            "core.config.get_config",
            "core.db.get_config",
            "core.file_operations.get_config",
            "core.index_context.get_config",
            "agents.base.get_config",
            "utils.git_operations.get_config",
        ):
            try:
                monkeypatch.setattr(site, lambda c=cfg: c)
            except (AttributeError, ImportError):
                pass
        monkeypatch.setattr(core_config, "get_config", lambda: cfg)

        captured: list[str] = []

        def fake_git_commit(file_path, message, **kwargs):
            captured.append(message)
            return {
                "ok": True,
                "attempted": True,
                "code": 0,
                "stage": "commit",
                "stdout": "",
                "stderr": "",
                "file_path": file_path,
                "commit_hash": "tagged1",
            }

        monkeypatch.setattr("file_editing.writer.git_commit", fake_git_commit)

        from file_editing.writer import materialize_proposal

        mat = materialize_proposal(prop["proposal_id"])
        assert mat["status"] == "success"
        assert captured, "git_commit must be invoked for the harness edit"

        message = captured[0]
        assert message.startswith("[PrizmForge] Agent edit via proposal")
        assert message.endswith("[iter-3]")
