from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class WorkspaceHelpTip:
    """Represents one tip card shown in workspace help."""

    title: str
    body: str


@dataclass(frozen=True)
class WorkspaceAIStatusMetric:
    """Represents one AI status metric and progress value."""

    label: str
    progress_percent: int
    description: str = ""

    def normalized_progress(self) -> int:
        return max(0, min(100, int(self.progress_percent)))


@dataclass(frozen=True)
class WorkspaceHelpSection:
    """Generic section model used by WorkspaceHelpPanel renderers."""

    key: str
    title: str
    kind: str
    icon: str = ""
    payload: Any = None


@dataclass(frozen=True)
class WorkspaceHelpDefinition:
    """Help definition for a single workspace."""

    workspace_id: str
    title: str
    sections: tuple[WorkspaceHelpSection, ...] = field(default_factory=tuple)
