# Family Memory AI Architecture

## Purpose

This document describes the technical architecture of Family Memory AI.

It is a living reference for the current implementation and the planned evolution of the system. As the project grows, this document should be updated to reflect new modules, responsibilities, and technical decisions.

---

# High Level Architecture

Family Memory AI is organized into several architectural layers that separate concerns and keep the application maintainable.

## 1. Presentation Layer

The presentation layer is responsible for displaying the user interface and handling user interaction.

It includes:

- windows and dialogs
- visual list and grid views
- user actions such as selecting folders, browsing photos, and overriding AI suggestions

This layer should remain focused on display and input, not on heavy computation.

## 2. Business Logic

The business logic layer contains the application rules and coordination logic.

It manages:

- photo collection behavior
- selection rules
- user workflow logic
- state transitions

This layer should decide what should happen, while the UI simply presents it.

## 3. Workers

Workers handle background processing so the UI remains responsive.

They are responsible for:

- scanning folders
- generating thumbnails
- preparing metadata
- running AI analysis in the background

Workers should not directly manipulate widgets.

## 4. Storage

The storage layer manages persistence and file access.

It may eventually provide:

- local file access
- metadata storage
- database-backed indexing
- cached results

This layer ensures that data can be recovered and reused efficiently.

## 5. AI

The AI layer contains computer vision and machine learning capabilities.

It may eventually support:

- face recognition
- duplicate detection
- quality analysis
- memory scoring
- natural language search

AI logic should be modular and isolated from the UI.

## 6. Future Cloud Integration

Cloud integration is a future consideration.

When introduced, it may support:

- remote backup
- cloud sync
- distributed processing
- advanced model inference

The architecture should allow this without forcing a rewrite of the desktop application.

---

# Folder Structure

## Current Folder Structure

```text
src/
  main.py
  core/
    photo_scanner.py
    metadata_extractor.py
  models/
    photo.py
    photo_model.py
  ui/
    main_window.py
    photo_card_widget.py
    photo_grid_widget.py
    photo_details_panel.py
    photo_grid_view.py
  workers/
    thumbnail_worker.py
  cache/
    thumbnail_cache.py
```

## Current Responsibilities

| Folder | Purpose |
| --- | --- |
| src/ | Main application source code |
| src/core/ | Scanning and metadata extraction helpers |
| src/models/ | Photo domain object and photo list model |
| src/ui/ | User interface components and windows |
| src/workers/ | Background processing tasks |
| src/cache/ | Caching logic and local temporary data |

## Planned Future Folder Structure

```text
src/
  ui/
  models/
  core/
  workers/
  cache/
  storage/
  ai/
  services/
```

## Why These Folders Exist

| Folder | Why it exists |
| --- | --- |
| ui/ | Keeps UI code separate from application logic |
| models/ | Defines the data structures used across the app |
| core/ | Holds shared logic, configuration, and orchestration |
| workers/ | Separates long-running tasks from the UI thread |
| cache/ | Improves responsiveness by storing computed results |
| storage/ | Centralizes persistence and file access |
| ai/ | Isolates machine learning and vision logic |
| services/ | Provides high-level application features such as search and curation |

---

# Main Components

## MainWindow

MainWindow is the primary application window.

It is responsible for:

- launching the UI
- coordinating views
- connecting user actions to services and workers
- presenting application state

It should not contain heavy image processing logic itself.

Current orchestration behavior includes staged import flow:

- Phase 1: immediate Photo Browser setup with placeholder cards;
- Phase 2: asynchronous thumbnail worker start;
- Phase 3: deferred secondary workspace preparation (Cleanup Review then Memory Review).

This keeps the UI responsive during large imports and avoids blocking secondary workspace setup.

## PhotoGridWidget

PhotoGridWidget is the current custom card grid used to display photos.

It is responsible for:

- rendering an initial batch of card widgets before the full collection
- adding more card widgets in small batches as the user scrolls
- handling photo card selection events
- applying deferred thumbnail updates safely
- supporting progressive loading in a scrollable container

It should depend on models and data providers rather than performing processing directly.

## PhotoGridView (Legacy Foundation)

PhotoGridView remains as an earlier model/view foundation artifact and is not the primary runtime grid in the current UI flow.

## Photo

Photo represents an individual image in the application.

It may contain:

