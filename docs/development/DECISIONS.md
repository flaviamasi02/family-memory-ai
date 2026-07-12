# Family Memory AI - Decision Ledger

## Purpose

This document records all officially approved project decisions.

Every decision has a permanent DEC identifier.

---

## Decisions

### DEC-0001
Decision Sync Queue

Approved.

### DEC-0002
Documentation Sync Sprint

Approved.

### DEC-0003
Create docs/development/DECISIONS.md

Approved.

### DEC-0004
Create docs/development/SYNC_QUEUE.md

Approved.

### DEC-0005
Mobile Product Owner Mode

Approved.

### DEC-0006
Mobile Documentation First

Approved.

### DEC-0007
Mobile Documentation Repository

Approved.

### DEC-0008
docs/development/PROMPT_TEMPLATE.md

Approved.

### DEC-0009
docs/development/AI_PROJECT_PLAYBOOK.md

Approved.

### DEC-0010
Mobile Mode / Development Mode

Approved.

### DEC-0011
Repository Bootstrap Prompt

Approved.

### DEC-0012
Documentation Architecture

Approved.

### DEC-0013
Decision Ledger

Approved.

### DEC-0014
Documentation First Development

Approved.

### DEC-0016
Atomic Documentation Sync

Approved.

### DEC-0018
Documentation System

Approved.

### DEC-0019
Single Source of Truth

Approved.

### DEC-0022
Story Timeline Architecture

**Value:** Product  
**Impact:** Medium

Version 1 is **NOT** focused on Story Timeline. Story Timeline is an approved future capability. The application architecture must remain extensible so future album types can be added without major redesign.

**Impacted documents:**
- docs/project/PROJECT_CONTEXT.md
- docs/project/PROJECT_STATE.md
- docs/project/ROADMAP.md
- docs/bootstrap/HANDOVER.md

### DEC-0023
Decision Impact Matrix

**Value:** Method  
**Impact:** Low

Every approved decision must include:
- Decision ID
- Value (Product / Method / Both)
- Impact
- Documents to update
- Impacted sprints

### DEC-0024
Product North Star

**Value:** Product  
**Impact:** Low

Superseded by later product-direction updates in PRODUCT-DECISION-001 and PRODUCT-DOC-002.

Original decision:

> "Automatically create the best possible annual family photo album."

Current interpretation:

Annual album creation remains an important output, but the broader product mission now centers on Family Memory Intelligence: helping families preserve, organize, understand, and continuously teach the system what matters most.

Future album types including:
- Vacation Albums
- Gift Albums
- Event Albums
- Story Timeline

are approved future directions but are **NOT** part of Version 1.

The architecture should remain extensible.

**Impacted documents:**
- docs/project/PROJECT_CONTEXT.md
- docs/project/PROJECT_STATE.md
- docs/project/ROADMAP.md
- docs/bootstrap/HANDOVER.md

### DEC-0025
Print Ready Export

**Value:** Product  
**Impact:** Medium

Decision:

The final objective is to export a print-ready album for external printing providers (initial target: CEWE/Crew), while keeping the export engine provider-independent.

**Impacted documents:**
- docs/project/ROADMAP.md
- docs/project/PROJECT_STATE.md
- docs/bootstrap/HANDOVER.md
- docs/architecture/ARCHITECTURE.md

**Impacted Sprints:**
DEV-006 and DEV-007.

### DEC-0026
DOCSYNC Command

**Value:** Method  
**Impact:** Low

Decision:

Documentation synchronization is performed through DOCSYNC PC / DOCSYNC MOBILE commands.

**Impacted documents:**
- docs/bootstrap/HANDOVER.md
- docs/development/AI_PROJECT_PLAYBOOK.md
- docs/development/SYNC_QUEUE.md

**Impacted Sprints:**
Documentation sprints and end-of-sprint sync activity.

### DEC-0027
Photo Intelligence Foundation

**Value:** Product  
**Impact:** Medium

Decision:

Before implementing selection rules or AI ranking, the project will first build a Photo Intelligence model.

**Impacted documents:**
- docs/project/ROADMAP.md
- docs/project/PROJECT_STATE.md
- docs/bootstrap/HANDOVER.md

**Impacted Sprints:**
DEV-002 and later.

### DEC-0028
Documentation Structure Refactoring

**Value:** Both  
**Impact:** High

Decision:

Documentation was reorganized into a modular folder architecture under `docs/` to support long-term scalability, predictable navigation, and AI-friendly initialization across conversations and assistant types.

Expected benefits:

- clearer ownership boundaries per documentation domain
- lower duplication and easier synchronization
- faster initialization for humans and AI assistants
- safer future expansion without repeated structural migrations

Folder responsibilities:

- `docs/bootstrap/`: initialization and command references
- `docs/project/`: project context/state/planning/terminology
- `docs/development/`: methods, decisions, and doc governance
- `docs/architecture/`: technical architecture references
- `docs/testing/`: testing documentation artifacts
- `docs/releases/`: release and migration communication
- `docs/archive/`: preserved legacy snapshots

