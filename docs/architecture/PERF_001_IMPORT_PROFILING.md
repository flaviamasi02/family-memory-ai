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

PERF-001B is next and will use these measurements to select optimization work;
PERF-001A makes no performance-improvement claim.
