# Family Memory AI Coding Standards

## Python Style

The codebase should follow Python best practices and remain easy to read and maintain.

- Follow PEP 8.
- Use meaningful names for variables, functions, classes, and modules.
- Keep methods small and focused.
- Keep classes small and focused.
- Use type hints when they improve clarity.
- Add docstrings for public classes and important public functions.

Readable code is a priority for long-term maintenance.

---

# Architecture Rules

The architecture should remain simple, modular, and predictable.

- Follow the Single Responsibility Principle.
- Use Dependency Injection where it improves flexibility.
- Avoid globals unless there is a strong reason.
- Avoid duplicated code.
- Keep modules independent where possible.

Each component should have a clear purpose and a clear boundary.

---

# Qt Rules

The Qt-based UI should be kept simple and safe.

- UI code should handle presentation only.
- Workers should perform background tasks.
- Signals should be used to communicate between components.
- Never update widgets from worker threads.

The user interface should remain responsive even when background work is running.

---

# Git Rules

Source control should be used carefully and consistently.

- Make small commits.
- Use meaningful commit messages.
- Keep the working application functional after every commit.
- Push only after testing.

The repository should not be left in a broken state.

---

# Refactoring Rules

Refactoring should be done carefully and incrementally.

- Make small incremental changes.
- Avoid unnecessary rewrites.
- Preserve existing behaviour.
- Keep each refactoring focused on one responsibility.

Refactoring should improve the code without changing user-visible behavior unexpectedly.

---

# Performance Rules

The application should remain efficient as the photo library grows.

- Avoid unnecessary allocations.
- Reuse cache results where appropriate.
- Avoid blocking the UI.
- Prepare for large photo libraries from the start.

Performance should be considered during implementation, not only after the fact.

---

# Testing Rules

Testing should be treated as part of the development process.

- Every Sprint should be tested manually.
- Future unit tests should be added for core logic.
- Future integration tests should cover major flows.
- Future AI evaluation tests should validate quality and behavior.

The goal is to keep the application reliable as it grows.

---

# Documentation Rules

Documentation should stay synchronized with the codebase.

- README should reflect the current state of the project.
- CHANGELOG should be updated regularly.
- ROADMAP should reflect current priorities.
- Architecture documentation should be updated when new modules are introduced.

Good documentation helps future contributors understand the product quickly.

---

# AI Collaboration Rules

When working with AI-assisted development, the process should stay structured and deliberate.

- Before coding, explain the architecture and intended approach.
- After approval, generate the implementation.
- Never change project direction without approval.
- Prefer maintainability over cleverness.

Readable code today is more valuable than clever code that nobody understands tomorrow.