# Family Memory AI
## Project Commands

This document defines all project commands used during Family Memory AI development.

Rules:
- Commands are case-insensitive.
- Commands must be executed automatically.
- The assistant should not ask for confirmation unless a command is ambiguous.
- This document is the authoritative reference for command behavior.
- DOCVERIFY commands are deterministic and verification-only.

---

## Command Structure

Every command must use this structure:

- Purpose: Why the command exists.
- Trigger: The command phrase that activates the workflow.
- Actions: Ordered steps the assistant must execute.
- Output: What the assistant must return to the user.
- Notes: Constraints, caveats, and integration details.

This structure is mandatory for consistency and easy extension.

---

## Command Prerequisites

Purpose:
Some commands require specific resources before they can execute.

General rules:
- Every command may declare prerequisites.
- If any mandatory prerequisite is missing, the command must not execute.
- The assistant must explain what is missing and wait for the required input.

Possible prerequisite types:
- Latest project ZIP
- Updated repository
- Repository access
- Specific documentation
- Configuration files
- Project source code
- External URL
- Required user confirmation

AI behavior:
- If prerequisites are satisfied, execute the command normally.
- If prerequisites are missing:
  1. Stop execution immediately.
  2. Explain which prerequisite is missing.
  3. Explain why it is required.
  4. Request the missing prerequisite.
  5. Wait for the user.

The AI must never:
- guess missing information
- estimate results
- claim success
- partially execute commands that require unavailable prerequisites

Standard prerequisite template:

Prerequisites:
Before execution, the following resources must be available:

- ...

If these prerequisites are not available, execution cannot begin.

Future commands:
Future commands should reuse this mechanism whenever appropriate.

Examples:
- DOCVERIFY
- IMPORT
- EXPORT
- ARCH REVIEW
- TEST
- BUILD
- Any future repository validation commands

---

## Official Command Grammar

Project commands must follow this grammar:

`<COMMAND_FAMILY> [CONTEXT] [MODE]`

Rules:

- `COMMAND_FAMILY` is mandatory and defines the operation group (for example `DOCSYNC`, `DOCVERIFY`, `SPRINT`, `DOC`, `STATUS`, `DECISION`, `HANDOVER`).
- `CONTEXT` is optional and narrows the execution scope (for example `PC`, `MOBILE`).
- `MODE` is optional and defines execution depth (for example `FULL`).
- Commands are case-insensitive.
- If a command is ambiguous, ask for clarification before execution.
- DOCVERIFY commands never modify documentation and never generate implementation prompts.

---

## DOCSYNC and DOCVERIFY Responsibilities

DOCSYNC:
- Preparation and synchronization only.
- May generate implementation prompts.
- Synchronizes documentation updates.
- Must update contextual workspace Help definitions when functionality, workflow, UI interaction, or AI decision behavior changes.
- Never performs repository verification.

DOCVERIFY:
- Verification only.
- Validates repository contents.
- Must verify contextual workspace Help coverage and behavioral accuracy for changed user-facing areas.
- Must report missing or outdated workspace Help as a documentation issue.
- Never generates implementation prompts.
- Never modifies documentation.

Canonical examples:

- `HANDOVER`
- `DOCSYNC PC`
- `DOCSYNC PC FULL`
- `DOCSYNC MOBILE`
- `DOCVERIFY PC`
- `DOCVERIFY PC FULL`
- `DOCVERIFY MOBILE`
- `DOCVERIFY MOBILE FULL`
- `SPRINT START`
- `SPRINT REVIEW`
- `DOC REVIEW`
- `STATUS`
- `DECISION`

---

## HANDOVER

Purpose:
Initialize a new ChatGPT session.

Trigger:
HANDOVER

Actions:
1. Read docs/bootstrap/HANDOVER.md.
2. Read every mandatory document listed in docs/bootstrap/HANDOVER.md.
3. Build project context.
4. Determine current sprint.
5. Determine project version.
6. Determine pending work.
7. Wait for user instructions.

Output:
- Short initialization summary with sprint, version, and pending work.

Notes:
- This command is required at the start of each new session.

---

## DOCSYNC PC

Purpose:
Synchronize project documentation after repository changes.

Trigger:
DOCSYNC PC

Actions:
1. Read docs/project/PROJECT_STATE.md.
2. Read docs/development/SYNC_QUEUE.md.
3. Detect pending documentation updates.
4. Verify documentation completeness for the implemented changes, including contextual workspace Help updates when user-facing behavior changed.
5. Update required documents.
6. Verify internal consistency.
7. Report completed updates.
8. Clear completed synchronization items.

