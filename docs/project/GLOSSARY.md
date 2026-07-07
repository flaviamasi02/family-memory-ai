# Family Memory AI
## Project Glossary

This document defines the official terminology used throughout Family Memory AI.

Rules:
- Every technical document should use the terminology defined here.
- New project concepts should be added to this glossary.
- Existing definitions should not be duplicated in other documentation.
- AI assistants should always use these official terms.

---

## Structure

Every glossary entry must follow this format:

### Term
Definition

Purpose

Used By

Related Terms

Notes (optional)

---

## Product Concepts

### Family Memory AI
Definition:
Family Memory Intelligence platform focused on helping families preserve, organize, understand, and rediscover meaningful memories.

Purpose:
Represents the full product identity and scope.

Used By:
All product, architecture, and development documentation.

Related Terms:
Memory Intelligence, Annual Album, Photo Library, Memory Review

### Annual Album
Definition:
The year-scoped album artifact for Version 1.

Purpose:
Primary product outcome for curation and later export.

Used By:
PROJECT_STATE, ROADMAP, album domain modules.

Related Terms:
Candidate Photo, Selected Photo, Rejected Photo, Album Generation

### Photo Library
Definition:
The imported collection of photos available for processing and curation.

Purpose:
Source dataset for album generation.

Used By:
Import flow, Photo Browser, selection/scoring workflows.

Related Terms:
Import Pipeline, Candidate Photo

### Candidate Photo
Definition:
A photo eligible for evaluation in an annual album workflow.

Purpose:
Input set for deterministic selection/scoring.

Used By:
AnnualAlbum, Candidate Selection Engine.

Related Terms:
Selected Photo, Rejected Photo, Photo Intelligence

### Selected Photo
Definition:
A candidate photo accepted for inclusion in the album set.

Purpose:
Represents photos that pass current selection criteria.

Used By:
Candidate Selection Engine, future Scoring Engine.

Related Terms:
Candidate Photo, Rejected Photo

### Rejected Photo
Definition:
A candidate photo excluded by selection rules, with reason.

Purpose:
Ensures transparent exclusion and explainability.

Used By:
Candidate Selection Engine, diagnostics/review.

Related Terms:
Candidate Photo, Selected Photo

### Favorite Photo
Definition:
A user-designated high-value photo.

Purpose:
Future preference signal for prioritization.

Used By:
Future scoring and feedback workflows.

Related Terms:
Manual Feedback, Scoring Engine

### Photo Metadata
Definition:
Extracted file/image properties such as date_taken, dimensions, camera info.

Purpose:
Provides factual context for intelligence and selection.

Used By:
Metadata extractor, Photo model, details UI.

Related Terms:
Photo Intelligence, Import Pipeline

### Photo Intelligence
Definition:
Structured photo-level intelligence fields used by selection/scoring layers.

Purpose:
Stable schema between raw metadata and curation logic.

Used By:
Photo model, Candidate Selection Engine, future Scoring Engine.

Related Terms:
Photo Metadata, Candidate Selection Engine, Ranking

### Photo Browser
Definition:
The grid-based UI used to browse imported photos.

Purpose:
Primary interaction surface for visual navigation and selection.

Used By:
Main window UI and photo grid widgets.

Related Terms:
View, Widget, Details Panel, Thumbnail

### Details Panel
Definition:
Right-side UI panel showing information for the active photo.

Purpose:
Displays selection context and processing/metadata details.

Used By:
Main window and photo selection flow.

Related Terms:
Photo Browser, Selected Photo

### Thumbnail
Definition:
Scaled preview image representing a photo in the browser.

Purpose:
Fast visual browsing with reduced load/memory cost.

Used By:
Photo cards, cache, background thumbnail worker.

Related Terms:
Cache, Background Task

### Album Builder
Definition:
Component that groups photos by year and builds AnnualAlbum instances.

Purpose:
Initial annual album assembly before selection/scoring.

Used By:
album builder workflow and tests.

