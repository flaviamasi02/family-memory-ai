from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialogButtonBox,
    QDialog,
    QGridLayout,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from core.category_registry import CategoryDefinition, CategoryRegistry


class CategoryEditorDialog(QDialog):
    def __init__(self, category: Optional[CategoryDefinition] = None, parent=None):
        super().__init__(parent)
        self._editing = category is not None
        self.setWindowTitle("Edit Category" if self._editing else "New Category")
        self.resize(520, 420)

        self.name_input = QLineEdit()
        self.description_input = QTextEdit()
        self.ai_description_input = QTextEdit()
        self.color_input = QLineEdit()
        self.icon_input = QLineEdit()
        self.album_candidate_checkbox = QCheckBox("Album Candidate")
        self.cleanup_category_checkbox = QCheckBox("Cleanup Category")

        self.description_input.setPlaceholderText("Vacation memories.")
        self.ai_description_input.setPlaceholderText(
            "Photos of vacations, mountains, beaches, cities, airports, hotels, landscapes."
        )
        self.color_input.setPlaceholderText("#3B82F6")
        self.icon_input.setPlaceholderText("Optional icon token")

        if category is not None:
            self.name_input.setText(category.display_name)
            self.description_input.setPlainText(category.description or "")
            self.ai_description_input.setPlainText(category.ai_description or "")
            self.color_input.setText(category.color or "")
            self.icon_input.setText(category.icon or "")
            self.album_candidate_checkbox.setChecked(bool(category.is_album_candidate))
            self.cleanup_category_checkbox.setChecked(bool(category.is_cleanup_category))
        else:
            self.album_candidate_checkbox.setChecked(False)
            self.cleanup_category_checkbox.setChecked(True)

        form = QFormLayout()
        form.addRow("Category Name *", self.name_input)
        form.addRow("Description", self.description_input)
        form.addRow("AI Description", self.ai_description_input)
        form.addRow("Color", self.color_input)
        form.addRow("Icon", self.icon_input)
        form.addRow("", self.album_candidate_checkbox)
        form.addRow("", self.cleanup_category_checkbox)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)

        root = QVBoxLayout(self)
        root.addLayout(form)
        root.addWidget(buttons)

    def _on_accept(self) -> None:
        if not self.values()["display_name"]:
            QMessageBox.warning(self, "Invalid category", "Category Name is required.")
            return
        self.accept()

    def values(self) -> dict[str, object]:
        return {
            "display_name": self.name_input.text().strip(),
            "description": self.description_input.toPlainText().strip(),
            "ai_description": self.ai_description_input.toPlainText().strip(),
            "color": self.color_input.text().strip(),
            "icon": self.icon_input.text().strip(),
            "is_album_candidate": self.album_candidate_checkbox.isChecked(),
            "is_cleanup_category": self.cleanup_category_checkbox.isChecked(),
        }


