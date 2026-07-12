# Family Memory AI - Prompt Templates

## Purpose

This document contains the official prompt templates used throughout the project.

All prompts must follow these templates.

---

# Implementation Prompt Standard

Every implementation prompt must contain these sections:

Execution Environment

Target

Estimated Task Size

Purpose

Expected Outcome

Repository

Definition of Done

Manual Test Plan

Acceptance Checklist

Suggested Commit Message

The prompt may include additional sections when needed, but these sections are mandatory for implementation work.

---

# Execution Environment Standard

Every ChatGPT-generated prompt for Family Memory AI must explicitly state where the prompt must be executed.

Allowed execution environment labels:

- 🌐 Codex Cloud
- 💻 Codex Local (VS Code)
- 🤖 GitHub Copilot (PR Comment)

Usage rules:

- Use 🌐 Codex Cloud for new sprints, new implementation work, and larger focused repository changes.
- Use 💻 Codex Local (VS Code) for local development/debug, Windows-specific reproduction, manual local verification, and work that must run against the Product Owner's local development environment.
- Use 🤖 GitHub Copilot (PR Comment) for follow-up improvements, review feedback, check-fix refinements, and other changes to an existing Pull Request.

ChatGPT must never provide an implementation prompt without an Execution Environment section.

---

# Target Standard

Every implementation or PR-feedback prompt must explicitly state the target of the work.

Examples:

```text
Target:
- New implementation
```

```text
Target:
- Existing Pull Request #9
- Existing branch: codex/improve-thumbnail-loading-speed-and-responsiveness
```

Rules:

- New work must state whether it should create a new branch or Pull Request.
- Existing PR feedback must state the Pull Request number and branch when known.
- Follow-up work on an existing PR must explicitly say not to create a new Pull Request unless the Product Owner asks for a new one.
- The target must appear before task details so the execution agent knows where to work before reading the implementation instructions.

---

# Documentation Update Standard

Documentation updates are mandatory for AI-assisted work.

Every implementation prompt must instruct the execution agent to update all affected canonical documentation before the task is considered complete.

At minimum, the agent must evaluate whether these documents require updates:

- docs/project/PROJECT_STATE.md
- docs/releases/CHANGELOG.md
- docs/architecture/ documentation
- docs/product/ documentation
- docs/development/AI_PROJECT_PLAYBOOK.md
- docs/development/PROMPT_TEMPLATE.md
- docs/development/DECISIONS.md
- contextual Workspace Help content

Documentation should be updated only where affected. Do not create new documentation files unless the new file has unique responsibility and clear long-term value.

ChatGPT may update repository documentation directly only after explicit Product Owner confirmation. When ChatGPT updates documentation directly, the change must be limited to the approved documentation scope and must preserve canonical ownership boundaries.

---

# Development Sprint Template

Execution Environment

Target

Estimated Task Size

Purpose

Expected Outcome

Repository

Sprint number or milestone

Project context

Files to read

Implementation tasks

Why We Test

Definition of Done

Implementation is not complete until all applicable conditions are satisfied:

- implementation finished
- documentation updated
- docs/project/PROJECT_STATE.md updated
- docs/releases/CHANGELOG.md updated
- tests updated or confirmed not applicable
- PR created or updated when the environment permits
- merge conflicts resolved
- repository ready for review

If GitHub verification cannot be completed because of environment limitations, explicitly state this instead of pretending verification succeeded.

Manual Test Plan

- How to manually test the feature
- Expected behaviour
- Persistence checks
- Regression checks
- Expected results

Acceptance Checklist

- Feature works
- Existing behaviour preserved
- UI regression check completed when applicable
- Performance regression check completed when applicable
- Documentation updated
- PROJECT_STATE updated
- CHANGELOG updated
- Tests updated or confirmed not applicable
- PR created or updated, or environment limitation stated
- Merge conflicts resolved
- Ready for review

Suggested Commit Message

---

# Bug Fix Template

Execution Environment

Target

Estimated Task Size

Purpose

Expected Outcome

Repository

Bug description

Why this fix exists

Expected behaviour

Implementation

Why We Test

Definition of Done

- fix implemented
- regression tests updated or confirmed not applicable
- documentation updated where affected
- docs/project/PROJECT_STATE.md updated when operational state changes
- docs/releases/CHANGELOG.md updated
- PR created or updated when the environment permits
- merge conflicts resolved
- repository ready for review

If GitHub verification cannot be completed because of environment limitations, explicitly state this instead of pretending verification succeeded.

Manual Test Plan

- How to manually test the fix
- Expected behaviour
- Persistence checks
- Regression checks
- Expected results

Acceptance Checklist

- Fix works
- Existing behaviour preserved
- UI regression check completed when applicable
- Performance regression check completed when applicable
- Documentation updated
- Tests updated or confirmed not applicable
- PR created or updated, or environment limitation stated
- Ready for review

Suggested Commit Message

---

# Documentation Sync Template

Execution Environment

Target

Estimated Task Size

Purpose

Expected Outcome

Repository

Goal

Target document

Tasks

Constraints

Definition of Done

- canonical owning document updated
- no duplicate documentation introduced
- cross-references updated where appropriate
- docs/project/PROJECT_STATE.md updated when operational state changes
- docs/releases/CHANGELOG.md updated
- repository ready for review

Manual Test Plan

Acceptance Checklist

Suggested Commit Message

---

# User Action Rule

When ChatGPT gives operational guidance to the Product Owner, it must always finish with:

NEXT ACTION

Estimated time

Step-by-step instructions

Expected result

Explicit "Do NOT..." instructions whenever appropriate

Never finish an implementation discussion without a clear next action.

---

## Rules

- Always update documentation.
- Every implementation prompt must include Execution Environment, Target, Estimated Task Size, Purpose, Expected Outcome, Repository, Definition of Done, Manual Test Plan, Acceptance Checklist, and Suggested Commit Message.
- Every implementation prompt must include Why We Test when code, tests, UI, workflow behavior, or user-facing behavior changes.
- Every prompt must clearly state whether it targets new work or an existing Pull Request.
- ChatGPT may update repository documentation directly only after explicit Product Owner confirmation.
- Never modify unrelated files.
- Keep commits focused.
- One Sprint = one objective.
- One Documentation Sync = one document whenever practical.
