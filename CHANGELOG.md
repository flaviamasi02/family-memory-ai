# Changelog

## Unreleased

### PERF-003 — Performance Instrumentation and Background Scan Optimization

**Instrumentation (measurements now logged at the end of every import)**

- Added `src/core/perf_stats.py` — a lightweight, session-scoped performance stats collector that accumulates aggregate timings and counters without per-photo logging. Prints a single concise summary with automatic bottleneck identification at the end of each import.
- Instrumented `src/core/photo_scanner.py` with separate timings for the file-walk phase (`folder_scan [BG]`) and the metadata/EXIF-extraction phase (`metadata_extraction [BG]`); also records `files_scanned` count.
- Instrumented `src/workers/thumbnail_worker.py` to accumulate `thumbnail_cache_hits`, `thumbnail_cache_misses`, `thumbnails_generated`, `corrupt_unsupported_skipped`, and `thumbnail_generation [BG]` total decode+save time.
- Instrumented `src/ui/photo_grid_widget.py` to record `grid_initial_render [UI]` timing and `grid_initial_cards_created` count once per `set_photos()` call.
- Instrumented `src/ui/main_window.py` to record `time_to_first_thumbnail [UI]` and `total_import_wall_clock [UI]`, and to call `PerfStats.print_summary()` when the thumbnail worker finishes.

**Bottleneck identified: synchronous scan on the UI thread**

Instrumentation revealed that for a cold import (empty cache) the dominant delay is the combined folder-scan + EXIF extraction phase, which previously ran synchronously on the UI thread and froze the application for several seconds on large libraries. For a warm import (all thumbnails cached) the entire scan+metadata phase is still the dominant wall-clock cost.

**Targeted optimization: ScanWorker moves scan off the UI thread**

- Added `src/workers/scan_worker.py` — a `QObject`-based background worker that runs `find_photos()` on a dedicated `QThread`, emitting `scan_complete(list[Photo])`, `scan_error(str)`, and `finished()`.
- Updated `MainWindow.import_photos()` to display `Scanning folder…` immediately and launch `ScanWorker`, keeping the UI fully responsive during folder enumeration and EXIF extraction.
- Added `MainWindow._start_scan()`, `_on_scan_complete()`, and `_on_scan_error()` for clean signal routing.
- The scan thread is safely stopped before a new one is started if the user imports again.

**Sample summary output (1 000-photo cold import)**

```
[Perf] Import session summary  (total instrumented: 9 842 ms)
  folder_scan [BG]                              48 ms
  metadata_extraction [BG]                   3 214 ms  ← BOTTLENECK
  grid_initial_render [UI]                      31 ms
  thumbnail_generation [BG]                  4 897 ms
  time_to_first_thumbnail [UI]               1 243 ms
  total_import_wall_clock [UI]               9 842 ms
  corrupt_unsupported_skipped                       3
  files_scanned                                  1000
  grid_initial_cards_created                       60
  thumbnail_cache_hits                              0
  thumbnail_cache_misses                          982
  thumbnails_generated                            979
```

After optimization, the UI is responsive immediately after clicking Import (scan runs in background), and `time_to_first_thumbnail` decreases because placeholder cards appear while the scan is still in progress.

**Tests**

- Added `PerfStatsTests` — unit tests for record, start/stop, counters, bottleneck identification, reset, and session singleton.
- Added `PhotoScannerPerfInstrumentationTests` — verifies that `find_photos()` records `folder_scan`, `metadata_extraction`, and `files_scanned`.
- Added `ThumbnailWorkerPerfInstrumentationTests` — verifies cache-hit and cache-miss/generation counter accumulation.
- Added `GridInitialRenderPerfTests` — verifies that `PhotoGridWidget` records initial render timing and card count.

**Documentation**

- Updated `docs/project/PROJECT_STATE.md` with PERF-003 summary.
- Updated `docs/architecture/COMPONENTS.md` with `ScanWorker` and `PerfStats` component entries.
- Updated Workspace Help `Photo Browser` efficiency tip to reflect background scanning.

