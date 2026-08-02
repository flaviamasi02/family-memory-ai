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

The follow-up applies styles only to the symmetric selection delta and updates
the count once. The same authoritative finalization call then replaces every
photo-specific detail field for the final active item. AI suggestions alone use
a separate 120 ms
single-shot timer, so rapid changes produce one suggestion for the final primary
photo. Request identity and primary-photo checks reject stale results. Selection
does not call filtering, sorting, scoring, persistence, thumbnail loading, or
grid rebuild code.

CI exposed why basic details cannot be deferred: selected keys and the active row
could change while a replaceable callback still represented an older selection,
leaving classification and pipeline fields stale. The final design synchronously
and deterministically replaces filename, category/source/reason/summary, visual
summary, confidence, decision, dates, pipeline/rejection, score explanations,
preview state, selectors, and suggestion display state. Missing values actively
write their defaults. Suggestion computation remains separately debounced and
guarded by its request generation and final active key.

Direct comparison with Cleanup Review also exposed two Memory Review-only costs
before highlight visibility: rebuilding the visible-key list/index on every
click, and toggling updates on the entire grid container. Visible-key indexes are
now built only when filters/sort change, and selection no longer disables and
re-enables the grid (which can schedule a full-container repaint). Only changed
cards receive style updates. Detail correctness is finalized once for the active
row; only suggestion computation remains asynchronous.

A reproducible 10,000-iteration median CPU benchmark compared the former
all-visible-card selection planning loop with the incremental delta calculation.
Results were: 1 item, 0.326 to 0.278 microseconds; 10 items, 0.653 to 0.452;
100 items, 3.993 to 2.037; 423 items, 15.472 to 6.614 (57.3% lower); and 1,000
items, 39.391 to 13.888 (64.7% lower). These are isolated selection-planning
measurements from the Linux test environment, not Product Owner end-to-end UI
latency. Runtime Developer Diagnostics remains the authority for UI timings.

After removing the remaining per-click visible-key rebuild, a second 10,000-run
median benchmark measured the complete selection-planning boundary (visible-key
index construction plus all-card membership checks before, cached index plus
selection delta after): 1 item, 0.680 to 0.278 microseconds; 10 items, 1.591 to
0.280; 100 items, 10.237 to 0.278; 423 items, 46.021 to 0.279 (99.4% lower);
and 1,000 items, 124.069 to 0.280 (99.8% lower). This isolates CPU work before
the repaint request; actual time-to-visible-highlight requires Product Owner/Qt
runtime diagnostics and is not inferred from the microbenchmark.

## Real-device diagnostic mode

The earlier optimizations did not produce a perceived improvement on the Product
Owner's Windows PC, so PERF-003 is not complete. Settings → Developer Diagnostics
now offers **Measure Memory Review selection**. It arms one aggregate real
interaction measurement and retains side-by-side Memory Review and Cleanup Review
reports without recording image paths or emitting per-card logs.

The report separates mouse/card handling, selected-key calculation, highlighting,
count update, detail/classification/preview work, preview loading, suggestion
scheduling/execution, synchronous time, and deferred completion. It includes
selection/card/style/repaint/layout/preview/thumbnail/detail/suggestion/grid/filter/
sort/row counts. Temporary process-local bypasses can independently skip preview,
details, suggestions, or selection styling; all default off and are reset when a
new Settings page is constructed. No optimization conclusion is drawn until the
Product Owner captures actual comparison results.

The first Product Owner diagnostic attempt remained at “No measured selection
yet.” The arming state was a single unscoped boolean and selection handlers
checked for any active workspace, allowing an unrelated Cleanup Review event or
incomplete run to consume or block the Memory Review measurement. Arming is now
workspace-scoped, clears incomplete active state, ignores events from the other
workspace, and displays “Waiting for Memory Review selection...” until the
matching interaction begins. Separate Memory Review and Cleanup Review buttons
populate their respective retained comparison reports.

