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

## Selection follow-up measurement

Product Owner testing of the first PERF-003 version found that rapid Memory
Review multi-selection was still visibly slower than Cleanup Review. Inspection
showed that every click reapplied a Qt stylesheet to every rendered card and
immediately rebuilt preview/details state; each detail refresh also queued an AI
suggestion. Range, select-all, and clear therefore paid one expensive card-style
update per rendered item even when most selection states were unchanged.

The follow-up applies styles only to the symmetric selection delta, disables
grid painting during that transaction, and updates the count once. One
authoritative finalization path then commits the active item and synchronously
refreshes its correctness-critical details. AI suggestions use a separate 120 ms
single-shot timer, so rapid changes produce one suggestion for the final primary
photo. Request identity and primary-photo checks reject stale results. Selection
does not call filtering, sorting, scoring, persistence, thumbnail loading, or
grid rebuild code.

CI exposed why details cannot share the suggestion debounce: selected keys and
the active row could be committed while a replaceable timer still represented an
older selection, leaving blank or stale filename, category, classification, and
pipeline fields. The simplified path owns selected keys, active key, changed
highlights, count, and details in that order. Only suggestion computation remains
deferred and guarded by its request generation and final active key.

A reproducible 10,000-iteration median CPU benchmark compared the former
all-visible-card selection planning loop with the incremental delta calculation.
Results were: 1 item, 0.326 to 0.278 microseconds; 10 items, 0.653 to 0.452;
100 items, 3.993 to 2.037; 423 items, 15.472 to 6.614 (57.3% lower); and 1,000
items, 39.391 to 13.888 (64.7% lower). These are isolated selection-planning
measurements from the Linux test environment, not Product Owner end-to-end UI
latency. Runtime Developer Diagnostics remains the authority for UI timings.
