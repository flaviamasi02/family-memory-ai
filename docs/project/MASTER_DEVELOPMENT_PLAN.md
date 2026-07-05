# Family Memory AI - Master Development Plan

## Purpose

This is the highest-level project planning document for Family Memory AI.

Its purpose is not to describe implementation details.

Its purpose is to describe what the product must become.

Future AI assistants must use this document before planning new work.

Implementation should always follow the product vision.

Never implement features simply because they are technically possible.

Always ask:

"Does this improve Family Memory Intelligence?"

If not, the feature should probably not be prioritized.

---

## Product Mission

Family Memory AI is an intelligent memory management platform.

Albums are only one possible output.

Primary objectives:

- Organize memories
- Remove clutter
- Learn user preferences
- Understand family history
- Preserve meaningful memories
- Generate meaningful outputs

The long-term mission is:

"Help families preserve, organize, understand and rediscover the memories that matter most while continuously learning what is important for each family."

Current strategic priority order:

1. Reliable AI-assisted media classification
2. Learning from user corrections
3. Cleanup quality and safety
4. People Intelligence
5. Output generation (albums as one downstream consumer)

---

## Permanent Product Principles

- Explainable Intelligence
- Human-in-the-loop
- Continuous Learning
- User Trust
- Transparent Decisions

---

## Development Methodology

Historical implementation remains unchanged:

- DEV-001
- DEV-002
- DEV-003
- DEV-004
- DEV-005
- BUG-001
- PERF-001
- DEV-006

Future work is no longer organized as DEV-007, DEV-008, and later numbers.

Future work is organized by product domains.

---

## Product Domains

### FOUNDATION

Status:
Already completed.

Mission:
Provide the deterministic historical base that later product domains can extend safely.

Historical scope:

- DEV-001
- DEV-002
- DEV-003
- DEV-004
- DEV-005
- BUG-001
- PERF-001
- DEV-006

### MEM

Title:
Memory Review

Purpose:
Teach the system what memories matter.

Mission:
Make Memory Review the central place where meaningful user decisions are captured.

Future milestones:

- MEM-003 Multi-Select Bulk Category Editing (completed)
- MEM-004 Compact Thumbnail-First Memory Review Grid (completed)
- MEM-005 True Multi-Column Memory Review Grid (completed)
- MEM-006 Memory Review UX polishing and keyboard workflow improvements (completed)
- MEM-008 Custom User Categories (completed)
- MEM-009 Editable System Category Properties (completed)

MEM-008 completed outcome:

- Categories are no longer limited to hardcoded values.
- Users can manage custom taxonomy from Memory Review and Cleanup Review.
- Category metadata includes optional AI Description for future classifier learning.
- Album and cleanup decisions are category-flag driven (album candidate / cleanup category).

MEM-009 completed outcome:

- System categories are now customizable while keeping protected stable IDs.
- System category deletion remains disallowed.
- System-category reset-to-default is available per category.

### CLEAN

Title:
Cleanup Intelligence

Purpose:
Detect and safely remove irrelevant media.

Mission:
Reduce clutter while preserving safety, explainability, and user control.

Future milestones:

- CLEAN-001 Media Classification & Decision Engine Foundation (completed)
- CLEAN-002 Improved deterministic initial media classification (completed)
- CLEAN-003 Cleanup Review UX & Explainability (completed)
- CLEAN-004 Advanced cleanup and duplicate cleanup workflows
- CLEAN-005 Visual content-based media classification (completed)

CLEAN-005 completed outcome:

- Local visual analysis now augments deterministic metadata/filename classification.
- Metadata-less images are classified by explainable visual evidence when strong signals are present.
- Unknown remains a conservative fallback for weak or conflicting evidence.

### DUP

Title:
Duplicate Intelligence

Purpose:
Detect duplicate photos.

Mission:
Reduce redundant media while preserving the best-quality and most meaningful variants.

Rules and scope:

- prefer highest quality
- respect different facial expressions

Future milestones:

- DUP-001 Exact Duplicate Detection
- DUP-002 Visual Duplicate Detection
- DUP-003 Near Duplicate Scoring

### LEARN

