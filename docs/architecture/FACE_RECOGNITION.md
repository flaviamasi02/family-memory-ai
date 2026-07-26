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
