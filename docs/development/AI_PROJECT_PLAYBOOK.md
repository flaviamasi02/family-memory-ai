# Family Memory AI - AI Project Playbook

## Purpose

This document defines the development methodology used by AI assistants working on Family Memory AI.

It allows any future AI to immediately understand how the project is managed.

---

# Core Principles

- AI generates as much implementation work as possible.
- The Product Owner makes all product decisions.
- Every important idea must be explicitly approved before becoming part of the project.
- Follow the Single Source of Truth principle.
- Documentation First Development.
- Mobile-First Documentation whenever practical.
- One Sprint = one objective.
- Keep commits focused.
- Documentation updates are mandatory.
- Documentation is Production Code (constitutional principle).
- Contextual Workspace Help is a mandatory product feature.

---

# Prompt Standards

The canonical prompt structure is owned by docs/development/PROMPT_TEMPLATE.md. ChatGPT must use that template when preparing implementation prompts for Codex.

Every implementation prompt must include Execution Environment, Target, Estimated Task Size, Purpose, Expected Outcome, Repository, Definition of Done, Manual Test Plan, Acceptance Checklist, and Suggested Commit Message.

Every implementation prompt should make the testing purpose explicit before the first code change is requested and end with the Acceptance Checklist.


---

# Official AI Collaboration Workflow

Family Memory AI uses one official collaboration chain for AI-assisted development:

Product Owner

↓

ChatGPT

↓

Implementation Prompt

↓

Codex

↓

Pull Request

↓

GitHub Actions

↓

ChatGPT Technical Review

↓

Product Owner Approval

↓

Merge

## Participant Responsibilities

Product Owner:

- defines product intent, priorities, acceptance expectations, and final approval;
- approves project direction changes and permanent workflow rules;
- decides when an exception to normal verification or merge policy is acceptable.

ChatGPT:

- translates Product Owner intent into implementation prompts;
- checks repository context and canonical documentation before directing work;
- reviews Codex output, GitHub Actions results, pull request status, and merge readiness;
- gives operational guidance with a clear NEXT ACTION block when the Product Owner must act.

Implementation Prompt:

- is the contract between ChatGPT and Codex;
- must follow docs/development/PROMPT_TEMPLATE.md;
- must define purpose, expected outcome, Definition of Done, manual testing, acceptance checklist, and suggested commit message.

Codex:

- implements the requested change in the repository;
- updates the canonical documentation that owns affected topics;
- runs available tests and checks;
- creates or updates the focused implementation commit and pull request whenever the environment permits;
- reports environment limitations honestly instead of pretending verification succeeded.

Pull Request:

- contains one coherent implementation;
- is updated until review feedback and required checks are satisfied;
- is the review boundary for ChatGPT, GitHub Actions, and Product Owner approval.

GitHub Actions:

- provides automated verification;
- must be inspected when a check fails;
- must not be bypassed unless the Product Owner explicitly approves the exception.

ChatGPT Technical Review:

- verifies that implementation, documentation, tests, PR status, and GitHub Actions align with the prompt and project rules;
- identifies root causes for failures using available repository, PR, and workflow information before asking the Product Owner for help.

Merge:

- happens only after review, required checks, mergeability confirmation, and Product Owner approval.

## Execution Environment Routing

Family Memory AI uses explicit AI execution routing:

- New implementation -> Codex Cloud
- Local development/debug -> Codex Local (VS Code)
- Existing Pull Request improvements -> GitHub Copilot (PR Comment)

Implementation prompts must state the intended Execution Environment and Target before task details.

New implementation work should normally go to Codex Cloud.

Local Windows debugging, manual reproduction, environment-specific testing, and local-only repository work should use Codex Local (VS Code).

Follow-up changes to an existing Pull Request, including review feedback and check-fix refinements, should use GitHub Copilot through a Pull Request comment whenever practical.

Existing Pull Request improvement prompts must name the Pull Request and branch when known, and must explicitly say not to create a new Pull Request unless the Product Owner approves one.

---

# Repository Documentation as Permanent Project Memory

Repository documentation is the permanent project memory for Family Memory AI.

ChatGPT may directly update repository documentation only after explicit Product Owner approval.

When ChatGPT updates documentation directly:

- the update must stay within the approved documentation scope;
- canonical ownership boundaries must be preserved;
- application source code and tests must not be modified unless explicitly approved;
- the resulting change should be committed as documentation-only work.

---

# Repository Health First

Before starting any implementation sprint, repository health must be checked first.

Official rule:

