# Family Memory AI - Data Model

## Purpose

This document describes the data model architecture of Family Memory AI.

## Status

Initial placeholder created during documentation structure refactoring.

Detailed model documentation should reference:

- `Photo`
- `PhotoIntelligence`
- `AnnualAlbum`
- Candidate selection result structures

## MODEL-003A Persistent Embeddings

Image embeddings are stored by the existing application data layer, not in a parallel photo registry. The default store is `cache/embeddings/semantic_embeddings.sqlite3` under `ApplicationDataPathService` application data.

The `embeddings` table is keyed by image identity plus provider/checkpoint/revision, with an additional `model_key` index for fast lookup and invalidation. Each row records source fingerprint, source modified timestamp, source file size, provider id, checkpoint id, model revision, embedding dimension, compact float32 embedding BLOB, generated/updated timestamps, status, last error, and schema version.

Cache validity requires all of the following to match the current source image and runtime metadata: image identity, source fingerprint, source modified timestamp, source size, status `ok`, and `ModelMetadata.model_key`. `ModelMetadata.model_key` is centralized as provider id, checkpoint id, revision, and embedding dimension, so incompatible provider/model/checkpoint/dimension changes are regenerated automatically.

`BatchEmbeddingService.embed_images(...)` returns typed batch results with total received, processed, cached, failed, cancelled, elapsed time, and per-image outcomes. Progress callbacks receive the current index, total count, current image, processed count, cached count, and failed count. Cancellation is checked between images so no partial embedding row is written for an in-flight image.

Future import, background AI analysis, manual selected-photo analysis, and maintenance tools should call `BatchEmbeddingService` rather than touching the SQLite table directly. This PR intentionally does not add semantic search, similarity UI, classification, duplicate detection, clustering, face recognition, automatic post-import analysis, or permanent UI controls.

Developer diagnostic command:

```bash
python scripts/embed_folder.py <folder> --limit 20
```

The command uses the existing supported metadata image extensions, reports individual corrupt images as failures, and leaves original photo files unchanged.
