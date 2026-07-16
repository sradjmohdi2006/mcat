import unittest
import os
import tempfile
import json
import sqlite3

from cat_tool.qa import (
    QAIssue, run_all_checks,
    check_missing_translations, check_unedited_fuzzy,
    check_inconsistent_translations, check_tag_mismatch,
    check_number_mismatch, check_whitespace, check_terminology,
    _extract_numbers, _count_tags,
)
from cat_tool.tm import TranslationMemory
from cat_tool.glossary import Glossary
from cat_tool.segmentation import advanced_segmenter, DEFAULT_RULES
from cat_tool.formats.tag_utils import PH_L, PH_R, extract_all_tags, apply_tags, restore_tags
from cat_tool.file_handler import CATFileHandler, convert_to_po
from cat_tool.mcat_format_manager import MCatProjectManager, SCHEMA_SQL
from cat_tool.formats._text_base import make_segments_from_texts


def make_seg(index=0, source="Hello world", target="", fuzzy=False, translated=False, tags=None, source_location=None):
    seg = {
        "index": index,
        "source": source,
        "target": target,
        "source_clean": source,
        "target_clean": target,
        "all_tags": tags or [],
        "notes": "",
        "fuzzy": fuzzy,
        "translated": translated,
        "locations": "",
        "source_location": source_location or {},
        "store": None,
        "unit": None,
    }
    if tags:
        from cat_tool.formats.tag_utils import apply_tags
        seg["source_clean"] = apply_tags(source, tags)
        seg["target_clean"] = apply_tags(target, tags)
    return seg


