import os

from cat_tool.formats import FORMAT_HANDLERS, FACTORY_EXTS
from cat_tool.formats.tag_utils import PH_L, PH_R, TAG_RE, extract_all_tags, apply_tags, restore_tags
from cat_tool.formats.factory import FactoryHandler

SUPPORTED_MSG = (
    "Supported: MCAT.DB, PO, POT, XLIFF, TS, TMX, TBX, CSV, TXT, "
    "PDF, DOCX, PPTX, XLSX, XLS, ODT, ODS, ODP, MQXLIFF"
)


class CATFileHandler:
    def __init__(self):
        self.current_file_path = None
        self.segments = []
        self._handler = None

    def load_file(self, file_path):
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        ext = os.path.splitext(file_path)[1].lower()
        if file_path.lower().endswith(".mcat.db"):
            ext = ".mcat.db"
        self.current_file_path = file_path

        handler_cls = FORMAT_HANDLERS.get(ext)
        if handler_cls is not None:
            self._handler = handler_cls()
            self.segments = self._handler.load(file_path)
            return self.segments

        if ext in FACTORY_EXTS:
            self._handler = FactoryHandler()
            self.segments = self._handler.load(file_path)
            return self.segments

        try:
            self._handler = FactoryHandler()
            self.segments = self._handler.load(file_path)
            return self.segments
        except Exception:
            raise ValueError(f"Unsupported file format: {ext}\n{SUPPORTED_MSG}")

    def _atomic_save(self, save_fn, target_path):
        dir_name = os.path.dirname(target_path) or "."
        tmp_path = os.path.join(dir_name, f".mcat_tmp_{os.getpid()}_{id(self)}")
        try:
            save_fn(tmp_path)
            os.replace(tmp_path, target_path)
        except BaseException:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            raise

    def save_file(self, target_path=None):
        if not self.segments:
            raise ValueError("No file loaded to save.")
        save_path = target_path or self.current_file_path
        ext = os.path.splitext(save_path)[1].lower()
        if save_path.lower().endswith(".mcat.db"):
            ext = ".mcat.db"

        def do_save(dest):
            if ext == ".mqxliff":
                from cat_tool.formats.mqxliif import MqxliffHandler
                MqxliffHandler().save(self.segments, dest)
            elif ext == ".sdlxliff":
                from cat_tool.formats.sdlxliff import SdlxliffHandler
                SdlxliffHandler().save(self.segments, dest)
            elif ext == ".mcat.db":
                from cat_tool.formats.mcatdb import McatDbHandler
                McatDbHandler().save(self.segments, dest)
            elif ext in FACTORY_EXTS:
                FactoryHandler().save(self.segments, dest)
            elif self._handler is not None and hasattr(self._handler, "save"):
                self._handler.save(self.segments, dest)
            else:
                raise ValueError(f"Cannot save to format: {ext}")

        self._atomic_save(do_save, save_path)
        self.current_file_path = save_path

    def save_as_mqxliif(self, output_path, src_lang="en", tgt_lang="es"):
        from cat_tool.formats.mqxliif import MqxliffHandler
        MqxliffHandler().save(self.segments, output_path, src_lang, tgt_lang)
        self.current_file_path = output_path

    def render_translated(self, output_path):
        if not self.segments:
            raise ValueError("No segments to render.")
        if not self.current_file_path:
            raise ValueError("No original file path; cannot render.")
        if self._handler is None:
            raise ValueError("No handler available for rendering.")
        if not hasattr(self._handler, "render"):
            raise ValueError(f"{type(self._handler).__name__} does not support rendering.")
        self._handler.render(self.current_file_path, self.segments, output_path)


def convert_to_po(source_path, output_path):
    from translate.storage.po import pofile
    handler = CATFileHandler()
    segments = handler.load_file(source_path)
    store = pofile()
    for seg in segments:
        unit = store.addsourceunit(seg["source"])
        unit.target = seg.get("target", "")
        if seg.get("fuzzy"):
            unit.markfuzzy()
    store.savefile(output_path)
    return output_path
