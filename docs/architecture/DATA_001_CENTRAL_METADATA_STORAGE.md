# DATA-001 — Central Metadata Storage Architecture Specification

Status: **DATA-001A–C implemented; automated validation complete; Product Owner validation pending**

Owner: Architecture
Last updated: 2026-07-28

This document is the authoritative technical contract for DATA-001. The durable decisions are recorded in `docs/development/DECISIONS.md`; this specification defines how later implementation increments must realize them. DATA-001A implements the application-data, registry, and minimal database/store foundation; DATA-001B implements schema version 2 and database operations; DATA-001C implements photo/import repositories and normal-import registration. DATA-001D–H, PERF-001, and MODEL-004B remain planned.

## 1. Executive Summary

Family Memory AI currently spreads durable data across photo-adjacent sidecars, application-data JSON profiles, and two purpose-specific SQLite caches. DATA-001 removes that fragmentation by giving every managed photo library one application-owned SQLite database named `family_memory.db`. Original photo roots remain immutable and contain no new app-generated metadata.

Central storage is required before PERF-001 so performance work can target stable identities, indexes, transactions, and queries rather than a storage design about to change. It is also required before MODEL-004B expands face recognition: face and person identity must join the same library identity and lifecycle instead of creating another independent database.

The target supports multiple independent libraries and at least 50,000 photos per library. SQLite is authoritative; thumbnails and model files remain disposable caches. Migration is staged, idempotent, observable, and non-destructive. Product Owner manual validation remains mandatory for every future implementation increment.

## 2. Goals

- Remove app-generated metadata from user photo folders and centralise it in application-managed storage.
- Support at least 50,000 photos in each of multiple independent managed libraries.
- Preserve current classifications, category corrections, review decisions, semantic embeddings, category definitions, learning/preferences, album state when it becomes durable, and future face/person data.
- Keep originals immutable while tolerating local, removable, network, and synced roots.
- Provide reliable backup, recovery, idempotent legacy migration, and forward schema evolution.
- Expose a stable persistence API to the Windows desktop application; remain platform-neutral below path adapters.
- Remain suitable for a future versioned portable export or mobile synchronisation boundary without implementing either.

## 3. Non-goals

- Cloud synchronisation, Android implementation, or a mobile UI.
- PERF-001 optimisation or a claim that semantic indexing performance has improved.
- MODEL-004B face detection or any new face-recognition behaviour.
- Rewriting EXIF or any original image bytes.
- Portable-library export, except internal backup artifacts required for safe migration.
- Replacing SQLite with a server database, splitting a library across databases, or storing logs in the database.
- Automatically deleting legacy metadata after migration.

## 4. Current-State Analysis

### 4.1 Persistence inventory

| Mechanism | Real path / owner | Current identity and behaviour |
|---|---|---|
| Per-photo sidecar | `<photo-parent>/<photo-stem>.familymemory.json`; `core.user_metadata_service.UserMetadataService` | Stores file path/name/size/mtime, automatic/corrected/effective category, cleanup or album decision, explanation, face summary, visual profile, suggestion feedback/acceptance, and writer metadata. It is read after fresh classification. Corrupt JSON is ignored. Size/mtime identity mismatch is tolerated when filename matches, otherwise metadata is not applied and a warning is returned. Writes are direct `write_text`, not atomic. |
| Category registry | `<app-data>/config/categories.json`; `core.category_registry.CategoryRegistry` | System and user category definitions; uses application-data paths and atomic JSON writes. |
| Category learning | `<app-data>/profiles/category_learning_profile.json`; `learning.category_learning_engine.CategoryLearningEngine` | Rules, event summaries, visual category profiles, and pending analyses; temporary-file replacement is used. |
| Preference learning | `<app-data>/profiles/preference_learning_profile.json`; `learning.preference_learning_engine.PreferenceLearningEngine` | Decision events and derived preference signals; atomic JSON write. |
| Legacy profiles | `<working-directory>/.familymemory/{categories.json,category_learning_profile.json,preference_learning_profile.json}` | `ApplicationDataPathService.migrate_legacy_files()` copies a newer legacy file into app data, backs up an existing destination, and writes `<app-data>/migration_diagnostics.json`; source files remain. The repository contains examples of all three. |
| Semantic embeddings | `<app-data>/cache/embeddings/semantic_embeddings.sqlite3`; `vision.embedding_provider.EmbeddingStore` | Float32 BLOB (legacy JSON is readable), keyed by resolved path plus provider/checkpoint/revision, with first-1-MiB SHA-256 fingerprint, size, and nanosecond mtime. WAL is enabled. A process lock serialises operations; each operation opens a connection. Invalid/stale files are filtered or marked invalidated. |
| Face foundation | `<app-data>/data/faces/face_intelligence.sqlite3`; `faces.persistence.SQLiteFaceRepository` | Independent SQLite database for people, clusters, faces, and face embeddings. Stable domain IDs and float32 BLOBs; WAL, foreign keys, per-operation connections, and an `RLock`. MODEL-004A foundation only. DATA-001 must absorb it rather than retain a second database. |
| Thumbnails | `<current-working-directory>/cache/thumbnails/<md5>.jpg`; `cache.thumbnail_cache.get_thumbnail_cache_path` | Disposable JPEG cache keyed by display version, resolved source path, size, and mtime. It is not authoritative and is currently cwd-dependent. |
| AI model/runtime data | `<app-data>/cache/models`, `<app-data>/ai-runtimes/*.json`, and `<app-data>/logs/ai-runtime/*.jsonl`; `ai_runtime.storage.AIRuntimeStorage` | Model files are cache-like shared application assets; installation/history/benchmark JSON and operational JSONL logs are application-scoped, not photo-library metadata. |
| Albums | `album.*`, `ui.main_window.MainWindow`, `ui.album_review_page.AlbumReviewPage`, and `ui.album_draft_page.AlbumDraftPage` | Annual albums, scores, selection results, draft pages, and the main-window pipeline cache are in memory. There is no durable album entity today. Review actions translate to `Photo.user_decision` and are persisted in the photo sidecar. |

### 4.2 Import and path behaviour

`core.photo_scanner.find_photos()` recursively walks every file, excluding `.familymemory.json` and the `_family_memory_deleted_review` / `_family_memory_cleanup_review` folders. It does not filter by extension at enumeration time. Each path becomes a new `models.photo.Photo` via `Photo.from_path()`, receives extracted filesystem/EXIF/date metadata, is classified, and then has a matching sidecar applied. There is no library registry, stable PhotoID, import-run record, database deduplication, deleted-file state, or relocation workflow.