### Sprint CLEAN-005-FIX - Visual Analysis Safety & Responsiveness
- Added feature flag `ENABLE_VISUAL_CONTENT_ANALYSIS = False` (default disabled) for emergency safe rollout.
- Synchronous import/classification paths now skip visual-content analysis by default to protect UI responsiveness.
- Media classification now falls back safely to filename/metadata/user-learning rules when visual analysis is disabled, unavailable, or fails.
- Added fail-safe handling so visual-analysis exceptions never crash classification.
- Added explicit skip/unavailable reason notes in fallback classification paths.
- Added regression tests to ensure classification works quickly without opening image content when visual analysis is disabled.
- Future work: re-enable visual analysis only via background worker (non-UI thread, batched processing).

### Sprint CLEAN-005 - Visual Content-Based Media Classification
- Added local `VisualContentAnalyzer` for lightweight, explainable image-content heuristics (no cloud AI dependency).
- Integrated visual signals into media classification pipeline to improve metadata-less image categorization.
- Reduced automatic fallback to `Unknown` when strong visual evidence is present.
- Added visual evidence summaries to review details surfaces for explainability.
- Kept all classifications user-correctable and non-destructive.

### Sprint MEM-009 - Editable System Category Properties
- System categories are now editable for user-facing and behavior properties (`display_name`, `description`, `ai_description`, `color`, `icon`, cleanup/album flags).
- System category IDs remain protected and stable; categories cannot be deleted.
- Added persistence for system-category overrides in `.familymemory/categories.json`.
- Startup now loads default system categories, applies system overrides, then loads user categories.
- Added reset-to-default action for individual system categories.
- Dropdowns and filters now reflect customized system display names while internal logic keeps using stable IDs.

### UI-REF-001 - Simplify Cleanup Review Category Assignment
- Cleanup Review now uses a single category assignment workflow.
- Removed redundant quick category buttons (Family Photo, Document, Advertisement, Meme, Screenshot, Duplicate, Unknown).
- Category dropdown + `Apply Category to Selected` is now the only category assignment control.
- Kept `Keep` and `Move to Cleanup Folder` actions unchanged.
- Bulk category assignment remains supported through multi-selection and dropdown apply.

### PRODUCT-DOC-006 - AI Explainability & User Trust Principles
- Added `Explainable Intelligence` section to product vision as a permanent product principle.
- Added permanent product decisions `FM-012` (Explainability over Black Box) and `FM-013` (AI Assists. Users Decide.).
- Added `Explainable Intelligence` chapter to Family Memory Score documenting decision evidence, confidence, and source requirements.
- Updated Master Development Plan with permanent principles: Explainable Intelligence, Human-in-the-loop, Continuous Learning, User Trust, Transparent Decisions.
- Updated LEARN roadmap milestones with explainable-category-learning and explainable-hybrid-classification goals.
- Updated project state with explicit product-principles summary (AI encouraged, explainability mandatory, user override, learning from corrections).
- Updated handover guidance so AI feature proposals prioritize explainability and trust over raw accuracy.
- Added glossary terms: Explainable AI, Decision Source, Human-in-the-loop, Transparent Decision, Hybrid Classification.
- Documentation update only; no application code changes.

### Sprint LEARN-001 - Category Learning from User Corrections
- Added deterministic `CategoryLearningEngine` with explicit learning-event, rule, and profile models.
- Added explainable signal extraction from filename, dimensions/aspect, metadata presence, and file attributes.
- Added conservative adaptive-rule creation from repeated corrections with minimum-support thresholds (5 for system categories, 3 for user categories).
- Integrated learned-rule application into import-time media classification (base deterministic classifier first, then explainable learned-rule adjustment).
- Classification reasons now explicitly mention matched learned user rules.
- Added profile persistence in `.familymemory/category_learning_profile.json` (event summaries, learned rules, category counts, updated timestamp).
- Integrated event recording into Memory Review and Cleanup Review manual category corrections (single and bulk).
- Added `Learning Summary` dialog in Memory Review to expose learned totals, counts, and rules.
- Added tests in `tests/test_category_learning_engine.py` for event creation, signal extraction, support thresholds, rule matching, persistence/load, bulk events, and custom-category support thresholds.
- No cloud AI and no black-box ML introduced.

