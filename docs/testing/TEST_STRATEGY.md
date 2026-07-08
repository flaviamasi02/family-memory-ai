# Family Memory AI - Test Strategy

## Purpose

This document defines testing strategy, scope, and quality goals.

## Status

Initial placeholder created during documentation structure refactoring.

## TEST-001 Qt/PySide6 test environment

PySide6 widget tests must run with `QT_QPA_PLATFORM=offscreen` in local headless environments and in CI.
The GitHub Actions test workflow installs the Ubuntu Qt/OpenGL runtime packages needed for PySide6 imports and pytest collection, including the provider for `libGL.so.1`.

For local Linux runs, install equivalent system packages before running the full test suite, then run:

```bash
QT_QPA_PLATFORM=offscreen python -m pytest
```