Paths are primarily `pathlib.Path` objects and resolved absolute strings. The embedding cache treats resolved path + size + mtime + partial content fingerprint as identity, so a rename, move, or removable-drive-letter change is a new key. Sidecars move only if an external file operation moves them with the photo. `safe_file_move_service` explicitly moves associated sidecars, while quarantine folders are excluded on later import.

### 4.3 Failure, recovery, and UI coupling

- Sidecar parse failure silently falls back to fresh metadata; a write failure is handled by the calling page, which may roll back its in-memory action.
- JSON profile migration is newer-wins and diagnostic, but is not a complete per-library migration and has no transactional cross-file boundary.
- SQLite cache writes are individually transactional. WAL permits readers during writes, but neither existing database is the approved library database.
- Missing or changed embedding sources are skipped; bad vector lengths raise during decoding; failed generation rows retain an error/status.
- `ScanWorker`, `ThumbnailWorker`, `EmbeddingWorker`, and `FaceDetectionWorker` run background work. Main-window and review pages coordinate lifecycle and own current in-memory collections.
- Photo Browser consumes scanner/model metadata. Cleanup Review and Memory Review call `UserMetadataService` directly. Album Review reads in-memory score/pipeline rows and writes decisions to sidecars. Album Draft consumes the in-memory reviewed result. Settings, Category Management, and Learning Summary use application-scoped JSON services. No UI issues raw SQL today, and it must never do so.
- BUG-001B showed that persisted state, application startup ownership, cancellation, stale Qt wrappers, and shutdown must be designed together. DATA-001 workers must report results to application-owned services; UI objects must not own database connections or be treated as durable job state.

## 5. Target Storage Layout

```text
AppData/
  Local/
    FamilyMemoryAI/
      metadata/
        library_registry.json
        libraries/
          <LibraryID>/
            family_memory.db
            backups/
      cache/
        thumbnails/
          <LibraryID>/
        models/
      logs/
```

`AppData/Local/FamilyMemoryAI` illustrates Windows; all code must obtain the root from the platform-neutral application data directory provider, extending `ApplicationDataPathService`. One managed library maps to exactly one LibraryID and one `family_memory.db`. `library_registry.json` is the minimal application-scoped locator needed before a library database can be opened; it must contain no photo metadata.

Thumbnails and models are regenerable and non-authoritative. Logs stay outside the database. Backups are authoritative recovery artifacts but not live stores. A photo root may be local, removable, network-mounted, or inside a third-party synced folder; the database is never placed there.

## 6. Library Identity Model

- **LibraryID:** lowercase UUIDv4 generated once at registration, stored in the registry and the database `libraries.library_id`. It is stable and never derived from a path.
- **Registry:** records LibraryID, display name, root path, normalised root key, database relative path, created/last-opened timestamps, and status. Updates use atomic replacement. The database copy is authoritative after open; the registry is the bootstrap locator.
- **Root normalisation:** expand/absolute-resolve where possible, normalise separators, remove redundant segments and trailing separators, and apply platform comparison semantics (case-insensitive on Windows). Preserve the user-entered/display path separately. Do not resolve through an unavailable share.
- **Duplicate prevention:** before registration compare normalised keys; when accessible also compare operating-system file identity where available. A same physical directory expressed through case, separator, `.`/`..`, junction, UNC, or mapped-drive variants reopens the existing library. If physical equivalence cannot be proven, warn and require explicit confirmation rather than silently register.
- **Relocation:** changing a root updates its current location and records the previous location; LibraryID and PhotoIDs remain unchanged. Relocation reconciliation matches relative paths and file evidence before marking old locations missing.
- **Status:** `active`, `root_missing`, `disconnected`, `relocating`, `migration_required`, `migration_failed`, or `archived`. Missing/disconnected roots do not delete rows and can still expose metadata read-only. `last_opened_at` changes only after a successful database open/health check.
- **Schema version:** database schema state lives in `schema_migrations`; `libraries.schema_version` is a convenient checked mirror updated in the same migration transaction.

## 7. Photo Identity Model

- **PhotoID:** UUIDv4 allocated by `PhotoRepository`; stable across locations, names, and imports. Domain/UI objects carry PhotoID rather than use Windows paths as identity.
- **Photo versus location:** `photos` represents logical content and metadata; `photo_locations` represents observed files. This supports moves and intentional duplicate files without merging their review state accidentally.
- **Observed identity:** store source path, root-relative path, normalised relative key, filename, size, mtime in nanoseconds, optional creation time, availability, and last-seen import.
- **Fast import:** first match active location by `(library_id, normalised_relative_path)`. If size and mtime agree, reuse without hashing. Changed evidence schedules a partial fingerprint; do not hash every file on every import.
- **Fingerprint:** preserve the repository-supported SHA-256 strategy over size plus the first 1 MiB (and record algorithm/version). For better large-file collision resistance, the implementation may add a last-1-MiB segment under a new fingerprint version. A full SHA-256 is lazy: compute for ambiguous move/duplicate resolution, explicit verification, or portable export, and cache it until size/mtime changes.
- **Rename/move:** match an unmatched new location to one unavailable old location using full hash when available, otherwise unique partial fingerprint + exact size with conservative timestamp/creation evidence. Ambiguous matches remain separate/conflicted; never transfer user metadata on guesswork.
- **Duplicates:** identical full hashes may link multiple `photo_locations` to one PhotoID only after policy-confirmed logical equivalence. Otherwise retain distinct PhotoIDs and an optional future duplicate-group relation. Same filename is never sufficient.
- **Drive changes:** root-relative paths and stable LibraryID insulate domain identity from drive letters; relocation updates the root, not every domain entity.
- **Lifecycle:** unavailable observations become `missing`; confirmed absence after a completed scan becomes `deleted`/soft-deleted according to retention policy. Rows are retained. Reappearance at a proven former location or matching fingerprint restores `available` and the existing PhotoID.

## 8. Database Schema

All timestamps are UTC ISO-8601 text initially; IDs are canonical UUID text. Foreign keys are enabled. `created_at` and `updated_at` are required unless stated. JSON is permitted only for versioned, non-query-critical payloads; searchable state gets typed columns.

### 8.1 Required for DATA-001

