# Changelog

## Unreleased
### Sprint MEM-006 - Image Preview on Double Click
- Added reusable image preview dialog for larger visual inspection from compact thumbnail grids.
- Enabled double-click preview opening from Memory Review and Cleanup Review cards.
- Added previous/next image navigation controls plus keyboard shortcuts (Esc, Left, Right).
- Preview now shows filename, media category, user decision, score when available, and visible-list position.
- Implemented original-image-first loading with thumbnail fallback and `Preview unavailable` messaging when media cannot be loaded.
- Added test coverage for dialog navigation, fallback behavior, Esc close behavior, and both page integrations.
- No persistence, no AI behavior, no classification/scoring rule changes, and no AlbumBuilder logic changes.

### Sprint CLEAN-003 - Cleanup Review UX & Explainability
- Replaced the Cleanup Review table workflow with a Memory Review-style visual workspace (toolbar filters, compact grid, right details panel).
- Added compact cleanup cards with thumbnail, filename, automatic category badge, confidence badge, and recommended action badge.
- Added structured explainability and low-confidence alternatives in the details panel for faster human validation.
- Added in-memory category correction chain (automatic -> user corrected -> effective) and explicit cleanup/category action buttons.
- Added category grouping view with counts, summary statistics, and batch-selection workflows.
- Added deterministic tests for cleanup-grid rendering, details updates, grouping/statistics, category correction, alternatives, selection, bulk actions, and safe move.
- No AI, no persistence, and no permanent deletion behavior added.

### Sprint CLEAN-002 (Refinement) - Improved Deterministic Initial Media Classification
- Refined deterministic classification priority to reduce false family-photo positives in ambiguous media.
- Expanded screenshot/document/advertisement/meme filename indicators, including common Italian terms.
- Added conservative WhatsApp/shared-image handling so ambiguous shared media defaults to unknown unless stronger photo evidence exists.
- Added camera-style filename pattern checks (IMG_/DSC_/PXL_/timestamp-like names) as positive family-photo evidence.
- Calibrated confidence and reasons to better reflect evidence strength for family-photo vs unknown outcomes.
- Added targeted test coverage for WhatsApp greetings, auguri graphics, Italian screenshot/invoice/promo names, camera-pattern photos, and weak-signal unknown cases.

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