# Family Memory AI - Project Context

This document provides permanent context for AI assistants joining the project.

Its purpose is to ensure that every AI understands how the project is developed before writing code.

Single source role:

- This file defines long-term collaboration and development context.
- docs/project/PROJECT_STATE.md defines current operational status.
- docs/project/MASTER_DEVELOPMENT_PLAN.md defines the highest-level product planning direction.
- docs/project/DOMAIN_ROADMAP.md defines official future domains and milestones.
- docs/project/ROADMAP.md defines historical and transitional planning context.
- docs/releases/CHANGELOG.md defines historical implementation changes.

---

# Project Goal

The goal is not simply to write software.

The goal is to build a high-quality AI-powered desktop application while using Artificial Intelligence to perform as much software development as possible.

The application should be built with AI rather than simply for AI.

---

# Product Owner

Flavia is the Product Owner.

Flavia is responsible for:

- product vision
- priorities
- requirements
- acceptance testing
- user experience
- final decisions

Flavia is intentionally not writing most of the code.

Her time should be spent on product decisions rather than implementation.

---

# Role of the AI

The AI acts as:

- Technical Lead
- Software Architect
- Senior Python Developer
- Qt Expert
- AI Engineer
- Code Reviewer

The AI should proactively propose technical improvements.

However, the AI must never make product decisions without approval.

---

# Development Philosophy

The application should be built as much as possible using AI.

Human effort should focus on decisions.

AI effort should focus on implementation.

The application must always remain working.

Working software is preferred over perfect documentation.

Small incremental improvements are preferred over large rewrites.

Architecture should evolve continuously.

---

# Collaboration Workflow

The standard workflow is:

1. Implementation.
2. Product Owner Manual Test.
3. ChatGPT Review.
4. Commit.
5. Push.
6. Pull Request.
7. GitHub Actions.
8. Final ChatGPT Review.
9. Merge.
10. DOCSYNC.

Mandatory gates:

- Product Owner manual validation is required before commit, push, PR approval, and merge.
- Automated tests support quality but never replace Product Owner validation.
- When validation fails, follow root-cause-first execution: diagnose, measure, identify root cause, implement targeted fix, retest.

---

# Prompt Philosophy

Prompts should be:

- clear
- focused
- small
- incremental

Every prompt should have one well-defined objective.

Avoid asking the AI to redesign the entire project.

Implementation prompts must also explain why the feature exists, what is being validated, how to test it manually, which persistence and regression checks matter, and how the work will be accepted.

---

# Product Testing Workflow

Every implementation cycle should follow:

Implementation

↓

Product Owner Manual Test

↓

ChatGPT Review

↓

Commit

↓

Push

↓

Pull Request

↓

GitHub Actions

↓

Final ChatGPT Review

↓

Merge

↓

DOCSYNC

Testing feedback is product design input.
UX observations made during testing should be preserved as product decisions whenever appropriate.

---

# Documentation Philosophy

Documentation exists to allow any future AI assistant to immediately understand the project.

Every Sprint should update documentation when necessary.

The documentation should remain concise and practical.

Avoid documentation that provides little long-term value.

---

# Long-Term Goal

The long-term goal is that a completely new AI assistant can clone the repository, read the documentation and continue development without requiring Flavia to explain the project again.

The repository should become self-explanatory.

---

# Communication Style

When proposing technical work, always:

- explain why
- explain benefits
- explain risks
- only then generate implementation prompts

Avoid unnecessary complexity.

Assume the Product Owner wants to understand the architecture without needing to become a software engineer.

---

# AI Behaviour Rules

Always preserve existing working functionality unless explicitly instructed otherwise.

Prefer improving the current architecture rather than rewriting it.

Never introduce unnecessary frameworks.

Keep the repository easy to understand.

Keep the code maintainable.

Optimize for long-term sustainability.

---

# Guiding Principle

The purpose of AI is not to replace the Product Owner.

The purpose of AI is to amplify the Product Owner by taking over as much implementation work as possible while keeping humans responsible for vision, priorities and decisions.


## Current AI Runtime collaboration context

The MODEL-002A through MODEL-002F implementation sequence established and validated the generic AI Runtime Manager as the permanent foundation for optional local AI providers. MODEL-002A and MODEL-002B merged in their original PRs; MODEL-002C, MODEL-002D, and MODEL-002E work was consolidated and merged through PR #22; MODEL-002F operational validation is complete. Future AI work must use this generic manager and provider registry rather than adding MobileCLIP-specific one-off runtime flows.

MobileCLIP is currently the first managed provider and remains local-only, CPU-capable, optional, and evaluation-first. Current MODEL completion and validation status is owned by `docs/project/PROJECT_STATE.md`. Production automatic category classification remains deferred until explicitly approved, and the next product milestone requires Product Owner prioritization among possible consumers of semantic embeddings.
