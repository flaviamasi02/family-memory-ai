from __future__ import annotations

from pathlib import Path
from time import perf_counter
from typing import Any

from PySide6.QtCore import QSize
from PySide6.QtGui import QImage, QImageReader

from core.face_detection_service import FaceDetectionService, FaceDetectionResult
from models.visual_feature_profile import VisualFeatureProfile


class VisualFeatureExtractionService:
    """Local deterministic visual feature extraction boundary.

    This service intentionally reads only image pixels and optional previously
    computed face-detection metadata. It never uses filename, extension, EXIF,
    file size, dates, or camera metadata as visual evidence.
    """

    def __init__(self, max_dimension: int = 512, timeout_ms: int = 300, face_service: FaceDetectionService | None = None):
        self._max_dimension = max(128, int(max_dimension))
        self._timeout_ms = max(10, int(timeout_ms))
        self._face_service = face_service

    def extract(
        self,
        file_path: str | Path,
        existing_metadata: dict[str, Any] | None = None,
        *,
        use_existing_faces: bool = True,
        run_face_detection: bool = False,
    ) -> VisualFeatureProfile:
        path = Path(file_path)
        if not path.exists() or not path.is_file():
            return VisualFeatureProfile.empty("unavailable", "Image file is missing; visual features were not extracted.")

        image, source_size = self._load_image(path)
        if image is None or image.isNull():
            return VisualFeatureProfile.empty("unavailable", "Image could not be opened; visual features were not extracted.")

        started = perf_counter()
        try:
            metrics = self._sample_metrics(image, started)
        except TimeoutError:
            return VisualFeatureProfile.empty("timeout", "Visual feature extraction reached the per-image time limit.")
        except Exception:
            return VisualFeatureProfile.empty("failed", "Visual feature extraction failed safely.")

        width, height = source_size
        orientation = self._orientation(width, height)
        ratio = (width / height) if height > 0 else 0.0
        tall_mobile = bool(ratio <= 0.62 and height >= 800)
        page_like = bool(0.65 <= ratio <= 0.85 or 1.2 <= ratio <= 1.6)
        low_res = bool(width < 900 or height < 700 or (width * height) < (900 * 700))
        square = bool(abs(width - height) <= 0.08 * max(width, height))

        text_conf = self._clip(0.48 * metrics["edge_density"] + 0.38 * metrics["high_contrast_ratio"] + 0.22 * metrics["white_ratio"] - 0.12 * metrics["saturation_score"])
        document_conf = self._clip(0.42 * metrics["white_ratio"] + 0.34 * text_conf + 0.18 * (1.0 if page_like else 0.0) + 0.08 * metrics["line_density"])
        screenshot_conf = self._clip(0.46 * (1.0 if tall_mobile else 0.0) + 0.24 * metrics["flat_ratio"] + 0.20 * metrics["line_density"] + 0.12 * text_conf)
        graphic_conf = self._clip(0.32 * (1.0 if low_res else 0.0) + 0.18 * (1.0 if square else 0.0) + 0.32 * metrics["flat_ratio"] + 0.26 * (1.0 - metrics["palette_diversity"]) + 0.10 * text_conf)

        metadata = dict(existing_metadata or {})
        face_result = self._face_from_metadata(metadata) if use_existing_faces else None
        if face_result is None and run_face_detection:
            service = self._face_service or FaceDetectionService(enabled=True)
            face_result = service.detect(path)

        tags: list[str] = []
        evidence: list[str] = [f"Visual layout is {orientation} ({width}x{height})."]
        if text_conf >= 0.58:
            tags.append("text-like-regions")
            evidence.append("Pixel analysis found prominent high-contrast text-like regions.")
        if document_conf >= 0.62:
            tags.append("document-like")
            evidence.append("Pixel analysis found page-like layout and bright document-like regions.")
        if screenshot_conf >= 0.62:
            tags.append("screenshot-like")
            evidence.append("Pixel analysis found flat regions and line structure consistent with screenshots.")
        if graphic_conf >= 0.62:
            tags.append("graphic-like")
            evidence.append("Pixel analysis found flat/limited-palette regions consistent with graphics or memes.")
        has_faces = bool(face_result.has_faces) if face_result is not None else False
        face_count = int(face_result.face_count) if face_result is not None else 0
        face_conf = float(face_result.confidence) if face_result is not None else 0.0
        if has_faces:
            tags.append("faces")
            evidence.append(f"Existing local face evidence reports {face_count} face(s).")

        return VisualFeatureProfile(
            has_faces=has_faces,
            face_count=face_count,
            face_confidence=round(self._clip(face_conf), 3),
            has_text_like_regions=text_conf >= 0.58,
            looks_like_document=document_conf >= 0.62,
            looks_like_screenshot=screenshot_conf >= 0.62,
            looks_like_graphic_or_meme=graphic_conf >= 0.62,
            dominant_orientation=orientation,
            visual_tags=tags,
            evidence_summary=evidence,
            confidence_by_feature={"text_like_regions": round(text_conf,3), "document": round(document_conf,3), "screenshot": round(screenshot_conf,3), "graphic_or_meme": round(graphic_conf,3), "faces": round(self._clip(face_conf),3)},
            extraction_status="extracted",
        )

    def apply_profile_to_photo(self, photo, profile: VisualFeatureProfile) -> None:
        metadata = dict(getattr(photo, "metadata", {}) or {})
        metadata["visual_feature_profile"] = profile.to_dict()
        photo.metadata = metadata
        if hasattr(photo, "visual_features"):
            photo.visual_features = profile

    def _face_from_metadata(self, metadata: dict[str, Any]) -> FaceDetectionResult | None:
        if "has_faces" not in metadata and "face_count" not in metadata and "faces_count" not in metadata:
            return None
        count = int(metadata.get("face_count", metadata.get("faces_count", 0)) or 0)
        return FaceDetectionResult(count, bool(metadata.get("has_faces", count > 0)), float(metadata.get("face_detection_confidence", 0.0) or 0.0), str(metadata.get("face_detection_detector", "existing") or "existing"), [])

    def _load_image(self, path: Path) -> tuple[QImage | None, tuple[int, int]]:
        reader = QImageReader(str(path)); reader.setAutoTransform(True)
        size = reader.size(); source = (size.width(), size.height()) if size.isValid() else (0, 0)
        if size.isValid() and max(size.width(), size.height()) > self._max_dimension:
            if size.width() >= size.height():
                reader.setScaledSize(QSize(self._max_dimension, max(1, int(size.height() * self._max_dimension / size.width()))))
            else:
                reader.setScaledSize(QSize(max(1, int(size.width() * self._max_dimension / size.height())), self._max_dimension))
        try:
            image = reader.read()
        except Exception:
            return None, source
        if source == (0, 0) and image is not None and not image.isNull():
            source = (image.width(), image.height())
        return image, source

    def _orientation(self, width: int, height: int) -> str:
        if width <= 0 or height <= 0: return "unknown"
        if abs(width - height) <= int(0.08 * max(width, height)): return "square"
        return "portrait" if height > width else "landscape"

    def _sample_metrics(self, image: QImage, started: float) -> dict[str, float]:
        w, h = image.width(), image.height(); step_x=max(1,w//80); step_y=max(1,h//80)
        white=contrast=flat=edge=line=samples=0; colors=set(); sats=[]; vals=[]
        for y in range(0,h,step_y):
            if (perf_counter()-started)*1000.0 > self._timeout_ms: raise TimeoutError()
            for x in range(0,w,step_x):
                c=image.pixelColor(x,y); r,g,b=float(c.red()),float(c.green()),float(c.blue())
                bright=0.2126*r+0.7152*g+0.0722*b; sat=(max(r,g,b)-min(r,g,b))/255.0
                vals.append(bright); sats.append(sat); colors.add((int(r)//32,int(g)//32,int(b)//32))
                if bright>=235 and sat<=0.18: white+=1
                if bright<=50 or bright>=205: contrast+=1
                rc=image.pixelColor(min(w-1,x+step_x),y); dc=image.pixelColor(x,min(h-1,y+step_y))
                rb=0.2126*rc.red()+0.7152*rc.green()+0.0722*rc.blue(); db=0.2126*dc.red()+0.7152*dc.green()+0.0722*dc.blue()
                grad=max(abs(bright-rb),abs(bright-db))
                if grad<=12: flat+=1
                if grad>=30: edge+=1
                if abs(bright-rb)>=40 or abs(bright-db)>=40: line+=1
                samples+=1
        samples=max(1,samples)
        return {"white_ratio":self._clip(white/samples),"high_contrast_ratio":self._clip(contrast/samples),"palette_diversity":self._clip(len(colors)/128.0),"saturation_score":self._clip((sum(sats)/samples)/0.5),"flat_ratio":self._clip(flat/samples),"edge_density":self._clip(edge/samples),"line_density":self._clip(line/samples)}

    def _clip(self, value: float) -> float:
        return max(0.0, min(1.0, float(value)))
