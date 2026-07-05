# Family Memory AI - Domain Roadmap

## Purpose

This document is the official roadmap for future development by domain.

It operates under the higher-level direction defined in docs/project/MASTER_DEVELOPMENT_PLAN.md.

Historical implementation remains recorded through completed DEV-XXX work.

Future implementation is organized by functional domains rather than a single sequential sprint chain.

---

## Workflow Principle

Historical development:

- DEV-001
- DEV-002
- DEV-003
- DEV-004
- DEV-005
- BUG-001
- PERF-001
- DEV-006

Future development:

- domain-based development

Whenever a new feature is requested, the correct domain should be identified first.

The project should not automatically continue with DEV-007, DEV-008, and later numbers as the primary planning model.

Instead, new work should create or continue milestones inside the appropriate functional domain.

MASTER_DEVELOPMENT_PLAN.md defines the product-level purpose of the domains.

---

## FOUNDATION

Status:
Completed

Mission:
Preserve the historical deterministic desktop foundation that later domains build upon.

Historical scope:

- DEV-001
- DEV-002
- DEV-003
- DEV-004
- DEV-005
- BUG-001
- PERF-001
- DEV-006

Purpose:
Build the deterministic desktop foundation for import, metadata, scoring, review UI, and first album-draft assembly.

Example milestones:

- DEV-001
- DEV-002
- DEV-003
- DEV-004
- DEV-005
- BUG-001
- PERF-001
- DEV-006

---

## MEM

Title:
Memory Review

Purpose:
Review meaningful memories.

Mission:
Teach the system what memories matter.

Example milestones:

- MEM-003 Multi-Select Bulk Category Editing (completed)
- MEM-004 Compact Memory Review thumbnail grid (completed)
- MEM-005 True multi-column Memory Review grid (completed)
- MEM-006 Memory Review UX polishing and keyboard workflow improvements

---

## CLEAN

Title:
Cleanup Engine

Purpose:
Detect irrelevant media.

Mission:
Safely identify clutter and cleanup-oriented media without permanent deletion.
Cleanup Review should follow the same UX philosophy as Memory Review: toolbar filters, compact thumbnail grid, and right-side explainable details.

Example milestones:

- CLEAN-001 Media Classification & Decision Engine Foundation (completed)
- CLEAN-002 Improved deterministic initial media classification (completed)
- CLEAN-003 Cleanup Review UX & Explainability (completed)
- CLEAN-004 Advanced cleanup and duplicate workflows
- CLEAN-005 Visual content-based local classification (completed)

---

## DUP

Title:
Duplicate Management

Purpose:
Duplicate detection.

Mission:
Reduce redundant media while preserving the best version and respecting meaningful differences.

Scope examples:

- exact duplicates
- visual duplicates
- best-quality selection

---

## LEARN

Title:
Preference Learning

Purpose:
Learn user preferences.

Mission:
Turn repeated user decisions into future personalization signals.

Foundation dependency:

- MEM-008 user-defined taxonomy stores per-category AI Description metadata for future explainable AI-assisted classification.

Milestones:

- LEARN-001 Explainable Category Learning (completed)
Goal:
Learn from user corrections while remaining fully explainable.

- LEARN-002 Hybrid AI Classification
Goal:
Combine deterministic rules, learned user preferences and AI inference into a single explainable decision.

---

## PEOPLE

Title:
People Intelligence

Purpose:
Recognize important people.

Mission:
Model family members, their relationships, and their relative importance over time.

Scope examples:

- family relationships
- importance learning

---

## EVENT

Title:
Event Intelligence

Purpose:
Model family events.

Mission:
Understand recurring and meaningful events that shape family memory collections.

Scope examples:

- birthdays
- vacations
- Christmas
- school
- trips

---

## MEMORY

Title:
Memory Intelligence

Purpose:
Model what makes memories meaningful.

Mission:
Transform signals from preferences, events, people, and curation into reusable Memory Intelligence.

Scope examples:

- Memory Value
- Rarity
- Storytelling
- Album Balance
- Timeline

---

## OUTPUT

Title:
Outputs

Purpose:
Generate meaningful outputs from Memory Intelligence.

Mission:
Turn Memory Intelligence into user-facing outputs without making any single output the sole purpose of the product.

Scope examples:

- Album Builder
- Album Refinement
- PDF
- Photo Book
- Slideshows
- Search

---

## Current Active Domain

- CLEAN

## Current Milestone

- CLEAN-003 Cleanup Review UX & Explainability (completed)

## Recently Completed Domains

- FOUNDATION
- MEM (review UX and decision ergonomics foundation)
- CLEAN (deterministic classification and cleanup-review UX foundation)

## Future Planned Domains

- MEM
- LEARN
- DUP
- PEOPLE
- EVENT
- MEMORY
- OUTPUT