class TestQAModule(unittest.TestCase):
    def setUp(self):
        self.segments = [
            make_seg(0, "Hello world", "Hola mundo", translated=True),
            make_seg(1, "Good morning", "", fuzzy=True),
            make_seg(2, "How are you?", "¿Cómo estás?", translated=True),
            make_seg(3, "Goodbye", ""),
            make_seg(4, "Hello world", "Hola mundo!", translated=True),
        ]

    def test_missing_translations(self):
        issues = check_missing_translations(self.segments)
        self.assertEqual(len(issues), 2)
        indices = {i.segment_index for i in issues}
        self.assertIn(1, indices)
        self.assertIn(3, indices)

    def test_missing_translations_none_target(self):
        segs = [make_seg(0, "test", None)]
        issues = check_missing_translations(segs)
        self.assertEqual(len(issues), 1)

    def test_unedited_fuzzy(self):
        issues = check_unedited_fuzzy(self.segments)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].segment_index, 1)

    def test_inconsistent_translations(self):
        issues = check_inconsistent_translations(self.segments)
        self.assertEqual(len(issues), 2)
        self.assertEqual(issues[0].segment_index, 0)
        self.assertEqual(issues[1].segment_index, 4)

    def test_inconsistent_translations_no_dupes(self):
        segs = [
            make_seg(0, "Hello", "Hola", translated=True),
            make_seg(1, "World", "Mundo", translated=True),
        ]
        issues = check_inconsistent_translations(segs)
        self.assertEqual(len(issues), 0)

    def test_tag_mismatch(self):
        segs = [
            make_seg(0, f"Start {PH_L}0{PH_R} end", f"Inicio {PH_L}0{PH_R} fin", tags=["<b>"]),
            make_seg(1, f"Hello {PH_L}0{PH_R} world", "Hola mundo", tags=["<b>"]),
            make_seg(2, "No tags", "Sin etiquetas"),
        ]
        issues = check_tag_mismatch(segs)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].segment_index, 1)

    def test_number_mismatch(self):
        segs = [
            make_seg(0, "Version 2.0 released", "Versión 2.0 lanzada", translated=True),
            make_seg(1, "File 1 of 3", "Archivo 1 de 3", translated=True),
            make_seg(2, "Cost: $50.00", "Costo: $99.00", translated=True),
            make_seg(3, "No numbers here", "Sin números"),
        ]
        issues = check_number_mismatch(segs)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].segment_index, 2)

    def test_whitespace(self):
        segs = [
            make_seg(0, "  Leading spaces", "Leading spaces", translated=True),
            make_seg(1, "No leading space", "  Has leading space", translated=True),
            make_seg(2, "Trailing space  ", "Trailing space", translated=True),
            make_seg(3, "No trailing", "Has trailing  ", translated=True),
            make_seg(4, "  Both sides  ", "  Both sides  ", translated=True),
            make_seg(5, "Good", "", translated=False),
        ]
        issues = check_whitespace(segs)
        self.assertEqual(len(issues), 4)

    def test_terminology(self):
        segs = [
            make_seg(0, "The cat is sleeping.", "El gato duerme.", translated=True),
            make_seg(1, "Quick brown fox.", "Zorro rápido.", translated=True),
            make_seg(2, "No terms here.", "Sin términos.", translated=True),
        ]
        tmp_dir = tempfile.TemporaryDirectory()
        gl = Glossary(os.path.join(tmp_dir.name, "test_gl.db"))
        gl.add_term("cat", "gato", "feline")
        gl.add_term("quick brown fox", "zorro marrón rápido", "fast fox")

        issues = check_terminology(segs, gl)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].segment_index, 1)
        tmp_dir.cleanup()

    def test_terminology_missing_target(self):
        segs = [make_seg(0, "The cat is here.", "", fuzzy=True)]
        tmp_dir = tempfile.TemporaryDirectory()
        gl = Glossary(os.path.join(tmp_dir.name, "test_gl.db"))
        gl.add_term("cat", "gato")
        issues = check_terminology(segs, gl)
        self.assertEqual(len(issues), 0)
        tmp_dir.cleanup()

    def test_run_all_checks(self):
        tmp_dir = tempfile.TemporaryDirectory()
        gl = Glossary(os.path.join(tmp_dir.name, "test_gl.db"))
        gl.add_term("cat", "gato")
        issues = run_all_checks(self.segments, glossary=gl)
        self.assertGreater(len(issues), 0)
        tmp_dir.cleanup()

    def test_run_all_checks_no_glossary(self):
        issues = run_all_checks(self.segments)
        self.assertGreater(len(issues), 2)

    def test_extract_numbers(self):
        self.assertEqual(_extract_numbers("Version 2.0"), {"2.0"})
        self.assertEqual(_extract_numbers("File 1 of 3"), {"1", "3"})
        self.assertEqual(_extract_numbers("No numbers"), set())

    def test_empty_segments(self):
        issues = run_all_checks([])
        self.assertEqual(len(issues), 0)

    def test_qa_issue_slots(self):
        issue = QAIssue("error", "Test", 0, "src", "tgt", "desc")
        self.assertEqual(issue.severity, "error")
        self.assertEqual(issue.segment_index, 0)


class TestTranslationMemory(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmp_dir.name, "tm.db")
        self.tm = TranslationMemory(self.db_path)

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_add_and_fuzzy_match(self):
        self.tm.add_translation("Hello world", "Hola mundo")
        matches = self.tm.get_fuzzy_matches("Hello world")
        self.assertGreater(len(matches), 0)
        self.assertEqual(matches[0]["target"], "Hola mundo")
        self.assertEqual(matches[0]["score"], 100.0)

    def test_fuzzy_match_partial(self):
        self.tm.add_translation("The quick brown fox", "El zorro marrón rápido")
        matches = self.tm.get_fuzzy_matches("The quick brown fox jumps", min_score=50.0)
        self.assertGreater(len(matches), 0)
        self.assertGreater(matches[0]["score"], 50.0)

    def test_no_match(self):
        self.tm.add_translation("Hello", "Hola")
        matches = self.tm.get_fuzzy_matches("Completely different text", min_score=90.0)
        self.assertEqual(len(matches), 0)

    def test_clear(self):
        self.tm.add_translation("Hello", "Hola")
        self.tm.clear()
        matches = self.tm.get_fuzzy_matches("Hello")
        self.assertEqual(len(matches), 0)

    def test_add_empty_source(self):
        self.tm.add_translation("", "vacio")
        matches = self.tm.get_fuzzy_matches("")
        self.assertEqual(len(matches), 0)

    def test_add_duplicate(self):
        self.tm.add_translation("Hello", "Hola")
        self.tm.add_translation("Hello", "¡Hola!")
        matches = self.tm.get_fuzzy_matches("Hello")
        self.assertEqual(matches[0]["target"], "¡Hola!")


