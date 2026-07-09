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

- MainWindow: Application shell and workflow orchestration.
- AlbumReviewPage: Current hybrid review UI (toolbar + grid + details), in-memory review status actions, and large-library optimizations. Long-term direction: Memory Review.
- PhotoGridWidget / PhotoCardWidget: Card-based photo browsing and selection surface with batched initial rendering and scroll-triggered continuation for large folders.
- PhotoDetailsPanel: Selected-photo metadata and context presentation.

### Background and Performance Components

- ThumbnailWorker: Cache-first background thumbnail loading, generation, caching, and update signaling.
- ThumbnailCache: Reusable thumbnail storage to avoid repeated rendering cost.

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
