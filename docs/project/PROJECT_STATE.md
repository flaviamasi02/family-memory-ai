# Family Memory AI - Project State

## Current Version

- Version: v0.1.0

## Current Sprint

- Sprint LEARN-001 (Category Learning from User Corrections) - Completed

## Project Status

- Status: In Development

## Last Updated

- 2026-07-05

## Overall Completion

- Estimate: Early prototype with a growing architecture foundation

---

# Executive Summary

Family Memory AI is currently in an early-stage desktop prototype phase. The application launches and supports a basic workflow around importing photos, scanning folders, generating thumbnails, and displaying a photo browser experience.

The immediate goals are to refine the photo library before deeper album work by improving deterministic cleanup, relevance categorization, and safe library triage, while keeping the app stable and without adding export features yet.

The immediate next goal is to shift product architecture toward Family Memory Intelligence, where Memory Review becomes the central interface for teaching future scoring, preference learning, cleanup, duplicate management, and memory-building improvements while keeping behavior deterministic, explainable, and local-only for now.

Future development is now organized by functional domains rather than by a single sequential DEV-XXX chain.

MASTER_DEVELOPMENT_PLAN.md defines the highest-level planning direction.

## Sprint 9 Update

Sprint 9 established the permanent Photo domain model foundation. The Photo object now carries core file information, file dates, UI state, metadata, and safe future AI fields without introducing AI features or databases. Compatibility with the scanner, model, view, and thumbnail worker was preserved so folder import, recursive scanning, thumbnail generation, and cache usage continue to work.

## Sprint 9.1 Update

Sprint 9.1 removed the temporary 300-photo display limit from the import flow. The application now attempts to display all scanned photos instead of only the first 300. The existing thumbnail cache and background thumbnail loading remain in place. This is an intermediate step, and true virtual scrolling or lazy loading is still pending for very large folders.

## Sprint 10 Update

Sprint 10 introduced a lightweight foundation for progressive thumbnail loading. The photo model remains the single source of truth for photo data, the view remains a simple list-based grid, and thumbnail work now runs in batches through the background worker so the UI stays responsive while thumbnails are loaded progressively. This is a preparation step for future lazy loading and virtual grid work rather than the final implementation.

## Sprint 12 Update

Sprint 12 added a simple metadata details panel to the main window and fixed the startup crash caused by connecting selection signals before the photo grid view had a valid selection model. The view now connects its selection handling safely inside the model-binding path, allowing photo selection to update the details panel without destabilizing startup or thumbnail loading. A follow-up bug fix also corrected an incorrect PySide6 import in the details panel, replacing the dynamic import path with the standard Qt import so the application can launch cleanly. Additional hardening was added to thumbnail loading for very large images by switching to QImageReader with scaled decoding, which avoids the full-resolution allocation failure and keeps the app responsive while continuing to use the existing thumbnail cache. The selection flow was then tightened so clicking a photo now routes through the photo model into the details panel, and the details view shows filename, size, dimensions, date, camera information, and status when available. A further fix now handles invalid or corrupted JPEG files safely by catching decode failures in both thumbnail loading and metadata extraction, logging concise warnings, and allowing the import process to continue without crashing. A targeted click-selection bug fix also resolved the earlier crash caused by mixing selectionChanged and clicked flows. The list view now relies on clicked as the reliable selection trigger, so clicking a photo updates the panel without crashing. A fallback interaction change then simplified the flow further by using double-click as the reliable trigger for showing photo details, which avoids the unstable single-click behavior seen after thumbnail updates in QListView. This sprint also introduced a reusable PhotoCardWidget component as the first building block for a future custom photo grid. The component displays a thumbnail and filename, emits a click signal, and can be reused in later Sprint work without introducing AI or database features. The unstable QListView-based photo grid was finally replaced with a lightweight custom PhotoGridWidget built from PhotoCardWidget instances so clicking a photo card reliably updates the details panel. This is an intermediate step toward a fuller custom photo browser and does not yet add virtual scrolling or advanced layout behavior.quiring a redesign of the current grid. The current PhotoGridView implementation was then rewritten from scratch as a minimal clicked-based wrapper because the earlier patchwork selection logic had become brittle when thumbnails and list-item rendering changed. The new view keeps only the essential responsibilities: configure the icon view, receive a click, resolve the selected Photo from the model, and emit the selection signal. This keeps the app functional while preserving a clear path toward a future custom grid implementation.placing the current QListView-based view. Invalid files may still lack thumbnails or metadata, but the app remains responsive and continues processing the rest of the library.

