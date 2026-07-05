# Family Memory AI
## Documentation Portal

This document is the entry point for understanding the Family Memory AI documentation ecosystem.

It helps developers and AI assistants quickly locate the correct document for each task.

Each document has a specific responsibility and should be used as the authoritative source for its domain.

---

## Documentation Overview

Family Memory AI documentation follows these principles:

- Single Source of Truth
- Documentation is Production Code
- AI-friendly documentation
- Minimal duplication
- Predictable organization
- Long-term maintainability

This principle is defined at the constitutional level in [PROJECT_CONSTITUTION.md](PROJECT_CONSTITUTION.md).

---

## Documentation Framework

Current framework version: 1.0.0

Purpose:

The Documentation Framework defines versioning, compatibility rules, core components, and upgrade policy for the entire documentation ecosystem.

Compatibility:

Framework 1.0.0 is compatible with:

- AI Bootstrap: 1.0
- Commands: 1.0
- Documentation Architecture: 1.0
- Project Constitution: 1.0

Authoritative reference: [bootstrap/DOCUMENTATION_FRAMEWORK.md](bootstrap/DOCUMENTATION_FRAMEWORK.md)

Core framework references:

- [bootstrap/AI_BOOTSTRAP.md](bootstrap/AI_BOOTSTRAP.md)
- [bootstrap/COMMANDS.md](bootstrap/COMMANDS.md)
- [development/DOCUMENTATION_ARCHITECTURE.md](development/DOCUMENTATION_ARCHITECTURE.md)

---

## Documentation Structure

```text
docs/
  bootstrap/
  project/
  development/
  architecture/
  testing/
  releases/
  archive/
```

Folder responsibilities:

- `bootstrap/`: Mandatory onboarding and execution entry points for AI sessions.
- `project/`: Product direction, state, roadmap, principles, and official terminology.
- `development/`: Team workflow, decisions, coding standards, and documentation governance.
- `architecture/`: System structure, components, data model, UI architecture, and API boundaries.
- `testing/`: Test strategy, test cases, reports, and validation references.
- `releases/`: Changelog, release notes, and migration guides.
- `archive/`: Historical legacy files retained for traceability.

---

## Getting Started

### For AI Assistants

Read in this order:

1. [bootstrap/HANDOVER.md](bootstrap/HANDOVER.md)
2. [bootstrap/DOCUMENTATION_FRAMEWORK.md](bootstrap/DOCUMENTATION_FRAMEWORK.md)
3. [bootstrap/AI_BOOTSTRAP.md](bootstrap/AI_BOOTSTRAP.md)
4. [bootstrap/COMMANDS.md](bootstrap/COMMANDS.md)
5. [development/DOCUMENTATION_ARCHITECTURE.md](development/DOCUMENTATION_ARCHITECTURE.md)
6. [project/PROJECT_CONTEXT.md](project/PROJECT_CONTEXT.md)
7. [project/PROJECT_STATE.md](project/PROJECT_STATE.md)
8. [development/AI_PROJECT_PLAYBOOK.md](development/AI_PROJECT_PLAYBOOK.md)
9. [development/DECISIONS.md](development/DECISIONS.md)
10. [project/ROADMAP.md](project/ROADMAP.md) (if present)
11. [project/GLOSSARY.md](project/GLOSSARY.md)

### For Developers

Start from the document that matches your goal:

- Understand the project: [project/PROJECT_CONTEXT.md](project/PROJECT_CONTEXT.md)
- Understand current implementation: [project/PROJECT_STATE.md](project/PROJECT_STATE.md)
- Review architecture: [architecture/ARCHITECTURE.md](architecture/ARCHITECTURE.md)
- Understand AI workflow: [development/AI_PROJECT_PLAYBOOK.md](development/AI_PROJECT_PLAYBOOK.md)
- Review decisions: [development/DECISIONS.md](development/DECISIONS.md)

---

## Documentation Index

| Document | Purpose | Typical Reader | Owner |
|---|---|---|---|
| [bootstrap/HANDOVER.md](bootstrap/HANDOVER.md) | Mandatory session entry point and reading order | AI assistants | Product/Architecture governance |
| [bootstrap/DOCUMENTATION_FRAMEWORK.md](bootstrap/DOCUMENTATION_FRAMEWORK.md) | Framework versioning, compatibility, and upgrade policy | AI assistants, developers | Documentation governance |
| [bootstrap/AI_BOOTSTRAP.md](bootstrap/AI_BOOTSTRAP.md) | AI operating behavior and initialization rules | AI assistants | Product/Architecture governance |
| [bootstrap/COMMANDS.md](bootstrap/COMMANDS.md) | Official command system and execution semantics | AI assistants, developers | Workflow governance |
| [project/PROJECT_CONTEXT.md](project/PROJECT_CONTEXT.md) | Product intent, context, and long-term direction | Developers, AI assistants | Product owner |
| [project/PROJECT_STATE.md](project/PROJECT_STATE.md) | Current implementation state and active sprint status | Developers, AI assistants | Development workflow |
| [project/ROADMAP.md](project/ROADMAP.md) | Planned milestones and forward priorities | Product owner, developers | Product planning |
| [project/GLOSSARY.md](project/GLOSSARY.md) | Official terminology definitions | Developers, AI assistants | Documentation governance |
| [PROJECT_CONSTITUTION.md](PROJECT_CONSTITUTION.md) | Stable constitutional principles of the project | Product owner, developers, AI assistants | Product/Architecture governance |
| [development/AI_PROJECT_PLAYBOOK.md](development/AI_PROJECT_PLAYBOOK.md) | Development methodology and sprint discipline | AI assistants, developers | Development workflow |
| [development/DECISIONS.md](development/DECISIONS.md) | Architecture Decision (DEC) ledger | Developers, architects, AI assistants | Architecture governance |
| [development/DOCUMENTATION_ARCHITECTURE.md](development/DOCUMENTATION_ARCHITECTURE.md) | Documentation structure, ownership, and rules | Developers, AI assistants | Documentation governance |
| [architecture/ARCHITECTURE.md](architecture/ARCHITECTURE.md) | High-level architecture and module boundaries | Developers, architects | Architecture governance |
| [releases/CHANGELOG.md](releases/CHANGELOG.md) | Versioned implementation history | Developers, stakeholders | Release management |

