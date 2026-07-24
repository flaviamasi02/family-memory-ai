# Family Memory AI - Platform Strategy

## Status

Approved by the Product Owner on 2026-07-24.

Formal decision record: `docs/development/DEC-0049.md`.

## Decision

Family Memory AI will follow a **desktop-first, mobile-ready** product strategy.

The Windows desktop application remains the only active implementation target until the desktop core workflow is sufficiently validated on a real family photo library. The project will not build complete desktop and mobile applications in parallel.

At the same time, all new implementation work must preserve a clear separation between reusable product logic and the PySide6 presentation layer so that an Android application can later become a second client of the same Family Memory Engine.

## Product interpretation

Family Memory AI is not permanently defined as a Windows-only application.

It is a reusable Family Memory platform whose first client is the Windows desktop application.

The desktop application is the power tool for:

- importing and processing large historical libraries;
- background thumbnail generation and indexing;
- classification, duplicate analysis, and people intelligence;
- large-batch Cleanup Review and Memory Review;
- annual album generation, refinement, and export;
- local model management and heavier processing.

A future Android application will focus first on:

- reviewing recent photos;
- fast touch-first category correction;
- approve, reject, or pending decisions;
- identifying people and teaching preferences;
- lightweight album review;
- optional exchange or synchronization with the desktop application.

## Delivery sequence

### Phase 1 - Validated Windows desktop product

Continue the Windows application until the core workflow is genuinely usable and reliable:

1. import a large photo collection;
2. render thumbnails responsively;
3. classify and clean up photos;
4. recognize and manage family people;
5. score and select meaningful photos;
6. create a credible annual album draft;
7. review and correct results;
8. persist decisions and preferences;
9. export useful album output.

### Phase 2 - Incremental core separation

Core extraction is not a single future rewrite. It must happen incrementally during desktop development.

Reusable responsibilities should remain independent from PySide6 wherever practical, including:

- metadata and date extraction;
- classification and category semantics;
- duplicate and similarity logic;
- people intelligence;
- technical and memory scoring;
- profile and preference learning;
- album selection and draft generation;
- persistence contracts and stable identifiers;
- explainability and decision records.

### Phase 3 - Android companion MVP

Begin the Android product after the desktop core is validated and suitably separated from the UI.

The first Android milestone should be intentionally limited. It should prove photo-library access, a responsive mobile thumbnail grid, local review decisions, and reuse or faithful consumption of shared domain behavior.

### Phase 4 - Desktop/mobile exchange

Add export/import or synchronization for decisions, profiles, album state, and selected metadata. Synchronizing all original photo files is not required for the first connected workflow.

### Phase 5 - Greater mobile independence

Only after the companion workflow is stable should mobile take on heavier classification, similarity, duplicate analysis, or complete album generation.

## Permanent architecture rules

1. **Business logic must not live in UI widgets.**
2. **PySide6 is a presentation layer, not the product core.**
3. **Workers may coordinate platform execution but must not define product decisions.**
4. **Core services must use platform-neutral inputs and outputs wherever practical.**
5. **Photo, person, profile, album, and decision records require stable identifiers.**
6. **Persistence formats must remain portable or explicitly migratable.**
7. **Windows-specific file access must stay behind platform boundaries.**
8. **Every new feature should be designed as though a second UI will eventually consume it.**
9. **No large rewrite is approved solely to prepare for mobile; extraction is incremental and evidence-driven.**
10. **Cloud upload must not become mandatory merely to support mobile. Local-first and privacy-preserving behavior remains the default.**

## What is explicitly not approved now

The following are not part of the current execution scope:

- building full desktop and Android applications in parallel;
- rewriting proven Python logic in Dart immediately;
- reproducing desktop screens one-for-one on mobile;
- mandatory cloud storage or photo upload;
- processing the entire historical 50,000-photo library on a phone in the first mobile release;
- simultaneous Android, iPhone, Windows, and web development.

## Mobile start gate

Full mobile implementation may begin when the Product Owner and ChatGPT Quality Gate confirm that:

- the desktop application works on a representative real library;
- Cleanup Review and Memory Review are reliable;
- scoring and album drafts provide useful results;
- decisions and preferences persist correctly;
- core responsibilities are sufficiently separated from PySide6;
- the Android MVP has a clearly limited product scope.

The desktop application does not need to be commercially polished before mobile work starts. It must, however, have a validated and reusable core workflow.

## Documentation ownership

- This file is the canonical detailed platform strategy.
- `docs/development/DEC-0049.md` is the formal approved decision record.
- `docs/project/PROJECT_STATE.md` owns current operational adoption status.
- `docs/project/ROADMAP.md` owns transitional platform delivery phases.

Future architecture, planning, bootstrap, and workflow documentation must reference this strategy rather than redefining it independently.

## Decision identifier

**DEC-0049 - Desktop-First, Mobile-Ready Platform Strategy**.