---

## Sprint 14 Update

Sprint 14 polished the custom card UX and status presentation. Photo cards remain focused on thumbnail and filename, and details-panel status values were normalized to user-friendly labels. Status refresh behavior between model updates and details rendering was improved for clearer runtime feedback.

## Sprint DEV-001 Update

DEV-001 introduced the first annual album domain foundation for the Version 1 objective. A new AnnualAlbum model was added with safe defaults for year-based album state (photos, candidate_photos, selected_photos, rejected_photos, status). A first AlbumBuilder was added to group photos by metadata year and create an annual album for a selected year, initially placing all matching photos into candidate_photos. This sprint intentionally does not add AI scoring/selection, PDF export, CEWE/Crew export, or significant UI changes.

Current limitations after DEV-001:

- candidate_photos are initialized but not yet ranked or curated
- no candidate selection engine yet
- no album scoring engine yet
- no album layout or export pipeline yet

## Sprint DEV-002 Update

DEV-002 introduced the Photo Intelligence foundation used by future annual album selection/scoring engines. A new PhotoIntelligence dataclass was added with safe grouped placeholders for metadata context, quality placeholders, people placeholders, duplicate placeholders, album placeholders, and AI placeholders. The Photo model now includes optional intelligence with safe initialization in Photo.from_path(), plus synchronization from metadata when available. Year/month/date_taken intelligence values are now derived when metadata provides date information. This sprint intentionally does not add AI models, face recognition, duplicate detection engine behavior, export, or significant UI changes.

Current limitations after DEV-002:

- intelligence fields are placeholders without production scoring logic
- no candidate selection engine yet
- no album scoring engine yet
- no album review UI flow yet
- no layout/export pipeline yet

Development sequence status:

- DEV-001 Annual Album Foundation: Completed
- DEV-002 Photo Intelligence Foundation: Completed
- DEV-003 Candidate Selection Engine: Completed
- DEV-004 Album Scoring Engine: Completed
- DEV-005 Album Review UI: Completed
- DEV-006 Album Builder: Completed
- DEV-007 Photo Cleanup & Relevance Engine: Completed

## Sprint DEV-003 Update

DEV-003 introduced the first deterministic CandidateSelectionEngine for annual albums. The engine evaluates AnnualAlbum.candidate_photos without deleting the original candidate pool and fills selected_photos/rejected_photos deterministically. Rejection reasons are recorded without AI using explicit rule outcomes (invalid_photo_object, missing_file_path, missing_year, year_mismatch). A lightweight CandidateSelectionResult now summarizes selected/rejected counts and rejection reason totals. Selection uses PhotoIntelligence year when available and falls back safely to metadata/date parsing when intelligence is missing. This sprint intentionally does not add AI ranking, face recognition, duplicate detection engine behavior, database persistence, export, or significant UI changes.

Additional UI improvement after DEV-003 completion:

- the photo browser now shows a clear visible selected-card state (highlight/border badge) so the currently selected photo in the grid stays visually synchronized with the details panel selection.
- Added visible selected-photo state in the photo browser so the active photo is clearly highlighted in the grid.

Current limitations after DEV-003:

- deterministic rule set is intentionally minimal and non-AI
- no album scoring engine yet
- no album review UI flow yet
- no layout/export pipeline yet

## Sprint DEV-004 Update

