"""Persistent newline-delimited JSON worker for the isolated Face Runtime."""
from __future__ import annotations
import json, sys, time
from pathlib import Path

PROTOCOL_VERSION = "face-worker-v1"
MAX_ACCEPTED_FACES = 50

def _iou(a, b):
    ax, ay, aw, ah = (int(v) for v in a); bx, by, bw, bh = (int(v) for v in b)
    left, top, right, bottom = max(ax,bx), max(ay,by), min(ax+aw,bx+bw), min(ay+ah,by+bh)
    intersection = max(0,right-left)*max(0,bottom-top)
    union = aw*ah+bw*bh-intersection
    return intersection/union if union else 0.0

def _accepted_boxes(boxes, width, height):
    """Deterministic bounds validation and overlap suppression."""
    minimum = max(24, int(min(width, height)*.015))
    valid = [(int(x),int(y),int(w),int(h)) for x,y,w,h in boxes
             if int(w)>=minimum and int(h)>=minimum and int(x)>=0 and int(y)>=0
             and int(x)+int(w)<=width and int(y)+int(h)<=height]
    accepted = []
    for box in sorted(valid, key=lambda item: (-item[2]*item[3], item[1], item[0])):
        if all(_iou(box, prior)<.35 for prior in accepted): accepted.append(box)
    limited = len(accepted)>MAX_ACCEPTED_FACES
    returned = accepted[:MAX_ACCEPTED_FACES]
    return returned, len(boxes)-len(returned), limited

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
        decode_started = time.perf_counter()
        try:
            with Image.open(source) as opened:
                image = np.asarray(ImageOps.exif_transpose(opened).convert("RGB"))
        except UnidentifiedImageError:
            return fail(request_id, started, "image", "decode_failed", "This image could not be decoded.")
        except Exception:
            return fail(request_id, started, "image", "image_processing_failed", "This image could not be prepared for face detection.")
        decode_ms = (time.perf_counter()-decode_started)*1000
        try:
            detection_started = time.perf_counter()
            gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
            raw = model.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(24, 24))
            faces, rejected, limited = _accepted_boxes(raw, image.shape[1], image.shape[0])
            return response(request_id, started, ok=True,
                            faces=[{"x":x,"y":y,"width":w,"height":h,"confidence":.8} for x,y,w,h in faces],
                            raw_detection_count=int(len(raw)), accepted_detection_count=int(len(faces)),
                            rejected_detection_count=int(rejected), unusually_many_faces=bool(limited),
                            image_width=int(image.shape[1]), image_height=int(image.shape[0]),
                            decode_ms=float(round(decode_ms,3)),
                            detection_ms=float(round((time.perf_counter()-detection_started)*1000,3)))
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
