![PrizmForge Logo](assets/logos/logo.png)

# PrizmForge

**Autonomous multi-agent software engineering system with governed self-editing.**

PrizmForge enables AI agents to safely modify a project repository, even a copy of their own codebase through a structured proposal and review process, while maintaining full auditability and human oversight.

## Core Philosophy

PrizmForge solves the fundamental problem of **safe autonomous code modification** by enforcing a strict separation between:

- **Mutation path** (sequential, governed): Developer → Proposal → Reviewer gate → Materialization
- **Analysis path** (parallel): Background agents provide continuous feedback without mutation rights

## Architecture

### System Architecture Diagram

```mermaid
flowchart TB
    subgraph PrizmForge["PrizmForge System"]
        direction TB

        MainOrch["Main Orchestrator\n(Sequential Task Loop)"]
        Governed["Governed Edit Pipeline\n(EditPayload → Proposal → Reviewer → Materialize)"]
        Parallel["Parallel Background Agents\n(jr_reviewer, archivist, report builder, etc.)"]
        Resource["Resource Controller\n(Throttling & Prioritization)"]
        DB[(SQLite Database\nUnified Schema)]

        MainOrch --> Governed
        Governed --> DB
        Parallel --> DB
        Resource --> Parallel
        
        %% Autonomous loop - Orchestrator reads proposals/tasks from DB (unattended mode)
        DB --> MainOrch
    end

    User["Developer / Human"] -.->|Optional: High-level goals & oversight| MainOrch
    LLM["LLM Endpoints\n(OpenAI, Gemini, etc.)"] <--> MainOrch
    LLM <--> Parallel
```

### Agent Classes

```mermaid
flowchart BT
    subgraph Class3["Class 3: Specialist Review Agents"]
        direction TB
        JrReviewer["jr_reviewer"]
        Security["security_reviewer"]
        TechWriter["tech_writer"]
        JrResearcher["jr_researcher"]

        JrReviewer --> Feedback["Feedback Store"]
        Security --> Feedback
        TechWriter --> Feedback
        JrResearcher --> Feedback
    end

    subgraph Class2["Class 2: Tool-Enabled Parallel Agents"]
        direction TB
        Prioritizer["Prioritizer"]
        Archivist["Archivist"]
        ReportBuilder["Report Builder"]
        ResourceCtrl["Resource Controller"]

        Prioritizer --> Feedback
        Archivist --> Feedback
        ReportBuilder --> Reports["Report Files"]
        ResourceCtrl --> Throttling["Throttling & Prioritization"]
    end

    subgraph Class1["Class 1: Strict File Edit Cycle"]
        direction TB
        Orchestrator["Orchestrator"]
        Developer["Developer"]
        Reviewer["Reviewer"]
        DBMat["DB + File Materialization"]

        Orchestrator --> Feedback
        Orchestrator --> Developer
        Developer --> Reviewer
        Reviewer --> DBMat
        DBMat --> Files["Project Files"]

        Files -.->|Triggers review upon commit| Class3
    end

    Feedback --> Orchestrator
    Class3 --> Feedback
    Class2 --> Feedback

    Class2 --> Class1
    Class1 --> Class2

    Reports["Report Files"]
    Throttling["Throttling & Prioritization"]
```

## Current File Editing Methodology (Governed Editing)

PrizmForge no longer uses traditional diffs or patches. Instead, it uses a **line-level governed editing system**:

### Key Concepts

- **Line GUIDs**: Every line in a governed file has a stable UUID (`line_guid`) + `sort_order` (REAL). This enables precise insertions, deletions, and replacements without relying on line numbers.
- **EditPayload**: Structured operations (`replace_block`, `insert_after`, `delete_lines`, etc.) validated by Pydantic.
- **Proposal**: A formal request containing the `EditPayload`, expected content hashes, and affected line GUIDs.
- **Optimistic Concurrency**: Proposals capture content hashes at creation time. If the file changes before application, the proposal is rejected as `conflicted`.
- **Reviewer Gate**: All proposals must be reviewed (by an agent or human) before materialization.
- **Materialization**: Only approved proposals are applied via `apply_edit_proposal()`.

### Editing Flow

```
Developer Agent
      │
      ▼
EditPayload (structured operations)
      │
      ▼
create_proposal_from_developer_output()
      │
      ▼
Proposal stored with expected_hashes + affected_line_guids
      │
      ▼
Reviewer Agent (or human) reviews
      │
      ▼
Status → approved / rejected
      │
      ▼
apply_edit_proposal(proposal_id)
      │
      ▼
validate_proposal() → hash check
      │
      ▼
Materialize changes to file_lines table
      │
      ▼
(Optional) writer.py → disk
```

This approach provides:
- Precise, stable edits even as files change
- Strong protection against concurrent modification
- Full audit trail of every proposed change
- Clear separation of proposal creation and application

## Key Safety Features

- Line-level optimistic concurrency via content hashes
- Strict Pydantic validation on all edit operations
- Reviewer safety gate before any mutation
- Post-write invalidation of overlapping proposals
- Comprehensive error logging and proposal status tracking

## Testing

The project includes a growing test suite focused on:

- Governed editing logic and edge cases
- Schema initialization
- JSON parsing and truncation detection
- Token estimation and budgeting
- Resource Controller data structures and logic
- Endpoint Manager, Proposal Builder, Task Runner, Agent Execution, and Parallel Workers (including race conditions)

Run tests with:

```bash
pytest tests/ -q
```

## Getting Started

1. Ensure Python 3.12+
2. Install dependencies (see `requirements.txt` or equivalent)
3. Initialize the database:

```bash
python -c "from core.db import init_db; init_db()"
```

4. Start in interactive mode:

```bash
python interactive.py
```

## Project Status

PrizmForge is under active development. The governed editing system represents the current production methodology for safe autonomous modifications.

For detailed architecture, see `architecture.md`.

## License

MIT
See repository for license information.
