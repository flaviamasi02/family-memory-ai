# Family Memory AI - UI Guidelines

This document defines the official User Interface standards for Family Memory AI.

It is the single source of truth for every future UI implementation.

Any future AI assistant modifying the UI must read this document first.

---

# General UI Philosophy

Family Memory AI should feel like:

- Google Photos
- Apple Photos
- Adobe Lightroom
- Notion

The interface must be:

- clean
- modern
- minimal
- calm
- responsive
- scalable
- focused on photographs

The photographs are always the primary content.

The interface should never feel like a developer tool.

---

# Design Principles

## Priorities

1. Photos first
2. Simplicity
3. Performance
4. Consistency
5. Accessibility
6. Scalability

Every new feature must integrate naturally into the existing interface.

---

# Photo Cards

A PhotoCard must contain only:

- thumbnail
- filename

Do NOT display:

- internal status
- debug information
- technical values

Future badges may include:

- ⭐ Favorite
- 😊 Smile detected
- 👤 Faces detected
- 📍 GPS
- 📅 Memory
- ❤️ AI Favorite
- Duplicate icon
- Cloud icon

These badges must be small and unobtrusive.

---

# Selection

Current baseline:

- one photo interaction at a time through card click
- details panel updates from the interacted card

Planned enhancement:

- persistent visible selected-card highlight (blue border preferred)
- highlight remains visible while scrolling

---

# Details Panel

Current fields:

- Selected Photo
- Filename
- File Size
- Dimensions
- Date Taken
- Camera
- Orientation
- GPS
- Status

Future fields:

- Lens
- AI Score (future)
- Faces (future)
- People (future)
- Duplicates (future)
- Story (future)

---

# Status Labels

Never display internal status values.

Display:

- 🟡 Pending
- 🔵 Loading Thumbnail...
- 🟢 Thumbnail Ready
- 🔴 Error

Reserved for future metadata/analysis flows:

- 🟣 Reading Metadata...
- ✅ Ready

---

# Icons

Prefer simple monochrome icons.

Avoid colorful icons except for:

- status
- favorites
- warnings

---

# Colors

Use a light neutral palette.

- Blue = selection
- Green = completed
- Yellow = processing
- Red = error
- Gray = inactive

Avoid aggressive colors.

---

# Typography

- Large readable filenames
- Secondary information smaller
- Never truncate important information if avoidable

---

# Performance Rules

The UI must always remain responsive.

- Never block the UI thread
- Large libraries (50,000+ photos) must remain usable
- Progressive loading is mandatory

---

# Future Features

Future UI additions include:

- Timeline
- Albums
- People
- Places
- Events
- Search
- Filters
- AI Assistant
- Story View
- Memory Timeline

---

# AI Rules

Any AI modifying the UI must:

- preserve visual consistency
- preserve existing design principles
- avoid redesigning the application
- update this document whenever UI decisions change

---

# Documentation Rule

Whenever a Sprint changes the user interface, update:

- docs/architecture/UI.md
- docs/project/PROJECT_STATE.md
- docs/releases/CHANGELOG.md

The documentation must always reflect the current implementation.


## Settings -> AI Models UI

Settings contains the current AI Models management surface. It must present runtime state as user-facing metadata, not as a developer console. The current MobileCLIP card shows provider, status, checkpoint, capabilities, CPU device, Python environment, model path, download/disk usage, licenses, verification, benchmark, and error state.

Valid actions are Inspect Python environment, View installation plan, Install, Cancel, Verify, Test, Open model folder, View logs, Remove model files, Dump AI metadata diagnostics, and bounded MobileCLIP evaluation source selection. Installation must remain confirmation-gated, and runtime operations must remain outside the UI thread.

MODEL-002E fixed a layout sizing issue where metadata labels contained text but could render as visually blank. Future UI changes must preserve explicit row sizing/geometry refresh behavior and keep diagnostics available for layout regressions.
