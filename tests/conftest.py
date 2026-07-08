"""Shared pytest configuration for local and CI test runs."""

import os
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"

if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

# Run Qt widget tests without requiring a visible display server.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