class TestGlossary(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmp_dir.name, "glossary.db")
        self.gl = Glossary(self.db_path)

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_add_and_check(self):
        self.gl.add_term("cat", "gato", "feline companion")
        matches = self.gl.check_segment("My cat is sleeping.")
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["source"], "cat")
        self.assertEqual(matches[0]["target"], "gato")

    def test_multi_word_term(self):
        self.gl.add_term("quick brown fox", "zorro marrón rápido")
        matches = self.gl.check_segment("The quick brown fox jumps.")
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["source"], "quick brown fox")

    def test_word_boundary_no_match(self):
        self.gl.add_term("cat", "gato")
        matches = self.gl.check_segment("Concatenation is a concept.")
        self.assertEqual(len(matches), 0)

    def test_case_insensitive_match(self):
        self.gl.add_term("Cat", "Gato")
        matches = self.gl.check_segment("My CAT is sleeping.")
        self.assertEqual(len(matches), 1)

    def test_remove_term(self):
        self.gl.add_term("dog", "perro")
        self.gl.remove_term("dog")
        matches = self.gl.check_segment("My dog runs.")
        self.assertEqual(len(matches), 0)

    def test_get_all_terms(self):
        self.gl.add_term("a", "1")
        self.gl.add_term("b", "2")
        terms = self.gl.get_all_terms()
        self.assertEqual(len(terms), 2)

    def test_check_empty_text(self):
        matches = self.gl.check_segment("")
        self.assertEqual(len(matches), 0)
        matches = self.gl.check_segment(None)
        self.assertEqual(len(matches), 0)

    def test_add_empty_term(self):
        self.gl.add_term("", "test")
        self.gl.add_term("test", "")
        terms = self.gl.get_all_terms()
        self.assertEqual(len(terms), 0)

    def test_update_existing(self):
        self.gl.add_term("cat", "gato")
        self.gl.add_term("cat", "michi")
        matches = self.gl.check_segment("My cat is here.")
        self.assertEqual(matches[0]["target"], "michi")


class TestSegmentation(unittest.TestCase):
    def test_basic_split(self):
        result = advanced_segmenter("Hello. How are you? I'm fine.")
        self.assertGreaterEqual(len(result), 2)

    def test_exception_no_split(self):
        result = advanced_segmenter("Dr. Smith went to the store.")
        self.assertEqual(len(result), 1)

    def test_multiple_exceptions(self):
        result = advanced_segmenter("Mr. and Mrs. Jones arrived. Dr. Brown came too.")
        self.assertEqual(len(result), 2)

    def test_empty_text(self):
        result = advanced_segmenter("")
        self.assertEqual(result, [])

    def test_no_splitters(self):
        result = advanced_segmenter("Hello world no punctuation here")
        self.assertEqual(len(result), 1)

    def test_custom_rules(self):
        rules = [
            {"pattern": ".", "break_after": True, "case_sensitive": False, "whole_word": False},
            {"pattern": "Inc", "break_after": False, "case_sensitive": True, "whole_word": True},
        ]
        result = advanced_segmenter("Hello Inc. World. Next sentence.", rules)
        self.assertEqual(len(result), 2)

    def test_semicolon_split(self):
        result = advanced_segmenter("First part; second part.")
        self.assertEqual(len(result), 2)

    def test_colon_split(self):
        result = advanced_segmenter("Note: important text here.")
        self.assertEqual(len(result), 2)