DEV-004 introduced a deterministic non-AI AlbumScoringEngine for annual albums. The engine scores only AnnualAlbum.selected_photos and produces an explainable score breakdown per photo with technical_score, memory_score, date_score, and total_score. Scored photos are ordered by total score descending and the final score is persisted to PhotoIntelligence.album_candidate_score for downstream deterministic workflows. This sprint intentionally does not add AI ranking, face recognition, duplicate detection behavior, database persistence, export pipeline, or significant UI changes.

Current limitations after DEV-004:

- scoring is deterministic and intentionally non-AI
- no album review UI flow yet
- no layout/export pipeline yet

## Sprint DEV-005 Update

DEV-005 introduced the official hybrid Album Review UI direction for scored annual album candidates: a top toolbar (search, filters, sorting), a central thumbnail grid, and a right-side details panel. The grid displays thumbnail, filename, total score, technical score, memory score, and date score for each reviewed photo, with in-memory review actions (approve, reject, reset to pending). The details panel shows a larger preview, score explanation lines, metadata, people, and date context for the selected photo. The grid rendering uses progressive batch population and responsive column layout to keep behavior scalable for large photo libraries. BUG-001 added a dedicated DateExtractionService and a robust import-time date extraction pipeline to populate PhotoIntelligence.date_taken/year/month/day plus date_source/source_of_date using prioritized sources (EXIF DateTimeOriginal, EXIF CreateDate, other EXIF date fields, filename parsing fallback including WhatsApp/IMG/PXL/Screenshot/VID patterns, then filesystem timestamps). Candidate selection now consistently uses extracted year values, Photo Browser details now shows date + date source, and Album Review shows Imported/Candidates/Selected/Rejected summary with rejection reasons. UI-FIX-001 increased default/minimum application window size and improved Album Review readability with a wider details panel, smaller preview area, and taller score explanation section. PERF-001 optimized Album Review scalability for very large libraries with debounced search, lazy on-demand card rendering, thumbnail/preview pixmap caching, and reduced unnecessary grid/details recomputation. This sprint intentionally does not add AI ranking, persistence/database storage, or export behavior.

Current limitations after DEV-005:

- review decisions are in-memory only
- no album builder workflow yet
- no layout/export pipeline yet

## Sprint DEV-006 Update

DEV-006 introduced the first deterministic AlbumDraftBuilder that builds an in-memory annual album draft from reviewed/scored photos. Approved photos are prioritized, rejected photos are excluded, and pending photos are used as a deterministic fallback when no approved photos exist. Draft assembly enforces a deterministic maximum draft size (120 photos), sorts included photos by date then score, and groups output pages by month with an Undated Memories page when date context is missing. The result now includes explicit inclusion/exclusion counters, exclusion reasons, and draft-level explanations for traceable curation behavior. This sprint intentionally does not add AI ranking, export generation, face recognition, duplicate detection behavior, database persistence, or cloud persistence.

Current limitations after DEV-006:

- album draft is in-memory only
- no print/export pipeline yet
- no duplicate-detection refinement yet

Current active domain and milestone are defined through the domain-based workflow.

## Sprint DEV-007 Update

DEV-007 introduced a deterministic Photo Cleanup & Relevance Engine that runs during import and prepares the library for safe review before later album refinement. The new cleanup layer classifies media into family_photo_candidate, document_or_scan, advertisement, screenshot, meme_or_graphic, video, duplicate_candidate, low_quality_photo, and unknown. Cleanup Review now provides category-based review, reason visibility, recommended actions, checkbox selection, select-all within the active category, and safe bulk move into `_family_memory_cleanup_review` under the imported folder. Exact duplicate handling is implemented as a placeholder using file hashes only: the technically best version is kept when deterministically available, otherwise the largest file is kept and the remaining exact duplicates become duplicate_candidate items. This sprint intentionally does not add AI behavior, permanent deletion, export behavior, or modifications to AlbumDraftBuilder logic.

Current limitations after DEV-007:

- cleanup classification is deterministic only (no AI)
- duplicate detection is exact-hash only; no visual similarity yet
- cleanup move uses quarantine move only; no permanent deletion workflow
- cleanup review ergonomics were later improved by CLEAN-003 (visual workspace, grouping, explainability, category correction)
- no print/export pipeline yet

Future work now follows domain-based planning rather than a single global next sprint.

## Product Decision Update

PRODUCT-DECISION-001 changes the long-term architecture priority.

Album Review is no longer treated only as a simple approve/reject screen.

It becomes the central decision interface where future user actions should teach the application through:

- User Decision Engine
- Preference Learning
- Photo Cleanup
- Album Builder improvements

This changes the development priority order. Instead of moving directly to Album Builder refinement, the next milestone focus becomes:

- User Decision Engine
- Preference Learning
- Photo Cleanup
- Album Builder improvements

## Product Evolution

PRODUCT-DOC-002 redefines the product mission around Family Memory Intelligence.

Family Memory AI is not primarily an album creator.

Its mission is to help families preserve, organize, and understand the memories that matter most while continuously learning what is important for each family.

This creates a strategic shift in development priority.

Future development priority becomes:

1. Decision Engine
2. Preference Learning
3. Cleanup
4. Duplicate Management
5. Memory Intelligence
6. Album Builder
7. Album Refinement

Album Builder becomes one consumer of the Memory Intelligence system rather than the sole center of the product mission.

## Current Active Domain

- LEARN

## Current Milestone

- LEARN-001 Category Learning from User Corrections

## Recently Completed Milestones

- FOUNDATION historical milestones completed
- DEV-007 Photo Cleanup & Relevance Engine
- CLEAN-001 Media Classification & Decision Engine Foundation
- MEM-002 Visible & Correctable Media Category in Memory Review
- CLEAN-002 Improved deterministic initial media classification
- MEM-003 Multi-select Memory Review with bulk category and decision editing
- MEM-004 Compact thumbnail-first Memory Review grid with immediate visible thumbnail loading
- MEM-005 True multi-column Memory Review grid with compact cards and right-panel details
- CLEAN-003 Cleanup Review redesigned with visual thumbnail workspace, explainable classification, grouping, and category correction
- MEM-006 Reusable image preview dialog with double-click navigation from Memory Review and Cleanup Review
- CLEAN-004 Cleanup Review migrated to shared thumbnail grid component with shared lazy rendering and selection model
- CLEAN-005 Visual content-based media classification for metadata-less images
- CLEAN-005-FIX Visual-analysis safety rollback for app responsiveness
- LEARN-001 Persistent sidecar metadata for user category corrections and user decisions
- MEDIA-FIX-001 Centralized orientation-aware image loading for thumbnails and previews
- MEM-008 Custom user-defined categories with Memory/Cleanup assignment and filtering
- MEM-009 Editable system category properties with protected stable IDs and reset-to-default
- LEARN-001 Deterministic category learning rules from repeated user corrections
- UI-REF-001 Cleanup Review single category assignment workflow

UI-REF-001 implementation summary:

- Cleanup Review now uses one category assignment flow: Category dropdown + Apply Category to Selected.
- Redundant quick category buttons were removed from the right-side panel.
- Bulk category assignment remains supported through multi-selection plus dropdown apply.

MEDIA-FIX-001 implementation summary:

- Added centralized display loader in `src/core/image_display_loader.py`.
- EXIF orientation is respected for display thumbnails and full previews across Photo Browser, Memory Review, Cleanup Review, Image Preview Dialog, and Album Draft surfaces.
- Thumbnail cache versioning enables safe regeneration when orientation behavior changes.
- Original source image files are never modified.

MEM-008 implementation summary:

- Category taxonomy is now user-extensible; the product no longer depends only on hardcoded category values.
- Memory Review and Cleanup Review both expose `Manage Categories` for create/rename/delete workflows.
- Category records persist in `.familymemory/categories.json` with optional `ai_description`, visual metadata, and behavior flags.
- Album candidacy and cleanup handling are category-driven via category flags instead of fixed category-name checks.
- Current normalized media categories are Family Photo, Not Family Photo, Document, Screenshot, Meme / Graphic, Video, and Unknown.
- User categories extend the taxonomy without changing stable internal IDs.
- Grouping in review surfaces is a visualization aid only; it does not change media classification.

