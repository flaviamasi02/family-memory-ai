from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class PhotoDetailsPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setObjectName("photoDetailsPanel")
        self.setMinimumWidth(260)

        self.title_label = QLabel("Selected photo")
        self.title_label.setStyleSheet("font-size: 16px; font-weight: bold;")

        self.details_label = QLabel("Double-click a photo to view details.")
        self.details_label.setWordWrap(True)
        self.details_label.setAlignment(Qt.AlignmentFlag.AlignTop)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.addWidget(self.title_label)
        layout.addWidget(self.details_label)

        self.setLayout(layout)

    def set_photo(self, photo):
        if photo is not None:
            print(f"PhotoDetailsPanel set_photo called: {photo.display_name()}")
        else:
            print("PhotoDetailsPanel set_photo called: None")

        if photo is None:
            self.title_label.setText("Selected photo")
            self.details_label.setText("Double-click a photo to view details.")
            return

        lines = [
            f"Filename: {photo.display_name()}",
            f"File size: {self._format_size(photo.file_size)}",
            f"Status: {self._format_status(photo.status)}",
        ]

        intelligence = getattr(photo, "intelligence", None)
        date_taken_value = None
        date_source_value = None

        if intelligence is not None:
            date_taken_value = getattr(intelligence, "date_taken", None)
            date_source_value = getattr(intelligence, "date_source", None)

        metadata = getattr(photo, "metadata", {}) or {}
        if metadata:
            width = metadata.get("width")
            height = metadata.get("height")
            if width is not None and height is not None:
                lines.append(f"Dimensions: {width} x {height}")

            if not date_taken_value:
                date_taken_value = metadata.get("date_taken")
            if not date_source_value:
                date_source_value = metadata.get("date_source")

            camera_make = metadata.get("camera_make")
            camera_model = metadata.get("camera_model")
            if camera_make or camera_model:
                camera = " ".join(part for part in [camera_make, camera_model] if part)
                lines.append(f"Camera: {camera}")

            orientation = metadata.get("orientation")
            if orientation is not None:
                lines.append(f"Orientation: {orientation}")

            if metadata.get("has_gps"):
                lines.append("GPS: present")

        lines.append(f"Date: {date_taken_value or '-'}")
        lines.append(f"Date source: {date_source_value or 'Unknown'}")
        lines.append(f"Relevance: {getattr(intelligence, 'relevance_category', 'unknown') if intelligence is not None else 'unknown'}")
        reason = getattr(intelligence, "relevance_reason", "") if intelligence is not None else ""
        if reason:
            lines.append(f"Relevance reason: {reason}")

        self.title_label.setText(photo.display_name())
        self.details_label.setText("\n".join(lines))

    def _format_status(self, status):
        labels = {
            "pending": "🟡 Pending",
            "thumbnail_loading": "🔵 Loading thumbnail...",
            "thumbnail_ready": "🟢 Thumbnail ready",
            "metadata_loading": "🟣 Reading metadata...",
            "ready": "✅ Ready",
            "error": "🔴 Error",
        }
        return labels.get(status, "⚪ Unknown")

    def _format_size(self, size):
        if size is None:
            return "Unknown"
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024 or unit == "GB":
                return f"{size:.1f} {unit}" if unit != "B" else f"{size} {unit}"
            size /= 1024
        return f"{size:.1f} GB"