Related Terms:
Annual Album, Candidate Photo, Candidate Selection Engine

### Album Generation
Definition:
One of several possible output-generation processes built on top of broader memory understanding.

Purpose:
Defines one output pipeline from memory understanding to album-ready output.

Used By:
Roadmap, sprint planning, architecture.

Related Terms:
Album Builder, Memory Intelligence, Candidate Selection Engine, Scoring Engine

---

## AI Concepts

### Candidate Selection Engine
Definition:
Deterministic non-AI engine that evaluates candidate photos into selected/rejected.

Purpose:
Provides first explainable filtering layer.

Used By:
DEV-003 implementation and album workflow.

Related Terms:
Candidate Photo, Selected Photo, Rejected Photo

### Learning Engine
Definition:
Future subsystem that adapts behavior from user and system feedback.

Purpose:
Improve personalization over time.

Used By:
Future AI sprints.

Related Terms:
Manual Feedback, AI Feedback

### Scoring Engine
Definition:
Deterministic non-AI engine that assigns explainable scores to selected album candidates.

Purpose:
Prioritize photos for album composition.

Used By:
DEV-004 implementation and downstream review workflows.

Related Terms:
AlbumScoringEngine, Ranking, Photo Intelligence, Family Memory Score

### AlbumScoringEngine
Definition:
Implemented deterministic scoring component for annual album selected candidates.

### Explainable AI
Definition:
An AI approach where user-visible decisions can be understood through clear reasons, evidence, confidence, and decision source.

Purpose:
Preserve user trust while allowing AI-assisted behavior.

Used By:
Product vision, decision engine, learning and classification documentation.

Related Terms:
Decision Source, Transparent Decision, Human-in-the-loop

### Decision Source
Definition:
The origin of a decision outcome (for example deterministic rules, learned user preferences, AI inference, or hybrid decision).

Purpose:
Make decision provenance explicit and reviewable.

Used By:
Classification reasoning, review UI explainability, documentation.

Related Terms:
Explainable AI, Hybrid Classification

### Human-in-the-loop
Definition:
A product principle where the user remains the final decision authority and can review/correct automated suggestions.

Purpose:
Ensure user control and safe correction pathways.

Used By:
Memory Review, Cleanup Review, decision/learning workflows.

Related Terms:
User Decision Engine, Transparent Decision

### Transparent Decision
Definition:
A decision that exposes why it was made, what evidence was used, confidence, and source.

Purpose:
Enable trust, reviewability, and correction.

Used By:
Decision Engine, explainability UX, product principles.

Related Terms:
Explainable AI, Decision Source

### Hybrid Classification
Definition:
A classification approach that combines deterministic rules, learned user preferences, and AI inference in one explainable outcome.

Purpose:
Improve classification quality without losing transparency.

Used By:
LEARN domain and future classification architecture.

Related Terms:
Decision Source, Explainable AI, Preference Learning

Purpose:
Produce explainable score breakdowns (technical, memory, date, total) and deterministic ranking order.

Used By:
DEV-004 runtime flow and Album Review.

Related Terms:
Scoring Engine, Family Memory Score, Album Review

### Date Extraction Pipeline
Definition:
Deterministic date-resolution process used during import.

Purpose:
Populate reliable date context for selection, scoring, and review.

Used By:
BUG-001 implementation, Photo Intelligence synchronization, and candidate selection.

Related Terms:
DateExtractionService, Photo Metadata, Candidate Selection Engine

### DateExtractionService
Definition:
Component that resolves photo date values using prioritized sources.

Purpose:
Ensure robust date_taken/year/month/day extraction with source transparency.

Used By:
Import-time metadata processing and deterministic album pipeline.

Related Terms:
Date Extraction Pipeline, Photo Metadata, Photo Intelligence

### Album Review
Definition:
Hybrid UI step where scored candidates are reviewed and where future user decisions become long-term teaching signals. In the long-term product direction, this evolves into Memory Review.

Purpose:
Capture current review decisions and evolve into the central decision interface for future learning-oriented workflows.