MEM-009 implementation summary:

- System categories remain protected and non-deletable, but users can now customize display and behavior properties.
- Stable internal category IDs remain unchanged so existing media/category links continue to work after display renames.
- System category overrides persist locally and are applied on startup after loading defaults.
- Added per-category reset-to-default for system categories.

CLEAN-005 implementation summary:

- Added local visual content analysis to improve classification for metadata-less images.
- Unknown is no longer the default for metadata-less images when visual evidence is strong.
- Classification explanations now include visual evidence.
- No cloud AI dependency added; local analysis remains explainable and user-correctable.

CLEAN-005-FIX implementation summary:

- Added emergency feature flag `ENABLE_VISUAL_CONTENT_ANALYSIS = False` as default.
- Synchronous import/UI classification now skips visual analysis to restore fast loading and avoid Not Responding states.
- Classifier now safely falls back to filename/metadata/user-learning rules when visual analysis is disabled, unavailable, or errors.
- Added regression tests for disabled mode, no-image-open behavior, exception safety, and quick classification return.
- Future work: run visual analysis only in background worker batches, never on UI thread.

Runtime stability update:

- Thumbnail generation now keeps `QPixmap` creation in the UI thread by emitting `QImage` from the worker.
- Photo Browser thumbnail updates use normalized absolute path keys so late-arriving thumbnails resolve reliably.
- Album review draft refreshes use `AlbumReviewPage.review_status_by_path()` again for current review-state mapping.
- Visual analysis remains feature-flagged off in synchronous import/UI paths until it can run only in background batches.

## Upcoming Milestones

- LEARN-002 Preference learning and aggregation foundations
- DUP-001 Exact Duplicate Detection refinement
- MEMORY-001 Memory Value

## Product Documentation

- PRODUCT-DOC-001 introduced docs/product/FAMILY_MEMORY_SCORE.md as the official long-term product specification for Family Memory AI photo ranking.
- The Family Memory Score specification is now the single source of truth for future scoring philosophy, component-level scoring design, and explainability requirements.

## Product Principles

- AI is encouraged.
- Explainability is mandatory.
- User decisions always override AI.
- User corrections become learning signals.

## Documentation Architecture Refactoring Update

Project documentation was fully reorganized into a modular folder structure to improve scalability and AI initialization consistency.

Migration completed:

- bootstrap documents moved to `docs/bootstrap/`
- project operational/context docs moved to `docs/project/`
- workflow/decision/doc-governance docs moved to `docs/development/`
- architecture references moved to `docs/architecture/`
- testing docs organized under `docs/testing/`
- release docs organized under `docs/releases/`
- legacy root-level context/state snapshots preserved in `docs/archive/`

Internal references were updated to the new structure.

---

# Current Architecture

The current implementation is a lightweight Qt desktop application with a modular structure centered on the Photo model and a custom photo card experience.

Current deterministic curation pipeline:

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

Memory Review and Cleanup Review now share the same visual UX philosophy and both expose confidence-driven explainable decisions.

## Current Folders

- src/
- src/ui/
- src/workers/
- src/cache/
- tests/
- docs/
- assets/
- tools/

## Major Modules

- Main application entry point
- Main window UI
- Photo card and photo grid widgets
- Thumbnail worker
- Thumbnail cache
- Photo scanning flow
- Metadata extraction flow
- Annual album domain model
- Annual album builder
- Photo intelligence model
- Candidate selection engine
- Album scoring engine
- Album review page
- Cleanup review page
- Album draft builder
- Album draft page

Future architectural emphasis:

- User Decision Engine over simple approve/reject state changes
- Preference-learning signals derived from repeated user decisions
- Decision-aware cleanup and recommendation flows
- Album Builder as one output of broader Memory Intelligence