- file path
- metadata
- thumbnail status
- AI analysis results
- memory-related attributes

This object should be a simple data representation.

## PhotoModel

PhotoModel is the data layer for photo collection management.

It is responsible for:

- holding photo data
- exposing photo collections to the UI
- tracking loading and selection state
- coordinating updates based on worker results

It acts as a bridge between storage and presentation.

## ThumbnailWorker

ThumbnailWorker generates and prepares thumbnails in the background.

It is responsible for:

- checking the existing versioned thumbnail cache before regenerating work
- reading image files when no valid cached thumbnail exists
- generating thumbnails in the background
- storing results in the cache
- notifying the application when cached or generated thumbnails are ready

## ThumbnailCache

ThumbnailCache stores generated thumbnails for reuse.

It is responsible for:

- avoiding repeated thumbnail computation
- improving startup and browse performance
- keeping memory and disk usage controlled

## PhotoScanner

PhotoScanner discovers photos from local folders.

It is responsible for:

- walking directories
- finding image files
- creating Photo objects
- passing discovered files to the rest of the system

## AnnualAlbum

AnnualAlbum is the Version 1 album domain container for one target year.

It is responsible for:

- storing year-scoped album collections
- tracking photos, candidate_photos, selected_photos, and rejected_photos
- exposing a simple status field for album workflow state

It does not perform selection/scoring logic by itself.

## PhotoIntelligence

PhotoIntelligence is a structured placeholder model attached to each Photo.

It is responsible for:

- storing normalized intelligence fields (basic metadata context, quality placeholders, people placeholders, duplicate placeholders, album placeholders, and AI placeholders)
- providing a stable schema for future candidate selection and scoring engines
- allowing safe initialization when metadata is missing

Current implementation includes metadata-driven year/month/date initialization when available.

## AlbumBuilder

AlbumBuilder is the first annual album orchestration helper.

It is responsible for:

- grouping photos by year
- creating an AnnualAlbum for a selected year
- initializing candidate_photos from matching-year photos

Current behavior is deterministic and foundational; it does not yet implement full candidate selection or ranking.

## CandidateSelectionEngine

CandidateSelectionEngine is the first deterministic selection step between yearly candidate pools and selected album sets.

It is responsible for:

- evaluating AnnualAlbum.candidate_photos using explicit non-AI rules
- populating AnnualAlbum.selected_photos and AnnualAlbum.rejected_photos
- preserving candidate_photos as the original candidate pool
- recording clear rejection reasons for traceable decisions

A lightweight CandidateSelectionResult summarizes counts and rejection reason totals for verification and testing.

## DateExtractionService

DateExtractionService is the deterministic date-resolution component used during import.

It is responsible for:

- resolving photo date context using a strict priority order
- populating date_taken/year/month/day and date source context
- enabling stable year-aware candidate selection and review summaries

Priority order:

- EXIF DateTimeOriginal
- EXIF CreateDate
- other EXIF date fields
- filename parsing (including WhatsApp/IMG/PXL/Screenshot/VID patterns)
- filesystem timestamps

## AlbumScoringEngine

AlbumScoringEngine is the deterministic non-AI scoring component for selected annual album candidates.

It is responsible for:

- scoring AnnualAlbum.selected_photos only
- producing explainable technical, memory, and date score breakdowns
- sorting scored candidates by total score for downstream review
- persisting the resulting candidate score for deterministic workflows

## AlbumReviewPage

AlbumReviewPage is the current hybrid review UI for scored annual album candidates and the precursor to future Memory Review.

It is responsible for:

- top toolbar controls (search, filters, sorting)
- central thumbnail-grid review experience
- right-side details panel with preview and score explanations
- in-memory review state transitions (approve, reject, pending)

In the long-term product direction, this interaction surface evolves into Memory Review: the main point where users teach the system what matters.

Current Memory Review loading behavior includes:

- asynchronous thumbnail synchronization compatible with deferred row/card creation;
- retained thumbnail cache keyed by normalized photo path;
- deterministic pipeline rendering with clear empty-state reasons when no usable date-year buckets are available.

## WorkspaceInfoPanel

WorkspaceInfoPanel is a reusable compact introduction card rendered near the top of each main workspace.

It is responsible for:

- concise workspace orientation (purpose, typical actions, tip);
- collapsible presentation to recover vertical space;
- per-workspace expanded/collapsed persistence with default expanded state.

