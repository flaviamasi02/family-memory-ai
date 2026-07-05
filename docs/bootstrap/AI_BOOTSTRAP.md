# Family Memory AI
## AI Bootstrap

This document defines the required initialization sequence for every AI assistant working on Family Memory AI.

Every new AI session must complete this bootstrap before performing any project work.

---

## Mission

The AI is expected to:
- understand the project
- preserve architectural consistency
- assist development
- avoid introducing inconsistencies
- maintain documentation quality

---

## Bootstrap Sequence

Mandatory initialization order:

1. Read docs/bootstrap/HANDOVER.md.
2. Read docs/bootstrap/DOCUMENTATION_FRAMEWORK.md.
3. Read docs/bootstrap/COMMANDS.md.
4. Read docs/development/DOCUMENTATION_ARCHITECTURE.md.
5. Read docs/project/PROJECT_CONTEXT.md.
6. Read docs/project/PROJECT_STATE.md.
7. Read docs/development/AI_PROJECT_PLAYBOOK.md.
8. Read docs/development/DECISIONS.md.
9. Read docs/project/ROADMAP.md (if present).
10. Read docs/project/GLOSSARY.md.
11. Read any additional mandatory documents referenced by those files.

The bootstrap must be completed before answering project-related requests.

---

## AI Responsibilities

The AI must:
- Build complete project context.
- Verify the Documentation Framework version and compatibility baseline.
- Understand current sprint.
- Understand project version.
- Understand completed work.
- Understand pending work.
- Understand architectural decisions.
- Understand documentation responsibilities.
- Understand project commands.
- Validate command prerequisites before executing any project command.
- Treat repository verification commands as dependent on access to the latest repository snapshot.
- Never report successful verification without repository access.

Before executing any project command:

1. Parse the command.
2. Validate prerequisites.
3. Execute only if prerequisites are satisfied.

Prerequisite definitions are owned by docs/bootstrap/COMMANDS.md and must not be duplicated in this document.

---

## Project Rules

The AI must always:
- Use English for project artifacts.
- Explain architectural changes before implementation.
- Prefer extending existing architecture.
- Avoid unnecessary complexity.
- Keep documentation synchronized.
- Update docs/project/PROJECT_STATE.md after implementation.
- Respect docs/development/DECISIONS.md.
- Respect docs/bootstrap/COMMANDS.md.
- Respect docs/development/AI_PROJECT_PLAYBOOK.md.
- Respect docs/development/DOCUMENTATION_ARCHITECTURE.md.

---

## What the AI Must Never Do

- Never invent project rules.
- Never invent architectural decisions.
- Never skip mandatory documents.
- Never mark a sprint complete unless Definition of Done is satisfied.
- Never duplicate documentation.
- Never contradict previous architectural decisions.
- Never rename official project concepts.

---

## Communication Rules

- Conversation language follows the user's preference.
- Project documentation is always English.
- Code comments are English.
- Commit messages are English.
- Architecture documents are English.
- Technical prompts are English.

---

## Documentation Ownership

### HANDOVER
Initialization entry point.

### DOCUMENTATION_FRAMEWORK
Framework versioning and compatibility reference.

### COMMANDS
Project commands.

### DOCUMENTATION_ARCHITECTURE
Documentation ecosystem.

### PROJECT_CONTEXT
Business vision.

### PROJECT_STATE
Current implementation.

### AI_PROJECT_PLAYBOOK
Development workflow.

### DECISIONS
Architectural decisions.

### ROADMAP
Future work.

### GLOSSARY
Official terminology.

### DOCSYNC and DOCVERIFY
DOCSYNC prepares documentation changes.
DOCVERIFY validates completed documentation changes in the repository snapshot provided by the user.

---

## Working Principles

The AI should:
- Prefer evolution over replacement.
- Keep implementations small.
- Avoid breaking existing features.
- Keep backward compatibility whenever practical.
- Produce deterministic behavior whenever possible.
- Minimize technical debt.
- Prefer readability over cleverness.
- Never redefine command behavior outside docs/bootstrap/COMMANDS.md.

---

## Session Checklist

Before implementation verify:

- ✓ Bootstrap completed
- ✓ Documentation Framework version verified
- ✓ Documentation read
- ✓ Current sprint identified
- ✓ Commands loaded
- ✓ Architecture understood
- ✓ Relevant decisions reviewed
- ✓ Documentation ownership understood

Only then start implementation.

---

## Future Compatibility

This bootstrap is intentionally AI-agnostic.

Any future AI assistant should be able to follow the same initialization sequence without requiring project-specific retraining.

---

## Definition of Done

AI_BOOTSTRAP.md becomes the mandatory operational manual for AI assistants working on Family Memory AI.

docs/bootstrap/HANDOVER.md should reference docs/bootstrap/AI_BOOTSTRAP.md as part of the mandatory initialization sequence.

This document must remain implementation-independent and should only describe AI behavior.
