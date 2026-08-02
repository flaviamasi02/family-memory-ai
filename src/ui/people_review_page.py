"""Product-owner controlled People Review workspace."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QListWidget, QMessageBox,
                               QPushButton, QVBoxLayout, QWidget)

from faces.eligibility import face_processing_eligibility
from faces.persistence import SQLiteFaceRepository
from faces.processing import FaceCropCache
from ui.components.workspace_header import WorkspaceHeader
from ui.components.workspace_info_content import WORKSPACE_INFO_CONTENT
from ui.components.workspace_info_panel import WorkspaceInfoPanel


SUGGESTED_PROFILES = ("Flavia", "Miguel", "Luis", "Patrizia", "Cleto", "Fiorenza",
                      "Daniele", "Chon", "Joaquin", "Dani")


class PeopleReviewPage(QWidget):
    WORKSPACE_ID = "people_review"
    help_requested = Signal(str)
    scan_requested = Signal(object)
    pause_requested = Signal()
    resume_requested = Signal()
    cancel_requested = Signal()
    runtime_settings_requested = Signal()

    def __init__(self, repository: SQLiteFaceRepository | None = None, parent=None):
        super().__init__(parent)
        self.repository = repository or SQLiteFaceRepository()
        self._photos = []
        layout = QVBoxLayout(self)
        self.header = WorkspaceHeader("People Review")
        self.header.help_clicked.connect(lambda: self.help_requested.emit(self.WORKSPACE_ID))
        layout.addWidget(self.header)
        info = WORKSPACE_INFO_CONTENT[self.WORKSPACE_ID]
        self.info_panel = WorkspaceInfoPanel(
            workspace_id=self.WORKSPACE_ID, title=info.title, purpose=info.purpose,
            purpose_details=info.purpose_details, typical_actions=info.typical_actions,
            tip=info.tip, collapsed_label=info.collapsed_label,
        )
        layout.addWidget(self.info_panel)
        layout.addWidget(QLabel("Face processing happens locally on this computer. Photos are never uploaded, and no identity is claimed without your confirmation."))
        self.progress_label = QLabel("Choose Scan eligible photos for faces to begin."); layout.addWidget(self.progress_label)
        self.open_runtime_settings_button = QPushButton("Open Face Runtime Settings")
        self.open_runtime_settings_button.clicked.connect(self.runtime_settings_requested.emit)
        layout.addWidget(self.open_runtime_settings_button)
        controls = QHBoxLayout()
        self.scan_button = QPushButton("Scan eligible photos for faces")
        self.pause_button = QPushButton("Pause")
        self.resume_button = QPushButton("Resume")
        self.cancel_button = QPushButton("Cancel")
        self.rebuild_button = QPushButton("Rebuild clusters")
        for button, signal in ((self.scan_button, self._scan), (self.pause_button, self.pause_requested.emit),
                               (self.resume_button, self.resume_requested.emit), (self.cancel_button, self.cancel_requested.emit),
                               (self.rebuild_button, self.refresh)):
            button.clicked.connect(signal); controls.addWidget(button)
        layout.addLayout(controls)
        self._runtime_ready = False
        self.set_runtime_ready(False)
        actions = QHBoxLayout()
        self.profiles_button = QPushButton("Create suggested family profiles")
        self.profiles_button.clicked.connect(self._create_suggested_profiles); actions.addWidget(self.profiles_button)
        actions.addWidget(QPushButton("Review unnamed clusters")); actions.addWidget(QPushButton("Review suggested matches")); actions.addStretch()
        layout.addLayout(actions)
        self.clusters = QListWidget(); self.clusters.setAccessibleName("Face cluster candidates"); layout.addWidget(self.clusters, 1)
        self.detail_label = QLabel("Select a cluster to review faces, source photos, confidence, and assignment actions.")
        self.detail_label.setWordWrap(True); layout.addWidget(self.detail_label)
        self.refresh()

    def set_photos(self, photos) -> None:
        self._photos = list(photos or [])
        eligible = sum(face_processing_eligibility(p).eligible for p in self._photos)
        excluded = len(self._photos) - eligible
        suffix = "Scan has not started automatically." if self._runtime_ready else "Face recognition runtime is not installed."
        self.progress_label.setText(f"Eligible photos: {eligible} | Excluded photos: {excluded} | {suffix}")

    def _scan(self) -> None:
        eligible = [p for p in self._photos if face_processing_eligibility(p).eligible]
        self.progress_label.setText(f"Preparing local face scan for {len(eligible)} eligible photos…")
        self.set_scan_state("running")
        self.scan_requested.emit(eligible)

    def set_scan_state(self, state: str) -> None:
        active, paused = state in {"running", "paused"}, state == "paused"
        self.scan_button.setEnabled(not active and self._runtime_ready)
        self.pause_button.setEnabled(state == "running")
        self.resume_button.setEnabled(paused)
        self.cancel_button.setEnabled(active)

    def set_runtime_ready(self, ready: bool) -> None:
        self._runtime_ready = bool(ready)
        self.open_runtime_settings_button.setVisible(not ready)
        if not ready:
            self.progress_label.setText("Face recognition runtime is not installed.")
        elif "runtime is not installed" in self.progress_label.text():
            self.progress_label.setText("Face recognition runtime is ready. Choose Scan eligible photos for faces to begin.")
        self.set_scan_state("idle")

    def show_scan_progress(self, progress) -> None:
        self.progress_label.setText(
            f"Eligible: {progress.eligible} | Processed: {progress.processed} | "
            f"Current: {progress.current or 'finishing'} | Faces found: {progress.faces_found} | "
            f"No faces: {progress.no_faces} | Failures: {progress.failures} | Remaining: {progress.remaining}"
        )

    def show_scan_completed(self, progress) -> None:
        self.refresh(); self.set_scan_state("idle")
        outcome = "cancelled safely" if progress.cancelled else "complete"
        self.progress_label.setText(
            f"Local face scan {outcome}. Processed {progress.processed} of {progress.eligible} photos; "
            f"found {progress.faces_found} faces; {progress.no_faces} had no faces; {progress.failures} failed."
        )

    def show_scan_unavailable(self, message: str) -> None:
        self.set_runtime_ready(False)
        self.progress_label.setText(f"Face recognition runtime is not available. {message}")

    def refresh(self) -> None:
        self.clusters.clear()
        persons = {p.id: p.name for p in self.repository.list_persons()}
        for cluster in self.repository.list_clusters():
            faces = self.repository.faces_for_cluster(cluster.id)
            photos = len({f.image_id for f in faces})
            name = persons.get(cluster.person_id, "Unnamed")
            quality = "Strong grouping" if (cluster.confidence or 0) >= .9 else "Needs review"
            self.clusters.addItem(f"{name} — {len(faces)} faces in {photos} photos — {quality}")

    def _create_suggested_profiles(self) -> None:
        names = "\n".join(SUGGESTED_PROFILES)
        if QMessageBox.question(self, "Create suggested family profiles",
                                f"Create these unassigned profiles?\n\n{names}") != QMessageBox.StandardButton.Yes:
            self.profiles_button.setVisible(False)  # do not repeatedly prompt after dismissal this session
            return
        existing = {p.name.casefold() for p in self.repository.list_persons()}
        from faces.models import Person
        for name in SUGGESTED_PROFILES:
            if name.casefold() not in existing: self.repository.save_person(Person(name=name))
        self.profiles_button.setVisible(False)

    def delete_all_face_analysis(self) -> bool:
        answer = QMessageBox.warning(
            self, "Delete all face analysis data?",
            "This removes detections, face crops, embeddings, clusters, suggestions, and confirmed person assignments. Original photos, categories, cleanup history, and album decisions remain untouched.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel)
        if answer != QMessageBox.StandardButton.Yes: return False
        self.repository.clear_face_analysis(); FaceCropCache().clear(); self.refresh(); return True
