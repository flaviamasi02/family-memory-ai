import time
import logging
import os
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
    raw_files: list[tuple[Path, object, FileObservation]] = []
    entries_discovered = 0
    files_discovered = 0
    unsupported_files = 0
    root = folder.resolve(strict=False)
    pending = [(root, Path())]
    while pending:
        directory, relative_directory = pending.pop()
        try:
            with os.scandir(directory) as entries:
                for entry in entries:
                    entries_discovered += 1
                    relative = relative_directory / entry.name
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            if entry.name not in EXCLUDED_IMPORT_FOLDERS:
                                pending.append((Path(entry.path), relative))
                            else:
                                unsupported_files += 1
                            continue
                        # Match pathlib's prior behavior: do not recurse through
                        # directory symlinks, but accept a symlink to a file.
                        if not entry.is_file():
                            continue
                        files_discovered += 1
                        file = Path(entry.path)
                        if not is_supported_media_path(file):
                            unsupported_files += 1
                            continue
                        stat = entry.stat()
                    except OSError:
                        unsupported_files += 1
                        continue
                    relative_text = str(relative)
                    resolved = root / relative
                    raw_files.append((file, stat, FileObservation(
                        resolved, relative_text, normalise_relative_path(relative_text),
                        entry.name, int(stat.st_size), int(stat.st_mtime_ns))))
        except OSError:
            unsupported_files += 1
    scan_ms = (time.perf_counter() - t0) * 1000
    stats.record("Filesystem scan", scan_ms, entries_discovered, "Background thread")
    stats.record("Supported-media filtering", scan_ms, files_discovered, "Background thread")
    stats.record("folder_scan", scan_ms, entries_discovered, "Background thread")
    stats.inc("filesystem_entries_discovered", entries_discovered)
    stats.inc("files_discovered", files_discovered)
    stats.inc("supported_media_candidates", len(raw_files))
    stats.inc("unsupported_files_skipped", unsupported_files)
    stats.inc("filesystem_stat_calls_avoided", len(raw_files))
    stats.inc("path_resolutions_avoided", len(raw_files) * 2)
    logger.info(
        "Import scan filtered entries=%s files=%s supported_media=%s unsupported_skipped=%s",
        entries_discovered, files_discovered, len(raw_files), unsupported_files,
    )

    sync_plan = None
    if synchronization_service is not None:
        observations = [observation for _file, _stat, observation in raw_files]
        plan_t0 = time.perf_counter()
        sync_plan = synchronization_service.plan_changes(observations)
        stats.record("Incremental synchronization planning",
                     (time.perf_counter() - plan_t0) * 1000, len(observations), "Background thread")
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
    for file, stat, observation in raw_files:
        photo = Photo.from_path(file, stat_result=stat)
        sync_item = sync_items_by_path.get(observation.path)
        photo.sync_state = sync_item.state if sync_item else "added"
        photo.id = sync_item.photo_id if sync_item else None
        if sync_item and sync_item.previous_location and sync_item.state in {"moved", "renamed"}:
            photo.previous_path = Path(sync_item.previous_location.source_path)
        needs_classification_snapshot = bool(sync_item and sync_item.classification is None)
        if photo.sync_state in {"added", "updated"} or needs_classification_snapshot:
            photo.metadata = extract_basic_metadata(file)
            photo.sync_intelligence_from_metadata()
            expensive_photos.append(photo)
        elif sync_item and sync_item.captured_at:
            # Rehydrate the durable capture date without reopening the image.
            # Memory Review groups by this domain date after restart as well as
            # during a same-session incremental import.
            photo.metadata = {"date_taken": sync_item.captured_at}
            photo.sync_intelligence_from_metadata()
        if sync_item and sync_item.classification:
            (photo.automatic_media_category, photo.effective_media_category,
             photo.relevance_category, relevant, photo.classification_confidence,
             photo.classification_reason) = sync_item.classification
            photo.is_album_relevant_candidate = bool(relevant)
            photo.media_category = photo.effective_media_category or photo.media_category
            photo.metadata.update({
                "automatic_media_category": photo.automatic_media_category,
                "effective_media_category": photo.effective_media_category,
                "media_category": photo.media_category,
                "relevance_category": photo.relevance_category,
                "is_album_relevant_candidate": photo.is_album_relevant_candidate,
                "classification_confidence": photo.classification_confidence,
                "classification_reason": photo.classification_reason,
            })
            photo.sync_intelligence_from_metadata()
        photos.append(photo)
    creation_ms = (time.perf_counter() - t1) * 1000
    stats.record("Photo object creation", creation_ms, len(photos), "Background thread")
    stats.record("Metadata loading", creation_ms, len(expensive_photos), "Background thread")
    stats.record("metadata_extraction", creation_ms, len(expensive_photos), "Background thread")

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
    stats.inc("processed_photos", len(photos))
    return photos