class TestTagUtils(unittest.TestCase):
    def test_extract_all_tags(self):
        tags = extract_all_tags("Hello <b>world</b>!")
        self.assertIn("<b>", tags)
        self.assertIn("</b>", tags)

    def test_extract_no_tags(self):
        tags = extract_all_tags("Hello world")
        self.assertEqual(tags, [])

    def test_extract_none_text(self):
        tags = extract_all_tags(None)
        self.assertEqual(tags, [])

    def test_apply_and_restore(self):
        tags = ["<b>", "</b>"]
        text = "<b>Hello</b>"
        applied = apply_tags(text, tags)
        self.assertIn(PH_L, applied)
        self.assertIn(PH_R, applied)
        restored = restore_tags(applied, tags)
        self.assertEqual(restored, text)

    def test_restore_no_tags(self):
        result = restore_tags("Hello world", [])
        self.assertEqual(result, "Hello world")

    def test_restore_none_text(self):
        result = restore_tags(None, ["<b>"])
        self.assertIsNone(result)

    def test_apply_no_text(self):
        result = apply_tags("", ["<b>"])
        self.assertEqual(result, "")

    def test_apply_no_taglist(self):
        result = apply_tags("Hello", None)
        self.assertEqual(result, "Hello")

    def test_unknown_tag_index(self):
        tags = ["<b>"]
        applied = apply_tags("<i>text</i>", tags)
        restored = restore_tags(applied, tags)
        self.assertIn("<i>", restored)
        self.assertIn("</i>", restored)

    def test_unique_tags(self):
        tags = extract_all_tags("<b><b><i></b></i>")
        self.assertEqual(len(tags), 4)

    def test_extract_incomplete_open_tag(self):
        tags = extract_all_tags("<b no closing angle")
        self.assertEqual(tags, [])

    def test_extract_incomplete_close_tag(self):
        tags = extract_all_tags("b> without opening")
        self.assertEqual(tags, [])

    def test_extract_bare_less_than(self):
        tags = extract_all_tags("Hello < world")
        self.assertEqual(tags, [])

    def test_extract_empty_angle_brackets(self):
        tags = extract_all_tags("<>")
        self.assertEqual(tags, [])

    def test_apply_with_incomplete_tag_preserved(self):
        text = "<b>hello</b"
        tags = ["<b>"]
        result = apply_tags(text, tags)
        self.assertIn("</b", result)
        restored = restore_tags(result, tags)
        self.assertEqual(restored, text)

    def test_apply_mixed_complete_and_incomplete_tags(self):
        text = "<b>Hello</b <i>world"
        tags = extract_all_tags(text)
        self.assertIn("<b>", tags)
        self.assertNotIn("</b", tags)
        self.assertNotIn("<i>", tags)
        applied = apply_tags(text, tags)
        restored = restore_tags(applied, tags)
        self.assertEqual(restored, text)


class TestMakeSegmentsFromTexts(unittest.TestCase):
    def test_basic(self):
        segs = make_segments_from_texts(["Hello", "World"], notes_prefix="Line ")
        self.assertEqual(len(segs), 2)
        self.assertEqual(segs[0]["source"], "Hello")
        self.assertEqual(segs[0]["notes"], "Line 1")
        self.assertEqual(segs[1]["source"], "World")

    def test_empty_text_skipped(self):
        segs = make_segments_from_texts(["Hello", "", "World"])
        self.assertEqual(len(segs), 2)

    def test_with_locations(self):
        locs = [{"line": 0}, {"line": 2}]
        segs = make_segments_from_texts(["Hello", "World"], source_locations=locs)
        self.assertEqual(segs[0]["source_location"], {"line": 0})
        self.assertEqual(segs[1]["source_location"], {"line": 2})

    def test_tag_extraction(self):
        segs = make_segments_from_texts(["<b>Hello</b>"])
        self.assertIn("<b>", segs[0]["all_tags"])
        self.assertIn("</b>", segs[0]["all_tags"])


