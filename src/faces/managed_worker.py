"""Stable JSON protocol entry point executed by the isolated Face Runtime."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def emit(value):
    print(json.dumps(value, ensure_ascii=True, separators=(",", ":")), flush=True)


def failure(scope, code, message):
    emit({"ok": False, "error_scope": scope, "error_code": code, "message": message})
    return 0


def load_runtime():
    try:
        import cv2
        import numpy as np
        from PIL import Image, ImageOps, UnidentifiedImageError
        return cv2, np, Image, ImageOps, UnidentifiedImageError
    except Exception:
        failure("runtime", "runtime_import_failed", "The managed Face Runtime could not load its required packages.")
        return None


def detect(request):
    runtime = load_runtime()
    if runtime is None:
        return 0
    cv2, np, Image, ImageOps, UnidentifiedImageError = runtime
    source = Path(request.get("image_path", ""))
    if not source.is_file():
        return failure("image", "source_missing", "The source image is missing.")
    try:
        with Image.open(source) as opened:
            image = np.asarray(ImageOps.exif_transpose(opened).convert("RGB"))
    except UnidentifiedImageError:
        return failure("image", "decode_failed", "This image could not be decoded.")
    except Exception:
        return failure("image", "image_processing_failed", "This image could not be prepared for face detection.")
    try:
        cascade_root = getattr(getattr(cv2, "data", None), "haarcascades", "")
        cascade_path = Path(cascade_root) / "haarcascade_frontalface_default.xml"
        if not cascade_path.is_file() or not hasattr(cv2, "CascadeClassifier"):
            return failure("runtime", "cascade_unavailable", "The managed face detector model is unavailable.")
        model = cv2.CascadeClassifier(str(cascade_path))
        if model.empty():
            return failure("runtime", "cascade_invalid", "The managed face detector model is invalid.")
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        faces = model.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(24, 24))
        emit({"ok": True, "faces": [{"x": int(x), "y": int(y), "width": int(w), "height": int(h), "confidence": .8} for x, y, w, h in faces]})
        return 0
    except Exception:
        return failure("image", "detection_failed", "Face detection failed for this image.")


def embed(request):
    runtime = load_runtime()
    if runtime is None:
        return 0
    cv2, np, *_ = runtime
    source = Path(request.get("crop_path", ""))
    if not source.is_file():
        return failure("image", "crop_missing", "The face crop is missing.")
    try:
        image = cv2.imread(str(source), cv2.IMREAD_GRAYSCALE)
        if image is None:
            return failure("image", "decode_failed", "This face crop could not be decoded.")
        descriptor = cv2.dct(cv2.resize(image, (32, 32)).astype(np.float32) / 255.0).flatten()[:128]
        norm = float(np.linalg.norm(descriptor))
        if not np.isfinite(norm) or norm <= 0:
            return failure("image", "invalid_descriptor", "A valid face descriptor could not be generated.")
        emit({"ok": True, "vector": (descriptor / norm).tolist()})
        return 0
    except Exception:
        return failure("image", "embedding_failed", "A face descriptor could not be generated.")


def main(argv=None):
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("command", choices=("detect", "embed"))
    parser.add_argument("--request-file", required=True)
    args = parser.parse_args(argv)
    try:
        request = json.loads(Path(args.request_file).read_text(encoding="utf-8"))
    except Exception:
        return failure("runtime", "invalid_request", "The managed worker request was invalid.")
    return detect(request) if args.command == "detect" else embed(request)


if __name__ == "__main__":
    raise SystemExit(main())
