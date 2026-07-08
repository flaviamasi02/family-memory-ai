# Changelog

## Unreleased
### DOCSYNC - Official AI collaboration workflow
- Formalized the official Product Owner -> ChatGPT -> Implementation Prompt -> Codex -> Pull Request -> GitHub Actions -> ChatGPT Technical Review -> Product Owner Approval -> Merge workflow.
- Added permanent repository health first, pull request lifecycle, GitHub Actions root-cause, human interaction, Codex Cloud limitation, and continuous workflow improvement policies.
- Extended the official prompt template with required implementation prompt sections, Definition of Done expectations, and the User Action Rule.
- Recorded DEC-0036 and updated project state for the documentation governance improvement.

### DOCSYNC - Product decision synchronization and prompt standard refresh
- Updated implementation prompt standards to require Why We Test, Manual Test Plan, and Acceptance Checklist sections.
- Documented Memory Review as the AI-teaching surface with learning visibility, content-first learning, and future Learning Inspector direction.
- Documented category semantics so content categories, organizational categories, and workflow categories are treated differently.
- Added the approved product testing workflow and aligned glossary, roadmap, and decision ledger terminology.

### UX-001/UX-002/UX-003 - Memory Review usability and Learning Summary timestamps
- Preserved thumbnail-grid scroll position and selection when category corrections are applied in Memory Review and Cleanup Review.
- When a corrected photo no longer matches the active filter, the review grid removes it, keeps the user's position, and selects the next visible photo.
- Memory Review now hides Decision editing controls so the workspace focuses on category correction, AI teaching, preference learning, and classification review.
- The underlying decision model and non-Memory Review decision workflows remain intact.
- Learning Summary now shows stored local date/time values for learned category rules, preference signals, and learning events.
- Updated contextual Help for Memory Review and Learning Summary behavior.

### LEARN-002 - Preference Learning and Aggregation Foundations
- Added `PreferenceLearningEngine` with `PreferenceLearningEvent`, `PreferenceSignal`, and `PreferenceLearningProfile` dataclasses.
- Aggregates local preference signals from category corrections, memory decisions, and cleanup-oriented decisions.
- Preference signals include signal type, target, decision, support count, strength, explanation, and source action.
- Persists the local preference profile at `.familymemory/preference_learning_profile.json`.
- Missing or corrupted preference profiles safely fall back to an empty profile.
- Added a summary API for UI/debug usage: total events, signal counts, strongest preference signals, and last-updated timestamp.
- Integrated preference event recording with existing Memory Review and Cleanup Review save points.
- Added focused tests for empty profile creation, event recording, aggregation, persistence/reload, corrupted profile fallback, and explainability.
- No cloud AI, black-box ML, database storage, face identity recognition, visual-analysis UI/import path changes, or original image modifications.

### PRODUCT-DOC-006 - DOCSYNC PC FULL canonical alignment
- Synchronized project state, domain roadmap, and historical roadmap on active domain/milestone and strategic priority order.
- Standardized priority order across planning/product docs: classification reliability, correction learning, cleanup quality, people intelligence, outputs.
- Clarified category semantics: Effective Category remains authoritative; grouping is visualization-only.
- Clarified People roadmap direction: PEOPLE-001 remains local face-evidence only, without identity recognition.
- Updated workflow references to canonical bootstrap paths.

### PEOPLE-001 - Face Detection and Family Photo Classification
- Added `FaceDetectionService` with `FaceDetectionResult` for local face detection foundations.
- Uses OpenCV Haar cascade when available; unavailable detector path returns safe fallback without crashing.
- Added `ENABLE_FACE_DETECTION = False` feature flag default for conservative rollout.
- Added `FaceDetectionWorker` for non-blocking background analysis.
- Added Cleanup Review action `Analyze Faces for Visible` to analyze selected/visible photos only.
- Persisted face metadata: `face_count`, `has_faces`, `face_detection_confidence`, `face_detection_detector`.
- Media classifier now treats strong face evidence as Family Photo evidence and includes `face detected` in classification reason.
- Unknown photos with strong face evidence can be reclassified to Family Photo.
- Automatic Meme/Graphic classification is only overridden by face evidence when there is no user-corrected category.
- User-corrected category remains authoritative.
- Added details-panel visibility for faces detected, face count, and detection confidence.
- No cloud AI, no person identity recognition, and no original file modifications.

