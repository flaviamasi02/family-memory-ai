# Family Memory AI - Project State

## Current Version

- Version: v0.1.0

## Current Sprint

- Sprint DEV-003 (Candidate Selection Engine) - Planned

## Project Status

- Status: In Development

## Last Updated

- 2026-07-05

## Overall Completion

- Estimate: Early prototype with a growing architecture foundation

---

# Executive Summary

Family Memory AI is currently in an early-stage desktop prototype phase. The application launches and supports a basic workflow around importing photos, scanning folders, generating thumbnails, and displaying a photo browser experience.

The immediate goals are to use the completed Photo Intelligence foundation to build deterministic candidate selection behavior while keeping the app stable and without adding AI or export features yet.

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
- DEV-003 Candidate Selection Engine: Planned

---

# Current Architecture

The current implementation is a lightweight Qt desktop application with a modular structure centered on the Photo model and a custom photo card experience.

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

---

# Current Limitations

- Temporary UI
- No true virtual scrolling yet
- Large folders still load progressively rather than instantly
- No database yet
- No AI scoring yet
- No deterministic candidate selection engine yet
- No face recognition yet
- No duplicate detection yet
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

# Next Sprint

## Title

Candidate Selection Engine

## Objective

Build the first deterministic candidate selection engine for annual albums using the Photo Intelligence foundation (without AI ranking).

## Expected Result

A deterministic flow that moves annual album photos from candidate_photos toward selected_photos/rejected_photos based on explicit non-AI rules.

## Files likely to change

- src/album/
- src/models/
- tests/

## Architecture impact

Medium

## Acceptance criteria

- The application remains functional.
- Deterministic non-AI rules can evaluate album candidates.
- Candidate photos can transition to selected/rejected states with reasons.
- Existing app import, thumbnail, details, and cache behavior remain functional.

---

# Upcoming Roadmap

See ROADMAP.md for the authoritative milestone plan.

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
| Completed Sprints | 16 |
| Architecture maturity | Emerging |

---

# AI Context

This document should be the first document read by any AI assistant before making implementation decisions.

It provides the current project status and operational context. The other project documents describe long-term direction and standards:

- [AI_DEVELOPER_GUIDE.md](AI_DEVELOPER_GUIDE.md)
- [ARCHITECTURE.md](ARCHITECTURE.md)
- [PRODUCT_VISION.md](PRODUCT_VISION.md)
- [CODING_STANDARDS.md](CODING_STANDARDS.md)
- [ARCHITECTURAL_DECISIONS.md](ARCHITECTURAL_DECISIONS.md)

PROJECT_STATE.md is the single source of truth for current version, active sprint, completed sprint count, and operational implementation status.

ROADMAP.md is the single source of truth for planned milestones.

CHANGELOG.md is the single source of truth for historical sprint changes.

---

# Update Rules

This document must be updated after every completed Sprint.

It should never be left outdated, because it is the operational memory of the project.

PROJECT_STATE.md is the operational memory of Family Memory AI. Every AI assistant should read this file before proposing changes to the project.