Output:
- Documentation synchronization report.
- Documentation completeness status (complete, partial, or missing items).

Notes:
- Use this for regular desktop documentation synchronization.
- Preparation and synchronization only.
- May generate implementation prompts when required for follow-up implementation.
- Never perform repository verification.

---

## DOCSYNC PC FULL

Purpose:
Perform a complete documentation synchronization and documentation quality audit.

Trigger:
DOCSYNC PC FULL

Actions:
1. Execute DOCSYNC PC.
2. Verify all mandatory project documents.
3. Verify sprint consistency.
4. Verify version consistency.
5. Verify architecture references.
6. Verify decision references.
7. Verify broken document links.
8. Verify missing documentation.
9. Verify documentation completeness for all implemented and planned changes.
10. Run Documentation Health Check (mandatory phase).
11. Produce a final synchronization report and Documentation Health Report.
12. Verify MASTER_DEVELOPMENT_PLAN consistency, DOMAIN_ROADMAP consistency, active domain, current milestone, product vision alignment, and Family Memory Score alignment.

Documentation Health Check (mandatory):
1. Missing Documents: Detect references to documentation files that do not exist, including markdown files, architecture documents, playbooks, roadmaps, and glossaries.
2. Broken Links: Verify relative markdown links, internal anchors, Mermaid references, and cross-document links.
3. Documentation Ownership: Verify information is in the correct source document (for example, current sprint -> PROJECT_STATE, architecture decision -> DECISIONS, commands -> COMMANDS, highest-level planning -> MASTER_DEVELOPMENT_PLAN, product vision -> product/PRODUCT_VISION.md). Report misplaced or duplicated ownership.
4. Duplicate Information: Detect duplicated architecture descriptions, duplicated workflows, duplicated command definitions, and repeated glossary entries.
5. Outdated Documentation: Detect inconsistencies across PROJECT_STATE, MASTER_DEVELOPMENT_PLAN, ROADMAP, DOMAIN_ROADMAP, DECISIONS, architecture documents, and playbook (for example, completed sprint marked active, implemented feature undocumented, superseded decision not updated).
6. Missing Decision Records: Identify architectural changes that should have a DEC record but do not (for example, major folder reorganization, new subsystem, breaking architectural changes).
7. Missing Documentation: Detect newly introduced project concepts that are undocumented (for example, new engines, services, UI components, commands, workflows).
8. Documentation Completeness: Verify that every implemented change has its required documentation updates and ownership updates completed.
9. Terminology Consistency: Verify terminology against GLOSSARY.md and report inconsistent naming.
10. Folder Organization: Verify each document is located in the correct folder according to DOCUMENTATION_ARCHITECTURE.md.
11. AI Readiness: Verify a new AI assistant can bootstrap successfully and discover mandatory documents in the expected order: HANDOVER, DOCUMENTATION_FRAMEWORK, AI_BOOTSTRAP, COMMANDS, DOCUMENTATION_ARCHITECTURE, PROJECT_CONTEXT, PROJECT_STATE, AI_PROJECT_PLAYBOOK, DECISIONS, MASTER_DEVELOPMENT_PLAN, DOMAIN_ROADMAP, ROADMAP (historical/transitional, if present), GLOSSARY.
12. Domain Workflow Readiness: Verify MASTER_DEVELOPMENT_PLAN and DOMAIN_ROADMAP are referenced correctly, the active domain is clear, the current milestone is clear, and workflow planning aligns with product vision and Family Memory Score.

Output:
- Full synchronization report with findings and resolved items.
- Documentation Health Report including:
  - Overall Status: PASS, WARNING, or FAIL
  - Check Results for all health-check items
  - Warnings
  - Recommended Improvements
  - MASTER_DEVELOPMENT_PLAN consistency
  - DOMAIN_ROADMAP consistency
  - Active domain and current milestone status
  - Product vision alignment status

Notes:
- Use this after major sprint work or multi-session implementation.
- Documentation Health Check is mandatory on every DOCSYNC PC FULL execution.
- DOCSYNC PC FULL is the official documentation quality gate for Family Memory AI.
- Definition of Done: Every execution verifies synchronization and documentation quality, consistency, maintainability, and AI readiness.
- DOCSYNC commands enforce the constitutional principle "Documentation is Production Code".
- Preparation and synchronization only.
- May generate implementation prompts when required for follow-up implementation.
- Never perform repository verification.