### Runtime Stability Hardening
- Switched background thumbnail generation to emit `QImage` and moved `QPixmap` conversion into the UI thread.
- Normalized Photo Browser thumbnail keys so late thumbnail updates resolve against stable absolute paths.
- Restored `AlbumReviewPage.review_status_by_path()` so MainWindow can refresh album draft state from current review statuses.
- Kept visual content analysis out of synchronous import/UI paths while the feature flag remains disabled by default.

### CLEAN-005-FIX - Visual-analysis safety rollback for app responsiveness
- Added emergency feature flag `ENABLE_VISUAL_CONTENT_ANALYSIS = False` as the default.
- Synchronous import/UI classification now skips visual analysis to restore fast loading and avoid Not Responding states.
- Classifier now safely falls back to filename, metadata, and user-learning rules when visual analysis is disabled, unavailable, or errors.
- Added regression tests for disabled mode, no-image-open behavior, exception safety, and quick classification return.
- Future work: run visual analysis only in background worker batches, never on the UI thread.

### MEDIA-FIX-001 - Centralized orientation-aware image loading
- Added a centralized display loader in `src/core/image_display_loader.py`.
- EXIF orientation is respected for display thumbnails and full previews across Photo Browser, Memory Review, Cleanup Review, Image Preview Dialog, and Album Draft surfaces.
- Thumbnail cache versioning enables safe regeneration when orientation behavior changes.
- Original source image files are never modified.

### MEM-008 - Custom user-defined categories with Memory/Cleanup assignment and filtering
- Category taxonomy is user-extensible; the product no longer depends only on hardcoded category values.
- Memory Review and Cleanup Review both expose `Manage Categories` for create, rename, and delete workflows.
- Category records persist in `.familymemory/categories.json` with optional `ai_description`, visual metadata, and behavior flags.
- Album candidacy and cleanup handling are category-driven via category flags instead of fixed category-name checks.

### MEM-009 - Editable system category properties with protected stable IDs and reset-to-default
- System categories remain protected and non-deletable, but users can customize display and behavior properties.
- Stable internal category IDs remain unchanged so existing media/category links continue to work after display renames.
- System category overrides persist locally and are applied on startup after loading defaults.
- Added per-category reset-to-default for system categories.

### LEARN-001 - Persistent sidecar metadata and deterministic learning rules from user corrections
- Added `UserMetadataService` for sidecar persistence of manual category corrections and user decisions.
- Sidecars are saved as `photo.familymemory.json` next to each image and include file identity, classification context, and update metadata.
- Import ignores sidecar files as media and applies sidecar values when identity matches.
- Import handles identity mismatches cautiously by preserving user correction and decision when filename matches and attaching a warning flag.
- Memory Review and Cleanup Review now save sidecar metadata immediately after category and decision changes.
- Added UI confirmation text for category saves: `User category saved`.
- Added tests for creation, persistence, load, effective-category override, missing sidecar safety, and mismatch handling.
- Sidecar-first only: no original image binary metadata writes.

### UI-REF-001 - Cleanup Review single category assignment workflow
- Cleanup Review now uses one category assignment flow: Category dropdown plus `Apply Category to Selected`.
- Redundant quick category buttons were removed from the right-side panel.
- Bulk category assignment remains supported through multi-selection plus dropdown apply.