Used By:
DEV-005 implementation, future Memory Review / User Decision Engine work, and Album Draft Builder inputs.

Related Terms:
AlbumScoringEngine, Album Draft Builder, Photo Decision, User Decision Engine, Selected Photo, Rejected Photo

### Memory Review
Definition:
The future evolution of Album Review as the main interaction point between the user and the Memory Intelligence system.

Purpose:
Turn review interactions into durable decision, cleanup, and preference-learning signals.

Used By:
Future User Decision Engine, Preference Learning, cleanup suggestions, and album-building improvements.

Related Terms:
Album Review, Photo Decision, User Decision Engine, Preference Learning

### User Decision
Definition:
Any meaningful user action that teaches the system how a memory should be interpreted, prioritized, or cleaned.

Purpose:
Provide learning signals for scoring, cleanup, duplicate handling, and future outputs.

Used By:
Memory Review, User Decision Engine, Preference Learning.

Related Terms:
Photo Decision, Decision Engine, Memory Review

### Photo Decision
Definition:
The long-term normalized user decision state assigned to a photo after review interaction.

Purpose:
Provide a stable decision vocabulary for album curation, cleanup, and future learning signals.

Used By:
Future User Decision Engine, Preference Learning, Album Review, and cleanup/recommendation workflows.

Related Terms:
Album Review, User Decision Engine, Preference Learning, Cleanup Category

### User Decision Engine
Definition:
Future architectural layer where user actions in Album Review are interpreted as durable product signals.

Purpose:
Transform review actions into preference-learning, cleanup, and recommendation inputs.

Used By:
Future scoring evolution, cleanup suggestions, and decision-aware album-building workflows.

Related Terms:
Photo Decision, Preference Learning, Album Review, Family Memory Score

### Decision Engine
Definition:
Future system layer that transforms user actions into normalized durable decisions.

Purpose:
Bridge interaction behavior and long-term memory intelligence behavior.

Used By:
Future Memory Review, cleanup workflows, duplicate handling, and recommendation systems.

Related Terms:
User Decision, User Decision Engine, Preference Learning

### Preference Learning
Definition:
Future process by which repeated user decisions influence scoring and recommendation behavior.

Purpose:
Help the application learn what matters to each family while preserving explainability.

Used By:
Future User Preference Score, Memory Value evolution, cleanup suggestions, and album recommendations.

Related Terms:
User Decision Engine, Photo Decision, Family Memory Score

### Preference Learning Engine
Definition:
Deterministic local engine that records user category corrections, memory decisions, and cleanup-oriented decisions as explainable preference signals.

Purpose:
Provide the foundation for future User Preference Score, recommendation, cleanup, and memory-intelligence personalization without cloud AI or black-box ML.

Used By:
Memory Review, Cleanup Review, future scoring and recommendation workflows.

Related Terms:
Preference Learning, User Decision, Photo Decision, User Decision Engine

### Memory Intelligence
Definition:
The broader system knowledge that models what matters to a family across memories, preferences, cleanup, duplicates, and outputs.

Purpose:
Provide reusable understanding that powers albums, stories, timelines, search, and recommendations.

Used By:
Future scoring, review, cleanup, album generation, storytelling, and output systems.

Related Terms:
Family Memory AI, Memory Review, Preference Learning, Album Generation

### Domain
Definition:
A functional development area that groups related capabilities and milestones.

Purpose:
Replace a purely sequential sprint model with capability-based planning.

Used By:
MASTER_DEVELOPMENT_PLAN, DOMAIN_ROADMAP, PROJECT_STATE, and future planning workflows.

Related Terms:
Milestone, Capability, Memory Intelligence

### Milestone
Definition:
A named implementation step inside a functional domain.

Purpose:
Provide precise progress tracking inside domain-based development.

Used By:
DOMAIN_ROADMAP, PROJECT_STATE, and implementation planning.

Related Terms:
Domain, Capability

### Capability
Definition:
A product or technical ability delivered by one or more domain milestones.