---

## DOCSYNC MOBILE

Purpose:
Synchronize documentation when development has been performed from a mobile conversation.

Trigger:
DOCSYNC MOBILE

Actions:
1. Collect mobile-session decisions, changes, and approvals.
2. Map each item to required documentation updates.
3. Apply updates to project documents in repository.
4. Validate consistency against docs/project/PROJECT_STATE.md and docs/development/DECISIONS.md.
5. Record synchronized items in docs/development/SYNC_QUEUE.md.
6. Report completion and remaining follow-ups.

Output:
- Mobile synchronization report with completed and pending items.

Notes:
- This command is optimized for cross-device continuity.
- Preparation and synchronization only.
- May generate implementation prompts when required for follow-up implementation.
- Never perform repository verification.

---

## DOCVERIFY PC

Purpose:
Verify that approved documentation changes have been successfully applied.
DOCVERIFY performs validation only.
It does not modify documentation.

Trigger:
DOCVERIFY PC

Prerequisites:
Use the generic Command Prerequisites mechanism.

Repository Requirement:
Verification requires at least one of the following:

- latest project ZIP
- updated repository
- updated project files

If none are available, stop execution and request the missing repository.

Expected input:
- Updated repository snapshot (for example ZIP or accessible repository)
- Relevant modified files when available

Actions:
1. Validate command prerequisites.
2. Read the updated documentation.
3. Compare repository documents against approved changes from the current conversation.
4. Verify that required updates have been applied.
5. Detect missing updates.
6. Detect inconsistencies.
7. Produce a verification report.

Output:
- Verification Report including:
  - Overall Status: PASS, WARNING, or FAIL
  - Verification Summary
  - Verified updates
  - Missing updates
  - Documentation inconsistencies
  - Recommended follow-up actions

Notes:
- Verification only: do not modify documentation.
- Do not generate implementation prompts.
- Deterministic execution.
- Follow the generic Command Prerequisites mechanism.

---

## DOCVERIFY PC FULL

Purpose:
Everything from DOCVERIFY PC plus full documentation quality verification.

Trigger:
DOCVERIFY PC FULL

Prerequisites:
Use the generic Command Prerequisites mechanism.

Repository Requirement:
Verification requires at least one of the following:

- latest project ZIP
- updated repository
- updated project files

If none are available, stop execution and request the missing repository.

Actions:
1. Validate command prerequisites.
2. Execute DOCVERIFY PC.
3. Run Documentation Health Check verification:
   - Broken links
   - Ownership validation
   - Terminology validation
   - Command consistency
   - Bootstrap validation
   - Framework version validation
   - Documentation Minimalism validation
   - Cross-reference validation
   - Architecture consistency
  - MASTER_DEVELOPMENT_PLAN consistency
  - DOMAIN_ROADMAP consistency
  - active domain and current milestone consistency
  - product vision alignment
  - Family Memory Score alignment
4. Produce a full verification report.

Output:
- Full Verification Report including:
  - Overall Status: PASS, WARNING, or FAIL
  - Verification Summary
  - Verified updates
  - Missing updates
  - Documentation inconsistencies
  - Recommended follow-up actions

Notes:
- Verification only: do not modify documentation.
- Do not generate implementation prompts.
- Deterministic execution.
- Follow the generic Command Prerequisites mechanism.

---

## DOCVERIFY MOBILE

Purpose:
Same behavior as DOCVERIFY PC, intended for repositories updated through mobile-assisted development.

Trigger:
DOCVERIFY MOBILE

Prerequisites:
Use the generic Command Prerequisites mechanism.

Repository Requirement:
Verification requires at least one of the following:

- latest project ZIP
- updated repository
- updated project files

If none are available, stop execution and request the missing repository.

Actions:
1. Validate command prerequisites.
2. Execute DOCVERIFY PC using the mobile-updated repository snapshot.
3. Keep verification scope aligned with mobile-originated changes.
4. Produce a verification report.

Output:
- Verification Report including status, verified updates, missing updates, inconsistencies, and follow-up actions.

Notes:
- Verification only: do not modify documentation.
- Do not generate implementation prompts.
- Deterministic execution.
- Follow the generic Command Prerequisites mechanism.

---

## DOCVERIFY MOBILE FULL

Purpose:
Same behavior as DOCVERIFY PC FULL, intended for repositories updated through mobile-assisted development.