The incomplete 1.7 ms value was the Python selection-handler duration, not
visible latency: it stopped before Qt painted the selected card and before queued
preview/suggestion work settled. The diagnostic now records handler completion,
first selected-card paint, Paint/LayoutRequest/UpdateRequest events, card and
viewport repaints, style polish, preview scaling/loading, details work, suggestion
execution, and total event-loop settling. The requested measurement appears at
the top of the report rather than below legacy aggregate history and includes a
completion timestamp and measured card counts.

Code-path comparison with Cleanup Review proved one extra synchronous image cost:
Memory Review scaled or loaded the right-panel preview inside `_show_details`
before returning from selection. Preview work is now a single replaceable 1 ms
deferred callback guarded by preview generation and the final selected key. Rapid
clicks coalesce it, stale previews cannot overwrite the final item, and the
selection highlight can paint before preview filesystem/scaling work. Basic text
details remain deterministic; AI suggestions retain their separate debounce.

## Second-and-subsequent Ctrl-click root cause

The authoritative Product Owner reproduction—first click immediate, later clicks
slow—isolated work created by the previous click. Memory Review alone schedules a
semantic suggestion scan on the UI thread. The prior 120 ms timer commonly fired
between ordinary Ctrl-clicks, so its evidence scan blocked delivery of the next
mouse event; Cleanup Review has no equivalent suggestion stage. The selection
handler also copied the growing selected set and computed a symmetric difference
even though a normal Ctrl-click changes exactly one known key.

Normal Ctrl-click now mutates and styles exactly that one key without copying or
comparing the selected set. Range, single, Select All, and Clear retain explicit
delta calculation. Suggestion work is treated as idle work with a single
replaceable 750 ms timer, while the preview uses one replaceable 1 ms timer.
Twenty rapid clicks therefore retain exactly one pending preview callback and one
pending suggestion callback; neither callback accumulates per click, and their
generation/current-key checks discard stale results. The 423-row Qt regression
asserts 20 card style calls for 20 additions, one more for a removal, unchanged
grid/thumbnail counts, exact final selection, and one active timer of each kind.

## Authoritative detail-row snapshot

The 423-row regression exposed an ambiguity that the earlier 100-row fixture hid:
score sorting means visible index 12 can be `photo_202.jpg`, not `photo_12.jpg`.
The test now selects the intended photos by stable photo key. Independently, the
runtime finalization now resolves that key exactly once and stores the resulting
row as the authoritative detail snapshot. All synchronous fields derive from that
row. Preview and suggestion timers capture the same detail generation and row
identity; callbacks must match generation, key, and object identity or are
discarded. Clearing selection, replacing page data, or changing filter/sort
invalidates both deferred contexts. The regression explicitly verifies
`photo_9.jpg → photo_12.jpg` and invokes a stale preview generation to prove it
cannot overwrite the final row.

## Duplicate CI determinism

The repository runs the same workflow for `push` and `pull_request`; there is no
step or dependency difference. A same-commit pass/fail split therefore exposed
test isolation rather than product behavior. The only wall-clock assertion in
the PERF-003 suite timed individual sub-microsecond calls, allowing scheduler/GC
noise to invert one push-run sample. It now measures 25 medians of 1,000-call
batches with GC restored afterward and retains a meaningful 20% improvement
threshold. In addition, the process-local selection diagnostic collector is
explicitly cleared before and after every Album Review, Cleanup Review, and
Developer Diagnostics UI test, preventing armed state, reports, bypasses, or
deferred Qt timers from leaking into later tests under a different collection
order. Assertions and product coverage are unchanged.

## Final suggestion timer determinism

The remaining CI failure was not a generation/key cancellation: after the normal
selection and Shift range selection, the pending row, request ID, detail
generation, current key, and authoritative row still matched. The timer itself
used Qt's default `CoarseTimer`. At a 750 ms interval Qt may coalesce a coarse
deadline by roughly 5%, which exceeds the regression's 30 ms observation margin
under CI load; the final callback then appeared missing (`suggest.call_count ==
0`) even though it remained pending. The timer now uses `Qt.PreciseTimer` with the
same 750 ms idle debounce. Intermediate selections still restart one single-shot
timer, while the final callback executes once against the authoritative row and
all stale generation/key guards remain unchanged. No selection-path work or
Product Owner-approved responsiveness changed.
