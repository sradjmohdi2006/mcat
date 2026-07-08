import re
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QLineEdit, QPushButton, QWidget, QCheckBox, QHeaderView,
)
from PyQt5.QtCore import Qt

DEFAULT_RULES = [
    {"pattern": ".", "break_after": True, "case_sensitive": False, "whole_word": False},
    {"pattern": "!", "break_after": True, "case_sensitive": False, "whole_word": False},
    {"pattern": "?", "break_after": True, "case_sensitive": False, "whole_word": False},
    {"pattern": ";", "break_after": True, "case_sensitive": False, "whole_word": False},
    {"pattern": ":", "break_after": True, "case_sensitive": False, "whole_word": False},
    {"pattern": "Mr", "break_after": False, "case_sensitive": True, "whole_word": True},
    {"pattern": "Mrs", "break_after": False, "case_sensitive": True, "whole_word": True},
    {"pattern": "Dr", "break_after": False, "case_sensitive": True, "whole_word": True},
    {"pattern": "Ms", "break_after": False, "case_sensitive": True, "whole_word": True},
    {"pattern": "Prof", "break_after": False, "case_sensitive": True, "whole_word": True},
    {"pattern": "Sr", "break_after": False, "case_sensitive": True, "whole_word": True},
    {"pattern": "Jr", "break_after": False, "case_sensitive": True, "whole_word": True},
]


class AdvancedRulesDialog(QDialog):
    def __init__(self, parent=None, rules=None):
        super().__init__(parent)
        self.setWindowTitle("Segmentation Rules")
        self.setMinimumWidth(600)
        self.rules = rules if rules is not None else [dict(r) for r in DEFAULT_RULES]
        self._build_ui()
        self._populate_table()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Pattern / Word", "Break After", "Case Sensitive", "Whole Word"])
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        for c in range(1, 4):
            self.table.horizontalHeader().setSectionResizeMode(c, QHeaderView.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        layout.addWidget(self.table)

        input_row = QHBoxLayout()
        self.pattern_input = QLineEdit()
        self.pattern_input.setPlaceholderText("Enter pattern or punctuation...")
        input_row.addWidget(self.pattern_input)
        self.add_btn = QPushButton("Add Rule")
        self.add_btn.clicked.connect(self._add_rule)
        input_row.addWidget(self.add_btn)
        layout.addLayout(input_row)

        btn_row = QHBoxLayout()
        self.remove_btn = QPushButton("Remove Selected Rule")
        self.remove_btn.clicked.connect(self._remove_selected)
        btn_row.addWidget(self.remove_btn)
        btn_row.addStretch()
        self.apply_btn = QPushButton("Apply Rules")
        self.apply_btn.clicked.connect(self.accept)
        btn_row.addWidget(self.apply_btn)
        layout.addLayout(btn_row)

    def _make_checkbox(self, state):
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        cb = QCheckBox()
        cb.setChecked(bool(state))
        cb.stateChanged.connect(lambda s, r=type(self): self._on_check_changed())
        lay.addWidget(cb, 0, Qt.AlignCenter)
        return w

    def _populate_table(self):
        self.table.setRowCount(0)
        self.table.setRowCount(len(self.rules))
        for idx, rule in enumerate(self.rules):
            item = QTableWidgetItem(rule["pattern"])
            self.table.setItem(idx, 0, item)
            self.table.setCellWidget(idx, 1, self._make_checkbox(rule["break_after"]))
            self.table.setCellWidget(idx, 2, self._make_checkbox(rule["case_sensitive"]))
            self.table.setCellWidget(idx, 3, self._make_checkbox(rule["whole_word"]))

    def _add_rule(self):
        text = self.pattern_input.text().strip()
        if not text:
            return
        self.rules.append({
            "pattern": text,
            "break_after": False,
            "case_sensitive": False,
            "whole_word": True,
        })
        self._populate_table()
        self.pattern_input.clear()
        self.table.selectRow(self.table.rowCount() - 1)

    def _remove_selected(self):
        rows = set()
        for idx in self.table.selectedIndexes():
            rows.add(idx.row())
        for row in sorted(rows, reverse=True):
            if 0 <= row < len(self.rules):
                self.rules.pop(row)
        self._populate_table()

    def _on_check_changed(self):
        pass

    def get_rules(self):
        for idx, rule in enumerate(self.rules):
            w1 = self.table.cellWidget(idx, 1)
            w2 = self.table.cellWidget(idx, 2)
            w3 = self.table.cellWidget(idx, 3)
            rule["break_after"] = w1.findChild(QCheckBox).isChecked()
            rule["case_sensitive"] = w2.findChild(QCheckBox).isChecked()
            rule["whole_word"] = w3.findChild(QCheckBox).isChecked()
        return self.rules


def advanced_segmenter(text, custom_rules=None):
    if not text:
        return []

    rules = custom_rules if custom_rules else DEFAULT_RULES
    splitters = [r for r in rules if r.get("break_after", True)]
    exceptions = [r for r in rules if not r.get("break_after", True)]

    try:
        splitter_chars = set()
        for r in splitters:
            if len(r["pattern"]) == 1 and not r.get("whole_word", False):
                splitter_chars.add(r["pattern"])
            elif r.get("whole_word", False):
                pass

        if not splitter_chars:
            return text.splitlines()

        char_class = "".join(re.escape(c) for c in sorted(splitter_chars))

        positions = []
        for m in re.finditer(rf"([{char_class}])\s+", text):
            pos = m.start()
            full = m.group(0)
            punct = m.group(1)
            end = m.end()

            prefix = text[:pos].rstrip()
            is_exception = False
            for r in exceptions:
                pat = r["pattern"]
                flags = 0 if r.get("case_sensitive", False) else re.IGNORECASE
                ww = r.get("whole_word", False)
                try:
                    if ww:
                        check = re.search(rf"\b{re.escape(pat)}\b$", prefix, flags)
                    else:
                        check = re.search(rf"{re.escape(pat)}$", prefix, flags)
                    if check:
                        is_exception = True
                        break
                except re.error:
                    continue

            if not is_exception:
                positions.append((pos, end))

        if not positions:
            return [text]

        segments = []
        prev = 0
        for start, end in positions:
            segments.append(text[prev:start].strip())
            prev = end
        segments.append(text[prev:].strip())

        return [s for s in segments if s]

    except re.error:
        return text.splitlines()
