from PyQt5.QtWidgets import QStyledItemDelegate, QLineEdit, QCompleter, QListView
from PyQt5.QtCore import QStringListModel
from PyQt5.QtCore import Qt, QTimer


VSCODE_POPUP = """
QListView {
    background-color: #252526;
    border: 1px solid #3c3c3c;
    outline: none;
    padding: 2px;
    font-family: "Segoe UI", Consolas, "Courier New", monospace;
    font-size: 12px;
    color: #d4d4d4;
}
QListView::item {
    padding: 4px 8px;
    min-height: 20px;
    border: none;
}
QListView::item:selected {
    background-color: #094771;
    color: white;
}
QListView::item:hover {
    background-color: #2a2d2e;
}
"""


class CompletionDelegate(QStyledItemDelegate):
    def __init__(self, parent, tm, glossary):
        super().__init__(parent)
        self.tm = tm
        self.glossary = glossary
        self._source_texts = []

    def set_source_texts(self, texts):
        self._source_texts = texts

    def createEditor(self, parent, option, index):
        editor = QLineEdit(parent)
        editor.setStyleSheet("font-size: 14px; padding: 2px;")
        completer = QCompleter()
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        completer.setFilterMode(Qt.MatchContains)

        popup = QListView()
        popup.setStyleSheet(VSCODE_POPUP)
        popup.setWindowFlags(Qt.ToolTip)
        popup.setFocusPolicy(Qt.StrongFocus)
        completer.setPopup(popup)
        completer.setMaxVisibleItems(12)
        editor.setCompleter(completer)

        source_text = ""
        row = index.row()
        if row < len(self._source_texts):
            source_text = self._source_texts[row]

        debounce = QTimer(editor)
        debounce.setSingleShot(True)
        debounce.setInterval(180)

        def update_model(current_text=None):
            suggestions = []
            if source_text:
                tm_matches = self.tm.get_fuzzy_matches(source_text, min_score=40) if self.tm else []
                for m in tm_matches:
                    target = m.get("target", "")
                    score = m.get("score", 0)
                    if not current_text or current_text.lower() in target.lower():
                        suggestions.append(target)

            if self.glossary:
                gl_terms = self.glossary.get_all_terms() if hasattr(self.glossary, 'get_all_terms') else []
                for term in gl_terms:
                    target = term.get("target", "")
                    src = term.get("source", "")
                    if not current_text or current_text.lower() in target.lower():
                        entry = f"{target}"
                        if entry not in suggestions:
                            suggestions.append(entry)

            model = QStringListModel(suggestions[:20])
            completer.setModel(model)
            if suggestions:
                completer.complete()

        def on_text_changed(text):
            debounce.stop()
            if text:
                debounce.start()
            else:
                update_model(text)

        def on_typing():
            update_model(editor.text())

        debounce.timeout.connect(on_typing)
        editor.textChanged.connect(on_text_changed)

        QTimer.singleShot(50, lambda: update_model())

        return editor

    def setModelData(self, editor, model, index):
        text = editor.text()
        model.setData(index, text, Qt.EditRole)
