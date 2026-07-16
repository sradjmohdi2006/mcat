from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
                             QLabel, QListWidget, QListWidgetItem, QWidget,
                             QFileDialog, QMessageBox)
from PyQt5.QtCore import Qt


class SpellCheckDialog(QDialog):
    def __init__(self, segments, spellchecker, parent=None):
        super().__init__(parent)
        self.segments = segments
        self.spellchecker = spellchecker
        self.setWindowTitle("Spell Check")
        self.setMinimumSize(700, 450)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        names = self.spellchecker.loaded_names
        dict_label = QLabel(f"Dictionaries: {', '.join(names) if names else 'None'}")
        dict_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(dict_label)

        if not self.spellchecker.has_dict:
            layout.addWidget(QLabel("No dictionary loaded. Load a LibreOffice .oxt / .zip / .dic file:"))
            btn = QPushButton("Load Dictionary")
            btn.clicked.connect(self._load_dict)
            layout.addWidget(btn)
            close_btn = QPushButton("Close")
            close_btn.clicked.connect(self.accept)
            layout.addWidget(close_btn)
            return

        self.results = []
        for idx, seg in enumerate(self.segments):
            target = seg.get("target_clean", seg.get("target", ""))
            if not target:
                continue
            errors = self.spellchecker.check_text(target)
            if errors:
                self.results.append((idx, seg, errors))

        status_label = QLabel(f"Found errors in {len(self.results)} of {len(self.segments)} segments")
        layout.addWidget(status_label)

        self.list_widget = QListWidget()
        self.list_widget.currentRowChanged.connect(self._show_details)
        layout.addWidget(self.list_widget)

        self.detail_label = QLabel("Select an error above to see suggestions")
        self.detail_label.setWordWrap(True)
        layout.addWidget(self.detail_label)

        self.suggestions_widget = QWidget()
        self.suggest_layout = QHBoxLayout(self.suggestions_widget)
        layout.addWidget(self.suggestions_widget)
        self.suggestions_widget.setVisible(False)

        btn_layout = QHBoxLayout()
        load_btn = QPushButton("Load Dictionary")
        load_btn.clicked.connect(self._load_dict)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(load_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

        self._populate()

    def _populate(self):
        self.list_widget.blockSignals(True)
        self.list_widget.clear()
        for seg_idx, seg, errors in self.results:
            text = f"Segment {seg_idx + 1}: {', '.join(w for w, _ in errors[:5])}"
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, (seg_idx, seg, errors))
            self.list_widget.addItem(item)
        self.list_widget.blockSignals(False)

    def _show_details(self, row):
        self._clear_suggestions()
        if row < 0 or row >= self.list_widget.count():
            self.detail_label.setText("Select an error above to see suggestions")
            self.suggestions_widget.setVisible(False)
            return
        item = self.list_widget.item(row)
        seg_idx, seg, errors = item.data(Qt.UserRole)

        parts = [f"Segment {seg_idx + 1}:"]
        parts.append(f"Source: {seg.get('source_clean', seg['source'])[:100]}")
        parts.append(f"Target: {seg.get('target_clean', seg.get('target', ''))[:100]}")
        parts.append("")
        for word, suggs in errors:
            if suggs:
                parts.append(f'  "{word}" -> {", ".join(suggs[:5])}')
            else:
                parts.append(f'  "{word}" (no suggestions)')
        self.detail_label.setText("\n".join(parts))

        self._show_suggestion_buttons(errors)

    def _clear_suggestions(self):
        while self.suggest_layout.count():
            w = self.suggest_layout.takeAt(0).widget()
            if w:
                w.deleteLater()

    def _show_suggestion_buttons(self, errors):
        self._clear_suggestions()
        if not errors:
            self.suggestions_widget.setVisible(False)
            return
        first_word, first_suggs = errors[0]
        if not first_suggs:
            self.suggestions_widget.setVisible(False)
            return
        lbl = QLabel(f'Replace "{first_word}":')
        self.suggest_layout.addWidget(lbl)
        for s in first_suggs[:8]:
            btn = QPushButton(s)
            btn.clicked.connect(lambda checked, w=first_word, r=s: self._replace_word(w, r))
            self.suggest_layout.addWidget(btn)
        self.suggest_layout.addStretch()
        self.suggestions_widget.setVisible(True)

    def _replace_word(self, old, new):
        row = self.list_widget.currentRow()
        if row < 0:
            return
        item = self.list_widget.item(row)
        seg_idx, seg, errors = item.data(Qt.UserRole)
        target = seg.get("target_clean", seg.get("target", ""))
        new_target = target.replace(old, new, 1)
        if "target_clean" in seg:
            seg["target_clean"] = new_target
        else:
            seg["target"] = new_target
        new_errors = self.spellchecker.check_text(new_target)
        new_errors = [e for e in new_errors if e[0] != old]
        if new_errors:
            self.results[row] = (seg_idx, seg, new_errors)
            self._populate()
            self.list_widget.setCurrentRow(row)
            self._show_details(row)
        else:
            self.results.pop(row)
            self._populate()
            if self.results:
                self.list_widget.setCurrentRow(min(row, len(self.results) - 1))
            else:
                self.detail_label.setText("All errors corrected!")
                self.suggestions_widget.setVisible(False)

    def _load_dict(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Dictionary", "",
            "Dictionary (*.oxt *.zip *.dic);;All Files (*)"
        )
        if not path:
            return
        if path.endswith(".dic"):
            ok = self.spellchecker.load_dictionary(path)
        else:
            ok = self.spellchecker.load_from_archive(path)
        if ok:
            QMessageBox.information(self, "Success", "Dictionary loaded.")
            self.init_ui()
        else:
            QMessageBox.warning(self, "Error", "Failed to load dictionary.")