- the repository should be healthy before new implementation begins;
- main should remain stable;
- obsolete pull requests should be closed or clearly superseded;
- unnecessary branches should be avoided;
- unresolved merge conflicts must be solved before adding more feature work on top;
- the active branch and pull request should be understood before changes are made.

If the repository is not healthy, the first task is to restore reviewable repository state rather than adding new functionality.

---

# Pull Request Lifecycle

Family Memory AI uses a focused pull request lifecycle:

- one implementation maps to one pull request;
- update the existing pull request whenever possible;
- avoid creating additional pull requests for the same feature or fix;
- keep the pull request focused on its stated purpose;
- merge only after review;
- merge only when the pull request is mergeable;
- merge only after required checks pass, unless the Product Owner explicitly approves an exception.

When review feedback, test failures, or GitHub Actions failures occur, update the same pull request instead of opening a replacement PR unless the original PR is technically unrecoverable or the Product Owner approves a reset.

---

# GitHub Actions Policy

When GitHub Actions fail:

1. Inspect the failing workflow and job output.
2. Identify the root cause.
3. Fix the root cause in the repository.
4. Update the same pull request.
5. Repeat until required checks pass or the Product Owner explicitly approves an exception.

Never guess. Do not treat a failing workflow as resolved until the cause is understood and the relevant verification has passed or the limitation has been explicitly documented.

---

# Human Interaction Policy

Before asking the Product Owner for logs, screenshots, GitHub output, or repository information, AI assistants must first use every available repository, GitHub, pull request, and workflow capability.

Ask the Product Owner for assistance only when the needed information is genuinely inaccessible from the available tools or permissions.

When user assistance is required, clearly state:

- what information is needed;
- why the AI cannot access it directly;
- how the Product Owner can retrieve it;
- what result is expected after the information is provided.

---

# Codex Cloud Limitations

Codex Cloud environments may be unable to perform `git push`, `git fetch`, or related remote operations because of network or credential restrictions.

When this occurs, Codex must:

- explain the limitation clearly;
- avoid repeatedly retrying the same blocked command;
- avoid inventing failures or claiming remote verification succeeded;
- continue with every action that is actually possible locally, including edits, local tests, commits, and documentation updates;
- state which GitHub or remote verification steps remain incomplete because of the environment limitation.

---

# Continuous Workflow Improvement

Whenever a workflow weakness is discovered during development, evaluate whether it should become a permanent project rule.

If the Product Owner approves the rule, add it to the appropriate canonical documentation instead of creating scattered notes.

Canonical ownership remains:

- docs/development/AI_PROJECT_PLAYBOOK.md for collaboration workflow, repository health, GitHub workflow, human interaction policy, and Codex limitations;
- docs/development/PROMPT_TEMPLATE.md for prompt structure, Definition of Done, and User Action Rule;
- docs/development/DECISIONS.md for approved project decisions;
- docs/project/PROJECT_STATE.md for current operational state;
- docs/releases/CHANGELOG.md for documentation update history.

---

# Workspace Help Documentation Policy (Permanent)

Family Memory AI treats contextual Workspace Help as part of the shipped product, not optional documentation.

The Workspace Help System is a permanent architectural component. It is not a supplementary feature and it is not optional.

Policy requirements:

- Every user-facing workspace must provide contextual Help.
- Help content is mandatory product functionality.
- Help documentation must evolve together with the product.
- Every new feature must update the corresponding workspace Help content.
- Every workflow change must update the corresponding workspace Help content.
- Every UI change affecting user interaction must update the corresponding workspace Help content.
- Every AI behavior change that affects user decisions must update the corresponding workspace Help content.
- No user-facing feature is considered complete until workspace Help content has been updated.

Required Help coverage per workspace:

- What this workspace does.
- Why it exists.
- When it should be used.
- How the user should use it.
- What the AI does automatically.
- What decisions are expected from the user.
- Best practices.
- Tips and recommendations.

---

# Documentation Structure

Reference the official documentation files:

- docs/development/IDEAS.md
- docs/development/DECISIONS.md
- docs/development/SYNC_QUEUE.md
- docs/project/PROJECT_STATE.md
- docs/bootstrap/HANDOVER.md
- docs/project/ROADMAP.md
- docs/development/PROMPT_TEMPLATE.md

Each document has a single responsibility.

---

# AI Behaviour

Always:

- explain important technical decisions;
- avoid unnecessary complexity;
- propose improvements but wait for Product Owner approval before changing project direction;
- keep documentation synchronized;
- respect the Decision Ledger.

Before proposing a new documentation file, first evaluate whether an existing document can be extended without violating ownership boundaries.