| Table | Purpose and key | Important columns, constraints, and indexes | Lifecycle |
|---|---|---|---|
| `schema_migrations` | Ordered schema history; PK `version INTEGER` | `name`, `checksum`, `started_at`, `applied_at`, `status`, `app_version`, `error`; unique checksum/name as appropriate; index status | Append-only; failed attempts retained or represented in migration diagnostics outside a rolled-back DDL transaction. |
| `libraries` | Self-description for this database; PK `library_id` | `display_name`, `root_path`, `normalised_root_key`, `created_at`, `last_opened_at`, `schema_version`, `status`; exactly one active library row enforced by repository validation; unique normalised root while active | Never hard-delete during normal use; archive/status transitions. |
| `photos` | Stable logical photo identity; PK `photo_id` | `preferred_location_id`, `media_type`, dimensions/date/camera fields, automatic/effective category summary, classification provenance, content hash/algorithm/version, metadata revision; FK preferred location deferred/nullable; indexes date, status, updated time, hash | `status` active/missing/deleted; `deleted_at` nullable. Originals unaffected. |
| `photo_locations` | Mutable file observations; PK `location_id` | FK `photo_id`, `source_path`, `root_relative_path`, `normalised_path_key`, filename, size, mtime_ns, creation time, partial fingerprint/version, availability, first/last seen run; unique `(library_id, normalised_path_key)` for non-deleted rows; indexes photo, fingerprint+size, last_seen, availability | Retain historical location rows; `removed_at` and status support reappearance. |
| `embeddings` | Authoritative semantic vectors; PK `embedding_id` | FK `photo_id`; provider/checkpoint/revision/model_key/dimension/dtype/vector BLOB, source fingerprint, generated/updated time, status/error; unique `(photo_id, model_key)`; indexes model+status and source fingerprint | Regenerable but authoritative record of available analysis; invalidate/replace transactionally, do not hard-delete on model change. |
| `categories` | Library category definitions; PK `category_id` | display/description/AI description/color/icon/system/cleanup/album flags, source; unique case-normalised display name among active user categories; indexes flags | Soft delete user categories only after reassignment; system IDs stable. |
| `photo_categories` | Category assignments and provenance; PK `photo_category_id` | FKs photo/category; `assignment_type` (`automatic`, `user`, `suggestion`), confidence, reason, source/model, active, assigned_at; unique active `(photo_id, assignment_type)` where policy permits; indexes photo+active and category+active | Supersede old assignments; retain history. `photos.effective_category_id` may be a query projection, not sole history. |
| `reviews` | Cleanup/Memory/album decision history; PK `review_id` | FK photo; `review_type`, decision, source, reason, created_at, superseded_at; unique current `(photo_id, review_type)` via repository invariant/partial index; indexes type+decision and photo | Append/supersede, never overwrite history silently. |
| `albums` | Durable album header; PK `album_id` | title, album type/year, status, settings/version, created/updated; unique optional `(album_type, year, active)` decided by repository | Draft/archive/soft-delete. Initial migration may create none because current albums are in memory. |
| `album_items` | Ordered album membership/review; PK `album_item_id` | FKs album/photo; page/group key, position, decision, score snapshot/provenance, added_at; unique `(album_id, photo_id)` and `(album_id, position)` when positioned; indexes album order, photo | Soft remove or retain status for audit. |
| `preferences` | Library-scoped settings/learning payloads; PK `(scope,key)` | `value_json`, `value_type`, `schema_version`, updated_at; keys include migrated learning profiles until normalised later | Versioned values; no arbitrary UI SQL. Application-global runtime settings remain outside library DB. |
| `import_runs` | One scan/import execution; PK `import_run_id` | root snapshot, started/completed/cancelled times, status, counters, app version, error summary; indexes start/status | Append-only operational history. |
| `import_run_items` | Per-observation outcome; PK `import_run_item_id` | FKs run/photo/location nullable; source path or privacy-safe relative path, event (`created`,`reused`,`changed`,`missing`,`conflict`,`failed`), fingerprint evidence, error code; unique idempotency key `(run_id, normalised_path_key, event)`; indexes run+event, photo | Retained per configured diagnostic policy; redact sensitive values from logs, not DB metadata. |
| `metadata_migration_history` | Legacy migration attempt/source ledger; PK `migration_history_id` | source type/path fingerprint, source mtime/size/hash, target version, attempt ID, status, imported/reused/skipped/conflicted/failed counts, started/completed time, report path/error; unique successful source fingerprint+target version | Append attempts; successful identity prevents duplicates. |

### 8.2 Reserved now for MODEL-004 (schema may be created empty)

| Table | Purpose and key | Important columns, constraints, and indexes | Lifecycle |
|---|---|---|---|
| `people` | Stable person identity; PK `person_id` | display name, notes, representative face, status, timestamps; unique names are **not** required; index normalised display name | Soft merge/archive; foundation records migrate from the current face DB. |
| `faces` | Detected region tied to a photo; PK `face_id` | FK photo/person nullable; bounding box, detector/model/revision, confidence, landmarks/quality JSON, source fingerprint, cluster ID placeholder; unique detector identity as later specified; indexes photo, person, cluster | Invalidate when source fingerprint changes; retain corrected assignment history where required. |
| `face_embeddings` | Versioned face vector; PK `face_embedding_id` | FK face; provider/model/revision/model_key/dimension/dtype/vector BLOB, source fingerprint, status/error; unique `(face_id,model_key)`; indexes model+status | Regenerable and invalidatable. No detection is implemented by DATA-001. |

The empty future-compatible tables allow consolidation of existing MODEL-004A records but do not authorize MODEL-004B. Optional later extensions include `change_log` for sync/export, duplicate groups, saved searches, and richer assignment histories; none blocks DATA-001A.

## 9. Embedding Storage Decision

**Decision: store float32 little-endian vectors as SQLite BLOBs in `family_memory.db`, one row per PhotoID and exact model key.** A 512-dimensional vector is 2,048 bytes; 50,000 raw vectors are about 97.7 MiB before indexes/page overhead, acceptable for a library database and backups.

| Option | Assessment |
|---|---|
| SQLite BLOB | Atomic with source/model metadata, portable with the library backup, already proven by `EmbeddingStore` and face foundation, easy invalidation/versioning. Selected. |
| Separate binary cache | Smaller core backups only if excluded, but creates split-brain, orphan cleanup, non-atomic updates, and portability failures. Rejected as authoritative storage. |
| JSON vectors / another engine | JSON is larger/slower and retained only for legacy reads. A vector extension or ANN side index may be evaluated by PERF-001, but cannot become a second authoritative store. |

