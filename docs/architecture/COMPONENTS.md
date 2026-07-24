# Family Memory AI - Components

## Purpose

This document describes component responsibilities and interactions.

## Current Component Map

### Import and Metadata Components

- PhotoScanner: Discovers photo files and creates photo-domain objects.
- MetadataExtractor: Extracts image metadata and delegates date resolution.
- DateExtractionService: Resolves date context with deterministic priority ordering (EXIF -> filename -> filesystem).

### Domain Components

- Photo: Core photo entity used across UI and album workflows.
- PhotoIntelligence: Structured metadata/intelligence context attached to photos.
- AnnualAlbum: Year-scoped album container for candidate, selected, and rejected pools.

### Deterministic Curation Components

- AlbumBuilder: Groups photos by year and initializes annual album candidates.
- CandidateSelectionEngine: Deterministic rule-based filtering to selected/rejected candidates.
- AlbumScoringEngine: Deterministic explainable scoring for selected candidates.
- AlbumDraftBuilder: Deterministic draft assembly from reviewed/scored photos with monthly pages and Undated Memories fallback.

### Memory Intelligence Components (Planned Direction)

- Memory Review: Evolves from Album Review into the main interaction point between user and system.
- Decision Engine: Converts user actions into durable decision states.
- Preference Learning: Learns patterns from repeated user actions.
- Cleanup Engine: Manages clutter classification and cleanup suggestions.
- Duplicate Engine: Expands duplicate handling beyond exact deterministic checks.
- Memory Intelligence Layer: Coordinates learned family-specific understanding across outputs.

### Review and UI Components

- MainWindow: Application shell and workflow orchestration, including staged import flow (Photo Browser first, then deferred Cleanup Review and Memory Review) and aggregate Memory Review preparation diagnostics.
- AlbumReviewPage: Current hybrid review UI (toolbar + grid + details), in-memory review status actions, and large-library optimizations. Long-term direction: Memory Review. Includes asynchronous thumbnail retention for deferred row/card creation and explicit empty-state reason handling.
- WorkspaceHeader: Reusable workspace title row with contextual Help action.
- WorkspaceInfoPanel: Reusable compact workspace introduction card with collapsible content and per-workspace UI-state persistence.
- WorkspaceInfoContent map: Centralized workspace-specific intro content definitions consumed by WorkspaceInfoPanel to avoid duplicated per-tab card construction.
- PhotoGridWidget / PhotoCardWidget: Card-based photo browsing and selection surface with batched initial rendering and scroll-triggered continuation for large folders.
- PhotoDetailsPanel: Selected-photo metadata and context presentation.

### Background and Performance Components

- ThumbnailWorker: Cache-first background thumbnail loading, generation, caching, update signaling, and aggregate performance counter accumulation (cache hits/misses, generation time, corrupt-file count).
- ScanWorker: Background worker that runs folder scanning and metadata extraction (find_photos) off the UI thread, keeping the main window responsive during import. Emits scan_complete, scan_error, and finished signals.
- ThumbnailCache: Reusable thumbnail storage to avoid repeated rendering cost.
- PerfStats: Lightweight session-scoped aggregate performance stats collector. Records named timing spans and counters across the import pipeline and prints a single human-readable summary with automatic bottleneck identification at the end of each import session.

## Long-Term Pipeline Responsibilities

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

Each step has a single primary owner component. Current deterministic implementations are early foundations of this broader Memory Intelligence pipeline.

### Content Learning Components

- VisualFeatureProfile: Local deterministic visual evidence model used as primary category-learning evidence.
- VisualFeatureExtractionService: Bounded local image-analysis boundary; it reads pixels, avoids cloud upload, and stores reusable profiles in sidecar metadata.
- CategoryLearningEngine: Records user category corrections, queues missing visual analysis, aggregates category visual profiles, persists schema-versioned learning data, and exposes conservative learned visual rules for recommendations and Learning Summary.
- LearningSummaryDialog: Separates activity counts, category visual learning, preference signals, learned visual-content rules, and recent learning activity so counts alone are not presented as visual learning.

## Vision embedding components