Long-term output framing:

- albums as one output
- stories as one output
- timelines as one output
- search as one output

---

# Completed Sprints

| Sprint | Status | Main Achievement |
| --- | --- | --- |
| Sprint 1 | Completed | Repository |
| Sprint 2 | Completed | First Window |
| Sprint 3 | Completed | Refactoring |
| Sprint 4 | Completed | Import Photos |
| Sprint 5 | Completed | Photo Browser |
| Sprint 6 | Completed | Background Thumbnail Loading |
| Sprint 7 | Completed | Persistent Thumbnail Cache |
| Sprint 7.5 | Completed | Architecture Refactoring |
| Sprint 8 | Completed | Model/View Architecture Foundation |
| Sprint 9 | Completed | Photo Domain Model Foundation |
| Sprint 9.1 | Completed | Removed the 300-photo display limit |
| Sprint 10 | Completed | Progressive / Lazy Loading Foundation |
| Sprint 11 | Completed | EXIF Metadata Foundation |
| Sprint 12 | Completed | Custom Photo Grid and Details Panel |
| Sprint 13 | Completed | Batch Photo Grid Loading |
| Sprint 14 | Completed | UI polish and status synchronization |
| Sprint DEV-001 | Completed | Annual album domain foundation |
| Sprint DEV-002 | Completed | Photo intelligence foundation |
| Sprint DEV-003 | Completed | Deterministic candidate selection engine |
| Sprint DEV-004 | Completed | Deterministic album scoring engine |
| Sprint DEV-005 | Completed | Album review UI with in-memory decisions |
| Sprint DEV-006 | Completed | Deterministic monthly album draft builder |
| Sprint DEV-007 | Completed | Photo cleanup, cleanup review, and safe cleanup-folder move workflow |

---

# Current Features