WorkspaceInfoPanel does not replace contextual Workspace Help and does not include workflow progress indicators.

## AlbumDraftBuilder

AlbumDraftBuilder is the deterministic draft assembly component that follows current review flows.

It is responsible for:

- including approved photos and excluding rejected photos
- using pending photos only as deterministic fallback when no approved photos exist
- enforcing deterministic draft-size limits
- sorting included photos deterministically by date then score
- grouping pages by month with an Undated Memories fallback page
- returning draft build counters, exclusion reasons, and explanations

## Relationship Summary

- Photo objects are the core item-level entities.
- PhotoIntelligence is attached to Photo as structured intelligence state.
- DateExtractionService resolves deterministic date context at import time.
- AlbumBuilder reads Photo and PhotoIntelligence date context to group and assemble albums.
- CandidateSelectionEngine evaluates AnnualAlbum candidate pools using PhotoIntelligence year when available and safe metadata fallback.
- AlbumScoringEngine scores selected candidates with explainable non-AI breakdowns.
- AlbumReviewPage captures in-memory review decisions over scored candidates and provides the future bridge toward Memory Review.
- AlbumDraftBuilder builds deterministic in-memory album drafts from reviewed/scored candidates.
- AnnualAlbum stores the year-scoped album state used by the deterministic curation flow.

## Long-Term Memory Intelligence Pipeline

The long-term product-direction pipeline is:

Import
-> Metadata Extraction
-> Classification
-> Technical Analysis
-> Scoring
-> Memory Review
-> Decision Engine
-> Preference Learning
-> Cleanup
-> Duplicate Management
-> Memory Intelligence
-> Album Builder
-> Album Refinement
-> Outputs

Current deterministic album flow remains an early implementation subset of this broader pipeline.

---

# Knowledge First Architecture

## Official Long-Term Vision

Knowledge First Architecture is the official long-term architectural direction for Family Memory AI.

The central principle is:

The AI should first understand a photo and build knowledge about it. Categories, scores, and recommendations are results of that knowledge — not the starting point.

## Conceptual Flow

The Knowledge First Architecture replaces the simple Photo → Category flow with:

```text
Photo
↓
AI Analysis
↓
Knowledge Database
↓
Memory Review          Cleanup Review
↓
AI Learning
↓
Better Recommendations
```

## What This Means

- **Photo → AI Analysis**: When a photo is imported, the AI analyzes it to build a structured knowledge representation. This includes understanding content, faces, context, quality, and relevance signals.
- **AI Analysis → Knowledge Database**: The AI stores its understanding in a persistent Knowledge Database. This knowledge is the foundation for all downstream decisions.
- **Knowledge Database → Memory Review / Cleanup Review**: Both review workspaces operate on the same underlying knowledge. They are different views with different goals, not separate systems.
- **Memory Review / Cleanup Review → AI Learning**: User decisions in both workspaces feed back into the AI as learning signals. The system becomes more accurate over time.
- **AI Learning → Better Recommendations**: Accumulated knowledge and user feedback improve ranking, categorization, cleanup suggestions, and memory outputs.

## Categories Are Not the First AI Decision

Under Knowledge First Architecture, categories are not the AI's first decision.

The AI first understands the photo. Categories become one result of that understanding.

This distinction is important: a category is a label attached to knowledge, not a substitute for it.

## Why This Architecture

- Knowledge accumulates over time rather than being computed on demand.
- Both Memory Review and Cleanup Review share the same knowledge source.
- AI improvements benefit all workspaces simultaneously.
- User feedback from any workspace enriches the shared knowledge base.
- Future capabilities (search, timeline, stories) build on knowledge rather than re-classifying from scratch.

## Status

Knowledge First Architecture is the official long-term direction for Family Memory AI.

Current implementation is a deterministic early subset working toward this architecture.

---

# Workspace Help Architecture

## Purpose

The Workspace Help System is a permanent architectural component of Family Memory AI.

Its purpose is to provide contextual, workspace-specific guidance to users without requiring them to leave their current workflow.

## Design Principles