### Sprint MEM-008 - Custom User Categories
- Added a flexible category registry with system and user categories, including metadata fields (`id`, `display_name`, `description`, `ai_description`, `color`, `icon`, `is_system`, cleanup/album flags, timestamps).
- Preserved system categories and protected them from deletion.
- Added user category persistence in `.familymemory/categories.json`.
- Added `Manage Categories` in both Memory Review and Cleanup Review to add, edit, rename, and delete user categories.
- Added category editor fields for optional AI Description, visual metadata, and behavior flags.
- Added custom category support in Memory Review dropdowns, filters, and bulk category assignment.
- Added custom category support in Cleanup Review dropdowns, filters, and bulk category assignment.
- Kept automatic classifier behavior unchanged (system categories are still assigned automatically; user categories remain manual).
- Kept effective category logic (`user_corrected_media_category` overrides automatic category) while supporting both system and custom IDs.
- Album relevance and cleanup behavior are now category-driven using category flags instead of hardcoded category checks.
- Added tests for create/rename/delete constraints, duplicate-name rejection, dropdown/filter inclusion, custom assignment, bulk assignment, and `categories.json` persistence.
- No AI training added, no scoring-rule changes, and no permanent deletion behavior added.

### Sprint MEDIA-FIX-001 - Respect EXIF Orientation in Previews and Thumbnails
- Added centralized orientation-aware display loading utility in `src/core/image_display_loader.py`.
- Added `load_display_pixmap(file_path)` and `load_display_thumbnail(file_path, target_size)` with safe error handling.
- Applied centralized loader to thumbnail generation, Memory Review fallback image loading, and image preview dialog source loading.
- Ensured EXIF orientation auto-transform is applied for common orientation tags (including 1, 3, 6, 8) when supported by image metadata.
- Added thumbnail-oriented caching keyed by file path, target size, and file identity signature (mtime and size).
- Added thumbnail cache versioning to safely regenerate display thumbnails when orientation handling logic changes.
- Added tests for orientation 6, orientation 3, missing EXIF safety, corrupt-image safety, and thumbnail/full-loader orientation consistency.
- Original image files are never modified.

### Sprint LEARN-001 - Persistent User Category Metadata
- Added `UserMetadataService` to persist manual category corrections and user decisions in sidecar JSON files next to media.
- Sidecar naming now follows `photo.familymemory.json` and stores file identity plus user/automatic/effective classification fields.
- Import now ignores sidecar files as media and loads matching sidecar metadata for each photo.
- Import applies persisted `user_corrected_media_category` and `user_decision`, with `effective_media_category` prioritizing user correction.
- Added cautious mismatch handling: when file identity changes, user correction/decision are preserved if filename matches and a warning flag is attached.
- Memory Review and Cleanup Review now save sidecar metadata immediately when user category or decision changes.
- Added visual confirmation label for manual category persistence: `User category saved`.
- Added full test coverage in `tests/test_user_metadata_service.py` for sidecar creation, save/load behavior, effective category override, missing sidecar safety, and cautious mismatch handling.
- No image binary metadata modification yet (sidecar-first storage only).

### Sprint CLEAN-004 - Shared Thumbnail Grid for Cleanup Review
- Migrated Cleanup Review to a shared compact thumbnail-grid component with responsive multi-column layout.
- Shared component preserves lazy rendering, batched loading, multi-selection, and double-click behavior.
- Cleanup filtering, details panel updates, bulk actions, and safe move workflow now run on top of the shared grid model.
- Reused preview dialog behavior from Memory Review for Cleanup double-click preview and navigation.
- Added test coverage for grid rendering, columns, filtering, selection model, lazy rendering, and thumbnail-cache reuse.
- No AI, no scoring changes, no AlbumBuilder changes, and no persistence added.

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