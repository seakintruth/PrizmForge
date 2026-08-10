# Multi-Platform CI/CD & Git Mirroring Architecture (GitHub, GitLab, AWS CodeCommit)

This document provides a unified deployment configuration and workflow architecture that enables **PrizmForge** to be committed and continuously tested across **GitHub**, **GitLab**, and **AWS CodeCommit / CodeBuild**.

---

## 1. Executive Summary & Multi-Remote Strategy

To support multi-cloud deployments, DoD/GovCloud air-gapped environments, and enterprise migration paths, PrizmForge can be configured for **Multi-Remote Synchronization** and **Cross-Platform CI/CD Parity**.

### Core Architecture Goals

1. **Identical Quality Gates**: Enforce the exact same linting (`ruff`), static typing (`mypy`), security scanning (`ruff --select S` / AST security), and test coverage (`pytest --cov-fail-under=90`) across all three platforms.

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

Pushing simultaneously across GitHub, GitLab, and AWS CodeCommit provides significant strategic, operational, and compliance benefits for enterprise and defense-oriented Python projects.

### 2.1 Disaster Recovery & High Availability

* **Zero Single Point of Failure**: Outages or degraded performance on a single platform (e.g., a GitHub incident or a local GitLab server maintenance window) do not block team velocity.

* **Instant Failover**: If one git provider experiences service disruption, developers can immediately shift remote tracking targets and continue pushing/pulling without data loss.

### 2.2 Compliance & Multi-Cloud / Air-Gapped Alignment

* **Bridging Commercial & GovCloud Environments**: Developers can work using familiar commercial interfaces (GitHub/GitLab) while automatically keeping AWS GovCloud (IL4/IL5) CodeCommit repositories perfectly in sync.

* **Centralized AWS Security Operations**: CodeCommit integration allows security teams to run native Amazon Inspector and AWS Security Hub scans in GovCloud without forcing developers to abandon their primary code forge.

### 2.3 Mitigation of Vendor Lock-In

* **Platform Independence**: Keeps build scripts, deployment configs, and code hosting portable across cloud providers and version control vendors.

* **Cost & Feature Flexibility**: Prevents dependency on a single vendor's pricing tiers, API rate limits, or runner minutes.

### 2.4 Synchronized Developer Workflows

* **Elimination of Manual Mirroring**: A single `git push all` command or CI mirror job ensures that branches, tags, and commit histories remain 100% identical across all remotes.

* **No Divergent History**: Prevents messy merge conflicts caused by out-of-sync manual pulls or delayed batch backups.

### 2.5 Best-of-Breed Tooling Integration

* **Simultaneous Ecosystem Strengths**:

  * **GitHub**: Leverage community extensions, dependabot, and rich PR review tools.

  * **GitLab**: Utilize built-in container registries, Security Dashboards, and Cobertura visual coverage reports.

  * **AWS CodeCommit / CodeBuild**: Take advantage of fine-grained IAM role access, VPC endpoint isolation, and direct integration with AWS CodePipeline.

### 2.6 Multi-Environment Pipeline Validation

* **Diverse Runner Testing**: Running tests across GitHub Actions (Ubuntu runners), GitLab CI (Docker runners), and AWS CodeBuild (Amazon Linux/Container environments) catches environment-specific assumptions, pathing bugs, and toolchain discrepancies early.

---

## 3. Multi-Remote Git Configuration

### 3.1 Local Git Multi-Remote Push Setup

To configure a single Git remote target (`all`) that pushes to GitHub, GitLab, and AWS CodeCommit simultaneously, run the following commands in your local repository:

```bash
# Add individual remotes
git remote add github git@github.com:your-org/PrizmForge.git
git remote add gitlab git@gitlab.com:your-org/PrizmForge.git
git remote add codecommit codecommit::us-east-1://PrizmForge

# Create a unified 'all' remote for simultaneous pushing
git remote add all git@github.com:your-org/PrizmForge.git
git remote set-url --add --push all git@github.com:your-org/PrizmForge.git
git remote set-url --add --push all git@gitlab.com:your-org/PrizmForge.git
git remote set-url --add --push all codecommit::us-east-1://PrizmForge

# Push to all three remotes with one command:
git push all main
```