Rows include dtype, dimension, byte order (implicit by dtype contract), provider/checkpoint/revision/model key, source fingerprint, status, and timestamps. Invalid dimensions/blobs are quarantined logically and regenerated. Batch writes are transactional. Exact model-key changes invalidate reuse without deleting old rows. Search initially reads compatible vectors lazily/in batches; PERF-001 may add an optional disposable search index derived from these rows, but DATA-001 does not claim search acceleration.

## 10. Metadata Service Boundary

Build on current service/repository patterns (`ApplicationDataPathService`, `EmbeddingStore`, and face repository protocols):

- `MetadataStore`: owns open/close, connection factory, pragmas, transactions, schema initialisation, health check, and online backup. It does not classify, score, render UI, or access image pixels.
- `LibraryRepository`: registry and library descriptor/status/relocation operations.
- `PhotoRepository`: get/create by observation, metadata upsert, location reconciliation, missing/reappearing state, and paginated queries.
- `CategoryRepository`, `ReviewRepository`, and `AlbumRepository`: typed domain persistence and history.
- `EmbeddingRepository`: exact-model vector read/write/invalidate and transactional batches; it does not run models or compute similarity.
- `ImportRepository`: run/item lifecycle and counters.
- `MigrationService`: ordered schema and legacy metadata migrations, reports, compatibility gates, backups, retry, and rollback orchestration.

Required API includes `open_library`, `close_library`, `initialise_schema`, `get_or_create_photo`, `upsert_photo_metadata`, category and review reads/writes, album reads/writes, embedding reads/writes, `record_import_run`, transactional batch operations, `execute_migrations`, `health_check`, and `backup`. Return typed results and stable IDs. UI controllers call application services, which call repositories; no widget imports `sqlite3`, passes raw SQL, or owns connections.

## 11. Transaction and Concurrency Model

- Use a connection factory: one SQLite connection per thread/work unit, never one cross-thread connection. Connections are short-lived or explicitly scoped and are not stored in Qt widgets.
- Enable `foreign_keys=ON`, WAL, a documented busy timeout (initial recommendation 5 seconds), and normal synchronous mode; durability-sensitive backup/migration steps may use stronger settings.
- One application process is the supported writer. Repositories retry bounded `SQLITE_BUSY` failures with cancellation-aware backoff; they never spin indefinitely.
- Imports create one run, then commit bounded batches (initial recommendation 100–500 items, measured later). Embeddings use similarly bounded batches. Review actions use small immediate transactions and return success before UI state is final.
- Thumbnail workers do not write authoritative metadata. Embedding/face workers compute outside a transaction, then submit typed results to a repository transaction on their own connection.
- Cancellation is checked between files and before each commit. Completed batches remain committed and the run becomes `cancelled`; the in-flight batch rolls back. Retry reuses idempotency keys.
- Application-owned coordinators retain worker/thread references until `finished`, disconnect safely, and prevent a stale result from updating a newly opened LibraryID. Each task carries LibraryID and run ID. This directly applies the BUG-001B lifecycle lesson.
- Shutdown stops admission, requests cancellation, waits a bounded interval, commits or rolls back active work, closes thread-owned connections, checkpoints WAL when safe, and only then destroys Qt owners. Forced exit relies on SQLite atomicity/WAL recovery.
- Opening/migrating/backup operations take a per-library exclusive application lock; normal reads/writes use database transactions. A database cannot be migrated while workers are active.

## 12. Schema Versioning and Migrations

Schema version is defined by the highest successful ordered row in `schema_migrations`, mirrored to `libraries.schema_version`; do not rely only on `PRAGMA user_version`. Migration files/functions will be immutable, checksum-verified, monotonic, and forward-only. Downgrade requires restoring a compatible backup, not reverse DDL.

On open: acquire library lock, health-check, compare supported version, back up before any destructive/table-rebuild migration, run each migration in the largest safe transaction, verify invariants/foreign keys, record success, then release. A newer unsupported database opens read-only or refuses with a clear message. Failure rolls back the migration, preserves the backup and report, marks registry status `migration_failed`, and blocks normal writes. There is no silent reset, table drop, data truncation, or destructive coercion.

Tests require every supported-version fixture to reach latest, fresh creation equivalence, checksum/order enforcement, rollback on injected failure, backup restore, idempotent reopen, foreign-key/integrity checks, and an unsupported-newer-version case.

## 13. Existing Metadata Migration

### 13.1 Discovery and mapping

For a selected root and application data directory, inventory without writing:

| Legacy source | Target |
|---|---|
| `<photo-stem>.familymemory.json` | `photos`, `photo_locations`, `photo_categories`, `reviews`, face-summary/visual metadata columns or versioned preference payload where not yet normalised; suggestion feedback retained with provenance. |
| `<app-data>/config/categories.json` and legacy `.familymemory/categories.json` | `categories`; merge stable category IDs, flag definition conflicts. |
| `<app-data>/profiles/category_learning_profile.json` and legacy equivalent | versioned `preferences` entries initially (events/rules/profiles/pending analyses preserved); normalisation is optional future work. |
| `<app-data>/profiles/preference_learning_profile.json` and legacy equivalent | versioned `preferences`; preserve events and derived signals. |
| `<app-data>/cache/embeddings/semantic_embeddings.sqlite3` | `embeddings`, resolving legacy `photo_key` path to PhotoID; accept only decodable float32/legacy JSON rows whose dimension/model key/source identity are valid. |
| `<app-data>/data/faces/face_intelligence.sqlite3` | reserved `people`, `faces`, and `face_embeddings`, mapping `image_id` conservatively to PhotoID; unresolved records are conflicted, never guessed. |
| Current in-memory album/review pipeline | No album source exists to migrate. Sidecar `user_decision` migrates to typed review rows; no fabricated album is created. |
| `migration_diagnostics.json` | Keep as source evidence/report reference; do not treat it as library metadata. |

AI runtime installation/history/benchmark JSON is application-scoped and does not migrate into a library. Thumbnail JPEGs and models remain caches.

### 13.2 Algorithm and safety

1. Create a pre-migration database backup and immutable inventory/report outside the source tree.
2. Assign an attempt ID; fingerprint every source by canonical path, size, mtime, and SHA-256 where affordable. Record the attempt in `metadata_migration_history`.
3. Parse/validate sources without mutation. Corrupt sources are failed items with actionable paths; valid items continue unless a required invariant is threatened.
4. Establish PhotoIDs from current root observations. Map sidecars by adjacency plus stored identity. A filename-only fallback is a conflict requiring review, not an automatic match.
5. Import deterministic batches with source fingerprint + target version idempotency. Existing identical rows count as `reused`; new as `imported`; irrelevant/unsupported as `skipped`; ambiguous values as `conflicted`; exceptions as `failed`.
6. Resolve conflicts by precedence: explicit user correction/decision beats automatic classification; a valid newer record may beat an older identical-provenance record; contradictory user records remain a reported conflict rather than last-write-wins.
7. Validate counts, foreign keys, representative reads, embedding dimensions/model keys, and source-to-target reconciliation. Mark success only after validation.
8. Present a user-visible summary with imported/reused/skipped/conflicted/failed totals per source type and report location. Partial success remains `partial` and keeps compatibility reads for unresolved items.

