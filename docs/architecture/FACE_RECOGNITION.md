# MODEL-004A — Face Recognition Foundation

## Status and scope

MODEL-004A establishes the reusable architecture for future people intelligence. It does **not** detect faces, generate embeddings, cluster faces, recognize people, or change any user-visible workflow. Existing application behavior remains unchanged.

Later milestones will add capabilities behind these boundaries: MODEL-004B detection, MODEL-004C embeddings, MODEL-004D clustering, MODEL-004E person management, and MODEL-004F Memory Review integration.

## Dependency boundary

The `faces` package is platform-neutral Python and has no PySide6, OpenCV, InsightFace, DeepFace, or face-recognition-library dependency. Domain records do not expose model-library objects. Future desktop workers and mobile clients may orchestrate these services, but presentation and platform execution must remain outside this package.

MODEL-004A placeholders are deliberately inert: detection returns no candidates, clustering preserves existing clusters without calculating new ones, and embedding generation reports that it is unavailable rather than inventing vectors. They are not production algorithms.

## Domain model

- `Face` represents one face region in one stable image identity. It stores a stable UUID, source fingerprint, pixel bounding box, optional detector confidence and provenance, extensible landmarks and quality metrics, optional Person/Cluster links, timestamps, and an incremental revision.
- `Person` is the stable, manually nameable identity. An empty name supports an identity before naming; aliases, notes, and a future profile face support profile learning.
- `FaceCluster` is a stable automatic grouping that may later be linked to a Person without changing either identifier.
- `FaceEmbedding` is a separate, versioned cache record keyed by Face and provider/model/revision/dimension. Keeping vectors outside `Face` allows re-embedding and re-training without changing Face IDs or losing assignments.

All domain records provide JSON-safe `to_dict`/`from_dict` serialization. Bounding boxes, landmarks, confidence values, quality metrics, and model provenance remain library-neutral.

## Service and repository contracts

Provider/service protocols define detection, embedding generation, clustering, and person management. Repository protocols define face, person, cluster, and embedding loading, saving, updating, invalidation, deletion, and common queries. `RepositoryPersonManagementService` already supports manual person creation, renaming, face assignment, and unassignment without UI dependencies.

Future AI implementations must implement these contracts and use the Generic AI Runtime Manager for optional model lifecycle management. They must not add model installation or inference behavior to domain objects or repositories.

## Persistence and incremental updates

`SQLiteFaceRepository` defaults to application data at `data/faces/face_intelligence.sqlite3`; no records are stored beside original photos or in Git. Its schema supports:

- multiple Faces for one image;
- stable Face, Person, and Cluster IDs;
- nullable Face-to-Person and Face-to-Cluster assignments;
- bounding boxes, landmarks, quality values, confidences, and provenance;
- multiple embedding model versions for one Face;
- source-fingerprint validation, targeted invalidation, and cascade cleanup;
- upserts and revisions for incremental scans and manual corrections.

Foreign keys clear obsolete Person/Cluster links and cascade face-embedding deletion. Current embedding queries join the cached source fingerprint to the Face fingerprint, preventing stale vectors from being treated as usable after source reprocessing. A schema version gate reserves explicit migrations for future changes.

## Future integration rules

Memory Review may later consume Person and Face query services, but it must not access SQLite tables or AI providers directly. Manual names and assignments remain durable product decisions. Automatic clusters remain independent evidence and must not overwrite a manual Person assignment. Profile learning may select profile faces or build versioned embeddings while preserving source Face IDs and history.

## FACE-001 processing and lifecycle

`faces.eligibility.face_processing_eligibility` is the shared policy boundary. It uses stable category IDs and excludes manual opt-outs, inactive/Trash records, unsupported media, and non-photographic categories. Restoring a valid unchanged photo makes it eligible again.

The OpenCV detector is lazy and reads EXIF-oriented pixels locally. Pixel bounding boxes refer to that authoritative orientation. Padded crops live only in the application cache. The separate local face-crop descriptor is not MobileCLIP. Embeddings are finite, dimension-checked, source-fingerprinted and model-versioned. Conservative deterministic clustering is advisory and never supplies a name. Confirmed assignments are manual and audited.

Face data is sensitive. Settings can delete detections, crops, embeddings, clusters, proposals and confirmed assignments without modifying originals, categories, cleanup history or album decisions. No cloud inference, relationship inference, automatic naming, or album-score adjustment is part of FACE-001. Work is incremental and bounded; UI rendering and model initialization must remain off the synchronous full-library path.

### Managed Windows face runtime

Face detection runs in the application-owned `.venv-face-runtime`, never the
MobileCLIP environment or an arbitrary `cv2` import from the application
interpreter. The reproducible Windows/Python 3.10–3.12 set is
`opencv-python-headless==4.10.0.84`, `numpy==1.26.4`, and `Pillow==10.4.0`.
Install and Repair diagnose the interpreter and installed distributions, remove
all conflicting OpenCV wheels, reinstall the pinned set, and verify module
location, version, `cv2.data.haarcascades`, the frontal-face XML, and a non-empty
`CascadeClassifier`. Detailed interpreter and module paths remain in the runtime
log; normal UI messages distinguish downloads, permissions, environments,
conflicts, shadowing/model/API verification, and corruption.