---

## 4. Platform 1: GitHub Actions Configuration

File: `.github/workflows/test.yml`

```yaml
name: PrizmForge GitHub CI/CD

on:
  push:
    branches: [ "main", "develop" ]
  pull_request:
    branches: [ "main", "develop" ]

concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

permissions:
  contents: read

jobs:
  static-security-and-lint:
    name: Code Quality & Security Audit
    runs-on: ubuntu-latest
    steps:
      - name: Checkout Repository
        uses: actions/checkout@v4

      - name: Set up Python 3.10
        uses: actions/setup-python@v5
        with:
          python-version: "3.10"
          cache: "pip"

      - name: Install Dependencies
        run: |
          python -m pip install --upgrade pip
          pip install ruff mypy

      - name: Run Ruff Linter & Security Rules (S / flake8-bandit)
        run: |
          ruff check . --select E,F,B,I,N,UP,S,A,RUF
          ruff format --check .

      - name: Run Mypy Static Type Checker
        run: |
          mypy agents/ core/ file_editing/ workflow/ cli/

  test-matrix:
    name: Pytest Suite (Python ${{ matrix.python-version }})
    needs: static-security-and-lint
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        python-version: ["3.10", "3.11", "3.12"]

    steps:
      - name: Checkout Repository
        uses: actions/checkout@v4

      - name: Set up Python ${{ matrix.python-version }}
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
          cache: "pip"

      - name: Install Test Dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
          pip install pytest pytest-cov pytest-mock hypothesis httpx pydantic fastapi pytest-benchmark

      - name: Execute Pytest Suite with 90% Coverage Gate
        env:
          PRIZMFORGE_TEST_MODE: "1"
        run: |
          pytest tests/ \
            -m "not slow" \
            --cov=agents \
            --cov=core \
            --cov=file_editing \
            --cov=workflow \
            --cov=cli \
            --cov-report=term-missing \
            --cov-report=xml \
            --cov-fail-under=90

      - name: Upload Coverage XML Artifact
        uses: actions/upload-artifact@v4
        with:
          name: coverage-py${{ matrix.python-version }}
          path: coverage.xml
```

---

## 5. Platform 2: GitLab CI/CD Configuration

File: `.gitlab-ci.yml`

```yaml
stages:
  - lint_and_security
  - test
  - mirror

variables:
  PIP_CACHE_DIR: "$CI_PROJECT_DIR/.cache/pip"
  PRIZMFORGE_TEST_MODE: "1"

cache:
  paths:
    - .cache/pip
    - .venv/

before_script:
  - python -V
  - python -m pip install --upgrade pip

# --- LINT & SECURITY STAGE ---

ruff_and_mypy:
  stage: lint_and_security
  image: python:3.10
  script:
    - pip install ruff mypy
    - ruff check . --select E,F,B,I,N,UP,S,A,RUF
    - ruff format --check .
    - mypy agents/ core/ file_editing/ workflow/ cli/

# --- TEST MATRIX STAGE ---

.test_template: &test_definition
  stage: test
  needs: ["ruff_and_mypy"]
  script:
    - pip install -r requirements.txt
    - pip install pytest pytest-cov pytest-mock hypothesis httpx pydantic fastapi pytest-benchmark
    - pytest tests/ -m "not slow" --cov=agents --cov=core --cov=file_editing --cov=workflow --cov=cli --cov-report=term-missing --cov-report=cobertura --cov-fail-under=90
  artifacts:
    reports:
      coverage_report:
        coverage_format: cobertura
        path: coverage.xml
    expire_in: 1 week

pytest_py310:
  <<: *test_definition
  image: python:3.10

pytest_py311:
  <<: *test_definition
  image: python:3.11

pytest_py312:
  <<: *test_definition
  image: python:3.12

# --- AUTOMATED MIRRORING STAGE (OPTIONAL) ---

sync_to_github_and_codecommit:
  stage: mirror
  image: alpine/git:latest
  only:
    - main
    - develop
  script:
    - git config --global user.email "ci-bot@prizmforge.internal"
    - git config --global user.name "PrizmForge CI Bot"
    - git remote add github_target https://oauth2:${GITHUB_MIRROR_TOKEN}@github.com/your-org/PrizmForge.git || true
    - git push github_target HEAD:${CI_COMMIT_REF_NAME} --force
```