- **Help is separated from the UI**: Help content is defined in dedicated data models, not embedded in UI widget logic. This separation keeps UI components focused and makes Help easy to update independently.
- **Help is data-driven**: Workspaces provide Help definitions as structured data. The panel renders them. This allows Help to evolve without touching UI rendering code.
- **Help must evolve with the product**: Every user-facing change that affects how a workspace works must include a corresponding Help update. Help is not a one-time document.

## Implementation Components

| Component | Location | Purpose |
| --- | --- | --- |
| WorkspaceHelpPanel | `src/ui/components/workspace_help_panel.py` | Reusable dock panel that renders Help content |
| WorkspaceHeader | `src/ui/components/workspace_header.py` | Title row with Help action trigger |
| WorkspaceHelpModels | `src/ui/help/workspace_help_models.py` | Typed Help data models |
| WorkspaceHelpRegistry | `src/ui/help/workspace_help_registry.py` | Maps workspace IDs to Help definitions |
| WorkspaceHelpContent | `src/ui/help/workspace_help_content.py` | All workspace Help definitions |

## Supported Help Section Kinds

| Section Kind | Purpose |
| --- | --- |
| Purpose | Explains what the workspace does and why it exists |
| Workflow | Step-by-step guidance on how to use the workspace |
| Best Practices | Recommendations for effective use |
| Tips | Short practical tips and keyboard shortcuts |
| AI Status | Describes current AI capabilities and limitations in this workspace |

## Developer Guide: Adding a New Workspace Help Page

Adding Help for a new workspace requires four steps:

### Step 1: Define the Help content

Add a new `WorkspaceHelpDefinition` entry in `src/ui/help/workspace_help_content.py`.

Each definition must include at minimum:

- A unique workspace ID string.
- A `Purpose` section explaining what the workspace does, why it exists, and when it should be used.
- A `Workflow` section explaining how the user should use it.
- An `AI Status` section describing what the AI does automatically and what is expected from the user.
- A `Best Practices` section.
- A `Tips` section.

### Step 2: Register the workspace ID

Ensure the workspace ID is registered in `src/ui/help/workspace_help_registry.py` so the Help panel can look it up at runtime.

### Step 3: Connect the workspace header

In the workspace widget, use `WorkspaceHeader` and connect its help action signal to emit the workspace ID.

### Step 4: Connect to main-window tab mapping

Ensure the main window tab-to-workspace ID mapping includes the new workspace so Help updates automatically when the user switches tabs.

## Why Help Is Separated from the UI

Keeping Help definitions separate from UI rendering code provides three long-term benefits:

1. UI refactoring does not break Help content.
2. Help can be reviewed and updated without touching UI widget logic.
3. Future export, search, or translation of Help content is straightforward.

## Why the Help System Is Designed to Evolve

The Help system uses a section-kind renderer pattern. The panel renders sections by kind, not by position. This means:

- New section kinds can be added without changing existing workspace Help definitions.
- Existing workspace Help definitions continue working after new section kinds are introduced.
- Help can grow in structured richness over time as the product matures.

---

## Future Database

A future database will provide structured persistence for metadata and relationships.

It may store:

- photo metadata
- face references
- albums
- events
- user preferences

## Future AI Engine

The future AI engine will manage image analysis and model execution.

It will provide:

- prediction services
- feature extraction
- scoring and ranking

## Future Services

Future services will provide high-level capabilities such as:

- memory curation
- album generation
- cleanup and clutter reduction
- duplicate management
- search
- recommendation

Album generation is treated as one consumer of Memory Intelligence rather than the sole center of the product.

These services should coordinate lower-level components without embedding UI behavior.

---

# Data Flow

A photo moves through the application in a clear sequence.

```text
User selects folder
↓
PhotoScanner
↓
Photo objects
↓
PhotoModel
↓
ThumbnailWorker
↓
Thumbnail Cache
↓
PhotoGridView
↓
User
```

## Flow Description

1. The user selects a folder.
2. The scanner discovers image files.
3. Photo objects are created from those files.
4. The model stores and exposes the photo collection.
5. The thumbnail worker generates previews in the background.
6. The cache stores those thumbnails for reuse.
7. The grid view displays the results to the user.
8. The user can interact with the displayed memories immediately.

---

# Threading Model

The application should be designed around a responsive threading model.

## UI Thread

The UI thread handles:

- window rendering
- user input
- basic view updates

It must remain responsive at all times.

## Background Workers

Background workers are used for:

- scanning folders
- generating thumbnails
- loading metadata
- performing non-UI tasks

## Future AI Workers

Future AI workers will handle:

- face detection
- duplicate analysis
- quality scoring
- other heavy inference tasks

## Future Metadata Workers

Future metadata workers will process:

- EXIF data
- event extraction
- indexing
- related metadata enrichment

## Rule

Never block the UI thread.

---

# Performance Strategy

The architecture must support large libraries of photos without becoming slow or unstable.

## Target

- 50,000 photos

## Performance Techniques

### Lazy Loading

Only load photo data when it is needed.

This prevents unnecessary memory use and speeds up initial startup.

### Virtual Scrolling

Render only the visible portion of the photo collection.

This keeps large galleries responsive.

### Thumbnail Cache

Store generated thumbnails so the same images do not need to be recomputed repeatedly.

### Metadata Cache

Cache extracted metadata to avoid repeated file reads and expensive parsing.

### Database Indexing

A future database should support fast search and retrieval.

### Background Processing

Heavy tasks should run in workers so the UI remains interactive.

These techniques are essential for keeping the experience fluid as the collection grows.

---

# Future AI Architecture

The future AI system should be modular and explainable.

## Planned Modules

### Face Recognition

Identifies people in photos and links images to known individuals.

### Smile Detection

Detects smiling expressions and can support preference-based ranking.

### Blur Detection

Identifies images that are too blurry to be valuable.

### Duplicate Detection

Detects repeated or near-duplicate images.

### Memory Score

Assigns a score based on emotional and historical value rather than only technical quality.

### Preference Learning

Learns user preferences over time to improve suggestions.

### Album Generator

Creates albums automatically based on events, people, and time.

### Natural Language Search

Allows users to search memories using natural language such as "best memories of 2023".

These modules should be independent enough to be upgraded or replaced over time.

---

# Scalability Principles

The architecture should scale without major rewrites by keeping responsibilities separated and interfaces stable.

## Principles

- Introduce abstractions where they add long-term value.
- Keep the UI independent from AI and storage details.
- Add worker-based processing as scale increases.
- Use caching to avoid repeated expensive work.
- Plan for database-backed indexing from the start.
- Prefer incremental expansion over architectural overhauls.

---

# Architecture Rules

The architecture should follow a small set of clear principles.

- Single Responsibility
- Loose coupling
- High cohesion
- Avoid circular dependencies
- UI never performs AI work directly
- Workers never manipulate widgets
- Model stores data
- View displays data

Architecture should always optimize maintainability before complexity.

## Content-Based Learning Architecture

LEARN-003.2 keeps learning responsibilities separated. UI review pages record authoritative user corrections and return immediately. `CategoryLearningEngine` owns persistent category visual profiles, idempotent correction event handling, conservative thresholds, pending visual-analysis records, and explainable visual-content rules. `VisualFeatureExtractionService` remains the deterministic local pixel-analysis boundary and persists completed profiles through existing sidecar metadata rather than original photo files. Recommendation integration combines deterministic classifier output with learned visual profile matches conservatively; filename and metadata evidence are secondary and cannot create high-confidence visual rules alone.

## MODEL-001 MobileCLIP Local Vision Foundation

Family Memory AI now treats pretrained vision models as optional local providers behind a `VisionEmbeddingProvider` boundary.  The production classifier is not replaced by this milestone: MobileCLIP is evaluation-only until Product Owner validation confirms speed and quality on the target Windows CPU-only machine.

The selected first checkpoint is `apple/MobileCLIP-S0` from the official Apple Hugging Face/GitHub release.  It is the smallest practical official MobileCLIP candidate currently documented for image/text embeddings, uses the Apple ML Research Model Terms for weights and MIT for the official code, has a 216 MB PyTorch checkpoint, and produces 512-dimensional normalized embeddings.  Its Apple/mobile latency claims are not used as Windows performance claims; the evaluation report records measured local CPU timings.

Photo analysis remains local.  The base app imports and starts without `torch`, `torchvision`, `mobileclip`, network access, or model weights.  Model download is explicit and is never triggered by app startup, photo import, or settings inspection.  Embeddings are stored in per-user application data, not beside original photos and not inside source images.

