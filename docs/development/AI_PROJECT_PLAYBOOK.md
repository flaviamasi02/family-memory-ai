# Family Memory AI - AI Project Playbook

## Purpose

This document defines the development methodology used by AI assistants working on Family Memory AI.

It allows any future AI to immediately understand how the project is managed.

---

# Core Principles

- AI generates as much implementation work as possible.
- The Product Owner makes all product decisions.
- Every important idea must be explicitly approved before becoming part of the project.
- Follow the Single Source of Truth principle.
- Documentation First Development.
- Mobile-First Documentation whenever practical.
- One Sprint = one objective.
- Keep commits focused.
- Documentation updates are mandatory.
- Documentation is Production Code (constitutional principle).
- Contextual Workspace Help is a mandatory product feature.

---

# Workspace Help Documentation Policy (Permanent)

Family Memory AI treats contextual Workspace Help as part of the shipped product, not optional documentation.

Policy requirements:

- Every user-facing workspace must provide contextual Help.
- Help content is mandatory product functionality.
- Every feature that changes user experience must update corresponding workspace Help content.
- Every workflow change must update corresponding workspace Help content.
- Every UI interaction change must update corresponding workspace Help content.
- Every AI behavior change that affects user decisions must update corresponding workspace Help content.
- No feature is complete until workspace Help content is updated.

Required Help coverage per workspace:

- What this workspace does.
- Why it exists.
- When it should be used.
- How the user should use it.
- What the AI does automatically.
- What decisions are expected from the user.
- Best practices.
- Tips and recommendations.

---

# Documentation Structure

Reference the official documentation files:

- docs/development/IDEAS.md
- docs/development/DECISIONS.md
- docs/development/SYNC_QUEUE.md
- docs/project/PROJECT_STATE.md
- docs/bootstrap/HANDOVER.md
- docs/project/ROADMAP.md
- docs/development/PROMPT_TEMPLATE.md

Each document has a single responsibility.

---

# AI Behaviour

Always:

- explain important technical decisions;
- avoid unnecessary complexity;
- propose improvements but wait for Product Owner approval before changing project direction;
- keep documentation synchronized;
- respect the Decision Ledger.

Before proposing a new documentation file, first evaluate whether an existing document can be extended without violating ownership boundaries.

Create a new document only when it provides unique responsibility, clear separation of concerns, and measurable long-term value.

---

# Session Types

Documentation Session

Development Session

Architecture Session

Review Session

---

## Command Execution

Before executing any project command:

1. Parse the command.
2. Validate prerequisites.
3. If prerequisites are missing, stop execution.
4. Request the missing resources.
5. Resume execution only after the prerequisites have been provided.

---

# End of Sprint Checklist

Before considering a Sprint complete:

- objective completed and verified;
- tests/manual validation completed when applicable;
- documentation updated where affected;
- workspace Help updated for all impacted user-facing workspaces;
- documentation completeness verified for all impacted ownership documents;
- docs/project/PROJECT_STATE.md updated;
- docs/releases/CHANGELOG.md updated;
- docs/bootstrap/HANDOVER.md updated if navigation or operating context changed;
- docs/development/SYNC_QUEUE.md reviewed and synchronized.

---

# Git Workflow

Every implementation should follow the same sequence to keep the repository clean and make changes easy to review or revert.

## Standard Workflow

1. Review the current project state.
2. Create a snapshot commit before significant work.

Example commit message:

`docs: snapshot before <feature or refactoring>`

3. Implement the requested changes.
4. Run available tests.
5. Perform documentation synchronization (`DOCSYNC PC` or `DOCSYNC PC FULL`).
6. Review all modified files.
7. Create the final implementation commit.
8. Push to the remote repository when the user decides.

## Commit Message Convention

Official commit prefixes:

- `feat:` New functionality.
- `fix:` Bug fix.
- `docs:` Documentation only.
- `refactor:` Code restructuring without functional changes.
- `test:` Tests.
- `chore:` Maintenance tasks.
- `style:` Formatting or style-only changes.
- `perf:` Performance improvements.

## Snapshot Commits

Snapshot commits should be created before significant or risky work to preserve a clean rollback point.

Examples:

- Before documentation refactoring.
- Before large architectural changes.
- Before major UI redesigns.
- Before risky refactoring.

## Final Commits

Final commits should summarize the completed work.

Examples:

- `feat: complete DEV-003 candidate selection engine`
- `docs: reorganize documentation architecture`
- `refactor: simplify photo browser selection logic`

## AI Responsibilities

AI assistants should:

- Suggest creating a snapshot commit before major work.
- Never ask the user to commit after every tiny change.
- Group logically related changes into a single implementation commit.
- Keep commit messages short and meaningful.

## Definition of Done

The Git workflow is the official development workflow for Family Memory AI.

Future AI assistants should consistently follow this workflow.

## Documentation Validation Workflow

Recommended flow for documentation governance:

Development

↓

DOCSYNC

↓

VS Code Copilot

↓

Commit

↓

Export latest project ZIP

↓

DOCVERIFY

↓

If PASS

Continue development

If WARNING or FAIL

Generate follow-up prompts

DOCSYNC obligations:

- Always update contextual workspace Help content whenever functionality, workflow, UI interaction, or AI decision behavior changes.

DOCVERIFY obligations:

- Always verify that contextual workspace Help matches implemented behavior.
- Report missing or outdated workspace Help as a documentation issue.

Definition of Done enforcement:

- Future AI assistants must treat workspace Help updates as part of Definition of Done.
- A user-facing feature is not considered complete until its contextual Workspace Help has been updated and accurately reflects current functionality.