---

## Common Workflows

Starting a new ChatGPT session

```text
HANDOVER
  -> DOCUMENTATION_FRAMEWORK
    -> AI_BOOTSTRAP
      -> COMMANDS
        -> DOCUMENTATION_ARCHITECTURE
          -> PROJECT_CONTEXT
            -> PROJECT_STATE
```

Starting a new sprint

```text
PROJECT_STATE
  -> ROADMAP
    -> DECISIONS
      -> AI_PROJECT_PLAYBOOK
```

Documentation synchronization

```text
DOCSYNC PC
or
DOCSYNC PC FULL
  -> repository snapshot
    -> DOCVERIFY PC
or
DOCVERIFY PC FULL
```

DOCSYNC prepares documentation updates.

DOCVERIFY validates that approved updates are present in the repository snapshot provided by the user.

DOCVERIFY always requires the latest repository snapshot (ZIP, accessible updated repository, or updated files).

DOCSYNC: Preparation.

DOCVERIFY: Verification.

Architecture review

```text
DECISIONS
  -> ARCHITECTURE
    -> PROJECT_STATE
```

---

## Documentation Ownership

Canonical ownership:

- Project vision: [project/PROJECT_CONTEXT.md](project/PROJECT_CONTEXT.md)
- Current sprint and implementation status: [project/PROJECT_STATE.md](project/PROJECT_STATE.md)
- Architecture: [architecture/ARCHITECTURE.md](architecture/ARCHITECTURE.md)
- Commands: [bootstrap/COMMANDS.md](bootstrap/COMMANDS.md)
- Terminology: [project/GLOSSARY.md](project/GLOSSARY.md)
- Workflow and process: [development/AI_PROJECT_PLAYBOOK.md](development/AI_PROJECT_PLAYBOOK.md)
- Architecture decisions: [development/DECISIONS.md](development/DECISIONS.md)
- Documentation architecture: [development/DOCUMENTATION_ARCHITECTURE.md](development/DOCUMENTATION_ARCHITECTURE.md)

---

## Documentation Lifecycle

```text
Implementation
  -> PROJECT_STATE
    -> (if architecture changed) DECISIONS
      -> (if workflow changed) COMMANDS
        -> (if terminology changed) GLOSSARY
          -> (if documentation structure changed) DOCUMENTATION_ARCHITECTURE
```

---

## AI Collaboration

AI assistants should:

- Read documentation before implementing.
- Respect ownership boundaries.
- Avoid duplication.
- Update all affected documents.
- Run DOCSYNC PC FULL after significant work.
- Use DOCVERIFY only when the latest repository snapshot is available.

---

## Future Documentation

New documentation should be added without violating existing responsibilities.

Prefer extending existing documents before creating unnecessary new files.

---

## Related Documents

- [bootstrap/HANDOVER.md](bootstrap/HANDOVER.md)
- [bootstrap/DOCUMENTATION_FRAMEWORK.md](bootstrap/DOCUMENTATION_FRAMEWORK.md)
- [bootstrap/AI_BOOTSTRAP.md](bootstrap/AI_BOOTSTRAP.md)
- [bootstrap/COMMANDS.md](bootstrap/COMMANDS.md)
- [development/DOCUMENTATION_ARCHITECTURE.md](development/DOCUMENTATION_ARCHITECTURE.md)
- [project/PROJECT_CONTEXT.md](project/PROJECT_CONTEXT.md)
- [project/PROJECT_STATE.md](project/PROJECT_STATE.md)
- [development/AI_PROJECT_PLAYBOOK.md](development/AI_PROJECT_PLAYBOOK.md)
- [development/DECISIONS.md](development/DECISIONS.md)
- [project/ROADMAP.md](project/ROADMAP.md)
- [project/GLOSSARY.md](project/GLOSSARY.md)
- [architecture/ARCHITECTURE.md](architecture/ARCHITECTURE.md)

---

## Definition of Done

README.md is the documentation portal for Family Memory AI.

Developers and AI assistants should be able to understand the documentation ecosystem by reading this file alone.
