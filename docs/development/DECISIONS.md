# Family Memory AI - Decision Ledger

## Purpose

This document records all officially approved project decisions.

Every decision has a permanent DEC identifier.

---

## Decisions

### DEC-0001
Decision Sync Queue

Approved.

### DEC-0002
Documentation Sync Sprint

Approved.

### DEC-0003
Create docs/development/DECISIONS.md

Approved.

### DEC-0004
Create docs/development/SYNC_QUEUE.md

Approved.

### DEC-0005
Mobile Product Owner Mode

Approved.

### DEC-0006
Mobile Documentation First

Approved.

### DEC-0007
Mobile Documentation Repository

Approved.

### DEC-0008
docs/development/PROMPT_TEMPLATE.md

Approved.

### DEC-0009
docs/development/AI_PROJECT_PLAYBOOK.md

Approved.

### DEC-0010
Mobile Mode / Development Mode

Approved.

### DEC-0011
Repository Bootstrap Prompt

Approved.

### DEC-0012
Documentation Architecture

Approved.

### DEC-0013
Decision Ledger

Approved.

### DEC-0014
Documentation First Development

Approved.

### DEC-0016
Atomic Documentation Sync

Approved.

### DEC-0018
Documentation System

Approved.

### DEC-0019
Single Source of Truth

Approved.

### DEC-0022
Story Timeline Architecture

**Value:** Product  
**Impact:** Medium

Version 1 is **NOT** focused on Story Timeline. Story Timeline is an approved future capability. The application architecture must remain extensible so future album types can be added without major redesign.

**Impacted documents:**
- docs/project/PROJECT_CONTEXT.md
- docs/project/PROJECT_STATE.md
- docs/project/ROADMAP.md
- docs/bootstrap/HANDOVER.md

### DEC-0023
Decision Impact Matrix

**Value:** Method  
**Impact:** Low

Every approved decision must include:
- Decision ID
- Value (Product / Method / Both)
- Impact
- Documents to update
- Impacted sprints

### DEC-0024
Product North Star

**Value:** Product  
**Impact:** Low

Superseded by later product-direction updates in PRODUCT-DECISION-001 and PRODUCT-DOC-002.

Original decision:

> "Automatically create the best possible annual family photo album."

Current interpretation:

Annual album creation remains an important output, but the broader product mission now centers on Family Memory Intelligence: helping families preserve, organize, understand, and continuously teach the system what matters most.

Future album types including:
- Vacation Albums
- Gift Albums
- Event Albums
- Story Timeline

are approved future directions but are **NOT** part of Version 1.

The architecture should remain extensible.

**Impacted documents:**
- docs/project/PROJECT_CONTEXT.md
- docs/project/PROJECT_STATE.md
- docs/project/ROADMAP.md
- docs/bootstrap/HANDOVER.md

### DEC-0025
Print Ready Export

**Value:** Product  
**Impact:** Medium

Decision:

The final objective is to export a print-ready album for external printing providers (initial target: CEWE/Crew), while keeping the export engine provider-independent.

**Impacted documents:**
- docs/project/ROADMAP.md
- docs/project/PROJECT_STATE.md
- docs/bootstrap/HANDOVER.md
- docs/architecture/ARCHITECTURE.md

**Impacted Sprints:**
DEV-006 and DEV-007.

### DEC-0026
DOCSYNC Command

**Value:** Method  
**Impact:** Low

Decision:

Documentation synchronization is performed through DOCSYNC PC / DOCSYNC MOBILE commands.

**Impacted documents:**
- docs/bootstrap/HANDOVER.md
- docs/development/AI_PROJECT_PLAYBOOK.md
- docs/development/SYNC_QUEUE.md

**Impacted Sprints:**
Documentation sprints and end-of-sprint sync activity.

### DEC-0027
Photo Intelligence Foundation

**Value:** Product  
**Impact:** Medium

Decision:

Before implementing selection rules or AI ranking, the project will first build a Photo Intelligence model.

**Impacted documents:**
- docs/project/ROADMAP.md
- docs/project/PROJECT_STATE.md
- docs/bootstrap/HANDOVER.md

