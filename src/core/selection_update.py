"""Small UI-independent helpers for incremental review selection updates."""
from __future__ import annotations


def changed_selection_keys(previous: set[str], current: set[str]) -> set[str]:
    """Return only keys whose highlight state changed."""
    return previous.symmetric_difference(current)