Migration never deletes, renames, or rewrites legacy files. Rollback restores the pre-attempt database (or rolls back uncommitted batches), leaves the failed attempt report, and returns to legacy reads. Retry uses recorded fingerprints to reuse completed work and reattempt only unresolved/changed sources. Automatic cleanup is forbidden; a later approved cleanup step may offer user-controlled archival after confirmed backups and Product Owner validation.

## 14. Read Compatibility During Transition

1. **Inventory/read legacy:** current readers remain while SQLite foundation is introduced; database writes are not yet user-facing.
2. **Migrate:** pause relevant writers, migrate and validate, then write a per-library cutover marker transactionally.
3. **SQLite preferred:** after successful cutover, all authoritative reads/writes use repositories. A safe legacy read fallback is allowed only for a source explicitly recorded as unresolved and must never overwrite a SQLite value.
4. **Disable legacy writes early:** switch each metadata domain as one increment. Never dual-write JSON and SQLite. If an increment cannot atomically own a domain, it remains legacy-owned.
5. **Later cleanup:** remove fallback only in DATA-001H or a separately approved cleanup after telemetry/reports and Product Owner confirmation; old files remain untouched.

The migration/cutover state is explicit per domain (`legacy`, `migrating`, `sqlite`, `fallback_read_only`). Repositories reject a legacy write once state is `sqlite`; UI does not choose the backend. This prevents split-brain.

## 15. Backup and Recovery

- Use SQLite's online backup API from a read connection to a temporary file, run integrity checks, then atomically rename and write a manifest (LibraryID, schema, time, app version, checksum).
- Back up before migration, destructive maintenance, and on user request; define retention/configuration during implementation. WAL/SHM files are never copied as an ad-hoc backup.
- Restore only while the library is closed: retain the current DB, validate checksum, `quick_check`/`integrity_check`, LibraryID and supported schema, restore to a temporary path, then atomic replace.
- On startup, WAL recovery handles interrupted committed writes. Failed migrations use their pre-migration backup. Corruption opens no writable session; offer diagnostics, verified backup restore, or creation of a new library without deleting evidence.
- User-controlled export in DATA-001 means a database backup plus manifest only; originals, thumbnails, models, logs, and app-global AI runtime state are excluded. Portable library packaging remains a non-goal.

## 16. Error Handling and Observability

- Structured logs include event code, LibraryID, run/attempt ID, schema version, counts, duration, SQLite error class/code, and safe relative identifiers. Never log image bytes, embeddings, face crops, full metadata payloads, or user names by default; avoid absolute paths unless an explicit diagnostics export requires them.
- User messages distinguish disconnected root, busy database, unsupported version, corruption, migration conflict, partial import, and invalid embedding. They state whether originals were untouched and where a report/backup exists.
- Health checks cover openability, schema/checksum, `quick_check`, foreign keys, one-library invariant, and optional full integrity check on demand. Diagnostics expose WAL size and pending/failed run counts without raw sensitive rows.
- A corrupt JSON/row is isolated when safe, reported, and skipped; it must not trigger database recreation. An invalid embedding is marked invalid and regenerable. A missing file updates availability, not photo metadata deletion.
- Migration reports are structured JSON plus a concise user summary and respect privacy/redaction rules.

## 17. Performance Design Constraints

DATA-001 must enable, but does not implement, PERF-001:

- 50,000+ photos with indexed path, PhotoID, fingerprint, date/category/review, model-key, and import-run lookups.
- Bounded batch photo and embedding inserts; lazy vector reads; paginated photo/album/review queries with deterministic ordering.
- No full-table UI reloads or loading all embeddings at startup. UI receives pages/deltas and does not block on database/image work.
- Background-safe operations, predictable schema/open checks, and repeated imports that stat/path-match unchanged rows before hashing or image decoding.
- Query plans and index size are tested on representative large fixtures; WAL growth is bounded by checkpoints after large jobs.

Known baseline: the Product Owner measured approximately **190.643 seconds** for initial CPU semantic indexing of 422 photos. Repeated runs reuse cached embeddings. This is context only; optimisation remains PERF-001.

## 18. Security and Privacy

Storage is local-only and never implies cloud upload. Apply user-only file/directory permissions where the platform supports them; do not weaken inherited protection. The database contains sensitive paths, decisions, embeddings, and eventually face/person metadata, so backups and diagnostic exports receive the same privacy warning. Logs exclude sensitive image content and minimise paths/person data.

Synced source folders do not mean the application database is synced. Encryption at rest may be evaluated later (OS protection or SQLite-compatible encryption), including key recovery and performance, but is not mandatory or silently enabled by DATA-001.

## 19. Future Mobile Compatibility

Stable UUID LibraryID/PhotoID/entity IDs, UTC timestamps, typed repositories, explicit schema versions, relative source locations, and provider/model provenance form the compatibility boundary. Domain entities must not require drive letters, backslashes, registry APIs, or PySide6.

A future export/sync design may add an append-only change log, tombstones, conflict versions, and a versioned API/schema projection. It must not expose the live SQLite file as a cross-platform concurrent sync protocol. DATA-001 creates compatible identities and boundaries only; it does not design Android or synchronisation.

## 20. Implementation Plan

Every increment is a separate reviewable PR, leaves the application working, updates canonical docs/help if visible, runs automated checks, and requires Product Owner manual validation.

### DATA-001A — Application data paths and library registry

- **Scope:** target directories, platform provider extension, atomic registry, UUID LibraryID, root normalisation/status/relocation contract.
- **Included foundation for this approved implementation increment:** minimal
  `schema_migrations` and `libraries` tables, `MetadataStore` lifecycle,
  connection-per-work-unit transactions, pragmas, and health checks.
- **Excluded:** the full target schema, backup/restore, metadata migration, and UI redesign.
- **Dependencies:** this approved specification.
- **Tests:** path platforms/override, registry atomicity/corruption, duplicate path variants, disconnected/relocated roots.
- **PO result:** register/reopen/locate a library without changing originals; clear status for missing root.
- **Rollback:** registry backup/atomic file restore; old import remains usable.
- **Acceptance:** one stable ID and one minimal `family_memory.db` per registered physical root; no photo-adjacent writes added.

