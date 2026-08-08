# Compliance, RMF & Secure Development (Navy RAISE / DoD)

This document records **authorization-oriented** implementation and security requirements for deploying Python CLI and (where applicable) **Shiny for Python** workloads in **AWS GovCloud (US)** under continuous authorization patterns aligned with **Navy RAISE 2.0**.

It is **governance and control-mapping documentation**, not the automated test suite. Day-to-day pytest guidance is in [`tests/README.md`](tests/README.md). Local product setup remains in [`README.md`](README.md) and [`CONFIGURATION.md`](CONFIGURATION.md).

> Placeholders such as `[Name]` / `[repository-url]` should be filled for a specific program of record. PrizmForge itself is the multi-agent forge; target applications (e.g. ExampleProject Shiny viewers) inherit platform controls when deployed on an approved RPOC.

---

## Solution context

Python solutions may operate as:

- A **CLI** utility (batch / agent / ops entrypoints), and/or
- An interactive **Shiny for Python** dashboard

when containerized for **AWS Elastic Kubernetes Service (EKS)** in **AWS GovCloud (US)**, engineered to support continuous Authorization to Operate (**cATO**) under **Navy RAISE 2.0** (Rapid Assess and Incorporate Software Engineering).

---

## RMF compliance framework & governance

To clear authorization gates and establish platform-level control inheritance with the Navy Authorizing Official (NAO), technical controls map to:

| Layer | Standard |
|-------|----------|
| **Federal foundation** | [NIST SP 800-53 Revision 5](https://csrc.nist.gov/publications/detail/sp/800-53/rev-5/final) — Security and Privacy Controls for Information Systems and Organizations |
| **DoD implementation** | [DoD Instruction 8510.01](https://www.esd.whs.mil/Portals/54/Documents/DD/issuances/dodi/851001p.pdf) — Risk Management Framework for DoD Information Technology |
| **Navy continuous authorization** | **Navy RAISE 2.0** memorandum — automated CI/CD security gating and control inheritance via an approved Platform of Choice (RPOC) |

---

## Software development security requirements

Secure development principles follow the **DISA Application Security and Development (ASD) STIG**.

### 1. Secure Python architecture (DISA ASD STIG)

| Topic | Requirement |
|-------|-------------|
| **Least privilege execution (APSC-DV-000510)** | Container image must not run as `root`. CLI and Shiny runtimes use a dedicated unprivileged user (e.g. **UID 10001**). |
| **Session & memory management (APSC-DV-000060)** | For reactive Shiny UIs, clear temporary user storage, state, and session variables on browser close, session end, or timeout. |
| **Input validation & sanitization** | CLI flags/parameters and Shiny reactive inputs validated against strict types to reduce injection and XSS risk. |

PrizmForge-specific technical controls already in-tree (engineering, not a STIG checklist): path containment under repo root, **content safety** (reject PE/MSI/OLE binaries in governed edits), config validation, and optional `llm.test_mode` without live keys.

### 2. Container hardening & AWS EKS governance

- **Base images:** Build on DoD-approved images from **Iron Bank / DCAR** where the program requires it.
- **EKS network isolation:** Kubernetes Network Policies; block AWS **IMDSv2** metadata access unless explicitly audited and permitted by the ISSE.

---

## RMF & RAISE 2.0 compliance artifacts matrix

Deliverables typically presented to the **ISSE** and **Navy Qualified Validator (NQV)**:

### 1. Initial deployment & boundary readiness (pre-deployment)

| Artifact | Purpose |
|----------|---------|
| **Application Security Plan (ASP) addendum** | Architecture, state tracking, pod boundaries; map to host EKS inherited NIST SP 800-53 controls |
| **DISA ASD STIG checklist (.ckl)** | STIG Viewer results; N/A or inherited items need justified text |
| **PPSM** | Ports, protocols, services (e.g. HTTPS :443 ingress; outbound to data stores / AWS APIs) |
| **eMASS inheritance matrix** | Inherited vs application-layer controls from the RPOC |

### 2. Automated CI/CD artifacts (continuous monitoring)

| Artifact | Purpose |
|----------|---------|
| **SBOM** | CycloneDX or SPDX inventory of Python dependencies and licenses |
| **SAST report** | e.g. `bandit` — no unmitigated High/Critical in custom code |
| **Container vulnerability scan** | Registry/image scan; no unmitigated OS/library CVEs per policy |
| **Pipeline compliance manifest** | Signed or attested receipt that security gates passed without improper overrides |

---

## DevSecOps pipeline & continuous monitoring

- **Remediation threshold:** Fail the build on unmitigated **Critical** or **High** findings per program policy.
- **GovCloud validation:** After push to **Amazon ECR**, continuous assessment (e.g. **Amazon Inspector**) for vulnerabilities and drift.

PrizmForge’s **pytest gates** (`tests/README.md`) support engineering quality; they **do not** replace SBOM, STIG .ckl, or Inspector evidence packages.

---

## Local development (security-oriented checks)

### Prerequisites

- Docker or Podman (for container builds)
- Python 3.11+ (project may support 3.12+ in practice)
- AWS CLI with GovCloud sandbox credentials when deploying

### Suggested local flow

```bash
git clone [repository-url]
cd [project-directory]

python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
# optional: pip install -r requirements-dev.txt

# Static security (when bandit is available in the environment)
bandit -r . --exclude .venv,tests,report

# Engineering test suite (no network required for default gate)
pytest tests/ -m "not slow" -q
```

**CLI / agent forge (this repo):**

```bash
python main.py
# or unattended via config.json cli_mode + optional llm.test_mode
```

**Target Shiny web mode (example application under `project_directory`, e.g. ExampleProject):**

```bash
pip install shiny
cd ExampleProject
shiny run app.py
```

---

## Points of contact

| Role | Contact |
|------|---------|
| Project ISSE | [Name] ([Email]) |
| Lead Cloud Engineer (EKS) | [Name] ([Email]) |
| Navy Qualified Validator (NQV) | [Name] ([Email]) |

---

## Document control

| Item | Value |
|------|--------|
| Audience | ISSE, NQV, developers integrating with RPOC |
| Related engineering docs | `README.md`, `CONFIGURATION.md`, `tests/README.md`, `architecture.md` |
| Related product tests | Pytest suite — **not** a substitute for STIG/SBOM/scan packages |
