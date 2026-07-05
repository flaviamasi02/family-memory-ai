import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.face_detection_service import FaceDetectionResult, FaceDetectionService
from core.media_classifier import MediaCategory, MediaClassifier
from models.photo import Photo


class FaceDetectionServiceTests(unittest.TestCase):
    def _make_photo(self, root: Path, filename: str, metadata=None) -> Photo:
        path = root / filename
        path.write_bytes(b"img-bytes")
        photo = Photo.from_path(path)
        photo.metadata.update(metadata or {})
        photo.sync_intelligence_from_metadata()
        return photo

    def test_result_model_works(self):
        result = FaceDetectionResult(
            face_count=2,
            has_faces=True,
            confidence=0.81,
            detector="opencv-haar",
            explanation=["Faces detected"],
        )

        self.assertEqual(result.face_count, 2)
        self.assertTrue(result.has_faces)
        self.assertAlmostEqual(result.confidence, 0.81, places=2)
        self.assertEqual(result.detector, "opencv-haar")
        self.assertEqual(result.explanation, ["Faces detected"])

    def test_unavailable_detector_fallback_does_not_crash(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "face.jpg"
            path.write_bytes(b"fake-image")

            with patch("core.face_detection_service.cv2", None), patch("core.face_detection_service.np", None):
                service = FaceDetectionService(enabled=True)
                result = service.detect(path)

            self.assertFalse(result.has_faces)
            self.assertEqual(result.face_count, 0)
            self.assertEqual(result.confidence, 0.0)
            self.assertEqual(result.detector, "unavailable")
            self.assertEqual(result.explanation, ["Face detection unavailable"])

    def test_classifier_uses_face_metadata_as_family_photo_evidence(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            photo = self._make_photo(
                Path(tmpdir),
                "faces_only.jpg",
                {
                    "width": 1200,
                    "height": 900,
                    "has_faces": True,
                    "face_count": 2,
                    "face_detection_confidence": 0.82,
                    "face_detection_detector": "opencv-haar",
                },
            )

            classifier = MediaClassifier()
            result = classifier.classify_photo(photo)

            self.assertEqual(result.media_category, MediaCategory.FamilyPhoto)
            self.assertEqual(photo.media_category, MediaCategory.FamilyPhoto.value)
            self.assertIn("face detected", result.classification_reason.lower())

    def test_user_corrected_category_is_not_overridden(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            photo = self._make_photo(
                Path(tmpdir),
                "corrected.jpg",
                {
                    "width": 1200,
                    "height": 900,
                    "has_faces": True,
                    "face_count": 1,
                    "face_detection_confidence": 0.9,
                    "face_detection_detector": "opencv-haar",
                    "automatic_media_category": "unknown",
                    "user_corrected_media_category": "advertisement",
                    "effective_media_category": "advertisement",
                    "media_category": "advertisement",
                },
            )

            classifier = MediaClassifier()
            classifier.classify_photo(photo)

            self.assertEqual(photo.user_corrected_media_category, MediaCategory.Advertisement.value)
            self.assertEqual(photo.effective_media_category, MediaCategory.Advertisement.value)
            self.assertEqual(photo.media_category, MediaCategory.Advertisement.value)

    def test_unknown_photo_with_face_metadata_becomes_family_photo(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            photo = self._make_photo(
                Path(tmpdir),
                "unknown_face.jpg",
                {
                    "width": 1200,
                    "height": 900,
                    "has_faces": True,
                    "face_count": 1,
                    "face_detection_confidence": 0.75,
                    "face_detection_detector": "opencv-haar",
                },
            )

            classifier = MediaClassifier()
            result = classifier.classify_photo(photo)

            self.assertEqual(result.media_category, MediaCategory.FamilyPhoto)
            self.assertEqual(photo.media_category, MediaCategory.FamilyPhoto.value)
            self.assertIn("face detected", result.classification_reason.lower())

    def test_no_face_metadata_does_not_force_family_photo(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            photo = self._make_photo(
                Path(tmpdir),
                "no_face.jpg",
                {
                    "width": 1200,
                    "height": 900,
                    "has_faces": False,
                    "face_count": 0,
                    "face_detection_confidence": 0.0,
                    "face_detection_detector": "opencv-haar",
                },
            )

            classifier = MediaClassifier()
            result = classifier.classify_photo(photo)

            self.assertEqual(result.media_category, MediaCategory.Unknown)
            self.assertNotIn("face detected", result.classification_reason.lower())


if __name__ == "__main__":
    unittest.main()
