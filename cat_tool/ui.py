import os
import sys

# Ensure parent directory is in sys.path to allow running this script directly
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

def _get_data_dir():
    d = os.path.join(os.environ["APPDATA"], "mcat")
    os.makedirs(d, exist_ok=True)
    return d

from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QTableWidget, QTableWidgetItem, QSplitter, QTextEdit, 
                             QPushButton, QLabel, QListWidget, QListWidgetItem, 
                             QFileDialog, QStatusBar, QProgressBar, QMessageBox, 
                             QCheckBox, QDialog, QFormLayout, QLineEdit, QHeaderView,
                             QComboBox, QDialogButtonBox, QMenu)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import (QColor, QFont, QKeySequence)

from cat_tool.file_handler import CATFileHandler, convert_to_po
from cat_tool.formats.tag_utils import PH_L, PH_R, extract_all_tags, apply_tags, restore_tags
from cat_tool.tm import TranslationMemory
from cat_tool.glossary import Glossary
from cat_tool.project import Project
from cat_tool.segmentation import AdvancedRulesDialog, advanced_segmenter, DEFAULT_RULES
from cat_tool.suggest import CompletionDelegate
from cat_tool import qa
from cat_tool.spellcheck import SpellChecker
from cat_tool.settings import AppSettings

DARK_STYLESHEET = """
QMainWindow {
    background-color: #121214;
}
QWidget {
    background-color: #1e1e24;
    color: #ffffff;
    font-family: "Segoe UI", Arial, sans-serif;
    font-size: 13px;
}
QTableWidget {
    background-color: #1a1a1e;
    gridline-color: #2c2c35;
    border: 1px solid #2c2c35;
    border-radius: 4px;
}
QTableWidget::item {
    padding: 8px;
    border-bottom: 1px solid #2c2c35;
}
QTableWidget::item:selected {
    background-color: #0078d4;
    color: white;
}
QHeaderView::section {
    background-color: #25252b;
    color: #b0b0b8;
    padding: 6px;
    border: 1px solid #2c2c35;
    font-weight: bold;
}
QTextEdit {
    background-color: #1a1a1e;
    border: 1px solid #2c2c35;
    border-radius: 4px;
    padding: 6px;
    font-size: 14px;
    color: #ffffff;
}
QTextEdit[readOnly="true"] {
    background-color: #151518;
    color: #a0a0a8;
}
QPushButton {
    background-color: #0078d4;
    color: white;
    border: none;
    padding: 8px 16px;
    border-radius: 4px;
    font-weight: bold;
}
QPushButton:hover {
    background-color: #1085e0;
}
QPushButton:pressed {
    background-color: #0066b3;
}
QPushButton:disabled {
    background-color: #3a3a42;
    color: #808088;
}
QListWidget {
    background-color: #1a1a1e;
    border: 1px solid #2c2c35;
    border-radius: 4px;
}
QListWidget::item {
    padding: 8px;
    border-bottom: 1px solid #2c2c35;
}
QListWidget::item:hover {
    background-color: #25252b;
}
QListWidget::item:selected {
    background-color: #0078d4;
    color: white;
}
QCheckBox {
    spacing: 5px;
}
QCheckBox::indicator {
    width: 18px;
    height: 18px;
}
QStatusBar {
    background-color: #121214;
    color: #b0b0b8;
}
QProgressBar {
    border: 1px solid #2c2c35;
    border-radius: 4px;
    text-align: center;
    background-color: #1a1a1e;
    color: white;
}
QProgressBar::chunk {
    background-color: #20c997;
    border-radius: 3px;
}
QLineEdit {
    background-color: #1a1a1e;
    border: 1px solid #2c2c35;
    border-radius: 4px;
    padding: 6px;
    color: white;
}
QLabel {
    font-weight: bold;
    color: #e0e0e8;
}
"""

class GlossaryDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Glossary Term")
        self.setMinimumWidth(400)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.src_edit = QLineEdit(self)
        self.tgt_edit = QLineEdit(self)
        self.desc_edit = QLineEdit(self)

        src_label = QLabel("Source Term:")
        form.addRow(src_label, self.src_edit)

        tgt_label = QLabel("Target Translation:")
        form.addRow(tgt_label, self.tgt_edit)

        desc_label = QLabel("Description/Context:")
        form.addRow(desc_label, self.desc_edit)

        layout.addLayout(form)

        buttons_layout = QHBoxLayout()
        self.save_btn = QPushButton("Save", self)
        self.save_btn.clicked.connect(self.accept)
        self.cancel_btn = QPushButton("Cancel", self)
        self.cancel_btn.clicked.connect(self.reject)
        self.cancel_btn.setStyleSheet("background-color: #4a4a52;")

        buttons_layout.addWidget(self.save_btn)
        buttons_layout.addWidget(self.cancel_btn)
        layout.addLayout(buttons_layout)

    def get_data(self):
        return (
            self.src_edit.text().strip(),
            self.tgt_edit.text().strip(),
            self.desc_edit.text().strip()
        )

LANGUAGES = [
    ("af", "Afrikaans"), ("sq", "Albanian"), ("ar", "Arabic"), ("hy", "Armenian"),
    ("az", "Azerbaijani"), ("eu", "Basque"), ("be", "Belarusian"), ("bn", "Bengali"),
    ("bs", "Bosnian"), ("bg", "Bulgarian"), ("ca", "Catalan"), ("zh", "Chinese (Simplified)"),
    ("zh-TW", "Chinese (Traditional)"), ("hr", "Croatian"), ("cs", "Czech"), ("da", "Danish"),
    ("nl", "Dutch"), ("en", "English"), ("eo", "Esperanto"), ("et", "Estonian"),
    ("fi", "Finnish"), ("fr", "French"), ("gl", "Galician"), ("ka", "Georgian"),
    ("de", "German"), ("el", "Greek"), ("gu", "Gujarati"), ("he", "Hebrew"),
    ("hi", "Hindi"), ("hu", "Hungarian"), ("is", "Icelandic"), ("id", "Indonesian"),
    ("ga", "Irish"), ("it", "Italian"), ("ja", "Japanese"), ("kn", "Kannada"),
    ("kk", "Kazakh"), ("ko", "Korean"), ("ky", "Kyrgyz"), ("lv", "Latvian"),
    ("lt", "Lithuanian"), ("mk", "Macedonian"), ("ms", "Malay"), ("ml", "Malayalam"),
    ("mt", "Maltese"), ("mr", "Marathi"), ("mn", "Mongolian"), ("ne", "Nepali"),
    ("no", "Norwegian"), ("fa", "Persian"), ("pl", "Polish"), ("pt", "Portuguese"),
    ("pt-BR", "Portuguese (Brazil)"), ("pa", "Punjabi"), ("ro", "Romanian"),
    ("ru", "Russian"), ("sr", "Serbian"), ("sk", "Slovak"), ("sl", "Slovenian"),
    ("es", "Spanish"), ("sw", "Swahili"), ("sv", "Swedish"), ("tl", "Tagalog"),
    ("ta", "Tamil"), ("te", "Telugu"), ("th", "Thai"), ("tr", "Turkish"),
    ("uk", "Ukrainian"), ("ur", "Urdu"), ("uz", "Uzbek"), ("vi", "Vietnamese"),
    ("cy", "Welsh"), ("xh", "Xhosa"), ("yi", "Yiddish"), ("zu", "Zulu"),
]


def _fill_lang_combo(combo, selected_code=""):
    combo.clear()
    for code, name in LANGUAGES:
        combo.addItem(f"{name}  [{code}]", code)
    if selected_code:
        idx = combo.findData(selected_code)
        if idx >= 0:
            combo.setCurrentIndex(idx)


