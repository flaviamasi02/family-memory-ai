# Family Memory AI - Handover

# START HERE

Every new AI assistant must begin with this document.

This is the single entry point for onboarding and orientation before any planning or implementation work.

---

# Mandatory Initialization Workflow

Every new ChatGPT session must follow this initialization workflow exactly.

The assistant must read mandatory documents in this order:

1. docs/bootstrap/HANDOVER.md
2. docs/bootstrap/DOCUMENTATION_FRAMEWORK.md
3. docs/bootstrap/AI_BOOTSTRAP.md
4. docs/bootstrap/COMMANDS.md
5. docs/development/DOCUMENTATION_ARCHITECTURE.md
6. docs/project/PROJECT_CONTEXT.md
7. docs/project/PROJECT_STATE.md
8. docs/development/AI_PROJECT_PLAYBOOK.md
9. docs/development/DECISIONS.md
10. docs/project/ROADMAP.md (if present)
11. docs/project/GLOSSARY.md
12. Any additional mandatory documents referenced by the documents above

The assistant must complete the full initialization workflow before responding to project requests.

---

# Initialization Rules

ChatGPT must:

- Read all mandatory documents before performing any implementation work.
- Verify the Documentation Framework version before implementation work.
- Treat docs/bootstrap/COMMANDS.md as the authoritative reference for project commands.
- Execute documented commands automatically.
- Never invent command behavior.
- Never skip mandatory documents.
- Report if any mandatory document is missing.
- Build complete project context before answering.

---

## Reading Order and Responsibilities

Read the documentation in this exact order:

1. docs/bootstrap/HANDOVER.md
2. docs/bootstrap/DOCUMENTATION_FRAMEWORK.md
3. docs/bootstrap/AI_BOOTSTRAP.md
4. docs/bootstrap/COMMANDS.md
5. docs/development/DOCUMENTATION_ARCHITECTURE.md
6. docs/project/PROJECT_CONTEXT.md
7. docs/project/PROJECT_STATE.md
8. docs/development/AI_PROJECT_PLAYBOOK.md
9. docs/development/DECISIONS.md
10. docs/project/ROADMAP.md (if present)
11. docs/project/GLOSSARY.md
12. Any additional mandatory documents referenced by the documents above

This document defines what must be read, in which order, and why the initialization sequence is mandatory.

docs/bootstrap/AI_BOOTSTRAP.md defines mandatory AI operating behavior.

docs/bootstrap/DOCUMENTATION_FRAMEWORK.md defines framework versioning and compatibility rules.

docs/bootstrap/COMMANDS.md defines how project commands work and what each command does.

The framework distinguishes between preparation commands (DOCSYNC) and verification commands (DOCVERIFY); see docs/bootstrap/COMMANDS.md for authoritative behavior.

This document must not duplicate command definitions; command behavior is owned only by docs/bootstrap/COMMANDS.md.

---

## Product North Star

Version 1 of Family Memory AI has one primary objective:

"Automatically create the best possible annual family photo album."

Future capabilities (Vacation Albums, Gift Albums, Story Timeline, and similar expansions) are intentionally postponed while keeping the architecture extensible.

---

## Current Development

DEV-001 (Annual Album Foundation) has been completed.

DEV-002 (Photo Intelligence Foundation) has been completed.

Next planned sprint: DEV-004 - Album Scoring Engine.

For detailed operational status, always refer to docs/project/PROJECT_STATE.md.

---

## First Actions for a New AI

- Complete the mandatory initialization workflow in the required order.
- Verify docs/project/PROJECT_STATE.md before proposing any work.
- Continue with the next planned Sprint.
- Respect all approved decisions.
- Never change project direction without Product Owner approval.

---

## Single Source of Truth

Each information type has one official location. Reference these documents instead of duplicating their content:

- docs/project/PROJECT_STATE.md: current operational state
- docs/project/ROADMAP.md: planned milestones and priorities
- docs/releases/CHANGELOG.md: implementation history by sprint
- docs/development/DECISIONS.md: approved decisions
- docs/development/AI_PROJECT_PLAYBOOK.md: working method and sprint discipline
- docs/project/PROJECT_CONTEXT.md: long-term collaboration and development context

---

## Maintenance Note

If new mandatory project documents are introduced in the future, this reading order must be updated so that every new ChatGPT conversation starts with a complete and consistent project context.

