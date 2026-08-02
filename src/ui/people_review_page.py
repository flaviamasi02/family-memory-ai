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
        controls = QHBoxLayout()
        for text, signal in (("Scan eligible photos for faces", self._scan), ("Pause", self.pause_requested.emit),
                             ("Resume", self.resume_requested.emit), ("Cancel", self.cancel_requested.emit),
                             ("Rebuild clusters", self.refresh)):
            button = QPushButton(text); button.clicked.connect(signal); controls.addWidget(button)
        layout.addLayout(controls)
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
        self.progress_label.setText(f"Eligible photos: {eligible} | Excluded photos: {excluded} | Scan has not started automatically.")

    def _scan(self) -> None:
        eligible = [p for p in self._photos if face_processing_eligibility(p).eligible]
        self.scan_requested.emit(eligible)

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
