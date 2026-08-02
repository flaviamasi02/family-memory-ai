from pathlib import Path
from types import SimpleNamespace
import os
import pytest
import json
import queue

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QMessageBox

from faces.models import BoundingBox, FaceEmbedding
from faces.persistence import SQLiteFaceRepository
from faces.processing import (FaceImageProcessingError, FaceModelUnavailable,
                              ManagedFaceRuntimeClient)
from faces.services import FaceDetectionCandidate
from workers.face_processing_worker import FaceProcessingWorker
from ui.main_window import MainWindow


class FakeDetector:
    provider_id, model_revision, available = "fake-detector", "1", True

    def detect(self, path, cancel_event=None):
        if "corrupt" in path.name:
            raise ValueError("corrupt fixture")
        if "empty" in path.name:
            return ()
        return (FaceDetectionCandidate(BoundingBox(1, 1, 10, 10), .95),)


class FakeCropCache:
    def create(self, path, face):
        face.crop_cache_path = str(path)
        return path


class FakeEmbedder:
    provider_id, model_id, model_revision, embedding_dimension = "fake-face", "identity", "1", 2

    def embed(self, path, faces, cancel_event=None):
        return tuple(FaceEmbedding(face.id, self.provider_id, self.model_id,
                                   self.model_revision, 2, (1.0, 0.0),
                                   face.source_fingerprint) for face in faces)


class _FakePipe:
    def __init__(self, lines=None, on_write=None): self.lines=queue.Queue(); self.on_write=on_write
    def write(self, value):
        if self.on_write: self.on_write(value)
    def flush(self): pass
    def close(self): self.lines.put(None)
    def readline(self):
        value=self.lines.get(); return "" if value is None else value


class _FakePersistentProcess:
    def __init__(self, responses, stderr=""):
        self.responses=iter(responses); self.stdout=_FakePipe(); self.stderr=_FakePipe(); self.running=True
        self.stdin=_FakePipe(on_write=self._request)
        self.stdout.lines.put(json.dumps({"ready":True,"protocol_version":"face-worker-v1","model_load_count":1})+"\n")
        for line in stderr.splitlines(): self.stderr.lines.put(line+"\n")
        self.stderr.lines.put(None)
    def _request(self, line):
        request=json.loads(line); response=next(self.responses)
        if response is None: return
        if isinstance(response, str): self.stdout.lines.put(response+"\n"); return
        response=dict(response); response["request_id"]=request["request_id"]
        self.stdout.lines.put(json.dumps(response)+"\n")
    def poll(self): return None if self.running else 0
    def wait(self, timeout=None): self.running=False; self.stdout.lines.put(None); self.stderr.lines.put(None); return 0
    def terminate(self): self.running=False; self.stdout.lines.put(None)
    def kill(self): self.terminate()


class FakePersistentProcessFactory:
    def __init__(self, responses, stderr=""): self.responses=responses; self.stderr=stderr; self.launch_count=0
    def __call__(self, *args, **kwargs): self.launch_count += 1; return _FakePersistentProcess(self.responses, self.stderr)


def photo(path, photo_id):
    return SimpleNamespace(path=path, filename=path.name, id=photo_id, metadata={},
                           effective_media_category="family_photo")


def test_worker_processes_batch_isolates_failure_persists_and_clusters(tmp_path):
    paths = [tmp_path / name for name in ("face.jpg", "empty.jpg", "corrupt.jpg")]
    for path in paths:
        path.write_bytes(b"fixture")
    repository = SQLiteFaceRepository(tmp_path / "faces.sqlite3")
    worker = FaceProcessingWorker([photo(path, str(i)) for i, path in enumerate(paths)], repository,
                                  FakeDetector(), FakeEmbedder(), crop_cache=FakeCropCache())
    updates, completed = [], []
    worker.progress.connect(updates.append); worker.completed.connect(completed.append)

    worker.run()

    result = completed[0]
    assert (result.processed, result.faces_found, result.no_faces, result.failures) == (3, 1, 1, 1)
    assert updates[-1].remaining == 0
    assert len(repository.list_faces()) == 1
    assert len(repository.list_clusters()) == 1
    assert repository.list_faces()[0].person_id is None


def test_worker_pause_resume_cancel_state_and_safe_partial_completion(tmp_path):
    path = tmp_path / "face.jpg"; path.write_bytes(b"fixture")
    worker = FaceProcessingWorker([photo(path, "one")], SQLiteFaceRepository(tmp_path / "faces.sqlite3"),
                                  FakeDetector(), FakeEmbedder(), crop_cache=FakeCropCache())
    worker.pause(); assert worker._paused is True
    worker.resume(); assert worker._paused is False
    completed = []; worker.completed.connect(completed.append)
    worker.cancel(); worker.run()
    assert completed[0].cancelled is True
    assert completed[0].processed == 0


