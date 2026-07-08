# Family Memory AI - Test Strategy

## Purpose

This document defines testing strategy, scope, and quality goals.

## Status

Initial placeholder created during documentation structure refactoring.

## TEST-001 Qt/PySide6 test environment

Status: Completed.

PySide6 widget tests must run with `QT_QPA_PLATFORM=offscreen` in local headless environments and in CI.
The GitHub Actions test workflow installs pytest and the Ubuntu Qt/OpenGL runtime packages needed for PySide6 imports and pytest collection, including the provider for `libGL.so.1`.

CI sets `QT_QPA_PLATFORM=offscreen` so PySide6 widget tests can run headlessly on Ubuntu runners.

The GitHub Actions test workflow runs:

- Python source compilation with `py_compile`
- pytest collection with `python -m pytest --collect-only`
- the full pytest suite with `python -m pytest`

For local Linux runs, install equivalent system packages before running the full test suite, then run:

```bash
QT_QPA_PLATFORM=offscreen python -m pytest
```
