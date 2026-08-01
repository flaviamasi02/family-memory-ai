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

UX-004 makes Developer Diagnostics lead with an **Import Efficiency** card
dashboard using plain-English labels: Photos processed, Already known photos,
New photos, Thumbnails reused, Embeddings reused, and Database work avoided.
Every card and technical metric has tooltip help. Existing avoided-work counters
are presented as File checks avoided, Path processing avoided, and Database
queries avoided without renaming their internal keys. Status is derived only
from collected counters and reads **Excellent reuse**, **Good reuse**, **Partial
reuse**, **Full processing required**, or **No completed import**.

Import Performance first shows completion time and the slowest activity. The
complete per-stage table, thread attribution, ms/item values, and developer
counters remain available in collapsed **Technical Details**. JSON export continues to use the original
internal counter keys and retains exact timings, thread attribution, environment,
and hardware information.
