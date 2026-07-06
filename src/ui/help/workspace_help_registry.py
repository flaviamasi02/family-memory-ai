from __future__ import annotations

from ui.help.workspace_help_content import build_workspace_help_definitions
from ui.help.workspace_help_models import WorkspaceHelpDefinition


class WorkspaceHelpRegistry:
    """Provides workspace help definitions by workspace identifier."""

    def __init__(self):
        definitions = list(build_workspace_help_definitions())
        self._definitions_by_id = {definition.workspace_id: definition for definition in definitions}
        self._fallback = definitions[0] if definitions else WorkspaceHelpDefinition(
            workspace_id="unknown",
            title="Workspace",
            sections=tuple(),
        )

    def get(self, workspace_id: str) -> WorkspaceHelpDefinition:
        key = str(workspace_id or "").strip()
        if not key:
            return self._fallback
        return self._definitions_by_id.get(key, self._fallback)

    def all_workspace_ids(self) -> list[str]:
        return sorted(self._definitions_by_id.keys())
