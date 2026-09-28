import re
import json
import os
from functools import lru_cache
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


# ============================================================
# OPTIMIZED SEGMENTATION ENGINE
# ============================================================

class _CompiledRules:
    """Pre-compiled segmentation rules for fast matching."""
    __slots__ = (
        "after_chars", "before_chars", "after_regex", "before_regex",
        "exception_patterns", "exception_regex", "has_exceptions"
    )
    
    def __init__(self, rules, language=None):
        self.after_chars = set()
        self.before_chars = set()
        self.after_regex = None
        self.before_regex = None
        self.exception_patterns = []
        self.exception_regex = None
        self.has_exceptions = False
        
        # Filter by language
        if language and language != "All":
            rules = [r for r in rules if r.get("language", "All") in ("All", language)]
        
        after_rules = [r for r in rules if r.get("break_after", False)]
        before_rules = [r for r in rules if r.get("break_before", False)]
        exceptions = [r for r in rules if not r.get("break_after", False) and not r.get("break_before", False)]
        
        # Single-char break-after (fast path: character class)
        for r in after_rules:
            pat = r["pattern"]
            if len(pat) == 1 and not r.get("whole_word", False):
                self.after_chars.add(pat)
        
        # Single-char break-before (fast path: character class)
        for r in before_rules:
            pat = r["pattern"]
            if len(pat) == 1 and not r.get("whole_word", False):
                self.before_chars.add(pat)
        
        # Multi-char or whole-word rules -> compile regex
        after_multi = [r for r in after_rules if len(r["pattern"]) > 1 or r.get("whole_word", False)]
        before_multi = [r for r in before_rules if len(r["pattern"]) > 1 or r.get("whole_word", False)]
        
        if after_multi:
            parts = []
            for r in after_multi:
                pat = re.escape(r["pattern"])
                if r.get("whole_word", False):
                    pat = rf"\b{pat}\b"
                flags = "" if r.get("case_sensitive", False) else "(?i)"
                parts.append(f"(?P<after_{id(r)}>{flags}{pat})")
            self.after_regex = re.compile("|".join(parts))
        
        if before_multi:
            parts = []
            for r in before_multi:
                pat = re.escape(r["pattern"])
                if r.get("whole_word", False):
                    pat = rf"\b{pat}\b"
                flags = "" if r.get("case_sensitive", False) else "(?i)"
                parts.append(f"(?P<before_{id(r)}>{flags}{pat})")
            self.before_regex = re.compile("|".join(parts))
        
        # Exceptions: compile combined regex for fast checking
        if exceptions:
            self.has_exceptions = True
            for r in exceptions:
                pat = re.escape(r["pattern"])
                flags = 0 if r.get("case_sensitive", False) else re.IGNORECASE
                if r.get("whole_word", False):
                    pat = rf"\b{pat}\b"
                self.exception_patterns.append((re.compile(pat + "$", flags), r.get("whole_word", False)))
            # Combined exception regex for single check
            exc_parts = []
            for r in exceptions:
                pat = re.escape(r["pattern"])
                if r.get("whole_word", False):
                    pat = rf"\b{pat}\b"
                flags = "" if r.get("case_sensitive", False) else "(?i)"
                exc_parts.append(f"(?P<exc_{id(r)}>{flags}{pat})$")
            self.exception_regex = re.compile("|".join(exc_parts))


@lru_cache(maxsize=32)
def _get_compiled_rules(rules_key, language):
    """Cache compiled rules by (rules_key, language)."""
    # Reconstruct rules from key
    rules = [
        {"pattern": p, "break_after": ba, "break_before": bb,
         "case_sensitive": cs, "whole_word": ww, "language": lang}
        for p, ba, bb, cs, ww, lang in rules_key
    ]
    return _CompiledRules(rules, language)


def advanced_segmenter(text, custom_rules=None, language=None, lang_code=None):
    """Fast segmentation using pre-compiled rules and single-pass scanning."""
    if not text:
        return []
    
    # Resolve rules
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
    
    # Get compiled rules (cached)
    rules_key = tuple((r["pattern"], r.get("break_after", False), r.get("break_before", False),
                       r.get("case_sensitive", False), r.get("whole_word", False), r.get("language", "All"))
                      for r in rules)
    compiled = _get_compiled_rules(rules_key, language or "All")
    
    # Fast path: no rules matched
    if not compiled.after_chars and not compiled.before_chars and not compiled.after_regex and not compiled.before_regex:
        return [text.strip()] if text.strip() else []
    
    # Find all break positions in a single pass
    positions = []
    text_len = len(text)
    
    # 1. Single-char break-after: scan once
    if compiled.after_chars:
        # Build a set for O(1) lookup
        after_set = compiled.after_chars
        i = 0
        while i < text_len - 1:
            ch = text[i]
            if ch in after_set and text[i + 1].isspace():
                # Check exception
                if not compiled.has_exceptions or not _is_exception_fast(text, i, compiled):
                    positions.append((i, i + 1))
                i += 2  # skip the whitespace
                continue
            i += 1
    
    # 2. Single-char break-before: scan once
    if compiled.before_chars:
        before_set = compiled.before_chars
        i = 1
        while i < text_len:
            ch = text[i]
            if ch in before_set and text[i - 1].isspace():
                if not compiled.has_exceptions or not _is_exception_fast(text, i, compiled):
                    positions.append((i, i))
            i += 1
    
    # 3. Multi-char / whole-word rules: use compiled regex
    if compiled.after_regex:
        for m in compiled.after_regex.finditer(text):
            start, end = m.span()
            # Check if followed by whitespace (break-after semantics)
            if end < text_len and text[end].isspace():
                if not compiled.has_exceptions or not _is_exception_fast(text, end, compiled):
                    positions.append((end, end + 1))  # break after the pattern + whitespace
    
    if compiled.before_regex:
        for m in compiled.before_regex.finditer(text):
            start, end = m.span()
            # Check if preceded by whitespace (break-before semantics)
            if start > 0 and text[start - 1].isspace():
                if not compiled.has_exceptions or not _is_exception_fast(text, start, compiled):
                    positions.append((start, start))
    
    if not positions:
        return [text.strip()] if text.strip() else []
    
    # Sort and merge positions
    positions.sort()
    merged = []
    for p in positions:
        if merged and p[0] < merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], p[1]))
        else:
            merged.append(p)
    
    # Extract segments
    segments = []
    prev = 0
    for start, end in merged:
        if start > prev:
            seg = text[prev:start].strip()
            if seg:
                segments.append(seg)
        prev = end
    # Last segment
    last = text[prev:].strip()
    if last:
        segments.append(last)
    
    return segments


def _is_exception_fast(text, pos, compiled):
    """Fast exception check using pre-compiled regex on prefix."""
    # Check prefix ending at pos
    prefix = text[:pos]
    # Use combined exception regex
    if compiled.exception_regex:
        return bool(compiled.exception_regex.search(prefix))
    return False