- [x] Application launches
- [x] Folder import
- [x] Recursive scan
- [x] Thumbnail generation
- [x] Persistent thumbnail cache
- [x] Responsive UI during import and thumbnail loading
- [x] Background worker
- [x] GitHub workflow
- [x] Photo domain model foundation
- [x] Thumbnail worker compatibility preserved
- [x] EXIF metadata extraction foundation
- [x] Custom photo card grid foundation
- [x] Progressive batch creation of photo cards
- [x] Details panel updates from card selection
- [x] Annual album domain model (year-based)
- [x] Annual album builder with metadata-year filtering
- [x] Candidate album initialization for selected year
- [x] Photo intelligence dataclass foundation
- [x] Photo-intelligence linkage on Photo model
- [x] Intelligence year/month/date population when metadata exists
- [x] Deterministic candidate selection engine
- [x] Candidate rejection reason tracking (non-AI)
- [x] Candidate selection result summary counts
- [x] Deterministic album scoring engine
- [x] Explainable album score breakdown per selected photo
- [x] Album candidate score persistence on PhotoIntelligence
- [x] Album review page for scored candidates
- [x] Hybrid review layout (toolbar + thumbnail grid + details panel)
- [x] BUG-001 dedicated DateExtractionService with EXIF/filename/filesystem fallback logic
- [x] PhotoIntelligence date context fields: date_taken/year/month/day/date_source/source_of_date
- [x] In-memory approve/reject/reset review state
- [x] Sidecar-based persistence for manual user category corrections and user decisions
- [x] Import-time sidecar loading with identity checks and cautious mismatch handling
- [x] Centralized image loader utility for orientation-aware full image and thumbnail loading
- [x] Flexible category registry with system and user category definitions
- [x] Manage Categories dialog in Memory Review (add, rename, delete user categories, update cleanup/album flags)
- [x] Memory Review category selector/filter supports user-defined categories
- [x] Cleanup Review category selector/filter supports user-defined categories
- [x] Custom categories persisted in `.familymemory/categories.json`
- [x] System categories protected from deletion
- [x] Custom category assignment persists per photo via sidecar metadata
- [x] Deterministic category learning engine with explainable signal extraction and adaptive rules
- [x] Learned rule application during import-time classification (base deterministic classifier + learned-rule boost)
- [x] Learning profile persistence in `.familymemory/category_learning_profile.json`
- [x] One learning event recorded per manual category correction (single and bulk)
- [x] Learning Summary dialog for transparency (event totals, category counts, learned rules)
- [x] No cloud AI and no black-box ML for category learning
- [x] Album review filters, sorting, and filename search
- [x] Album review details panel with explanation visibility
- [x] Review visibility for imported/candidates/selected/rejected pools with rejection reasons
- [x] UI-FIX-001 readability improvements for main window sizing and Album Review details/explanation area
- [x] PERF-001 Album Review scalability improvements for 4,000+ photo libraries
- [x] Deterministic AlbumDraftBuilder for annual draft assembly
- [x] Monthly draft pages plus Undated Memories fallback grouping
- [x] Review-driven inclusion rules (approved/rejected/pending fallback)
- [x] Draft build counters, exclusion reasons, and explanations
- [x] Deterministic photo cleanup and relevance classification during import
- [x] Photo Browser cleanup/relevance filter
- [x] Cleanup Review tab with grouped category review and bulk selection
- [x] Memory Review multi-selection (single, Ctrl toggle, Shift range)
- [x] Memory Review bulk category editing with Automatic Category -> User Corrected Category -> Effective Category behavior
- [x] Memory Review bulk decision editing with in-memory decision-history events
- [x] Memory Review compact thumbnail-first cards for fast visual review
- [x] Memory Review responsive multi-column layout with lazy rendering and thumbnail caching
- [x] Cleanup Review redesigned with the same UX philosophy as Memory Review (toolbar, compact grid, right details panel)
- [x] Cleanup Review explainable classification view with structured reason checklist and confidence display
- [x] Cleanup Review category grouping and category-by-category review workflow
- [x] Cleanup Review possible alternatives for low-confidence classifications (<80%)
- [x] Cleanup category correction with Automatic Category -> User Corrected Category -> Effective Category propagation
- [x] Reusable Image Preview dialog with larger visual inspection
- [x] Double-click on Memory Review cards opens large image preview
- [x] Double-click on Cleanup Review cards opens the same preview dialog
- [x] Preview dialog supports next/previous navigation within the current visible filtered list
- [x] Preview dialog keyboard shortcuts: Esc (close), Left/Right (previous/next)
- [x] Preview dialog uses original image when available and falls back to thumbnail when original is unavailable
- [x] Preview dialog shows filename, media category, user decision, score (when available), and position (N of total)
- [x] Shared thumbnail grid component for review workspaces (compact cards, multi-column layout, lazy rendering)
- [x] Cleanup Review migrated to shared thumbnail grid and shared interaction model
- [x] Shared double-click preview flow between Memory Review and Cleanup Review
- [x] Shared lazy/batched rendering and selection model for Cleanup Review grid
- [x] Cleanup Review thumbnail cache reuse for compact-card rendering
- [x] EXIF orientation respected in Photo Browser thumbnails, Memory Review thumbnails/previews, Cleanup Review thumbnails/previews, and preview dialog
- [x] Thumbnail caching keys include path, target size, and file identity signature (mtime and size)
- [x] Orientation handling uses safe auto-transform with graceful fallback for missing/corrupt metadata
- [x] Immediate sidecar save on Memory Review and Cleanup Review manual category/decision changes
- [x] UI indicator for saved manual category changes ("User category saved")
- [x] Safe move to cleanup review folder with confirmation and result summary
- [x] Exact duplicate placeholder handling using file hashes and deterministic keeper selection
- [x] Improved deterministic initial media classification with richer multilingual indicators and conservative family-photo assignment
- [x] Deterministic end-to-end curation pipeline from import through draft assembly
- [x] Visible selected-photo highlight in the photo grid
- [x] Documentation architecture refactored into modular folders