**Impacted Sprints:**
DEV-002 and later.

### DEC-0028
Documentation Structure Refactoring

**Value:** Both  
**Impact:** High

Decision:

Documentation was reorganized into a modular folder architecture under `docs/` to support long-term scalability, predictable navigation, and AI-friendly initialization across conversations and assistant types.

Expected benefits:

- clearer ownership boundaries per documentation domain
- lower duplication and easier synchronization
- faster initialization for humans and AI assistants
- safer future expansion without repeated structural migrations

Folder responsibilities:

- `docs/bootstrap/`: initialization and command references
- `docs/project/`: project context/state/planning/terminology
- `docs/development/`: methods, decisions, and doc governance
- `docs/architecture/`: technical architecture references
- `docs/testing/`: testing documentation artifacts
- `docs/releases/`: release and migration communication
- `docs/archive/`: preserved legacy snapshots

Backward compatibility considerations:

- all internal references must be migrated to new paths
- legacy root-level context/state docs are preserved in `docs/archive/`
- command and reading-order workflows must continue to resolve mandatory documents

**Impacted documents:**
- docs/bootstrap/HANDOVER.md
- docs/bootstrap/AI_BOOTSTRAP.md
- docs/bootstrap/COMMANDS.md
- docs/development/DOCUMENTATION_ARCHITECTURE.md
- docs/project/PROJECT_STATE.md

**Impacted Sprints:**
Post DEV-003 documentation refactoring activities.

### DEC-0029
Prompt Standards for Implementation Prompts

**Value:** Method  
**Impact:** Medium

Implementation prompts must include:

- Why We Test
- Manual Test Plan
- Acceptance Checklist

Testing must explain why the feature exists, how to test it manually, what persistence and regression checks matter, and what result qualifies as done.

**Impacted documents:**
- docs/development/PROMPT_TEMPLATE.md
- docs/development/AI_PROJECT_PLAYBOOK.md
- docs/project/PROJECT_CONTEXT.md

**Impacted Sprints:**
All future implementation prompts.

### DEC-0030
Memory Review Learning Focus

**Value:** Product  
**Impact:** High

Memory Review primarily exists to teach the AI.

Its future UI should focus on:

- media category correction
- AI teaching
- preference learning
- classification validation

Decision editing should move out of the Memory Review UI in a future milestone while preserving the underlying decision model.

**Impacted documents:**
- docs/project/PROJECT_STATE.md
- docs/project/PROJECT_CONTEXT.md
- docs/product/PRODUCT_VISION.md
- docs/product/FAMILY_MEMORY_SCORE.md

**Impacted Sprints:**
Memory Review UX and learning workflow milestones.

### DEC-0031
Learning Transparency and Learning Inspector

**Value:** Product  
**Impact:** Medium

Learning must be visible and understandable to users.

Future learning views should expose:

- learned rules
- learned preferences
- learned signals
- support count
- confidence
- explanation
- date learned
- time learned

**Impacted documents:**
- docs/project/PROJECT_STATE.md
- docs/project/PROJECT_CONTEXT.md
- docs/product/PRODUCT_VISION.md
- docs/product/FAMILY_MEMORY_SCORE.md
- docs/project/MASTER_DEVELOPMENT_PLAN.md
- docs/project/DOMAIN_ROADMAP.md
- docs/project/GLOSSARY.md

**Impacted Sprints:**
MEM learning transparency milestones.

### DEC-0032
Content-First Learning

**Value:** Product  
**Impact:** High

Preference learning must prioritize the visual content of an image.

Visual evidence comes first. Metadata is secondary support only.

Learning rules must not rely primarily on metadata such as filename, extension, EXIF, file size, or date source.

**Impacted documents:**
- docs/project/PROJECT_STATE.md
- docs/product/PRODUCT_VISION.md
- docs/product/FAMILY_MEMORY_SCORE.md
- docs/project/MASTER_DEVELOPMENT_PLAN.md
- docs/project/DOMAIN_ROADMAP.md
- docs/project/GLOSSARY.md

**Impacted Sprints:**
LEARN and CLEAN milestones that affect learning or classification.

### DEC-0033
Category Semantics