### CLEAN-004 - Shared Thumbnail Grid for Cleanup Review
- Migrated Cleanup Review to a shared thumbnail-grid component used for review workflows.
- Shared grid supports compact cards, responsive multi-column layout, lazy/batched rendering, multi-selection, and double-click handling.
- Cleanup cards remain compact and display only thumbnail, filename, automatic category badge, confidence badge, and recommended action badge.
- Kept existing Cleanup filters (category, confidence, recommended action, search) with grid refresh behavior.
- Preserved bulk actions (category correction, safe move to cleanup folder, decision updates) on top of shared selection model.
- Reused image-preview dialog flow so Cleanup double-click opens the same preview with next/previous and Esc support.
- Added/updated tests for shared-grid rendering in Cleanup Review, multi-column behavior, details updates, filtering, multi-selection, lazy rendering, and thumbnail-cache reuse.
- No AI added, no scoring/AlbumBuilder changes, and no persistence added.

### MEM-006 - Image Preview on Double Click
- Added reusable `ImagePreviewDialog` for large visual inspection from compact review grids.
- Added double-click preview opening from Memory Review cards.
- Added double-click preview opening from Cleanup Review cards.
- Added Previous/Next controls and keyboard shortcuts (Left/Right arrows, Esc close).
- Added preview metadata context: filename, media category, user decision, score (when available), and position (N of total visible list).
- Implemented original-image-first loading with thumbnail fallback and a clear `Preview unavailable` state.
- Kept preview loading focused on current image only, with scaled pixmap caching to keep navigation responsive.
- Added deterministic tests for dialog navigation, fallback behavior, Esc close, and double-click integration in both review pages.
- No persistence, no AI behavior, no scoring/classification rule changes, and no AlbumBuilder logic changes.

### CLEAN-003 - Cleanup Review UX & Explainability
- Replaced Cleanup Review's table-centric UI with a visual review workspace aligned to Memory Review: toolbar filters, compact thumbnail grid, and right-side details panel.
- Added compact cleanup cards that display only thumbnail, filename, automatic category badge, confidence badge, and recommended action badge.
- Added structured explainability in details: "Why was this classified?" checklist signals and confidence display.
- Added "Possible alternatives" visibility for low-confidence classifications (<80%) using deterministic category probability hints.
- Added in-memory category correction flow with automatic -> user corrected -> effective category mapping.
- Added explicit cleanup decision/action controls: Keep, Move to Cleanup Folder, and direct category-marking actions.
- Added category grouping view with counts and category-by-category filtering workflow.
- Added cleanup statistics summary: imported, cleanup candidates, category counts, and average confidence.
- Reused Memory Review interaction patterns: compact cards, multi-selection model, right-side preview/details panel, lazy batch rendering, and thumbnail updates.
- Added deterministic Qt tests for cleanup card rendering, details updates, grouping/statistics, category correction, alternatives visibility, selection/bulk actions, and safe move action.
- No AI added, no persistence added, and no permanent delete workflow added.

### MEM-005 - True Multi-Column Thumbnail Grid for Memory Review
- Refactored Memory Review to use a true multi-column compact thumbnail grid with automatic column recalculation on resize.
- Simplified cards to compact visual content: thumbnail, shortened filename, score badge, category badge, and decision badge.
- Moved long contextual text to the right details panel only to keep the grid scan-friendly.
- Preserved lazy/batched rendering and infinite-scroll style batch expansion for large libraries.
- Preserved multi-select behavior, selected-count state, and bulk category/decision editing flows.
- Kept right-side details panel with full selected-photo context (preview, score, category, reason, confidence, decision, date, date source, explanations).
- Added/updated deterministic tests for multi-column behavior, compact card sizing/content, and preserved selection/bulk behavior.
- No persistence, no AI training, no scoring-rule changes, and no AlbumDraftBuilder changes in this milestone.

