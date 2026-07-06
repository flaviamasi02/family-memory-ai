# Family Memory AI
## Project Constitution

This document defines the core principles of the Family Memory AI project.

Unlike project state or roadmap documents, this constitution is intentionally stable and should change only in exceptional circumstances.

All future architectural, technical, and product decisions should remain consistent with these principles.

---

## Mission

Family Memory AI exists to preserve family memories and help families rediscover meaningful moments.

The project reduces the effort required to organize large photo collections while using AI to assist, not replace, human judgment.

Trust and transparency are foundational requirements for every major decision.

---

## Vision

Family Memory AI aims to become the best AI-assisted family photo organization platform.

The platform should reliably support collections with tens of thousands of images, continuously improve through user feedback, and remain maintainable for many years.

---

## Core Principles

### User First

Product decisions must improve the user experience and deliver clear value to families.

### AI-First Development

AI should perform as much implementation work as possible.

Humans focus on decisions, validation, testing, and product direction.

### Simplicity

Prefer simple solutions over unnecessary complexity.

### Incremental Evolution

Small improvements are preferred over large rewrites.

### Maintainability

Readable code is preferred over clever code.

### Documentation Matters

Documentation is part of the product and must evolve with implementation.

### Documentation is Production Code

Documentation is not an optional activity.

Documentation is part of the delivered product.

Implementation and documentation must evolve together.

A feature is considered incomplete until its required documentation has been updated.

Good documentation reduces future development cost and enables long-term AI collaboration.

### Documentation Minimalism

Documentation should evolve by extending existing documents whenever possible.

New documentation files should be introduced only when they provide:

- unique responsibility
- clear separation of concerns
- measurable long-term value

### Deterministic Before Intelligent

Prefer deterministic behavior before introducing AI-driven behavior.

### Performance by Design

Architecture should scale to large photo libraries by default, not as an afterthought.

### Transparency

AI decisions should be explainable whenever practical.

---

## Architectural Principles

- Avoid unnecessary coupling.
- Prefer composition over duplication.
- Separate UI, business logic, and infrastructure.
- Preserve backward compatibility whenever practical.
- Prefer extending architecture rather than replacing it.

---

## AI Collaboration Principles

AI assistants should:

- Read project documentation before working.
- Respect documented decisions.
- Respect documentation ownership.
- Avoid inventing project rules.
- Explain architectural changes before implementation.
- Keep documentation synchronized.

---

## Documentation Principles

Documentation should:

- Have a single responsibility.
- Avoid duplication.
- Be easy to navigate.
- Remain understandable by both humans and AI.
- Prefer extending existing documents over creating new files.
- Avoid unnecessary document proliferation.

## Practical Rules

- Every implementation should update docs/project/PROJECT_STATE.md.
- Architectural changes should update docs/development/DECISIONS.md.
- Workflow changes should update docs/bootstrap/COMMANDS.md.
- Terminology changes should update docs/project/GLOSSARY.md.
- Documentation structure changes should update docs/development/DOCUMENTATION_ARCHITECTURE.md.
- Major project changes should update docs/README.md when appropriate.

---

## AI Responsibilities

AI assistants should:

- Always identify documentation affected by an implementation.
- Always recommend updating the required documentation.
- Never consider an implementation complete if mandatory documentation is missing.
- Treat documentation with the same importance as production code.

---

## Git Principles

- Meaningful commits are preferred.
- Large changes should begin with a snapshot commit.
- Documentation updates are part of implementation.

---

## Long-Term Goals

- Keep the project understandable after years of development.
- Allow any future AI assistant to continue development.
- Reduce onboarding time.
- Maintain architectural consistency.

---

## Changing the Constitution

This document should change only after careful consideration.

Constitution-level changes should normally require a new Architecture Decision (DEC) before adoption.

---

## Definition of Done

PROJECT_CONSTITUTION.md is the highest-level guiding document for Family Memory AI.

Future project decisions should remain aligned with this constitution.

A feature is complete only when:

- Implementation completed.
- Tests completed (where applicable).
- Documentation updated.
- Contextual Workspace Help updated for any impacted user-facing workspace.
- Architecture decisions recorded (if required).
- Documentation synchronization completed.

Permanent Definition of Done requirement:

"A user-facing feature is not considered complete until its contextual Workspace Help has been updated and accurately reflects the current functionality."