Create a new document only when it provides unique responsibility, clear separation of concerns, and measurable long-term value.

---

# Session Types

Documentation Session

Development Session

Architecture Session

Review Session

---

## Command Execution

Before executing any project command:

1. Parse the command.
2. Validate prerequisites.
3. If prerequisites are missing, stop execution.
4. Request the missing resources.
5. Resume execution only after the prerequisites have been provided.

---

# End of Sprint Checklist

Before considering a Sprint complete:

- objective completed and verified;
- tests/manual validation completed when applicable;
- documentation updated where affected;
- workspace Help updated for all impacted user-facing workspaces;
- documentation completeness verified for all impacted ownership documents;
- docs/project/PROJECT_STATE.md updated;
- docs/releases/CHANGELOG.md updated;
- docs/bootstrap/HANDOVER.md updated if navigation or operating context changed;
- docs/development/SYNC_QUEUE.md reviewed and synchronized.

---

# Git Workflow

Every implementation should follow the same sequence to keep the repository clean and make changes easy to review or revert.

## Standard Workflow

1. Review the current project state.
2. Create a snapshot commit before significant work.

Example commit message:

`docs: snapshot before <feature or refactoring>`

3. Implement the requested changes.
4. Run available tests.
5. Perform documentation synchronization (`DOCSYNC PC` or `DOCSYNC PC FULL`).
6. Review all modified files.
7. Create the final implementation commit.
8. Push to the remote repository when the user decides.

## Commit Message Convention

Official commit prefixes:

- `feat:` New functionality.
- `fix:` Bug fix.
- `docs:` Documentation only.
- `refactor:` Code restructuring without functional changes.
- `test:` Tests.
- `chore:` Maintenance tasks.
- `style:` Formatting or style-only changes.
- `perf:` Performance improvements.

## Snapshot Commits

Snapshot commits should be created before significant or risky work to preserve a clean rollback point.

Examples:

- Before documentation refactoring.
- Before large architectural changes.
- Before major UI redesigns.
- Before risky refactoring.

## Final Commits

Final commits should summarize the completed work.

Examples:

- `feat: complete DEV-003 candidate selection engine`
- `docs: reorganize documentation architecture`
- `refactor: simplify photo browser selection logic`

## AI Responsibilities

AI assistants should:

- Suggest creating a snapshot commit before major work.
- Never ask the user to commit after every tiny change.
- Group logically related changes into a single implementation commit.
- Keep commit messages short and meaningful.

## Definition of Done

The Git workflow is the official development workflow for Family Memory AI.

Future AI assistants should consistently follow this workflow.

### Permanent Definition of Done Requirements

A sprint or feature is complete only when all of the following are satisfied:

- Implementation is complete and working.
- Tests and/or manual validation are complete where applicable.
- Documentation is updated for all impacted areas.
- **A user-facing feature is not considered complete until its contextual Workspace Help accurately reflects the implemented functionality.**
- Workspace Help content is updated for every impacted user-facing workspace.
- docs/project/PROJECT_STATE.md is updated.
- docs/releases/CHANGELOG.md is updated.
- docs/development/SYNC_QUEUE.md is reviewed and cleared of completed items.

This Workspace Help requirement is a permanent project rule and cannot be waived.

## Documentation Validation Workflow

Recommended flow for documentation governance:

Development

↓

DOCSYNC

↓

VS Code Copilot

↓

Commit

↓

Export latest project ZIP

↓

DOCVERIFY

↓

If PASS

Continue development

If WARNING or FAIL

Generate follow-up prompts

### DOCSYNC Obligations

Every DOCSYNC execution must:

- Update contextual workspace Help content when functionality changes.
- Update workspace Help workflow descriptions when user interaction changes.
- Update workspace Help tips when new capabilities are introduced.
- Keep workspace Help synchronized with the current implementation at all times.

Workspace Help updates are mandatory during every DOCSYNC. They are not optional.

### DOCVERIFY Obligations

Every DOCVERIFY execution must verify:

- Every user-facing workspace has contextual Help content.
- Help content matches the currently implemented behavior.
- Help workflow descriptions are correct and up to date.
- Help tips remain valid for the current feature set.
- Help content has been updated after any UI or AI behavior change.

If Help is missing or outdated, it must be reported as a documentation issue with FAIL or WARNING status.

### Definition of Done Enforcement

- Future AI assistants must treat workspace Help updates as part of Definition of Done.
- A user-facing feature is not considered complete until its contextual Workspace Help has been updated and accurately reflects current functionality.
- DOCSYNC prepares and applies Help updates. DOCVERIFY validates that Help updates were applied correctly.