Purpose:
Describe what the system should be able to do independent of historical sprint numbering.

Used By:
Product vision, roadmap planning, and domain development.

Related Terms:
Domain, Milestone, Memory Intelligence

### Cleanup Category
Definition:
The normalized category used to mark non-album-relevant or cleanup-oriented media.

Purpose:
Support cleanup review, safe triage, and future decision-aware cleanup recommendations.

Used By:
Cleanup Review, cleanup engine behavior, and future User Decision Engine flows.

Related Terms:
Photo Decision, User Decision Engine, Photo Classification

### Cleanup Engine
Definition:
System layer responsible for classifying clutter, irrelevant media, and cleanup-oriented recommendations.

Purpose:
Support safe cleanup workflows and future learning-aware clutter reduction.

Used By:
Cleanup Review, cleanup classification, and future decision-driven cleanup suggestions.

Related Terms:
Cleanup Category, Memory Intelligence, Duplicate Engine

### Album Draft Builder
Definition:
Deterministic component that builds in-memory annual draft pages from reviewed/scored photos.

Purpose:
Create grouped monthly draft output with explicit inclusion/exclusion reasoning.

Used By:
DEV-006 implementation and upcoming draft UI workflows.

Related Terms:
Album Review, Annual Album, Family Memory Score, Album Generation

### Family Memory Score
Definition:
The explainable multi-factor scoring system used by Family Memory AI to rank photos.

Purpose:
Defines how ranking should prioritize meaningful memories over purely technical quality.

Used By:
Future scoring algorithms, ranking design decisions, and album curation specifications.

Related Terms:
Scoring Engine, Ranking, Memory Value Score, Album Balance

Reference:
../product/FAMILY_MEMORY_SCORE.md

### Ranking
Definition:
Ordered prioritization of photos based on scoring criteria.

Purpose:
Choose best candidates under album constraints.

Used By:
Future scoring and review workflows.

Related Terms:
Scoring Engine, Selected Photo

### Photo Classification
Definition:
Current review-time classification of media into explainable labels.

Purpose:
Support deterministic triage, cleanup, and user correction.

Used By:
Memory Review, Cleanup Review, import classification, learning workflows.

Related Terms:
Media Category, Cleanup Category, Learning Engine

### Media Category
Definition:
The normalized, user-correctable classification label assigned to imported media.

Purpose:
Provide the current review-time vocabulary for classifying media as Family Photo, Not Family Photo, Document, Screenshot, Meme / Graphic, Video, or Unknown.

Used By:
Memory Review, Cleanup Review, import classification, and learning workflows.

Related Terms:
Photo Classification, Cleanup Category, User Category, Grouping

Notes:
User-defined categories extend this taxonomy; they do not replace the stable internal IDs.

### User Category
Definition:
A user-created or user-renamed category used for organizing media without changing the underlying stable system IDs.

Purpose:
Allow families to tailor organization while preserving consistent internal references.

Used By:
Manage Categories, Memory Review, Cleanup Review, sidecar persistence.

Related Terms:
Media Category, System Category, Category Registry

### System Category
Definition:
A protected built-in category with a stable internal ID and configurable display and behavior properties.

Purpose:
Provide the fixed core taxonomy that user categories extend.

Used By:
Category management, import classification, Memory Review, Cleanup Review.

Related Terms:
Media Category, User Category, Category Registry

### Category Registry
Definition:
The local collection of system and user category definitions used by review and classification workflows.

Purpose:
Provide the editable taxonomy and the stable IDs behind it.

Used By:
Manage Categories, Memory Review, Cleanup Review, category loading, and persistence.

Related Terms:
System Category, User Category, Media Category

### Grouping
Definition:
A review-time visualization arrangement that clusters media for scanning and decision-making.

Purpose:
Improve human review speed without changing classification semantics.

Used By:
Cleanup Review and other grid-based review surfaces.

Related Terms:
Media Category, Cleanup Category, Thumbnail Grid

Notes:
Grouping is a visualization feature only and must not be treated as media classification.