**Value:** Product  
**Impact:** High

The system must distinguish between category types:

- Content Categories
- Organizational Categories
- Workflow Categories

Workflow categories describe actions, not visual meaning, and must not learn visual rules.

**Impacted documents:**
- docs/project/PROJECT_STATE.md
- docs/product/PRODUCT_VISION.md
- docs/product/FAMILY_MEMORY_SCORE.md
- docs/project/MASTER_DEVELOPMENT_PLAN.md
- docs/project/DOMAIN_ROADMAP.md
- docs/project/GLOSSARY.md

**Impacted Sprints:**
MEM, LEARN, CLEAN, and future workflow milestones.

### DEC-0034
Memory Review UX Continuity

**Value:** Product  
**Impact:** Medium

Memory Review and Cleanup Review should preserve scroll position, selection, and user context during category corrections and filtering changes.

If the active photo disappears because of filtering, the workspace should remain at the same scroll position and select the next visible photo.

**Impacted documents:**
- docs/project/PROJECT_STATE.md
- docs/project/PROJECT_CONTEXT.md
- docs/product/PRODUCT_VISION.md
- docs/product/FAMILY_MEMORY_SCORE.md

**Impacted Sprints:**
Memory Review and Cleanup Review UX milestones.

### DEC-0035
Product Testing Workflow

**Value:** Method  
**Impact:** Medium

Every implementation cycle should follow:

Implementation -> Manual Test -> Product Owner Feedback -> Documentation Update -> Commit -> Push -> Next Sprint

Testing feedback is product design input and UX observations made during testing should be preserved as product decisions when appropriate.

**Impacted documents:**
- docs/project/PROJECT_CONTEXT.md
- docs/development/AI_PROJECT_PLAYBOOK.md
- docs/development/PROMPT_TEMPLATE.md

**Impacted Sprints:**
All future implementation cycles.

### DEC-0036
Official AI Collaboration Workflow

**Value:** Method
**Impact:** High

Family Memory AI adopts the following official AI-assisted development workflow:

Product Owner -> ChatGPT -> Implementation Prompt -> Codex -> Pull Request -> GitHub Actions -> ChatGPT Technical Review -> Product Owner Approval -> Merge.

Note: the permanent execution sequence was later refined by DEC-0045 and now ends with DOCSYNC after merge, with Product Owner manual validation gating commit/push/approval/merge.

This workflow formalizes repository health checks before implementation, focused pull request lifecycle rules, GitHub Actions root-cause analysis, human interaction expectations, Codex Cloud limitation handling, implementation prompt standards, Definition of Done requirements, user action guidance, and continuous workflow improvement.

Permanent rules:

- repository health comes before new implementation work;
- one implementation should map to one pull request;
- existing pull requests should be updated whenever possible;
- failed GitHub Actions must be inspected, root-caused, fixed, and re-run on the same pull request;
- AI assistants should use available repository, GitHub, pull request, and workflow capabilities before asking the Product Owner for logs or screenshots;
- Codex Cloud limitations must be stated honestly when remote git or GitHub verification is inaccessible;
- implementation prompts must follow the official prompt template;
- implementation is not complete until applicable Definition of Done conditions are satisfied;
- operational guidance to the Product Owner must end with a clear Next Step section;
- approved workflow improvements must be added to canonical documentation instead of scattered notes.

**Impacted documents:**
- docs/development/AI_PROJECT_PLAYBOOK.md
- docs/development/PROMPT_TEMPLATE.md
- docs/project/PROJECT_STATE.md
- docs/releases/CHANGELOG.md

**Impacted Sprints:**
All future implementation and documentation cycles.

### DEC-0037
Prompt Execution Environment Standard

**Value:** Method
**Impact:** Medium

Every implementation, bug-fix, documentation-sync, or Pull Request feedback prompt must explicitly state the Execution Environment before task details.

Approved execution environment labels:

- Codex Cloud
- Codex Local (VS Code)
- GitHub Copilot (PR Comment)

This prevents ambiguity about where work should be performed and whether the execution agent has cloud, local Windows, or Pull Request comment context.

