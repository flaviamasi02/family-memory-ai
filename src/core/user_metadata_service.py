from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


@dataclass
class UserMetadataLoadResult:
    loaded: bool
    identity_match: bool
    identity_mismatch_warning: bool
    sidecar_path: Optional[Path]


class UserMetadataService:
    SIDE_CAR_SUFFIX = ".familymemory.json"
    IDENTITY_MTIME_TOLERANCE_SECONDS = 1.0

    def __init__(self, app_version: Optional[str] = None):
        self._app_version = app_version or os.environ.get("FAMILY_MEMORY_AI_VERSION")

    def sidecar_path_for(self, file_path: str | Path) -> Path:
        path = Path(file_path)
        return path.with_name(f"{path.stem}{self.SIDE_CAR_SUFFIX}")

    def save_for_photo(self, photo, app_version: Optional[str] = None) -> Optional[Path]:
        photo_path = Path(getattr(photo, "path", ""))
        if not photo_path:
            return None

        payload = self._build_payload(photo, app_version=app_version)
        sidecar_path = self.sidecar_path_for(photo_path)
        sidecar_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")
        return sidecar_path

    def apply_for_photo(self, photo) -> UserMetadataLoadResult:
        photo_path = Path(getattr(photo, "path", ""))
        if not photo_path:
            return UserMetadataLoadResult(False, False, False, None)

        sidecar_path = self.sidecar_path_for(photo_path)
        if not sidecar_path.exists():
            return UserMetadataLoadResult(False, False, False, sidecar_path)

        try:
            data = json.loads(sidecar_path.read_text(encoding="utf-8"))
        except Exception:
            return UserMetadataLoadResult(False, False, False, sidecar_path)

        current_identity = self._current_identity(photo_path)
        identity_match = self._identity_matches(data, current_identity)
        stored_filename = str(data.get("file_name", "") or "").strip()
        filename_matches = stored_filename.lower() == str(photo_path.name).strip().lower()

        if not identity_match and not filename_matches:
            return UserMetadataLoadResult(True, False, True, sidecar_path)

        metadata = dict(getattr(photo, "metadata", {}) or {})
        automatic = str(data.get("automatic_media_category", "") or "").strip()
        user_corrected = str(data.get("user_corrected_media_category", "") or "").strip()
        effective_from_sidecar = str(data.get("effective_media_category", "") or "").strip()
        user_decision = str(data.get("user_decision", "") or "").strip()
        classification_reason = str(data.get("classification_reason", "") or "").strip()

        if automatic:
            metadata["automatic_media_category"] = automatic

        if user_corrected:
            metadata["user_corrected_media_category"] = user_corrected

        effective = user_corrected or effective_from_sidecar or automatic or str(
            metadata.get("effective_media_category", "") or metadata.get("media_category", "unknown")
        )
        metadata["effective_media_category"] = effective
        metadata["media_category"] = effective

        if user_decision:
            metadata["user_decision"] = user_decision

        if classification_reason:
            metadata["classification_reason"] = classification_reason

        if not identity_match:
            metadata["user_metadata_warning"] = "identity_mismatch"
        else:
            metadata.pop("user_metadata_warning", None)

        photo.metadata = metadata
        photo.automatic_media_category = str(metadata.get("automatic_media_category", "") or photo.automatic_media_category)
        photo.user_corrected_media_category = str(metadata.get("user_corrected_media_category", "") or "")
        photo.effective_media_category = str(metadata.get("effective_media_category", "") or photo.effective_media_category)
        photo.media_category = str(metadata.get("media_category", "") or photo.media_category)
        if user_decision:
            photo.user_decision = user_decision
        photo.sync_intelligence_from_metadata()

        return UserMetadataLoadResult(True, identity_match, not identity_match, sidecar_path)

    def _build_payload(self, photo, app_version: Optional[str] = None) -> dict[str, Any]:
        path = Path(getattr(photo, "path", ""))
        stat = path.stat() if path.exists() else None
        metadata = dict(getattr(photo, "metadata", {}) or {})

        automatic = str(
            getattr(photo, "automatic_media_category", "")
            or metadata.get("automatic_media_category", "")
            or getattr(photo, "media_category", "")
            or "unknown"
        ).strip()
        user_corrected = str(
            getattr(photo, "user_corrected_media_category", "")
            or metadata.get("user_corrected_media_category", "")
            or metadata.get("cleanup_user_corrected_category", "")
            or ""
        ).strip()
        effective = str(
            getattr(photo, "effective_media_category", "")
            or metadata.get("effective_media_category", "")
            or metadata.get("cleanup_effective_category", "")
            or user_corrected
            or automatic
            or "unknown"
        ).strip()
        user_decision = str(
            getattr(photo, "user_decision", "")
            or metadata.get("user_decision", "")
            or metadata.get("cleanup_user_decision", "")
            or "pending"
        ).strip()
        classification_reason = str(
            getattr(photo, "classification_reason", "")
            or metadata.get("classification_reason", "")
            or metadata.get("relevance_reason", "")
            or ""
        ).strip()

        payload = {
            "file_path": str(path),
            "file_name": path.name,
            "file_size": int(stat.st_size) if stat is not None else int(getattr(photo, "file_size", 0) or 0),
            "last_modified": float(stat.st_mtime) if stat is not None else 0.0,
            "automatic_media_category": automatic,
            "user_corrected_media_category": user_corrected,
            "effective_media_category": effective,
            "user_decision": user_decision,
            "classification_reason": classification_reason,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "app_version": app_version or self._app_version,
        }
        return payload

    def _current_identity(self, path: Path) -> dict[str, Any]:
        stat = path.stat()
        return {
            "file_name": path.name,
            "file_size": int(stat.st_size),
            "last_modified": float(stat.st_mtime),
        }

    def _identity_matches(self, stored: dict[str, Any], current: dict[str, Any]) -> bool:
        stored_name = str(stored.get("file_name", "") or "").strip().lower()
        current_name = str(current.get("file_name", "") or "").strip().lower()
        if not stored_name or stored_name != current_name:
            return False

        try:
            stored_size = int(stored.get("file_size", -1))
            current_size = int(current.get("file_size", -2))
        except Exception:
            return False
        if stored_size != current_size:
            return False

        try:
            stored_mtime = float(stored.get("last_modified", -1.0))
            current_mtime = float(current.get("last_modified", -2.0))
        except Exception:
            return False

        return abs(stored_mtime - current_mtime) <= self.IDENTITY_MTIME_TOLERANCE_SECONDS