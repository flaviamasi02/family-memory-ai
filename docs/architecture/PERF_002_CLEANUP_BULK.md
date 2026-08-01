# PERF-002 — Cleanup Review Bulk Interaction Performance

## Measured root cause

The pre-change category loop persisted both learning profiles after every photo.
Each persistence recalculated the complete event-derived profile and rewrote its
JSON file, so a bulk action performed repeated growing work. It also rebuilt
every `CleanupReviewRow`, even when the active filter and ordering were unchanged,
and card refresh always smooth-scaled an unchanged thumbnail.

A reproducible lightweight benchmark (`tests/test_perf_002_cleanup_bulk.py`) uses
10, 100, and 1,000 synthetic photos. The legacy algorithm was reproduced by
running each correction outside a batch; the optimized path uses one batch. On
the sprint Linux runner, one controlled category-learning run measured:

| Photos | Before | After | Improvement |
| ---: | ---: | ---: | ---: |
| 10 | 44.3 ms | 1.1 ms | 97.5% |
| 100 | 135.5 ms | 8.2 ms | 94.0% |
| 1,000 | 11,470.1 ms | 82.2 ms | 99.3% |

These synthetic measurements isolate profile derivation/persistence and are not
a claim about a particular user's disk or complete UI latency.

## Implementation

- Category and preference learning retain every event but derive and save each
  profile once at the outer bulk-action boundary.
- Compatible per-photo sidecars remain in place. Failures are counted and the
  failed in-memory mutation is rolled back; successful corrections and learning
  events remain durable.
- Cleanup Review rebuilds only affected row projections. When filtering does not
  change membership, it refreshes affected rendered cards only. An unchanged
  thumbnail object is not rescaled. Filter membership is recomputed once and, if
  it changes, the grid is rebuilt once with existing thumbnail objects.
- Missing and null thumbnails always display the deterministic shared placeholder.
  Reuse is allowed only when the incoming and previous thumbnail objects and the
  currently displayed pixmap are all valid, so a later real thumbnail replaces
  the placeholder normally and an accidentally cleared label is repaired.
- A duplicate category submission is ignored while the action is active, and a
  concise busy/result label is shown. Widgets and the final refresh stay on the
  Qt UI thread. Sidecars remain synchronous because the current mutable Photo and
  singleton learning services do not provide a safe cross-thread transaction;
  the bounded batching removes the measured dominant repeated work without
  introducing unsafe Qt or shared-service access.
- One aggregate `[PERF]` record reports selection count, total/responsive time,
  sidecar/metadata/database/learning/UI timings, affected cards, rebuilds,
  thumbnail reloads, and update requests. Database time is zero because category
  history has not yet been cut over to central SQLite (DATA-001E–H remain planned).

## Behavioral boundary

Automatic categories are retained while manual effective categories change.
Custom/system IDs, learning events, selection, scroll restoration, preview,
filters, and source files keep their existing behavior. Memory Review is not
changed by PERF-002.
