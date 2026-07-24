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
10. docs/project/MASTER_DEVELOPMENT_PLAN.md
11. docs/project/DOMAIN_ROADMAP.md
12. docs/project/ROADMAP.md (historical/transitional, if present)
13. docs/project/GLOSSARY.md
14. Any additional mandatory documents referenced by the documents above

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
10. docs/project/MASTER_DEVELOPMENT_PLAN.md
11. docs/project/DOMAIN_ROADMAP.md
12. docs/project/ROADMAP.md (historical/transitional, if present)
13. docs/project/GLOSSARY.md
14. Any additional mandatory documents referenced by the documents above

This document defines what must be read, in which order, and why the initialization sequence is mandatory.

docs/bootstrap/AI_BOOTSTRAP.md defines mandatory AI operating behavior.

docs/bootstrap/DOCUMENTATION_FRAMEWORK.md defines framework versioning and compatibility rules.

docs/bootstrap/COMMANDS.md defines how project commands work and what each command does.

The framework distinguishes between preparation commands (DOCSYNC) and verification commands (DOCVERIFY); see docs/bootstrap/COMMANDS.md for authoritative behavior.

This document must not duplicate command definitions; command behavior is owned only by docs/bootstrap/COMMANDS.md.

---

# Development Workflow

Historical implementation used the sequential milestone chain:

- DEV-001
- DEV-002
- DEV-003
- DEV-004
- DEV-005
- DEV-006

Future implementation uses domain-based development.

Whenever a new feature is requested, the AI must first determine the correct functional domain.

Never automatically continue with DEV-007, DEV-008, and later numbers as the default planning model.

Instead, create or continue work inside the appropriate domain defined in docs/project/MASTER_DEVELOPMENT_PLAN.md and docs/project/DOMAIN_ROADMAP.md.

---

## Product North Star

Family Memory AI is evolving into a Family Memory Intelligence system.

Its mission is:

"Help families preserve, organize and understand the memories that matter most, while continuously learning what is important for each family."

Future capabilities (Vacation Albums, Gift Albums, Story Timeline, and similar expansions) are intentionally postponed while keeping the architecture extensible.

---

## Current Development

DEV-001 (Annual Album Foundation) has been completed.

DEV-002 (Photo Intelligence Foundation) has been completed.

DEV-003 (Candidate Selection Engine) has been completed.

DEV-004 (Album Scoring Engine) has been completed.

DEV-005 (Hybrid Album Review UI) has been completed.

DEV-006 (Album Draft Builder) has been completed.

DEV-007 (Photo Cleanup & Relevance Engine) has been completed.

Current active domain and current milestone are defined in docs/project/PROJECT_STATE.md and docs/project/DOMAIN_ROADMAP.md.

For detailed operational status, always refer to docs/project/PROJECT_STATE.md.

Current status:

- PR #9 is completed and merged.
- PERF-004 staged loading baseline is complete (responsive import, deferred secondary workspace setup, asynchronous thumbnails).
- UX-001 is complete (reusable `WorkspaceInfoPanel`, collapsible panels, per-workspace persisted state, default expanded).
- Memory Review asynchronous loading/thumbnails bug fix is complete and manually validated.
- Current state should always be confirmed from docs/project/PROJECT_STATE.md before planning new implementation.

Next task:

Continue domain-based milestone execution from the stabilized baseline and follow the mandatory Product Owner manual validation gate before commit/push/PR approval/merge.

---

## First Actions for a New AI

- Complete the mandatory initialization workflow in the required order.
- Verify docs/project/PROJECT_STATE.md before proposing any work.
- Read docs/project/MASTER_DEVELOPMENT_PLAN.md before planning new work.
- Identify the correct functional domain before planning new implementation.
- Respect all approved decisions.
- Never change project direction without Product Owner approval.
- When working on photo scoring, album generation, duplicate detection, AI ranking, or album selection, always read docs/product/FAMILY_MEMORY_SCORE.md before making design decisions.

Before modifying Album Review, always read docs/product/FAMILY_MEMORY_SCORE.md because it contains the official product decisions.

Before making architecture decisions, read:

- docs/product/PRODUCT_VISION.md
- docs/product/FAMILY_MEMORY_SCORE.md

These documents define the product philosophy and take precedence over implementation details whenever design decisions are required.

When proposing AI features:

- Never optimize only for accuracy.
- Always preserve explainability and user trust.

## Permanent Response and Validation Rules

- Every Family Memory AI response must end with a clear Next Step section.
- Product Owner manual validation is mandatory before commit, push, PR approval, and merge.
- If manual validation fails, follow root-cause-first execution: diagnose, measure, identify root cause, implement targeted fix, retest.

---

## Single Source of Truth

Each information type has one official location. Reference these documents instead of duplicating their content:

- docs/project/PROJECT_STATE.md: current operational state
- docs/project/MASTER_DEVELOPMENT_PLAN.md: highest-level product planning and domain rule set
- docs/project/DOMAIN_ROADMAP.md: official domain roadmap and future capability structure
- docs/project/ROADMAP.md: historical and transitional planning context
- docs/releases/CHANGELOG.md: implementation history by sprint
- docs/development/DECISIONS.md: approved decisions
- docs/development/AI_PROJECT_PLAYBOOK.md: working method and sprint discipline
- docs/project/PROJECT_CONTEXT.md: long-term collaboration and development context

---

## Maintenance Note

If new mandatory project documents are introduced in the future, this reading order must be updated so that every new ChatGPT conversation starts with a complete and consistent project context.


## Current handover update — after MODEL-003C

As of 2026-07-22, PR #28 and PR #29 are merged. MODEL-002F is complete and manually validated; MODEL-003A persistent batch embedding foundation is complete and merged; MODEL-003B automatic import-time embedding generation is complete, merged, and manually validated; and MODEL-003C stored-vector semantic image similarity diagnostic is complete, merged, and manually validated. See `docs/project/PROJECT_STATE.md` for canonical current operational status and validation evidence.

Runtime boundary: start the main PySide6 application from the normal project `.venv` with `python src\main.py`. MobileCLIP does not run by importing torch/mobileclip in the main application environment. It runs through the Generic AI Runtime Manager's configured dedicated Python interpreter, selected and verified in Settings -> AI Models. The interpreter path comes from runtime configuration rather than a hard-coded environment path.

Validation handover: verify MobileCLIP through Settings -> AI Models, import an image folder, wait for the `[EmbeddingIndex]` summary, then run `python scripts\similar_images.py <source-image> <folder> --limit 10` against a source image that has already been embedded. Detailed observed evidence is kept in `docs/project/PROJECT_STATE.md` so this handover remains concise.

Current limits: production automatic category classification is not implemented; semantic similarity is available only through the developer diagnostic script, not the production UI; near-duplicate workflow, clustering, similar-photo UI, automatic category suggestions, semantic search UI, and learning from corrections remain future work. The next product milestone requires Product Owner selection among these possible consumers of semantic embeddings.