**Impacted documents:**
- docs/development/PROMPT_TEMPLATE.md
- docs/development/AI_PROJECT_PLAYBOOK.md

**Impacted Sprints:**
All future implementation, debugging, review, and documentation-sync prompts.

### DEC-0038
Prompt Target Standard

**Value:** Method
**Impact:** Medium

Every implementation, bug-fix, documentation-sync, or Pull Request feedback prompt must explicitly state the Target before task details.

For new work, the prompt must state whether it is new implementation and whether a new branch or Pull Request is expected.

For existing Pull Request work, the prompt must state the Pull Request number and branch when known, and must explicitly say not to create a new Pull Request unless the Product Owner approves one.

**Impacted documents:**
- docs/development/PROMPT_TEMPLATE.md
- docs/development/AI_PROJECT_PLAYBOOK.md

**Impacted Sprints:**
All future implementation, debugging, review, and documentation-sync prompts.

### DEC-0039
ChatGPT Documentation Update Permission

**Value:** Method
**Impact:** Medium

ChatGPT may directly update repository documentation only after explicit Product Owner approval.

When approved, the update must stay within the approved documentation scope, preserve canonical ownership boundaries, avoid application source-code changes unless separately approved, and be committed as documentation-only work when a commit is requested.

Repository documentation is the permanent project memory and must remain synchronized with approved project state, decisions, workflow rules, and review outcomes.

**Impacted documents:**
- docs/development/AI_PROJECT_PLAYBOOK.md
- docs/development/PROMPT_TEMPLATE.md
- docs/bootstrap/HANDOVER.md

**Impacted Sprints:**
All future documentation-sync and project governance updates.

### DEC-0040
Official AI Execution Workflow Routing

**Value:** Method
**Impact:** High

Family Memory AI adopts the following official execution routing:

- New implementation -> Codex Cloud
- Local development/debug -> Codex Local (VS Code)
- Existing Pull Request improvements -> GitHub Copilot (PR Comment)

This routing keeps new implementation work focused, sends local Windows debugging to the local environment, and keeps existing Pull Request refinements attached to the active PR instead of creating unnecessary replacement PRs.

**Impacted documents:**
- docs/development/AI_PROJECT_PLAYBOOK.md
- docs/development/PROMPT_TEMPLATE.md
- docs/project/PROJECT_STATE.md
- docs/bootstrap/HANDOVER.md
- docs/releases/CHANGELOG.md

**Impacted Sprints:**
All future implementation, review, debugging, and PR-improvement cycles.

### DEC-0041
WorkspaceInfoPanel Reusable Intro Pattern

**Value:** Product
**Impact:** Medium

Approved UX-001 decisions:

- the reusable component name is `WorkspaceInfoPanel`;
- workspace introduction panels are collapsible;
- expanded/collapsed state is remembered separately per workspace using stable workspace identifiers;
- default state is expanded on first workspace use;
- no workflow progress/status indicator is included in the workspace introduction panel.

Scope constraints:

- persistence stores UI preference state only;
- no business workflow logic is moved into the component;
- existing Workspace Help remains active and separate from the compact panel.

**Impacted documents:**
- docs/project/PROJECT_STATE.md
- docs/releases/CHANGELOG.md
- docs/architecture/COMPONENTS.md

**Impacted Sprints:**
UX-001 and future workspace UX consistency updates.

### DEC-0042
Assistant Response Next Step Rule

**Value:** Method
**Impact:** Medium

For every Family Memory AI project response, the assistant must finish with a "Next Step" section.

The Next Step section must:

- provide concrete executable actions;
- avoid ambiguity;
- specify which tool should be used;
- include direct repository or PR/Issue links when GitHub actions are involved.

**Impacted documents:**
- docs/development/AI_PROJECT_PLAYBOOK.md
- docs/development/PROMPT_TEMPLATE.md

**Impacted Sprints:**
All future implementation, review, debugging, and documentation-sync cycles.

### DEC-0043
Mandatory Product Owner Validation Gate

**Value:** Method
**Impact:** High

Product Owner manual validation is mandatory before commit, push, PR approval, and merge.

Automated tests are required but never replace Product Owner validation.