### DATA-001B — Full SQLite schema and migration operations

- **Scope:** extend the DATA-001A store with all approved DATA-001 tables,
  immutable ordered migrations, and online backup/restore foundations.
- **Excluded:** UI cutover, legacy content import, PERF-001/MODEL-004B.
- **Dependencies:** A.
- **Tests:** schema/constraints/indexes, migration ordering/failure/backup, concurrency basics, unsupported/corrupt DB.
- **PO result:** library health/backup diagnostics; normal application remains operational on legacy metadata.
- **Rollback:** delete only the new unadopted DB or restore backup; registry remains.
- **Acceptance:** exactly one `family_memory.db`, all required/reserved schema explicit, no second new DB.

### DATA-001C — Photo and import metadata repositories

- **Scope:** PhotoID/location identity, scan run/item records, repeat import, missing/reappearing/relocation reconciliation, read path integration.
- **Excluded:** category/review/embedding/album cutover.
- **Dependencies:** B.
- **Tests:** 50k fixture, path variants, move/rename/duplicates, cancellation, repeated/disconnected import.
- **PO result:** repeated import reports created/reused/changed/missing without duplicate photos.
- **Rollback:** feature gate returns import identity to legacy/in-memory path; new DB retained for diagnosis.
- **Acceptance:** stable PhotoIDs, transactional batches, originals unchanged, each cancelled run accurately recorded.

### DATA-001D — Category and review migration

- **Scope:** categories, sidecar classifications/confirmation/suggestion feedback, Cleanup/Memory/album decisions, learning profile preservation, SQLite write ownership for these domains.
- **Excluded:** embedding and album entity migration.
- **Dependencies:** C.
- **Tests:** real-format fixtures, conflict precedence, corrupt sidecars, idempotency, Cleanup/Memory/Photo Browser UI integration.
- **PO result:** existing categories and decisions appear unchanged; new edits survive restart without new sidecar writes.
- **Rollback:** before-cutover backup plus domain state reset to legacy; never dual-write.
- **Acceptance:** reconciled counts/report, legacy retained/read-only, sidecar writes disabled after cutover.

### DATA-001E — Embedding migration

- **Scope:** validate/import semantic cache rows as float32 BLOBs, exact model/source reuse, repository cutover, invalid-row regeneration status.
- **Excluded:** similarity optimisation/ANN/hardware work.
- **Dependencies:** C; D may run first to keep recommended order.
- **Tests:** BLOB/legacy JSON, dimensions/model revisions, stale/missing files, batch rollback/cancel, 50k size/query fixture.
- **PO result:** cached embeddings are reused after migration; invalid ones are clearly queued, not silently trusted.
- **Rollback:** restore DB and use untouched legacy cache read-only until retry.
- **Acceptance:** counts reconcile, one authoritative DB, no PERF-001 claim.

### DATA-001F — Album and preference migration

- **Scope:** durable album repository/UI state, preference/category-learning payload import, album review/draft restart persistence.
- **Excluded:** export/rendering redesign and scoring changes.
- **Dependencies:** D and C.
- **Tests:** empty current album source, CRUD/order/history, preference fixtures, UI restart and cross-library isolation.
- **PO result:** album/review draft state and library preferences survive restart and stay isolated by library.
- **Rollback:** domain cutover marker/backup; in-memory album remains safe until cutover succeeds.
- **Acceptance:** no fabricated legacy albums; current preferences preserved; application works after restart.

### DATA-001G — Legacy read compatibility and write cutover

- **Scope:** centralise backend selection, resolve partial migrations, enforce SQLite writes, bounded safe fallback reads, face-foundation consolidation if validated.
- **Excluded:** deleting legacy files, MODEL-004B behaviour.
- **Dependencies:** D–F and reserved face tables from B.
- **Tests:** mixed/partial states, split-brain rejection, fallback precedence, interrupted cutover, all affected UI pages.
- **PO result:** normal use no longer creates/updates photo-sidecar metadata; unresolved legacy records remain visible with warnings.
- **Rollback:** restore pre-cutover backup and explicit backend state, not dual-write.
- **Acceptance:** all authoritative domains SQLite-owned; any fallback is read-only, reported, and scoped.

### DATA-001H — Legacy cleanup readiness and operational hardening

- **Scope:** recovery UX, migration reports, integrity/restore validation, WAL/shutdown stress, cleanup-readiness report and user-controlled archival proposal.
- **Excluded:** automatic legacy deletion, PERF-001, MODEL-004B.
- **Dependencies:** G.
- **Tests:** crash/kill, corruption, lock contention, worker shutdown, backup restore, privacy, full regression and 50k soak.
- **PO result:** understandable health/migration/backup workflows and a confirmed working library; legacy files still retained.
- **Rollback:** verified restore; cleanup action remains disabled unless separately approved.
- **Acceptance:** operational runbook passes, no silent loss, Product Owner validates every workspace, DATA-001 may then be marked implemented.

## 21. Testing Strategy

- **Unit:** path normalisation, UUID/identity evidence, vector codecs, state machines, conflict rules, query pagination.
- **Repository:** every constraint/index/CRUD/history operation against temporary databases; foreign keys and transaction rollback.
- **Migration fixtures:** anonymised exact schemas/payloads for every format in section 13, including older/missing keys and current repository examples.
- **Idempotency:** rerun unchanged, partial, cancelled, and changed-source migrations; assert counts and no duplicate domain rows.
- **Corruption/interruption:** malformed JSON/BLOB/SQLite, injected migration and commit failures, process termination, WAL recovery and verified restore.
- **Concurrency:** simultaneous UI reads/review write/import/embedding batches; busy timeout/cancellation and no cross-thread connection use.
- **Scale:** at least 50,000 photos and representative embeddings; bounded memory, startup, pagination and import query plans (targets recorded before implementation).
- **Identity:** root relocation, UNC/mapped drive/case/separator variants, rename/move, missing/deleted/reappearing, true duplicates and ambiguous fingerprints.
- **UI integration:** Photo Browser, Cleanup Review, Memory Review, Album Review/Draft, Category Management, Settings/Learning Summary; no raw SQL or full reload.
- **Manual Product Owner:** backup real test metadata, migrate, reconcile summary, inspect representative classifications/reviews/embeddings, repeat/restart/disconnect/relocate, exercise recovery, and confirm originals/legacy files are unchanged.

