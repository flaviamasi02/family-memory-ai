# PERF-003 — Memory Review Performance

## Measurement and root cause

PERF-003 instruments aggregate page load, score retrieval, database reads, grid
creation, filter/sort updates, selection, preview, suggestions, and thumbnail
updates. Developer Diagnostics reports the last, average, maximum, and sample
count for each operation, plus rebuild/update counters. Logging uses only
aggregate `[PERF]` records and never logs one record per photo.

Code-path measurements identified the primary avoidable work: every sort change
destroyed all rendered cards, recreated up to 100 cards, rescaled their retained
thumbnails, selected the first row again, and refreshed its preview/suggestion.
Row lookup during selection was also linear and repeated several times. Memory
Review does not issue SQL while refreshing; it consumes the import's rehydrated
photo projection. Score calculation occurs once per changed review signature and
the existing pipeline cache reuses it for identical input.

## Optimization

Sort-only changes now relayout existing cards instead of rebuilding them. This
preserves thumbnail objects, selection, and scroll position while avoiding card
construction and repaint churn. Row lookup is indexed by normalized path.
Pipeline refreshes retain the current filter, sort, search, and compatible
selection after the initial load. Full rebuilds remain for membership-changing
filters, are batched to the existing initial-render limit, and restore scroll.
Existing preview and category-suggestion caches remain authoritative; unchanged
detail selection continues to skip refresh.

The diagnostics counter `grid_rebuilds_avoided` provides direct measurable
evidence for the optimized path. No scoring, filtering, sorting, thumbnail,
suggestion, category, or Cleanup Review behavior is changed.
