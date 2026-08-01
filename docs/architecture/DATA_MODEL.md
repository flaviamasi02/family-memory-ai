# Family Memory AI - Data Model

## Purpose

This document describes the data model architecture of Family Memory AI.

## Current managed-library model

DATA-001A–D are implemented and Product Owner validated. The current expected SQLite schema is **version 5**. Each registered root has one UUIDv4 `LibraryID`, one application-managed `metadata/libraries/<LibraryID>/family_memory.db`, and stable UUID `PhotoID` values for logical photos. The original folder contains no central database and original media is not modified. DATA-001E–H remain planned, so current sidecars, JSON profiles, the semantic cache, and face-foundation database still apply where their content has not migrated.

The implemented migrations are forward-only and checksum verified:

| Version | Name | Implemented purpose |
|---|---|---|
| 1 | `data_001a_foundation` | Creates `schema_migrations` and the library self-description row. |
| 2 | `data_001b_full_schema` | Adds migration/library operational fields and all approved central tables, constraints, foreign keys, and indexes. |
| 3 | `data_001c_import_registration` | Adds `import_runs.elapsed_time_ms` for durable normal-import registration results. |
| 4 | `data_001d_incremental_photo_sync` | Adds unchanged, added, removed, moved, renamed, and updated counters to `import_runs`. |
| 5 | `data_001d_classification_snapshot` | Adds the current classifier/relevance snapshot to `photos`, allowing unchanged/restart imports to rehydrate Cleanup Review without reclassification. |

### Implemented identity and synchronization tables

- `libraries`: primary key `library_id`; persisted root and `normalised_root_key`, schema mirror, lifecycle status, and created/opened/availability timestamps. The registry and database reuse the normalized root identity; the schema uniquely indexes the normalized root.
- `photos`: primary key `photo_id`, required `library_id`, optional preferred location, media/stat-derived metadata, content-hash fields, `status` (`active`, `missing`, or `deleted`), metadata revision, timestamps, and version-5 classifier snapshot (`automatic_media_category`, `effective_media_category`, `relevance_category`, `is_album_relevant_candidate`, `classification_confidence`, `classification_reason`). Indexes support library/status, capture date, content hash, and update time.
- `photo_locations`: primary key `location_id`, required photo/library relationships, absolute `source_path`, `root_relative_path`, normalized path key, filename/extension, byte size, nanosecond mtime, optional creation time, partial-fingerprint evidence/version, first/last seen run and timestamps, `removed_at`, and availability (`available`, `missing`, `deleted`, or `disconnected`). `(library_id, normalised_path_key)` is unique; indexes cover photo, fingerprint+size, last-seen time, and library availability.
- `import_runs`: primary key `import_run_id`, library/source relationship, lifecycle timestamps/status, schema/application version, errors, elapsed time, discovered/created/reused/changed/missing/skipped/failed counters, and the six explicit incremental counters. It is indexed by library/start time and status.
- `import_run_items`: primary key `import_run_item_id`; run plus nullable photo/location relationships; normalized path key; event (`created`, `reused`, `changed`, `missing`, `skipped`, `conflict`, or `failed`); fingerprint evidence/error code; and creation timestamp. `(import_run_id, normalised_path_key, event)` prevents duplicate outcomes; run/event and photo indexes support diagnostics.

A current location with `availability='available'` belongs to an active logical photo. When a previously available file is not observed, its location becomes `missing` and the photo becomes `missing` only when it has no remaining available location; rows and history are retained rather than duplicated or hard-deleted. A unique fingerprint-and-size relocation candidate preserves the PhotoID, marks the historical location missing, and creates the new available location. Path normalization uses normalized separators and OS case folding on Windows. The unchanged check uses normalized relative path, byte size, nanosecond mtime, and existing availability; the SHA-256 partial fingerprint covers size plus at most the first MiB and is conservative evidence, not a full-content identity guarantee.

The full schema also contains `embeddings`, `categories`, `photo_categories`, `reviews`, `albums`, `album_items`, `preferences`, `people`, `faces`, `face_embeddings`, and `metadata_migration_history`. Their presence does not mean legacy content has been migrated or that MODEL-004B/mobile synchronization is implemented. The authoritative detailed contract remains [DATA-001 — Central Metadata Storage Architecture Specification](DATA_001_CENTRAL_METADATA_STORAGE.md).

## MODEL-003A Persistent Embeddings

Image embeddings are stored by the existing application data layer, not in a parallel photo registry. The default store is `cache/embeddings/semantic_embeddings.sqlite3` under `ApplicationDataPathService` application data.

The `embeddings` table is keyed by image identity plus provider/checkpoint/revision, with an additional `model_key` index for fast lookup and invalidation. Each row records source fingerprint, source modified timestamp, source file size, provider id, checkpoint id, model revision, embedding dimension, compact float32 embedding BLOB, generated/updated timestamps, status, last error, and schema version.

Cache validity requires all of the following to match the current source image and runtime metadata: image identity, source fingerprint, source modified timestamp, source size, status `ok`, and `ModelMetadata.model_key`. `ModelMetadata.model_key` is centralized as provider id, checkpoint id, revision, and embedding dimension, so incompatible provider/model/checkpoint/dimension changes are regenerated automatically.

`BatchEmbeddingService.embed_images(...)` returns typed batch results with total received, processed, cached, failed, cancelled, elapsed time, and per-image outcomes. Progress callbacks receive the current index, total count, current image, processed count, cached count, and failed count. Cancellation is checked between images so no partial embedding row is written for an in-flight image.

Import/index integration and maintenance tools should call `BatchEmbeddingService` rather than touching the SQLite table directly. MODEL-003B adds automatic background embedding generation for missing or outdated images during import/index while reusing unchanged valid cache rows.

MODEL-003C adds semantic image similarity over stored embeddings. The similarity service reads current stored vectors, rejects stale/deleted/replaced/modified sources, rejects incompatible model keys or dimensions, excludes the source image, applies optional minimum thresholds, and returns deterministic top-N cosine-similarity results. It does not decode images, generate embeddings, alter categories, implement duplicate detection, or expose production semantic search UI.

Developer diagnostic command:

```bash
python scripts/embed_folder.py <folder> --limit 20
python scripts/similar_images.py <source-image> <folder> --limit 10
```

The command uses the existing supported metadata image extensions, reports individual corrupt images as failures, and leaves original photo files unchanged.

## MODEL-004A Face intelligence records

The platform-neutral `faces` domain adds stable `Face`, `Person`, and `FaceCluster` records plus a separately versioned `FaceEmbedding` cache record. Faces retain image identity, source fingerprint, bounding box, detector provenance/confidence, landmarks, quality metrics, optional Person/Cluster assignments, timestamps, and revision. Embeddings are keyed independently by provider/model/revision/dimension so future retraining does not replace Face or Person identity.

The SQLite persistence design supports multiple Faces per image, incremental upserts, stale-source filtering, targeted embedding invalidation, and relationship cleanup. The canonical design and compatibility rules are documented in `docs/architecture/FACE_RECOGNITION.md`.
