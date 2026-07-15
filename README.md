# Family Memory AI

Family Memory AI is a Family Memory Intelligence platform.

Its long-term mission is to help families preserve, organize, understand, and rediscover the memories that matter most while continuously learning what is important for each family. Albums are only one possible output generated from that knowledge, not the primary purpose of the system.

Historical implementation remains organized through completed DEV-XXX milestones. Future work follows domain-based milestones so new capabilities are planned inside functional areas such as Memory Review, Cleanup, Duplicate Management, Preference Learning, Memory Intelligence, and Outputs.

The highest-level planning document is docs/project/MASTER_DEVELOPMENT_PLAN.md.

Version: v0.1.0
Status: In development

## Quick Start

1. Install dependencies:
	pip install -r requirements.txt
2. Run the app:
	python src/main.py

## Documentation Entry Point

Start here for project context and current status:

- docs/bootstrap/HANDOVER.md
- docs/project/PROJECT_STATE.md

## Documentation Map

- docs/project/DOMAIN_ROADMAP.md: Official domain-based future roadmap
- docs/project/MASTER_DEVELOPMENT_PLAN.md: Highest-level product planning document
- docs/project/ROADMAP.md: Planned milestones and priorities
- docs/releases/CHANGELOG.md: Sprint-by-sprint implementation history
- docs/project/PROJECT_STATE.md: Current operational state (single source of truth for current sprint and status)
- docs/project/PROJECT_CONTEXT.md: Long-term development context and collaboration model
### Optional MobileCLIP evaluation dependencies

The base app does not require ML packages.  To evaluate MobileCLIP locally, explicitly install compatible CPU PyTorch, torchvision, Pillow, and Apple's official MobileCLIP package/checkpoint into your environment and place the selected `apple/MobileCLIP-S0` `.pt` checkpoint in the app-data model cache shown in Settings.  The app never downloads model weights automatically.

In Settings, choose an explicit MobileCLIP evaluation source before pressing **Run MobileCLIP evaluation**: the current imported library, the photos selected in a supported workspace, or another folder.  The preview shows available images and the configured sample cap before any evaluation starts.  MobileCLIP remains local-only and evaluation-only; it does not modify originals, thumbnails, categories, cleanup decisions, or the normal import workflow.

### AI Models runtime management

Settings includes an **AI Models** section backed by the generic AI Runtime Manager. It can show registered providers such as MobileCLIP, inspect the selected Python interpreter, and generate an explicit installation plan with dependencies, model files, destination, licenses, and warnings. MODEL-002A provides the provider-agnostic runtime foundation; MODEL-002B adds the managed MobileCLIP installation and verification flow. Both are merged, but Product Owner manual validation of real dependency installation, checkpoint download, Ready status, one-image embedding, and CPU performance is still pending.

### MODEL-002B managed MobileCLIP installation

MobileCLIP is now the first real managed AI runtime. Use **Settings → AI Models** to select the dedicated interpreter, normally `C:\Projects\family-memory-ai\.venv-mobileclip\Scripts\python.exe` on the Product Owner Windows machine. The app validates that interpreter, persists it, and revalidates it after restart.

The installation plan is explicit and must be reviewed before anything runs. It shows the selected Python path/version, 64-bit/writable/pip validation, CPU-only device, package commands using `python.exe -m pip`, the official Apple MobileCLIP GitHub source, `apple/MobileCLIP-S0`, the app-data checkpoint destination outside Git, estimated size/disk usage, code/model licenses, restart note, warnings, and verification steps. There are no automatic downloads or silent package installs.

Verification requires imports, the checkpoint file, model/transforms creation, tokenizer creation, and one synthetic image embedding with finite numeric output before Ready is recorded. Product Owner detailed manual validation for MODEL-002B was deferred after merge; do not treat MobileCLIP as installed or Ready until repository-owned evidence and Product Owner validation confirm it. The production classifier has not been replaced by MobileCLIP. After merge, repository cleanup remains mandatory: switch to `main`, fetch/pull, delete merged local branches, confirm no open PRs, confirm `git stash list` is empty, and confirm GitHub Desktop shows 0 changed files.
