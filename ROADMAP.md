# Family Memory AI - Roadmap

## Purpose

This document tracks planned milestones only.

Implementation history belongs in CHANGELOG.md.

Current runtime status belongs in docs/PROJECT_STATE.md.

---

## Version 1 (Current Focus)

Version 1 is dedicated **exclusively** to the **Annual Family Album**.

- Annual Family Album

Current implementation baseline:

- Annual album domain foundation completed (DEV-001)
	- AnnualAlbum model
	- AlbumBuilder year grouping and annual album creation
	- Candidate pool initialization from matching-year photos
	- No AI selection and no export pipeline yet
- Photo intelligence foundation completed (DEV-002)
	- PhotoIntelligence model
	- Photo linkage and safe initialization
	- Metadata-based year/month intelligence population
	- Foundation placeholders only (no AI/selection engines yet)

Technical development sequence:

- DEV-001 Annual Album Foundation (Completed)
- DEV-002 Photo Intelligence Foundation (Completed)
- DEV-003 Candidate Selection Engine (Next)
- DEV-004 Album Scoring Engine
- DEV-005 Album Review UI
- DEV-006 Album Layout Engine
- DEV-007 Print Ready Export

---

## Future Roadmap (Post Version 1)

- Vacation Albums
- Gift Albums
- Event Albums
- Story Timeline
