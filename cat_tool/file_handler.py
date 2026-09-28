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

    def render_translated(self, output_path, original_path=None):
        """Render translated segments to output_path.
        
        If original_path is provided, use its handler for rendering (to support
        MCAT.DB working format where current_file_path is the .mcat.db file).
        """
        if not self.segments:
            raise ValueError("No segments to render.")
        if self._handler is None:
            raise ValueError("No handler available for rendering.")
        
        # Determine which handler to use for rendering
        render_handler = self._handler
        render_source_path = self.current_file_path
        
        if original_path and original_path != self.current_file_path:
            # Use original file's handler for rendering
            ext = os.path.splitext(original_path)[1].lower()
            if ext == ".mcat.db":
                ext = os.path.splitext(original_path.replace(".mcat.db", ""))[1].lower()
            from cat_tool.formats import FORMAT_HANDLERS, FACTORY_EXTS
            handler_cls = FORMAT_HANDLERS.get(ext)
            if handler_cls is not None:
                render_handler = handler_cls()
                render_source_path = original_path
            elif ext in FACTORY_EXTS:
                from cat_tool.formats.factory import FactoryHandler
                render_handler = FactoryHandler()
                render_source_path = original_path
        
        if not hasattr(render_handler, "render"):
            raise ValueError(f"{type(render_handler).__name__} does not support rendering.")
        render_handler.render(render_source_path, self.segments, output_path)

    def load_bookmarks(self):
        """Extract bookmarks/outlines from the current file, if supported.

        Returns a list of dicts with keys: title, level, page.
        Returns an empty list if the format has no bookmark support or no bookmarks.
        """
        if not self.current_file_path or not self._handler:
            return []
        if hasattr(self._handler, "load_bookmarks"):
            return self._handler.load_bookmarks(self.current_file_path)
        return []


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


def convert_to_mcatdb(source_path, output_path):
    """Convert any supported source file to MCAT.DB working format."""
    handler = CATFileHandler()
    segments = handler.load_file(source_path)
    from cat_tool.formats.mcatdb import McatDbHandler
    McatDbHandler().save(segments, output_path)
    return output_path
