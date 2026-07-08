# Family Memory AI - Test Strategy

## Purpose

This document defines testing strategy, scope, and quality goals.

## Status

Initial placeholder created during documentation structure refactoring.

## Local and CI PySide6 Test Environment

Family Memory AI includes PySide6 UI tests and image-processing tests that import Qt modules during pytest collection. On Linux, those imports require native Qt/OpenGL runtime libraries in addition to the Python packages from `requirements.txt`.

For Debian/Ubuntu-based local or CI environments, install these packages before running pytest:

```bash
sudo apt-get update
sudo apt-get install -y \
  libgl1 \
  libegl1 \
  libxkbcommon-x11-0 \
  libxcb-cursor0 \
  libxcb-icccm4 \
  libxcb-image0 \
  libxcb-keysyms1 \
  libxcb-randr0 \
  libxcb-render-util0 \
  libxcb-shape0 \
  libxcb-xinerama0
```

The repository pytest setup adds `src/` to the import path and defaults `QT_QPA_PLATFORM=offscreen` so widget tests can run in headless environments. The GitHub Actions test workflow applies the same setup before running source compilation, pytest collection, and the full pytest suite.