### MEM-004 - Fast Compact Thumbnail Grid for Memory Review
- Replaced oversized Memory Review cards with a compact thumbnail-first grid layout optimized for dense visual scanning.
- Reduced card and thumbnail dimensions and added compact score/category/decision badges for each card.
- Added immediate thumbnail resolution for visible cards using thumbnail_path when available, with scaled-original fallback when thumbnail_path is missing.
- Added per-path scaled pixmap caching for visible-card thumbnail loading to avoid loading full-size images for entire libraries.
- Fixed stale "No thumbnail" behavior by wiring thumbnail worker updates directly into Memory Review card refreshes.
- Preserved lazy/batched rendering for large libraries and maintained multi-select and bulk edit behavior.
- Added deterministic tests for compact sizing, immediate visible thumbnail loading paths, fallback loading, and thumbnail visibility without requiring category changes.
- No persistence, no AI training, no scoring-rule changes, and no album-builder changes in this milestone.

### MEM-003 - Multi-Select Bulk Category Editing
- Added multi-select behavior in Memory Review grid with intuitive single click, Ctrl+click toggle selection, and Shift+click visible range selection.
- Added in-memory selection state by file path with selected-count display, clear selection, and select-all-visible actions.
- Added bulk category editor with Apply Category to Selected; automatic category is preserved while user-corrected and effective categories are updated.
- Added bulk decision editor with Apply Decision to Selected for UserDecision updates across selected photos.
- Added safety confirmation for bulk actions over 20 selected photos with cancel support.
- Added per-photo in-memory learning events for bulk category and decision changes with source=user_bulk.
- Added deterministic tests for multi-select, selection actions, bulk apply behavior, effective-category override behavior, learning events, and large-bulk confirmation flow.
- No persistence and no AI training added in this milestone.

### CLEAN-002 - Improved Deterministic Initial Media Classification
- Strengthened deterministic MediaClassifier rules for meme, graphic, advertisement, screenshot, document, and unknown/non-family media.
- Added richer filename indicators for meme-like/shared/downloaded media patterns.
- Added dimension-aware classification heuristics for very small images, banner-like images, and tall phone screenshot shapes.
- Added metadata-aware confidence behavior so family_photo requires stronger evidence and weak metadata profiles move toward unknown/graphic outputs.
- Expanded explainable classification reasons to include filename, dimension, and metadata rationale.
- Added deterministic tests for WhatsApp meme-like images, downloaded funny images, banner images, small square non-camera images, normal camera photos, screenshots, and documents.
- No cloud AI, no persistence, and no permanent deletion added in this milestone.

### MEM-002 - Visible & Correctable Media Category in Memory Review
- Promoted automatic media category to a first-class Memory Review concept with card-level visibility.
- Added readable classification fields in details panel (category, reason, confidence, user decision, date, date source, score).
- Added dedicated category filter independent from decision-status filter.
- Added user category correction controls with Apply Category behavior.
- Added in-memory category state fields: automatic_media_category, user_corrected_media_category, effective_media_category.
- Added in-memory learning events for category corrections and decision changes with file_path, event_type, previous_value, new_value, and source=user.
- Added deterministic tests for card visibility, category filtering, category correction, effective category override, learning-event recording, and details display behavior.
- No persistence added and no AI model training added in this milestone.

### CLEAN-001 - Media Classification & Decision Engine Foundation
- Added deterministic media classifier foundation with explicit MediaCategory and UserDecision enums.
- Added classification outputs for media_category, classification_reason, and classification_confidence for imported media.
- Added model integration for media_category, user_decision, classification_reason, and classification_confidence.
- Replaced simple Album Review action buttons with a full decision selector supporting all UserDecision values.
- Added in-memory decision history object to capture every user decision event for future preference-learning integration.
- Added deterministic tests for classifier behavior, decision assignment, and decision persistence.
- No AI behavior added, no permanent deletion behavior added, and no AlbumDraftBuilder modifications in this milestone.

### PRODUCT-DOC-005
- Introduced docs/project/MASTER_DEVELOPMENT_PLAN.md as the highest-level project planning document.
- Documented product domains, permanent principles, future decision model, and the rule that new work must map to an owning product domain.
- Updated bootstrap, framework, commands, state, and roadmap documents to treat MASTER_DEVELOPMENT_PLAN.md as the primary planning document.
- No application code modified.