Future product priority after PRODUCT-DECISION-001:

- Memory Review as the central decision engine
- Preference learning from repeated user actions
- Decision-aware cleanup and album-building improvements

Future product priority after PRODUCT-DOC-002:

- Memory Review as the main interaction point between user and system
- Preference learning from all meaningful user actions
- Cleanup and duplicate management as learning-aware infrastructure
- Memory Intelligence before deeper output refinement

---

# Current Limitations

- Temporary UI
- No true virtual scrolling yet
- Large folders still load progressively rather than instantly
- No database yet
- No AI scoring yet
- No face recognition yet
- No duplicate detection yet
- No AI cleanup classification yet
- No visual-similarity duplicate detection yet
- Cleanup and Memory review corrections are in-memory only (no persistence yet)
- Preference Learning engine is not active yet (decision signals are foundation only)
- No print-ready export pipeline yet
- No HEIC support yet
- No cloud integration yet

---

# Technical Debt

## High

- The custom card grid still needs a more scalable layout and rendering strategy for very large libraries.
- UI and processing concerns should be further decoupled as the feature set grows.
- The architecture should continue to formalize the separation between domain models, UI widgets, and background workers.

## Medium

- Thumbnail handling should be expanded into a more general media pipeline.
- The app needs better state management as more metadata and interactions are added.
- Performance expectations for very large libraries now require more explicit virtualization planning.

## Low

- Documentation should remain synchronized as the project evolves.
- Some UI patterns may need refinement as the interface matures.

---

# Domain Workflow

Historical DEV-XXX milestones remain valid as implementation history.

Future planning must use domains and milestones defined in docs/project/DOMAIN_ROADMAP.md.

MASTER_DEVELOPMENT_PLAN.md defines the higher-level product-planning rule set that all domain planning must follow.

Before planning implementation, the correct functional domain must be identified first.

---

# Upcoming Roadmap

See docs/project/ROADMAP.md for the authoritative milestone plan.

---

# Known Issues

- [ ] Add issue tracker entries as bugs and limitations are discovered.
- [ ] Record major regressions after each Sprint.
- [ ] Capture performance problems for large photo collections.

---

# Open Decisions

- [ ] Confirm long-term database strategy.
- [ ] Confirm whether metadata should be stored locally first.
- [ ] Confirm initial AI feature priorities.
- [ ] Confirm future cloud strategy.

---

# Project Metrics

| Metric | Value |
| --- | --- |
| Python files | TBD |
| Lines of code | TBD |
| Classes | TBD |
| Modules | TBD |
| Implemented features | TBD |
| Completed Sprints | 20 |
| Architecture maturity | Emerging |

---

# AI Context

This document should be the first document read by any AI assistant before making implementation decisions.

It provides the current project status and operational context. The other project documents describe long-term direction and standards:

- [AI_DEVELOPER_GUIDE.md](../development/AI_DEVELOPER_GUIDE.md)
- [ARCHITECTURE.md](../architecture/ARCHITECTURE.md)
- [PRODUCT_VISION.md](PRODUCT_VISION.md)
- [CODING_STANDARDS.md](../development/CODING_STANDARDS.md)
- [ARCHITECTURAL_DECISIONS.md](../architecture/ARCHITECTURAL_DECISIONS.md)

PROJECT_STATE.md is the single source of truth for current version, active domain/milestone, completed sprint count, and operational implementation status.

docs/project/DOMAIN_ROADMAP.md is the single source of truth for future planned domains and milestones.

docs/project/MASTER_DEVELOPMENT_PLAN.md is the single source of truth for highest-level product planning direction.

docs/project/ROADMAP.md is retained as historical and transitional planning context.

docs/releases/CHANGELOG.md is the single source of truth for historical sprint changes.

---

# Update Rules

This document must be updated after every completed Sprint.

It should never be left outdated, because it is the operational memory of the project.

PROJECT_STATE.md is the operational memory of Family Memory AI. Every AI assistant should read this file before proposing changes to the project.