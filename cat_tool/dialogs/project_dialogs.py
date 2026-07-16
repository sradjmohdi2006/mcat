import os

from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QLineEdit,
                             QLabel, QPushButton, QHBoxLayout, QListWidget,
                             QFileDialog, QDialogButtonBox, QComboBox)
from PyQt5.QtCore import Qt

from cat_tool.dialogs import fill_lang_combo, FILE_FILTER


class NewProjectDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("New Project")
        self.setMinimumWidth(520)
        self.source_files = []
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.name_edit = QLineEdit(self)
        self.name_edit.setPlaceholderText("My Translation Project")
        name_label = QLabel("Project Name:")
        form.addRow(name_label, self.name_edit)

        self.src_lang_combo = QComboBox(self)
        fill_lang_combo(self.src_lang_combo, "en")
        self.src_lang_combo.setMinimumWidth(250)
        src_label = QLabel("Source Language:")
        form.addRow(src_label, self.src_lang_combo)

        self.tgt_lang_combo = QComboBox(self)
        fill_lang_combo(self.tgt_lang_combo, "es")
        self.tgt_lang_combo.setMinimumWidth(250)
        tgt_label = QLabel("Target Language:")
        form.addRow(tgt_label, self.tgt_lang_combo)

        layout.addLayout(form)
        layout.addSpacing(10)

        files_label = QLabel("Files to Translate:")
        layout.addWidget(files_label)
        self.file_list = QListWidget(self)
        layout.addWidget(self.file_list)

        file_btn_layout = QHBoxLayout()
        browse_btn = QPushButton("Browse for Files...", self)
        browse_btn.clicked.connect(self.browse_files)
        clear_btn = QPushButton("Clear", self)
        clear_btn.setStyleSheet("background-color: #4a4a52;")
        clear_btn.clicked.connect(self.clear_files)
        file_btn_layout.addWidget(browse_btn)
        file_btn_layout.addWidget(clear_btn)
        layout.addLayout(file_btn_layout)

        layout.addSpacing(10)
        buttons_layout = QHBoxLayout()
        self.create_btn = QPushButton("Create Project", self)
        self.create_btn.clicked.connect(self.accept)
        self.cancel_btn = QPushButton("Cancel", self)
        self.cancel_btn.clicked.connect(self.reject)
        self.cancel_btn.setStyleSheet("background-color: #4a4a52;")
        buttons_layout.addStretch()
        buttons_layout.addWidget(self.create_btn)
        buttons_layout.addWidget(self.cancel_btn)
        layout.addLayout(buttons_layout)

    def browse_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Select Files to Translate", "", FILE_FILTER
        )
        for f in files:
            if f not in self.source_files:
                self.source_files.append(f)
                self.file_list.addItem(f"{os.path.basename(f)}  ({os.path.dirname(f)})")

    def clear_files(self):
        self.source_files.clear()
        self.file_list.clear()

    def get_data(self):
        return (
            self.name_edit.text().strip(),
            self.src_lang_combo.currentData(),
            self.tgt_lang_combo.currentData(),
            list(self.source_files),
        )


class ProjectSettingsDialog(QDialog):
    def __init__(self, project, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Project Settings")
        self.setMinimumWidth(500)
        self.project = project
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.name_edit = QLineEdit(self.project.name, self)
        name_label = QLabel("Project Name:")
        form.addRow(name_label, self.name_edit)

        self.src_lang_combo = QComboBox(self)
        fill_lang_combo(self.src_lang_combo, self.project.source_lang)
        self.src_lang_combo.setMinimumWidth(250)
        src_label = QLabel("Source Language:")
        form.addRow(src_label, self.src_lang_combo)

        self.tgt_lang_combo = QComboBox(self)
        fill_lang_combo(self.tgt_lang_combo, self.project.target_lang)
        self.tgt_lang_combo.setMinimumWidth(250)
        tgt_label = QLabel("Target Language:")
        form.addRow(tgt_label, self.tgt_lang_combo)

        layout.addLayout(form)
        layout.addSpacing(10)
        files_label = QLabel("Source Files:")
        layout.addWidget(files_label)
        self.file_list = QListWidget(self)
        for f in self.project.source_files:
            self.file_list.addItem(os.path.basename(f))
        layout.addWidget(self.file_list)

        file_btn_layout = QHBoxLayout()
        add_btn = QPushButton("Add PO File...", self)
        add_btn.clicked.connect(self.add_source_file)
        rem_btn = QPushButton("Remove", self)
        rem_btn.setStyleSheet("background-color: #4a4a52;")
        rem_btn.clicked.connect(self.remove_source_file)
        file_btn_layout.addWidget(add_btn)
        file_btn_layout.addWidget(rem_btn)
        layout.addLayout(file_btn_layout)

        layout.addSpacing(10)
        btn_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def add_source_file(self):
        files, _ = QFileDialog.getOpenFileName(
            self, "Add Source File", "", "PO Files (*.po);;All Files (*)"
        )
        if files:
            self.project.source_files.append(files)
            self.file_list.addItem(os.path.basename(files))

    def remove_source_file(self):
        row = self.file_list.currentRow()
        if row >= 0:
            self.file_list.takeItem(row)
            self.project.source_files.pop(row)

    def apply(self):
        self.project.name = self.name_edit.text().strip()
        self.project.source_lang = self.src_lang_combo.currentData()
        self.project.target_lang = self.tgt_lang_combo.currentData()
