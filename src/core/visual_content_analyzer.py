from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from time import perf_counter
from typing import Optional

from PySide6.QtCore import QSize
from PySide6.QtGui import QImage, QImageReader


MEME_FILENAME_INDICATORS = {
    "meme",
    "sticker",
    "gif",
    "funny",
    "lol",
    "joke",
    "quote",
    "imgflip",
    "tenor",
    "giphy",
    "reaction",
    "buongiorno",
    "auguri",
}

DOCUMENT_FILENAME_INDICATORS = {
    "document",
    "scan",
    "scanned",
    "receipt",
    "invoice",
    "fattura",
    "scontrino",
    "ricevuta",
    "contract",
    "pdf",
}

SCREENSHOT_FILENAME_INDICATORS = {
    "screenshot",
    "screen_shot",
    "screen-shot",
    "schermata",
    "capture",
    "screenrec",
}

ADVERTISEMENT_FILENAME_INDICATORS = {
    "promo",
    "promotion",
    "advert",
    "advertisement",
    "pubblicita",
    "banner",
    "offerta",
    "sale",
    "discount",
}


@dataclass
class VisualContentSignals:
    file_path: str
    width: int | None
    height: int | None
    aspect_ratio: float | None
    dominant_layout: str | None
    has_faces: bool | None
    face_count: int
    text_likelihood: float
    graphic_likelihood: float
    photo_likelihood: float
    screenshot_likelihood: float
    document_likelihood: float
    advertisement_likelihood: float
    explanation: list[str] = field(default_factory=list)


