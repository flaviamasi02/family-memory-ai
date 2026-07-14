
## MODEL-002A — Generic AI Runtime Manager

Decision: manage MobileCLIP and future local AI providers through one generic AI Runtime Manager and one AI Models UI surface.

Consequences:
- Providers register descriptors and factories; the manager/UI must not be rewritten for every model.
- Installation uses explicit, typed plans and Product Owner confirmation; no silent dependency/model download is allowed.
- Runtime files, history, benchmarks, logs, and model cache live outside Git through `ApplicationDataPathService`.
- Runtime records can point to the current app environment, an existing environment such as `.venv-mobileclip`, or a future dedicated environment.
- MobileCLIP is registered first, remains evaluation-only, and real installation is deferred to MODEL-002B.

## MODEL-002B — MobileCLIP installation and verification

Decision: MobileCLIP installation is managed locally through the generic AI Runtime Manager and a dedicated Python environment rather than shell activation or ad hoc scripts.

Consequences:
- The selected interpreter is displayed, persisted, and used explicitly for every `python -m pip` command.
- Official Apple MobileCLIP source and `apple/MobileCLIP-S0` checkpoint metadata are recorded in the plan.
- Checkpoints live under application data outside Git and are downloaded only after confirmation.
- Ready requires full provider verification, not package presence.
- MobileCLIP stays evaluation-only; no original photos are modified or uploaded.