class TestFileHandler(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.handler = CATFileHandler()

    def tearDown(self):
        self.tmp_dir.cleanup()

    def _make_po(self, content):
        path = os.path.join(self.tmp_dir.name, "test.po")
        with open(path, "w", encoding="utf-8") as f:
            f.write(content.strip())
        return path

    def test_load_po(self):
        path = self._make_po("""msgid "Hello"
msgstr "Hola"
msgid "World"
msgstr "Mundo"
""")
        segments = self.handler.load_file(path)
        self.assertGreater(len(segments), 0)

    def test_load_nonexistent(self):
        with self.assertRaises(FileNotFoundError):
            self.handler.load_file("nonexistent.po")

    def test_load_unsupported(self):
        path = os.path.join(self.tmp_dir.name, "test.xyz")
        with open(path, "w") as f:
            f.write("data")
        with self.assertRaises(ValueError):
            self.handler.load_file(path)

    def test_save_po(self):
        path = self._make_po("""msgid "Hello"
msgstr ""
""")
        segments = self.handler.load_file(path)
        segments[0]["target"] = "Hola"
        save_path = os.path.join(self.tmp_dir.name, "output.po")
        self.handler.save_file(save_path)
        self.assertTrue(os.path.exists(save_path))
        with open(save_path, encoding="utf-8") as f:
            content = f.read()
        self.assertIn("Hola", content)

    def test_save_no_segments(self):
        with self.assertRaises(ValueError):
            self.handler.save_file("out.po")

    def test_atomic_save(self):
        path = self._make_po("""msgid "Hello"
msgstr ""
""")
        self.handler.load_file(path)
        save_path = os.path.join(self.tmp_dir.name, "atomic.po")
        self.handler.save_file(save_path)
        self.assertTrue(os.path.exists(save_path))

    def test_convert_to_po(self):
        txt_path = os.path.join(self.tmp_dir.name, "test.txt")
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write("Hello\nWorld")
        po_out = os.path.join(self.tmp_dir.name, "out.po")
        convert_to_po(txt_path, po_out)
        self.assertTrue(os.path.exists(po_out))
        with open(po_out, encoding="utf-8") as f:
            content = f.read()
        self.assertIn("Hello", content)

    def test_render_no_segments(self):
        with self.assertRaises(ValueError):
            self.handler.render_translated("out.txt")


class TestMCatProjectManager(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmp_dir.name, "test.mcat.db")

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_create_project(self):
        MCatProjectManager.create_project_file(self.db_path, "en", "es")
        self.assertTrue(os.path.exists(self.db_path))

    def test_create_project_auto_extension(self):
        path = os.path.join(self.tmp_dir.name, "test")
        MCatProjectManager.create_project_file(path, "en", "es")
        self.assertTrue(os.path.exists(path + ".mcat.db"))

    def test_import_and_get_stream(self):
        MCatProjectManager.create_project_file(self.db_path, "en", "es")
        segments = [
            {"file_id": "test.txt", "source": "Hello", "target": "Hola", "status": "Confirmed", "match_score": 100},
        ]
        MCatProjectManager.import_extracted_segments(self.db_path, segments)
        rows = MCatProjectManager.get_editor_stream(self.db_path)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["source_text"], "Hello")
        self.assertEqual(rows[0]["target_text"], "Hola")

    def test_get_stream_filtered(self):
        MCatProjectManager.create_project_file(self.db_path, "en", "es")
        segments = [
            {"file_id": "a.txt", "source": "Hello", "target": "", "status": "Untranslated", "match_score": 0},
            {"file_id": "a.txt", "source": "World", "target": "Mundo", "status": "Confirmed", "match_score": 100},
        ]
        MCatProjectManager.import_extracted_segments(self.db_path, segments)
        rows = MCatProjectManager.get_editor_stream(self.db_path, filter_status="Confirmed")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["source_text"], "World")

    def test_update_segment(self):
        MCatProjectManager.create_project_file(self.db_path, "en", "es")
        segments = [
            {"file_id": "a.txt", "source": "Hello", "target": "", "status": "Untranslated", "match_score": 0},
        ]
        MCatProjectManager.import_extracted_segments(self.db_path, segments)
        rows = MCatProjectManager.get_editor_stream(self.db_path)
        unit_id = rows[0]["id"]
        MCatProjectManager.update_segment_translation(self.db_path, unit_id, "Hola", "Confirmed")
        rows = MCatProjectManager.get_editor_stream(self.db_path)
        self.assertEqual(rows[0]["target_text"], "Hola")
        self.assertEqual(rows[0]["status"], "Confirmed")