Trigger:
DOCVERIFY MOBILE FULL

Prerequisites:
Use the generic Command Prerequisites mechanism.

Repository Requirement:
Verification requires at least one of the following:

- latest project ZIP
- updated repository
- updated project files

If none are available, stop execution and request the missing repository.

Actions:
1. Validate command prerequisites.
2. Execute DOCVERIFY MOBILE.
3. Execute full health-check validations from DOCVERIFY PC FULL.
4. Produce a full verification report.

Output:
- Full Verification Report including status, verified updates, missing updates, inconsistencies, and follow-up actions.

Notes:
- Verification only: do not modify documentation.
- Do not generate implementation prompts.
- Deterministic execution.
- Follow the generic Command Prerequisites mechanism.

---

## DOCVERIFY Limitations

- DOCVERIFY can only validate repository contents provided by the user.
- DOCVERIFY cannot verify repositories that are not accessible.
- If no updated repository is available, the verification process must stop and return this exact response:

"Please upload the latest project ZIP (or provide access to the updated repository) so I can verify that the approved changes have actually been implemented."

This requirement is mandatory for:

- DOCVERIFY PC
- DOCVERIFY PC FULL
- DOCVERIFY MOBILE
- DOCVERIFY MOBILE FULL

---

## DOCVERIFY Conversation Behaviour

DOCVERIFY follows the generic Command Prerequisites mechanism defined in this document.

When repository prerequisites are missing, use the required response defined in DOCVERIFY Limitations and wait for the user.

---

## SPRINT START

Purpose:
Start implementation of the current sprint.

Trigger:
SPRINT START

Actions:
1. Identify current sprint.
2. Explain architecture before implementation.
3. Prepare implementation plan.
4. Generate implementation prompt.
5. Wait for approval if architectural decisions are required.

Output:
- Sprint start plan and implementation prompt.

Notes:
- Respect approved decisions and current sprint boundaries.

---

## SPRINT REVIEW

Purpose:
Review implementation quality.

Trigger:
SPRINT REVIEW

Actions:
1. Review code.
2. Review architecture.
3. Review tests.
4. Review documentation.
5. List improvements.

Output:
- Structured review report with findings and recommendations.

Notes:
- Prioritize correctness, regressions, and maintainability.

---

## DECISION

Purpose:
Register a new architectural decision.

Trigger:
DECISION

Actions:
1. Assign next DEC number.
2. Update docs/development/DECISIONS.md.
3. Update docs/project/PROJECT_STATE.md if necessary.
4. Update architecture references if affected.

Output:
- Decision record summary with impacted documents and sprint impact.

Notes:
- Never create decisions without explicit approval.

---

## DOC REVIEW

Purpose:
Review all documentation.

Trigger:
DOC REVIEW

Actions:
1. Detect inconsistencies.
2. Detect duplicated information.
3. Detect outdated information.
4. Suggest improvements.

Output:
- Documentation review report with prioritized actions.

Notes:
- Preserve single-source-of-truth boundaries.

---

## STATUS

Purpose:
Provide a project status summary.

Trigger:
STATUS

Actions:
1. Read docs/project/PROJECT_STATE.md.
2. Cross-check docs/development/DECISIONS.md and docs/project/ROADMAP.md when needed.
3. Produce current snapshot.

Output should include:
- Current version
- Current sprint
- Completed sprints
- Current priorities
- Known blockers
- Documentation status

Notes:
- Keep output concise and fact-based.

---

## Global Rules

- Always use English for project artifacts.
- Explain architectural changes before implementation.
- Never mark a sprint complete unless Definition of Done is satisfied.
- Always update docs/project/PROJECT_STATE.md after implementation.
- Never invent project decisions.
- Always follow docs/development/DECISIONS.md.
- Always follow docs/development/AI_PROJECT_PLAYBOOK.md.
- Always follow docs/bootstrap/HANDOVER.md.
- Always follow this COMMANDS.md.
- Commands may call other commands internally.
- DOCSYNC prepares documentation updates; DOCVERIFY validates repository application of those updates.

---

## Extending the Command System

When adding new commands:
1. Add a new section in this document.
2. Use the mandatory Command Structure.
3. Define clear actions and expected output.
4. Reference impacted documents.
5. Validate alignment with Global Rules.

Compatibility guidance:
- Future commands should remain backward compatible whenever possible.
- Existing command semantics must not change without explicit approval.