### PRODUCT-DOC-004
- Adopted domain-based development workflow as the official future methodology.
- Added docs/project/DOMAIN_ROADMAP.md as the official future roadmap.
- Replaced single next-sprint planning with current active domain, current milestone, recently completed domains, and future planned domains.
- Updated bootstrap, framework, commands, product docs, and documentation ownership to validate domain-roadmap consistency and product vision alignment.
- No application code modified.

### PRODUCT-DOC-002
- Redefined the product mission around Family Memory Intelligence rather than album creation alone.
- Documented Memory Review as the long-term central interaction point between the user and the system.
- Added Continuous Learning, future learning categories, and broader Family Memory Intelligence workflow direction to the product documentation.
- Reorganized the roadmap into Foundation, Learning, Memory Intelligence, and Outputs phases.
- Established docs/product/PRODUCT_VISION.md as the canonical product-vision document and aligned documentation ownership around it.
- No application code modified.

### PRODUCT-DECISION-001
- Updated the major long-term product direction before further implementation work.
- Defined Album Review as the future central decision engine instead of a simple Approve / Reject / Pending screen.
- Introduced preference learning into the official product architecture and documentation.
- Documented the future PhotoDecision model and User Decision Engine workflow.
- No application code modified.

### Sprint DEV-007 - Photo Cleanup & Relevance Engine
- Added PhotoCleanupEngine for deterministic cleanup categorization during import.
- Added cleanup categories: family_photo_candidate, document_or_scan, advertisement, screenshot, meme_or_graphic, video, duplicate_candidate, low_quality_photo, and unknown.
- Added exact duplicate placeholder handling using file hashes, keeping the technically best version when deterministically available, otherwise keeping the largest file.
- Added Cleanup Review tab with category grouping/filtering, thumbnails when available, filename, reasons, recommended action, checkbox selection, and select-all in current category.
- Added Photo Browser cleanup/relevance filtering for family candidates, documents/scans, advertisements, screenshots, memes/graphics, videos, duplicates, low quality, and unknown files.
- Added safe move workflow through `_family_memory_cleanup_review` inside the imported folder.
- Added explicit confirmation before safe move, including file count, destination, and warning text.
- Added safe move result summary with moved, skipped, and failed counts.
- Added tests for deterministic cleanup classification and safe cleanup-folder move behavior.
- No permanent delete, no AI behavior changes, no album export, and no AlbumDraftBuilder rule changes in this sprint.

### Sprint DEV-006 - Album Builder
- Added AlbumDraftBuilder for deterministic in-memory annual album draft creation from reviewed/scored photos.
- Added AlbumDraftPage, AlbumDraft, and AlbumDraftBuildResult dataclasses for structured draft outputs and traceable build metrics.
- Added deterministic inclusion logic: approved photos included, rejected photos excluded, and pending fallback when no approved photos exist.
- Added deterministic default draft cap (120 photos) with exclusion reason tracking.
- Added monthly draft page grouping plus Undated Memories fallback for missing date context.
- Added deterministic sorting by date then score.
- Added tests for inclusion/exclusion rules, limits, monthly/undated grouping, counters, explanations, and deterministic ordering.
- No AI scoring-rule changes, no export, no database persistence, no face recognition, and no duplicate-detection implementation in this sprint.

### PRODUCT-DOC-001 - Family Memory Score Product Specification
- Added official Family Memory Score product specification at docs/product/FAMILY_MEMORY_SCORE.md.
- Documented long-term explainable multi-factor scoring philosophy and component definitions.
- Documented intended future scoring architecture with independent scorers and FamilyMemoryScoreEngine composition.
- Documentation update only: no application code changed.

