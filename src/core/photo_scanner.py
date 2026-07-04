from pathlib import Path

from models.photo import Photo

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def find_photos(folder_path):
    folder = Path(folder_path)

    return [
        Photo.from_path(file)
        for file in folder.rglob("*")
        if file.suffix.lower() in SUPPORTED_EXTENSIONS
    ]
