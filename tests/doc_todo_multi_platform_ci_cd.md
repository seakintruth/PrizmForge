# Multi-Platform CI/CD & Git Mirroring Architecture (GitHub, GitLab, AWS CodeCommit)

This document provides a unified deployment configuration and workflow architecture that enables **PrizmForge** to be committed and continuously tested across **GitHub**, **GitLab**, and **AWS CodeCommit / CodeBuild**.

**Status note (2026-08-16):** GitHub Actions is the active primary CI (`.github/workflows/python-package.yml`). Current gates on `pull_request` to `main`/`develop`:

1. **Auto-Fix & Push** — `ruff check --fix`, `black`, `isort`, `ruff format` (bot commit, often `[skip ci]`)
2. **Code Quality** — `ruff check .` and `ruff format --check .` (must be clean; this is the lint failure surface on PRs)
3. **Normal Test Suite** — `./utils/run_tests.sh --normal -j 4 --timeout 30`

High-priority pure unit suite (local / PR verification):

```bash
pytest tests/unit/test_edit_response_validator.py \
       tests/unit/test_edit_mode_selector.py \
       tests/unit/test_edit_payload.py \
       tests/unit/test_proposal_builder.py \
       tests/unit/test_config.py \
       tests/unit/test_json_parser.py \
       tests/unit/test_response_parser.py \
       tests/unit/test_agent_schemas.py \
       tests/unit/test_endpoint_manager.py \
       tests/unit/test_rate_limiter.py -q
```

Known lint pitfalls when adding tests: Ruff `RUF043` requires escaping metacharacters in `pytest.raises(..., match=...)` (e.g. `r"file_editing\.method"`). Complex multi-branch validators may need `# noqa: C901` when the branching is the product surface (same pattern as `writer.materialize_proposal`).

---

## 1. Executive Summary & Multi-Remote Strategy

To support multi-cloud deployments, DoD/GovCloud air-gapped environments, and enterprise migration paths, PrizmForge can be configured for **Multi-Remote Synchronization** and **Cross-Platform CI/CD Parity**.

### Core Architecture Goals

1. **Identical Quality Gates**: Enforce the same linting (`ruff`), and test runner (`utils/run_tests.sh --normal`) across platforms. Optional: mypy, coverage fail-under — not hard gates on GitHub today.

2. **Dual Sync Mechanisms**:

   * **Local Developer Multi-Push**: A single `git push` command automatically pushes commits to GitHub, GitLab, and AWS CodeCommit simultaneously.

   * **Automated CI Mirroring**: Any commit pushed to the primary repository triggers an automated pipeline job that mirrors branches and tags to the secondary remotes.

```
                     ┌──────────────────────────────────────┐
                     │     Developer Local Workstation      │
                     └──────────────────┬───────────────────┘
                                        │ git push (multi-remote)
            ┌───────────────────────────┼───────────────────────────┐
            │                           │                           │
            ▼                           ▼                           ▼
  ┌──────────────────┐        ┌──────────────────┐        ┌──────────────────┐
  │  GitHub Repo     │        │  GitLab Repo     │        │ AWS CodeCommit   │
  ├──────────────────┤        ├──────────────────┤        ├──────────────────┤
  │ GitHub Actions   │        │ GitLab CI/CD     │        │ AWS CodePipeline │
  │ (.github/...)    │        │ (.gitlab-ci.yml) │        │ (buildspec.yml)  │
  └──────────────────┘        └──────────────────┘        └──────────────────┘
```

---

## 2. Key Advantages of Multi-Remote Pushing & Mirroring

### 2.1 Disaster Recovery & High Availability

* **Zero Single Point of Failure**: Outages on a single platform do not block team velocity.
* **Instant Failover**: Shift remote tracking targets without data loss.

### 2.2 Compliance & Multi-Cloud / Air-Gapped Alignment

* Bridge commercial forges with GovCloud CodeCommit while keeping developer UX familiar.
* Centralize Inspector / Security Hub scans in AWS without abandoning GitHub PR review.

### 2.3 Mitigation of Vendor Lock-In

* Keep build scripts and quality gates portable across providers.

### 2.4 Synchronized Developer Workflows

* `git push all` or CI mirror jobs keep branches/tags identical.

### 2.5 Best-of-Breed Tooling Integration

* GitHub PR review + Dependabot; GitLab security dashboards; AWS IAM / VPC isolation.

### 2.6 Multi-Environment Pipeline Validation

* Catch pathing and toolchain assumptions across Ubuntu, Docker, and Amazon Linux runners.

---

## 3. Multi-Remote Git Configuration

```bash
git remote add github git@github.com:your-org/PrizmForge.git
git remote add gitlab git@gitlab.com:your-org/PrizmForge.git
git remote add codecommit codecommit::us-east-1://PrizmForge

git remote add all git@github.com:your-org/PrizmForge.git
git remote set-url --add --push all git@github.com:your-org/PrizmForge.git
git remote set-url --add --push all git@gitlab.com:your-org/PrizmForge.git
git remote set-url --add --push all codecommit::us-east-1://PrizmForge

git push all main
```

---

## 4. Platform 1: GitHub Actions (active)

Source of truth: `.github/workflows/python-package.yml`

* Triggers: `pull_request` → `main`/`develop`; `push` → `main`, `develop`, `feature/**`, `fix/**`, `ci/**`
* Note: `test/**` branches rely on **pull_request** events (not the push branch filter)
* Jobs: auto-fix-and-push → code-quality (`ruff check`, `ruff format --check`) → test-normal (`run_tests.sh --normal`)

Keep local pre-push aligned:

```bash
ruff check .
ruff format --check .
./utils/run_tests.sh --normal -j 4 --timeout 30
```

---

## 5. Platform 2: GitLab CI/CD (parity template)

File: `.gitlab-ci.yml` (repo may carry a lighter variant). Recommended parity stages:

1. `ruff check .` + `ruff format --check .`
2. Install `requirements-dev.txt` + run `./utils/run_tests.sh --normal`

Optional: cobertura coverage artifacts for the GitLab MR widget — not required for pure-suite merge readiness.

---

## 6. Platform 3: AWS CodeCommit & CodeBuild (parity template)

File: `buildspec.yml` (template)

```yaml
version: 0.2
env:
  variables:
    PRIZMFORGE_TEST_MODE: "1"
phases:
  install:
    runtime-versions:
      python: 3.12
    commands:
      - python -m pip install --upgrade pip
      - pip install -r requirements-dev.txt
      - pip install ruff
  pre_build:
    commands:
      - ruff check .
      - ruff format --check .
  build:
    commands:
      - chmod +x utils/run_tests.sh
      - ./utils/run_tests.sh --normal -j 4 --timeout 30
```

---

## 7. Feature Parity Matrix (simplified)

| Feature / Gate | GitHub Actions (today) | GitLab (target) | CodeBuild (target) |
| ----- | ----- | ----- | ----- |
| **Trigger file** | `.github/workflows/python-package.yml` | `.gitlab-ci.yml` | `buildspec.yml` |
| **Lint gate** | `ruff check` + `format --check` | same | same |
| **Test gate** | `run_tests.sh --normal` | same | same |
| **Auto-format bot** | Yes (stefanzweifel auto-commit) | optional | optional |
| **Coverage fail-under** | Not enforced | optional | optional |
| **mypy hard gate** | No | optional | optional |
