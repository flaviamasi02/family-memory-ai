# Family Memory AI - Prompt Templates

## Purpose

This document contains the official prompt templates used throughout the project.

All prompts must follow these templates.

---

# Documentation Sync Template

Repository

Goal

Target document

Tasks

Constraints

Commit message

Expected output

---

# Development Sprint Template

Repository

Sprint number

Goal

Project context

Why this feature exists

Files to read

Implementation tasks

Why We Test

Manual Test Plan

- How to manually test the feature
- Expected behaviour
- Persistence checks
- Regression checks
- Expected results

Tests

Definition of Done

Documentation Update (Mandatory)

Update:

- docs/project/PROJECT_STATE.md
- docs/releases/CHANGELOG.md
- Any affected documentation

Commit message

Acceptance Checklist

- Feature works
- Existing behaviour preserved
- UI regression check
- Performance regression check
- Documentation updated
- Ready for commit

---

# Bug Fix Template

Repository

Bug description

Why this fix exists

Expected behaviour

Why We Test

Manual Test Plan

- How to manually test the fix
- Expected behaviour
- Persistence checks
- Regression checks
- Expected results

Implementation

Regression tests

Documentation updates

Commit message

Acceptance Checklist

- Fix works
- Existing behaviour preserved
- UI regression check
- Performance regression check
- Documentation updated
- Ready for commit

---

## Rules

- Always update documentation.
- Every implementation prompt must include Why We Test, Manual Test Plan, and Acceptance Checklist.
- Never modify unrelated files.
- Keep commits focused.
- One Sprint = one objective.
- One Documentation Sync = one document whenever practical.