---

## 6. Platform 3: AWS CodeCommit & CodeBuild Configuration

File: `buildspec.yml`

```yaml
version: 0.2

env:
  variables:
    PRIZMFORGE_TEST_MODE: "1"

phases:
  install:
    runtime-versions:
      python: 3.11
    commands:
      - echo "Installing Python build dependencies..."
      - python -m pip install --upgrade pip
      - pip install -r requirements.txt
      - pip install ruff mypy pytest pytest-cov pytest-mock hypothesis httpx pydantic fastapi pytest-benchmark
      # Optional: Download AWS Inspector SBOM Generator if running in CodeBuild
      - curl -s -O https://inspector-sbomgen.amazonaws.com/latest/linux/amd64/inspector-sbomgen || true
      - chmod +x inspector-sbomgen || true

  pre_build:
    commands:
      - echo "Running Ruff linting & security rules..."
      - ruff check . --select E,F,B,I,N,UP,S,A,RUF
      - echo "Running Mypy static type check..."
      - mypy agents/ core/ file_editing/ workflow/ cli/

  build:
    commands:
      - echo "Running Pytest suite with 90% coverage enforcement..."
      - pytest tests/ -m "not slow" --cov=agents --cov=core --cov=file_editing --cov=workflow --cov=cli --cov-report=term-missing --cov-report=xml --cov-fail-under=90

      # Optional: Inspector SBOM Generation
      - |
        if [ -f "./inspector-sbomgen" ]; then
          ./inspector-sbomgen directory --path . --output sbom.json
          aws inspector2-scan sbom --sbom file://sbom.json > scan_results.json || true
        fi

artifacts:
  files:
    - coverage.xml
    - sbom.json
    - scan_results.json
  name: PrizmForgeBuildArtifacts
```

---

## 7. Feature Parity & Cross-Platform Comparison Matrix

| Feature / Gate | GitHub Actions | GitLab CI/CD | AWS CodeBuild / Pipeline | 
| ----- | ----- | ----- | ----- | 
| **Pipeline Trigger File** | `.github/workflows/test.yml` | `.gitlab-ci.yml` | `buildspec.yml` | 
| **Python Version Matrix** | Matrix strategy (`3.10`, `3.11`, `3.12`) | Parallel jobs (`pytest_py310`, `py311`, `py312`) | Single runtime per build (matrix via CodePipeline) | 
| **Linting & Security Gate** | `ruff check . --select E,F,B,I,N,UP,S,A,RUF` | `ruff check . --select E,F,B,I,N,UP,S,A,RUF` | `ruff check . --select E,F,B,I,N,UP,S,A,RUF` | 
| **Type Checking Gate** | `mypy` | `mypy` | `mypy` | 
| **Test Suite Enforcement** | `pytest --cov-fail-under=90` | `pytest --cov-fail-under=90` | `pytest --cov-fail-under=90` | 
| **Test Artifacts Export** | `actions/upload-artifact` | `artifacts: reports: cobertura` | `artifacts: files` (S3 Export) | 
| **Secret Management** | GitHub Secrets (`${{ secrets.TOKEN }}`) | GitLab CI Variables (`$CI_JOB_TOKEN`) | AWS Secrets Manager / Parameter Store | 
