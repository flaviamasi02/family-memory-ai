from __future__ import annotations

import json
import os
import tempfile
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from core.application_data import get_app_data_service, atomic_write_json


@dataclass
class CategoryDefinition:
    id: str
    display_name: str
    description: str
    ai_description: str
    color: str
    icon: str
    is_system: bool
    is_cleanup_category: bool
    is_album_candidate: bool
    created_at: str
    updated_at: str

    @property
    def type(self) -> str:
        return "system" if self.is_system else "user"

    @property
    def is_album_candidate_category(self) -> bool:
        return self.is_album_candidate


_SYSTEM_CATEGORIES: list[tuple[str, str, str, bool, bool]] = [
    ("family_photo", "Family Photo", "Default family memory candidate.", False, True),
    ("personal_photo", "Personal Photo", "Personal moments and portraits.", False, True),
    ("screenshot", "Screenshot", "Captured screen content.", True, False),
    ("document", "Document", "Generic document media.", True, False),
    ("receipt", "Receipt", "Receipt or payment proof.", True, False),
    ("invoice", "Invoice", "Invoice or bill media.", True, False),
    ("advertisement", "Advertisement", "Promotional or ad media.", True, False),
    ("meme", "Meme", "Meme-like media.", True, False),
    ("graphic", "Graphic", "Graphic or design media.", True, False),
    ("video", "Video", "Video media.", True, False),
    ("duplicate_candidate", "Duplicate Candidate", "Likely duplicate media.", True, False),
    ("low_quality", "Low Quality", "Low-quality image candidate.", True, False),
    ("unknown", "Unknown", "Unclassified media.", True, False),
    # Compatibility IDs currently produced/used in cleanup flows.
    ("family_photo_candidate", "Family photos", "Cleanup family-photo candidate.", True, True),
    ("document_or_scan", "Documents", "Cleanup document/scan category.", True, False),
    ("meme_or_graphic", "Memes", "Cleanup meme/graphic category.", True, False),
    ("low_quality_photo", "Low quality", "Cleanup low-quality category.", True, False),
]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class CategoryRegistry:
    def __init__(self, storage_root: Optional[str | Path] = None):
        configured_root = storage_root if storage_root is not None else os.environ.get("FAMILY_MEMORY_CATEGORIES_ROOT")
        service = get_app_data_service(
            configured_root,
            legacy_root=Path.cwd(),
            migrate_legacy=configured_root is None,
        )
        self._storage_root = service.root
        self.migration_diagnostics = service.diagnostics
        self._storage_path = service.config_path("categories.json")
        self._categories: dict[str, CategoryDefinition] = {}
        self._system_defaults: dict[str, CategoryDefinition] = {}
        self._bootstrap_system_categories()
        self._load_persisted_categories()

    @property
    def storage_path(self) -> Path:
        return self._storage_path

    def all_categories(self) -> list[CategoryDefinition]:
        return [self._categories[category_id] for category_id in self.ordered_ids()]

    def ordered_ids(self) -> list[str]:
        system_ids = [cid for cid, item in self._categories.items() if item.is_system]
        user_ids = [cid for cid, item in self._categories.items() if not item.is_system]
        system_ids.sort(key=lambda cid: self._system_index(cid))
        user_ids.sort(key=lambda cid: self._categories[cid].display_name.lower())
        return system_ids + user_ids

    def cleanup_category_ids(self) -> list[str]:
        return [
            category_id
            for category_id in self.ordered_ids()
            if self._categories[category_id].is_cleanup_category
        ]

    def is_cleanup_category(self, category_id: str) -> bool:
        item = self.get(category_id)
        return bool(item.is_cleanup_category) if item is not None else False

    def is_album_candidate_category(self, category_id: str) -> bool:
        item = self.get(category_id)
        return bool(item.is_album_candidate) if item is not None else False

    def has_category(self, category_id: str) -> bool:
        return str(category_id or "").strip().lower() in self._categories

    def get(self, category_id: str) -> Optional[CategoryDefinition]:
        return self._categories.get(str(category_id or "").strip().lower())

    def label_for(self, category_id: str) -> str:
        item = self.get(category_id)
        if item is not None:
            return item.display_name
        return str(category_id or "Unknown").replace("_", " ").title()

    def create_user_category(
        self,
        display_name: str,
        description: str = "",
        ai_description: str = "",
        is_cleanup_category: bool = True,
        is_album_candidate: bool = False,
        color: str = "",
        icon: str = "",
    ) -> CategoryDefinition:
        clean_name = str(display_name or "").strip()
        if not clean_name:
            raise ValueError("Category name is required")

        if self._display_name_exists(clean_name):
            raise ValueError("A category with this name already exists")

        category_id = self._slugify(clean_name)
        if not category_id:
            raise ValueError("Category name must contain letters or numbers")
        if category_id in self._categories:
            raise ValueError("A category with this ID already exists")

        now = _now_iso()
        item = CategoryDefinition(
            id=category_id,
            display_name=clean_name,
            description=str(description or "").strip(),
            ai_description=str(ai_description or "").strip(),
            color=str(color or "").strip(),
            icon=str(icon or "").strip(),
            is_system=False,
            is_cleanup_category=bool(is_cleanup_category),
            is_album_candidate=bool(is_album_candidate),
            created_at=now,
            updated_at=now,
        )
        self._categories[item.id] = item
        self._save_categories()
        return item

    def rename_user_category(self, category_id: str, new_display_name: str) -> CategoryDefinition:
        return self.update_category_properties(category_id=category_id, display_name=new_display_name)

    def update_category_properties(
        self,
        category_id: str,
        display_name: Optional[str] = None,
        description: Optional[str] = None,
        ai_description: Optional[str] = None,
        color: Optional[str] = None,
        icon: Optional[str] = None,
        is_cleanup_category: Optional[bool] = None,
        is_album_candidate: Optional[bool] = None,
    ) -> CategoryDefinition:
        item = self.get(category_id)
        if item is None:
            raise ValueError("Category not found")

        if display_name is not None:
            name = str(display_name or "").strip()
            if not name:
                raise ValueError("Category name is required")
            if item.display_name.lower() != name.lower() and self._display_name_exists(name, exclude_id=item.id):
                raise ValueError("A category with this name already exists")
            item.display_name = name

        if description is not None:
            item.description = str(description or "").strip()
        if ai_description is not None:
            item.ai_description = str(ai_description or "").strip()
        if color is not None:
            item.color = str(color or "").strip()
        if icon is not None:
            item.icon = str(icon or "").strip()
        if is_cleanup_category is not None:
            item.is_cleanup_category = bool(is_cleanup_category)
        if is_album_candidate is not None:
            item.is_album_candidate = bool(is_album_candidate)

        item.updated_at = _now_iso()
        self._categories[item.id] = item
        self._save_categories()
        return item

    def update_user_category_flags(
        self,
        category_id: str,
        is_cleanup_category: bool,
        is_album_candidate: bool,
        description: Optional[str] = None,
        ai_description: Optional[str] = None,
        color: Optional[str] = None,
        icon: Optional[str] = None,
    ) -> CategoryDefinition:
        item = self._require_user_category(category_id)
        return self.update_category_properties(
            category_id=item.id,
            is_cleanup_category=is_cleanup_category,
            is_album_candidate=is_album_candidate,
            description=description,
            ai_description=ai_description,
            color=color,
            icon=icon,
        )

    def reset_system_category_to_default(self, category_id: str) -> CategoryDefinition:
        target_id = str(category_id or "").strip().lower()
        default_item = self._system_defaults.get(target_id)
        if default_item is None:
            raise ValueError("System category not found")

        current = self._categories.get(target_id)
        if current is None or not current.is_system:
            raise ValueError("System category not found")

        current.display_name = default_item.display_name
        current.description = default_item.description
        current.ai_description = default_item.ai_description
        current.color = default_item.color
        current.icon = default_item.icon
        current.is_cleanup_category = default_item.is_cleanup_category
        current.is_album_candidate = default_item.is_album_candidate
        current.updated_at = _now_iso()
        self._categories[current.id] = current
        self._save_categories()
        return current

    def delete_user_category(
        self,
        category_id: str,
        used_count: int = 0,
        reassign_to: str = "",
    ) -> tuple[bool, str]:
        item = self.get(category_id)
        if item is None:
            return False, "Category not found"
        if item.is_system:
            return False, "System categories cannot be deleted"

        if int(used_count) > 0 and not str(reassign_to or "").strip():
            return False, "Category is in use; choose a reassignment category first"

        self._categories.pop(item.id, None)
        self._save_categories()
        return True, ""

    def _bootstrap_system_categories(self) -> None:
        now = _now_iso()
        for category_id, display_name, description, is_cleanup, is_album_candidate in _SYSTEM_CATEGORIES:
            item = CategoryDefinition(
                id=category_id,
                display_name=display_name,
                description=description,
                ai_description="",
                color="",
                icon="",
                is_system=True,
                is_cleanup_category=is_cleanup,
                is_album_candidate=is_album_candidate,
                created_at=now,
                updated_at=now,
            )
            self._categories[category_id] = item
            self._system_defaults[category_id] = CategoryDefinition(**asdict(item))

    def _load_persisted_categories(self) -> None:
        if not self._storage_path.exists():
            return
        try:
            payload = json.loads(self._storage_path.read_text(encoding="utf-8"))
        except Exception:
            return

        if isinstance(payload, dict):
            system_items = payload.get("system_overrides", [])
            items = payload.get("categories", [])
        else:
            # Backward compatibility with old format where payload was just a categories list.
            system_items = []
            items = payload if isinstance(payload, list) else []

        if isinstance(system_items, list):
            for raw in system_items:
                self._apply_system_override(raw)

        # Backward compatibility: if system entries were historically written in categories list,
        # treat them as overrides instead of user categories.
        if isinstance(items, list):
            for raw in items:
                if isinstance(raw, dict) and bool(raw.get("is_system", False)):
                    self._apply_system_override(raw)

        if not isinstance(items, list):
            return

        for raw in items:
            if not isinstance(raw, dict):
                continue
            category_id = str(raw.get("id", "")).strip().lower()
            if not category_id:
                continue

            if category_id in self._system_defaults:
                # already handled through system overrides path
                continue

            display_name = str(raw.get("display_name", "")).strip()
            if not display_name:
                continue

            item = CategoryDefinition(
                id=category_id,
                display_name=display_name,
                description=str(raw.get("description", "") or "").strip(),
                ai_description=str(raw.get("ai_description", "") or "").strip(),
                color=str(raw.get("color", "") or "").strip(),
                icon=str(raw.get("icon", "") or "").strip(),
                is_system=bool(raw.get("is_system", False)),
                is_cleanup_category=bool(raw.get("is_cleanup_category", True)),
                is_album_candidate=bool(
                    raw.get("is_album_candidate", raw.get("is_album_candidate_category", False))
                ),
                created_at=str(raw.get("created_at", _now_iso())),
                updated_at=str(raw.get("updated_at", _now_iso())),
            )
            self._categories[item.id] = item

    def _apply_system_override(self, raw: dict) -> None:
        if not isinstance(raw, dict):
            return
        category_id = str(raw.get("id", "")).strip().lower()
        if not category_id:
            return
        default_item = self._system_defaults.get(category_id)
        current = self._categories.get(category_id)
        if default_item is None or current is None or not current.is_system:
            return

        display_name = str(raw.get("display_name", current.display_name)).strip()
        if display_name and self._display_name_exists(display_name, exclude_id=current.id):
            display_name = current.display_name
        if display_name:
            current.display_name = display_name

        current.description = str(raw.get("description", current.description) or "").strip()
        current.ai_description = str(raw.get("ai_description", current.ai_description) or "").strip()
        current.color = str(raw.get("color", current.color) or "").strip()
        current.icon = str(raw.get("icon", current.icon) or "").strip()
        current.is_cleanup_category = bool(raw.get("is_cleanup_category", current.is_cleanup_category))
        current.is_album_candidate = bool(
            raw.get("is_album_candidate", raw.get("is_album_candidate_category", current.is_album_candidate))
        )
        current.updated_at = str(raw.get("updated_at", current.updated_at) or current.updated_at)
        self._categories[current.id] = current

    def _save_categories(self) -> None:
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
        user_items = [
            asdict(self._categories[category_id])
            for category_id in self.ordered_ids()
            if not self._categories[category_id].is_system
        ]
        system_overrides = [
            asdict(self._categories[category_id])
            for category_id in self.ordered_ids()
            if self._categories[category_id].is_system and self._is_system_overridden(category_id)
        ]
        payload = {"system_overrides": system_overrides, "categories": user_items}
        payload["schema_version"] = 1
        payload["updated_at"] = _now_iso()
        atomic_write_json(self._storage_path, payload)

    def _is_system_overridden(self, category_id: str) -> bool:
        current = self._categories.get(category_id)
        default_item = self._system_defaults.get(category_id)
        if current is None or default_item is None:
            return False
        return any(
            [
                current.display_name != default_item.display_name,
                current.description != default_item.description,
                current.ai_description != default_item.ai_description,
                current.color != default_item.color,
                current.icon != default_item.icon,
                current.is_cleanup_category != default_item.is_cleanup_category,
                current.is_album_candidate != default_item.is_album_candidate,
            ]
        )

    def _display_name_exists(self, display_name: str, exclude_id: str = "") -> bool:
        target = str(display_name or "").strip().lower()
        if not target:
            return False
        excluded = str(exclude_id or "").strip().lower()
        return any(
            item.display_name.strip().lower() == target and item.id != excluded
            for item in self._categories.values()
        )

    def _require_user_category(self, category_id: str) -> CategoryDefinition:
        item = self.get(category_id)
        if item is None:
            raise ValueError("Category not found")
        if item.is_system:
            raise ValueError("System categories cannot be modified")
        return item

    def _slugify(self, text: str) -> str:
        normalized = re.sub(r"[^a-zA-Z0-9]+", "_", str(text or "").strip().lower())
        normalized = normalized.strip("_")
        return normalized

    def _system_index(self, category_id: str) -> int:
        ids = [item[0] for item in _SYSTEM_CATEGORIES]
        try:
            return ids.index(category_id)
        except ValueError:
            return len(ids) + 100


_default_registry: Optional[CategoryRegistry] = None


def get_category_registry(storage_root: Optional[str | Path] = None, force_reload: bool = False) -> CategoryRegistry:
    global _default_registry
    if storage_root is not None:
        return CategoryRegistry(storage_root=storage_root)
    if force_reload or _default_registry is None:
        _default_registry = CategoryRegistry()
    return _default_registry


def reset_category_registry() -> None:
    global _default_registry
    _default_registry = None