class TestTextHandler(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_load_and_render(self):
        from cat_tool.formats.text import TextHandler
        txt_path = os.path.join(self.tmp_dir.name, "test.txt")
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write("Hello\nWorld\nFoo")
        handler = TextHandler()
        segments = handler.load(txt_path)
        self.assertEqual(len(segments), 3)
        segments[0]["target"] = "Hola"
        segments[1]["target"] = "Mundo"
        out_path = os.path.join(self.tmp_dir.name, "out.txt")
        handler.render(txt_path, segments, out_path)
        with open(out_path, encoding="utf-8") as f:
            content = f.read()
        self.assertIn("Hola", content)
        self.assertIn("Mundo", content)


class TestMcatDbHandler(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmp_dir.name, "test.mcat.db")
        MCatProjectManager.create_project_file(self.db_path, "en", "es")

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_load(self):
        from cat_tool.formats.mcatdb import McatDbHandler
        MCatProjectManager.import_extracted_segments(self.db_path, [
            {"file_id": "f.txt", "source": "Hello", "target": "Hola", "status": "Confirmed", "match_score": 100},
        ])
        handler = McatDbHandler()
        segments = handler.load(self.db_path)
        self.assertEqual(len(segments), 1)
        self.assertEqual(segments[0]["source"], "Hello")
        self.assertEqual(segments[0]["target"], "Hola")
        self.assertFalse(segments[0]["fuzzy"])
        self.assertTrue(segments[0]["translated"])

    def test_load_with_tags(self):
        from cat_tool.formats.mcatdb import McatDbHandler
        conn = sqlite3.connect(self.db_path)
        conn.executescript(SCHEMA_SQL)
        conn.execute("INSERT INTO translation_units (file_id, source_text, target_text) VALUES (?, ?, ?)",
                     ("f.txt", "<b>Hello</b>", "<b>Hola</b>"))
        conn.commit()
        conn.close()
        segments = McatDbHandler().load(self.db_path)
        self.assertEqual(len(segments), 1)
        self.assertIn("<b>", segments[0]["all_tags"])

    def test_save(self):
        from cat_tool.formats.mcatdb import McatDbHandler
        segs = [{
            "index": 0, "source": "Hello", "target": "Hola",
            "all_tags": [], "source_clean": "Hello", "target_clean": "Hola",
            "fuzzy": False, "translated": True, "locations": "f.txt",
            "notes": "", "source_location": {}, "store": None, "unit": None,
            "match_score": 100,
        }]
        out_path = os.path.join(self.tmp_dir.name, "out.mcat.db")
        McatDbHandler().save(segs, out_path)
        self.assertTrue(os.path.exists(out_path))
        loaded = McatDbHandler().load(out_path)
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0]["target"], "Hola")

    def test_save_empty_raises(self):
        from cat_tool.formats.mcatdb import McatDbHandler
        with self.assertRaises(ValueError):
            McatDbHandler().save([], "out.mcat.db")

    def test_render_copies(self):
        from cat_tool.formats.mcatdb import McatDbHandler
        out_path = os.path.join(self.tmp_dir.name, "copy.mcat.db")
        McatDbHandler().render(self.db_path, [], out_path)
        self.assertTrue(os.path.exists(out_path))


if __name__ == "__main__":
    unittest.main()
