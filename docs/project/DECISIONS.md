
## MODEL-002A — Generic AI Runtime Manager

Decision: manage MobileCLIP and future local AI providers through one generic AI Runtime Manager and one AI Models UI surface.

Consequences:
- Providers register descriptors and factories; the manager/UI must not be rewritten for every model.
- Installation uses explicit, typed plans and Product Owner confirmation; no silent dependency/model download is allowed.
- Runtime files, history, benchmarks, logs, and model cache live outside Git through `ApplicationDataPathService`.
- Runtime records can point to the current app environment, an existing environment such as `.venv-mobileclip`, or a future dedicated environment.
- MobileCLIP is registered first, remains evaluation-only, and managed installation/verification flow is implemented by MODEL-002B; Product Owner validation is still pending.

## MODEL-002B — MobileCLIP installation and verification

Decision: MobileCLIP installation is managed locally through the generic AI Runtime Manager and a dedicated Python environment rather than shell activation or ad hoc scripts.

Consequences:
- The selected interpreter is displayed, persisted, and used explicitly for every `python -m pip` command.
- Official Apple MobileCLIP source and `apple/MobileCLIP-S0` checkpoint metadata are recorded in the plan.
- Checkpoints live under application data outside Git and are downloaded only after confirmation.
- Ready requires full provider verification, not package presence.
- MobileCLIP stays evaluation-only; no original photos are modified or uploaded.

## IDEA 3 — Generic AI Runtime Manager approved

Decision: Family Memory AI must use one provider-agnostic AI Runtime Manager for current and future local AI models instead of one-off model-specific installers.

Scope:
- Implemented now: generic runtime registration, MobileCLIP as the first managed runtime, environment inspection, explicit installation plans, confirmation-gated execution, background workers, checkpoint handling, verification hooks, status/history records, and safe model-file removal.
- Future providers remain possible but are not implemented by this decision: Florence-2, SigLIP2, face-recognition models, OCR models, object-detection models, and other future local providers.

Permanent rules:
- The Runtime Manager owns registration, dependency checks, environment selection, installation plans, explicit confirmation, model storage, verification, status, logs, history, benchmark records, safe removal, and updates where supported.
- Photo processing remains local; no photo upload is allowed for these runtimes.
- No silent model download or silent dependency installation is allowed.
- Long-running AI operations must run outside the Qt UI thread.
- The base app must continue working without optional AI models.
- Model files, runtime metadata, user profiles, and learning data must stay outside Git-managed source files.
- Virtual environments, including `.venv` and `.venv-mobileclip`, must not be committed.
- Removal must never delete photos, thumbnails, categories, or learning profiles, and shared Python packages must not be silently removed.
- Automated tests must not download real models or install packages.

## MODEL validation and production-classifier policy

Decision: MobileCLIP remains evaluation-only until Product Owner-guided validation produces measured local evidence.

Consequences:
- MobileCLIP is the first managed runtime, but the production classifier has not been replaced.
- Florence-2 remains a possible later second-stage model, not current implementation.
- CPU-only compatibility is required.
- No black-box production classifier replacement is approved.
- Manual validation is required before documentation may claim runtime Ready status, installation success, real embedding quality, or performance results.

## Repository workflow, prompt, and cleanup decisions

Decision: Family Memory AI uses the permanent role split Product Owner = Flavia, ChatGPT = Chief Architect and Quality Gate, and Codex = Software Engineer.

Permanent workflow:
Product Owner -> ChatGPT specification -> Codex implementation -> ChatGPT review -> Product Owner manual test -> Product Owner approval -> merge -> repository cleanup.

Rules:
- Every code modification must be manually tested by the Product Owner before merge; automated tests do not replace Product Owner testing.
- Documentation-only PRs require documentation review but do not require launching the application unless they alter user-visible application help generated from code.
- Every GitHub/Codex implementation prompt must include the Codex link `https://chatgpt.com/codex`, repository link `https://github.com/flaviamasi02/family-memory-ai`, execution environment, estimated task size, purpose, expected outcome, base branch, instruction not to merge automatically, and Product Owner manual-test requirement.
- When correcting an existing PR, Codex must update the same PR and must not create a new PR unless explicitly instructed.
- After every merged feature or bug-fix PR, complete the repository cleanup checklist documented in `docs/development/AI_PROJECT_PLAYBOOK.md`.

## MODEL-002E metadata-rendering lesson

Decision: Settings -> AI Models metadata rendering defects must be diagnosed as UI layout problems before runtime/provider data is changed.

Consequences:
- Keep AI Runtime provider state generic and data-oriented.
- Inspect Qt widget hierarchy, grid rows, visibility, geometry, size hints, and layout ordering when metadata appears blank.
- Preserve explicit row sizing/geometry refresh behavior in the AI Models card.
- Use MODEL-003 for first real MobileCLIP image classification; do not mix classification behavior changes into runtime diagnostics or layout fixes.