- `core.application_data.ApplicationDataPathService`: canonical stable application-data paths, legacy `.familymemory` migration, atomic JSON writes, and migration diagnostics.
- `vision.embedding_provider`: provider protocol, model metadata/status, normalized embedding records, fake provider, and SQLite embedding store.
- `vision.mobileclip_provider.MobileCLIPEmbeddingProvider`: optional MobileCLIP-S0 CPU provider with lazy loading and explicit local checkpoint cache.
- `vision.evaluation`: bounded evaluation workflow, timing/storage report, zero-shot prompt aggregation, and personalized prototype evaluation without self-match leakage.

## AI runtime components

- `ai_runtime.models`: canonical runtime descriptors, states, capabilities, installation records, environment records, typed plan actions, history records, and benchmark records.
- `ai_runtime.registry.AIRuntimeRegistry`: lightweight provider registry with duplicate-provider protection and lazy provider factory storage.
- `ai_runtime.manager.AIRuntimeManager`: status detection, Python environment inspection, explicit installation/removal plan generation, metadata persistence, diagnostics, and confirmation-gated execution.
- `ai_runtime.executor.AIRuntimeCommandExecutor`: safe typed command execution using argv tokens, explicit interpreter paths, bounded output, timeout, cancellation, and structured results.
- `ai_runtime.mobileclip_registration`: registers MobileCLIP-S0 as the first generic runtime while preserving evaluation-only behavior and no automatic downloads.
- `ui.settings_page.SettingsPage`: exposes the user-visible AI Models section, runtime status, environment inspection, and plan preview.

### MODEL-002B MobileCLIP runtime installation components

- `AIRuntimeManager.build_installation_plan`: creates the explicit MobileCLIP plan with selected interpreter, CPU device, package commands, official sources, checkpoint destination, licenses, warnings, and verification actions.
- `AIRuntimeManager.execute_installation_plan`: runs only confirmed typed actions, including dependency installation, checkpoint download, import checks, and provider verification.
- `AIRuntimeManager.verify_provider`: performs selected-interpreter end-to-end MobileCLIP verification before Ready.
- `SettingsPage`: exposes MobileCLIP plan/install/cancel/verify/test/folder/log/removal actions without replacing the production classifier.

### AI runtime worker component

- `workers.ai_runtime_worker.AIRuntimeOperationWorker`: runs install, verify, one-image embedding test, and model-file removal off the Qt UI thread while emitting progress, completed, failed, and finished signals. Settings owns button state and cancellation while the worker delegates runtime behavior to `AIRuntimeManager`.

### Current AI runtime validation boundary

The AI Runtime Manager and Settings AI Models UI are implemented, and MobileCLIP is registered as the first managed runtime. Product Owner validation confirmed the managed MobileCLIP runtime is Ready on Windows CPU, automatic embedding generation works from the normal app environment, persistent embeddings are written and reused, and stored-vector semantic similarity returns ordered diagnostic results. The production classifier remains unchanged, and semantic similarity is not yet exposed in the production UI.

## Explainable Category Suggestions (MODEL-003D)

`core.category_suggestion_service.CategorySuggestionService` is the reusable, UI-independent boundary for advisory category suggestions. It consumes `vision.semantic_similarity_service.SemanticSimilarityService`, `vision.embedding_provider.EmbeddingStore`, the existing category registry, current photo metadata, and deterministic media classification. It does not create a category store, recompute embeddings, read image pixels, upload images, or mutate photo categories during suggestion generation.

The service returns a typed result with source identity, status, suggested category id/name when available, bounded heuristic confidence, evidence counts, supporting similar-photo references, model key provenance, and user-facing reason strings. Eligible categories are existing content/album-candidate categories only; Unknown and workflow cleanup categories are excluded. Manual/user-corrected labels are strongest evidence, accepted prior suggestions and explicitly trusted deterministic labels are lower-ranked evidence, and unreviewed machine labels are not treated as trustworthy support.

Current performance is an exact stored-vector scan through the semantic similarity service: O(n*d) for n current valid embeddings and d embedding dimensions. Results are cached by source/model/evidence signature and invalidated after category changes or feedback. Rejected suggestions are persisted through the existing photo sidecar metadata so the same category is not immediately resurfaced for unchanged evidence; future ANN indexing can be added behind the similarity service boundary.
