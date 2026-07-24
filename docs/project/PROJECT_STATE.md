# Family Memory AI - Project State

## Current Version

- Version: v0.1.0

## Current Sprint

- PERF-004 (Staged load: Photo Browser first, secondary views deferred) - Completed
- UX-001 (Collapsible Workspace Information Panels) - Completed
- MEM-REVIEW-FIX (Asynchronous Memory Review loading and thumbnail synchronization) - Completed and manually validated

## Project Status

- Status: In Development
- Repository state: PR #30 (DOCSYNC after MODEL-003C) and PR #31 (desktop-first, mobile-ready platform strategy) are completed and merged.
- Performance state: asynchronous thumbnail loading, responsive import, deferred secondary workspace setup, and JPEG warning suppression are now part of the current baseline.
- UX state: reusable `WorkspaceInfoPanel` is integrated in all main workspaces with collapsible per-workspace persisted state (default expanded).
- Memory Review state: asynchronous loading diagnosis and root-cause fix are complete; manual Product Owner validation confirmed expected behavior.
- Current focus: MODEL-001 through MODEL-003C are complete through stored-vector semantic similarity; the next product milestone is not committed and requires Product Owner prioritization among possible semantic-embedding consumers.
- PR #28 is merged: MODEL-003B automatic background embedding generation during import/index is complete and manually validated.
- PR #29 is merged: MODEL-003C semantic image similarity over stored embeddings is complete and manually validated.
- MobileCLIP managed runtime is operational on the Product Owner Windows CPU machine through Settings -> AI Models.
- Persistent embeddings, automatic background embedding generation, and developer semantic similarity diagnostics are operational.
- Production automatic category classification is still not implemented. Semantic similarity is currently available through `scripts/similar_images.py`, not through the production UI.
- Near-duplicate workflow, clustering, similar-photo UI, automatic category suggestions, semantic search UI, and learning from corrections remain future work.

## Platform Strategy

- DEC-0049 is approved: Family Memory AI is desktop-first and mobile-ready.
- Windows desktop remains the only active implementation target until the core workflow is validated on a representative real library.
- Complete desktop and mobile applications will not be developed in parallel.
- New business and domain logic must remain outside PySide6 UI widgets wherever practical.
- Android is the planned second client, beginning with a limited companion MVP after desktop validation and sufficient core separation.
- Cloud upload is not mandatory for future mobile support; local-first privacy remains the default.
- Canonical details are defined in `docs/architecture/PLATFORM_STRATEGY.md` and `docs/development/DEC-0049.md`.

## Last Updated

- 2026-07-24

## MODEL chain current validation update

Completed chain and validation scope:

- [x] MODEL-001 — evaluation and provider direction.
- [x] MODEL-002A through MODEL-002F — runtime architecture, installation, diagnostics, and operational validation.
- [x] MODEL-003A — persistent batch embedding foundation, completed and merged. Do not treat this as a claim that every internal MODEL-003A requirement was separately manually validated beyond the later end-to-end validation evidence below.
- [x] MODEL-003B — automatic import-time embedding generation, completed, merged in PR #28, and manually validated.
- [x] MODEL-003C — stored-vector semantic similarity diagnostic, completed, merged in PR #29, and manually validated.

End-to-end Product Owner validation confirmed: import -> managed runtime embedding generation -> persistent storage -> stored-vector retrieval -> cosine similarity -> ordered top-N results.

Product Owner observed evidence on Windows CPU: app launched from the normal `.venv` with `python src\main.py`; MobileCLIP was verified through Settings -> AI Models with exit code 0, `embedding_dimension = 512`, and `tokenizer = true`; importing `C:\Projects\test 20` produced `[EmbeddingIndex] processed=20 cached=0 failed=0 cancelled=0 elapsed=31.581s`; and `python scripts\similar_images.py "C:\Projects\test 20\20210214_112224.jpg" "C:\Projects\test 20" --limit 10` returned 10 ordered results from 20 candidates while excluding the source image. The folder path is a validation record only, not a reusable setup requirement.

Reusable validation procedure: launch the app from the main `.venv`, verify MobileCLIP through Settings -> AI Models, import an image folder, wait for the embedding summary, confirm processed/cached/failed counts, run `python scripts\similar_images.py <source-image> <folder> --limit 10`, and confirm ordered similarity results. The 20-image run took about 31.6 seconds in one CPU-only Windows environment and is not a universal performance guarantee.

## UX-001 Update

- Added reusable `WorkspaceInfoPanel` in `src/ui/components/workspace_info_panel.py`.
- Integrated the panel in all main workspaces: Photo Browser, Memory Review, Cleanup Review, Album Draft, and Settings.
- Panels are collapsible with per-workspace persisted UI state.
- Default panel state is expanded for first use.
- The change adds concise workspace orientation only and does not introduce workflow progress indicators.
- Existing `WorkspaceHeader` and Workspace Help interactions remain active.

## Memory Review Fix Update

- Root cause was diagnosed before code changes: Memory Review could appear empty when review input had no usable date-year buckets and/or relevance filtering produced an empty review input set.
