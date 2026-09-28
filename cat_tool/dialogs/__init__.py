"""Shared dialog utilities and re-exports."""
from PyQt5.QtWidgets import QComboBox

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


def fill_lang_combo(combo, selected_code=""):
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

from cat_tool.dialogs.glossary_dialogs import GlossaryDialog, LangDialog
from cat_tool.dialogs.project_dialogs import NewProjectDialog, ProjectSettingsDialog
from cat_tool.dialogs.view_dialogs import ShortcutsDialog, QADialog, TagViewDialog, ChapterViewDialog
from cat_tool.dialogs.spellcheck_dialog import SpellCheckDialog
from cat_tool.dialogs.settings_dialog import SettingsDialog
from cat_tool.dialogs.search_dialog import SearchDialog

__all__ = [
    "GlossaryDialog", "LangDialog", "NewProjectDialog", "ProjectSettingsDialog",
    "ShortcutsDialog", "QADialog", "SpellCheckDialog", "SettingsDialog", "TagViewDialog",
    "ChapterViewDialog", "SearchDialog",
    "LANGUAGES", "fill_lang_combo", "FILE_FILTER",
]
