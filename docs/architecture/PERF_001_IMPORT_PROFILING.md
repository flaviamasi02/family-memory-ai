# PERF-001A — Import Performance Profiling & Diagnostics

PERF-001A adds measurement only; it does not optimize or reorder the import pipeline.
Each import owns an `ImportPerformanceSession` using Python's monotonic
`perf_counter()`. Aggregate stages include start/end values, elapsed time, item
counts, per-item averages, and UI/background thread attribution.

The existing scan, synchronization, metadata, thumbnail, embedding, review,
SQLite, and UI-refresh boundaries are instrumented in place. No filesystem walk,
query, thumbnail, or embedding is repeated. Structured `[PERF]` records are
aggregate-only and never emitted per photo.

Completed sessions are process-local and bounded to the last 20 imports. Developer
Diagnostics can select a previous session and export JSON with system context,
library size, stage timings, diagnostics, and future-facing hints.

## PERF-001B optimization result

PERF-001B retained these measurement boundaries and the import lifecycle while
removing duplicate work: the single filesystem traversal now reuses `scandir`
metadata and precomputes path projections, synchronization planning uses one
joined SQLite snapshot, inserted photo/location records are returned without
read-back queries, and synchronization plan lookup is constant-time. Developer
Diagnostics exposes aggregate avoided-stat, avoided-resolution, and avoided-query
counters.

A five-run synthetic 500-photo database-path benchmark measured median added
registration at 109.43 ms before and 95.12 ms after (13.1% lower). Median
unchanged planning was 11.85 ms before and 11.36 ms after (4.1% lower); because
that delta is close to run-to-run noise it is directional only. The latest
production semantic baseline remains 190.643 seconds for 422 photos; it was not
rerun here, so no MobileCLIP performance gain is claimed.

## Product Owner presentation

Developer Diagnostics presents the same counters under an **Import Efficiency**
summary using plain-English labels: Photos processed/reused, Thumbnails reused,
Embeddings reused, File checks avoided, Path processing avoided, and Database
queries avoided. Each reuse/avoided-work value includes an in-app explanation.
The summary status is descriptive rather than a performance score: a completed
import with a strict majority of photos reused and no newly generated thumbnails
or embeddings reports **Efficient reuse detected**; any other import with reused
photos reports **Some work reused**; a completed import without reuse reports
**Full processing required**; and an empty history reports **No completed import
available**.

The per-stage table remains visible. JSON export continues to use the original
internal counter keys and retains exact timings, thread attribution, environment,
and hardware information.