FILE_FILTER = (
    "All Supported Files (*.po *.pot *.xlf *.xliff *.mqxliff *.sdlxliff *.ts *.tmx *.tbx *.csv "
    "*.txt *.pdf *.docx *.pptx *.ppsx *.xlsx *.xls *.odt *.ods *.odp);;"
    "PO Files (*.po *.pot);;"
    "XLIFF (*.xlf *.xliff);;"
    "memoQ MQXLIFF (*.mqxliff);;"
    "SDL Trados SDLXLIFF (*.sdlxliff);;"
    "Qt TS (*.ts);;"
    "TMX (*.tmx);;"
    "TBX (*.tbx);;"
    "CSV (*.csv);;"
    "Text (*.txt);;"
    "PDF (*.pdf);;"
    "Word (*.docx);;"
    "PowerPoint (*.pptx *.ppsx);;"
    "Excel (*.xlsx *.xls);;"
    "OpenDocument (*.odt *.ods *.odp);;"
    "All Files (*)"
)


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
        _fill_lang_combo(self.src_lang_combo, "en")
        self.src_lang_combo.setMinimumWidth(250)
        src_label = QLabel("Source Language:")
        form.addRow(src_label, self.src_lang_combo)

        self.tgt_lang_combo = QComboBox(self)
        _fill_lang_combo(self.tgt_lang_combo, "es")
        self.tgt_lang_combo.setMinimumWidth(250)
        tgt_label = QLabel("Target Language:")
        form.addRow(tgt_label, self.tgt_lang_combo)

        layout.addLayout(form)
        layout.addSpacing(10)

        # Source files section
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
        _fill_lang_combo(self.src_lang_combo, self.project.source_lang)
        self.src_lang_combo.setMinimumWidth(250)
        src_label = QLabel("Source Language:")
        form.addRow(src_label, self.src_lang_combo)

        self.tgt_lang_combo = QComboBox(self)
        _fill_lang_combo(self.tgt_lang_combo, self.project.target_lang)
        self.tgt_lang_combo.setMinimumWidth(250)
        tgt_label = QLabel("Target Language:")
        form.addRow(tgt_label, self.tgt_lang_combo)

        layout.addLayout(form)

        # Source files list
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


class ShortcutsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Keyboard Shortcuts")
        self.setMinimumSize(500, 400)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        table = QTableWidget()
        table.setColumnCount(2)
        table.setHorizontalHeaderLabels(["Shortcut", "Action"])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectRows)

        shortcuts = [
            ("Ctrl+N", "New Project"),
            ("Ctrl+Shift+O", "Open Project"),
            ("Ctrl+Shift+S", "Save Project"),
            ("Ctrl+O", "Open File"),
            ("Ctrl+S", "Save File"),
            ("Ctrl+R", "Render Translated File"),
            ("Ctrl+Down", "Next Segment"),
            ("Ctrl+Up", "Previous Segment"),
            ("Ctrl+U", "Next Untranslated Segment"),
            ("Ctrl+Enter", "Confirm and Next"),
            ("Ctrl+F", "Toggle Fuzzy / Needs Review"),
            ("Ctrl+G", "Add Glossary Term"),
            ("Ctrl+Shift+G", "View/Manage Glossary"),
            ("Ctrl+M", "Import PO into TM"),
            ("Ctrl+Shift+T", "Segmentation Rules"),
            ("Ctrl+Home", "Go to First Segment"),
            ("Ctrl+End", "Go to Last Segment"),
            ("Ctrl+Shift+Q", "Quality Assurance Check"),
            ("F1 / Ctrl+Shift+H", "Show Keyboard Shortcuts"),
        ]

        table.setRowCount(len(shortcuts))
        for i, (shortcut, action) in enumerate(shortcuts):
            table.setItem(i, 0, QTableWidgetItem(shortcut))
            table.setItem(i, 1, QTableWidgetItem(action))

        layout.addWidget(table)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)


class QADialog(QDialog):
    def __init__(self, issues, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Quality Assurance Results")
        self.resize(900, 500)
        self._issues = issues
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        summary = QLabel(
            f"Found {len(self._issues)} issue(s)"
            if self._issues else "No issues found."
        )
        summary.setStyleSheet("font-weight: bold; font-size: 14px; padding: 4px;")
        layout.addWidget(summary)

        self.qa_table = QTableWidget()
        self.qa_table.setColumnCount(6)
        self.qa_table.setHorizontalHeaderLabels(["", "Severity", "Check", "#", "Source", "Target", "Description"])
        self.qa_table.setColumnHidden(0, True)
        self.qa_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.qa_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self.qa_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.qa_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.qa_table.setSelectionMode(QTableWidget.SingleSelection)
        self.qa_table.cellDoubleClicked.connect(self._on_double_click)
        self.qa_table.setRowCount(len(self._issues))

        for i, issue in enumerate(self._issues):
            sev_item = QTableWidgetItem(issue.severity.upper())
            if issue.severity == "error":
                sev_item.setForeground(QColor("#ff4444"))
            else:
                sev_item.setForeground(QColor("#ffaa00"))

            idx_item = QTableWidgetItem(str(issue.segment_index))
            idx_item.setTextAlignment(Qt.AlignCenter)

            self.qa_table.setItem(i, 1, sev_item)
            self.qa_table.setItem(i, 2, QTableWidgetItem(issue.check_name))
            self.qa_table.setItem(i, 3, idx_item)
            self.qa_table.setItem(i, 4, QTableWidgetItem(issue.source[:120] if issue.source else ""))
            self.qa_table.setItem(i, 5, QTableWidgetItem(issue.target[:120] if issue.target else ""))
            self.qa_table.setItem(i, 6, QTableWidgetItem(issue.description))

            # Hidden column 0 stores the segment index for navigation
            hidden_item = QTableWidgetItem(str(issue.segment_index))
            self.qa_table.setItem(i, 0, hidden_item)

        layout.addWidget(self.qa_table)

        btn_layout = QHBoxLayout()
        go_btn = QPushButton("Go to Selected Segment")
        go_btn.setStyleSheet("background-color: #0078d4;")
        go_btn.clicked.connect(self._go_to_segment)
        btn_layout.addWidget(go_btn)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)

        layout.addLayout(btn_layout)

    def _go_to_segment(self):
        row = self.qa_table.currentRow()
        if row < 0:
            return
        seg_idx = int(self.qa_table.item(row, 0).text())
        main_win = self.parent()
        if main_win and hasattr(main_win, "navigate_to_segment"):
            main_win.navigate_to_segment(seg_idx)
        self.accept()

    def _on_double_click(self, row, col):
        self._go_to_segment()


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


class SettingsDialog(QDialog):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("Options")
        self.setMinimumWidth(400)
        self.init_ui()

    def init_ui(self):
        layout = QFormLayout(self)

        self.src_font_spin = QSpinBox()
        self.src_font_spin.setRange(8, 30)
        self.src_font_spin.setValue(self.settings["source_font_size"])
        layout.addRow("Source font size:", self.src_font_spin)

        self.tgt_font_spin = QSpinBox()
        self.tgt_font_spin.setRange(8, 30)
        self.tgt_font_spin.setValue(self.settings["target_font_size"])
        layout.addRow("Target font size:", self.tgt_font_spin)

        self.auto_save_cb = QCheckBox()
        self.auto_save_cb.setChecked(self.settings["auto_save_on_segment_change"])
        layout.addRow("Auto-save on segment change:", self.auto_save_cb)

        self.show_tags_cb = QCheckBox()
        self.show_tags_cb.setChecked(self.settings["show_tag_placeholders"])
        layout.addRow("Show tag placeholders:", self.show_tags_cb)

        btn_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btn_box.accepted.connect(self._save)
        btn_box.rejected.connect(self.reject)
        layout.addRow(btn_box)

    def _save(self):
        self.settings["source_font_size"] = self.src_font_spin.value()
        self.settings["target_font_size"] = self.tgt_font_spin.value()
        self.settings["auto_save_on_segment_change"] = self.auto_save_cb.isChecked()
        self.settings["show_tag_placeholders"] = self.show_tags_cb.isChecked()
        self.settings.save()
        self.accept()