Backward compatibility considerations:

- all internal references must be migrated to new paths
- legacy root-level context/state docs are preserved in `docs/archive/`
- command and reading-order workflows must continue to resolve mandatory documents

**Impacted documents:**
- docs/bootstrap/HANDOVER.md
- docs/bootstrap/AI_BOOTSTRAP.md
- docs/bootstrap/COMMANDS.md
- docs/development/DOCUMENTATION_ARCHITECTURE.md
- docs/project/PROJECT_STATE.md

**Impacted Sprints:**
Post DEV-003 documentation refactoring activities.

### DEC-0029
Prompt Standards for Implementation Prompts

**Value:** Method  
**Impact:** Medium

Implementation prompts must include:

- Why We Test
- Manual Test Plan
- Acceptance Checklist

Testing must explain why the feature exists, how to test it manually, what persistence and regression checks matter, and what result qualifies as done.

**Impacted documents:**
- docs/development/PROMPT_TEMPLATE.md
- docs/development/AI_PROJECT_PLAYBOOK.md
- docs/project/PROJECT_CONTEXT.md

**Impacted Sprints:**
All future implementation prompts.

### DEC-0030
Memory Review Learning Focus

**Value:** Product  
**Impact:** High

Memory Review primarily exists to teach the AI.

Its future UI should focus on:

- media category correction
- AI teaching
- preference learning
- classification validation

Decision editing should move out of the Memory Review UI in a future milestone while preserving the underlying decision model.

**Impacted documents:**
- docs/project/PROJECT_STATE.md
- docs/project/PROJECT_CONTEXT.md
- docs/product/PRODUCT_VISION.md
- docs/product/FAMILY_MEMORY_SCORE.md

**Impacted Sprints:**
Memory Review UX and learning workflow milestones.

### DEC-0031
Learning Transparency and Learning Inspector

**Value:** Product  
**Impact:** Medium

Learning must be visible and understandable to users.

Future learning views should expose:

- learned rules
- learned preferences
- learned signals
- support count
- confidence
- explanation
- date learned
- time learned

**Impacted documents:**
- docs/project/PROJECT_STATE.md
- docs/project/PROJECT_CONTEXT.md
- docs/product/PRODUCT_VISION.md
- docs/product/FAMILY_MEMORY_SCORE.md
- docs/project/MASTER_DEVELOPMENT_PLAN.md
- docs/project/DOMAIN_ROADMAP.md
- docs/project/GLOSSARY.md

**Impacted Sprints:**
MEM learning transparency milestones.

### DEC-0032
Content-First Learning

**Value:** Product  
**Impact:** High

Preference learning must prioritize the visual content of an image.

Visual evidence comes first. Metadata is secondary support only.

Learning rules must not rely primarily on metadata such as filename, extension, EXIF, file size, or date source.

**Impacted documents:**
- docs/project/PROJECT_STATE.md
- docs/product/PRODUCT_VISION.md
- docs/product/FAMILY_MEMORY_SCORE.md
- docs/project/MASTER_DEVELOPMENT_PLAN.md
- docs/project/DOMAIN_ROADMAP.md
- docs/project/GLOSSARY.md

**Impacted Sprints:**
LEARN and CLEAN milestones that affect learning or classification.

### DEC-0033
Category Semantics

**Value:** Product  
**Impact:** High

The system must distinguish between category types:

- Content Categories
- Organizational Categories
- Workflow Categories

Workflow categories describe actions, not visual meaning, and must not learn visual rules.

**Impacted documents:**
- docs/project/PROJECT_STATE.md
- docs/product/PRODUCT_VISION.md
- docs/product/FAMILY_MEMORY_SCORE.md
- docs/project/MASTER_DEVELOPMENT_PLAN.md
- docs/project/DOMAIN_ROADMAP.md
- docs/project/GLOSSARY.md

**Impacted Sprints:**
MEM, LEARN, CLEAN, and future workflow milestones.

### DEC-0034
Memory Review UX Continuity

**Value:** Product  
**Impact:** Medium

Memory Review and Cleanup Review should preserve scroll position, selection, and user context during category corrections and filtering changes.

If the active photo disappears because of filtering, the workspace should remain at the same scroll position and select the next visible photo.

**Impacted documents:**
- docs/project/PROJECT_STATE.md
- docs/project/PROJECT_CONTEXT.md
- docs/product/PRODUCT_VISION.md
- docs/product/FAMILY_MEMORY_SCORE.md

**Impacted Sprints:**
Memory Review and Cleanup Review UX milestones.

### DEC-0035
Product Testing Workflow

**Value:** Method  
**Impact:** Medium

Every implementation cycle should follow:

Implementation -> Manual Test -> Product Owner Feedback -> Documentation Update -> Commit -> Push -> Next Sprint

