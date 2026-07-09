import time
from pathlib import Path

from core.media_classifier import MediaClassifier
from core.metadata_extractor import extract_basic_metadata
from core.perf_stats import get_session_stats
from core.user_metadata_service import UserMetadataService
from models.photo import Photo

EXCLUDED_IMPORT_FOLDERS = {
    "_family_memory_deleted_review",
    "_family_memory_cleanup_review",
}
SIDECAR_SUFFIX = ".familymemory.json"


_media_classifier = MediaClassifier()
_user_metadata_service = UserMetadataService()


def find_photos(folder_path):
    stats = get_session_stats()
    folder = Path(folder_path)

    # Phase 1: file walk — enumerate qualifying paths (no image I/O).
    t0 = time.perf_counter()
    raw_files: list[Path] = []
    for file in folder.rglob("*"):
        if not file.is_file():
            continue
        if file.name.lower().endswith(SIDECAR_SUFFIX):
            continue
        if any(excluded_folder in file.parts for excluded_folder in EXCLUDED_IMPORT_FOLDERS):
            continue
        raw_files.append(file)
    stats.record("folder_scan [BG]", (time.perf_counter() - t0) * 1000)

    # Phase 2: metadata extraction — opens each image file via PIL for EXIF.
    photos: list[Photo] = []
    t1 = time.perf_counter()
    for file in raw_files:
        photo = Photo.from_path(file)
        photo.metadata = extract_basic_metadata(file)
        photo.sync_intelligence_from_metadata()
        photos.append(photo)
    stats.record("metadata_extraction [BG]", (time.perf_counter() - t1) * 1000)

    _media_classifier.classify_photos(photos)

    for photo in photos:
        _user_metadata_service.apply_for_photo(photo)

    stats.inc("files_scanned", len(photos))
    return photos
