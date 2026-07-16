import re
import json
import os
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QLineEdit, QPushButton, QWidget, QCheckBox, QComboBox, QLabel,
    QGroupBox, QSplitter, QMessageBox,
)
from PyQt5.QtCore import Qt

LANGUAGES = [
    "All", "English", "Spanish", "French", "German", "Italian",
    "Portuguese", "Dutch", "Russian", "Arabic", "Chinese", "Japanese",
    "Korean", "Turkish", "Polish", "Swedish", "Danish", "Norwegian",
    "Finnish", "Greek", "Hebrew", "Hindi", "Thai", "Vietnamese",
    "Czech", "Slovak", "Hungarian", "Romanian", "Bulgarian", "Ukrainian",
]

LANG_NAME_TO_CODE = {
    "All": "all", "English": "en", "Spanish": "es", "French": "fr",
    "German": "de", "Italian": "it", "Portuguese": "pt", "Dutch": "nl",
    "Russian": "ru", "Arabic": "ar", "Chinese": "zh", "Japanese": "ja",
    "Korean": "ko", "Turkish": "tr", "Polish": "pl", "Swedish": "sv",
    "Danish": "da", "Norwegian": "no", "Finnish": "fi", "Greek": "el",
    "Hebrew": "he", "Hindi": "hi", "Thai": "th", "Vietnamese": "vi",
    "Czech": "cs", "Slovak": "sk", "Hungarian": "hu", "Romanian": "ro",
    "Bulgarian": "bg", "Ukrainian": "uk",
}


def _segrules_dir():
    d = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "mcat", "segrules")
    os.makedirs(d, exist_ok=True)
    return d


def load_rules(lang_code):
    path = os.path.join(_segrules_dir(), f"{lang_code}.json")
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return None


