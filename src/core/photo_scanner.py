import time
import logging
from pathlib import Path

from core.media_classifier import MediaClassifier
from core.metadata_extractor import extract_basic_metadata
from core.perf_stats import get_session_stats
from core.user_metadata_service import UserMetadataService
from core.supported_media import is_supported_media_path
from models.photo import Photo
from storage.import_registration import FileObservation
from storage.photo_repository import normalise_relative_path

EXCLUDED_IMPORT_FOLDERS = {
    "_family_memory_deleted_review",
    "_family_memory_cleanup_review",
}
SIDECAR_SUFFIX = ".familymemory.json"


_media_classifier = MediaClassifier()
_user_metadata_service = UserMetadataService()
logger = logging.getLogger(__name__)


def find_photos(folder_path, synchronization_service=None):
    stats = get_session_stats()
    folder = Path(folder_path)

    # Phase 1: file walk — enumerate qualifying paths (no image I/O).
    t0 = time.perf_counter()
    raw_files: list[tuple[Path, object]] = []
    entries_discovered = 0
    files_discovered = 0
    unsupported_files = 0
    for file in folder.rglob("*"):
        entries_discovered += 1
        if not file.is_file():
            continue
        files_discovered += 1
        if any(excluded_folder in file.parts for excluded_folder in EXCLUDED_IMPORT_FOLDERS):
            unsupported_files += 1
            continue
        # Reject unsupported files before Photo construction, metadata/EXIF
        # extraction, classification, sidecar lookup, or thumbnail scheduling.
        if not is_supported_media_path(file):
            unsupported_files += 1
            continue
        try:
            raw_files.append((file, file.stat()))
        except OSError:
            unsupported_files += 1
    stats.record("folder_scan [BG]", (time.perf_counter() - t0) * 1000)
    stats.inc("filesystem_entries_discovered", entries_discovered)
    stats.inc("files_discovered", files_discovered)
    stats.inc("supported_media_candidates", len(raw_files))
    stats.inc("unsupported_files_skipped", unsupported_files)
    logger.info(
        "Import scan filtered entries=%s files=%s supported_media=%s unsupported_skipped=%s",
        entries_discovered, files_discovered, len(raw_files), unsupported_files,
    )

    sync_plan = None
    if synchronization_service is not None:
        observations = []
        root = folder.resolve(strict=False)
        for file, stat in raw_files:
            relative = str(file.resolve(strict=False).relative_to(root))
            observations.append(FileObservation(
                file.resolve(strict=False), relative, normalise_relative_path(relative),
                file.name, int(stat.st_size), int(stat.st_mtime_ns)))
        sync_plan = synchronization_service.plan_changes(observations)
        sync_items_by_path = {
            item.observation.path: item for item in sync_plan.items
        }
    else:
        sync_items_by_path = {}

    # Phase 2: expensive extraction/classification runs only for new or updated
    # files. Unchanged and relocated files reuse sidecar/domain metadata.
    photos: list[Photo] = []
    expensive_photos: list[Photo] = []
    t1 = time.perf_counter()
    for file, stat in raw_files:
        photo = Photo.from_path(file, stat_result=stat)
        sync_item = sync_items_by_path.get(file.resolve(strict=False))
        photo.sync_state = sync_item.state if sync_item else "added"
        photo.id = sync_item.photo_id if sync_item else None
        if sync_item and sync_item.previous_location and sync_item.state in {"moved", "renamed"}:
            photo.previous_path = Path(sync_item.previous_location.source_path)
        if photo.sync_state in {"added", "updated"}:
            photo.metadata = extract_basic_metadata(file)
            photo.sync_intelligence_from_metadata()
            expensive_photos.append(photo)
        photos.append(photo)
    stats.record("metadata_extraction [BG]", (time.perf_counter() - t1) * 1000)

    _media_classifier.classify_photos(expensive_photos)

    for photo in photos:
        if photo.previous_path:
            loaded = _user_metadata_service.apply_for_photo(
                photo, sidecar_source_path=photo.previous_path, trusted_relocation=True)
            if loaded.loaded:
                continue
        _user_metadata_service.apply_for_photo(photo)

    stats.inc("files_scanned", len(photos))
    stats.inc("photos_expensively_processed", len(expensive_photos))
    return photos