**Impacted documents:**
- docs/development/AI_PROJECT_PLAYBOOK.md
- docs/development/PROMPT_TEMPLATE.md
- docs/project/PROJECT_CONTEXT.md

**Impacted Sprints:**
All future implementation and release cycles.

### DEC-0044
Root Cause First Rule

**Value:** Method
**Impact:** High

When manual validation fails, the mandatory fix sequence is:

1. diagnose
2. measure
3. identify root cause
4. implement targeted fix
5. retest

Speculative fixes must not be attempted first.

Temporary diagnostics should be removed after the targeted fix unless they provide long-term maintenance value.

**Impacted documents:**
- docs/development/AI_PROJECT_PLAYBOOK.md
- docs/development/PROMPT_TEMPLATE.md
- docs/project/PROJECT_CONTEXT.md

**Impacted Sprints:**
All future bug-fix and validation-failure cycles.

### DEC-0045
Permanent Development Workflow Sequence

**Value:** Method
**Impact:** High

Approved workflow sequence:

Implementation -> Product Owner Manual Test -> ChatGPT Review -> Commit -> Push -> Pull Request -> GitHub Actions -> Final ChatGPT Review -> Merge -> DOCSYNC.

**Impacted documents:**
- docs/development/AI_PROJECT_PLAYBOOK.md
- docs/development/PROMPT_TEMPLATE.md
- docs/project/PROJECT_CONTEXT.md
- docs/bootstrap/HANDOVER.md

**Impacted Sprints:**
All future implementation and documentation cycles.

### DEC-LEARN-0032
Content-first category learning is approved for LEARN-003.2. Visual evidence from local deterministic feature extraction is the primary learning evidence for category profiles. Metadata and filenames may support explanations but must not create strong learned visual rules on their own. Learning profiles use explicit schema versioning and local persistence; no cloud upload or black-box model training is introduced.

Approved.

## Decision: Stable app data and optional MobileCLIP provider

Learning profiles and ML artifacts must live outside the Git checkout in a platform-aware per-user application-data directory.  Repository-local `.familymemory` is legacy runtime data and is ignored by Git.  MobileCLIP integration uses a provider boundary so future checkpoints/providers can be added without rewriting the domain layer.  Model weights are never downloaded silently.

### DEC-0046
Generic AI Runtime Manager is the canonical local-model foundation.

**Value:** Both
**Impact:** High

Approved. Optional local AI providers must be registered and managed through the provider-agnostic AI Runtime Manager. Provider descriptors own capabilities, dependencies, model files, licenses, environment requirements, and verification hooks. Runtime UI should consume generic manager state rather than hard-coding provider-specific lifecycle behavior.

### DEC-0047
MobileCLIP Ready requires full verification.

**Value:** Product
**Impact:** High

Approved. MobileCLIP must not be treated as Ready solely because dependencies or checkpoint files exist. Ready requires import checks, checkpoint load, provider/model/transforms construction, tokenizer creation, and a finite embedding result.

### DEC-0048
AI Models metadata rendering bugs require layout diagnostics first.

**Value:** Method
**Impact:** Medium

Approved. If Settings -> AI Models metadata appears blank, future agents must inspect Qt widget hierarchy, row counts, size hints, geometry, visibility, and layout order before changing provider data or runtime verification logic. MODEL-002D/002E showed that valid label text can be hidden by layout sizing.

### DEC-0049
Desktop-First, Mobile-Ready Platform Strategy

**Value:** Both
**Impact:** High

Approved by the Product Owner on 2026-07-24. Family Memory AI is a reusable Family Memory platform whose primary and first client is the Windows desktop application. Planned Android and iOS applications are evolutions of the same product. The Windows desktop app remains the only active implementation target until the representative desktop workflow is validated; full desktop and mobile applications must not be built in parallel. New work must keep reusable business and domain logic independent from PySide6 wherever practical, prefer reusable services over UI-specific implementations, keep Windows-specific access behind platform boundaries, preserve portable or migratable persistence with stable identifiers, and avoid desktop-only architecture that would force a complete mobile redesign, mandatory cloud upload, or a large mobile-preparation rewrite.

