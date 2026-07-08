from cat_tool.formats.tag_utils import PH_L, PH_R, TAG_RE, extract_all_tags, apply_tags, restore_tags
from cat_tool.formats.factory import FactoryHandler
from cat_tool.formats.mqxliif import MqxliffHandler
from cat_tool.formats.sdlxliff import SdlxliffHandler
from cat_tool.formats.text import TextHandler
from cat_tool.formats.pdf import PdfHandler
from cat_tool.formats.docx import DocxHandler
from cat_tool.formats.pptx import PptxHandler
from cat_tool.formats.xlsx import XlsxHandler
from cat_tool.formats.xls import XlsHandler
from cat_tool.formats.odf import OdfHandler
from cat_tool.formats.mcatdb import McatDbHandler

FORMAT_HANDLERS = {
    ".txt": TextHandler,
    ".pdf": PdfHandler,
    ".docx": DocxHandler,
    ".pptx": PptxHandler,
    ".ppsx": PptxHandler,
    ".xlsx": XlsxHandler,
    ".xls": XlsHandler,
    ".odt": OdfHandler,
    ".ods": OdfHandler,
    ".odp": OdfHandler,
    ".mqxliff": MqxliffHandler,
    ".sdlxliff": SdlxliffHandler,
    ".mcat.db": McatDbHandler,
}

FACTORY_EXTS = frozenset({".po", ".pot", ".mo", ".xlf", ".xliff", ".ts", ".tmx", ".tbx", ".csv"})
