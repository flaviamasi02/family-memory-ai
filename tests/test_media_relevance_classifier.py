import tempfile
import unittest
from pathlib import Path

from core.media_relevance_classifier import MediaRelevanceClassifier


class MediaRelevanceClassifierTests(unittest.TestCase):
    def setUp(self):
        self.classifier = MediaRelevanceClassifier()

    def test_screenshot_classification(self):
        result = self.classifier.classify("Screenshot_2024-05-06.png", {"width": 1200, "height": 800})

        self.assertEqual(result.relevance_category, "screenshot")
        self.assertFalse(result.is_album_relevant_candidate)

    def test_video_classification(self):
        result = self.classifier.classify("vacation_clip.mp4")

        self.assertEqual(result.relevance_category, "video")
        self.assertFalse(result.is_album_relevant_candidate)

    def test_document_and_receipt_classification(self):
        doc_result = self.classifier.classify("document_scan_01.jpg")
        receipt_result = self.classifier.classify("receipt_2024.jpg")

        self.assertEqual(doc_result.relevance_category, "document_image")
        self.assertEqual(receipt_result.relevance_category, "receipt_or_scan")
        self.assertFalse(doc_result.is_album_relevant_candidate)
        self.assertFalse(receipt_result.is_album_relevant_candidate)

    def test_unsupported_classification(self):
        result = self.classifier.classify("notes.txt")

        self.assertEqual(result.relevance_category, "unsupported_file")
        self.assertFalse(result.is_album_relevant_candidate)

    def test_default_family_photo_candidate(self):
        result = self.classifier.classify("family_photo.jpg", {"width": 2000, "height": 1500})

        self.assertEqual(result.relevance_category, "family_photo_candidate")
        self.assertTrue(result.is_album_relevant_candidate)


if __name__ == "__main__":
    unittest.main()