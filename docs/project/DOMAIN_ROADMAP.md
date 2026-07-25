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

DEC-0049 platform rule: domain milestones target the Windows desktop application first while preserving reusable core boundaries for a later Android companion. Roadmap items must not assume parallel full desktop/mobile delivery, mandatory cloud upload, or a large mobile-preparation rewrite.

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
Review meaningful memories through category correction, AI teaching, preference learning, and classification validation.

Mission:
Teach the system what memories matter while preserving explainability and user context.

Example milestones:

- MEM-003 Multi-Select Bulk Category Editing (completed)
- MEM-004 Compact Memory Review thumbnail grid (completed)
- MEM-005 True multi-column Memory Review grid (completed)
- MEM-006 Memory Review UX polishing and keyboard workflow improvements
- MEM-010 Learning Transparency and Learning Inspector

MEM-010 direction:

- expose learned rules, learned preferences, learned signals, support count, confidence, explanation, date learned, and time learned in a non-technical view
- keep learning understandable to non-technical users
- surface a visible learning counter inside Memory Review

---

## CLEAN

Title:
Cleanup Engine

Purpose:
Detect irrelevant media.

Mission:
Safely identify clutter and cleanup-oriented media without permanent deletion.
Cleanup Review should follow the same UX philosophy as Memory Review: toolbar filters, compact thumbnail grid, and right-side explainable details.
Cleanup Review should also preserve scroll position and selection when filters or category changes remove the current item.

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
- Content categories, organizational categories, and workflow categories must be treated differently by future learning models.

Milestones:

- LEARN-001 Explainable Category Learning (completed)
Goal:
Learn from user corrections while remaining fully explainable.

- LEARN-002 Preference Learning and Aggregation Foundations (completed)
Goal:
Aggregate category corrections, user decisions, and cleanup-oriented decisions into local deterministic preference signals.

- LEARN-003 Hybrid AI Classification
Goal:
Combine deterministic rules, learned user preferences and AI inference into a single explainable decision while keeping visual evidence primary and metadata secondary.

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

Milestones:

- PEOPLE-001 Face Detection and Family Photo Classification (completed)
Goal:
Use local face detection as explainable Family Photo evidence without identity recognition.

- PEOPLE-002 Relationship Modeling
- PEOPLE-003 Importance Learning

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

- LEARN

## Current Milestone

- LEARN-002 Preference Learning and Aggregation Foundations (completed)

## Recently Completed Domains and Infrastructure

- FOUNDATION
- MEM (review UX and decision ergonomics foundation)
- CLEAN (deterministic classification and cleanup-review UX foundation)
- LEARN-002 Preference Learning and Aggregation Foundations
- TEST-001 PySide6 test environment and GitHub Actions test workflow setup

## Strategic Priority Order

1. Reliable AI-assisted media classification
2. Learning from user corrections
3. Cleanup quality and safety
4. People Intelligence
5. Output generation (albums as one downstream consumer)

## Future Planned Domains

- MEM
- LEARN
- DUP
- PEOPLE
- EVENT
- MEMORY
- OUTPUT

### LEARN-003.1 Visual Feature Extraction Foundation

Status: completed

Outcome:
- Introduced reusable local visual feature profiles for content-first learning evidence.
- Added deterministic visual feature extraction without cloud AI or black-box ML.
- Persisted visual feature profiles through backward-compatible sidecar metadata.
- Connected category learning to visual/content evidence while keeping metadata-only corrections non-generalized.
- Preserved app responsiveness by keeping extraction behind an explicit service boundary for future background batching.

## Learning Domain - LEARN-003.2

Content-based learning is the current learning-domain milestone. User category corrections teach the system from deterministic local visual features first; preference counts, filenames, and metadata remain secondary support. The milestone preserves local-only storage, no cloud image upload, no black-box model dependency, and background visual enrichment so review workflows stay responsive.

### MODEL-001 MobileCLIP local vision evaluation

The roadmap now follows a pretrained-model-first strategy: use a compact pretrained image/text model for general visual semantics, then let Family Memory AI learn personal meaning from corrections through embedding similarity.  MobileCLIP-S0 is the first CPU baseline provider; Florence-2 remains a possible future secondary provider.  Tags, subcategories, combined rules, and a bulk rule editor are intentionally deferred.

