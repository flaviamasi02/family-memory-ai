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
Create DECISIONS.md

Approved.

### DEC-0004
Create SYNC_QUEUE.md

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
PROMPT_TEMPLATE.md

Approved.

### DEC-0009
AI_PROJECT_PLAYBOOK.md

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
- PROJECT_CONTEXT.md
- PROJECT_STATE.md
- ROADMAP.md
- HANDOVER.md

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

Version 1 of Family Memory AI has one primary objective:

> "Automatically create the best possible annual family photo album."

Future album types including:
- Vacation Albums
- Gift Albums
- Event Albums
- Story Timeline

are approved future directions but are **NOT** part of Version 1.

The architecture should remain extensible.

**Impacted documents:**
- PROJECT_CONTEXT.md
- PROJECT_STATE.md
- ROADMAP.md
- HANDOVER.md

### DEC-0025
Print Ready Export

**Value:** Product  
**Impact:** Medium

Decision:

The final objective is to export a print-ready album for external printing providers (initial target: CEWE/Crew), while keeping the export engine provider-independent.

**Impacted documents:**
- ROADMAP.md
- PROJECT_STATE.md
- HANDOVER.md
- ARCHITECTURE.md

**Impacted Sprints:**
DEV-006 and DEV-007.

### DEC-0026
DOCSYNC Command

**Value:** Method  
**Impact:** Low

Decision:

Documentation synchronization is performed through DOCSYNC PC / DOCSYNC MOBILE commands.

**Impacted documents:**
- HANDOVER.md
- AI_PROJECT_PLAYBOOK.md
- SYNC_QUEUE.md

**Impacted Sprints:**
Documentation sprints and end-of-sprint sync activity.

### DEC-0027
Photo Intelligence Foundation

**Value:** Product  
**Impact:** Medium

Decision:

Before implementing selection rules or AI ranking, the project will first build a Photo Intelligence model.

**Impacted documents:**
- ROADMAP.md
- PROJECT_STATE.md
- HANDOVER.md

**Impacted Sprints:**
DEV-002 and later.