def test_unavailable_runtime_is_visible_signal(tmp_path):
    class UnavailableDetector(FakeDetector):
        available = False
    repository = SQLiteFaceRepository(tmp_path / "faces.sqlite3")
    worker = FaceProcessingWorker([], repository, UnavailableDetector(), FakeEmbedder(), crop_cache=FakeCropCache())
    messages = []; worker.unavailable.connect(messages.append)
    worker.run()
    assert messages and "unavailable" in messages[0].lower()


def test_main_window_wires_scan_click_filters_inputs_and_updates_immediately(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    eligible_path = tmp_path / "family.jpg"; eligible_path.write_bytes(b"fixture")
    excluded_path = tmp_path / "screen.jpg"; excluded_path.write_bytes(b"fixture")
    eligible = photo(eligible_path, "family")
    excluded = photo(excluded_path, "screen")
    excluded.effective_media_category = "screenshot"
    received = []
    monkeypatch.setattr(MainWindow, "_start_face_processing", lambda self, photos: received.append(list(photos)))
    window = MainWindow()
    window.people_review_page.set_photos([eligible, excluded])
    window.people_review_page.set_runtime_ready(True)

    window.people_review_page.scan_button.click(); app.processEvents()

    assert received == [[eligible]]
    assert "Preparing local face scan for 1 eligible photos" in window.people_review_page.progress_label.text()
    assert not window.people_review_page.scan_button.isEnabled()
    assert window.people_review_page.pause_button.isEnabled()
    assert window.people_review_page.cancel_button.isEnabled()
    window.close()


def test_progress_and_control_states_are_explained_to_owner(tmp_path):
    app = QApplication.instance() or QApplication([])
    from ui.people_review_page import PeopleReviewPage
    from workers.face_processing_worker import FaceScanProgress
    page = PeopleReviewPage(SQLiteFaceRepository(tmp_path / "faces.sqlite3"))
    page.set_runtime_ready(True)
    page.show_scan_progress(FaceScanProgress(10, 4, "photo.jpg", 3, 1, 0, 6))
    assert "Processed: 4" in page.progress_label.text()
    assert "Faces found: 3" in page.progress_label.text()
    page.set_scan_state("paused")
    assert page.resume_button.isEnabled() and not page.pause_button.isEnabled()
    page.show_scan_completed(FaceScanProgress(10, 4, cancelled=True, remaining=6))
    assert "cancelled safely" in page.progress_label.text()
    assert page.scan_button.isEnabled()
    app.processEvents()


def test_missing_runtime_navigates_to_settings_and_ready_update_needs_no_restart(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    page = window.people_review_page
    page.set_runtime_ready(False)
    assert not page.scan_button.isEnabled()
    assert not page.open_runtime_settings_button.isHidden()

    page.open_runtime_settings_button.click(); app.processEvents()
    assert window.tabs.currentWidget() is window.settings_page

    window.settings_page.face_runtime_ready_changed.emit(True); app.processEvents()
    assert page.scan_button.isEnabled()
    assert not page.open_runtime_settings_button.isVisible()
    window.close()


def test_verification_failure_recommends_repair_not_internet(tmp_path):
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    window.settings_page._on_face_runtime_failed(
        "The OpenCV installation is invalid or incomplete. Technical detail: CASCADE_API_MISSING"
    )
    message = window.settings_page.face_runtime_message.text().lower()
    assert "repair" in message
    assert "internet" not in message
    assert window.settings_page.face_runtime_progress.value() == 0
    assert window.settings_page.face_runtime_repair_button.isEnabled()
    window.close(); app.processEvents()


def test_managed_protocol_success_image_failure_runtime_failure_and_logs(tmp_path):
    responses = [
        {"ok":True,"faces":[],"processing_ms":2},
        {"ok":False,"error_scope":"image","error_code":"decode_failed","message":"This image could not be decoded.","processing_ms":3},
        {"ok":False,"error_scope":"runtime","error_code":"runtime_import_failed","message":"The managed runtime could not load OpenCV.","processing_ms":1},
    ]
    factory = FakePersistentProcessFactory(responses, stderr="decoder detail\nimport detail\n")
    client = ManagedFaceRuntimeClient(tmp_path / "runtime with spaces" / "python.exe",
                                      tmp_path / "runtime.log", process_factory=factory)
    assert client.invoke("detect", {"image_path": "C:/Fotos/niño one.jpg"}, suffix=".jpg")["faces"] == []
    with pytest.raises(FaceImageProcessingError, match="could not be decoded"):
        client.invoke("detect", {"image_path": "bad.jpg"}, suffix=".jpg")
    with pytest.raises(FaceModelUnavailable, match="load OpenCV"):
        client.invoke("detect", {"image_path": "valid.jpg"}, suffix=".jpg")
    log = (tmp_path / "runtime.log").read_text()
    assert "decoder detail" in log and "import detail" in log and "image_suffix" in log
    assert "niño one.jpg" not in log
    assert factory.launch_count == 1
    client.close()


def test_malformed_protocol_and_timeout_are_precisely_classified(tmp_path):
    import subprocess
    malformed = ManagedFaceRuntimeClient("managed-python", tmp_path / "bad.log",
                                         process_factory=FakePersistentProcessFactory(["not-json"]))
    with pytest.raises(FaceModelUnavailable, match="invalid protocol"):
        malformed.invoke("detect", {"image_path": "x.jpg"})
    timed = ManagedFaceRuntimeClient("managed-python", tmp_path / "timeout.log",
                                    process_factory=FakePersistentProcessFactory([None]))
    with pytest.raises(FaceImageProcessingError, match="timed out"):
        timed.invoke("detect", {"image_path": "x.jpg"}, timeout=.01)
    timed.close()


def test_heic_is_excluded_consistently_instead_of_invalidating_runtime(tmp_path):
    path = tmp_path / "phone.heic"; path.write_bytes(b"fixture")
    from faces.eligibility import face_processing_eligibility
    decision = face_processing_eligibility(photo(path, "heic"))
    assert not decision.eligible and decision.reason_code == "managed_decoder_unsupported"


def test_one_persistent_process_handles_one_hundred_requests(tmp_path):
    factory=FakePersistentProcessFactory([{"ok":True,"faces":[],"processing_ms":1} for _ in range(100)])
    client=ManagedFaceRuntimeClient("managed-python", tmp_path/"performance.log", process_factory=factory)
    for index in range(100):
        result=client.invoke("detect", {"image_path":f"C:/Photos/image {index}.jpg"})
        assert result["faces"] == []
    assert factory.launch_count == 1 and client.launch_count == 1
    client.close()


def test_embedding_failure_preserves_successful_detection(tmp_path):
    class FailingEmbedder(FakeEmbedder):
        def embed(self, path, faces, cancel_event=None):
            raise ValueError("descriptor fixture failure")

    path = tmp_path / "face.jpg"; path.write_bytes(b"fixture")
    repository = SQLiteFaceRepository(tmp_path / "faces.sqlite3")
    worker = FaceProcessingWorker([photo(path, "one")], repository, FakeDetector(),
                                  FailingEmbedder(), crop_cache=FakeCropCache())
    completed = []; worker.completed.connect(completed.append); worker.run()
    result = completed[0]
    assert result.faces_found == 1
    assert result.failures == 0
    assert result.embedding_failures == 1
    assert repository.faces_for_image("one")[0].processing_error == "embedding_failed"


def test_crop_failure_preserves_detection_and_is_not_a_hard_image_failure(tmp_path):
    class FailingCrop:
        def create(self, path, face): raise OSError("crop fixture failure")

    path = tmp_path / "face.jpg"; path.write_bytes(b"fixture")
    repository = SQLiteFaceRepository(tmp_path / "faces.sqlite3")
    worker = FaceProcessingWorker([photo(path, "one")], repository, FakeDetector(),
                                  FakeEmbedder(), crop_cache=FailingCrop())
    completed = []; worker.completed.connect(completed.append); worker.run()
    result = completed[0]
    assert (result.faces_found, result.failures, result.crop_failures) == (1, 0, 1)
    assert len(repository.faces_for_image("one")) == 1


def test_grouped_hard_failure_reasons_are_counted_and_ranked(tmp_path):
    paths = [tmp_path / f"corrupt-{index}.jpg" for index in range(3)]
    for path in paths: path.write_bytes(b"bad")
    worker = FaceProcessingWorker([photo(path, str(index)) for index, path in enumerate(paths)],
                                  SQLiteFaceRepository(tmp_path / "faces.sqlite3"), FakeDetector(),
                                  FakeEmbedder(), crop_cache=FakeCropCache())
    completed = []; worker.completed.connect(completed.append); worker.run()
    assert completed[0].failure_reasons == (("image_processing_failed", 3),)


def test_high_failure_warning_shows_top_reason_and_can_cancel(tmp_path, monkeypatch):
    from ui.people_review_page import PeopleReviewPage
    from workers.face_processing_worker import FaceScanProgress
    app = QApplication.instance() or QApplication([])
    page = PeopleReviewPage(SQLiteFaceRepository(tmp_path / "faces.sqlite3"))
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: QMessageBox.StandardButton.No)
    cancelled = []; page.cancel_requested.connect(lambda: cancelled.append(True))
    page.show_scan_progress(FaceScanProgress(100, processed=20, failures=15, remaining=80,
                                             failure_reasons=(("crop_failed", 15),)))
    assert "top reason: crop_failed" in page.progress_label.text()
    assert cancelled == [True]
    app.processEvents()