class TagViewDialog(QDialog):
    def __init__(self, segment, column, parent=None):
        super().__init__(parent)
        self.segment = segment
        self.column = column
        self.setWindowTitle("View Tags")
        self.setMinimumWidth(550)
        self.setMinimumHeight(350)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        if self.column == 0:
            label = QLabel("Source Text:")
            text = self.segment.get("source_clean", self.segment["source"])
        else:
            label = QLabel("Target Text:")
            text = self.segment.get("target_clean", self.segment["target"])
        layout.addWidget(label)

        self.text_edit = QTextEdit()
        self.text_edit.setPlainText(text)
        if self.column == 0:
            self.text_edit.setReadOnly(True)
        layout.addWidget(self.text_edit)

        tags = self.segment.get("all_tags", [])
        tags_label = QLabel(f"Tags ({len(tags)}):")
        layout.addWidget(tags_label)

        self.tag_list = QListWidget()
        if not tags:
            self.tag_list.addItem("(No tags in this segment)")
            self.tag_list.item(0).setFlags(Qt.NoItemFlags)
        else:
            for i, tag in enumerate(tags):
                text = f"{PH_L}{i}{PH_R}  =  {tag}" if self.column == 0 else f"{PH_L}{i}{PH_R}"
                item = QListWidgetItem(text)
                item.setData(Qt.UserRole, i)
                if self.column == 0:
                    item.setToolTip(tag)
                else:
                    item.setToolTip(f"Double-click to insert: {tag}")
                self.tag_list.addItem(item)

        if self.column == 1 and tags:
            self.tag_list.itemDoubleClicked.connect(self._insert_tag_from_list)

        layout.addWidget(self.tag_list)

        btn_layout = QHBoxLayout()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

    def _insert_tag_from_list(self, item):
        tag_idx = item.data(Qt.UserRole)
        if tag_idx is None:
            return
        cursor = self.text_edit.textCursor()
        ph = f"{PH_L}{tag_idx}{PH_R}"
        cursor.insertText(ph)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("mcat")
        self.resize(1100, 750)
        self.setStyleSheet(DARK_STYLESHEET)

        # Initialize backends
        data_dir = _get_data_dir()
        self.file_handler = CATFileHandler()
        self.tm = TranslationMemory(os.path.join(data_dir, "translation_memory.db"))
        self.glossary = Glossary(os.path.join(data_dir, "glossary.db"))
        self.project = None

        self.current_segment_index = -1
        self.modified = False
        self.segmentation_rules = [dict(r) for r in DEFAULT_RULES]

        self.settings = AppSettings().load()
        self._spellchecker = SpellChecker()
        self._spellchecker.auto_load()

        self.init_menu()
        self.init_ui()
        self._apply_settings()
        self.update_stats()

    def init_menu(self):
        menubar = self.menuBar()

        # File Menu
        file_menu = menubar.addMenu("&File")

        self.new_project_action = file_menu.addAction("&New Project...")
        self.new_project_action.setShortcut(QKeySequence("Ctrl+N"))
        self.new_project_action.triggered.connect(self.new_project)

        self.open_project_action = file_menu.addAction("&Open Project...")
        self.open_project_action.setShortcut(QKeySequence("Ctrl+Shift+O"))
        self.open_project_action.triggered.connect(self.open_project)

        self.save_project_action = file_menu.addAction("&Save Project")
        self.save_project_action.setShortcut(QKeySequence("Ctrl+Shift+S"))
        self.save_project_action.triggered.connect(self.save_project)

        self.save_project_as_action = file_menu.addAction("Save Project &As...")
        self.save_project_as_action.triggered.connect(self.save_project_as)

        self.close_project_action = file_menu.addAction("&Close Project")
        self.close_project_action.triggered.connect(self.close_project)

        file_menu.addSeparator()

        self.project_settings_action = file_menu.addAction("Project &Settings...")
        self.project_settings_action.triggered.connect(self.project_settings)

        file_menu.addSeparator()

        self.recent_menu = file_menu.addMenu("&Recent Projects")

        file_menu.addSeparator()

        import_menu = file_menu.addMenu("&Import Project")

        import_omegat_action = import_menu.addAction("Import Omega&T Project...")
        import_omegat_action.triggered.connect(self.import_omegat_project)

        import_menu.addSeparator()

        import_memoq_action = import_menu.addAction("Import &memoQ Project...")
        import_memoq_action.triggered.connect(self.import_memoq_project)

        import_menu.addSeparator()

        import_sdl_action = import_menu.addAction("Import &SDL Trados SDLXLIFF...")
        import_sdl_action.triggered.connect(self.import_sdlxliff)

        file_menu.addSeparator()

        open_action = file_menu.addAction("&Open File...")
        open_action.setShortcut(QKeySequence.Open)
        open_action.triggered.connect(self.open_file)

        save_action = file_menu.addAction("&Save File")
        save_action.setShortcut(QKeySequence.Save)
        save_action.triggered.connect(self.save_file)

        save_as_action = file_menu.addAction("Save File &As...")
        save_as_action.triggered.connect(self.save_file_as)

        file_menu.addSeparator()

        self.render_action = file_menu.addAction("&Render Translated File...")
        self.render_action.setShortcut(QKeySequence("Ctrl+R"))
        self.render_action.triggered.connect(self.render_translated_file)

        file_menu.addSeparator()
        exit_action = file_menu.addAction("E&xit")
        exit_action.triggered.connect(self.close)

        # Go / Navigation Menu
        go_menu = menubar.addMenu("&Go")

        self.next_seg_action = go_menu.addAction("&Next Segment")
        self.next_seg_action.setShortcut(QKeySequence("Ctrl+Down"))
        self.next_seg_action.triggered.connect(self._go_next_segment)

        self.prev_seg_action = go_menu.addAction("&Previous Segment")
        self.prev_seg_action.setShortcut(QKeySequence("Ctrl+Up"))
        self.prev_seg_action.triggered.connect(self._go_prev_segment)

        go_menu.addSeparator()

        self.next_untranslated_action = go_menu.addAction("Next &Untranslated")
        self.next_untranslated_action.setShortcut(QKeySequence("Ctrl+U"))
        self.next_untranslated_action.triggered.connect(self._go_next_untranslated)


        go_menu.addSeparator()

        self.toggle_fuzzy_action = go_menu.addAction("Toggle &Fuzzy")
        self.toggle_fuzzy_action.setShortcut(QKeySequence("Ctrl+F"))
        self.toggle_fuzzy_action.triggered.connect(self._toggle_fuzzy)

        go_menu.addSeparator()

        self.first_seg_action = go_menu.addAction("&First Segment")
        self.first_seg_action.setShortcut(QKeySequence("Ctrl+Home"))
        self.first_seg_action.triggered.connect(self._go_first_segment)

        self.last_seg_action = go_menu.addAction("&Last Segment")
        self.last_seg_action.setShortcut(QKeySequence("Ctrl+End"))
        self.last_seg_action.triggered.connect(self._go_last_segment)

        # TM Menu
        tm_menu = menubar.addMenu("&Translation Memory")
        import_tm_action = tm_menu.addAction("&Import PO into TM...")
        import_tm_action.setShortcut(QKeySequence("Ctrl+M"))
        import_tm_action.triggered.connect(self.import_po_to_tm)
        
        clear_tm_action = tm_menu.addAction("&Clear TM Database")
        clear_tm_action.triggered.connect(self.clear_tm)

        # Glossary Menu
        glossary_menu = menubar.addMenu("&Glossary")
        add_term_action = glossary_menu.addAction("&Add Term...")
        add_term_action.setShortcut(QKeySequence("Ctrl+G"))
        add_term_action.triggered.connect(self.add_glossary_term)

        view_all_action = glossary_menu.addAction("&View/Manage Glossary")
        view_all_action.setShortcut(QKeySequence("Ctrl+Shift+G"))
        view_all_action.triggered.connect(self.view_glossary)

        # Tools Menu
        tools_menu = menubar.addMenu("&Tools")
        seg_rules_action = tools_menu.addAction("&Segmentation Rules...")
        seg_rules_action.setShortcut(QKeySequence("Ctrl+Shift+T"))
        seg_rules_action.triggered.connect(self.open_segmentation_rules)

        tools_menu.addSeparator()

        self.qa_action = tools_menu.addAction("&Quality Assurance...")
        self.qa_action.setShortcut(QKeySequence("Ctrl+Shift+Q"))
        self.qa_action.triggered.connect(self.run_qa)

        tools_menu.addSeparator()
        self.import_dict_action = tools_menu.addAction("&Import Dictionary...")
        self.import_dict_action.triggered.connect(self.import_dictionary)

        tools_menu.addSeparator()
        self.spellcheck_action = tools_menu.addAction("&Spell Check...")
        self.spellcheck_action.setShortcut(QKeySequence("Ctrl+Shift+S"))
        self.spellcheck_action.triggered.connect(self.run_spellcheck)

        tools_menu.addSeparator()
        self.options_action = tools_menu.addAction("&Options...")
        self.options_action.setShortcut(QKeySequence("Ctrl+,"))
        self.options_action.triggered.connect(self.show_options)

        # Help Menu
        help_menu = menubar.addMenu("&Help")
        self.shortcuts_action = help_menu.addAction("&Keyboard Shortcuts...")
        self.shortcuts_action.setShortcuts(["F1", "Ctrl+Shift+H"])
        self.shortcuts_action.triggered.connect(self.show_shortcuts)

        help_menu.addSeparator()
        get_dicts_action = help_menu.addAction("&Get Dictionaries...")
        get_dicts_action.triggered.connect(self._open_dicts_page)

        self._update_recent_menu()

    def init_ui(self):
        main_splitter = QSplitter(Qt.Horizontal)

        # ----------------- LEFT PANEL: 2-Column Editable Table -----------------
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        self.table = QTableWidget()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["Source Segment", "Translation"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.itemSelectionChanged.connect(self.segment_selected)
        self.table.cellChanged.connect(self._on_target_cell_changed)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._table_context_menu)

        self.completion_delegate = CompletionDelegate(self.table, self.tm, self.glossary)
        self.table.setItemDelegateForColumn(1, self.completion_delegate)

        seg_label = QLabel("Segments")
        left_layout.addWidget(seg_label)
        left_layout.addWidget(self.table)

        # Bottom button bar
        btn_layout = QHBoxLayout()
        self.fuzzy_checkbox = QCheckBox("Fuzzy / Needs Review")
        self.fuzzy_checkbox.stateChanged.connect(self.fuzzy_state_changed)

        self.confirm_btn = QPushButton("Confirm & Next (Ctrl+Enter)")
        self.confirm_btn.clicked.connect(self.confirm_active_segment)
        self.confirm_btn.setShortcut(QKeySequence("Ctrl+Return"))

        btn_layout.addWidget(self.fuzzy_checkbox)
        btn_layout.addStretch()
        btn_layout.addWidget(self.confirm_btn)
        left_layout.addLayout(btn_layout)

        # ----------------- RIGHT PANEL: Sidebars -----------------
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)

        tm_label = QLabel("TM Fuzzy Matches (Double-click to apply)")
        right_layout.addWidget(tm_label)
        self.tm_list = QListWidget()
        self.tm_list.itemDoubleClicked.connect(self.apply_tm_suggestion)
        right_layout.addWidget(self.tm_list)

        glossary_label = QLabel("Detected Terminology / Glossary")
        right_layout.addWidget(glossary_label)
        self.glossary_table = QTableWidget()
        self.glossary_table.setColumnCount(2)
        self.glossary_table.setHorizontalHeaderLabels(["Source Term", "Translation"])
        self.glossary_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.glossary_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.glossary_table.setSelectionMode(QTableWidget.SingleSelection)
        self.glossary_table.itemDoubleClicked.connect(self.insert_glossary_term)
        right_layout.addWidget(self.glossary_table)

        main_splitter.addWidget(left_widget)
        main_splitter.addWidget(right_widget)
        main_splitter.setSizes([700, 350])

        self.setCentralWidget(main_splitter)

        # ----------------- STATUS BAR -----------------
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximumWidth(200)
        self.progress_bar.setValue(0)
        self.status_bar.addPermanentWidget(self.progress_bar)

        self.status_label = QLabel("Ready")
        self.status_bar.addWidget(self.status_label)

    # ----------------- FILE OPERATIONS -----------------
    def open_file(self):
        if self.modified:
            reply = QMessageBox.question(
                self, "Unsaved Changes",
                "You have unsaved changes. Open a new file anyway?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.No:
                return

        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open Translation File", "", FILE_FILTER
        )
        if not file_path:
            return

        try:
            segments = self.file_handler.load_file(file_path)
            self.populate_table(segments)
            self.modified = False
            self.update_stats()
            self.status_label.setText(f"Loaded file: {os.path.basename(file_path)}")
            
            # Select first segment
            if segments:
                self.table.selectRow(0)
        except Exception as e:
            QMessageBox.critical(self, "Error Loading File", str(e))

    def populate_table(self, segments):
        self.table.blockSignals(True)
        self.table.setRowCount(len(segments))
        for idx, seg in enumerate(segments):
            src_text = seg.get("source_clean", seg["source"])
            src_item = QTableWidgetItem(src_text)
            src_item.setFlags(src_item.flags() & ~Qt.ItemIsEditable)
            self.set_source_cell_style(src_item, seg)
            self.table.setItem(idx, 0, src_item)

            tgt_text = seg.get("target_clean", seg["target"])
            tgt_item = QTableWidgetItem(tgt_text)
            tgt_item.setFlags(tgt_item.flags() | Qt.ItemIsEditable)
            self.set_target_cell_style(tgt_item, seg)
            self.table.setItem(idx, 1, tgt_item)

        self.table.blockSignals(False)

        source_texts = [seg.get("source_clean", seg["source"]) for seg in segments]
        self.completion_delegate.set_source_texts(source_texts)

    def get_status_text(self, seg):
        if seg["fuzzy"]:
            return "Fuzzy"
        elif seg["target"] and seg["target"].strip():
            return "Translated"
        else:
            return "Untranslated"

    def set_source_cell_style(self, item, seg):
        if seg["fuzzy"]:
            item.setBackground(QColor("#3d2e00"))
            item.setForeground(QColor("#ff9800"))
        elif seg.get("translated", False) or (seg["target"] and seg["target"].strip()):
            item.setBackground(QColor("#002b00"))
            item.setForeground(QColor("#28a745"))
        else:
            item.setBackground(QColor("#1a1a1e"))
            item.setForeground(QColor("#a0a0a8"))

    def set_target_cell_style(self, item, seg):
        if seg["fuzzy"]:
            item.setBackground(QColor("#3d2e00"))
            item.setForeground(QColor("#ff9800"))
        elif seg.get("translated", False) or (seg["target"] and seg["target"].strip()):
            item.setBackground(QColor("#003300"))
            item.setForeground(QColor("#ffffff"))
        else:
            item.setBackground(QColor("#1a1a1e"))
            item.setForeground(QColor("#808080"))

    def _on_target_cell_changed(self, row, col):
        if col != 1:
            return
        seg = self.file_handler.segments[row]
        item = self.table.item(row, 1)
        if item is None:
            return

        new_text = item.text().strip()
        tags = seg.get("all_tags", [])
        restored = restore_tags(new_text, tags)

        if seg["target"] == restored:
            return

        seg["target"] = restored
        seg["translated"] = bool(restored)
        new_tgt_tags = extract_all_tags(restored)
        all_tags = list(tags)
        for t in new_tgt_tags:
            if t not in all_tags:
                all_tags.append(t)
        seg["all_tags"] = all_tags
        seg["target_clean"] = apply_tags(restored, all_tags)

        if restored:
            self.tm.add_translation(seg["source"], restored)

        item.setText(seg["target_clean"])
        self.set_target_cell_style(item, seg)
        self.set_source_cell_style(self.table.item(row, 0), seg)

        self.modified = True
        self.update_stats()

    def save_file(self):
        if not self.file_handler.current_file_path:
            self.save_file_as()
            return
        try:
            self.file_handler.save_file()
            self.modified = False
            self.status_label.setText(f"Saved: {os.path.basename(self.file_handler.current_file_path)}")
            QMessageBox.information(self, "Success", "File saved successfully.")
        except Exception as e:
            QMessageBox.critical(self, "Error Saving File", str(e))

    def save_file_as(self):
        file_path, selected_filter = QFileDialog.getSaveFileName(
            self, "Save Translation File As", "",
            "MCAT Project (*.mcat.db);;PO Files (*.po);;memoQ MQXLIFF (*.mqxliff);;SDL Trados SDLXLIFF (*.sdlxliff);;OmegaT Project folder;;All Files (*)"
        )
        if not file_path:
            return
        try:
            src_lang = self.project.source_lang if self.project else "en"
            tgt_lang = self.project.target_lang if self.project else "es"

            if "OmegaT" in selected_filter:
                dir_path = QFileDialog.getExistingDirectory(
                    self, "Select folder to create OmegaT project in",
                    os.path.dirname(file_path) if os.path.dirname(file_path) else ""
                )
                if not dir_path:
                    return
                target_dir = os.path.join(dir_path, os.path.splitext(os.path.basename(file_path))[0])
                p = self.project if self.project else Project()
                if not self.project:
                    p.new(os.path.basename(target_dir), src_lang, tgt_lang, [])
                p.save_as_omegat(target_dir)
                self.status_label.setText(f"OmegaT project saved: {target_dir}")
                QMessageBox.information(self, "Success",
                    f"Exported to OmegaT format:\n{target_dir}")
                return
            elif "MCAT" in selected_filter:
                if not file_path.lower().endswith(".mcat.db"):
                    file_path += ".mcat.db"
                self.file_handler.save_file(file_path)
            elif "MQXLIFF" in selected_filter:
                if not file_path.endswith(".mqxliff"):
                    file_path += ".mqxliff"
                self.file_handler.save_as_mqxliif(file_path, src_lang, tgt_lang)
            elif "SDLXLIFF" in selected_filter:
                if not file_path.endswith(".sdlxliff"):
                    file_path += ".sdlxliff"
                from cat_tool.formats.sdlxliff import SdlxliffHandler
                SdlxliffHandler().save(self.file_handler.segments, file_path, src_lang, tgt_lang)
                self.file_handler.current_file_path = file_path
            else:
                self.file_handler.save_file(file_path)
            self.modified = False
            self.status_label.setText(f"Saved: {os.path.basename(file_path)}")
            QMessageBox.information(self, "Success", "File saved successfully.")
        except Exception as e:
            QMessageBox.critical(self, "Error Saving File", str(e))

    # ----------------- RENDER TRANSLATED -----------------
    def render_translated_file(self):
        if not self.file_handler.segments:
            QMessageBox.warning(self, "No Data", "No file loaded. Open a file first.")
            return
        ext = os.path.splitext(self.file_handler.current_file_path or "")[1].lower()
        ext_filter = f"Translated {ext.upper()} (*{ext})" if ext else "All Files (*)"
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Translated File As", f"translated{ext}", ext_filter
        )
        if not file_path:
            return
        try:
            self.file_handler.render_translated(file_path)
            self.status_label.setText(f"Rendered: {os.path.basename(file_path)}")
            QMessageBox.information(self, "Success", f"Translated file saved:\n{file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Render Error", str(e))

    # ----------------- SELECTION & CONFIRMATION -----------------
    def segment_selected(self):
        row = self.table.currentRow()
        if row < 0:
            return

        self.current_segment_index = row
        seg = self.file_handler.segments[row]

        self.fuzzy_checkbox.blockSignals(True)
        self.fuzzy_checkbox.setChecked(seg["fuzzy"])
        self.fuzzy_checkbox.blockSignals(False)

        self.update_fuzzy_matches(seg["source"])
        self.update_glossary_matches(seg["source"])

    def fuzzy_state_changed(self, state):
        if self.current_segment_index < 0:
            return
        seg = self.file_handler.segments[self.current_segment_index]
        seg["fuzzy"] = (state == Qt.Checked)
        self.modified = True
        
        # Update table status cell
        self.update_table_row_status(self.current_segment_index, seg)
        self.update_stats()

    def update_table_row_status(self, row, seg):
        self.table.blockSignals(True)
        item = self.table.item(row, 1)
        if item:
            item.setText(seg.get("target_clean", seg["target"]))
            self.set_target_cell_style(item, seg)
        src_item = self.table.item(row, 0)
        if src_item:
            self.set_source_cell_style(src_item, seg)
        self.table.blockSignals(False)

    def confirm_active_segment(self):
        if self.current_segment_index < 0:
            return

        row = self.current_segment_index
        item = self.table.item(row, 1)
        cell_text = item.text().strip() if item else ""

        seg = self.file_handler.segments[row]
        tags = seg.get("all_tags", [])
        restored = restore_tags(cell_text, tags)
        if seg["target"] == restored and seg["translated"] == bool(restored):
            pass
        else:
            seg["target"] = restored
            seg["translated"] = bool(restored)
            new_tgt_tags = extract_all_tags(restored)
            all_tags = list(tags)
            for t in new_tgt_tags:
                if t not in all_tags:
                    all_tags.append(t)
            seg["all_tags"] = all_tags
            seg["target_clean"] = apply_tags(restored, all_tags)
            if restored:
                self.tm.add_translation(seg["source"], restored)

            self.modified = True
            if item:
                item.setText(seg["target_clean"])
            self.update_table_row_status(row, seg)

        self.update_stats()

        if self.modified and self.file_handler.current_file_path:
            try:
                self.file_handler.save_file()
                self.modified = False
            except Exception as e:
                self.status_label.setText(f"Auto-save failed: {e}")

        if row < len(self.file_handler.segments) - 1:
            self.table.selectRow(row + 1)
            self._edit_target_cell(row + 1)
        else:
            self.status_label.setText("Reached the end of the file!")

    # ----------------- SEGMENT NAVIGATION -----------------
    def _edit_target_cell(self, row):
        idx = self.table.model().index(row, 1)
        self.table.edit(idx)

    def _go_next_segment(self):
        if not self.file_handler.segments:
            return
        next_idx = self.current_segment_index + 1
        if next_idx < len(self.file_handler.segments):
            self.table.selectRow(next_idx)
            self._edit_target_cell(next_idx)
        else:
            self.status_label.setText("Already at the last segment.")

    def _go_prev_segment(self):
        if not self.file_handler.segments:
            return
        prev_idx = self.current_segment_index - 1
        if prev_idx >= 0:
            self.table.selectRow(prev_idx)
            self._edit_target_cell(prev_idx)
        else:
            self.status_label.setText("Already at the first segment.")

    def _go_next_untranslated(self):
        if not self.file_handler.segments:
            return
        start = self.current_segment_index + 1
        for i in range(start, len(self.file_handler.segments)):
            seg = self.file_handler.segments[i]
            if not seg.get("translated", False) or not seg.get("target", "").strip():
                self.table.selectRow(i)
                self._edit_target_cell(i)
                return
        self.status_label.setText("No more untranslated segments.")

    # ----------------- CONTEXT MENU -----------------
    def _table_context_menu(self, pos):
        index = self.table.indexAt(pos)
        if not index.isValid():
            return
        row = index.row()
        col = index.column()
        if row < 0 or row >= len(self.file_handler.segments):
            return
        seg = self.file_handler.segments[row]
        self.table.selectRow(row)

        menu = QMenu(self)
        view_action = menu.addAction("View Tags")
        if col == 0:
            view_action.triggered.connect(lambda: TagViewDialog(seg, 0, self).exec_())
        else:
            view_action.triggered.connect(lambda: self._show_tag_dialog_for_target(seg))
        menu.addSeparator()
        spell_action = menu.addAction("Spell Check Segment")
        spell_action.triggered.connect(lambda: self._spellcheck_segment(seg))
        menu.exec_(self.table.viewport().mapToGlobal(pos))

    def _show_tag_dialog_for_target(self, seg):
        dlg = TagViewDialog(seg, 1, self)
        if dlg.exec_() == QDialog.Accepted:
            new_text = dlg.text_edit.toPlainText().strip()
            if self.current_segment_index >= 0:
                item = self.table.item(self.current_segment_index, 1)
                if item and new_text != item.text():
                    item.setText(new_text)

    def _spellcheck_segment(self, seg):
        dlg = SpellCheckDialog([seg], self._spellchecker, self)
        dlg.exec_()
        self.populate_table(self.file_handler.segments)

    def show_options(self):
        dlg = SettingsDialog(self.settings, self)
        if dlg.exec_() == QDialog.Accepted:
            self._apply_settings()

    def _apply_settings(self):
        font = self.table.font()
        font.setPointSize(self.settings["source_font_size"])
        self.table.horizontalHeaderItem(0).setFont(font) if self.table.horizontalHeaderItem(0) else None
        if self.settings["source_font_size"] != self.settings["target_font_size"]:
            tgt_font = QFont(font)
            tgt_font.setPointSize(self.settings["target_font_size"])
            self.table.horizontalHeaderItem(1).setFont(tgt_font) if self.table.horizontalHeaderItem(1) else None
        self.table.setFont(font)

    # ----------------- SIDEBAR SUGGESTIONS & INTERACTIONS -----------------
    def update_fuzzy_matches(self, source_text):
        self.tm_list.clear()
        matches = self.tm.get_fuzzy_matches(source_text, min_score=40.0)
        
        for m in matches:
            item = QListWidgetItem(f"[{m['score']}% Match] {m['target']}\n(From: \"{m['source']}\")")
            item.setData(Qt.UserRole, m["target"])
            self.tm_list.addItem(item)

    def apply_tm_suggestion(self, item):
        target_suggestion = item.data(Qt.UserRole)
        if target_suggestion and self.current_segment_index >= 0:
            tgt_item = self.table.item(self.current_segment_index, 1)
            if tgt_item:
                tgt_item.setText(target_suggestion)
                self._edit_target_cell(self.current_segment_index)

    def update_glossary_matches(self, source_text):
        self.glossary_table.setRowCount(0)
        matches = self.glossary.check_segment(source_text)
        
        self.glossary_table.setRowCount(len(matches))
        for idx, m in enumerate(matches):
            src_item = QTableWidgetItem(m["source"])
            tgt_item = QTableWidgetItem(m["target"])
            
            src_item.setFlags(src_item.flags() & ~Qt.ItemIsEditable)
            tgt_item.setFlags(tgt_item.flags() & ~Qt.ItemIsEditable)

            # Tooltip shows details/description
            if m["description"]:
                src_item.setToolTip(m["description"])
                tgt_item.setToolTip(m["description"])

            self.glossary_table.setItem(idx, 0, src_item)
            self.glossary_table.setItem(idx, 1, tgt_item)

    def insert_glossary_term(self, item):
        glossary_row = item.row()
        term_item = self.glossary_table.item(glossary_row, 1)
        if not term_item or self.current_segment_index < 0:
            return
        tgt_item = self.table.item(self.current_segment_index, 1)
        if tgt_item:
            current = tgt_item.text()
            tgt_item.setText(current + term_item.text())
            self._edit_target_cell(self.current_segment_index)

    # ----------------- GLOSSARY MANAGEMENT -----------------
    def add_glossary_term(self):
        dial = GlossaryDialog(self)
        if dial.exec_() == QDialog.Accepted:
            src, tgt, desc = dial.get_data()
            if src and tgt:
                self.glossary.add_term(src, tgt, desc)
                self.status_label.setText(f"Added glossary term: '{src}'")
                # Refresh matches if we have an active segment
                if self.current_segment_index >= 0:
                    seg = self.file_handler.segments[self.current_segment_index]
                    self.update_glossary_matches(seg["source"])
            else:
                QMessageBox.warning(self, "Invalid Input", "Source and Target cannot be empty.")

    def view_glossary(self):
        terms = self.glossary.get_all_terms()
        # Display simple scrollable list dialog
        dialog = QDialog(self)
        dialog.setWindowTitle("Glossary Terms List")
        dialog.setMinimumSize(500, 400)
        
        layout = QVBoxLayout(dialog)
        tbl = QTableWidget()
        tbl.setColumnCount(3)
        tbl.setHorizontalHeaderLabels(["Source Term", "Target Translation", "Description"])
        tbl.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        tbl.setRowCount(len(terms))
        
        for idx, t in enumerate(terms):
            tbl.setItem(idx, 0, QTableWidgetItem(t["source"]))
            tbl.setItem(idx, 1, QTableWidgetItem(t["target"]))
            tbl.setItem(idx, 2, QTableWidgetItem(t["description"]))

        layout.addWidget(tbl)
        
        # Add delete button
        btn_layout = QHBoxLayout()
        del_btn = QPushButton("Delete Selected", dialog)
        
        def delete_selected():
            selected_items = tbl.selectedItems()
            if not selected_items:
                return
            row = selected_items[0].row()
            src = tbl.item(row, 0).text()
            self.glossary.remove_term(src)
            tbl.removeRow(row)
            self.status_label.setText(f"Deleted term: '{src}'")
            if self.current_segment_index >= 0:
                seg = self.file_handler.segments[self.current_segment_index]
                self.update_glossary_matches(seg["source"])

        del_btn.clicked.connect(delete_selected)
        btn_layout.addWidget(del_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        dialog.exec_()

    # ----------------- TM MANAGEMENT -----------------
    def import_po_to_tm(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Import PO for Translation Memory", "", "PO Files (*.po);;All Files (*)"
        )
        if not file_path:
            return
        try:
            handler = CATFileHandler()
            segments = handler.load_file(file_path)
            imported_count = 0
            for seg in segments:
                if seg["target"] and seg["target"].strip() and not seg["fuzzy"]:
                    self.tm.add_translation(seg["source"], seg["target"])
                    imported_count += 1
            
            QMessageBox.information(
                self, "Success", f"Imported {imported_count} translations into translation memory."
            )
            # Refresh matching if active
            if self.current_segment_index >= 0:
                seg = self.file_handler.segments[self.current_segment_index]
                self.update_fuzzy_matches(seg["source"])
        except Exception as e:
            QMessageBox.critical(self, "Import Error", str(e))

    def clear_tm(self):
        reply = QMessageBox.question(
            self, "Confirm Delete", "Are you sure you want to clear the entire Translation Memory?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.tm.clear()
            self.status_label.setText("Translation Memory cleared.")
            if self.current_segment_index >= 0:
                seg = self.file_handler.segments[self.current_segment_index]
                self.update_fuzzy_matches(seg["source"])

    def _toggle_fuzzy(self):
        if self.current_segment_index >= 0:
            self.fuzzy_checkbox.toggle()

    def _go_first_segment(self):
        if self.file_handler.segments:
            self.table.selectRow(0)
            self._edit_target_cell(0)

    def _go_last_segment(self):
        if self.file_handler.segments:
            last = len(self.file_handler.segments) - 1
            self.table.selectRow(last)
            self._edit_target_cell(last)

    def show_shortcuts(self):
        dlg = ShortcutsDialog(self)
        dlg.exec_()

    def _open_dicts_page(self):
        import webbrowser
        webbrowser.open("https://extensions.libreoffice.org/en?Tags%5B%5D=50")

    def navigate_to_segment(self, segment_index):
        if 0 <= segment_index < len(self.file_handler.segments):
            self.table.selectRow(segment_index)
            self._edit_target_cell(segment_index)

    def run_qa(self):
        if not self.file_handler.segments:
            QMessageBox.warning(self, "No Data", "Open a file first before running QA.")
            return
        issues = qa.run_all_checks(self.file_handler.segments, glossary=self.glossary)
        dlg = QADialog(issues, self)
        dlg.exec_()

    def import_dictionary(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Import Dictionary", "",
            "Dictionary (*.oxt *.zip *.dic);;All Files (*)"
        )
        if not path:
            return
        if path.endswith(".dic"):
            ok = self._spellchecker.load_dictionary(path)
        else:
            ok = self._spellchecker.load_from_archive(path)
        if ok:
            names = self._spellchecker.loaded_names
            QMessageBox.information(
                self, "Success",
                f"Dictionary imported.\nLoaded: {', '.join(names)}"
            )
        else:
            QMessageBox.warning(self, "Error", "Failed to load dictionary.\n\n"
                                "Make sure the file contains valid .dic/.aff files.")

    def _load_spelling_dict_for_language(self, lang_code):
        if not lang_code:
            return
        from cat_tool.spellcheck import DICTS_DIR
        code = lang_code.lower()
        found = None
        if os.path.isdir(DICTS_DIR):
            for name in os.listdir(DICTS_DIR):
                if name.lower().startswith(code):
                    found = name
                    break
        if found:
            if found not in self._spellchecker.loaded_names:
                path = os.path.join(DICTS_DIR, found)
                for f in os.listdir(path):
                    if f.endswith(".dic"):
                        base = os.path.join(path, os.path.splitext(f)[0])
                        try:
                            from spylls.hunspell import Dictionary
                            d = Dictionary.from_files(base)
                            self._spellchecker.dictionaries.append(d)
                            self._spellchecker._loaded_names.append(found)
                        except Exception:
                            pass
                        break
                self.status_label.setText(
                    f"Loaded spelling dictionary: {found}"
                )
        else:
            self.status_label.setText(
                f"No spelling dictionary found for '{lang_code}'. "
                f"Use Tools > Import Dictionary to add one."
            )

    def run_spellcheck(self):
        if not self.file_handler.segments:
            QMessageBox.warning(self, "No Data", "Open a file first before spell check.")
            return
        dlg = SpellCheckDialog(self.file_handler.segments, self._spellchecker, self)
        dlg.exec_()
        self.populate_table(self.file_handler.segments)

    # ----------------- STATS UPDATE -----------------
    def update_stats(self):
        if not self.file_handler.segments:
            self.progress_bar.setValue(0)
            self.progress_bar.setFormat("No file loaded")
            return

        total = len(self.file_handler.segments)
        translated = 0
        fuzzy = 0

        for seg in self.file_handler.segments:
            if seg["fuzzy"]:
                fuzzy += 1
            elif seg["target"] and seg["target"].strip():
                translated += 1

        percent = int((translated / total) * 100) if total > 0 else 0
        self.progress_bar.setValue(percent)
        self.progress_bar.setFormat(f"%p% ({translated}/{total})")
        
        proj_name = self.project.name if self.project else "No Project"
        self.status_label.setText(
            f"[{proj_name}] "
            f"Active File: {os.path.basename(self.file_handler.current_file_path or 'None')} | "
            f"Translated: {translated} | Fuzzy: {fuzzy} | Total: {total}"
        )
        title = f"mcat - {proj_name}"
        if self.file_handler.current_file_path:
            title += f" [{os.path.basename(self.file_handler.current_file_path)}]"
        self.setWindowTitle(title)

    # ----------------- PROJECT OPERATIONS -----------------

    def close_project(self):
        if not self.project:
            return
        if self.modified:
            reply = QMessageBox.question(
                self, "Unsaved Changes",
                "You have unsaved changes. Save before closing?",
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel
            )
            if reply == QMessageBox.Cancel:
                return
            if reply == QMessageBox.Yes:
                self.save_project()

        proj_name = self.project.name
        self.project = None
        self.file_handler = CATFileHandler()
        self.current_segment_index = -1
        self.modified = False
        self.table.setRowCount(0)
        self.tm_list.clear()
        self.glossary_table.setRowCount(0)
        self.status_label.setText(f"Project closed: {proj_name}")

    def new_project(self):
        if self.modified:
            reply = QMessageBox.question(
                self, "Unsaved Changes",
                "You have unsaved changes. Start a new project anyway?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.No:
                return

        dial = NewProjectDialog(self)
        if dial.exec_() != QDialog.Accepted:
            return

        name, src_lang, tgt_lang, src_files = dial.get_data()
        if not name:
            QMessageBox.warning(self, "Invalid", "Project name cannot be empty.")
            return

        self.project = Project()
        self.project.new(name, src_lang, tgt_lang, src_files)
        self.file_handler = CATFileHandler()
        self.current_segment_index = -1
        self.modified = False

        if src_files:
            self._open_project_source_file(0)
        else:
            self.table.setRowCount(0)

        self.update_stats()
        self._load_spelling_dict_for_language(tgt_lang)
        self.status_label.setText(f"Created project: {name}")

    def open_project(self):
        if self.modified:
            reply = QMessageBox.question(
                self, "Unsaved Changes",
                "You have unsaved changes. Open a different project anyway?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.No:
                return

        filter_str = "CAT Project (*.mcatproj);;OmegaT Project (folder with omegat.project);;memoQ Project (folder with manifest.xml)"
        file_path, selected_filter = QFileDialog.getOpenFileName(
            self, "Open Project", "", filter_str
        )
        if not file_path:
            return

        if "OmegaT" in selected_filter:
            dir_path = QFileDialog.getExistingDirectory(
                self, "Select OmegaT Project Folder (contains omegat.project)"
            )
            if not dir_path:
                return
            proj_file = os.path.join(dir_path, "omegat.project")
            if not os.path.exists(proj_file):
                QMessageBox.warning(self, "Invalid Project",
                                    "Selected folder does not contain omegat.project")
                return
            self._load_omegat(dir_path)
        elif "memoQ" in selected_filter:
            dir_path = QFileDialog.getExistingDirectory(
                self, "Select memoQ Project Folder (contains manifest.xml)"
            )
            if not dir_path:
                return
            manifest_file = os.path.join(dir_path, "manifest.xml")
            if not os.path.exists(manifest_file):
                QMessageBox.warning(self, "Invalid Project",
                                    "Selected folder does not contain manifest.xml")
                return
            self._load_memoq(dir_path)
        else:
            self._load_project(file_path)

    def _load_project(self, file_path):
        try:
            self.project = Project.load(file_path)
            self.file_handler = CATFileHandler()
            self.current_segment_index = -1
            self.modified = False

            if self.project.source_files:
                self._open_project_source_file(0)
            else:
                self.table.setRowCount(0)

            Project.add_recent(file_path, self.project.name)
            self._update_recent_menu()
            self.update_stats()
            self._load_spelling_dict_for_language(self.project.target_lang)
            self.status_label.setText(f"Opened project: {self.project.name}")
        except Exception as e:
            QMessageBox.critical(self, "Error Opening Project", str(e))

    def _load_omegat(self, dir_path):
        try:
            self.project = Project.load_omegat(dir_path)
            self.file_handler = CATFileHandler()
            self.current_segment_index = -1
            self.modified = False

            if self.project.source_files:
                self._open_project_source_file(0)
            else:
                self.table.setRowCount(0)

            Project.add_recent(dir_path, self.project.name)
            self._update_recent_menu()
            self.update_stats()
            self._load_spelling_dict_for_language(self.project.target_lang)
            self.status_label.setText(f"Opened OmegaT project: {self.project.name}")
        except Exception as e:
            QMessageBox.critical(self, "Error Opening Project", str(e))

    def project_settings(self):
        if not self.project:
            QMessageBox.information(self, "No Project", "No project is currently open.")
            return

        dial = ProjectSettingsDialog(self.project, self)
        if dial.exec_() != QDialog.Accepted:
            return

        dial.apply()
        self.modified = True
        self.update_stats()
        self._load_spelling_dict_for_language(self.project.target_lang)
        self.status_label.setText("Project settings updated.")

    def _open_project_source_file(self, index):
        if not self.project or index >= len(self.project.source_files):
            return
        file_path = self.project.source_files[index]
        if not os.path.exists(file_path):
            QMessageBox.warning(self, "File Not Found", f"Source file not found:\n{file_path}")
            return

        ext = os.path.splitext(file_path)[1].lower()
        is_po = ext in (".po", ".pot")
        try:
            if is_po:
                self.file_handler.load_file(file_path)
            else:
                po_path = file_path + ".po"
                convert_to_po(file_path, po_path)
                self.file_handler.load_file(po_path)

            self.populate_table(self.file_handler.segments)
            if self.file_handler.segments:
                self.table.selectRow(0)
            self.update_stats()
            label = os.path.basename(file_path)
            if not is_po:
                label += "  (auto-converted to PO)"
            self.status_label.setText(f"Loaded: {label}")
        except Exception as e:
            QMessageBox.critical(self, "Error Loading Source File", str(e))

    def save_project(self):
        if not self.project:
            QMessageBox.information(self, "No Project", "No project is currently open.")
            return
        if not self.project.file_path:
            self.save_project_as()
            return
        try:
            self.project.save()
            self.modified = False
            Project.add_recent(self.project.file_path, self.project.name)
            self._update_recent_menu()
            self.update_stats()
            self.status_label.setText(f"Project saved: {self.project.name}")
        except Exception as e:
            QMessageBox.critical(self, "Error Saving Project", str(e))

    def save_project_as(self):
        if not self.project:
            QMessageBox.information(self, "No Project", "No project is currently open.")
            return
        filter_str = "CAT Project (*.mcatproj);;OmegaT Project folder;;memoQ Project folder"
        file_path, selected_filter = QFileDialog.getSaveFileName(
            self, "Save Project As", f"{self.project.name}.mcatproj", filter_str
        )
        if not file_path:
            return

        if "OmegaT" in selected_filter:
            dir_path = QFileDialog.getExistingDirectory(
                self, "Select folder to create OmegaT project in",
                os.path.dirname(file_path) if os.path.dirname(file_path) else ""
            )
            if not dir_path:
                return
            target_dir = os.path.join(dir_path, self.project.name)
            try:
                self.project.save_as_omegat(target_dir)
                self.modified = False
                self.project.file_path = target_dir
                Project.add_recent(target_dir, self.project.name)
                self._update_recent_menu()
                self.update_stats()
                self.status_label.setText(
                    f"OmegaT project saved: {target_dir}"
                )
                QMessageBox.information(
                    self, "Success",
                    f"Project exported to OmegaT format:\n{target_dir}\n\n"
                    f"Source files copied to '{target_dir}\\source\\'.\n"
                    f"You can open this folder directly in OmegaT."
                )
            except Exception as e:
                QMessageBox.critical(self, "Export Error", str(e))
        elif "memoQ" in selected_filter:
            dir_path = QFileDialog.getExistingDirectory(
                self, "Select folder to create memoQ project in",
                os.path.dirname(file_path) if os.path.dirname(file_path) else ""
            )
            if not dir_path:
                return
            target_dir = os.path.join(dir_path, self.project.name)
            try:
                self.project.save_as_memoq(target_dir, self.file_handler)
                self.modified = False
                self.project.file_path = target_dir
                Project.add_recent(target_dir, self.project.name)
                self._update_recent_menu()
                self.update_stats()
                self.status_label.setText(
                    f"memoQ project saved: {target_dir}"
                )
                QMessageBox.information(
                    self, "Success",
                    f"Project exported to memoQ format:\n{target_dir}\n\n"
                    f"Source files copied to '{target_dir}\\source\\'.\n"
                    f"Translations saved as MQXLIFF in '{target_dir}\\target\\'.\n"
                    f"You can open the .mqxliff file directly in memoQ."
                )
            except Exception as e:
                QMessageBox.critical(self, "Export Error", str(e))
        else:
            if not file_path.endswith(".mcatproj"):
                file_path += ".mcatproj"
            try:
                self.project.save(file_path)
                self.modified = False
                Project.add_recent(file_path, self.project.name)
                self._update_recent_menu()
                self.update_stats()
                self.status_label.setText(f"Project saved: {self.project.name}")
            except Exception as e:
                QMessageBox.critical(self, "Error Saving Project", str(e))

    def open_segmentation_rules(self):
        dlg = AdvancedRulesDialog(self, self.segmentation_rules)
        if dlg.exec_() == QDialog.Accepted:
            self.segmentation_rules = dlg.get_rules()
            self.status_label.setText(
                f"Segmentation rules updated ({len(self.segmentation_rules)} rules)"
            )

    def import_omegat_project(self):
        dir_path = QFileDialog.getExistingDirectory(
            self, "Select OmegaT Project Folder (contains omegat.project)"
        )
        if not dir_path:
            return
        proj_file = os.path.join(dir_path, "omegat.project")
        if not os.path.exists(proj_file):
            QMessageBox.warning(self, "Invalid Project",
                                "Selected folder does not contain omegat.project")
            return
        try:
            self.project = Project.load_omegat(dir_path)
            self.file_handler = CATFileHandler()
            self.current_segment_index = -1
            self.modified = False
            if self.project.source_files:
                self._open_project_source_file(0)
            else:
                self.table.setRowCount(0)
            Project.add_recent(dir_path, self.project.name)
            self._update_recent_menu()
            self.update_stats()
            self.status_label.setText(f"Imported OmegaT project: {self.project.name}")
        except Exception as e:
            QMessageBox.critical(self, "Import Error", str(e))

    def export_omegat_project(self):
        if not self.project:
            QMessageBox.information(self, "No Project", "No project is currently open.")
            return
        dir_path = QFileDialog.getExistingDirectory(
            self, "Select folder to export OmegaT project into"
        )
        if not dir_path:
            return
        target_dir = os.path.join(dir_path, self.project.name)
        try:
            self.project.save_as_omegat(target_dir)
            QMessageBox.information(
                self, "Success",
                f"OmegaT project exported to:\n{target_dir}\n\n"
                f"Source files copied to '{target_dir}\\source\\'.\n"
                f"Open the folder in OmegaT to translate."
            )
            self.status_label.setText(f"Exported OmegaT project: {target_dir}")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", str(e))

    # ----------------- MEMOQ PROJECTS -----------------
    def import_memoq_project(self):
        dir_path = QFileDialog.getExistingDirectory(
            self, "Select memoQ Project Folder (contains manifest.xml)"
        )
        if not dir_path:
            return
        manifest_file = os.path.join(dir_path, "manifest.xml")
        if not os.path.exists(manifest_file):
            QMessageBox.warning(self, "Invalid Project",
                                "Selected folder does not contain manifest.xml")
            return
        self._load_memoq(dir_path)

    def export_memoq_project(self):
        if not self.project:
            QMessageBox.information(self, "No Project", "No project is currently open.")
            return
        dir_path = QFileDialog.getExistingDirectory(
            self, "Select folder to export memoQ project into"
        )
        if not dir_path:
            return
        target_dir = os.path.join(dir_path, self.project.name)
        try:
            self.project.save_as_memoq(target_dir, self.file_handler)
            QMessageBox.information(
                self, "Success",
                f"memoQ project exported to:\n{target_dir}\n\n"
                f"Source files copied to '{target_dir}\\source\\'.\n"
                f"Translations saved as MQXLIFF in '{target_dir}\\target\\'."
            )
            self.status_label.setText(f"Exported memoQ project: {target_dir}")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", str(e))

    def _load_memoq(self, dir_path):
        try:
            self.project = Project.load_memoq(dir_path)
            self.file_handler = CATFileHandler()
            self.current_segment_index = -1
            self.modified = False

            if self.project.mqxliff_files:
                self.file_handler.load_file(self.project.mqxliff_files[0])
                self.populate_table(self.file_handler.segments)
                if self.file_handler.segments:
                    self.table.selectRow(0)
            elif self.project.source_files:
                self._open_project_source_file(0)
            else:
                self.table.setRowCount(0)

            Project.add_recent(dir_path, self.project.name)
            self._update_recent_menu()
            self.update_stats()
            self._load_spelling_dict_for_language(self.project.target_lang)
            self.status_label.setText(f"Opened memoQ project: {self.project.name}")
        except Exception as e:
            QMessageBox.critical(self, "Error Opening memoQ Project", str(e))

    # ----------------- SDL TRADOS -----------------
    def import_sdlxliff(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open SDL Trados SDLXLIFF", "", "SDLXLIFF (*.sdlxliff);;All Files (*)"
        )
        if not file_path:
            return
        try:
            segs = self.file_handler.load_file(file_path)
            self.populate_table(segs)
            self.modified = False
            self.update_stats()
            self.status_label.setText(f"Loaded SDLXLIFF: {os.path.basename(file_path)}")
            if segs:
                self.table.selectRow(0)
        except Exception as e:
            QMessageBox.critical(self, "Error Loading SDLXLIFF", str(e))

    def export_sdlxliff(self):
        if not self.file_handler.segments:
            QMessageBox.information(self, "Nothing to Export", "No file loaded to export.")
            return
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export as SDL Trados SDLXLIFF", "", "SDLXLIFF (*.sdlxliff);;All Files (*)"
        )
        if not file_path:
            return
        if not file_path.endswith(".sdlxliff"):
            file_path += ".sdlxliff"
        try:
            src_lang = self.project.source_lang if self.project else "en"
            tgt_lang = self.project.target_lang if self.project else "es"
            from cat_tool.formats.sdlxliff import SdlxliffHandler
            SdlxliffHandler().save(self.file_handler.segments, file_path, src_lang, tgt_lang)
            self.status_label.setText(f"Exported SDLXLIFF: {os.path.basename(file_path)}")
            QMessageBox.information(self, "Success", f"Exported to SDLXLIFF:\n{file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", str(e))

    def _update_recent_menu(self):
        self.recent_menu.clear()
        recents = Project.get_recent()
        if not recents:
            action = self.recent_menu.addAction("(No recent projects)")
            action.setEnabled(False)
            return
        for r in recents:
            path = r.get("path", "")
            name = r.get("name", os.path.basename(path))
            action = self.recent_menu.addAction(f"{name}  [{os.path.basename(os.path.dirname(path))}]")
            action.setData(path)
            action.triggered.connect(lambda checked, p=path: self._load_project(p))