## 22. Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Data loss | Pre-migration online backup, source retention, transactions, reconciliation, no silent destructive migrations. |
| Duplicate records | Stable IDs, normalised location uniqueness, conservative fingerprints, idempotency ledger, conflicts instead of guesses. |
| JSON/SQLite split-brain | Per-domain ownership marker; never dual-write; legacy fallback read-only. |
| Path/drive/share changes | Root-relative locations, stable LibraryID/PhotoID, relocation reconciliation, disconnected states. |
| Schema lock contention | Per-library migration lock, WAL, short/batched transactions, busy timeout/backoff, no migration with workers. |
| Worker shutdown/BUG-001B regression | Application-owned coordinators, task LibraryID/run tokens, cancellation and bounded join before connection/UI teardown. |
| Corrupt database | Health checks, verified online backups, read-only failure, evidence retention and restore workflow. |
| Invalid cached embeddings | Validate dtype/length/dimension/model/source; mark invalid and regenerate; never abort all metadata migration. |
| Excessive migration time | Inventory/progress, bounded commits, resumable idempotency, fast identity path, cancellation. |
| Cleanup Review, Memory Review, Photo Browser, Album regressions | Incremental domain cutovers, fixture/restart/UI tests, feature rollback and mandatory Product Owner checks. |
| Sensitive diagnostics | Structured redaction/minimisation; no image/vector/face payloads in logs. |

## 23. Acceptance Criteria

This architecture specification is complete when Product Owner review confirms:

- The one-library/one-`family_memory.db` layout, explicit schema, table lifecycle, keys, constraints, and indexes are sufficient for implementation.
- Stable library/photo identity and path relocation/duplicate/unavailable rules are explicit.
- UI-free service boundaries and connection/transaction/worker shutdown models are explicit.
- Legacy formats are exhaustively mapped from repository evidence; migration is idempotent, recoverable, counted, non-destructive, and prevents split-brain.
- Backup, schema migration, corruption, security, mobile-compatibility, scale, and testing contracts are actionable.
- DATA-001A–H have scope, exclusions, dependencies, tests, visible result, rollback, and acceptance; each leaves a working application.
- DATA-001 remains ahead of PERF-001 and MODEL-004B; neither is claimed started.
- No unresolved architectural question blocks DATA-001A and canonical documents contain no contradiction.

## 24. Open Questions

These are implementation calibration questions, not reopened durable decisions.

| Context | Options | Recommendation | Blocks DATA-001A? |
|---|---|---|---|
| Physical-folder equivalence when Windows file identity is unavailable (offline share or mapped drive) | Reject duplicate registration; warn and require confirmation; attempt network-specific identifiers | Warn, show the existing normalised candidate, and require explicit confirmation while recording the ambiguity. | No; implement normalisation and extensible comparison evidence. |
| Retention for import item history and automatic backups | Unlimited; count/time based; user setting | Start conservatively with documented count/time retention after measuring report size; never prune migration history or the only valid backup automatically. Product Owner approves defaults in B/H. | No. |
| Whether to create empty MODEL-004 tables in schema v1 or add them immediately before face consolidation | Create now; deferred ordered migration | Create the minimal reserved tables now because the approved single-database boundary and existing MODEL-004A database make their purpose concrete; do not expose detection behaviour. | No. |

No open question changes Windows-first/mobile-ready direction, the database name/count/location, original-file immutability, migration safety, roadmap order, or mandatory Product Owner validation.

## DATA-001A implementation note (2026-07-28)

DATA-001A extends `ApplicationDataPathService` with idempotent `metadata/libraries`, `cache/thumbnails`, `cache/models`, and `logs` paths. Windows resolves from `%LOCALAPPDATA%/FamilyMemoryAI`; constructor and environment overrides isolate tests. The application-level locator is the specification-approved, atomically replaced `metadata/library_registry.json` (registry format version 1). It stores UUIDv4 LibraryIDs, display and normalised roots, timestamps/status, schema mirror, and a database-relative path. Windows comparison keys normalise case, slashes, redundant/trailing separators, and absolute input. Disconnected mapped/network roots cannot be proven physically equivalent without access; DATA-001A does not content-scan them.

Each registration creates only `metadata/libraries/<LibraryID>/family_memory.db`; it never writes below the source root. The minimal schema contains `schema_migrations` and the database self-description `libraries` row. Version 1 is transactional, checksum-labelled, forward-only, and configures foreign keys, a 5-second busy timeout, WAL, and normal synchronous mode. `MetadataStore` provides open/close, initialise/version/health, database and LibraryID properties, and connection-per-work-unit transactions; no connection is shared between PySide6 workers.

Existing sidecars, JSON profiles, embedding/face caches, import, review, album, and MobileCLIP flows remain authoritative and unchanged. No metadata migration, compatibility fallback, write cutover, legacy deletion, cache move, or original-photo mutation occurred. DATA-001B–H remain planned. Manual validation: run `PYTHONPATH=src python -m storage.diagnostics`, confirm the reported application root and library count, then use a temporary diagnostic script/service call to register a test folder, open it, and confirm the UUID directory, `family_memory.db`, schema version 1, healthy result, and an unchanged source folder. Product Owner approval is required before merge.

## DATA-001B implementation note (2026-07-28)

DATA-001B adds immutable migration version 2, `data_001b_full_schema`, after the unchanged version-1 `data_001a_foundation`. Version 2 extends migration and library self-description fields and creates `photos`, `photo_locations`, `embeddings`, `categories`, `photo_categories`, `reviews`, `albums`, `album_items`, `preferences`, `import_runs`, `import_run_items`, `people`, `faces`, `face_embeddings`, and `metadata_migration_history`. Primary/foreign keys, state and numeric checks, library/path/model/idempotency uniqueness, partial current-record indexes, album ordering, and expected lookup indexes prepare repository work without populating any table.

`MetadataStore` verifies ordered migration names and SHA-256 checksums, rejects newer schemas, applies each migration under a per-store re-entrant operation lock and `BEGIN IMMEDIATE`, and rolls a failed migration back without recording it. Health reports database/LibraryID, actual and expected versions, integrity and foreign-key results, migration consistency, missing required tables, newer-schema state, read/write availability, and overall status.

`backup(destination_path, overwrite=False)` uses SQLite's online backup API into a temporary file, integrity/schema-validates it, and atomically publishes it; destinations are never silently overwritten. `validate_backup(path)` rejects corrupt, incomplete, foreign-key-invalid, and unsupported databases. `restore(path)` validates first, retains a uniquely named pre-restore safety copy, stages and atomically replaces the live database under the exclusive operation lock, clears stale WAL companions, and health-checks the replacement; failure restores from the retained safety copy.

