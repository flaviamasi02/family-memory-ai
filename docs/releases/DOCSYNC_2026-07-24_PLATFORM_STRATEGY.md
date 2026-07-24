# DOCSYNC Record - Desktop-First, Mobile-Ready Platform Strategy

**Date:** 2026-07-24  
**Command:** DOCSYNC GITHUB FULL  
**Status:** Prepared in draft pull request

## Approved decision synchronized

Family Memory AI will continue as a Windows-first product until the desktop core workflow is validated. Complete desktop and mobile applications will not be developed in parallel.

All future desktop work must remain mobile-ready by keeping reusable business logic independent from PySide6 wherever practical. Android is the planned second client after core validation, beginning with a focused companion MVP for recent-photo review and teaching workflows.

## Canonical documentation result

- Added `docs/architecture/PLATFORM_STRATEGY.md` as the detailed canonical platform decision.
- Updated `docs/project/ROADMAP.md` with the approved platform delivery phases and explicit non-parallel strategy.
- Proposed decision ledger identifier: `DEC-0049 - Desktop-First, Mobile-Ready Platform Strategy`.

## Consistency rules established

- Desktop remains the active implementation target.
- Core extraction occurs incrementally, not through a large rewrite.
- PySide6 remains a presentation layer.
- Business logic must not be implemented inside UI widgets.
- Platform-specific file and photo access must remain behind boundaries.
- Mobile starts after a validated desktop workflow and a clear Android MVP scope.
- Cloud upload is not mandatory for mobile support.
- Android, iPhone, Windows, and web will not be developed simultaneously.

## Follow-through rule

When this pull request is merged, future DOCSYNC runs must treat `docs/architecture/PLATFORM_STRATEGY.md` and the platform section of `docs/project/ROADMAP.md` as authoritative. Any future changes to platform sequencing require explicit Product Owner approval and a new decision-ledger entry.
