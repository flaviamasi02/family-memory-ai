# Family Memory AI - Roadmap

## Purpose

This document tracks planned milestones only.

Implementation history belongs in CHANGELOG.md.

Current runtime status belongs in docs/PROJECT_STATE.md.

---

## Current Baseline

- Current version: v0.1.0
- Last completed sprint: Sprint 14
- Current phase: Early prototype hardening

---

## Near-Term Milestones

### M1 - Photo Grid Virtualization Foundation

Priority: High

Goal:
Improve scalability of the custom photo grid for large libraries by reducing widget creation/rendering overhead.

Success criteria:

- Large folders remain responsive during navigation.
- Progressive thumbnail flow remains stable.
- No regressions in details panel updates.

### M2 - Metadata Pipeline Hardening

Priority: High

Goal:
Strengthen metadata extraction and status handling for invalid files and edge cases.

Success criteria:

- Robust behavior with corrupt or incomplete image metadata.
- Clear and consistent status flow in UI.

### M3 - UI Stability and Selection Reliability

Priority: Medium

Goal:
Stabilize custom card selection behavior and reduce coupling between rendering and details updates.

Success criteria:

- Predictable selection behavior.
- Details panel always reflects the intended selected photo.

---

## Mid-Term Milestones

### M4 - Local Metadata Persistence Strategy

Priority: Medium

Goal:
Define and implement initial local persistence for metadata and indexing.

### M5 - AI Readiness Foundation

Priority: Medium

Goal:
Prepare interfaces and pipeline boundaries for future AI modules without introducing full AI features yet.

---

## Long-Term Milestones

- People recognition
- Duplicate and near-duplicate detection
- Memory scoring and preference learning
- Storytelling and album generation
- Natural language memory search
