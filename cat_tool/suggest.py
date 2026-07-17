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
    def __init__(self, parent, tm, glossary, spellcheck=None, settings=None, source_lang=None, target_lang=None):
        super().__init__(parent)
        self.tm = tm
        self.glossary = glossary
        self.spellcheck = spellcheck
        self.settings = settings
        self.source_lang = source_lang
        self.target_lang = target_lang
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
        completer.setMaxVisibleItems(15)
        editor.setCompleter(completer)

        source_text = ""
        row = index.row()
        if row < len(self._source_texts):
            source_text = self._source_texts[row]

        min_score = 40.0
        if self.settings:
            min_score = self.settings.get("fuzzy_match_min_score", 40.0)

        debounce = QTimer(editor)
        debounce.setSingleShot(True)
        debounce.setInterval(180)

        def update_model(current_text=None):
            all_items = []
            seen_targets = set()

            if source_text:
                tm_matches = self.tm.get_fuzzy_matches(source_text, min_score=min_score, limit=15, source_lang=self.source_lang, target_lang=self.target_lang) if self.tm else []
                for m in tm_matches:
                    target = m.get("target", "")
                    score = m.get("score", 0)
                    src = m.get("source", "")
                    if not current_text or current_text.lower() in target.lower():
                        if target.lower() not in seen_targets:
                            seen_targets.add(target.lower())
                            label = f"{int(score):>2}%  {target}"
                            all_items.append((score, 0, label, target))

            if source_text:
                sem_matches = self.tm.get_semantic_matches(source_text, limit=5, source_lang=self.source_lang, target_lang=self.target_lang) if self.tm and hasattr(self.tm, 'get_semantic_matches') else []
                for m in sem_matches:
                    target = m.get("target", "")
                    score = m.get("score", 0)
                    if not current_text or current_text.lower() in target.lower():
                        if target.lower() not in seen_targets:
                            seen_targets.add(target.lower())
                            label = f"SEM {int(score):>2}%  {target}"
                            all_items.append((score, 1, label, target))

            if self.glossary and source_text:
                gl_terms = self.glossary.check_segment(source_text, source_lang=self.source_lang, target_lang=self.target_lang) if hasattr(self.glossary, 'check_segment') else []
                for term in gl_terms:
                    target = term.get("target", "")
                    src = term.get("source", "")
                    if not current_text or current_text.lower() in target.lower():
                        if target.lower() not in seen_targets:
                            seen_targets.add(target.lower())
                            label = f"GLOS  {target}  ({src})"
                            all_items.append((100, 2, label, target))

            if current_text and self.spellcheck and hasattr(self.spellcheck, 'suggest'):
                last_word = current_text.strip().split()[-1] if current_text.strip() else ""
                if last_word and len(last_word) > 2:
                    sp_suggestions = self.spellcheck.suggest(last_word)
                    for s in sp_suggestions[:5]:
                        replacement = current_text.rstrip(last_word) + s
                        if replacement.lower() not in seen_targets:
                            seen_targets.add(replacement.lower())
                            label = f"SPELL  {replacement}"
                            all_items.append((90, 3, label, replacement))

            all_items.sort(key=lambda x: (-x[0], x[1]))
            suggestions = [item[2] for item in all_items[:30]]

            model = QStringListModel(suggestions)
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