### Manual Feedback
Definition:
Explicit user input (accept/reject/favorite) about photos or album choices.

Purpose:
Capture user intent and preferences.

Used By:
Future learning/scoring workflows.

Related Terms:
AI Feedback, Favorite Photo

### AI Feedback
Definition:
System-generated rationale or confidence outputs about photo decisions.

Purpose:
Improve transparency and model trust.

Used By:
Future explainability features.

Related Terms:
Scoring Engine, Ranking

### Future AI Features
Definition:
Approved but not yet implemented AI capabilities (for example recognition and advanced ranking).

Purpose:
Maintain roadmap clarity without premature implementation.

Used By:
ROADMAP and DECISIONS context.

Related Terms:
Learning Engine, Scoring Engine

---

## Architecture Concepts

### Model
Definition:
Data structure representing domain entities and their state.

Purpose:
Provide stable data contracts across layers.

Used By:
Photo, PhotoIntelligence, AnnualAlbum models.

Related Terms:
Service, Repository, View

### Service
Definition:
Business-logic component orchestrating domain operations.

Purpose:
Encapsulate use-case logic separate from UI.

Used By:
Current/future orchestration layers.

Related Terms:
Model, Repository

### Repository
Definition:
Persistence/data-access abstraction.

Purpose:
Isolate storage concerns from domain/UI logic.

Used By:
Future persistence architecture.

Related Terms:
Service, Cache

### UI Component
Definition:
Reusable user-interface building block.

Purpose:
Compose UI behavior with clear boundaries.

Used By:
MainWindow, details panel, photo card.

Related Terms:
View, Widget

### View
Definition:
UI layer representation of model data.

Purpose:
Render state and interactions without heavy business logic.

Used By:
Photo browser flows.

Related Terms:
Widget, UI Component

### Widget
Definition:
Qt UI object used to render and interact with interface elements.

Purpose:
Concrete UI implementation unit.

Used By:
PhotoGridWidget, PhotoCardWidget, Details Panel.

Related Terms:
View, UI Component

### Cache
Definition:
Stored reusable computed artifacts (for example thumbnails).

Purpose:
Reduce repeated computation and improve responsiveness.

Used By:
Thumbnail cache and image loading flow.

Related Terms:
Thumbnail, Background Task

### Background Task
Definition:
Non-UI threaded workload executed asynchronously.

Purpose:
Keep UI responsive during heavy operations.

Used By:
Thumbnail worker and future processing workers.

Related Terms:
Cache, Import Pipeline

### Import Pipeline
Definition:
Flow that scans folders, creates photo objects, and initializes browser state.

Purpose:
Ingest photos into application domain models.

Used By:
Photo scanner, model setup, thumbnail loading.

Related Terms:
Photo Library, Photo Metadata

---

## Development Concepts

### Sprint
Definition:
Focused development iteration with a single objective.

Purpose:
Deliver incremental value with clear scope.

Used By:
PROJECT_STATE, CHANGELOG, ROADMAP.

Related Terms:
Milestone, Definition of Done

### Milestone
Definition:
Higher-level checkpoint grouping multiple sprint outcomes.

Purpose:
Track strategic progress.

Used By:
ROADMAP and planning documents.

Related Terms:
Sprint

### Definition of Done
Definition:
Explicit completion criteria required before marking work complete.

Purpose:
Ensure quality and consistency.

Used By:
Sprint prompts, review processes.

Related Terms:
Sprint Review, Documentation Update

### Implementation
Definition:
Execution of approved technical work in code/docs/tests.

Purpose:
Turn decisions into functioning artifacts.

Used By:
All development sessions.

Related Terms:
Review, Refactoring

### Review
Definition:
Validation phase covering correctness, architecture, tests, and docs.

Purpose:
Catch regressions and improve quality.

Used By:
SPRINT REVIEW, code/doc QA.

Related Terms:
Definition of Done

### Refactoring
Definition:
Code structure improvement without changing intended behavior.

