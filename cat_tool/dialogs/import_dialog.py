"""Dialog for reviewing multiple files before a batch import."""
import os

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QDialog, QDialogButtonBox, QFileDialog,
                             QHBoxLayout, QLabel, QListWidget,
                             QListWidgetItem, QMessageBox, QPushButton,
                             QVBoxLayout)


class MultiFileImportDialog(QDialog):
    """Show a list of files that will be imported in one operation.

    Files can be added, removed or cleared before pressing *Import*.
    """

    def __init__(self, parent=None, title="Import Files",
                 file_filter="All Files (*)", initial_files=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumSize(640, 360)
        self._file_filter = file_filter
        self._last_dir = ""
        self._build_ui()
        for path in initial_files or []:
            self._add_path(path)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Files to import:"))

        self.file_list = QListWidget(self)
        self.file_list.setSelectionMode(QListWidget.ExtendedSelection)
        layout.addWidget(self.file_list)

        buttons = QHBoxLayout()
        add_btn = QPushButton("Add Files...")
        add_btn.setToolTip("Add more files to this import")
        add_btn.clicked.connect(self.add_files)
        remove_btn = QPushButton("Remove Selected")
        remove_btn.setToolTip("Remove the selected files from this import")
        remove_btn.clicked.connect(self.remove_selected)
        clear_btn = QPushButton("Clear")
        clear_btn.setToolTip("Remove every file from this import")
        clear_btn.clicked.connect(self.file_list.clear)
        buttons.addWidget(add_btn)
        buttons.addWidget(remove_btn)
        buttons.addWidget(clear_btn)
        buttons.addStretch()
        layout.addLayout(buttons)

        box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
                               self)
        box.button(QDialogButtonBox.Ok).setText("Import")
        box.accepted.connect(self._accept_if_any)
        box.rejected.connect(self.reject)
        layout.addWidget(box)

    def _add_path(self, path):
        if not path:
            return
        path = os.path.normpath(path)
        if not os.path.isfile(path):
            return
        existing = {
            self.file_list.item(i).data(Qt.UserRole)
            for i in range(self.file_list.count())
        }
        if path in existing:
            return
        item = QListWidgetItem(path)
        item.setData(Qt.UserRole, path)
        item.setToolTip(path)
        self.file_list.addItem(item)
        if not self._last_dir:
            self._last_dir = os.path.dirname(path)

    def add_files(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Add Files", self._last_dir, self._file_filter)
        for path in paths:
            self._add_path(path)
            if path and not self._last_dir:
                self._last_dir = os.path.dirname(path)

    def remove_selected(self):
        for item in self.file_list.selectedItems():
            self.file_list.takeItem(self.file_list.row(item))

    def _accept_if_any(self):
        if self.file_list.count() == 0:
            QMessageBox.information(
                self, "No Files", "Add at least one file to import.")
            return
        self.accept()

    def files(self):
        return [
            self.file_list.item(i).data(Qt.UserRole)
            for i in range(self.file_list.count())
        ]
