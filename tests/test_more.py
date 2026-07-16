import unittest
import os
import sys
import tempfile
import json
import shutil
import importlib


# ========================== SPELL CHECKER TESTS ==========================

class TestSpellChecker(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls._orig_appdata = os.environ.get("APPDATA")
        os.environ["APPDATA"] = cls._tmp.name
        import cat_tool.spellcheck
        importlib.reload(cat_tool.spellcheck)

    @classmethod
    def tearDownClass(cls):
        if cls._orig_appdata:
            os.environ["APPDATA"] = cls._orig_appdata
        else:
            del os.environ["APPDATA"]
        cls._tmp.cleanup()

    def setUp(self):
        dicts_dir = os.path.join(os.environ["APPDATA"], "mcat", "dicts")
        if os.path.isdir(dicts_dir):
            shutil.rmtree(dicts_dir)

    def _make_real_dic(self, dic_path, aff_path, words=None):
        os.makedirs(os.path.dirname(dic_path), exist_ok=True)
        with open(aff_path, "w", encoding="utf-8") as f:
            f.write("SET UTF-8\n")
        words = words or ["hello", "world"]
        with open(dic_path, "w", encoding="utf-8") as f:
            f.write(f"{len(words)}\n")
            for w in words:
                f.write(f"{w}\n")

    def test_empty_checker(self):
        from cat_tool.spellcheck import SpellChecker
        sc = SpellChecker()
        self.assertFalse(sc.has_dict)
        self.assertEqual(sc.loaded_names, [])
        self.assertTrue(sc.check("anything"))
        self.assertEqual(sc.suggest("anything"), [])
        self.assertEqual(sc.check_text(""), [])
        self.assertEqual(sc.check_text(None), [])

    def test_auto_load_picks_up_dict(self):
        from cat_tool.spellcheck import SpellChecker
        dic_dir = os.path.join(os.environ["APPDATA"], "mcat", "dicts", "en_US")
        self._make_real_dic(
            os.path.join(dic_dir, "en_US.dic"),
            os.path.join(dic_dir, "en_US.aff"),
            ["Hello", "World"],
        )
        sc = SpellChecker()
        sc.auto_load()
        self.assertTrue(sc.has_dict)
        self.assertIn("en_US", sc.loaded_names)

    def test_check_known_word(self):
        from cat_tool.spellcheck import SpellChecker
        dic_dir = os.path.join(os.environ["APPDATA"], "mcat", "dicts", "en_US")
        self._make_real_dic(
            os.path.join(dic_dir, "en_US.dic"),
            os.path.join(dic_dir, "en_US.aff"),
            ["Hello", "World"],
        )
        sc = SpellChecker()
        sc.auto_load()
        self.assertTrue(sc.check("Hello"))
        self.assertTrue(sc.check("World"))

    def test_check_unknown_word(self):
        from cat_tool.spellcheck import SpellChecker
        dic_dir = os.path.join(os.environ["APPDATA"], "mcat", "dicts", "en_US")
        self._make_real_dic(
            os.path.join(dic_dir, "en_US.dic"),
            os.path.join(dic_dir, "en_US.aff"),
            ["Hello", "World"],
        )
        sc = SpellChecker()
        sc.auto_load()
        self.assertFalse(sc.check("xyzzzzz"))

    def test_auto_load_no_dicts_dir(self):
        from cat_tool.spellcheck import SpellChecker
        sc = SpellChecker()
        sc.auto_load()
        self.assertFalse(sc.has_dict)

    def test_auto_load_empty_dicts_dir(self):
        from cat_tool.spellcheck import SpellChecker
        os.makedirs(os.path.join(os.environ["APPDATA"], "mcat", "dicts"), exist_ok=True)
        sc = SpellChecker()
        sc.auto_load()
        self.assertFalse(sc.has_dict)

    def test_auto_load_skips_non_dic_files(self):
        from cat_tool.spellcheck import SpellChecker
        dicts_dir = os.path.join(os.environ["APPDATA"], "mcat", "dicts", "es")
        os.makedirs(dicts_dir, exist_ok=True)
        open(os.path.join(dicts_dir, "readme.txt"), "w").close()
        sc = SpellChecker()
        sc.auto_load()
        self.assertFalse(sc.has_dict)

    def test_auto_load_skips_missing_aff(self):
        from cat_tool.spellcheck import SpellChecker
        dicts_dir = os.path.join(os.environ["APPDATA"], "mcat", "dicts", "fr")
        os.makedirs(dicts_dir, exist_ok=True)
        with open(os.path.join(dicts_dir, "fr.dic"), "w", encoding="utf-8") as f:
            f.write("1\nmot\n")
        sc = SpellChecker()
        sc.auto_load()
        self.assertFalse(sc.has_dict)

    def test_load_dictionary_missing_aff(self):
        from cat_tool.spellcheck import SpellChecker
        sc = SpellChecker()
        ok = sc.load_dictionary(r"C:\nonexistent.dic")
        self.assertFalse(ok)

    def test_load_dictionary_copies_and_loads(self):
        from cat_tool.spellcheck import SpellChecker
        src_dir = os.path.join(self._tmp.name, "src")
        os.makedirs(src_dir, exist_ok=True)
        dic_path = os.path.join(src_dir, "custom.dic")
        aff_path = os.path.join(src_dir, "custom.aff")
        self._make_real_dic(dic_path, aff_path, ["foo", "bar"])
        sc = SpellChecker()
        ok = sc.load_dictionary(dic_path)
        self.assertTrue(ok)
        self.assertIn("custom", sc.loaded_names)
        self.assertTrue(sc.check("foo"))
        self.assertFalse(sc.check("baz"))

    def test_suggest_with_dict(self):
        from cat_tool.spellcheck import SpellChecker
        dic_dir = os.path.join(os.environ["APPDATA"], "mcat", "dicts", "en_US")
        self._make_real_dic(
            os.path.join(dic_dir, "en_US.dic"),
            os.path.join(dic_dir, "en_US.aff"),
            ["hello", "world"],
        )
        sc = SpellChecker()
        sc.auto_load()
        suggs = sc.suggest("worlt")
        self.assertIsInstance(suggs, list)

    def test_check_text_deduplicates(self):
        from cat_tool.spellcheck import SpellChecker
        dic_dir = os.path.join(os.environ["APPDATA"], "mcat", "dicts", "en_US")
        self._make_real_dic(
            os.path.join(dic_dir, "en_US.dic"),
            os.path.join(dic_dir, "en_US.aff"),
            ["hello"],
        )
        sc = SpellChecker()
        sc.auto_load()
        errors = sc.check_text("hello world world hello")
        err_words = [e[0] for e in errors]
        self.assertEqual(err_words.count("world"), 1)

    def test_check_text_catches_errors(self):
        from cat_tool.spellcheck import SpellChecker
        dic_dir = os.path.join(os.environ["APPDATA"], "mcat", "dicts", "en_US")
        self._make_real_dic(
            os.path.join(dic_dir, "en_US.dic"),
            os.path.join(dic_dir, "en_US.aff"),
            ["hello", "world", "test"],
        )
        sc = SpellChecker()
        sc.auto_load()
        errors = sc.check_text("hello worlt test")
        err_words = [e[0] for e in errors]
        self.assertIn("worlt", err_words)

    def test_lang_id_from_archive_with_underscore(self):
        import zipfile
        from cat_tool.spellcheck import SpellChecker
        sc = SpellChecker()
        archive_path = os.path.join(self._tmp.name, "dict_en_US.oxt")
        with zipfile.ZipFile(archive_path, "w") as z:
            z.writestr("en_US.dic", "1\nword\n")
            z.writestr("en_US.aff", "")
        lang_id = sc._lang_id_from_archive(archive_path)
        self.assertEqual(lang_id, "en_US")

    def test_lang_id_from_archive_uses_filename_fallback(self):
        import zipfile
        from cat_tool.spellcheck import SpellChecker
        sc = SpellChecker()
        archive_path = os.path.join(self._tmp.name, "spanish.oxt")
        with zipfile.ZipFile(archive_path, "w") as z:
            pass
        lang_id = sc._lang_id_from_archive(archive_path)
        self.assertEqual(lang_id, "spanish")

    def test_lang_id_from_archive_with_dic_inside(self):
        import zipfile
        from cat_tool.spellcheck import SpellChecker
        sc = SpellChecker()
        archive_path = os.path.join(self._tmp.name, "dicts.zip")
        with zipfile.ZipFile(archive_path, "w") as z:
            z.writestr("es_MX.dic", "1\nhola\n")
            z.writestr("es_MX.aff", "")
        lang_id = sc._lang_id_from_archive(archive_path)
        self.assertEqual(lang_id, "es_MX")

    def test_load_from_archive_nonexistent_returns_false(self):
        from cat_tool.spellcheck import SpellChecker
        sc = SpellChecker()
        ok = sc.load_from_archive(r"C:\nonexistent.zip")
        self.assertFalse(ok)

    def test_load_from_archive_bad_zip_returns_false(self):
        from cat_tool.spellcheck import SpellChecker
        sc = SpellChecker()
        bad_path = os.path.join(self._tmp.name, "bad.oxt")
        with open(bad_path, "w") as f:
            f.write("not a zip")
        ok = sc.load_from_archive(bad_path)
        self.assertFalse(ok)

    def test_load_from_archive_good_zip(self):
        import zipfile
        from cat_tool.spellcheck import SpellChecker
        sc = SpellChecker()
        dic_dir = os.path.join(self._tmp.name, "dictsrc")
        os.makedirs(dic_dir, exist_ok=True)
        with open(os.path.join(dic_dir, "es.dic"), "w", encoding="utf-8") as f:
            f.write("2\nhola\nmundo\n")
        with open(os.path.join(dic_dir, "es.aff"), "w", encoding="utf-8") as f:
            f.write("SET UTF-8\n")
        archive_path = os.path.join(self._tmp.name, "spanish.zip")
        with zipfile.ZipFile(archive_path, "w") as z:
            z.write(os.path.join(dic_dir, "es.dic"), "es.dic")
            z.write(os.path.join(dic_dir, "es.aff"), "es.aff")
        ok = sc.load_from_archive(archive_path)
        self.assertTrue(ok)


class TestSpellCheckerConstants(unittest.TestCase):
    def test_dicts_dir_uses_appdata(self):
        with tempfile.TemporaryDirectory() as tmp:
            old = os.environ.get("APPDATA")
            os.environ["APPDATA"] = tmp
            import cat_tool.spellcheck
            importlib.reload(cat_tool.spellcheck)
            expected = os.path.join(tmp, "mcat", "dicts")
            self.assertEqual(cat_tool.spellcheck.DICTS_DIR, expected)
            if old:
                os.environ["APPDATA"] = old
            else:
                del os.environ["APPDATA"]


# ========================== SETTINGS TESTS ==========================

class TestAppSettings(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._orig_appdata = os.environ.get("APPDATA")
        os.environ["APPDATA"] = self._tmp.name
        import cat_tool.settings
        importlib.reload(cat_tool.settings)

    def tearDown(self):
        if self._orig_appdata:
            os.environ["APPDATA"] = self._orig_appdata
        else:
            del os.environ["APPDATA"]

    def _settings_path(self):
        return os.path.join(self._tmp.name, "mcat", "settings.json")

    def test_defaults(self):
        from cat_tool.settings import AppSettings, DEFAULTS
        s = AppSettings().load()
        for k, v in DEFAULTS.items():
            self.assertEqual(s[k], v, f"Default {k} mismatch")

    def test_save_and_load(self):
        from cat_tool.settings import AppSettings
        s = AppSettings()
        s.load()
        s["source_font_size"] = 20
        s["target_font_size"] = 16
        s["auto_save_on_segment_change"] = True
        s.save()
        self.assertTrue(os.path.exists(self._settings_path()))
        s2 = AppSettings().load()
        self.assertEqual(s2["source_font_size"], 20)
        self.assertEqual(s2["target_font_size"], 16)
        self.assertTrue(s2["auto_save_on_segment_change"])

    def test_partial_overrides_keep_defaults(self):
        from cat_tool.settings import AppSettings
        os.makedirs(os.path.dirname(self._settings_path()), exist_ok=True)
        with open(self._settings_path(), "w") as f:
            json.dump({"source_font_size": 18}, f)
        s = AppSettings().load()
        self.assertEqual(s["source_font_size"], 18)
        self.assertEqual(s["target_font_size"], 13)

    def test_corrupted_json_falls_back_to_defaults(self):
        from cat_tool.settings import AppSettings, DEFAULTS
        os.makedirs(os.path.dirname(self._settings_path()), exist_ok=True)
        with open(self._settings_path(), "w") as f:
            f.write("not valid json")
        s = AppSettings().load()
        self.assertEqual(s["source_font_size"], DEFAULTS["source_font_size"])

    def test_missing_file_falls_back_to_defaults(self):
        from cat_tool.settings import AppSettings, DEFAULTS
        s = AppSettings().load()
        self.assertEqual(s["source_font_size"], DEFAULTS["source_font_size"])

    def test_contains(self):
        from cat_tool.settings import AppSettings
        s = AppSettings().load()
        self.assertIn("source_font_size", s)
        self.assertNotIn("nonexistent_key", s)

    def test_get(self):
        from cat_tool.settings import AppSettings
        s = AppSettings().load()
        self.assertEqual(s.get("source_font_size"), 13)
        self.assertIsNone(s.get("nonexistent"))
        self.assertEqual(s.get("nonexistent", 42), 42)

    def test_as_dict(self):
        from cat_tool.settings import AppSettings
        s = AppSettings().load()
        d = s.as_dict()
        self.assertIsInstance(d, dict)
        self.assertIn("source_font_size", d)
        self.assertEqual(d["source_font_size"], 13)

    def test_setitem_updates_dict(self):
        from cat_tool.settings import AppSettings
        s = AppSettings().load()
        s["source_font_size"] = 99
        self.assertEqual(s["source_font_size"], 99)

    def test_save_creates_directory(self):
        from cat_tool.settings import AppSettings
        s = AppSettings().load()
        s.save()
        self.assertTrue(os.path.isdir(os.path.join(self._tmp.name, "mcat")))


# ========================== ADDITIONAL QA EDGE CASES ==========================

class TestQAModuleAdditional(unittest.TestCase):
    def test_mixed_severity(self):
        from cat_tool.qa import QAIssue
        e = QAIssue("error", "E", 0, "s", "t", "d")
        w = QAIssue("warning", "W", 1, "s", "t", "d")
        self.assertEqual(e.severity, "error")
        self.assertEqual(w.severity, "warning")

    def test_empty_description(self):
        from cat_tool.qa import QAIssue
        issue = QAIssue("error", "test", 0, "src", "tgt", "")
        self.assertEqual(issue.description, "")

    def test_extract_numbers_edge_cases(self):
        from cat_tool.qa import _extract_numbers
        self.assertEqual(_extract_numbers(""), set())
        self.assertEqual(_extract_numbers("No digits here!"), set())
        self.assertEqual(_extract_numbers("Version 1.2.3"), {"1.2", "3"})

    def test_whitespace_no_source(self):
        from cat_tool.qa import check_whitespace
        segs = [{"source": None, "target": "Hello", "translated": True}]
        issues = check_whitespace(segs)
        self.assertEqual(len(issues), 0)

    def test_count_tags_empty(self):
        from cat_tool.qa import _count_tags
        self.assertEqual(_count_tags(""), 0)
        self.assertEqual(_count_tags(None), 0)
        self.assertEqual(_count_tags("plain text"), 0)


# ========================== ADDITIONAL SEGMENTATION EDGE CASES ==========================

class TestSegmentationAdditional(unittest.TestCase):
    def test_none_text(self):
        from cat_tool.segmentation import advanced_segmenter
        result = advanced_segmenter(None)
        self.assertEqual(result, [])

    def test_multiple_periods(self):
        from cat_tool.segmentation import advanced_segmenter
        result = advanced_segmenter("Hello... World...")
        self.assertGreaterEqual(len(result), 2)

    def test_exclamation_and_question(self):
        from cat_tool.segmentation import advanced_segmenter
        result = advanced_segmenter("Wow! Really? Yes.")
        self.assertGreaterEqual(len(result), 3)

    def test_break_before_literal(self):
        from cat_tool.segmentation import advanced_segmenter
        rules = [
            {"pattern": "@", "break_after": False, "break_before": True,
             "case_sensitive": False, "whole_word": False, "language": "All"},
        ]
        result = advanced_segmenter("hello @world @test", rules)
        self.assertGreaterEqual(len(result), 3)

    def test_break_before_combined(self):
        from cat_tool.segmentation import advanced_segmenter
        rules = [
            {"pattern": ".", "break_after": True,
             "case_sensitive": False, "whole_word": False, "language": "All"},
            {"pattern": "@", "break_after": False, "break_before": True,
             "case_sensitive": False, "whole_word": False, "language": "All"},
        ]
        result = advanced_segmenter("hello. @world. @test", rules)
        self.assertGreaterEqual(len(result), 3)

    def test_break_before_and_after(self):
        from cat_tool.segmentation import advanced_segmenter
        rules = [
            {"pattern": ".", "break_after": True,
             "case_sensitive": False, "whole_word": False, "language": "All"},
            {"pattern": "@", "break_after": False, "break_before": True,
             "case_sensitive": False, "whole_word": False, "language": "All"},
        ]
        result = advanced_segmenter("Hello. Next @mention. Done.", rules)
        self.assertGreaterEqual(len(result), 3)


# ========================== ADDITIONAL TAG UTILS EDGE CASES ==========================

class TestTagUtilsAdditional(unittest.TestCase):
    def test_extract_single_tag(self):
        from cat_tool.formats.tag_utils import extract_all_tags
        tags = extract_all_tags("<br/>")
        self.assertIn("<br/>", tags)

    def test_extract_nested_tags(self):
        from cat_tool.formats.tag_utils import extract_all_tags
        tags = extract_all_tags("<outer><inner>text</inner></outer>")
        self.assertIn("<outer>", tags)
        self.assertIn("<inner>", tags)
        self.assertIn("</inner>", tags)
        self.assertIn("</outer>", tags)

    def test_extract_self_closing_xml(self):
        from cat_tool.formats.tag_utils import extract_all_tags
        tags = extract_all_tags("<img src='x'/> and <hr/>")
        self.assertIn("<img src='x'/>", tags)
        self.assertIn("<hr/>", tags)

    def test_restore_with_none_tags(self):
        from cat_tool.formats.tag_utils import restore_tags
        result = restore_tags("Hello", None)
        self.assertEqual(result, "Hello")

    def test_apply_with_none_text(self):
        from cat_tool.formats.tag_utils import apply_tags
        result = apply_tags(None, ["<b>"])
        self.assertIsNone(result)


# ========================== ADDITIONAL FILE HANDLER EDGE CASES ==========================

class TestFileHandlerAdditional(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.fh = __import__("cat_tool.file_handler", fromlist=["CATFileHandler"]).CATFileHandler()

    def tearDown(self):
        self.tmp.cleanup()

    def test_atomic_save_failure_cleans_temp(self):
        tmp_file = os.path.join(self.tmp.name, "test.po")
        with open(tmp_file, "w", encoding="utf-8") as f:
            f.write('msgid "Hello"\nmsgstr ""\n')
        self.fh.load_file(tmp_file)
        def _fail(_):
            raise RuntimeError("simulated failure")
        with self.assertRaises(RuntimeError):
            self.fh._atomic_save(_fail, tmp_file)
        temps = [f for f in os.listdir(self.tmp.name) if f.startswith(".mcat_tmp_")]
        self.assertEqual(len(temps), 0)

    def test_save_file_without_loading_raises(self):
        fh = __import__("cat_tool.file_handler", fromlist=["CATFileHandler"]).CATFileHandler()
        with self.assertRaises(ValueError):
            fh.save_file()

    def test_current_file_path_none_on_new(self):
        self.assertIsNone(self.fh.current_file_path)

    def test_load_with_mcatdb_extension(self):
        from cat_tool.formats.mcatdb import McatDbHandler
        path = os.path.join(self.tmp.name, "project.mcat.db")
        McatDbHandler().save([{
            "index": 0, "source": "Hello", "target": "Hola",
            "source_clean": "Hello", "target_clean": "Hola",
            "all_tags": [], "fuzzy": False, "translated": True,
            "locations": "", "notes": "", "source_location": {},
            "store": None, "unit": None,
        }], path)
        segs = self.fh.load_file(path)
        self.assertEqual(len(segs), 1)
        self.assertEqual(segs[0]["source"], "Hello")

    def test_render_without_handler_raises(self):
        self.fh.segments = [{"source": "Hello", "target": "Hola"}]
        self.fh.current_file_path = os.path.join(self.tmp.name, "dummy.txt")
        with self.assertRaises(ValueError):
            self.fh.render_translated(os.path.join(self.tmp.name, "out.txt"))

    def test_save_file_mcatdb_preserves_path(self):
        from cat_tool.formats.mcatdb import McatDbHandler
        path = os.path.join(self.tmp.name, "project.mcat.db")
        McatDbHandler().save([{
            "index": 0, "source": "Hello", "target": "",
            "source_clean": "Hello", "target_clean": "",
            "all_tags": [], "fuzzy": False, "translated": False,
            "locations": "", "notes": "", "source_location": {},
            "store": None, "unit": None,
        }], path)
        self.fh.load_file(path)
        self.fh.save_file()
        self.assertEqual(self.fh.current_file_path, path)


# ========================== XLS HANDLER TESTS ==========================

class TestXlsHandler(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def test_xls_load_basic(self):
        try:
            from cat_tool.formats.xls import XlsHandler
        except ImportError:
            self.skipTest("XlsHandler not available")
        try:
            import xlwt
        except ImportError:
            self.skipTest("xlwt not available")
        wb = xlwt.Workbook()
        ws = wb.add_sheet("Sheet1")
        ws.write(0, 0, "Hello")
        ws.write(0, 1, "World")
        path = os.path.join(self.tmp.name, "test.xls")
        wb.save(path)
        segs = XlsHandler().load(path)
        texts = [s["source"] for s in segs]
        self.assertIn("Hello", texts)

    def test_xls_load_empty_workbook(self):
        try:
            from cat_tool.formats.xls import XlsHandler
        except ImportError:
            self.skipTest("XlsHandler not available")
        try:
            import xlwt
        except ImportError:
            self.skipTest("xlwt not available")
        wb = xlwt.Workbook()
        wb.add_sheet("Empty")
        path = os.path.join(self.tmp.name, "empty.xls")
        wb.save(path)
        segs = XlsHandler().load(path)
        self.assertEqual(len(segs), 0)

    def test_xls_load_nonexistent_raises(self):
        try:
            from cat_tool.formats.xls import XlsHandler
        except ImportError:
            self.skipTest("XlsHandler not available")
        with self.assertRaises(FileNotFoundError):
            XlsHandler().load(r"C:\nonexistent.xls")


# ========================== ODF HANDLER TESTS ==========================

class TestOdfHandler(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def test_load_odt(self):
        try:
            from odf.opendocument import OpenDocumentText
            from odf.text import P
        except ImportError:
            self.skipTest("odf not available")
        doc = OpenDocumentText()
        p = P(text="Hello ODF World")
        doc.text.addElement(p)
        path = os.path.join(self.tmp.name, "test.odt")
        doc.save(path)
        from cat_tool.formats.odf import OdfHandler
        segs = OdfHandler().load(path)
        texts = [s["source"] for s in segs]
        self.assertIn("Hello ODF World", texts)

    def test_odf_load_nonexistent_raises(self):
        try:
            from cat_tool.formats.odf import OdfHandler
        except ImportError:
            self.skipTest("odf not available")
        with self.assertRaises(FileNotFoundError):
            OdfHandler().load(r"C:\nonexistent.odt")

    def test_odf_render_updates_target(self):
        try:
            from odf.opendocument import OpenDocumentText
            from odf.text import P
        except ImportError:
            self.skipTest("odf not available")
        doc = OpenDocumentText()
        p = P(text="Hello")
        doc.text.addElement(p)
        path = os.path.join(self.tmp.name, "test.odt")
        doc.save(path)
        from cat_tool.formats.odf import OdfHandler
        handler = OdfHandler()
        segs = handler.load(path)
        segs[0]["target"] = "Hola"
        out_path = os.path.join(self.tmp.name, "out.odt")
        handler.render(path, segs, out_path)
        segs2 = handler.load(out_path)
        self.assertEqual(segs2[0]["source"], "Hola")

    def test_odf_render_no_segments_output_created(self):
        try:
            from odf.opendocument import OpenDocumentText
        except ImportError:
            self.skipTest("odf not available")
        doc = OpenDocumentText()
        path = os.path.join(self.tmp.name, "empty.odt")
        doc.save(path)
        from cat_tool.formats.odf import OdfHandler
        out_path = os.path.join(self.tmp.name, "out.odt")
        OdfHandler().render(path, [], out_path)
        self.assertTrue(os.path.exists(out_path))


# ========================== ADDITIONAL FORMAT EDGE CASES ==========================

class TestMakeSegmentsFromTextsAdditional(unittest.TestCase):
    def test_none_text_skipped(self):
        from cat_tool.formats._text_base import make_segments_from_texts
        segs = make_segments_from_texts(["Hello", None, "World"])
        self.assertEqual(len(segs), 2)

    def test_all_empty_skipped(self):
        from cat_tool.formats._text_base import make_segments_from_texts
        segs = make_segments_from_texts(["", "", None])
        self.assertEqual(len(segs), 0)

    def test_normal_works(self):
        from cat_tool.formats._text_base import make_segments_from_texts
        segs = make_segments_from_texts(["Hello", "World"])
        self.assertEqual(len(segs), 2)


# ========================== CONVERT TO PO EDGE CASES ==========================

class TestConvertToPoAdditional(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def test_convert_to_po_creates_file(self):
        from cat_tool.file_handler import convert_to_po
        txt_path = os.path.join(self.tmp.name, "source.txt")
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write("Hello\nWorld\nTest")
        out = os.path.join(self.tmp.name, "output.po")
        convert_to_po(txt_path, out)
        self.assertTrue(os.path.exists(out))
        with open(out, encoding="utf-8") as f:
            content = f.read()
        self.assertIn("Hello", content)
        self.assertIn("World", content)

    def test_convert_to_po_roundtrip(self):
        from cat_tool.file_handler import CATFileHandler, convert_to_po
        txt_path = os.path.join(self.tmp.name, "source.txt")
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write("Line one\nLine two")
        po_path = os.path.join(self.tmp.name, "conv.po")
        convert_to_po(txt_path, po_path)
        fh = CATFileHandler()
        segs = fh.load_file(po_path)
        self.assertEqual(len(segs), 2)


# ========================== MCAT FORMAT MANAGER ADDITIONAL TESTS ==========================

class TestMCatProjectManagerAdditional(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmp.name, "test.mcat.db")

    def tearDown(self):
        self.tmp.cleanup()

    def test_get_editor_stream_empty_db(self):
        from cat_tool.mcat_format_manager import MCatProjectManager
        MCatProjectManager.create_project_file(self.db_path, "en", "es")
        rows = MCatProjectManager.get_editor_stream(self.db_path)
        self.assertEqual(len(rows), 0)

    def test_get_editor_stream_filter_nonexistent_status(self):
        from cat_tool.mcat_format_manager import MCatProjectManager
        MCatProjectManager.create_project_file(self.db_path, "en", "es")
        rows = MCatProjectManager.get_editor_stream(self.db_path, filter_status="NonExistent")
        self.assertEqual(len(rows), 0)

    def test_update_segment_invalid_id(self):
        from cat_tool.mcat_format_manager import MCatProjectManager
        MCatProjectManager.create_project_file(self.db_path, "en", "es")
        MCatProjectManager.update_segment_translation(self.db_path, 999, "test", "Confirmed")

    def test_import_and_get_stream(self):
        from cat_tool.mcat_format_manager import MCatProjectManager
        MCatProjectManager.create_project_file(self.db_path, "en", "es")
        segments = [
            {"file_id": "test.txt", "source": "Hello", "target": "Hola", "status": "Confirmed", "match_score": 100},
        ]
        MCatProjectManager.import_extracted_segments(self.db_path, segments)
        rows = MCatProjectManager.get_editor_stream(self.db_path)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["source_text"], "Hello")

    def test_update_segment(self):
        from cat_tool.mcat_format_manager import MCatProjectManager
        MCatProjectManager.create_project_file(self.db_path, "en", "es")
        MCatProjectManager.import_extracted_segments(self.db_path, [
            {"file_id": "a.txt", "source": "Hello", "target": "", "status": "Untranslated", "match_score": 0},
        ])
        rows = MCatProjectManager.get_editor_stream(self.db_path)
        unit_id = rows[0]["id"]
        MCatProjectManager.update_segment_translation(self.db_path, unit_id, "Hola", "Confirmed")
        rows = MCatProjectManager.get_editor_stream(self.db_path)
        self.assertEqual(rows[0]["target_text"], "Hola")


# ========================== DEDICATED QA CHECK TESTS ==========================

class TestQACheckFunctions(unittest.TestCase):
    def test_check_terminology_no_glossary(self):
        from cat_tool.qa import check_terminology
        segs = [{"source": "cat", "target": "gato", "translated": True}]
        with self.assertRaises(AttributeError):
            check_terminology(segs, None)

    def test_check_inconsistent_translations_empty_source(self):
        from cat_tool.qa import check_inconsistent_translations
        segs = [
            {"source": "", "target": "Hola", "translated": True},
            {"source": "", "target": "Hello", "translated": True},
        ]
        issues = check_inconsistent_translations(segs)
        self.assertEqual(len(issues), 0)

    def test_tag_mismatch_no_source_tags(self):
        from cat_tool.qa import check_tag_mismatch
        segs = [{"source": "Hello", "target": "Hola {0}", "all_tags": []}]
        issues = check_tag_mismatch(segs)
        self.assertEqual(len(issues), 0)

    def test_count_tags_with_tags(self):
        from cat_tool.qa import _count_tags
        from cat_tool.formats.tag_utils import PH_L, PH_R
        text = f"{PH_L}0{PH_R} and {PH_L}1{PH_R}"
        self.assertEqual(_count_tags(text), 2)


# ========================== MEMORY / EDGE CASE TESTS ==========================

class TestTranslationMemoryAdditional(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmp.name, "tm.db")
        from cat_tool.tm import TranslationMemory
        self.tm = TranslationMemory(self.db_path)

    def tearDown(self):
        self.tmp.cleanup()

    def test_add_translation_none_target(self):
        self.tm.add_translation("Hello", None)
        matches = self.tm.get_fuzzy_matches("Hello")
        self.assertEqual(len(matches), 0)

    def test_get_fuzzy_matches_empty_db(self):
        matches = self.tm.get_fuzzy_matches("Anything")
        self.assertEqual(len(matches), 0)

    def test_get_fuzzy_matches_with_min_score(self):
        self.tm.add_translation("Hello world", "Hola mundo")
        matches = self.tm.get_fuzzy_matches("Hello world!", min_score=90.0)
        self.assertGreater(len(matches), 0)

    def test_get_fuzzy_matches_extreme_min_score(self):
        self.tm.add_translation("Hello", "Hola")
        matches = self.tm.get_fuzzy_matches("Completely different", min_score=0.0)
        self.assertGreater(len(matches), 0)


class TestGlossaryAdditional(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmp.name, "glossary.db")
        from cat_tool.glossary import Glossary
        self.gl = Glossary(self.db_path)

    def tearDown(self):
        self.tmp.cleanup()

    def test_remove_nonexistent_term(self):
        self.gl.remove_term("nonexistent")
        terms = self.gl.get_all_terms()
        self.assertEqual(len(terms), 0)

    def test_check_segment_none_text(self):
        matches = self.gl.check_segment(None)
        self.assertEqual(len(matches), 0)

    def test_add_term_special_chars(self):
        self.gl.add_term("cafe", "coffee")
        matches = self.gl.check_segment("I like cafe")
        self.assertEqual(len(matches), 1)

    def test_add_term_with_langs(self):
        self.gl.add_term("hello", "hola", source_lang="en", target_lang="es")
        terms = self.gl.get_all_terms()
        self.assertEqual(len(terms), 1)
        self.assertEqual(terms[0]["source_lang"], "en")
        self.assertEqual(terms[0]["target_lang"], "es")

    def test_import_tmx_basic(self):
        import xml.etree.ElementTree as ET
        tmx_content = """<?xml version="1.0" encoding="UTF-8"?>
<tmx version="1.4">
  <header srclang="en" datatype="plaintext"/>
  <body>
    <tu>
      <tuv xml:lang="en"><seg>Hello</seg></tuv>
      <tuv xml:lang="es"><seg>Hola</seg></tuv>
    </tu>
    <tu>
      <tuv xml:lang="en"><seg>Goodbye</seg></tuv>
      <tuv xml:lang="es"><seg>Adiós</seg></tuv>
    </tu>
  </body>
</tmx>"""
        tmx_path = os.path.join(self.tmp.name, "test.tmx")
        with open(tmx_path, "w", encoding="utf-8") as f:
            f.write(tmx_content)
        count = self.gl.import_tmx(tmx_path)
        self.assertEqual(count, 2)
        terms = self.gl.get_all_terms()
        self.assertEqual(len(terms), 2)
        for t in terms:
            self.assertEqual(t["source_lang"], "en")
            self.assertEqual(t["target_lang"], "es")

    def test_import_tmx_nonexistent_file(self):
        with self.assertRaises(FileNotFoundError):
            self.gl.import_tmx("nonexistent.tmx")

    def test_import_tmx_empty_body(self):
        import xml.etree.ElementTree as ET
        tmx_content = """<?xml version="1.0" encoding="UTF-8"?>
<tmx version="1.4">
  <header srclang="en" datatype="plaintext"/>
  <body>
  </body>
</tmx>"""
        tmx_path = os.path.join(self.tmp.name, "empty.tmx")
        with open(tmx_path, "w", encoding="utf-8") as f:
            f.write(tmx_content)
        count = self.gl.import_tmx(tmx_path)
        self.assertEqual(count, 0)

    def test_import_tmx_missing_body(self):
        import xml.etree.ElementTree as ET
        tmx_content = """<?xml version="1.0" encoding="UTF-8"?>
<tmx version="1.4">
  <header srclang="en" datatype="plaintext"/>
</tmx>"""
        tmx_path = os.path.join(self.tmp.name, "nobody.tmx")
        with open(tmx_path, "w", encoding="utf-8") as f:
            f.write(tmx_content)
        count = self.gl.import_tmx(tmx_path)
        self.assertEqual(count, 0)

    def test_import_tmx_no_srclang_header(self):
        import xml.etree.ElementTree as ET
        tmx_content = """<?xml version="1.0" encoding="UTF-8"?>
<tmx version="1.4">
  <header datatype="plaintext"/>
  <body>
    <tu>
      <tuv xml:lang="fr"><seg>Bonjour</seg></tuv>
      <tuv xml:lang="en"><seg>Hello</seg></tuv>
    </tu>
  </body>
</tmx>"""
        tmx_path = os.path.join(self.tmp.name, "nosrclang.tmx")
        with open(tmx_path, "w", encoding="utf-8") as f:
            f.write(tmx_content)
        count = self.gl.import_tmx(tmx_path)
        self.assertEqual(count, 1)

    def test_import_tmx_with_explicit_source_lang(self):
        import xml.etree.ElementTree as ET
        tmx_content = """<?xml version="1.0" encoding="UTF-8"?>
<tmx version="1.4">
  <header srclang="en" datatype="plaintext"/>
  <body>
    <tu>
      <tuv xml:lang="en"><seg>Cat</seg></tuv>
      <tuv xml:lang="fr"><seg>Chat</seg></tuv>
    </tu>
  </body>
</tmx>"""
        tmx_path = os.path.join(self.tmp.name, "explicit.tmx")
        with open(tmx_path, "w", encoding="utf-8") as f:
            f.write(tmx_content)
        count = self.gl.import_tmx(tmx_path, source_lang="fr")
        self.assertEqual(count, 1)
        terms = self.gl.get_all_terms()
        self.assertEqual(terms[0]["source"], "Chat")
        self.assertEqual(terms[0]["target"], "Cat")
        self.assertEqual(terms[0]["source_lang"], "fr")

    def test_peek_tmx_basic(self):
        import xml.etree.ElementTree as ET
        tmx_content = """<?xml version="1.0" encoding="UTF-8"?>
<tmx version="1.4">
  <header srclang="en" datatype="plaintext"/>
  <body>
    <tu><tuv xml:lang="en"><seg>Hello</seg></tuv><tuv xml:lang="es"><seg>Hola</seg></tuv></tu>
    <tu><tuv xml:lang="en"><seg>Bye</seg></tuv><tuv xml:lang="es"><seg>Adiós</seg></tuv></tu>
  </body>
</tmx>"""
        tmx_path = os.path.join(self.tmp.name, "peek.tmx")
        with open(tmx_path, "w", encoding="utf-8") as f:
            f.write(tmx_content)
        info = self.gl.peek_tmx(tmx_path)
        self.assertEqual(info["source_lang"], "en")
        self.assertEqual(info["target_lang"], "es")
        self.assertEqual(info["count"], 2)

    def test_peek_tmx_no_srclang(self):
        import xml.etree.ElementTree as ET
        tmx_content = """<?xml version="1.0" encoding="UTF-8"?>
<tmx version="1.4">
  <header datatype="plaintext"/>
  <body>
    <tu><tuv xml:lang="fr"><seg>Bonjour</seg></tuv><tuv xml:lang="en"><seg>Hello</seg></tuv></tu>
  </body>
</tmx>"""
        tmx_path = os.path.join(self.tmp.name, "peek2.tmx")
        with open(tmx_path, "w", encoding="utf-8") as f:
            f.write(tmx_content)
        info = self.gl.peek_tmx(tmx_path)
        self.assertEqual(info["source_lang"], "")
        self.assertIn("fr", info["target_lang"])
        self.assertEqual(info["count"], 1)

    def test_export_tmx_empty(self):
        tmx_path = os.path.join(self.tmp.name, "out.tmx")
        count = self.gl.export_tmx(tmx_path)
        self.assertEqual(count, 0)

    def test_export_tmx_roundtrip(self):
        from cat_tool.glossary import Glossary
        import xml.etree.ElementTree as ET
        self.gl.add_term("hello", "hola", source_lang="en", target_lang="es")
        self.gl.add_term("goodbye", "adiós", source_lang="en", target_lang="es")
        tmx_path = os.path.join(self.tmp.name, "roundtrip.tmx")
        count = self.gl.export_tmx(tmx_path)
        self.assertEqual(count, 2)

        self.gl2 = Glossary(os.path.join(self.tmp.name, "glossary2.db"))
        count2 = self.gl2.import_tmx(tmx_path)
        self.assertEqual(count2, 2)
        terms = self.gl2.get_all_terms()
        self.assertEqual(len(terms), 2)
        self.assertEqual(terms[0]["source_lang"], "en")
        self.assertEqual(terms[0]["target_lang"], "es")

    def test_export_tmx_source_lang_override(self):
        import xml.etree.ElementTree as ET
        self.gl.add_term("bonjour", "hello", source_lang="fr", target_lang="en")
        tmx_path = os.path.join(self.tmp.name, "override.tmx")
        self.gl.export_tmx(tmx_path, source_lang="fr")
        tree = ET.parse(tmx_path)
        root = tree.getroot()
        header = root.find("header")
        self.assertEqual(header.get("srclang"), "fr")


if __name__ == "__main__":
    unittest.main()