class CategoryManagementDialog(QDialog):
    def __init__(
        self,
        registry: CategoryRegistry,
        usage_counts: Optional[dict[str, int]] = None,
        reassignment_callback: Optional[Callable[[str, str], None]] = None,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Manage Categories")
        self.resize(620, 420)

        self._registry = registry
        self._usage_counts = dict(usage_counts or {})
        self._reassignment_callback = reassignment_callback

        self.system_categories_list = QListWidget()
        self.system_categories_list.currentItemChanged.connect(self._on_selection_changed)
        self.user_categories_list = QListWidget()
        self.user_categories_list.currentItemChanged.connect(self._on_selection_changed)

        self.type_value = QLabel("-")
        self.description_value = QLabel("-")
        self.description_value.setWordWrap(True)
        self.ai_description_value = QLabel("-")
        self.ai_description_value.setWordWrap(True)
        self.color_value = QLabel("-")
        self.icon_value = QLabel("-")
        self.usage_value = QLabel("0")
        self.cleanup_checkbox = QCheckBox("Cleanup category")
        self.album_checkbox = QCheckBox("Album candidate category")

        add_button = QPushButton("+ New Category")
        add_button.clicked.connect(self._add_category)
        self.edit_button = QPushButton("Edit")
        self.edit_button.clicked.connect(self._edit_category)
        self.delete_button = QPushButton("Delete")
        self.delete_button.clicked.connect(self._delete_category)
        self.save_flags_button = QPushButton("Save Flags")
        self.save_flags_button.clicked.connect(self._save_flags)
        self.reset_system_button = QPushButton("Reset System Category to Default")
        self.reset_system_button.clicked.connect(self._reset_system_category)

        left_layout = QVBoxLayout()
        left_layout.addWidget(QLabel("SYSTEM CATEGORIES"))
        left_layout.addWidget(self.system_categories_list, 1)
        left_layout.addWidget(QLabel("USER CATEGORIES"))
        left_layout.addWidget(self.user_categories_list, 1)

        button_row = QHBoxLayout()
        button_row.addWidget(add_button)
        button_row.addWidget(self.edit_button)
        button_row.addWidget(self.delete_button)
        left_layout.addLayout(button_row)

        details_form = QFormLayout()
        details_form.addRow("Type:", self.type_value)
        details_form.addRow("Description:", self.description_value)
        details_form.addRow("AI Description:", self.ai_description_value)
        details_form.addRow("Color:", self.color_value)
        details_form.addRow("Icon:", self.icon_value)
        details_form.addRow("Used by photos:", self.usage_value)

        self.system_notice_label = QLabel(
            "System category - protected. You can customize display and behavior, but cannot delete it."
        )
        self.system_notice_label.setWordWrap(True)
        self.system_notice_label.setStyleSheet("color: #374151; font-size: 12px;")
        self.system_notice_label.setVisible(False)

        right_layout = QVBoxLayout()
        right_layout.addWidget(QLabel("Selected category details"))
        right_layout.addLayout(details_form)
        right_layout.addWidget(self.system_notice_label)
        right_layout.addWidget(self.cleanup_checkbox)
        right_layout.addWidget(self.album_checkbox)
        right_layout.addWidget(self.save_flags_button)
        right_layout.addWidget(self.reset_system_button)
        right_layout.addStretch(1)

        body = QGridLayout()
        body.addLayout(left_layout, 0, 0)
        body.addLayout(right_layout, 0, 1)
        body.setColumnStretch(0, 3)
        body.setColumnStretch(1, 2)

        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)

        root = QVBoxLayout(self)
        root.addLayout(body, 1)
        root.addWidget(close_button, 0, Qt.AlignmentFlag.AlignRight)

        self._reload_list()

    def _reload_list(self) -> None:
        selected_id = self._current_category_id()
        self.system_categories_list.clear()
        self.user_categories_list.clear()

        for category in self._registry.all_categories():
            text = category.display_name
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, category.id)
            if category.is_system:
                self.system_categories_list.addItem(item)
            else:
                self.user_categories_list.addItem(item)

        if self.system_categories_list.count() + self.user_categories_list.count() <= 0:
            self._clear_detail_fields()
            return

        if selected_id:
            for widget in (self.system_categories_list, self.user_categories_list):
                for index in range(widget.count()):
                    item = widget.item(index)
                    if str(item.data(Qt.ItemDataRole.UserRole) or "") == selected_id:
                        widget.setCurrentRow(index)
                        return

        if self.system_categories_list.count() > 0:
            self.system_categories_list.setCurrentRow(0)
        elif self.user_categories_list.count() > 0:
            self.user_categories_list.setCurrentRow(0)

    def _current_category_id(self) -> str:
        item = self.user_categories_list.currentItem()
        if item is None:
            item = self.system_categories_list.currentItem()
        if item is None:
            return ""
        return str(item.data(Qt.ItemDataRole.UserRole) or "")

    def _current_category(self) -> Optional[CategoryDefinition]:
        category_id = self._current_category_id()
        if not category_id:
            return None
        return self._registry.get(category_id)

    def _on_selection_changed(self, _current, _previous) -> None:
        sender = self.sender()
        if sender is self.system_categories_list and self.system_categories_list.currentItem() is not None:
            self.user_categories_list.blockSignals(True)
            self.user_categories_list.clearSelection()
            self.user_categories_list.blockSignals(False)
        elif sender is self.user_categories_list and self.user_categories_list.currentItem() is not None:
            self.system_categories_list.blockSignals(True)
            self.system_categories_list.clearSelection()
            self.system_categories_list.blockSignals(False)

        category = self._current_category()
        if category is None:
            self._clear_detail_fields()
            return

        self.type_value.setText(category.type)
        self.description_value.setText(category.description or "-")
        self.ai_description_value.setText(category.ai_description or "-")
        self.color_value.setText(category.color or "-")
        self.icon_value.setText(category.icon or "-")
        self.usage_value.setText(str(int(self._usage_counts.get(category.id, 0))))
        self.cleanup_checkbox.setChecked(bool(category.is_cleanup_category))
        self.album_checkbox.setChecked(bool(category.is_album_candidate))

        can_delete = not category.is_system
        self.cleanup_checkbox.setEnabled(True)
        self.album_checkbox.setEnabled(True)
        self.delete_button.setEnabled(can_delete)
        self.system_notice_label.setVisible(category.is_system)
        self.reset_system_button.setEnabled(category.is_system)

    def _clear_detail_fields(self) -> None:
        self.type_value.setText("-")
        self.description_value.setText("-")
        self.ai_description_value.setText("-")
        self.color_value.setText("-")
        self.icon_value.setText("-")
        self.usage_value.setText("0")
        self.cleanup_checkbox.setChecked(False)
        self.album_checkbox.setChecked(False)
        self.cleanup_checkbox.setEnabled(False)
        self.album_checkbox.setEnabled(False)
        self.delete_button.setEnabled(False)
        self.system_notice_label.setVisible(False)
        self.reset_system_button.setEnabled(False)

    def _add_category(self) -> None:
        editor = CategoryEditorDialog(parent=self)
        if editor.exec() != QDialog.DialogCode.Accepted:
            return

        values = editor.values()

        try:
            self._registry.create_user_category(
                display_name=str(values["display_name"]),
                description=str(values["description"]),
                ai_description=str(values["ai_description"]),
                color=str(values["color"]),
                icon=str(values["icon"]),
                is_album_candidate=bool(values["is_album_candidate"]),
                is_cleanup_category=bool(values["is_cleanup_category"]),
            )
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid category", str(exc))
            return

        self._reload_list()

    def _edit_category(self) -> None:
        category = self._current_category()
        if category is None:
            return

        editor = CategoryEditorDialog(category=category, parent=self)
        if editor.exec() != QDialog.DialogCode.Accepted:
            return
        values = editor.values()

        try:
            self._registry.update_category_properties(
                category_id=category.id,
                display_name=str(values["display_name"]),
                is_cleanup_category=bool(values["is_cleanup_category"]),
                is_album_candidate=bool(values["is_album_candidate"]),
                description=str(values["description"]),
                ai_description=str(values["ai_description"]),
                color=str(values["color"]),
                icon=str(values["icon"]),
            )
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid category", str(exc))
            return

        self._reload_list()

    def _save_flags(self) -> None:
        category = self._current_category()
        if category is None:
            return

        self._registry.update_category_properties(
            category_id=category.id,
            is_cleanup_category=self.cleanup_checkbox.isChecked(),
            is_album_candidate=self.album_checkbox.isChecked(),
        )
        self._reload_list()

    def _reset_system_category(self) -> None:
        category = self._current_category()
        if category is None or not category.is_system:
            return
        try:
            self._registry.reset_system_category_to_default(category.id)
        except ValueError as exc:
            QMessageBox.warning(self, "Cannot reset", str(exc))
            return
        self._reload_list()

    def _delete_category(self) -> None:
        category = self._current_category()
        if category is None:
            return

        used_count = int(self._usage_counts.get(category.id, 0))
        reassignment = ""
        if used_count > 0:
            choices = [
                cat.display_name
                for cat in self._registry.all_categories()
                if cat.id != category.id
            ]
            if not choices:
                QMessageBox.warning(self, "Cannot delete", "No category available for reassignment.")
                return

            selected, ok = QInputDialog.getItem(
                self,
                "Reassign photos",
                "Category is in use. Reassign to:",
                choices,
                editable=False,
            )
            if not ok or not selected:
                return

            for item in self._registry.all_categories():
                if item.display_name == selected:
                    reassignment = item.id
                    break

        deleted, reason = self._registry.delete_user_category(
            category_id=category.id,
            used_count=used_count,
            reassign_to=reassignment,
        )
        if not deleted:
            QMessageBox.warning(self, "Cannot delete", reason)
            return

        if used_count > 0 and reassignment and callable(self._reassignment_callback):
            self._reassignment_callback(category.id, reassignment)

        self._reload_list()
