from __future__ import annotations

import json, os, shutil, tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

APP_DIR_NAME = "FamilyMemoryAI"
SCHEMA_VERSION = 1


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def default_app_data_root() -> Path:
    override = os.environ.get("FAMILY_MEMORY_APP_DATA_ROOT")
    if override:
        return Path(override).expanduser()
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / APP_DIR_NAME
    if sys_xdg := os.environ.get("XDG_DATA_HOME"):
        return Path(sys_xdg) / "family-memory-ai"
    return Path.home() / ".local" / "share" / "family-memory-ai"


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    os.close(fd)
    tmp_path = Path(tmp)
    try:
        tmp_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")
        os.replace(tmp_path, path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)


def _payload_time(path: Path) -> str:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            for key in ("updated_at", "last_updated_at", "generated_at"):
                if data.get(key): return str(data[key])
    except Exception:
        pass
    try: return datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat()
    except Exception: return ""


def _is_newer(src: Path, dst: Path) -> bool:
    if not dst.exists(): return True
    st, dt = _payload_time(src), _payload_time(dst)
    if st and dt and st != dt: return st > dt
    try: return src.stat().st_mtime > dst.stat().st_mtime
    except Exception: return False


@dataclass
class MigrationRecord:
    source: str
    destination: str
    action: str
    reason: str
    timestamp: str


class ApplicationDataPathService:
    """Stable per-user application data paths, independent of cwd or git branch."""
    def __init__(self, app_data_root: str | Path | None = None, legacy_root: str | Path | None = None):
        self.root = Path(app_data_root).expanduser() if app_data_root else default_app_data_root()
        self.legacy_root = Path(legacy_root).expanduser() if legacy_root else Path.cwd()
        self._diagnostics: list[MigrationRecord] = []

    @property
    def diagnostics(self) -> list[dict[str, str]]:
        return [r.__dict__ for r in self._diagnostics]

    def profile_path(self, name: str) -> Path:
        return self.root / "profiles" / name
    def config_path(self, name: str) -> Path:
        return self.root / "config" / name
    def cache_dir(self, name: str) -> Path:
        return self.root / "cache" / name
    def reports_dir(self) -> Path:
        return self.root / "reports"

    def legacy_familymemory_dir(self) -> Path:
        return self.legacy_root / ".familymemory"

    def migrate_legacy_files(self) -> list[dict[str, str]]:
        mapping = {
            "category_learning_profile.json": self.profile_path("category_learning_profile.json"),
            "preference_learning_profile.json": self.profile_path("preference_learning_profile.json"),
            "categories.json": self.config_path("categories.json"),
        }
        legacy = self.legacy_familymemory_dir()
        for name, dst in mapping.items():
            src = legacy / name
            if not src.exists(): continue
            if _is_newer(src, dst):
                dst.parent.mkdir(parents=True, exist_ok=True)
                if dst.exists():
                    backup = dst.with_suffix(dst.suffix + f".backup-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}")
                    shutil.copy2(dst, backup)
                shutil.copy2(src, dst)
                action, reason = "migrated", "legacy file was newer or destination was missing"
            else:
                action, reason = "skipped", "stable application-data file is newer; legacy file was not copied"
            self._diagnostics.append(MigrationRecord(str(src), str(dst), action, reason, _now_iso()))
        if self._diagnostics:
            atomic_write_json(self.root / "migration_diagnostics.json", {"schema_version": SCHEMA_VERSION, "updated_at": _now_iso(), "records": self.diagnostics})
        return self.diagnostics


def get_app_data_service(
    storage_root: str | Path | None = None,
    legacy_root: str | Path | None = None,
    *,
    migrate_legacy: bool = True,
) -> ApplicationDataPathService:
    service = ApplicationDataPathService(storage_root, legacy_root)
    if migrate_legacy:
        service.migrate_legacy_files()
    return service