### Sprint DEV-005 - Album Review UI
- Added Album Review page with the official hybrid layout: top toolbar (search, filter, sorting), central thumbnail grid, and right-side details panel.
- The thumbnail grid displays filename plus total, technical, memory, and date scores for each scored photo (no list-only review layout).
- Added review details panel with larger preview, score explanation list, metadata summary, people summary, and date context for selected photos.
- Added in-memory review actions: Approve, Reject, and Reset to Pending.
- Added review filters: All, Pending, Approved, and Rejected.
- Added sorting controls: Highest score, Lowest score, and Date.
- Added filename search for quick review narrowing.
- Added scalable batch card rendering and responsive grid columns to support large photo libraries.
- BUG-001: Added dedicated DateExtractionService for robust photo date resolution during import.
- Added robust import-time date extraction priority: EXIF DateTimeOriginal, EXIF CreateDate, other EXIF date fields, filename parsing fallback, then filesystem creation/modification timestamp.
- Added filename date parsing support for common patterns including WhatsApp/IMG/PXL/Screenshot and VID_20240118_093015.mp4.
- Added PhotoIntelligence date fields population: date_taken, year, month, day, date_source/source_of_date.
- Added date_source values: EXIF, Filename, Filesystem, Unknown.
- CandidateSelectionEngine now reliably uses extracted intelligence year values from the new pipeline.
- Photo Browser details panel now shows Date and Date source.
- Album Review now surfaces Imported/Candidates/Selected/Rejected summary and rejection reasons.
- Added UI/unit tests for sorting, filtering, review actions, detail panel behavior, and explanation visibility.
- Added unit tests for each supported filename date pattern and WhatsApp import scoring visibility.
- UI-FIX-001: increased default/minimum application window size while keeping standard resizable window behavior.
- UI-FIX-001: improved Album Review readability with a wider details panel, smaller preview box, and a taller score explanation area for multi-line visibility.
- Added UI tests for explanation panel minimum height and larger main-window minimum size.
- PERF-001: optimized Album Review scalability for large libraries (4,000+ photos) with lazy on-demand card rendering and reduced UI-thread work.
- PERF-001: added debounced search, card/preview pixmap caching, and selection-preserving details updates to avoid unnecessary full refreshes.
- PERF-001: added in-memory review pipeline cache in main window to avoid repeated scoring rebuilds when imported photos are unchanged.
- PERF-001: documentation and performance-safe tests added; no product behavior changed.
- Scope remains deterministic and local-only: no AI behavior changes, no export pipeline, no persistence/database support.

### Sprint DEV-004 - Album Scoring Engine
- Added AlbumScoringEngine to score AnnualAlbum selected candidates deterministically.
- Added AlbumScoreBreakdown dataclass with technical_score, memory_score, date_score, total_score, and explanation fields.
- Added AlbumScoringResult dataclass to return scored photos and scored count.
- Scoring now persists total score to PhotoIntelligence.album_candidate_score.
- Added tests for selected-only scoring, ignored non-selected pools, descending sort, score persistence, blurry technical penalty, missing intelligence safety, and explanation generation.
- Deterministic non-AI scoring only: no AI ranking, no face recognition, no duplicate detection engine behavior, no export pipeline, no database persistence, and no significant UI changes.

### Sprint DEV-003 - Candidate Selection Engine
- Added CandidateSelectionEngine to evaluate AnnualAlbum candidate pools deterministically.
- Added CandidateSelectionResult with selected/rejected counters and rejection reason summaries.
- Candidate evaluation now populates selected_photos and rejected_photos while preserving candidate_photos as the original pool.
- Added explicit non-AI rejection reasons: invalid_photo_object, missing_file_path, missing_year, and year_mismatch.
- Added tests for same-year selection, year mismatch rejection, missing intelligence safety, and result count accuracy.
- No AI ranking, no face recognition, no duplicate detection engine, no database persistence, and no export pipeline in this sprint.

