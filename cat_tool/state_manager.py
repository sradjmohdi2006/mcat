"""Application state manager — owns backends, project state, DB operations."""
import os

from cat_tool.file_handler import CATFileHandler, convert_to_po, convert_to_mcatdb
from cat_tool.tm import TranslationMemory
from cat_tool.glossary import Glossary
from cat_tool.project import Project
from cat_tool.segmentation import DEFAULT_RULES, load_rules
from cat_tool.settings import AppSettings
from cat_tool.spellcheck import SpellChecker, DICTS_DIR


def _get_data_dir():
    d = os.path.join(os.environ["APPDATA"], "mcat")
    os.makedirs(d, exist_ok=True)
    return d


class AppState:
    """Central state manager for the mcat application.

    Owns all backend services (file_handler, TM, glossary, etc.),
    project state, and provides business-logic methods that the
    MainWindow UI delegates to.
    """

    def __init__(self):
        data_dir = _get_data_dir()
        self.file_handler = CATFileHandler()
        self.tm = TranslationMemory(os.path.join(data_dir, "translation_memory.db"))
        self.glossary = Glossary(os.path.join(data_dir, "glossary.db"))
        self.project = None
        self.settings = AppSettings().load()
        self.spellchecker = SpellChecker()
        self.spellchecker.auto_load()
        self.segmentation_rules = [dict(r) for r in DEFAULT_RULES]
        self.current_segment_index = -1
        self.modified = False
        self._original_file_ext = None
        self._original_file_path = None
        self._load_segmentation_rules()

    # ---- property helpers ----

    @property
    def tm_sl(self):
        return self.project.source_lang if self.project else ""

    @property
    def tm_tl(self):
        return self.project.target_lang if self.project else ""

    @property
    def current_lang_code(self):
        if self.project and self.project.source_lang:
            return self.project.source_lang
        return "all"

    @property
    def has_segments(self):
        return bool(self.file_handler.segments)

    @property
    def segment_count(self):
        return len(self.file_handler.segments) if self.file_handler.segments else 0

    @property
    def current_segment(self):
        if not self.file_handler.segments:
            return None
        if 0 <= self.current_segment_index < len(self.file_handler.segments):
            return self.file_handler.segments[self.current_segment_index]
        return None

    # ---- segmentation rules ----

    def _load_segmentation_rules(self):
        from cat_tool.segmentation import LANG_NAME_TO_CODE
        all_rules = []
        for code in set(LANG_NAME_TO_CODE.values()):
            loaded = load_rules(code)
            if loaded:
                all_rules.extend(loaded)
        if all_rules:
            self.segmentation_rules = all_rules
        else:
            self.segmentation_rules = [dict(r) for r in DEFAULT_RULES]

    # ---- project operations ----

    def new_project(self, name, src_lang, tgt_lang, src_files):
        self.project = Project()
        self.project.new(name, src_lang, tgt_lang, src_files)
        self.file_handler = CATFileHandler()
        self.current_segment_index = -1
        self.modified = False

    def load_project(self, file_path):
        self.project = Project.load(file_path)
        self.file_handler = CATFileHandler()
        self.current_segment_index = -1
        self.modified = False
        Project.add_recent(file_path, self.project.name)

    def load_omegat(self, dir_path):
        self.project = Project.load_omegat(dir_path)
        self.file_handler = CATFileHandler()
        self.current_segment_index = -1
        self.modified = False
        Project.add_recent(dir_path, self.project.name)

    def load_memoq(self, dir_path):
        self.project = Project.load_memoq(dir_path)
        self.file_handler = CATFileHandler()
        self.current_segment_index = -1
        self.modified = False
        Project.add_recent(dir_path, self.project.name)

    def close_project(self):
        proj_name = self.project.name if self.project else ""
        self.project = None
        self.file_handler = CATFileHandler()
        self.current_segment_index = -1
        self.modified = False
        self._original_file_ext = None
        self._original_file_path = None
        return proj_name

    def save_project(self):
        if self.project and self.project.file_path:
            self.project.save()
            Project.add_recent(self.project.file_path, self.project.name)
            self.modified = False

    def save_project_as_mcatproj(self, file_path):
        if not file_path.endswith(".mcatproj"):
            file_path += ".mcatproj"
        self.project.save(file_path)
        self.modified = False
        Project.add_recent(file_path, self.project.name)

    def save_project_as_omegat(self, target_dir):
        self.project.save_as_omegat(target_dir)
        self.modified = False
        self.project.file_path = target_dir
        Project.add_recent(target_dir, self.project.name)

    def save_project_as_memoq(self, target_dir, file_handler):
        self.project.save_as_memoq(target_dir, file_handler)
        self.modified = False
        self.project.file_path = target_dir
        Project.add_recent(target_dir, self.project.name)

    # ---- source file loading ----

    def open_project_source_file(self, index):
        """Load a project source file. Returns (segments, display_label, is_error, error_msg)."""
        if not self.project or index >= len(self.project.source_files):
            return None, "", False, "No source file at that index"
        file_path = self.project.source_files[index]
        if not os.path.exists(file_path):
            return None, "", False, f"Source file not found:\n{file_path}"
        ext = os.path.splitext(file_path)[1].lower()
        is_mcatdb = ext == ".mcat.db"
        try:
            if is_mcatdb:
                self.file_handler.load_file(file_path)
                label = os.path.basename(file_path)
            else:
                # Convert to MCAT.DB as working format (fast, low memory)
                mcatdb_path = file_path + ".mcat.db"
                convert_to_mcatdb(file_path, mcatdb_path)
                self.file_handler.load_file(mcatdb_path)
                # Store original extension for rendering back
                self._original_file_ext = ext
                self._original_file_path = file_path
                label = os.path.basename(file_path) + "  (MCAT.DB working format)"
            return self.file_handler.segments, label, True, None
        except Exception as e:
            return None, "", False, str(e)

    # ---- TM operations ----

    def import_po_to_tm(self, po_path):
        handler = CATFileHandler()
        segments = handler.load_file(po_path)
        imported_count = 0
        for seg in segments:
            if seg["target"] and seg["target"].strip() and not seg["fuzzy"]:
                self.tm.add_translation(seg["source"], seg["target"], self.tm_sl, self.tm_tl)
                imported_count += 1
        return imported_count, segments

    def clear_tm(self):
        self.tm.clear()

    def get_fuzzy_matches(self, source_text):
        return self.tm.get_fuzzy_matches(
            source_text, min_score=40.0,
            source_lang=self.tm_sl or None, target_lang=self.tm_tl or None
        )

    # ---- spelling dictionary ----

    def load_spelling_dict(self, lang_code):
        if not lang_code:
            return None
        code = lang_code.lower()
        found = None
        if os.path.isdir(DICTS_DIR):
            for name in os.listdir(DICTS_DIR):
                if name.lower().startswith(code):
                    found = name
                    break
        if found and found not in self.spellchecker.loaded_names:
            path = os.path.join(DICTS_DIR, found)
            for f in os.listdir(path):
                if f.endswith(".dic"):
                    base = os.path.join(path, os.path.splitext(f)[0])
                    try:
                        from spylls.hunspell import Dictionary
                        d = Dictionary.from_files(base)
                        self.spellchecker.dictionaries.append(d)
                        self.spellchecker._loaded_names.append(found)
                    except Exception:
                        pass
                    break
            return found
        return None

    # ---- statistics ----

    def compute_stats(self):
        """Return a dict with translation statistics."""
        if not self.file_handler.segments:
            return {"total": 0, "translated": 0, "fuzzy": 0,
                    "total_words": 0, "total_chars": 0, "translated_words": 0, "percent": 0}
        total = len(self.file_handler.segments)
        translated = 0
        fuzzy = 0
        total_words = 0
        total_chars = 0
        translated_words = 0
        for seg in self.file_handler.segments:
            src = seg.get("source", "") or ""
            tgt = seg.get("target", "") or ""
            total_words += len(src.split())
            total_chars += len(src)
            if seg["fuzzy"]:
                fuzzy += 1
            elif tgt.strip():
                translated += 1
                translated_words += len(tgt.split())
        percent = int((translated / total) * 100) if total > 0 else 0
        return {
            "total": total, "translated": translated, "fuzzy": fuzzy,
            "total_words": total_words, "total_chars": total_chars,
            "translated_words": translated_words, "percent": percent,
        }