### MODEL-002A Generic AI Runtime Manager

Approved: optional local AI models are managed by a generic runtime registry and manager rather than MobileCLIP-specific UI or services. Current and future providers can register descriptors, dependencies, model files, capabilities, licenses, environment needs, and verification behavior without requiring runtime-manager UI rewrites.

MODEL-002A delivers architecture, MobileCLIP registration, Settings → AI Models visibility, installation-plan generation, metadata/history/benchmark persistence, and safe removal planning. SigLIP2, Florence-2, OCR, face recognition, and other local providers remain future registrations unless intentionally added. MODEL-002B implements the managed MobileCLIP installation and verification flow; Product Owner validation remains pending.

### MODEL-002B MobileCLIP managed installation

MODEL-002B turns MobileCLIP from a registered optional provider into the first real managed runtime. It keeps MODEL-002A's generic manager architecture, requires a dedicated Python environment, supports CPU-only installation, uses official Apple MobileCLIP code and `apple/MobileCLIP-S0`, stores weights outside Git, and requires explicit Product Owner confirmation plus full verification before Ready.

### MODEL-002C Product Owner-guided MobileCLIP validation

Status: next practical milestone.

Now:
- Validate managed MobileCLIP installation through Settings -> AI Models on the Product Owner CPU-only Windows computer.
- Confirm or fix AI Models metadata rendering after the observed blank MobileCLIP/provider fields.
- Verify runtime Ready only after dependency import, checkpoint load, provider construction, tokenizer creation, and finite embedding verification succeed.
- Run one-image real embedding, 10-image smoke test, and 100-image benchmark.
- Record actual CPU performance and any installation friction.

Not in scope yet:
- Replacing the production classifier.
- Claiming real classification quality or performance before measured evidence.

Later:
- Compare MobileCLIP against current visual learning.
- Explore zero-shot category suggestions.
- Integrate semantic embeddings into learning after evidence supports it.
- Evaluate Florence-2 as a possible second-stage model.
- Evaluate face recognition, OCR, object detection, and category/tag/subcategory/rule-system expansions.
- Migrate production classification only after measured evidence and explicit approval.

## MODEL roadmap update after MODEL-002E

Implementation complete:
- [x] MODEL-002A — Generic AI Runtime Manager foundation.
- [x] MODEL-002B — Managed MobileCLIP installation and runtime validation improvements.
- [x] MODEL-002C — Provider verification workflow.
- [x] MODEL-002D — Runtime diagnostics for AI Models metadata investigation.
- [x] MODEL-002E — Settings -> AI Models Qt layout sizing fix.

Merge history clarification:
- MODEL-002A and MODEL-002B merged in their original PRs.
- MODEL-002C, MODEL-002D, and MODEL-002E work was consolidated and merged through PR #22.
- PR #20 and PR #21 were closed without merge.

Validation state:
- [x] Repaired Settings -> AI Models UI manually validated on Windows.
- [x] Real MobileCLIP dependency installation through the app.
- [x] `mobileclip_s0.pt` checkpoint download through the confirmed flow.
- [x] Runtime Ready confirmation.
- [x] One-image embedding confirmation.
- [x] 10-image smoke test.
- [x] 100-image benchmark and real CPU timing/memory observations.
- [x] Persistence after restart.

Completed milestone:
- [x] MODEL-002F — Product Owner-guided MobileCLIP installation and operational validation.

Current MODEL-003 milestones:
- [x] MODEL-003A — Persistent batch image embeddings.
- [x] MODEL-003B — Automatic background embedding generation during import/index.
- [x] MODEL-003C — Reusable semantic image similarity service over stored embeddings.

MODEL-003C keeps the production classifier unchanged and adds a reusable non-UI service for future category suggestions, near-duplicate detection, semantic search, clustering, and learning from corrections. Automatic classification remains deferred until explicitly approved.

### MODEL-003D — Explainable Category Suggestions

- [x] MODEL-003D — Advisory category suggestions in Memory Review using stored semantic vectors and trusted existing labels.

MODEL-003D is intentionally advisory: it can propose at most one existing content category with heuristic confidence and evidence-based reasons, but no category changes occur without an explicit user click through the existing correction workflow. Manual categories remain authoritative, unreviewed machine labels are not trusted as strong evidence, and production automatic category replacement remains deferred.