Canonical detailed strategy: `docs/architecture/PLATFORM_STRATEGY.md`.

**Impacted documents:**
- docs/architecture/PLATFORM_STRATEGY.md
- docs/architecture/ARCHITECTURE.md
- docs/project/PROJECT_CONTEXT.md
- docs/project/PROJECT_STATE.md
- docs/project/MASTER_DEVELOPMENT_PLAN.md
- docs/project/DOMAIN_ROADMAP.md
- docs/development/AI_PROJECT_PLAYBOOK.md
- docs/bootstrap/HANDOVER.md
- docs/releases/CHANGELOG.md

**Impacted Sprints:**
All future implementation, architecture, planning, and documentation cycles.

### DEC-0050
Memory Review Workspace Presentation

**Value:** Product
**Impact:** Medium

Approved through the completed and merged UX-001 Memory Review Redesign:

- Memory Review uses a compact grouped toolbar above a balanced, resizable grid/workspace split.
- Preview and Current Status form one horizontal row; the preview receives the larger share while preserving image aspect ratio and orientation without cropping.
- The primary workspace hierarchy is Preview + Current Status, AI Suggestion, Classification Summary, and Actions.
- Photo Information and Technical Details are secondary, collapsed-by-default sections.
- The primary workflow must fit without vertical scrolling during normal maximized desktop use; detailed information remains available on demand.
- AI Suggestion explanations use adaptive word wrapping rather than nested scrolling.
- Styling uses the application palette and clear hierarchy. A richer project-wide colour/icon badge language is deliberately deferred to UX-002.
- The redesign must preserve MODEL-003D semantics and all existing classification, suggestion, persistence, sidecar, embedding, selection, filter, thumbnail, and action behavior.

**Impacted documents:**
- docs/architecture/UI.md
- docs/project/PROJECT_STATE.md
- docs/project/DOMAIN_ROADMAP.md
- docs/releases/CHANGELOG.md

**Impacted milestones:**
UX-001 Memory Review Redesign, UX-002, and UX-003.

### DEC-0051
MODEL-004 Face Recognition Uses Stable Domain Identity and Versioned Evidence

**Value:** Both
**Impact:** High

Approved by the MODEL-004A architecture specification. Face, Person, and FaceCluster are stable, platform-neutral domain identities. Bounding boxes, landmarks, confidence, quality, and provider provenance use portable values rather than AI-library objects. Face embeddings are versioned cache evidence separate from Face identity, permitting re-embedding, retraining, clustering changes, and profile learning without replacing manual names or assignments. Persistence lives in application data behind repository contracts and supports incremental upserts and explicit schema migration. PySide6, model installation, AI providers, and Memory Review presentation remain outside the domain and persistence layers.

MODEL-004A supplies contracts and inert placeholders only. It must not be described as face detection or recognition, and introduces no InsightFace, DeepFace, or face-recognition dependency.

Canonical detail: `docs/architecture/FACE_RECOGNITION.md`.

### DEC-0052
Central Metadata Storage and Original Photo Protection

**Value:** Both
**Impact:** High

Approved on 2026-07-27 for DATA-001. Each managed photo library will use one application-owned SQLite database named `family_memory.db`; separate databases for photos, embeddings, people, review, and albums are not approved. Logical scope includes Libraries, Photos, Embeddings, Categories, Review, Albums, Preferences, ImportHistory, Faces, and People. The exact physical schema may evolve during DATA-001 design, but the one-database-per-library decision is durable.

Metadata belongs under application-managed storage, with a platform-neutral equivalent of the Windows-primary shape `AppData/Local/FamilyMemoryAI/metadata/libraries/<LibraryID>/family_memory.db`; caches (including thumbnails and models) and logs remain separate application-managed concerns. Original images and folders must remain untouched and clean: no app-generated JSON or metadata beside photos and no image modification for metadata storage. Portable-project/export behavior must be explicit and user-controlled. The design must support multiple libraries and future backup/export and mobile synchronization without coupling the desktop implementation to a mobile application now.

DATA-001 planning must define an idempotent migration that detects existing app-generated JSON and sidecars, imports them without duplication, preserves user decisions and classifications, logs work and presents a summary, retains old metadata until success is confirmed, defines rollback/recovery, and keeps existing libraries compatible during transition. These are requirements, not unapproved implementation details.

