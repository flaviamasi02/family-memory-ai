"""Confirmation-gated, reversible CLEAN-004 Trash workflow.

This service never deletes.  UI and other callers must confirm records before
calling ``move_confirmed``; proposed records are ignored by design.
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable

from core.safe_file_move_service import TRASH_FOLDER_NAME, move_file_safely

WORKFLOW_STATES = frozenset({
    "proposed_to_trash", "confirmed_to_trash", "moved_to_trash", "move_failed", "restored",
})


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class TrashRecord:
    photo_id: str
    source_path: str
    state: str = "proposed_to_trash"
    destination_path: str = ""
    confidence: float = 0.0
    proposal_source: str = ""
    explanation: str = ""
    error: str = ""
    history: list[dict[str, str]] = field(default_factory=list)


@dataclass
class TrashOperationResult:
    requested_count: int = 0
    moved_count: int = 0
    failed_count: int = 0
    restored_count: int = 0
    records: list[TrashRecord] = field(default_factory=list)

    @property
    def message(self) -> str:
        if self.failed_count:
            return f"{self.moved_count} of {self.requested_count} photos moved to Trash. {self.failed_count} could not be moved."
        return f"{self.moved_count} photos moved to Trash."


class TrashWorkflowService:
    def __init__(self, library_root: str | Path, *, repository_root: str | Path | None = None):
        self.library_root = Path(library_root).resolve()
        self.repository_root = Path(repository_root or Path.cwd()).resolve()

    @property
    def default_destination(self) -> Path:
        return self.library_root.parent / TRASH_FOLDER_NAME

    def validate_destination(self, destination: str | Path) -> Path:
        target = Path(destination).expanduser().resolve()
        if target == self.library_root or self.library_root in target.parents:
            raise ValueError("Trash destination cannot be inside an actively scanned library")
        if target == self.repository_root or self.repository_root in target.parents:
            raise ValueError("Trash destination cannot be inside the application repository")
        return target

    def confirm(self, records: Iterable[TrashRecord]) -> list[TrashRecord]:
        now = _now()
        result = []
        for record in records:
            if record.state == "proposed_to_trash":
                record.state = "confirmed_to_trash"
                record.history.append({"action": "confirmed_to_trash", "timestamp": now})
            result.append(record)
        return result

    def reject(self, record: TrashRecord, category: str) -> TrashRecord:
        record.state = "restored"
        record.history.append({"action": "proposal_rejected", "category": category, "timestamp": _now()})
        return record

    def move_confirmed(self, records: Iterable[TrashRecord], destination: str | Path | None = None,
                       *, on_change: Callable[[TrashRecord], None] | None = None) -> TrashOperationResult:
        confirmed = [record for record in records if record.state in {"confirmed_to_trash", "move_failed"}]
        result = TrashOperationResult(requested_count=len(confirmed))
        target = self.validate_destination(destination or self.default_destination)
        for record in confirmed:
            original = record.source_path
            try:
                moved = move_file_safely(original, target)
                record.destination_path = str(moved)
                record.state = "moved_to_trash"
                record.error = ""
                record.history.append({"action": "moved_to_trash", "source": original,
                                       "destination": str(moved), "timestamp": _now()})
                result.moved_count += 1
            except Exception as exc:
                record.state = "move_failed"
                record.error = str(exc)
                record.history.append({"action": "move_failed", "source": original,
                                       "error": str(exc), "timestamp": _now()})
                result.failed_count += 1
            if on_change:
                on_change(record)
            result.records.append(record)
        return result

    def restore(self, records: Iterable[TrashRecord], destination: str | Path | None = None,
                *, on_change: Callable[[TrashRecord], None] | None = None) -> TrashOperationResult:
        moved = [record for record in records if record.state == "moved_to_trash"]
        result = TrashOperationResult(requested_count=len(moved))
        for record in moved:
            target = Path(destination) if destination else Path(record.source_path).parent
            try:
                restored = move_file_safely(record.destination_path, target)
                record.destination_path = str(restored)
                record.state = "restored"
                record.error = ""
                record.history.append({"action": "restored", "destination": str(restored), "timestamp": _now()})
                result.restored_count += 1
            except Exception as exc:
                record.error = str(exc)
                result.failed_count += 1
            if on_change:
                on_change(record)
            result.records.append(record)
        return result

    @staticmethod
    def save_history(path: str | Path, records: Iterable[TrashRecord]) -> None:
        """Atomically persist sidecar audit/history without touching originals."""
        output = Path(path)
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = output.with_suffix(output.suffix + ".tmp")
        temporary.write_text(json.dumps([asdict(record) for record in records], indent=2), encoding="utf-8")
        os.replace(temporary, output)