def save_rules(rules, lang_code):
    path = os.path.join(_segrules_dir(), f"{lang_code}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(rules, f, indent=2, ensure_ascii=False)


DEFAULT_RULES = [
    {"pattern": ".", "break_after": True, "case_sensitive": False, "whole_word": False, "language": "All"},
    {"pattern": "!", "break_after": True, "case_sensitive": False, "whole_word": False, "language": "All"},
    {"pattern": "?", "break_after": True, "case_sensitive": False, "whole_word": False, "language": "All"},
    {"pattern": ";", "break_after": True, "case_sensitive": False, "whole_word": False, "language": "All"},
    {"pattern": ":", "break_after": True, "case_sensitive": False, "whole_word": False, "language": "All"},
    {"pattern": "Mr", "break_after": False, "case_sensitive": True, "whole_word": True, "language": "English"},
    {"pattern": "Mrs", "break_after": False, "case_sensitive": True, "whole_word": True, "language": "English"},
    {"pattern": "Dr", "break_after": False, "case_sensitive": True, "whole_word": True, "language": "English"},
    {"pattern": "Ms", "break_after": False, "case_sensitive": True, "whole_word": True, "language": "English"},
    {"pattern": "Prof", "break_after": False, "case_sensitive": True, "whole_word": True, "language": "English"},
    {"pattern": "Sr", "break_after": False, "case_sensitive": True, "whole_word": True, "language": "English"},
    {"pattern": "Jr", "break_after": False, "case_sensitive": True, "whole_word": True, "language": "English"},
]


def _rule_summary(rule):
    parts = [f"\"{rule['pattern']}\""]
    ba = rule.get("break_after", False)
    bb = rule.get("break_before", False)
    if ba:
        parts.append("break after")
    elif bb:
        parts.append("break before")
    else:
        parts.append("no break")
    flags = []
    if rule.get("case_sensitive"):
        flags.append("case")
    if rule.get("whole_word"):
        flags.append("whole word")
    if flags:
        parts.append(", ".join(flags))
    lang = rule.get("language", "All")
    parts.append(f"[{lang}]")
    return " \u2014 ".join(parts)


class AdvancedRulesDialog(QDialog):
    def __init__(self, parent=None, rules=None, lang_code=None):
        super().__init__(parent)
        self.lang_code = lang_code or "all"
        title = f"Segmentation Rules — {self.lang_code}.json"
        self.setWindowTitle(title)
        self.setMinimumWidth(720)
        self.setMinimumHeight(500)
        self.rules = rules if rules is not None else [dict(r) for r in DEFAULT_RULES]
        self._modified_index = None
        self._build_ui()
        self._refresh_list()

    def _build_ui(self):
        outer = QVBoxLayout(self)

        splitter = QSplitter(Qt.Horizontal)

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)

        left_layout.addWidget(QLabel("Rules:"))
        self.rule_list = QListWidget()
        self.rule_list.currentRowChanged.connect(self._on_selection_changed)
        left_layout.addWidget(self.rule_list)

        list_btn_row = QHBoxLayout()
        self.add_btn = QPushButton("Add")
        self.add_btn.clicked.connect(self._start_add)
        self.remove_btn = QPushButton("Remove")
        self.remove_btn.clicked.connect(self._remove_selected)
        self.remove_btn.setEnabled(False)
        list_btn_row.addWidget(self.add_btn)
        list_btn_row.addWidget(self.remove_btn)
        list_btn_row.addStretch()
        left_layout.addLayout(list_btn_row)

        splitter.addWidget(left_panel)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)

        detail_group = QGroupBox("Rule Details")
        detail_layout = QVBoxLayout(detail_group)

        detail_layout.addWidget(QLabel("Pattern (word, punctuation, or phrase):"))
        self.pattern_input = QLineEdit()
        self.pattern_input.setPlaceholderText("e.g. Mr, ., !, ...")
        detail_layout.addWidget(self.pattern_input)

        detail_layout.addWidget(QLabel("Language:"))
        self.lang_combo = QComboBox()
        self.lang_combo.addItems(LANGUAGES)
        detail_layout.addWidget(self.lang_combo)

        detail_layout.addWidget(QLabel("Options:"))
        self.break_after_cb = QCheckBox("Break after this pattern")
        self.break_after_cb.setChecked(True)
        self.break_before_cb = QCheckBox("Break before this pattern")
        self.case_cb = QCheckBox("Case sensitive")
        self.ww_cb = QCheckBox("Whole word only")
        detail_layout.addWidget(self.break_after_cb)
        detail_layout.addWidget(self.break_before_cb)
        detail_layout.addWidget(self.case_cb)
        detail_layout.addWidget(self.ww_cb)

        detail_btn_row = QHBoxLayout()
        self.save_btn = QPushButton("Add Rule")
        self.save_btn.clicked.connect(self._save_rule)
        self.save_btn.setStyleSheet("background-color: #0078d4; color: white;")
        self.clear_btn = QPushButton("Clear")
        self.clear_btn.clicked.connect(self._clear_form)
        detail_btn_row.addWidget(self.save_btn)
        detail_btn_row.addWidget(self.clear_btn)
        detail_btn_row.addStretch()
        detail_layout.addLayout(detail_btn_row)

        detail_layout.addStretch()
        right_layout.addWidget(detail_group)

        apply_row = QHBoxLayout()
        apply_row.addStretch()
        self.apply_btn = QPushButton("Apply Rules")
        self.apply_btn.clicked.connect(self._apply)
        apply_row.addWidget(self.apply_btn)
        right_layout.addLayout(apply_row)

        splitter.addWidget(right_panel)
        splitter.setSizes([300, 420])
        outer.addWidget(splitter)

    def _rule_summary(self, rule):
        return _rule_summary(rule)

    def _refresh_list(self):
        self.rule_list.blockSignals(True)
        self.rule_list.clear()
        for rule in self.rules:
            item = QListWidgetItem(self._rule_summary(rule))
            self.rule_list.addItem(item)
        self.rule_list.blockSignals(False)
        self.remove_btn.setEnabled(self.rule_list.count() > 0)

    def _on_selection_changed(self, row):
        if row < 0 or row >= len(self.rules):
            self._clear_form()
            self.remove_btn.setEnabled(False)
            return
        self.remove_btn.setEnabled(True)
        rule = self.rules[row]
        self._modified_index = row
        self.pattern_input.setText(rule["pattern"])
        lang = rule.get("language", "All")
        idx = self.lang_combo.findText(lang)
        if idx >= 0:
            self.lang_combo.setCurrentIndex(idx)
        else:
            self.lang_combo.setCurrentIndex(0)
        self.break_after_cb.setChecked(rule.get("break_after", False))
        self.break_before_cb.setChecked(rule.get("break_before", False))
        self.case_cb.setChecked(rule.get("case_sensitive", False))
        self.ww_cb.setChecked(rule.get("whole_word", False))
        self.save_btn.setText("Update Rule")

    def _clear_form(self):
        self._modified_index = None
        self.pattern_input.clear()
        self.lang_combo.setCurrentIndex(0)
        self.break_after_cb.setChecked(True)
        self.break_before_cb.setChecked(False)
        self.case_cb.setChecked(False)
        self.ww_cb.setChecked(False)
        self.save_btn.setText("Add Rule")
        self.rule_list.clearSelection()

    def _save_rule(self):
        pattern = self.pattern_input.text().strip()
        if not pattern:
            QMessageBox.warning(self, "Missing Pattern", "Please enter a pattern.")
            return
        rule = {
            "pattern": pattern,
            "break_after": self.break_after_cb.isChecked(),
            "break_before": self.break_before_cb.isChecked(),
            "case_sensitive": self.case_cb.isChecked(),
            "whole_word": self.ww_cb.isChecked(),
            "language": self.lang_combo.currentText(),
        }
        if self._modified_index is not None and 0 <= self._modified_index < len(self.rules):
            self.rules[self._modified_index] = rule
        else:
            self.rules.append(rule)
        self._refresh_list()
        self._clear_form()

    def _start_add(self):
        self._clear_form()
        self.pattern_input.setFocus()

    def _remove_selected(self):
        row = self.rule_list.currentRow()
        if row < 0 or row >= len(self.rules):
            return
        reply = QMessageBox.question(
            self, "Remove Rule",
            f"Remove rule: {self._rule_summary(self.rules[row])}?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        self.rules.pop(row)
        self._refresh_list()
        self._clear_form()

    def _apply(self):
        if self.pattern_input.text().strip():
            self._save_rule()
        by_lang = {}
        for rule in self.rules:
            lang_name = rule.get("language", "All")
            code = LANG_NAME_TO_CODE.get(lang_name, "all")
            by_lang.setdefault(code, []).append(rule)
        for code, lang_rules in by_lang.items():
            save_rules(lang_rules, code)
        self.accept()

    def get_rules(self):
        return self.rules


def advanced_segmenter(text, custom_rules=None, language=None, lang_code=None):
    if not text:
        return []

    rules = custom_rules
    if rules is None and lang_code:
        lang_rules = []
        loaded = load_rules(lang_code)
        if loaded:
            lang_rules.extend(loaded)
        loaded_all = load_rules("all")
        if loaded_all:
            lang_rules.extend(loaded_all)
        if lang_rules:
            rules = lang_rules
    if rules is None:
        rules = DEFAULT_RULES

    if language and language != "All":
        rules = [r for r in rules if r.get("language", "All") in ("All", language)]
        if not rules:
            return text.splitlines()

    after_rules = [r for r in rules if r.get("break_after", False)]
    before_rules = [r for r in rules if r.get("break_before", False)]
    exceptions = [r for r in rules if not r.get("break_after", False) and not r.get("break_before", False)]

    try:
        positions = []

        # --- break-after: single-char splitters ---
        after_chars = set()
        for r in after_rules:
            if len(r["pattern"]) == 1 and not r.get("whole_word", False):
                after_chars.add(r["pattern"])

        if after_chars:
            cc = "".join(re.escape(c) for c in sorted(after_chars))
            for m in re.finditer(rf"([{cc}])\s+", text):
                if not _is_exception(text[:m.start()].rstrip(), exceptions):
                    positions.append((m.start(), m.end()))

        # --- break-before: single-char splitters ---
        before_chars = set()
        for r in before_rules:
            if len(r["pattern"]) == 1 and not r.get("whole_word", False):
                before_chars.add(r["pattern"])

        if before_chars:
            cc = "".join(re.escape(c) for c in sorted(before_chars))
            for m in re.finditer(rf"(?<=\s)[{cc}]", text):
                if not _is_exception(text[:m.start()].rstrip(), exceptions):
                    positions.append((m.start(), m.start()))

        positions.sort(key=lambda x: (x[0], x[1]))

        # Merge overlapping / adjacent positions
        merged = []
        for p in positions:
            if merged and p[0] < merged[-1][1]:
                merged[-1] = (merged[-1][0], max(merged[-1][1], p[1]))
            else:
                merged.append(p)
        positions = merged

        if not positions:
            return [text]

        segments = []
        prev = 0
        for start, end in positions:
            if start > prev:
                segments.append(text[prev:start].strip())
            prev = end
        segments.append(text[prev:].strip())

        return [s for s in segments if s]

    except re.error:
        return text.splitlines()


def _is_exception(prefix, exceptions):
    for r in exceptions:
        pat = r["pattern"]
        flags = 0 if r.get("case_sensitive", False) else re.IGNORECASE
        ww = r.get("whole_word", False)
        try:
            if ww:
                if re.search(rf"\b{re.escape(pat)}\b$", prefix, flags):
                    return True
            else:
                if re.search(rf"{re.escape(pat)}$", prefix, flags):
                    return True
        except re.error:
            continue
    return False