DATA-001 precedes PERF-001 so centralized indexed storage is stable before semantic-embedding optimization. The approved decision is realised as an implementation contract in `docs/architecture/DATA_001_CENTRAL_METADATA_STORAGE.md`; that specification is ready for Product Owner review and does not mark implementation started.

**Impacted documents:**
- docs/project/PROJECT_STATE.md
- docs/project/ROADMAP.md
- docs/architecture/ARCHITECTURE.md
- docs/architecture/DATA_MODEL.md
- docs/development/AI_PROJECT_PLAYBOOK.md
- docs/releases/CHANGELOG.md

### DEC-0053
AUTO REVIEW MODE and ROOT CAUSE MODE

**Value:** Method
**Impact:** High

AUTO REVIEW MODE is the official PR-review workflow. ChatGPT reviews PR state and scope, Actions and failures, regression risk, and manual-validation evidence whenever the Product Owner supplies a PR link. Failed CI blocks merge. Green CI is necessary but insufficient: successful Product Owner manual validation is also required, and Product Owner validation remains the authoritative human gate. ChatGPT supplies the exact correction prompt when a correction is required. After merge, delete the branch, synchronize `main`, and update the roadmap.

ROOT CAUSE MODE activates automatically after more than two correction cycles on one PR. Incremental workarounds stop; the correction must identify and simplify the architectural cause, remove obsolete/redundant paths, prefer deterministic coordination for lifecycle complexity, and test the cause. Full CI and Product Owner manual validation remain mandatory.

GitHub `@codex` comments are not a reliable same-task continuation mechanism. Complex corrections use the existing Codex task as the authoritative channel, and correction prompts must require the existing PR and branch and prohibit new or follow-up PRs.

Canonical workflow detail: `docs/development/AI_PROJECT_PLAYBOOK.md`.

### DATA-001A implementation record — 2026-07-28

The approved bootstrap registry is the architecture-specified, atomically replaced `metadata/library_registry.json`, not a per-library sidecar. Library identity is canonical lowercase UUIDv4; database paths derive only from that ID. The minimal version-1 per-library SQLite foundation contains `schema_migrations` and `libraries`, and all access is behind a connection-per-work-unit `MetadataStore`. This implements DATA-001A infrastructure only: legacy JSON/sidecars and current caches remain authoritative, and DATA-001B–H remain planned. Product Owner manual validation is still required.

### DATA-001B implementation record — 2026-07-28

Schema version 2 is the complete DATA-001 foundation: all domain tables share the one managed `family_memory.db`; semantic and face vectors are constrained float32 little-endian BLOBs. Ordered migrations are checksum-verified, forward-only, individually transactional, and serialized with work units. Online backup, validated safety-copy restore, structured health reporting, and explicit non-destructive diagnostics are service responsibilities. DATA-001B does not connect import or migrate/cut over legacy content; DATA-001C–H remain planned and Product Owner validation is required.

### DEV-007 developer validation surface — 2026-08-01

DATA-001B manual validation is available through a collapsed Settings section using the existing application-composed storage services. It is read-only by default and exposes only explicit registration/open, health/schema inspection, online backup/validation, safe managed-folder opening, and a minimized clipboard report. There is no restore/delete/SQL console, scanning, import integration, or legacy migration. The CLI remains supported, while DATA-001C remains next.

### DATA-001C implementation record — 2026-08-01

Normal folder import now idempotently registers or reopens its library and records one durable import run. Stable UUIDv4 PhotoIDs, current file observations, and per-run outcomes are written through `PhotoRepository` and `MetadataStore` in a constant number of transactions using the scanner's existing result list; no second scan or eager hashing is introduced. Relative-path matches preserve identity across repeated imports and changed observations, while fingerprint/hash lookup and location history establish the conservative foundation for later rename/move policy. Schema version 3 records measured elapsed time. Existing JSON/sidecar, MobileCLIP, review, album, and embedding behavior remains unchanged; DATA-001D–H remain planned and Product Owner validation is required.
