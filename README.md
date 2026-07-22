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
### AI Models runtime management

Settings includes an **AI Models** section backed by the generic AI Runtime Manager. MobileCLIP is the first managed local AI provider and runs through a configured dedicated Python interpreter, not through provider-specific dependencies installed in the main application `.venv`. The main PySide6 application starts from the normal project environment with `python src/main.py`; MobileCLIP inference runs across the managed runtime boundary selected and verified in Settings.

The Product Owner manually validated the Windows CPU workflow after PR #28 and PR #29: Settings -> AI Models verification completed with exit code 0, reported `embedding_dimension = 512` and `tokenizer = true`, automatic import embedding processed 20/20 images with 0 failures in about 31.6 seconds, and the similarity diagnostic returned ordered top-N results from stored embeddings. This is observed validation evidence, not a universal performance guarantee.

Developer diagnostics remain available when needed:

```bash
python scripts/embed_folder.py <folder> --limit 20
python scripts/similar_images.py <source-image> <folder> --limit 10
```

Current limits: production automatic category classification is not implemented, semantic similarity is not exposed in the production UI, and similar-photo UI, near-duplicate assistance, clustering, automatic category suggestions, and learning from corrections remain future Product Owner-prioritized work.
