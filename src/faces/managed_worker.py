"""Persistent newline-delimited JSON worker for the isolated Face Runtime."""
from __future__ import annotations
import json, sys, time
from pathlib import Path

PROTOCOL_VERSION = "face-worker-v1"

def emit(value):
    sys.stdout.write(json.dumps(value, ensure_ascii=True, separators=(",", ":")) + "\n")
    sys.stdout.flush()

def response(request_id, started, **value):
    value.update(request_id=request_id, processing_ms=round((time.perf_counter()-started)*1000, 3))
    emit(value)

def fail(request_id, started, scope, code, message):
    response(request_id, started, ok=False, error_scope=scope, error_code=code, message=message)

def load_runtime():
    try:
        import cv2
        import numpy as np
        from PIL import Image, ImageOps, UnidentifiedImageError
    except Exception:
        return None, "runtime_import_failed", "The managed Face Runtime could not load its required packages."
    root = getattr(getattr(cv2, "data", None), "haarcascades", "")
    path = Path(root) / "haarcascade_frontalface_default.xml"
    if not path.is_file() or not hasattr(cv2, "CascadeClassifier"):
        return None, "cascade_unavailable", "The managed face detector model is unavailable."
    model = cv2.CascadeClassifier(str(path))
    if model.empty():
        return None, "cascade_invalid", "The managed face detector model is invalid."
    return (cv2, np, Image, ImageOps, UnidentifiedImageError, model), "", ""

def process(request, runtime):
    started = time.perf_counter(); request_id = request.get("request_id")
    if request.get("operation_version") != PROTOCOL_VERSION:
        return fail(request_id, started, "runtime", "version_mismatch", "The managed worker protocol version is incompatible.")
    if runtime is None:
        return fail(request_id, started, "runtime", STARTUP_ERROR[0], STARTUP_ERROR[1])
    cv2, np, Image, ImageOps, UnidentifiedImageError, model = runtime
    operation = request.get("operation")
    source = Path(request.get("source_path", ""))
    if not source.is_file():
        return fail(request_id, started, "image", "source_missing", "The source image is missing.")
    if operation == "detect":
        try:
            with Image.open(source) as opened:
                image = np.asarray(ImageOps.exif_transpose(opened).convert("RGB"))
        except UnidentifiedImageError:
            return fail(request_id, started, "image", "decode_failed", "This image could not be decoded.")
        except Exception:
            return fail(request_id, started, "image", "image_processing_failed", "This image could not be prepared for face detection.")
        try:
            gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
            faces = model.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(24, 24))
            return response(request_id, started, ok=True, faces=[{"x":int(x),"y":int(y),"width":int(w),"height":int(h),"confidence":.8} for x,y,w,h in faces])
        except Exception:
            return fail(request_id, started, "image", "detection_failed", "Face detection failed for this image.")
    if operation == "embed":
        try:
            image = cv2.imread(str(source), cv2.IMREAD_GRAYSCALE)
            if image is None: return fail(request_id, started, "image", "decode_failed", "This face crop could not be decoded.")
            descriptor = cv2.dct(cv2.resize(image,(32,32)).astype(np.float32)/255.0).flatten()[:128]
            norm = float(np.linalg.norm(descriptor))
            if not np.isfinite(norm) or norm <= 0: return fail(request_id, started, "image", "invalid_descriptor", "A valid face descriptor could not be generated.")
            return response(request_id, started, ok=True, vector=(descriptor/norm).tolist())
        except Exception:
            return fail(request_id, started, "image", "embedding_failed", "A face descriptor could not be generated.")
    return fail(request_id, started, "runtime", "unknown_operation", "The managed worker operation was invalid.")

def main():
    global STARTUP_ERROR
    runtime, code, message = load_runtime(); STARTUP_ERROR = (code, message)
    emit({"ready": runtime is not None, "protocol_version": PROTOCOL_VERSION,
          "error_code": code or None, "message": message or "ready", "model_load_count": 1 if runtime else 0})
    for line in sys.stdin:
        try: request = json.loads(line)
        except Exception:
            emit({"ok":False,"request_id":None,"error_scope":"runtime","error_code":"malformed_request","message":"The request was not valid JSON.","processing_ms":0})
            continue
        process(request, runtime)
    return 0

if __name__ == "__main__": raise SystemExit(main())
