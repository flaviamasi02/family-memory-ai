# Family Memory AI - Project State

## Current Version

- Version: v0.1.0

## Current Sprint

- Sprint 13

## Project Status

- Status: In Development

## Last Updated

- 2026-07-05

## Overall Completion

- Estimate: Early prototype with a growing architecture foundation

---

# Executive Summary

Family Memory AI is currently in an early-stage desktop prototype phase. The application launches and supports a basic workflow around importing photos, scanning folders, generating thumbnails, and displaying a photo browser experience.

The immediate goals are to strengthen the architecture, improve scalability, and move toward a more structured model/view-based foundation for future AI features.

## Sprint 9 Update

Sprint 9 established the permanent Photo domain model foundation. The Photo object now carries core file information, file dates, UI state, metadata, and safe future AI fields without introducing AI features or databases. Compatibility with the scanner, model, view, and thumbnail worker was preserved so folder import, recursive scanning, thumbnail generation, and cache usage continue to work.

## Sprint 9.1 Update

Sprint 9.1 removed the temporary 300-photo display limit from the import flow. The application now attempts to display all scanned photos instead of only the first 300. The existing thumbnail cache and background thumbnail loading remain in place. This is an intermediate step, and true virtual scrolling or lazy loading is still pending for very large folders.

## Sprint 10 Update

Sprint 10 introduced a lightweight foundation for progressive thumbnail loading. The photo model remains the single source of truth for photo data, the view remains a simple list-based grid, and thumbnail work now runs in batches through the background worker so the UI stays responsive while thumbnails are loaded progressively. This is a preparation step for future lazy loading and virtual grid work rather than the final implementation.

## Sprint 12 Update

Sprint 12 added a simple metadata details panel to the main window and fixed the startup crash caused by connecting selection signals before the photo grid view had a valid selection model. The view now connects its selection handling safely inside the model-binding path, allowing photo selection to update the details panel without destabilizing startup or thumbnail loading. A follow-up bug fix also corrected an incorrect PySide6 import in the details panel, replacing the dynamic import path with the standard Qt import so the application can launch cleanly. Additional hardening was added to thumbnail loading for very large images by switching to QImageReader with scaled decoding, which avoids the full-resolution allocation failure and keeps the app responsive while continuing to use the existing thumbnail cache. The selection flow was then tightened so clicking a photo now routes through the photo model into the details panel, and the details view shows filename, size, dimensions, date, camera information, and status when available. A further fix now handles invalid or corrupted JPEG files safely by catching decode failures in both thumbnail loading and metadata extraction, logging concise warnings, and allowing the import process to continue without crashing. A targeted click-selection bug fix also resolved the earlier crash caused by mixing selectionChanged and clicked flows. The list view now relies on clicked as the reliable selection trigger, so clicking a photo updates the panel without crashing. A fallback interaction change then simplified the flow further by using double-click as the reliable trigger for showing photo details, which avoids the unstable single-click behavior seen after thumbnail updates in QListView. This sprint also introduced a reusable PhotoCardWidget component as the first building block for a future custom photo grid. The component displays a thumbnail and filename, emits a click signal, and can be reused in later Sprint work without introducing AI or database features. The unstable QListView-based photo grid was finally replaced with a lightweight custom PhotoGridWidget built from PhotoCardWidget instances so clicking a photo card reliably updates the details panel. This is an intermediate step toward a fuller custom photo browser and does not yet add virtual scrolling or advanced layout behavior.quiring a redesign of the current grid. The current PhotoGridView implementation was then rewritten from scratch as a minimal clicked-based wrapper because the earlier patchwork selection logic had become brittle when thumbnails and list-item rendering changed. The new view keeps only the essential responsibilities: configure the icon view, receive a click, resolve the selected Photo from the model, and emit the selection signal. This keeps the app functional while preserving a clear path toward a future custom grid implementation.placing the current QListView-based view. Invalid files may still lack thumbnails or metadata, but the app remains responsive and continues processing the rest of the library.

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

---

# Current Limitations

- Temporary UI
- No true virtual scrolling yet
- Large folders still load progressively rather than instantly
- No database yet
- No AI scoring yet
- No face recognition yet
- No duplicate detection yet
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

Photo Grid Performance and Virtualization Foundation

## Objective

Improve the custom photo grid for large libraries by introducing a more scalable rendering strategy and reducing the cost of creating many card widgets.

## Expected Result

A smoother photo browser experience for large folders with better memory behavior and more explicit performance boundaries.

## Files likely to change

- src/ui/
- src/workers/
- src/cache/

## Architecture impact

High

## Acceptance criteria

- The application remains functional.
- The custom card grid remains responsive for large folders.
- Thumbnail loading continues to work with the existing cache.
- The architecture remains easy to extend for metadata and AI features.

---

# Upcoming Roadmap

| Milestone | Status | Priority |
| --- | --- | --- |
| Photo model | Planned | High |
| Photo grid view | Planned | High |
| Virtual scrolling | Planned | High |
| Metadata extraction | Planned | High |
| Blur detection | Planned | Medium |
| Smile detection | Planned | Medium |
| Face recognition | Planned | Medium |
| Duplicate detection | Planned | Medium |
| Memory scoring | Planned | Medium |
| Preference learning | Planned | Low |
| Storytelling | Planned | Low |
| Album generation | Planned | Low |
| Natural language search | Planned | Low |
| Android | Planned | Low |
| Commercial version | Planned | Low |

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
| Completed Sprints | 13 |
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

PROJECT_STATE.md represents the current implementation, while the other documents describe long-term direction and principles.

---

# Update Rules

This document must be updated after every completed Sprint.

It should never be left outdated, because it is the operational memory of the project.

PROJECT_STATE.md is the operational memory of Family Memory AI. Every AI assistant should read this file before proposing changes to the project.