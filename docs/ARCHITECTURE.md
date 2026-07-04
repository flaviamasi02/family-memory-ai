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
  ui/
    main_window.py
  workers/
    thumbnail_worker.py
  cache/
    thumbnail_cache.py
```

## Current Responsibilities

| Folder | Purpose |
| --- | --- |
| src/ | Main application source code |
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

## PhotoGridView

PhotoGridView displays a grid of photos to the user.

It is responsible for:

- rendering thumbnails
- supporting scrolling and selection
- showing current photo state
- responding to user interaction

It should depend on models and data providers rather than performing processing directly.

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

- reading image files
- generating thumbnails
- storing results in the cache
- notifying the application when thumbnails are ready

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
- search
- recommendation

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