Diagnostic usage is explicit and non-destructive: `PYTHONPATH=src python -m storage.diagnostics --help`, then `root`, `list`, `register <chosen-test-root>`, `open <LibraryID>`, `backup <LibraryID> <destination>`, or `validate <LibraryID> <backup>`. Use `--app-data-root <temporary-directory>` to isolate validation. Registration never occurs implicitly.

This increment makes **no persistence cutover**. Normal import is not connected to SQLite; no photos, imports, categories, reviews, embeddings, albums, preferences, face data, JSON, or sidecar content were migrated. Current legacy sidecars, JSON profiles, semantic cache, face-foundation database, and in-memory albums remain authoritative, and original photo folders remain untouched. DATA-001C–H remain planned before PERF-001 and MODEL-004B.

Product Owner manual validation is mandatory: use a temporary app-data root and explicitly chosen test photo directory; register/open it; confirm schema version 2 and healthy diagnostics; create and validate a backup; add disposable test metadata through a test script, restore, and confirm the safety copy and restored health; run the current application/import, Cleanup Review, Memory Review, Photo Browser, album draft, MobileCLIP verification and repeated semantic-cache flow; finally confirm the source tree, legacy sidecars/JSON, and existing cache files are unchanged. Do not merge until ChatGPT has reviewed the pull request and GitHub Actions and the Product Owner has completed this checklist.

## DEV-007 — Developer Diagnostics UI (2026-08-01)

Settings now includes a collapsed-by-default **Developer Diagnostics** section backed by the application-composed `ApplicationServices`, `LibraryRegistry`, and `MetadataStore`. It displays the application-data root, registry count, active library/database identity, actual and expected schema versions, integrity and foreign-key results, migration consistency, missing tables, and read/write availability. It can refresh, explicitly register an operator-chosen test folder, open a selected registered library, run health and schema summaries, create or validate a backup, safely open managed folders, and copy a minimized plain-text report. The UI never opens SQLite directly and provides no SQL console, Restore, Delete, scan, or migration action.

The command-line diagnostic remains available, but it is no longer required for normal Product Owner validation. In Settings, expand Developer Diagnostics; select **Register Test Library** and choose an empty disposable folder; confirm one stable LibraryID and the application-managed `family_memory.db`; confirm schema version 2; run Health Check; create and validate a backup with the standard dialogs; confirm the selected folder stayed empty; then exercise normal import, MobileCLIP, Photo Browser, Cleanup Review, Memory Review, and album behavior. Registration remains explicit, normal import is still disconnected from SQLite, legacy content remains authoritative and unmigrated, and DATA-001C remains the next metadata increment.

## PR #46 mixed-folder import regression correction (2026-08-01)

Manual validation exposed a pre-existing scanner defect rather than a DATA-001B database cutover: `photo_scanner.find_photos()` accepted every regular file except the exact `.familymemory.json` suffix and quarantine folders. Consequently project files, arbitrary JSON, SQLite main/WAL/SHM files, and extensionless files became `Photo` objects, entered the Photo Browser/review/album collections, and incurred per-file stat, metadata/date extraction, classification, sidecar lookup, card construction, and thumbnail-queue iteration. PR #46 did not introduce that unbounded rule—the DATA-001 architecture current-state inventory already recorded it—but explicit diagnostics made mixed folders and managed database artifacts more visible during Product Owner validation. Both the incorrect cards and most of the observed preparation slowdown share this root cause.

`core.supported_media` is now the single extension contract: JPG/JPEG, PNG, WebP, HEIC/HEIF, MP4, MOV, AVI, and MKV, case-insensitively. The scanner rejects everything else before `Photo` construction or metadata work. Scanner output is the trusted import collection passed unchanged through Photo Browser, Cleanup Review, Memory Review, albums, semantic indexing, and lifecycle queues; filters are not duplicated in orchestration. Thumbnail decoding retains an extension safety guard, while unsupported real filesystem entries never reach it. Instrumentation reports filesystem entries, regular files, supported candidates, unsupported skips, and final scanned media, providing exact before/after counts without wall-clock assertions. A filename may contain any number of dots and hidden names remain eligible only when their final extension is explicitly supported.

Normal import still never registers or opens a managed library, performs a health/schema/backup operation, or scans application-data storage. Developer Diagnostics remains explicit and isolated. DATA-001C was not started, and existing legacy sidecars are neither deleted nor migrated; they are simply excluded as unsupported import candidates.


### CI lifecycle boundary correction (2026-08-01)

The first mixed-folder correction redundantly filtered already trusted collections in `MainWindow._on_scan_complete()`, `load_photos()`, `start_thumbnail_loading()`, and `ThumbnailWorker.__init__()`. That broke lifecycle type compatibility: mocked/prevalidated values such as `"photo"`, `"second"`, and `"second-photo"` were removed because they were not filesystem paths with extensions. Filtering now occurs only during filesystem discovery in `PhotoScanner`; downstream orchestration preserves trusted domain inputs unchanged. Real databases, WAL/SHM files, JSON/sidecars, project files, and all other unsupported filesystem entries remain excluded before Photo construction, metadata extraction, or thumbnail work.

## DATA-001C implementation note (2026-08-01)

DATA-001C connects the existing single-pass background import to managed metadata without changing the scanner, classification, sidecar, MobileCLIP, Cleanup Review, Memory Review, Album Draft, or semantic-embedding behavior. Import idempotently registers the selected root, opens its existing LibraryID when known, creates a durable `ImportRun` before scanning, and transactionally registers the scanner's existing `Photo` results afterward. Schema version 3 adds the measured elapsed-time field to import history; start/completion timestamps, terminal state, discovered/created/reused/changed/skipped/failed counters, and per-file outcomes are retained.

`PhotoRepository` allocates UUIDv4 PhotoIDs and provides create, update, PhotoID, relative-path, fingerprint/hash, and library-list operations behind `MetadataStore`. The registrar first matches the indexed normalized relative path, reuses stable PhotoIDs on repeated import and changed observations, refreshes `photo_locations`, and assigns the PhotoID to the existing domain object. It performs one durable run-start transaction and one batch transaction rather than per-photo connections or a duplicate filesystem walk. A failed batch rolls back all photo/location/items together and marks the independently durable run failed. Original folders and legacy JSON/sidecars remain unchanged and authoritative for their existing workflows; no legacy metadata is migrated. DATA-001D–H remain planned, and Product Owner manual validation is required before merge.