Title:
Preference Learning

Purpose:
Learn from user decisions.

Mission:
Continuously improve recommendations and scoring from repeated user behavior.

Future milestones:

- LEARN-001 Category Learning from User Corrections (completed)
- LEARN-002 Preference Learning
- LEARN-003 Adaptive Scoring

### PEOPLE

Title:
People Intelligence

Purpose:
Learn family members, relationships, and importance.

Mission:
Understand who matters to the family and how people shape memory value.

Future milestones:

- PEOPLE-001 Face Detection and Family Photo Classification (completed)
- PEOPLE-002 Relationship Modeling
- PEOPLE-003 Importance Learning

PEOPLE-001 completed outcome:

- Added local-only face detection foundation as explainable Family Photo evidence.
- Added explicit background/manual face analysis workflow to avoid UI blocking import paths.
- No identity recognition, no person-name matching, and no cloud AI in this milestone.
- User corrections remain authoritative over automatic face-based categorization.

### EVENT

Title:
Event Intelligence

Purpose:
Understand birthdays, vacations, Christmas, trips, and celebrations.

Mission:
Recognize the events that give structure and meaning to family memory collections.

Future milestones:

- EVENT-001 Event Detection Foundations
- EVENT-002 Family Event Modeling
- EVENT-003 Event Importance

### MEMORY

Title:
Memory Intelligence

Purpose:
Model Memory Value, Storytelling, Timeline, Album Balance, and Rarity.

Mission:
Build reusable Memory Intelligence that can drive multiple outputs.

Future milestones:

- MEMORY-001 Memory Value
- MEMORY-002 Storytelling
- MEMORY-003 Timeline
- MEMORY-004 Album Balance
- MEMORY-005 Rarity

### OUTPUT

Title:
Outputs

Purpose:
Generate user-facing outputs from Family Memory Intelligence.

Mission:
Turn Memory Intelligence into useful experiences such as albums, books, slideshows, search, and timelines.

Future milestones:

- OUTPUT-001 Album Builder
- OUTPUT-002 Album Refinement
- OUTPUT-003 PDF
- OUTPUT-004 Photo Books
- OUTPUT-005 Slideshows
- OUTPUT-006 Timeline Viewer
- OUTPUT-007 Advanced Search

---

## Product Principles

Permanent principles:

- Memory is more important than technical quality.
- Different expressions are not duplicates.
- Albums should tell a story.
- Albums should represent the whole year.
- The system must continuously learn.
- Every important score must be explainable.
- User decisions are training signals.
- The application assists the user.
- The user always has the final decision.

Current deterministic workflow reference:

Import
-> Metadata Extraction
-> Media Classification
-> Memory Review
-> Cleanup Review
-> Decision Engine
-> Preference Learning (future)
-> Duplicate Management (future)
-> Memory Intelligence (future)
-> Album Builder

---

## Decision Engine

Future decision model:

- Pending
- ApprovedForAlbum
- Keep
- IrrelevantMedia
- Duplicate
- Document
- Screenshot
- Advertisement
- MemeGraphic
- Rejected
- Unknown

These decisions become long-term learning examples.

Category terminology for review interfaces:

- Media Category
- Automatic Category
- User Corrected Category
- Effective Category

Classification principles:

- initial classification remains deterministic and explainable
- classification confidence is a first-class signal for review prioritization
- default system categories are stable, user-correctable, and taxonomy-driven
- Effective Category (Automatic Category -> User Corrected Category -> Effective Category) is authoritative for review behavior
- grouping remains a review visualization aid and must not change underlying classification semantics

---

## Product Decision Rule

Before implementing any new feature, the AI must determine:

Which product domain owns this functionality?

If the functionality belongs to an existing domain, continue that domain.

Do not automatically create sequential DEV numbers.

---

## Relationship To Other Planning Documents

This document is the primary planning document.

- MASTER_DEVELOPMENT_PLAN.md defines what the product must become.
- DOMAIN_ROADMAP.md defines how future milestones are grouped by domain.
- PROJECT_STATE.md defines the current active domain, current milestone, and operational state.
- ROADMAP.md is retained as historical and transitional planning context.
