from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QLineEdit,
                             QComboBox, QLabel, QPushButton, QHBoxLayout,
                             QDialogButtonBox)
from cat_tool.dialogs import fill_lang_combo


class GlossaryDialog(QDialog):
    def __init__(self, parent=None, source_lang="", target_lang=""):
        super().__init__(parent)
        self.setWindowTitle("Add Glossary Term")
        self.setMinimumWidth(500)
        self.source_lang = source_lang
        self.target_lang = target_lang
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.src_edit = QLineEdit(self)
        self.tgt_edit = QLineEdit(self)
        self.desc_edit = QLineEdit(self)

        self.src_lang_combo = QComboBox(self)
        fill_lang_combo(self.src_lang_combo, self.source_lang)
        self.tgt_lang_combo = QComboBox(self)
        fill_lang_combo(self.tgt_lang_combo, self.target_lang)

        form.addRow("Source Term:", self.src_edit)
        form.addRow("Source Language:", self.src_lang_combo)
        form.addRow("Target Translation:", self.tgt_edit)
        form.addRow("Target Language:", self.tgt_lang_combo)
        form.addRow("Description/Context:", self.desc_edit)

        layout.addLayout(form)

        btn_box = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel, self)
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def get_data(self):
        return (
            self.src_edit.text().strip(),
            self.tgt_edit.text().strip(),
            self.desc_edit.text().strip(),
            self.src_lang_combo.currentData() or "",
            self.tgt_lang_combo.currentData() or "",
        )


class LangDialog(QDialog):
    def __init__(self, sl, tl, count, parent=None):
        super().__init__(parent)
        self.setWindowTitle("TMX Language Detection")
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"Found <b>{count}</b> term pairs in TMX."))
        layout.addWidget(QLabel("Detected languages:"))
        f = QFormLayout()
        self.src_combo = QComboBox()
        fill_lang_combo(self.src_combo, sl)
        self.tgt_combo = QComboBox()
        fill_lang_combo(self.tgt_combo, tl)
        f.addRow("Source:", self.src_combo)
        f.addRow("Target:", self.tgt_combo)
        layout.addLayout(f)
        btns = QHBoxLayout()
        ok = QPushButton("Import")
        ok.setToolTip("Import the TMX terms into the glossary")
        ok.clicked.connect(self.accept)
        cancel = QPushButton("Cancel")
        cancel.setToolTip("Cancel TMX import")
        cancel.clicked.connect(self.reject)
        btns.addWidget(ok)
        btns.addWidget(cancel)
        layout.addLayout(btns)