Embedding persistence uses SQLite under the stable application-data cache.  Records include a stable resolved path key, source fingerprint, size and mtime invalidation data, provider/checkpoint/revision, embedding dimension, normalized embedding, timestamp, and status/error.  SQLite was chosen instead of one large JSON file so the cache can grow toward 50,000 photos without repeatedly rewriting all records.

## Generic AI Runtime Manager

The `ai_runtime` package is the canonical architecture for optional local AI providers. Providers register an `AIRuntimeDescriptor` with stable ID, display metadata, type, checkpoint/revision, capabilities, source, code/model licenses, expected size, supported devices, Python dependencies, required model files, provider factory, and verifier. The registry supports future providers without Settings UI rewrites and does not import heavy ML packages at app startup.

`AIRuntimeManager` performs deterministic status checks: Ready requires importable dependencies, registered model files in the managed cache, matching metadata, and provider verification. It generates structured installation and removal plans made of typed actions; UI code does not execute arbitrary shell strings. Install execution requires explicit plan confirmation and uses `AIRuntimeCommandExecutor` with argv tokens, active interpreter visibility, bounded output, timeout, cancellation, and structured results.

Runtime metadata is stored through `ApplicationDataPathService` outside the repository under `ai-runtimes/`, `cache/models/<provider>/`, and `logs/ai-runtime/`. JSON writes are atomic, schema-versioned, and corruption-safe. Removal plans delete only manager-owned paths with ownership markers and never delete photos, thumbnails, categories, learning profiles, or semantic embeddings unless a future explicit embedding cleanup option is approved.

## MODEL-002B Managed Runtime Installation Flow

MobileCLIP installation now uses the same `AIRuntimeManager` architecture introduced in MODEL-002A. The manager validates the selected Python interpreter, builds a typed plan, executes only confirmed actions, downloads the checkpoint to a temporary partial file before atomic rename, and records history/status outside Git. Verification is performed in the selected interpreter and requires torch, torchvision, Pillow, mobileclip, checkpoint presence/load, model/transforms, tokenizer, and a finite synthetic image embedding before the runtime becomes Ready.

## AI Runtime Safety and Storage Rules

Permanent runtime rules:
- Photo processing remains local; photos are not uploaded and originals are never modified.
- Optional AI models must not be downloaded silently, and dependencies must not be installed silently.
- Product Owner confirmation is required before installation, checkpoint download, verification actions that depend on installed model files, or removal.
- Long-running AI operations run outside the Qt UI thread.
- The base app works without optional AI models, model weights, torch, torchvision, or mobileclip installed.
- Runtime metadata and model files use application-data locations outside the Git repository.
- Virtual environments, AI model files, user profiles, and learning data must not be committed.
- Model removal may remove manager-owned model files only; it must never delete photos, thumbnails, categories, or learning profiles.
- Shared Python packages are not silently removed.
- Automated tests must not install packages or download real models.

Current environment strategy:
- Main app: `C:\Projects\family-memory-ai\.venv`.
- MobileCLIP runtime: `C:\Projects\family-memory-ai\.venv-mobileclip`.
- MobileCLIP target: Python 3.10, 64-bit, CPU-only, explicit selected interpreter, no shell-activation dependency, and package commands using `python.exe -m pip ...`.


## Current AI Runtime Architecture

The current optional local-model architecture is provider-agnostic. `src/ai_runtime/registry.py` stores provider descriptors; `src/ai_runtime/manager.py` coordinates environment inspection, status, installation plans, verification, diagnostics, history, benchmarks, and safe removal; `src/ai_runtime/storage.py` persists runtime records under app-data locations outside Git; and `src/workers/ai_runtime_worker.py` runs long operations off the Qt UI thread.

MobileCLIP is registered in `src/ai_runtime/mobileclip_registration.py` as the first provider with image embeddings, text embeddings, and zero-shot classification capabilities. It uses official Apple MobileCLIP code and the `apple/MobileCLIP-S0` checkpoint, but remains optional and local-only. The production deterministic classifier remains authoritative until a later milestone explicitly changes classification behavior.

Provider lifecycle is register -> inspect/select interpreter -> generate plan -> Product Owner confirmation -> worker-thread install/download -> strict provider verification -> Ready/history records -> optional testing/evaluation/removal. MODEL-002F is the next milestone for Product Owner-guided MobileCLIP installation and operational validation. MODEL-003 classification integration follows only after MODEL-002F succeeds.