Testing feedback is product design input and UX observations made during testing should be preserved as product decisions when appropriate.

**Impacted documents:**
- docs/project/PROJECT_CONTEXT.md
- docs/development/AI_PROJECT_PLAYBOOK.md
- docs/development/PROMPT_TEMPLATE.md

**Impacted Sprints:**
All future implementation cycles.

### DEC-0036
Official AI Collaboration Workflow

**Value:** Method
**Impact:** High

Family Memory AI adopts the following official AI-assisted development workflow:

Product Owner -> ChatGPT -> Implementation Prompt -> Codex -> Pull Request -> GitHub Actions -> ChatGPT Technical Review -> Product Owner Approval -> Merge.

This workflow formalizes repository health checks before implementation, focused pull request lifecycle rules, GitHub Actions root-cause analysis, human interaction expectations, Codex Cloud limitation handling, implementation prompt standards, Definition of Done requirements, user action guidance, and continuous workflow improvement.

Permanent rules:

- repository health comes before new implementation work;
- one implementation should map to one pull request;
- existing pull requests should be updated whenever possible;
- failed GitHub Actions must be inspected, root-caused, fixed, and re-run on the same pull request;
- AI assistants should use available repository, GitHub, pull request, and workflow capabilities before asking the Product Owner for logs or screenshots;
- Codex Cloud limitations must be stated honestly when remote git or GitHub verification is inaccessible;
- implementation prompts must follow the official prompt template;
- implementation is not complete until applicable Definition of Done conditions are satisfied;
- operational guidance to the Product Owner must end with a clear NEXT ACTION block;
- approved workflow improvements must be added to canonical documentation instead of scattered notes.

**Impacted documents:**
- docs/development/AI_PROJECT_PLAYBOOK.md
- docs/development/PROMPT_TEMPLATE.md
- docs/project/PROJECT_STATE.md
- docs/releases/CHANGELOG.md

**Impacted Sprints:**
All future implementation and documentation cycles.

### DEC-0037
Prompt Execution Environment Standard

**Value:** Method
**Impact:** Medium

Every implementation, bug-fix, documentation-sync, or Pull Request feedback prompt must explicitly state the Execution Environment before task details.

Approved execution environment labels:

- Codex Cloud
- Codex Local (VS Code)
- GitHub Copilot (PR Comment)

This prevents ambiguity about where work should be performed and whether the execution agent has cloud, local Windows, or Pull Request comment context.

**Impacted documents:**
- docs/development/PROMPT_TEMPLATE.md
- docs/development/AI_PROJECT_PLAYBOOK.md

**Impacted Sprints:**
All future implementation, debugging, review, and documentation-sync prompts.

### DEC-0038
Prompt Target Standard

**Value:** Method
**Impact:** Medium

Every implementation, bug-fix, documentation-sync, or Pull Request feedback prompt must explicitly state the Target before task details.

For new work, the prompt must state whether it is new implementation and whether a new branch or Pull Request is expected.

For existing Pull Request work, the prompt must state the Pull Request number and branch when known, and must explicitly say not to create a new Pull Request unless the Product Owner approves one.

**Impacted documents:**
- docs/development/PROMPT_TEMPLATE.md
- docs/development/AI_PROJECT_PLAYBOOK.md

**Impacted Sprints:**
All future implementation, debugging, review, and documentation-sync prompts.

### DEC-0039
ChatGPT Documentation Update Permission

**Value:** Method
**Impact:** Medium

ChatGPT may directly update repository documentation only after explicit Product Owner approval.

When approved, the update must stay within the approved documentation scope, preserve canonical ownership boundaries, avoid application source-code changes unless separately approved, and be committed as documentation-only work when a commit is requested.

Repository documentation is the permanent project memory and must remain synchronized with approved project state, decisions, workflow rules, and review outcomes.

**Impacted documents:**
- docs/development/AI_PROJECT_PLAYBOOK.md
- docs/development/PROMPT_TEMPLATE.md
- docs/bootstrap/HANDOVER.md

**Impacted Sprints:**
All future documentation-sync and project governance updates.

### DEC-0040
Official AI Execution Workflow Routing

**Value:** Method
**Impact:** High

Family Memory AI adopts the following official execution routing:

- New implementation -> Codex Cloud
- Local development/debug -> Codex Local (VS Code)
- Existing Pull Request improvements -> GitHub Copilot (PR Comment)

This routing keeps new implementation work focused, sends local Windows debugging to the local environment, and keeps existing Pull Request refinements attached to the active PR instead of creating unnecessary replacement PRs.

**Impacted documents:**
- docs/development/AI_PROJECT_PLAYBOOK.md
- docs/development/PROMPT_TEMPLATE.md
- docs/project/PROJECT_STATE.md
- docs/bootstrap/HANDOVER.md
- docs/releases/CHANGELOG.md

**Impacted Sprints:**
All future implementation, review, debugging, and PR-improvement cycles.
