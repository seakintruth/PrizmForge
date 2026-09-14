"""§14.2 manifest-v2 tests: parse/reject, contract_hash folding, repo fixtures."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

_TERMINAL_TASK = {
    "task_id": "c1_fix_flag",
    "kind": "terminal",
    "seed": "Make the CLI's --retries flag default to 3 in cli.py",
    "repo": {"url": "https://example.invalid/app.git", "commit": "deadbeef"},
    "setup": ["git status"],
    "verifier": {"command": "python app/check.py", "timeout": 30},
    "contract": [{"file_path": "app/cli.py", "fragment": "retries=3", "mode": "contains"}],
}


def _parse(raw):
    from harness.benchmark.tasks import parse_bench_task

    return parse_bench_task(raw)


class TestTaskManifestV2:
    def test_parse_all_v2_fields(self):
        task = _parse(_TERMINAL_TASK)
        assert task.is_terminal
        assert task.kind == "terminal"
        assert task.repo is not None
        assert task.repo.url == "https://example.invalid/app.git"
        assert task.repo.commit == "deadbeef"
        assert task.setup == ("git status",)
        assert task.verifier is not None
        assert task.verifier.command == "python app/check.py"
        assert task.verifier.timeout == 30
        assert len(task.contract) == 1

    def test_v1_task_parses_with_defaults(self):
        task = _parse({"task_id": "t_a", "seed": "s", "fixture": {"f.py": "x"}, "contract": []})
        assert task.kind == "content"
        assert not task.is_terminal
        assert task.repo is None
        assert task.verifier is None
        assert task.setup == ()

    def test_contract_hash_folds_new_fields(self):
        base = {k: v for k, v in _TERMINAL_TASK.items()}
        h1 = _parse(base).contract_hash
        verifier_changed = {**base, "verifier": {"command": "python app/other.py", "timeout": 30}}
        assert _parse(verifier_changed).contract_hash != h1
        commit_changed = {**base, "repo": {"url": base["repo"]["url"], "commit": "abcdef00"}}
        assert _parse(commit_changed).contract_hash != h1
        seed_changed = {**base, "seed": "Renumber --retries to default 3 in cli.py"}
        assert _parse(seed_changed).contract_hash != h1

    def test_contract_hash_stable_per_input(self):
        base = {k: v for k, v in _TERMINAL_TASK.items()}
        h1 = _parse(base).contract_hash
        assert _parse(base).contract_hash == h1

    def test_rendered_contract_folds_verifier_but_not_seed(self):
        task = _parse(_TERMINAL_TASK)
        rc1 = task.rendered_contract()
        assert "cli.py" in rc1
        assert "check.py" in rc1
        same_seed = _parse({**_TERMINAL_TASK, "seed": "a different seed"})
        assert same_seed.rendered_contract() == rc1

    def test_reject_verifier_without_command(self):
        with pytest.raises(ValueError, match=r"verifier\.command"):
            _parse({**_TERMINAL_TASK, "verifier": {"timeout": 30}})

    def test_reject_repo_without_commit(self):
        with pytest.raises(ValueError, match=r"repo\.commit"):
            _parse({**_TERMINAL_TASK, "repo": {"url": "https://example.invalid/app.git"}})

    def test_reject_unsupported_kind(self):
        with pytest.raises(ValueError, match="unsupported task kind"):
            _parse({**_TERMINAL_TASK, "kind": "docker"})

    def test_reject_terminal_without_grading_surface(self):
        with pytest.raises(ValueError, match="no grading surface"):
            _parse({**_TERMINAL_TASK, "verifier": None, "contract": []})

    def test_manifest_version_2_accepted(self, tmp_path):
        from harness.benchmark.tasks import SUPPORTED_SCHEMA_VERSION, load_task_manifest

        p = tmp_path / "tasks.json"
        p.write_text(
            json.dumps({"schema_version": 2, "default_k": 1, "tasks": [_TERMINAL_TASK]}),
            encoding="utf-8",
        )
        manifest = load_task_manifest(p)
        assert manifest["schema_version"] == SUPPORTED_SCHEMA_VERSION == 2
        assert manifest["tasks"][0].is_terminal


class TestTerminalTaskSet:
    """§14.5 — the crafted terminal set parses, is deterministic, and names targets."""

    def _load(self):
        from harness.benchmark.tasks import load_task_manifest

        p = Path(__file__).resolve().parent.parent.parent / "harness" / "benchmark" / "tasks_terminal.json"
        return load_task_manifest(p)

    def test_five_terminal_tasks_parse(self):
        manifest = self._load()
        assert manifest["schema_version"] == 2
        tasks = manifest["tasks"]
        assert len(tasks) == 5
        assert all(t.is_terminal for t in tasks)
        assert all(t.verifier is not None for t in tasks)

    def test_terminal_tasks_name_a_target_and_fold_fields(self):
        tasks = self._load()["tasks"]
        for t in tasks:
            assert any(s in t.seed for s in (".py", ".sh")), t.task_id
            assert any("." in key for key in t.fixture), t.task_id
            assert t.contract_hash
        hashes = [t.contract_hash for t in tasks]
        assert len(set(hashes)) == len(hashes)

    def test_verifier_variants_deterministic(self):
        tasks = {t.task_id: t for t in self._load()["tasks"]}
        assert tasks["c3_make_script_executable"].verifier.command.startswith("bash -c")
        assert tasks["c4_fix_failing_test"].setup == ()
        c5 = tasks["c5_color_flag"]
        assert "app/check.py" in c5.fixture
        assert "python3 -m app.check" in c5.verifier.command


def _make_local_repo(root: Path) -> tuple[str, str, str]:
    """Build a tiny git repo with three commits (first content, then content change, then a big file)."""
    (root / "app").mkdir(parents=True)
    (root / "app" / "cli.py").write_text("RETRIES = 1\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.email", "bench@test"], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.name", "bench"], check=True)
    subprocess.run(["git", "-C", str(root), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(root), "commit", "-qm", "one"], check=True)
    first = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], check=True, capture_output=True, text=True).stdout.strip()
    (root / "app" / "cli.py").write_text("RETRIES = 3\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(root), "commit", "-qam", "two"], check=True)
    second = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], check=True, capture_output=True, text=True).stdout.strip()
    (root / "app" / "big.bin").write_bytes(b"\x00" * 600_000)
    subprocess.run(["git", "-C", str(root), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(root), "commit", "-qm", "big"], check=True)
    return first, second, str(root)


@pytest.mark.usefixtures("temp_db")
class TestRepoFixture:
    def test_clone_materializes_pinned_commit(self, tmp_path):
        from harness.benchmark.repo_fixture import clone_repo, ingest_tree_to_governed

        origins = tmp_path / "origins"
        first, second, url = _make_local_repo(origins / "app")
        checkout = clone_repo(url, first, tmp_path / "dest", cache_dir=tmp_path / "cache")
        assert (checkout / "app" / "cli.py").read_text(encoding="utf-8") == "RETRIES = 1\n"
        ingested = ingest_tree_to_governed(checkout)
        assert "app/cli.py" in ingested

        second_checkout = clone_repo(url, second, tmp_path / "dest2", cache_dir=tmp_path / "cache")
        assert (second_checkout / "app" / "cli.py").read_text(encoding="utf-8") == "RETRIES = 3\n"

    def test_clone_shares_mirror_cache(self, tmp_path):
        from harness.benchmark.repo_fixture import clone_repo

        origins = tmp_path / "origins"
        first, _, url = _make_local_repo(origins / "app")
        cache = tmp_path / "cache"
        checkout = clone_repo(url, first, tmp_path / "dest", cache_dir=cache)
        assert (cache / (url.rsplit("/", 1)[-1] + ".git")).exists() is False
        assert any(cache.glob("*.git"))
        assert (checkout / "app" / "cli.py").read_text(encoding="utf-8") == "RETRIES = 1\n"

    def test_ingest_skips_oversize(self, tmp_path):
        import harness.benchmark.repo_fixture as rf

        root = tmp_path / "tree"
        root.mkdir()
        (root / "app").mkdir(parents=True)
        (root / "app" / "other.py").write_text("y = 2\n", encoding="utf-8")
        (root / "small.py").write_text("x = 1\n", encoding="utf-8")
        (root / "big.bin").write_bytes(b"\x00" * 600_000)
        ingested = rf.ingest_tree_to_governed(root, max_file_bytes=512_000, max_files=100)
        assert "app/other.py" in ingested
        assert "small.py" in ingested
        assert "big.bin" not in ingested

    def test_ingest_respects_file_count_cap(self, tmp_path):
        import harness.benchmark.repo_fixture as rf

        root = tmp_path / "tree"
        root.mkdir()
        for i in range(6):
            (root / f"f{i}.py").write_text(f"x = {i}\n", encoding="utf-8")
        ingested = rf.ingest_tree_to_governed(root, max_files=2)
        assert len(ingested) == 2

    def test_fixture_paths_for_task_uses_manifest_for_content(self):
        from harness.benchmark.repo_fixture import fixture_paths_for_task

        task = _parse({"task_id": "t", "seed": "s", "fixture": {"a.py": "x"}, "contract": []})
        assert fixture_paths_for_task(task, Path("/none")) == ["a.py"]

    def test_fixture_paths_for_task_ingests_repo(self, tmp_path):
        from harness.benchmark.repo_fixture import clone_repo, fixture_paths_for_task

        origins = tmp_path / "origins"
        first, _, _url = _make_local_repo(origins / "app")
        url = str(origins / "app")
        checkout = clone_repo(url, first, tmp_path / "dest", cache_dir=tmp_path / "cache")
        task = _parse({**_TERMINAL_TASK, "repo": {"url": url, "commit": first}})
        paths = fixture_paths_for_task(task, checkout)
        assert "app/cli.py" in paths
