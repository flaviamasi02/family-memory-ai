from pathlib import Path

from core.media_classifier import MediaClassifier
from core.metadata_extractor import extract_basic_metadata
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
    folder = Path(folder_path)
    photos = []

    for file in folder.rglob("*"):
        if not file.is_file():
            continue

        if file.name.lower().endswith(SIDECAR_SUFFIX):
            continue

        if any(excluded_folder in file.parts for excluded_folder in EXCLUDED_IMPORT_FOLDERS):
            continue

        photo = Photo.from_path(file)
        photo.metadata = extract_basic_metadata(file)
        photo.sync_intelligence_from_metadata()
        photos.append(photo)

    _media_classifier.classify_photos(photos)

    for photo in photos:
        _user_metadata_service.apply_for_photo(photo)

    return photos
