from __future__ import annotations

from dataclasses import dataclass

from ui.help.workspace_help_content import (
    ALBUM_DRAFT_WORKSPACE,
    CLEANUP_REVIEW_WORKSPACE,
    MEMORY_REVIEW_WORKSPACE,
    PHOTO_BROWSER_WORKSPACE,
    SETTINGS_WORKSPACE,
)


@dataclass(frozen=True)
class WorkspaceInfoContent:
    title: str
    purpose: str
    purpose_details: str
    typical_actions: tuple[str, ...]
    tip: str
    collapsed_label: str = "Workspace overview"


WORKSPACE_INFO_CONTENT: dict[str, WorkspaceInfoContent] = {
    PHOTO_BROWSER_WORKSPACE: WorkspaceInfoContent(
        title="Photo Browser",
        purpose="Browse all imported photos and inspect the complete photo library.",
        purpose_details=(
            "Use this workspace to explore photos, filter the collection, open individual items and "
            "inspect available metadata."
        ),
        typical_actions=(
            "Browse imported photos",
            "Filter the library",
            "Select a photo",
            "Inspect photo details and metadata",
        ),
        tip="Open Workspace Help for a complete explanation of this workspace.",
    ),
    CLEANUP_REVIEW_WORKSPACE: WorkspaceInfoContent(
        title="Cleanup Review",
        purpose="Review media that may not be useful for the family memory collection.",
        purpose_details=(
            "The system suggests screenshots, documents, advertisements, memes and other "
            "cleanup-oriented media. Nothing must be permanently deleted automatically; "
            "the user remains in control."
        ),
        typical_actions=(
            "Review cleanup suggestions",
            "Correct media categories",
            "Select multiple items",
            "Move unwanted files to the safe cleanup location",
        ),
        tip="Open Workspace Help for a complete explanation of this workspace.",
    ),
    MEMORY_REVIEW_WORKSPACE: WorkspaceInfoContent(
        title="Memory Review",
        purpose="Teach Family Memory AI which photos and memories matter.",
        purpose_details=(
            "Use this workspace to correct categories, validate classifications, review memory "
            "candidates and provide learning signals for future recommendations."
        ),
        typical_actions=(
            "Review potential family memories",
            "Correct categories",
            "Review explanations",
            "Teach the system through user decisions",
        ),
        tip="Open Workspace Help for a complete explanation of this workspace.",
    ),
    ALBUM_DRAFT_WORKSPACE: WorkspaceInfoContent(
        title="Album Draft",
        purpose="Review the first automatically assembled draft of a family album.",
        purpose_details=(
            "The draft uses reviewed and scored memories as an output of the underlying memory "
            "knowledge."
        ),
        typical_actions=(
            "Review the proposed album structure",
            "Inspect selected memories",
            "Refine album content",
            "Prepare for future export workflows",
        ),
        tip="Open Workspace Help for a complete explanation of this workspace.",
    ),
    SETTINGS_WORKSPACE: WorkspaceInfoContent(
        title="Settings",
        purpose="Configure Family Memory AI and its local application behaviour.",
        purpose_details=(
            "Use this workspace to manage available application preferences and future "
            "configurable options."
        ),
        typical_actions=(
            "Review application settings",
            "Configure supported preferences",
            "Manage local behaviour",
            "Inspect available options",
        ),
        tip="Open Workspace Help for a complete explanation of this workspace.",
    ),
}