Purpose:
Improve maintainability and clarity.

Used By:
Architecture and quality maintenance.

Related Terms:
Implementation, Review

### Architecture Decision
Definition:
Approved decision with recorded rationale and impact.

Purpose:
Preserve long-term technical consistency.

Used By:
DECISIONS document and architecture governance.

Related Terms:
DECISION command, docs/development/DECISIONS.md

### Documentation Update
Definition:
Synchronized update of impacted project documents after changes.

Purpose:
Keep single-source-of-truth integrity.

Used By:
DOCSYNC workflows and sprint closeout.

Related Terms:
DOCSYNC, docs/project/PROJECT_STATE.md

---

## Documentation Concepts

### HANDOVER
Definition:
Session entry document for mandatory initialization workflow.

Purpose:
Ensure every conversation starts with consistent context.

Used By:
All new sessions.

Related Terms:
COMMANDS, PROJECT_STATE

### COMMANDS
Definition:
Authoritative command behavior reference.

Purpose:
Define operational commands and expected outputs/actions.

Used By:
ChatGPT command execution workflows.

Related Terms:
DOCSYNC, SPRINT START, STATUS

### PROJECT_CONTEXT
Definition:
Long-term product and collaboration context document.

Purpose:
Provide strategic and organizational background.

Used By:
Architecture and planning decisions.

Related Terms:
PROJECT_STATE, ROADMAP

### PROJECT_STATE
Definition:
Operational snapshot of current implementation and sprint status.

Purpose:
Track what is completed, current sprint, and pending priorities.

Used By:
Daily execution and status reporting.

Related Terms:
CHANGELOG, ROADMAP

### AI_PROJECT_PLAYBOOK
Definition:
Methodology for AI-assisted development workflow.

Purpose:
Define execution discipline and collaboration rules.

Used By:
All implementation sessions.

Related Terms:
HANDOVER, DECISIONS

### DECISIONS
Definition:
Decision ledger for approved architecture/product decisions.

Purpose:
Preserve decision history and impact mapping.

Used By:
Architecture governance.

Related Terms:
Architecture Decision, ROADMAP

### ROADMAP
Definition:
Planned future direction and sprint sequencing.

Purpose:
Guide medium/long-term implementation order.

Used By:
Planning and prioritization.

Related Terms:
PROJECT_STATE, Milestone

### DOCUMENTATION_ARCHITECTURE
Definition:
Map of documentation responsibilities, relationships, and reading order.

Purpose:
Keep documentation ecosystem coherent and navigable.

Used By:
Documentation design and synchronization.

Related Terms:
HANDOVER, COMMANDS

### DOCUMENTATION_FRAMEWORK
Definition:
Authoritative framework document that defines documentation versioning, compatibility, components, and upgrade policy.

Purpose:
Allow AI assistants and developers to verify documentation compatibility before implementation.

Used By:
Bootstrap initialization and documentation governance.

Related Terms:
HANDOVER, AI_BOOTSTRAP, DOCUMENTATION_ARCHITECTURE

### Documentation Framework Version
Definition:
Semantic version identifier for the documentation framework.

Purpose:
Provide a stable compatibility checkpoint across sessions and future framework upgrades.

Used By:
AI bootstrap and framework validation steps.

Related Terms:
DOCUMENTATION_FRAMEWORK, Compatibility

### Documentation Minimalism
Definition:
Governance principle that prefers extending existing documents over creating new files.

Purpose:
Prevent documentation sprawl while preserving clear ownership and long-term maintainability.

Used By:
Documentation architecture decisions and AI documentation proposals.

Related Terms:
Documentation is Production Code, DOCUMENTATION_ARCHITECTURE

### SYNC_QUEUE
Definition:
Queue of pending or tracked documentation synchronization items.

Purpose:
Avoid losing documentation tasks across sessions.

Used By:
DOCSYNC workflows.

Related Terms:
DOCSYNC PC, DOCSYNC MOBILE

### DOCSYNC
Definition:
Documentation synchronization command family.

