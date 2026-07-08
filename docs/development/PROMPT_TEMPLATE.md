# Family Memory AI - Prompt Templates

## Purpose

This document contains the official prompt templates used throughout the project.

All prompts must follow these templates.

---

# Implementation Prompt Standard

Every implementation prompt must contain these sections:

Execution Environment

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

# Development Sprint Template

Execution Environment

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
- Every implementation prompt must include Execution Environment, Estimated Task Size, Purpose, Expected Outcome, Repository, Definition of Done, Manual Test Plan, Acceptance Checklist, and Suggested Commit Message.
- Every implementation prompt must include Why We Test when code, tests, UI, workflow behavior, or user-facing behavior changes.
- Never modify unrelated files.
- Keep commits focused.
- One Sprint = one objective.
- One Documentation Sync = one document whenever practical.