### Sprint DEV-002 - Photo Intelligence Foundation
- Added PhotoIntelligence dataclass with safe grouped placeholders for basic, quality, people, duplicate, album, and AI-related fields.
- Updated Photo model to include optional intelligence and safe initialization in Photo.from_path().
- Added intelligence synchronization from metadata with derived year/month/date_taken when available.
- Updated metadata extraction to include year/month derivation from date_taken.
- Added tests for PhotoIntelligence defaults, Photo integration, and metadata-derived year/month.
- Maintained existing annual album foundation behavior (album builder tests pass).
- Foundation only: no UI redesign, no AI implementation, no face recognition, no duplicate detection engine, and no export pipeline.

### Sprint DEV-001 - Annual Album Foundation
- Added AnnualAlbum as the first Version 1 annual album domain model.
- Added AlbumBuilder for metadata-year filtering and annual album creation.
- Added initial tests for album foundation behavior.
- Foundation only: candidate initialization without selection or ranking engines.
- No UI changes in this sprint.

### Sprint D001 - Documentation Review
- Reviewed required repository documentation for consistency and single-source-of-truth alignment.
- Fixed cross-document responsibility boundaries (state vs roadmap vs changelog).
- Updated README, ROADMAP, PROJECT_STATE, HANDOVER, AI project docs, and sync queue to remove stale or conflicting documentation.

### Sprint 14 - UI polish and status synchronization
- Polished the custom photo card UI so cards show only the thumbnail and filename.
- Synced card and details-panel status updates from the current Photo object.
- Replaced internal processing status strings with user-friendly labels in the details panel.

### Sprint 13 - Batch photo grid loading
- Added progressive batch creation of photo cards for large folders.
- Fixed pending thumbnail update logic by switching to stable path-based keys.

### Sprint 12 - Custom photo grid foundation
- Replaced the unstable QListView-based photo grid with a custom PhotoCardWidget and PhotoGridWidget.
- Connected card selection to the metadata details panel.
### Added
- A custom photo-card grid foundation with progressive batch loading for smoother large-folder import behavior.
- Reusable PhotoCardWidget support for simple thumbnail-and-filename cards.
- A PhotoGridWidget for a custom QWidget-based photo browser experience.
- Basic EXIF metadata extraction for dimensions, date taken, camera info, and GPS presence when available.

### Improved
- The details panel now updates from custom photo-card selection.
- Thumbnail loading is hardened for large or invalid images while preserving cache usage.
- Pending thumbnail updates now use stable path-based keys, preventing crashes when thumbnails arrive before cards are created.
- Photo processing now updates a visible status lifecycle through the model and details panel, including pending, thumbnail_loading, thumbnail_ready, metadata_loading, ready, and error states.

### Notes
- The current UI now uses a custom card grid as the first step toward a more reliable custom photo browser.
- True virtual scrolling remains pending for very large photo libraries.

### LEARN-003.1 - Visual Feature Extraction Foundation
- Added reusable `VisualFeatureProfile` data for local, content-derived visual signals such as face evidence, text-like regions, document-like layouts, screenshot-like layouts, graphic/meme-like layouts, orientation, visual tags, evidence summaries, extraction status, and extractor version.
- Added `VisualFeatureExtractionService` as a deterministic local service boundary that reads image pixels, can reuse existing face-detection evidence, never modifies originals, and does not use filename, extension, EXIF, date source, file size, or camera metadata as visual evidence.
- Extended sidecar metadata persistence with backward-compatible visual feature profile storage and safe missing/corrupted fallback behavior.
- Updated category learning so learned rules can consume visual feature profiles and avoid generalizing from metadata-only correction evidence.
- Kept visual extraction out of synchronous import/UI refresh paths; background batch scheduling remains future work.

## TEST-001 — PySide6 test environment setup

- Added pytest configuration for deterministic test discovery and source imports.
- Added shared pytest setup for headless Qt execution via `QT_QPA_PLATFORM=offscreen`.
- Added a GitHub Actions test workflow that installs the Linux Qt/OpenGL packages required by PySide6 before collecting and running tests.
