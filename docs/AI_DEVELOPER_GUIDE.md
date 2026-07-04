# Family Memory AI

## Vision

Family Memory AI is an AI-powered desktop application that helps families preserve, organize, and rediscover their most meaningful memories.

It is not a traditional photo organizer. It is an AI Memory Curator.

Commercialization may happen in the future, but the current goal is to build the best possible application for Flavia's own family.

---

# Product Philosophy

The following principles guide every product decision:

- Working software is always more important than perfect documentation.
- Every Sprint must end with:
  - working application
  - repository not broken
  - something visible or architecturally valuable
  - commit and push
- Prefer incremental improvements.
- Avoid unnecessary rewrites.
- Never sacrifice usability for architecture.

---

# Team Roles

## Flavia

Flavia is the Product Owner.

She defines:

- requirements
- priorities
- product vision
- UX decisions
- testing
- feature approval

## AI Engineer

The AI acts as:

- Software Architect
- Senior Python Developer
- Qt Expert
- AI Engineer
- Code Reviewer

The AI should generate as much implementation as possible while keeping the application working.

Before implementing major architectural changes, the AI should always explain:

- why
- benefits
- alternatives
- future impact

Only implement after approval.

---

# Technology Stack

## Current Stack

| Area | Technology |
| --- | --- |
| Language | Python |
| UI Framework | PySide6 |
| UI Foundation | Qt |
| Platform Focus | Windows First |
| Editor | VS Code |
| Desktop Git Workflow | GitHub Desktop |
| Source Control | GitHub |

## Future Technologies

- OpenCV
- PyTorch
- ONNX Runtime
- SQLite
- FAISS
- Sentence Transformers

---

# Current Project Structure

The current repository is intentionally small and focused. Its main purpose is to establish a working desktop foundation before adding more advanced AI features.

## Existing Folders and Responsibilities

| Path | Responsibility |
| --- | --- |
| src/ | Application entry point and core source code |
| src/ui/ | Qt user interface components and windows |
| src/workers/ | Background processing and long-running tasks |
| src/cache/ | Caching utilities such as thumbnails |
| tests/ | Automated tests and regression coverage |
| docs/ | Project documentation |
| assets/ | Static assets such as images and resources |
| tools/ | Development utilities and helpers |

## Current Implementation Notes

- The application entry point is in src/main.py.
- The main window is implemented in src/ui/main_window.py.
- Thumbnail generation is handled in src/workers/thumbnail_worker.py.
- Thumbnail storage and lookup logic lives in src/cache/thumbnail_cache.py.

---

# Target Architecture

The future architecture should remain modular and scalable as the application grows beyond basic photo viewing and thumbnail generation.

```text
src/
  ui/
  models/
  core/
  workers/
  cache/
  storage/
  ai/
  services/
```

## Module Responsibilities

| Module | Responsibility |
| --- | --- |
| ui/ | User interface components, windows, dialogs, and view models |
| models/ | Data models for photos, people, albums, events, and memories |
| core/ | Shared application logic, configuration, and orchestration |
| workers/ | Background jobs for indexing, analysis, and processing |
| cache/ | Thumbnail cache, metadata cache, and temporary runtime cache |
| storage/ | Persistence layer, file access, and database integration |
| ai/ | AI inference, feature extraction, and model integration |
| services/ | High-level services such as search, curation, and recommendation |

---

# Coding Standards

All implementation should follow Python best practices and stay easy to maintain.

## Rules

- Follow the Single Responsibility Principle.
- Keep classes small and focused.
- Keep methods small and readable.
- Avoid duplicated code.
- Use meaningful names.
- Add type hints where they improve clarity.
- Keep imports clean and intentional.
- Keep code readable over cleverness.
- Preserve existing behavior during refactoring.

---

# Performance Requirements

The application must remain responsive even as it scales to large photo collections.

## Target

- 50,000 photos

## Required Design Principles

The architecture must support:

- lazy loading
- virtual scrolling
- background workers
- thumbnail cache
- metadata cache
- database-backed storage
- no UI freezes

The UI should remain fast and interactive even when AI processing is running in the background.

---

# User Experience Principles

The experience should feel calm, fast, and forgiving.

## Core UX Rules

- Feedback must always be optional.
- Never require the user to explain decisions.
- The user can always:
  - Skip
  - Override AI
  - Continue immediately
- The application should feel instant even when AI processing is running.

The product should assist the user without creating friction.

---

# Memory Curation Philosophy

Technical quality matters, but emotional value matters more.

Rare memories should survive even if they are technically poor.

## Examples of valuable memories

- only family photo
- only photo with grandparents
- only photo of Luis
- birthday
- graduation
- vacation

## Important rule

Different facial expressions are not duplicates.
Different emotions are not duplicates.
Different interactions are not duplicates.

The system should prioritize human meaning over simple visual similarity.

---

# Artificial Intelligence Roadmap

The long-term AI capabilities should focus on helping families discover and preserve meaningful memories.

## Planned Capabilities

- People recognition
- Duplicate detection
- Near duplicate detection
- Smile detection
- Blur detection
- Closed eyes detection
- Composition score
- Technical quality assessment
- Memory score
- Rarity score
- Preference learning
- Storytelling
- Automatic album generation
- Natural language search
- Explainability engine

These features should be explainable, controllable, and useful in daily life.

---

# Development Workflow

The recommended development workflow is:

1. Explain architectural decisions.
2. Wait for approval.
3. Generate code.
4. Keep the project working.
5. Run tests.
6. Commit.
7. Push.
8. Update CHANGELOG.
9. Update README version.

---

# Git Rules

- Make small commits.
- Use meaningful commit messages.
- Never leave the repository broken.
- Prefer refactoring in small steps.

---

# Documentation Rules

- README should always reflect the current version.
- CHANGELOG should be updated after every Sprint.
- ROADMAP should be updated after milestone completion.
- Architecture documentation should be updated whenever a new module is introduced.

---

# Long Term Vision

Family Memory AI should eventually become an intelligent family memory assistant capable of understanding photos, people, events, emotions, and stories.

It should eventually answer questions such as:

- "What are the best memories of 2023?"
- "Create an album for Grandma."
- "Select the best 150 photos for printing."
- "Show Luis growing up."

The system should remain fast, explainable, and fully controlled by the user.

---

## Guiding Principle

The AI should always optimize for building a useful product, not simply writing more code.