Purpose:
Keep docs consistent after implementation or decision changes.

Used By:
DOCSYNC PC, DOCSYNC PC FULL, DOCSYNC MOBILE.

Related Terms:
Documentation Update, SYNC_QUEUE

---

## Command Concepts

### DOCSYNC PC
Definition:
Desktop documentation sync workflow command.

Purpose:
Apply regular documentation updates and consistency checks.

Used By:
Post-implementation sessions.

Related Terms:
DOCSYNC, SYNC_QUEUE

### DOCSYNC PC FULL
Definition:
Complete documentation audit and synchronization command.

Purpose:
Perform full integrity checks across mandatory docs.

Used By:
Major sprint closeouts or broad refactors.

Related Terms:
DOCSYNC PC, DOCUMENTATION_ARCHITECTURE

### Documentation Health Check
Definition:
Mandatory audit phase executed by DOCSYNC PC FULL.

Purpose:
Verify documentation completeness, consistency, ownership, quality, and AI readiness.

Used By:
DOCSYNC PC FULL governance workflow.

Related Terms:
DOCSYNC PC FULL, Documentation Update, DOCUMENTATION_ARCHITECTURE

### Command Grammar
Definition:
Official syntax model for project command composition.

Purpose:
Keep command invocation predictable, parseable, and backward compatible across sessions.

Used By:
COMMANDS authoring and command execution workflows.

Related Terms:
COMMANDS, DOCSYNC, SPRINT START

### DOCSYNC MOBILE
Definition:
Documentation synchronization workflow for mobile-originated changes.

Purpose:
Keep repository docs aligned with mobile decisions/work.

Used By:
Cross-device development process.

Related Terms:
DOCSYNC, SYNC_QUEUE

### HANDOVER
Definition:
Initialization command/workflow for new sessions.

Purpose:
Load mandatory context before handling project requests.

Used By:
Session start operations.

Related Terms:
COMMANDS, PROJECT_STATE

### SPRINT START
Definition:
Command to initialize implementation of current sprint.

Purpose:
Prepare architecture-aware implementation plan.

Used By:
Development sessions.

Related Terms:
Sprint, Definition of Done

### SPRINT REVIEW
Definition:
Command to assess quality of implementation outputs.

Purpose:
Review code, tests, architecture, and docs.

Used By:
Post-implementation validation.

Related Terms:
Review, Documentation Update

### STATUS
Definition:
Command that returns project status summary.

Purpose:
Provide concise operational visibility.

Used By:
Planning and synchronization.

Related Terms:
PROJECT_STATE, ROADMAP

### DOC REVIEW
Definition:
Command to review documentation quality and consistency.

Purpose:
Find inconsistencies, duplication, and stale content.

Used By:
Documentation maintenance sessions.

Related Terms:
DOCSYNC, DOCUMENTATION_ARCHITECTURE

### DECISION
Definition:
Command to register an approved new decision.

Purpose:
Update decision ledger and impacted references.

Used By:
Architecture governance workflows.

Related Terms:
DECISIONS, Architecture Decision

---

## Naming Conventions

Consistency is preferred over synonyms.

Always use:
- Photo Browser

Never:
- Gallery

Always use:
- Details Panel

Never:
- Inspector

Always use:
- Candidate Selection Engine

Never:
- Selection Module

Always use:
- Annual Album

Never:
- Year Album

---

## Adding New Terms

When a new concept appears:
1. Add the term to this glossary before broad architectural adoption.
2. Use the standard glossary structure.
3. Define ownership and related terms clearly.
4. Reference this glossary from affected documents when needed.
5. Avoid creating parallel definitions in multiple documents.

Every new project concept should be added here before becoming part of the architecture.

---

## AI Guidelines

AI assistants should:

- Always use official terminology.
- Avoid introducing synonyms.
- Avoid renaming existing concepts.
- Prefer extending this glossary instead of creating alternative names.

---

## Definition of Done

This glossary is the official vocabulary reference for Family Memory AI.