class VisualContentAnalyzer:
    def __init__(self, max_dimension: int = 512, timeout_ms: int = 300):
        self._max_dimension = max(128, int(max_dimension))
        self._timeout_ms = max(10, int(timeout_ms))
        self._cache: dict[str, VisualContentSignals] = {}

    def analyze(self, file_path: str) -> VisualContentSignals:
        path = Path(file_path)
        signature = self._cache_key(path)
        cached = self._cache.get(signature)
        if cached is not None:
            return cached

        filename_lower = path.name.lower()
        if not path.exists() or not path.is_file():
            signals = VisualContentSignals(
                file_path=str(path),
                width=None,
                height=None,
                aspect_ratio=None,
                dominant_layout=None,
                has_faces=None,
                face_count=0,
                text_likelihood=0.0,
                graphic_likelihood=0.0,
                photo_likelihood=0.0,
                screenshot_likelihood=0.0,
                document_likelihood=0.0,
                advertisement_likelihood=0.0,
                explanation=["Visual analysis skipped because file is missing."],
            )
            self._cache[signature] = signals
            return signals

        image, source_w, source_h = self._load_for_analysis(path)
        if image is None or image.isNull():
            signals = VisualContentSignals(
                file_path=str(path),
                width=None,
                height=None,
                aspect_ratio=None,
                dominant_layout=None,
                has_faces=None,
                face_count=0,
                text_likelihood=0.0,
                graphic_likelihood=0.0,
                photo_likelihood=0.0,
                screenshot_likelihood=0.0,
                document_likelihood=0.0,
                advertisement_likelihood=0.0,
                explanation=["Visual analysis unavailable because image cannot be decoded."],
            )
            self._cache[signature] = signals
            return signals

        width = int(source_w if isinstance(source_w, int) and source_w > 0 else image.width())
        height = int(source_h if isinstance(source_h, int) and source_h > 0 else image.height())
        ratio = (float(width) / float(height)) if height > 0 else None
        layout = self._dominant_layout(width, height, ratio)

        started_at = perf_counter()
        try:
            sample = self._sample_metrics(image, started_at)
        except TimeoutError:
            signals = VisualContentSignals(
                file_path=str(path),
                width=None,
                height=None,
                aspect_ratio=None,
                dominant_layout=None,
                has_faces=None,
                face_count=0,
                text_likelihood=0.0,
                graphic_likelihood=0.0,
                photo_likelihood=0.0,
                screenshot_likelihood=0.0,
                document_likelihood=0.0,
                advertisement_likelihood=0.0,
                explanation=["Visual analysis unavailable because per-image timeout was reached."],
            )
            self._cache[signature] = signals
            return signals
        low_res = bool(width < 900 or height < 700 or (width * height) < (900 * 700))
        square = bool(abs(width - height) <= 0.08 * max(width, height))
        tall_mobile = bool(ratio is not None and ratio <= 0.62 and height >= 800)
        wide_banner = bool(ratio is not None and ratio >= 2.6 and width >= 800)
        page_like = bool(ratio is not None and (0.65 <= ratio <= 0.85 or 1.2 <= ratio <= 1.6))
        no_faces_note = "Face detection unavailable in local lightweight analyzer."

        text_likelihood = self._clip(
            0.45 * sample["edge_density"]
            + 0.40 * sample["high_contrast_ratio"]
            + 0.20 * sample["white_ratio"]
            - 0.10 * sample["saturation_score"]
        )

        graphic_likelihood = self._clip(
            0.30 * (1.0 if low_res else 0.0)
            + 0.18 * (1.0 if square else 0.0)
            + 0.30 * sample["flat_ratio"]
            + 0.25 * (1.0 - sample["palette_diversity"])
            + 0.12 * text_likelihood
        )

        photo_likelihood = self._clip(
            0.20
            + 0.30 * sample["palette_diversity"]
            + 0.22 * sample["variance_score"]
            + 0.20 * sample["saturation_score"]
            + 0.10 * (1.0 if not tall_mobile and not wide_banner else 0.0)
            - 0.18 * sample["flat_ratio"]
            - 0.10 * (1.0 if square and low_res else 0.0)
        )

        screenshot_likelihood = self._clip(
            0.44 * (1.0 if tall_mobile else 0.0)
            + 0.22 * sample["flat_ratio"]
            + 0.20 * sample["line_density"]
            + 0.12 * text_likelihood
            + 0.10 * (1.0 if any(k in filename_lower for k in SCREENSHOT_FILENAME_INDICATORS) else 0.0)
        )

        document_likelihood = self._clip(
            0.36 * sample["white_ratio"]
            + 0.28 * text_likelihood
            + 0.18 * (1.0 if page_like else 0.0)
            + 0.12 * (1.0 if any(k in filename_lower for k in DOCUMENT_FILENAME_INDICATORS) else 0.0)
            + 0.08 * sample["line_density"]
        )

        advertisement_likelihood = self._clip(
            0.52 * (1.0 if wide_banner else 0.0)
            + 0.30 * graphic_likelihood
            + 0.20 * (1.0 if any(k in filename_lower for k in ADVERTISEMENT_FILENAME_INDICATORS) else 0.0)
            + 0.12 * text_likelihood
        )

        if any(k in filename_lower for k in MEME_FILENAME_INDICATORS):
            graphic_likelihood = self._clip(graphic_likelihood + 0.12)

        explanation: list[str] = []
        explanation.append(f"Layout appears {layout or 'unknown'} ({width}x{height}).")
        if sample["white_ratio"] >= 0.55:
            explanation.append("Large white background areas detected.")
        if sample["flat_ratio"] >= 0.55:
            explanation.append("Large flat color regions detected.")
        if sample["palette_diversity"] >= 0.55:
            explanation.append("Color palette diversity looks photo-like.")
        if text_likelihood >= 0.60:
            explanation.append("Text-like/high-contrast regions are prominent.")
        if tall_mobile:
            explanation.append("Aspect ratio resembles a tall mobile screenshot.")
        if wide_banner:
            explanation.append("Aspect ratio resembles a wide banner/ad layout.")
        if any(k in filename_lower for k in DOCUMENT_FILENAME_INDICATORS):
            explanation.append("Filename has document-related indicators.")
        if any(k in filename_lower for k in SCREENSHOT_FILENAME_INDICATORS):
            explanation.append("Filename has screenshot indicators.")
        if any(k in filename_lower for k in ADVERTISEMENT_FILENAME_INDICATORS):
            explanation.append("Filename has promotional/advertisement indicators.")
        if any(k in filename_lower for k in MEME_FILENAME_INDICATORS):
            explanation.append("Filename has meme/graphic indicators.")
        explanation.append(no_faces_note)

        signals = VisualContentSignals(
            file_path=str(path),
            width=width,
            height=height,
            aspect_ratio=ratio,
            dominant_layout=layout,
            has_faces=None,
            face_count=0,
            text_likelihood=text_likelihood,
            graphic_likelihood=graphic_likelihood,
            photo_likelihood=photo_likelihood,
            screenshot_likelihood=screenshot_likelihood,
            document_likelihood=document_likelihood,
            advertisement_likelihood=advertisement_likelihood,
            explanation=explanation,
        )
        self._cache[signature] = signals
        return signals

    def _cache_key(self, path: Path) -> str:
        try:
            stat = path.stat()
            return f"{path.resolve()}:{int(stat.st_mtime_ns)}:{int(stat.st_size)}"
        except Exception:
            return str(path)

    def _load_for_analysis(self, path: Path) -> tuple[Optional[QImage], Optional[int], Optional[int]]:
        reader = QImageReader(str(path))
        reader.setAutoTransform(True)

        original_size = reader.size()
        source_w = original_size.width() if original_size.isValid() else None
        source_h = original_size.height() if original_size.isValid() else None
        if original_size.isValid() and original_size.width() > 0 and original_size.height() > 0:
            width = original_size.width()
            height = original_size.height()
            if max(width, height) > self._max_dimension:
                if width >= height:
                    scaled = QSize(self._max_dimension, max(1, int(height * (self._max_dimension / width))))
                else:
                    scaled = QSize(max(1, int(width * (self._max_dimension / height))), self._max_dimension)
                reader.setScaledSize(scaled)

        try:
            return reader.read(), source_w, source_h
        except Exception:
            return None, source_w, source_h

    def _dominant_layout(self, width: int, height: int, ratio: Optional[float]) -> str:
        if ratio is None:
            return "unknown"
        if abs(width - height) <= int(0.08 * max(width, height)):
            return "square"
        if ratio <= 0.62 and height >= 800:
            return "tall_mobile"
        if ratio >= 2.6 and width >= 800:
            return "wide_banner"
        if ratio < 1.0:
            return "portrait"
        return "landscape"

    def _sample_metrics(self, image: QImage, started_at: float) -> dict[str, float]:
        width = image.width()
        height = image.height()
        if width <= 0 or height <= 0:
            return {
                "white_ratio": 0.0,
                "high_contrast_ratio": 0.0,
                "palette_diversity": 0.0,
                "variance_score": 0.0,
                "saturation_score": 0.0,
                "flat_ratio": 0.0,
                "edge_density": 0.0,
                "line_density": 0.0,
            }

        grid_w = min(96, width)
        grid_h = min(96, height)
        step_x = max(1, width // grid_w)
        step_y = max(1, height // grid_h)

        brightness_values: list[float] = []
        saturation_values: list[float] = []
        quantized_colors: set[tuple[int, int, int]] = set()

        white_count = 0
        high_contrast_count = 0
        flat_count = 0
        edge_count = 0
        line_count = 0
        samples = 0

        for y in range(0, height, step_y):
            if (perf_counter() - started_at) * 1000.0 > self._timeout_ms:
                raise TimeoutError("visual analysis timed out")
            for x in range(0, width, step_x):
                color = image.pixelColor(x, y)
                r = float(color.red())
                g = float(color.green())
                b = float(color.blue())
                brightness = (0.2126 * r + 0.7152 * g + 0.0722 * b)
                saturation = (max(r, g, b) - min(r, g, b)) / 255.0

                brightness_values.append(brightness)
                saturation_values.append(saturation)
                quantized_colors.add((int(r) // 32, int(g) // 32, int(b) // 32))

                if brightness >= 235 and saturation <= 0.18:
                    white_count += 1
                if brightness <= 50 or brightness >= 205:
                    high_contrast_count += 1

                right_x = min(width - 1, x + step_x)
                down_y = min(height - 1, y + step_y)
                right = image.pixelColor(right_x, y)
                down = image.pixelColor(x, down_y)
                right_b = 0.2126 * right.red() + 0.7152 * right.green() + 0.0722 * right.blue()
                down_b = 0.2126 * down.red() + 0.7152 * down.green() + 0.0722 * down.blue()
                grad = max(abs(brightness - right_b), abs(brightness - down_b))
                if grad <= 12:
                    flat_count += 1
                if grad >= 30:
                    edge_count += 1
                if abs(brightness - right_b) >= 40 or abs(brightness - down_b) >= 40:
                    line_count += 1

                samples += 1

        if samples <= 0:
            samples = 1

        mean_brightness = sum(brightness_values) / samples
        variance = sum((v - mean_brightness) ** 2 for v in brightness_values) / samples

        return {
            "white_ratio": self._clip(white_count / samples),
            "high_contrast_ratio": self._clip(high_contrast_count / samples),
            "palette_diversity": self._clip(len(quantized_colors) / 128.0),
            "variance_score": self._clip(variance / 2800.0),
            "saturation_score": self._clip((sum(saturation_values) / samples) / 0.5),
            "flat_ratio": self._clip(flat_count / samples),
            "edge_density": self._clip(edge_count / samples),
            "line_density": self._clip(line_count / samples),
        }

    def _clip(self, value: float) -> float:
        return max(0.0, min(1.0, float(value)))
