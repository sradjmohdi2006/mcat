import unittest
import os
import tempfile
import json
import shutil
import sys

from cat_tool.project import Project
from cat_tool.file_handler import CATFileHandler
from cat_tool.formats.mqxliif import MqxliffHandler
from cat_tool.formats.sdlxliff import SdlxliffHandler
from cat_tool.formats.text import TextHandler
from cat_tool.formats._text_base import make_segments_from_texts


# ========================== PROJECT TESTS ==========================

class TestProject(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def test_new_project(self):
        p = Project()
        p.new("Test Proj", "en", "es", ["a.txt", "b.txt"])
        self.assertEqual(p.name, "Test Proj")
        self.assertEqual(p.source_lang, "en")
        self.assertEqual(p.target_lang, "es")
        self.assertEqual(len(p.source_files), 2)
        self.assertTrue(p.created_at)
        self.assertTrue(p.modified_at)

    def test_save_and_load(self):
        p = Project()
        p.new("SaveTest", "fr", "de", [])
        proj_path = os.path.join(self.tmp.name, "test.mcatproj")
        p.save(proj_path)
        self.assertTrue(os.path.exists(proj_path))
        loaded = Project.load(proj_path)
        self.assertEqual(loaded.name, "SaveTest")
        self.assertEqual(loaded.source_lang, "fr")
        self.assertEqual(loaded.target_lang, "de")

    def test_save_no_path_raises(self):
        p = Project()
        p.new("NoPath", "en", "es", [])
        with self.assertRaises(ValueError):
            p.save()

    def test_to_dict_roundtrip(self):
        p = Project()
        p.new("DictTest", "en", "es", ["f1.txt"])
        d = p.to_dict()
        self.assertEqual(d["version"], 1)
        self.assertEqual(d["name"], "DictTest")
        p2 = Project.from_dict(d)
        self.assertEqual(p2.name, "DictTest")
        self.assertEqual(p2.source_lang, "en")

    def test_default_dir(self):
        d = Project.default_dir()
        self.assertTrue(os.path.isabs(d))

    def test_recent_projects(self):
        Project.add_recent("/fake/path", "FakeProj")
        recents = Project.get_recent()
        found = any(r.get("path") == "/fake/path" for r in recents)
        self.assertTrue(found)
        self.assertLessEqual(len(recents), 10)

    def test_str(self):
        p = Project()
        p.new("StrTest", "en", "es", [])
        s = str(p)
        self.assertIn("StrTest", s)
        self.assertIn("en", s)

    def test_omegat_save_and_load(self):
        src_file = os.path.join(self.tmp.name, "doc.txt")
        with open(src_file, "w", encoding="utf-8") as f:
            f.write("Hello")
        p = Project()
        p.new("OmegaTTest", "en", "es", [src_file])
        omegat_dir = os.path.join(self.tmp.name, "OmegaTTest")
        p.save_as_omegat(omegat_dir)
        self.assertTrue(os.path.exists(os.path.join(omegat_dir, "omegat.project")))
        self.assertTrue(os.path.exists(os.path.join(omegat_dir, "source", "doc.txt")))
        loaded = Project.load_omegat(omegat_dir)
        self.assertEqual(loaded.name, "OmegaTTest")
        self.assertEqual(loaded.source_lang, "en")
        self.assertEqual(loaded.target_lang, "es")
        self.assertIn("doc.txt", loaded.source_files[0])

    def test_omegat_load_raises_on_missing(self):
        with self.assertRaises(FileNotFoundError):
            Project.load_omegat("nonexistent_dir")

    def test_memoq_save_and_load(self):
        src_file = os.path.join(self.tmp.name, "doc.txt")
        with open(src_file, "w", encoding="utf-8") as f:
            f.write("Hello")
        p = Project()
        p.new("MemoQTest", "en", "es", [src_file])

        handler = CATFileHandler()
        handler.segments = make_segments_from_texts(["Hello"], notes_prefix="")
        handler.segments[0]["target"] = "Hola"

        memoq_dir = os.path.join(self.tmp.name, "memoq_out")
        p.save_as_memoq(memoq_dir, handler)
        self.assertTrue(os.path.exists(os.path.join(memoq_dir, "manifest.xml")))
        self.assertTrue(os.path.exists(os.path.join(memoq_dir, "source", "doc.txt")))
        self.assertTrue(os.path.exists(os.path.join(memoq_dir, "target", "MemoQTest.mqxliff")))

        loaded = Project.load_memoq(memoq_dir)
        self.assertEqual(loaded.name, "MemoQTest")
        self.assertEqual(loaded.source_lang, "en")
        self.assertEqual(loaded.target_lang, "es")
        self.assertGreater(len(loaded.mqxliff_files), 0)

    def test_memoq_load_raises_on_missing(self):
        with self.assertRaises(FileNotFoundError):
            Project.load_memoq("nonexistent_dir")

    def test_load_omegat_from_minimal_xml(self):
        omegat_dir = os.path.join(self.tmp.name, "minimal_omegat")
        os.makedirs(omegat_dir)
        os.makedirs(os.path.join(omegat_dir, "source"))
        et = ET = __import__("xml.etree.ElementTree", fromlist=["ElementTree"])
        root = et.Element("omegat")
        pe = et.SubElement(root, "project")
        et.SubElement(pe, "source_lang").text = "EN-US"
        et.SubElement(pe, "target_lang").text = "FR"
        tree = et.ElementTree(root)
        tree.write(os.path.join(omegat_dir, "omegat.project"), encoding="utf-8", xml_declaration=True)
        loaded = Project.load_omegat(omegat_dir)
        self.assertEqual(loaded.source_lang, "en-us")
        self.assertEqual(loaded.target_lang, "fr")

    def test_load_omegat_missing_project_element(self):
        omegat_dir = os.path.join(self.tmp.name, "bad_omegat")
        os.makedirs(omegat_dir)
        et = ET = __import__("xml.etree.ElementTree", fromlist=["ElementTree"])
        root = et.Element("omegat")
        tree = et.ElementTree(root)
        tree.write(os.path.join(omegat_dir, "omegat.project"), encoding="utf-8", xml_declaration=True)
        with self.assertRaises(ValueError):
            Project.load_omegat(omegat_dir)


# ========================== MQXLIFF TESTS ==========================

class TestMqxliffHandler(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def _make_mqxliff(self, content):
        path = os.path.join(self.tmp.name, "test.mqxliff")
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return path

    def test_load_simple(self):
        xml = """<?xml version="1.0"?>
<xliff xmlns="urn:oasis:names:tc:xliff:document:1.2" version="1.2">
  <file original="test" source-language="en" target-language="es">
    <body>
      <trans-unit id="1">
        <source>Hello</source>
        <target>Hola</target>
      </trans-unit>
    </body>
  </file>
</xliff>"""
        path = self._make_mqxliff(xml)
        segs = MqxliffHandler().load(path)
        self.assertEqual(len(segs), 1)
        self.assertEqual(segs[0]["source"], "Hello")
        self.assertEqual(segs[0]["target"], "Hola")
        self.assertTrue(segs[0]["translated"])

    def test_load_empty_target(self):
        xml = """<?xml version="1.0"?>
<xliff xmlns="urn:oasis:names:tc:xliff:document:1.2" version="1.2">
  <file original="test" source-language="en" target-language="es">
    <body>
      <trans-unit id="1">
        <source>Hello</source>
        <target></target>
      </trans-unit>
    </body>
  </file>
</xliff>"""
        path = self._make_mqxliff(xml)
        segs = MqxliffHandler().load(path)
        self.assertEqual(len(segs), 1)
        self.assertEqual(segs[0]["target"], "")
        self.assertFalse(segs[0]["translated"])

    def test_load_missing_body_raises(self):
        xml = """<?xml version="1.0"?>
<xliff xmlns="urn:oasis:names:tc:xliff:document:1.2" version="1.2">
  <file original="test" source-language="en" target-language="es">
  </file>
</xliff>"""
        path = self._make_mqxliff(xml)
        with self.assertRaises(ValueError):
            MqxliffHandler().load(path)

    def test_save_and_reload(self):
        segs = [{
            "index": 0, "source": "Hello", "target": "Hola",
            "source_clean": "Hello", "target_clean": "Hola",
            "all_tags": [], "notes": "",
            "fuzzy": False, "translated": True,
            "locations": "", "store": None, "unit": None,
        }]
        out = os.path.join(self.tmp.name, "out.mqxliff")
        MqxliffHandler().save(segs, out, src_lang="en", tgt_lang="es")
        self.assertTrue(os.path.exists(out))
        reloaded = MqxliffHandler().load(out)
        self.assertEqual(len(reloaded), 1)
        self.assertEqual(reloaded[0]["source"], "Hello")
        self.assertEqual(reloaded[0]["target"], "Hola")

    def test_save_no_target(self):
        segs = [{
            "index": 0, "source": "Hello", "target": "",
            "source_clean": "Hello", "target_clean": "",
            "all_tags": [], "notes": "",
            "fuzzy": False, "translated": False,
            "locations": "", "store": None, "unit": None,
        }]
        out = os.path.join(self.tmp.name, "empty.mqxliff")
        MqxliffHandler().save(segs, out)
        self.assertTrue(os.path.exists(out))
        reloaded = MqxliffHandler().load(out)
        self.assertEqual(reloaded[0]["target"], "")

    def test_load_missing_source_element(self):
        xml = """<?xml version="1.0"?>
<xliff xmlns="urn:oasis:names:tc:xliff:document:1.2" version="1.2">
  <file original="test" source-language="en" target-language="es">
    <body>
      <trans-unit id="1">
        <target>Hola</target>
      </trans-unit>
    </body>
  </file>
</xliff>"""
        path = self._make_mqxliff(xml)
        segs = MqxliffHandler().load(path)
        self.assertEqual(len(segs), 0)

    def test_load_missing_target_element(self):
        xml = """<?xml version="1.0"?>
<xliff xmlns="urn:oasis:names:tc:xliff:document:1.2" version="1.2">
  <file original="test" source-language="en" target-language="es">
    <body>
      <trans-unit id="1">
        <source>Hello</source>
      </trans-unit>
    </body>
  </file>
</xliff>"""
        path = self._make_mqxliff(xml)
        segs = MqxliffHandler().load(path)
        self.assertEqual(len(segs), 1)
        self.assertEqual(segs[0]["target"], "")
        self.assertFalse(segs[0]["translated"])

    def test_load_source_with_escaped_tags(self):
        xml = """<?xml version="1.0"?>
<xliff xmlns="urn:oasis:names:tc:xliff:document:1.2" version="1.2">
  <file original="test" source-language="en" target-language="es">
    <body>
      <trans-unit id="1">
        <source>&lt;b&gt;Hello</source>
        <target>&lt;b&gt;Hola</target>
      </trans-unit>
    </body>
  </file>
</xliff>"""
        path = self._make_mqxliff(xml)
        segs = MqxliffHandler().load(path)
        self.assertEqual(len(segs), 1)
        self.assertEqual(segs[0]["source"], "<b>Hello")
        self.assertIn("<b>", segs[0]["all_tags"])

    def test_load_target_with_escaped_incomplete_tag(self):
        xml = """<?xml version="1.0"?>
<xliff xmlns="urn:oasis:names:tc:xliff:document:1.2" version="1.2">
  <file original="test" source-language="en" target-language="es">
    <body>
      <trans-unit id="1">
        <source>Hello</source>
        <target>Hola&lt;/b</target>
      </trans-unit>
    </body>
  </file>
</xliff>"""
        path = self._make_mqxliff(xml)
        segs = MqxliffHandler().load(path)
        self.assertEqual(len(segs), 1)
        self.assertEqual(segs[0]["target"], "Hola</b")
        self.assertTrue(segs[0]["translated"])

    def test_load_mixed_escaped_and_plain_tags(self):
        xml = """<?xml version="1.0"?>
<xliff xmlns="urn:oasis:names:tc:xliff:document:1.2" version="1.2">
  <file original="test" source-language="en" target-language="es">
    <body>
      <trans-unit id="1">
        <source>&lt;b&gt;Hello world</source>
        <target>&lt;b&gt;Hola mundo</target>
      </trans-unit>
    </body>
  </file>
</xliff>"""
        path = self._make_mqxliff(xml)
        segs = MqxliffHandler().load(path)
        self.assertEqual(len(segs), 1)
        self.assertIn("<b>", segs[0]["all_tags"])
        self.assertEqual(len(segs[0]["all_tags"]), 1)


# ========================== SDLXLIFF TESTS ==========================

class TestSdlxliffHandler(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def _make_sdlxliff(self, content):
        path = os.path.join(self.tmp.name, "test.sdlxliff")
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return path

    def test_load_simple(self):
        xml = """<?xml version="1.0"?>
<xliff xmlns="urn:oasis:names:tc:xliff:document:1.2"
       xmlns:sdl="http://sdl.com/FileTypes/SdlXliff/1.0" version="1.2">
  <file original="test" datatype="x-sdlfilterframework2" source-language="en" target-language="es">
    <header/>
    <body>
      <trans-unit id="1">
        <source>Hello</source>
        <seg-source><mrk mtype="seg" mid="1">Hello</mrk></seg-source>
        <target><mrk mtype="seg" mid="1">Hola</mrk></target>
        <sdl:seg-defs><sdl:seg id="1" conf="Translated"/></sdl:seg-defs>
      </trans-unit>
    </body>
  </file>
</xliff>"""
        path = self._make_sdlxliff(xml)
        segs = SdlxliffHandler().load(path)
        self.assertEqual(len(segs), 1)
        self.assertEqual(segs[0]["source"], "Hello")
        self.assertEqual(segs[0]["target"], "Hola")
        self.assertTrue(segs[0]["translated"])

    def test_load_skips_translate_no(self):
        xml = """<?xml version="1.0"?>
<xliff xmlns="urn:oasis:names:tc:xliff:document:1.2"
       xmlns:sdl="http://sdl.com/FileTypes/SdlXliff/1.0" version="1.2">
  <file original="test" datatype="x-sdlfilterframework2" source-language="en" target-language="es">
    <header/>
    <body>
      <trans-unit id="1" translate="no">
        <source>Skip me</source>
      </trans-unit>
      <trans-unit id="2">
        <source>Hello</source>
        <seg-source><mrk mtype="seg" mid="1">Hello</mrk></seg-source>
        <target><mrk mtype="seg" mid="1">Hola</mrk></target>
        <sdl:seg-defs><sdl:seg id="1" conf="Translated"/></sdl:seg-defs>
      </trans-unit>
    </body>
  </file>
</xliff>"""
        path = self._make_sdlxliff(xml)
        segs = SdlxliffHandler().load(path)
        self.assertEqual(len(segs), 1)
        self.assertEqual(segs[0]["source"], "Hello")

    def test_load_skip_no_source(self):
        xml = """<?xml version="1.0"?>
<xliff xmlns="urn:oasis:names:tc:xliff:document:1.2"
       xmlns:sdl="http://sdl.com/FileTypes/SdlXliff/1.0" version="1.2">
  <file original="test" datatype="x-sdlfilterframework2" source-language="en" target-language="es">
    <header/>
    <body>
      <trans-unit id="1">
        <seg-source><mrk mtype="seg" mid="1"></mrk></seg-source>
      </trans-unit>
    </body>
  </file>
</xliff>"""
        path = self._make_sdlxliff(xml)
        segs = SdlxliffHandler().load(path)
        self.assertEqual(len(segs), 0)

    def test_save_and_reload(self):
        segs = [{
            "index": 0, "source": "Hello", "target": "Hola",
            "source_clean": "Hello", "target_clean": "Hola",
            "all_tags": [], "notes": "",
            "fuzzy": False, "translated": True,
            "locations": "", "store": None, "unit": None,
        }]
        out = os.path.join(self.tmp.name, "out.sdlxliff")
        SdlxliffHandler().save(segs, out, src_lang="en", tgt_lang="es")
        self.assertTrue(os.path.exists(out))
        reloaded = SdlxliffHandler().load(out)
        self.assertEqual(len(reloaded), 1)
        self.assertEqual(reloaded[0]["source"], "Hello")
        self.assertEqual(reloaded[0]["target"], "Hola")

    def test_save_without_target(self):
        segs = [{
            "index": 0, "source": "Hello", "target": "",
            "source_clean": "Hello", "target_clean": "",
            "all_tags": [], "notes": "",
            "fuzzy": False, "translated": False,
            "locations": "", "store": None, "unit": None,
        }]
        out = os.path.join(self.tmp.name, "empty.sdlxliff")
        SdlxliffHandler().save(segs, out)
        self.assertTrue(os.path.exists(out))
        reloaded = SdlxliffHandler().load(out)
        self.assertEqual(reloaded[0]["target"], "")

    def test_target_without_mrk(self):
        xml = """<?xml version="1.0"?>
<xliff xmlns="urn:oasis:names:tc:xliff:document:1.2"
       xmlns:sdl="http://sdl.com/FileTypes/SdlXliff/1.0" version="1.2">
  <file original="test" datatype="x-sdlfilterframework2" source-language="en" target-language="es">
    <header/>
    <body>
      <trans-unit id="1">
        <source>Hello</source>
        <seg-source><mrk mtype="seg" mid="1">Hello</mrk></seg-source>
        <target>Hola</target>
        <sdl:seg-defs><sdl:seg id="1" conf="Translated"/></sdl:seg-defs>
      </trans-unit>
    </body>
  </file>
</xliff>"""
        path = self._make_sdlxliff(xml)
        segs = SdlxliffHandler().load(path)
        self.assertEqual(len(segs), 1)
        self.assertEqual(segs[0]["target"], "Hola")

    def test_load_source_with_escaped_tags_in_mrk(self):
        xml = """<?xml version="1.0"?>
<xliff xmlns="urn:oasis:names:tc:xliff:document:1.2"
       xmlns:sdl="http://sdl.com/FileTypes/SdlXliff/1.0" version="1.2">
  <file original="test" datatype="x-sdlfilterframework2" source-language="en" target-language="es">
    <header/>
    <body>
      <trans-unit id="1">
        <source>&lt;b&gt;Hello</source>
        <seg-source><mrk mtype="seg" mid="1">&lt;b&gt;Hello</mrk></seg-source>
        <target><mrk mtype="seg" mid="1">&lt;b&gt;Hola</mrk></target>
        <sdl:seg-defs><sdl:seg id="1" conf="Translated"/></sdl:seg-defs>
      </trans-unit>
    </body>
  </file>
</xliff>"""
        path = self._make_sdlxliff(xml)
        segs = SdlxliffHandler().load(path)
        self.assertEqual(len(segs), 1)
        self.assertEqual(segs[0]["source"], "<b>Hello")
        self.assertIn("<b>", segs[0]["all_tags"])

    def test_load_target_with_escaped_incomplete_tag_in_mrk(self):
        xml = """<?xml version="1.0"?>
<xliff xmlns="urn:oasis:names:tc:xliff:document:1.2"
       xmlns:sdl="http://sdl.com/FileTypes/SdlXliff/1.0" version="1.2">
  <file original="test" datatype="x-sdlfilterframework2" source-language="en" target-language="es">
    <header/>
    <body>
      <trans-unit id="1">
        <source>Hello</source>
        <seg-source><mrk mtype="seg" mid="1">Hello</mrk></seg-source>
        <target><mrk mtype="seg" mid="1">Hola&lt;/b</mrk></target>
        <sdl:seg-defs><sdl:seg id="1" conf="Translated"/></sdl:seg-defs>
      </trans-unit>
    </body>
  </file>
</xliff>"""
        path = self._make_sdlxliff(xml)
        segs = SdlxliffHandler().load(path)
        self.assertEqual(len(segs), 1)
        self.assertEqual(segs[0]["target"], "Hola</b")

    def test_load_missing_seg_source_and_source(self):
        xml = """<?xml version="1.0"?>
<xliff xmlns="urn:oasis:names:tc:xliff:document:1.2"
       xmlns:sdl="http://sdl.com/FileTypes/SdlXliff/1.0" version="1.2">
  <file original="test" datatype="x-sdlfilterframework2" source-language="en" target-language="es">
    <header/>
    <body>
      <trans-unit id="1">
        <target><mrk mtype="seg" mid="1">Hola</mrk></target>
      </trans-unit>
    </body>
  </file>
</xliff>"""
        path = self._make_sdlxliff(xml)
        segs = SdlxliffHandler().load(path)
        self.assertEqual(len(segs), 0)

    def test_load_plain_target_with_escaped_tag(self):
        xml = """<?xml version="1.0"?>
<xliff xmlns="urn:oasis:names:tc:xliff:document:1.2"
       xmlns:sdl="http://sdl.com/FileTypes/SdlXliff/1.0" version="1.2">
  <file original="test" datatype="x-sdlfilterframework2" source-language="en" target-language="es">
    <header/>
    <body>
      <trans-unit id="1">
        <source>Hello</source>
        <seg-source><mrk mtype="seg" mid="1">Hello</mrk></seg-source>
        <target>Hola&lt;/i&gt;</target>
        <sdl:seg-defs><sdl:seg id="1" conf="Translated"/></sdl:seg-defs>
      </trans-unit>
    </body>
  </file>
</xliff>"""
        path = self._make_sdlxliff(xml)
        segs = SdlxliffHandler().load(path)
        self.assertEqual(len(segs), 1)
        self.assertEqual(segs[0]["target"], "Hola</i>")
        self.assertIn("</i>", segs[0]["all_tags"])


# ========================== GUI SMOKE TEST ==========================

class TestGuiSmoke(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def test_create_mainwindow(self):
        from PyQt5.QtWidgets import QApplication
        app = QApplication.instance()
        existed = app is not None
        if not existed:
            app = QApplication(sys.argv)
        try:
            from cat_tool.ui import MainWindow
            win = MainWindow()
            self.assertIsNotNone(win)
            self.assertEqual(win.windowTitle()[:4], "mcat")
        finally:
            if not existed:
                pass
            app = None

    def test_load_po_file_through_handler(self):
        from PyQt5.QtWidgets import QApplication
        app = QApplication.instance()
        existed = app is not None
        if not existed:
            app = QApplication(sys.argv)
        try:
            from cat_tool.ui import MainWindow
            win = MainWindow()
            po_content = '''msgid "Hello"
msgstr "Hola"
msgid "World"
msgstr "Mundo"
'''
            po_path = os.path.join(self.tmp.name, "test.po")
            with open(po_path, "w", encoding="utf-8") as f:
                f.write(po_content)
            segs = win.state.file_handler.load_file(po_path)
            win.populate_table(segs)
            self.assertEqual(win.table.rowCount(), 2)
            self.assertEqual(win.table.item(0, 0).text(), "Hello")
        finally:
            if not existed:
                pass
            app = None

    def test_load_po_and_translate(self):
        from PyQt5.QtWidgets import QApplication
        app = QApplication.instance()
        existed = app is not None
        if not existed:
            app = QApplication(sys.argv)
        try:
            from cat_tool.ui import MainWindow
            win = MainWindow()
            po_content = '''msgid "Hello"
msgstr ""
'''
            po_path = os.path.join(self.tmp.name, "test.po")
            with open(po_path, "w", encoding="utf-8") as f:
                f.write(po_content)
            segs = win.state.file_handler.load_file(po_path)
            win.populate_table(segs)
            win.state.file_handler.segments[0]["target"] = "Hola"
            win.update_table_row_status(0, win.state.file_handler.segments[0])
            self.assertEqual(win.state.file_handler.segments[0]["target"], "Hola")
        finally:
            if not existed:
                pass
            app = None

    def test_qa_dialog_creation(self):
        from PyQt5.QtWidgets import QApplication, QDialog
        app = QApplication.instance()
        existed = app is not None
        if not existed:
            app = QApplication(sys.argv)
        try:
            from cat_tool.qa import QAIssue
            from cat_tool.ui import QADialog
            issues = [
                QAIssue("error", "Missing translation", 0, "Hello", "", "No target"),
            ]
            dlg = QADialog(issues)
            self.assertIsInstance(dlg, QDialog)
        finally:
            if not existed:
                pass
            app = None

    def test_shortcuts_dialog_creation(self):
        from PyQt5.QtWidgets import QApplication, QDialog
        app = QApplication.instance()
        existed = app is not None
        if not existed:
            app = QApplication(sys.argv)
        try:
            from cat_tool.ui import ShortcutsDialog
            dlg = ShortcutsDialog()
            self.assertIsInstance(dlg, QDialog)
        finally:
            if not existed:
                pass
            app = None

    def test_glossary_dialog_creation(self):
        from PyQt5.QtWidgets import QApplication, QDialog
        app = QApplication.instance()
        existed = app is not None
        if not existed:
            app = QApplication(sys.argv)
        try:
            from cat_tool.ui import GlossaryDialog
            dlg = GlossaryDialog()
            self.assertIsInstance(dlg, QDialog)
        finally:
            if not existed:
                pass
            app = None


class TestMultiFileImportDialog(unittest.TestCase):
    def setUp(self):
        from PyQt5.QtWidgets import QApplication
        self.app = QApplication.instance()
        if self.app is None:
            self.app = QApplication(sys.argv)
        self.tmp = tempfile.TemporaryDirectory()
        self.files = []
        for name in ("alpha.tmx", "beta.tmx", "gamma.tbx"):
            path = os.path.join(self.tmp.name, name)
            with open(path, "w", encoding="utf-8") as f:
                f.write("<tmx version=\"1.4\"/>")
            self.files.append(os.path.normpath(path))

    def tearDown(self):
        self.tmp.cleanup()

    def test_initial_files_are_deduplicated(self):
        from cat_tool.dialogs import MultiFileImportDialog
        dlg = MultiFileImportDialog(
            initial_files=[self.files[0], self.files[0], self.files[1]])
        self.assertEqual(dlg.files(), [self.files[0], self.files[1]])

    def test_missing_or_empty_paths_are_ignored(self):
        from cat_tool.dialogs import MultiFileImportDialog
        dlg = MultiFileImportDialog(initial_files=[
            os.path.join(self.tmp.name, "missing.tmx"), "", None])
        self.assertEqual(dlg.files(), [])

    def test_remove_selected(self):
        from cat_tool.dialogs import MultiFileImportDialog
        dlg = MultiFileImportDialog(initial_files=self.files[:2])
        dlg.file_list.item(0).setSelected(True)
        dlg.remove_selected()
        self.assertEqual(dlg.files(), [self.files[1]])

    def test_clear(self):
        from cat_tool.dialogs import MultiFileImportDialog
        dlg = MultiFileImportDialog(initial_files=self.files)
        dlg.file_list.clear()
        self.assertEqual(dlg.files(), [])

    def test_add_files(self):
        from unittest.mock import patch
        from cat_tool.dialogs import MultiFileImportDialog
        dlg = MultiFileImportDialog(file_filter="TMX Files (*.tmx)")
        with patch(
            "cat_tool.dialogs.import_dialog.QFileDialog.getOpenFileNames",
            return_value=([self.files[0], self.files[2]], ""),
        ):
            dlg.add_files()
        self.assertEqual(dlg.files(), [self.files[0], self.files[2]])

    def test_import_requires_at_least_one_file(self):
        from unittest.mock import patch
        from PyQt5.QtWidgets import QDialog
        from cat_tool.dialogs import MultiFileImportDialog
        dlg = MultiFileImportDialog()
        with patch(
            "cat_tool.dialogs.import_dialog.QMessageBox.information"
        ) as info:
            dlg._accept_if_any()
        info.assert_called_once()
        self.assertNotEqual(dlg.result(), QDialog.Accepted)

    def test_accept_with_files(self):
        from PyQt5.QtWidgets import QDialog
        from cat_tool.dialogs import MultiFileImportDialog
        dlg = MultiFileImportDialog(initial_files=[self.files[0]])
        dlg._accept_if_any()
        self.assertEqual(dlg.result(), QDialog.Accepted)


class TestLanguageCombo(unittest.TestCase):
    def setUp(self):
        from PyQt5.QtWidgets import QApplication
        self.app = QApplication.instance()
        if self.app is None:
            self.app = QApplication(sys.argv)

    def test_regional_code_falls_back_to_base_language(self):
        from PyQt5.QtWidgets import QComboBox
        from cat_tool.dialogs import fill_lang_combo
        combo = QComboBox()
        fill_lang_combo(combo, "en-US")
        self.assertEqual(combo.currentData(), "en")

    def test_unknown_code_keeps_default_selection(self):
        from PyQt5.QtWidgets import QComboBox
        from cat_tool.dialogs import fill_lang_combo
        combo = QComboBox()
        fill_lang_combo(combo, "xx-YY")
        self.assertEqual(combo.currentIndex(), 0)

    def test_lang_dialog_offers_auto_detect_when_target_missing(self):
        from cat_tool.dialogs import LangDialog
        dlg = LangDialog("en", "", 3, format_name="TBX")
        self.assertEqual(dlg.tgt_combo.currentData(), "")
        self.assertIn("Auto-detect", dlg.tgt_combo.currentText())

    def test_lang_dialog_shows_format_and_unit_label(self):
        from PyQt5.QtWidgets import QLabel
        from cat_tool.dialogs import LangDialog
        dlg = LangDialog("en", "es", 4, format_name="TMX",
                         item_label="translation units")
        self.assertEqual(dlg.windowTitle(), "TMX Language Detection")
        label_text = " ".join(child.text() for child in dlg.findChildren(QLabel))
        self.assertIn("translation units", label_text)
        self.assertIn("TMX", label_text)
        self.assertGreaterEqual(dlg.src_combo.count(), 1)


# ========================== FORMAT HANDLER INTEGRATION ==========================

class TestFileHandlerIntegration(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def _make_po(self, content):
        path = os.path.join(self.tmp.name, "test.po")
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return path

    def test_po_load_save_roundtrip(self):
        po = '''msgid "Hello"
msgstr "Hola"
msgid "World"
msgstr ""
'''
        path = self._make_po(po)
        fh = CATFileHandler()
        segs = fh.load_file(path)
        segs[0]["target"] = "¡Hola!"
        segs[1]["target"] = "Mundo"
        out = os.path.join(self.tmp.name, "out.po")
        fh.save_file(out)
        fh2 = CATFileHandler()
        segs2 = fh2.load_file(out)
        self.assertEqual(segs2[0]["target"], "¡Hola!")
        self.assertEqual(segs2[1]["target"], "Mundo")

    def test_txt_load_save_roundtrip(self):
        txt_path = os.path.join(self.tmp.name, "input.txt")
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write("Line one\nLine two\nLine three")
        fh = CATFileHandler()
        segs = fh.load_file(txt_path)
        self.assertEqual(len(segs), 3)
        segs[0]["target"] = "Línea uno"
        segs[1]["target"] = "Línea dos"
        out = os.path.join(self.tmp.name, "out.txt")
        fh.render_translated(out)
        with open(out, encoding="utf-8") as f:
            content = f.read()
        self.assertIn("Línea uno", content)
        self.assertIn("Línea dos", content)

    def test_po_convert_to_po_from_txt(self):
        from cat_tool.file_handler import convert_to_po
        txt_path = os.path.join(self.tmp.name, "source.txt")
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write("Hello\nWorld")
        po_out = os.path.join(self.tmp.name, "converted.po")
        convert_to_po(txt_path, po_out)
        self.assertTrue(os.path.exists(po_out))
        fh = CATFileHandler()
        segs = fh.load_file(po_out)
        self.assertEqual(len(segs), 2)

    def test_factory_xliff_load(self):
        xliff = """<?xml version="1.0" encoding="utf-8"?>
<xliff xmlns="urn:oasis:names:tc:xliff:document:1.2" version="1.2">
  <file source-language="en" target-language="es" datatype="plaintext" original="test.txt">
    <body>
      <trans-unit id="1">
        <source>Hello</source>
        <target>Hola</target>
      </trans-unit>
    </body>
  </file>
</xliff>"""
        path = os.path.join(self.tmp.name, "test.xlf")
        with open(path, "w", encoding="utf-8") as f:
            f.write(xliff)
        fh = CATFileHandler()
        segs = fh.load_file(path)
        self.assertGreater(len(segs), 0)
        self.assertEqual(segs[0]["source"].strip(), "Hello")

    def test_render_no_current_path_raises(self):
        fh = CATFileHandler()
        fh.segments = [{"source": "Hello", "target": "Hola"}]
        with self.assertRaises(ValueError):
            fh.render_translated("out.txt")

    def test_load_mcatdb_and_save_mcatdb_roundtrip(self):
        from cat_tool.mcat_format_manager import MCatProjectManager
        db_path = os.path.join(self.tmp.name, "proj.mcat.db")
        MCatProjectManager.create_project_file(db_path, "en", "es")
        MCatProjectManager.import_extracted_segments(db_path, [
            {"file_id": "f.txt", "source": "Hello", "target": "Hola", "status": "Confirmed", "match_score": 100},
        ])
        fh = CATFileHandler()
        segs = fh.load_file(db_path)
        self.assertEqual(len(segs), 1)
        self.assertEqual(segs[0]["source"], "Hello")
        self.assertEqual(segs[0]["target"], "Hola")
        out_db = os.path.join(self.tmp.name, "copy.mcat.db")
        fh.save_file(out_db)
        self.assertTrue(os.path.exists(out_db))
        fh2 = CATFileHandler()
        segs2 = fh2.load_file(out_db)
        self.assertEqual(segs2[0]["source"], "Hello")


# ========================== REAL DOCUMENT LOAD TESTS ==========================

class TestRealDocumentLoad(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def test_docx_load(self):
        from docx import Document
        doc = Document()
        doc.add_paragraph("Hello World")
        doc.add_paragraph("Second paragraph")
        docx_path = os.path.join(self.tmp.name, "test.docx")
        doc.save(docx_path)
        from cat_tool.formats.docx import DocxHandler
        segs = DocxHandler().load(docx_path)
        self.assertGreaterEqual(len(segs), 2)
        texts = [s["source"] for s in segs]
        self.assertIn("Hello World", texts)
        self.assertIn("Second paragraph", texts)

    def test_docx_render(self):
        from docx import Document
        doc = Document()
        doc.add_paragraph("Hello")
        docx_path = os.path.join(self.tmp.name, "test.docx")
        doc.save(docx_path)
        from cat_tool.formats.docx import DocxHandler
        handler = DocxHandler()
        segs = handler.load(docx_path)
        segs[0]["target"] = "Hola"
        out_path = os.path.join(self.tmp.name, "out.docx")
        handler.render(docx_path, segs, out_path)
        self.assertTrue(os.path.exists(out_path))
        doc2 = Document(out_path)
        texts = [p.text for p in doc2.paragraphs]
        self.assertIn("Hola", texts)

    def test_pptx_load(self):
        from pptx import Presentation
        from pptx.util import Inches
        prs = Presentation()
        slide = prs.slides.add_slide(prs.slide_layouts[6])
        txBox = slide.shapes.add_textbox(Inches(1), Inches(1), Inches(8), Inches(2))
        tf = txBox.text_frame
        tf.text = "Hello from PowerPoint"
        pptx_path = os.path.join(self.tmp.name, "test.pptx")
        prs.save(pptx_path)
        from cat_tool.formats.pptx import PptxHandler
        segs = PptxHandler().load(pptx_path)
        texts = [s["source"] for s in segs]
        self.assertIn("Hello from PowerPoint", texts)

    def test_pptx_render(self):
        from pptx import Presentation
        from pptx.util import Inches
        prs = Presentation()
        slide = prs.slides.add_slide(prs.slide_layouts[6])
        txBox = slide.shapes.add_textbox(Inches(1), Inches(1), Inches(8), Inches(2))
        tf = txBox.text_frame
        tf.text = "Hello"
        pptx_path = os.path.join(self.tmp.name, "test.pptx")
        prs.save(pptx_path)
        from cat_tool.formats.pptx import PptxHandler
        handler = PptxHandler()
        segs = handler.load(pptx_path)
        segs[0]["target"] = "Hola"
        out_path = os.path.join(self.tmp.name, "out.pptx")
        handler.render(pptx_path, segs, out_path)
        self.assertTrue(os.path.exists(out_path))
        prs2 = Presentation(out_path)
        for slide in prs2.slides:
            for shape in slide.shapes:
                if shape.has_text_frame:
                    self.assertIn("Hola", shape.text_frame.text)

    def test_xlsx_load(self):
        from openpyxl import Workbook
        wb = Workbook()
        ws = wb.active
        ws["A1"] = "Hello"
        ws["B1"] = "World"
        xlsx_path = os.path.join(self.tmp.name, "test.xlsx")
        wb.save(xlsx_path)
        from cat_tool.formats.xlsx import XlsxHandler
        segs = XlsxHandler().load(xlsx_path)
        texts = [s["source"] for s in segs]
        self.assertIn("Hello", texts)
        self.assertIn("World", texts)

    def test_xlsx_render(self):
        from openpyxl import Workbook
        wb = Workbook()
        ws = wb.active
        ws["A1"] = "Hello"
        xlsx_path = os.path.join(self.tmp.name, "test.xlsx")
        wb.save(xlsx_path)
        from cat_tool.formats.xlsx import XlsxHandler
        handler = XlsxHandler()
        segs = handler.load(xlsx_path)
        segs[0]["target"] = "Hola"
        out_path = os.path.join(self.tmp.name, "out.xlsx")
        handler.render(xlsx_path, segs, out_path)
        self.assertTrue(os.path.exists(out_path))
        from openpyxl import load_workbook
        wb2 = load_workbook(out_path)
        self.assertEqual(wb2.active["A1"].value, "Hola")


class TestBatchImportGui(unittest.TestCase):
    """Exercise the multi-file import methods in ``MainWindow``."""

    @classmethod
    def setUpClass(cls):
        from PyQt5.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def setUp(self):
        from unittest.mock import patch
        self.tmp = tempfile.TemporaryDirectory()
        self._env_patch = patch.dict(
            os.environ, {"APPDATA": self.tmp.name})
        self._env_patch.start()
        from cat_tool.ui import MainWindow
        self.win = MainWindow()

    def tearDown(self):
        self.win.cleanup()
        self.win.close()
        self.win.deleteLater()
        self._env_patch.stop()
        self.tmp.cleanup()

    def _write(self, name, content):
        path = os.path.join(self.tmp.name, name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return path

    def _tmx(self, name, pairs, srclang="en", target="es"):
        units = "".join(
            f'<tu><tuv xml:lang="{srclang}"><seg>{src}</seg></tuv>'
            f'<tuv xml:lang="{target}"><seg>{tgt}</seg></tuv></tu>'
            for src, tgt in pairs
        )
        return self._write(name, (
            '<?xml version="1.0" encoding="UTF-8"?>'
            f'<tmx version="1.4"><header srclang="{srclang}"/>'
            f'<body>{units}</body></tmx>'
        ))

    def _tbx(self, name, pairs, srclang="en", target="fr"):
        entries = "".join(
            f'<termEntry id="{i}">'
            f'<langSet xml:lang="{srclang}"><tig><term>{src}</term></tig></langSet>'
            f'<langSet xml:lang="{target}"><tig><term>{tgt}</term></tig></langSet>'
            "</termEntry>"
            for i, (src, tgt) in enumerate(pairs)
        )
        return self._write(name, (
            '<?xml version="1.0" encoding="UTF-8"?>'
            f'<tbx version="2" xml:lang="{srclang}"><text><body>'
            f"{entries}</body></text></tbx>"
        ))

    @staticmethod
    def _accepting_dialog(files):
        from unittest.mock import MagicMock, patch
        dialog = MagicMock()
        dialog.files.return_value = files
        dialog.exec_.return_value = 1  # QDialog.Accepted
        return patch("cat_tool.ui.MultiFileImportDialog",
                     return_value=dialog)

    def test_batch_tmx_into_glossary(self):
        from unittest.mock import patch
        files = [
            self._tmx("one.tmx", [("house", "casa")]),
            self._tmx("two.tmx", [("mouse", "ratón")]),
        ]
        with patch.object(
            self.win, "_ask_import_languages", return_value=("en", "es")
        ), patch("cat_tool.ui.QMessageBox.information") as info:
            self.win._import_tmx_files_to_glossary(files)
        terms = {t["source"]: t["target"]
                 for t in self.win.state.glossary.get_all_terms()}
        self.assertEqual(terms, {"house": "casa", "mouse": "ratón"})
        info.assert_called_once()

    def test_batch_tbx_into_glossary(self):
        from unittest.mock import patch
        files = [
            self._tbx("one.tbx", [("house", "maison")]),
            self._tbx("two.tbx", [("mouse", "souris")]),
        ]
        with patch.object(
            self.win, "_ask_import_languages", return_value=("en", "fr")
        ), patch("cat_tool.ui.QMessageBox.information") as info:
            self.win._import_tbx_files_to_glossary(files)
        terms = {t["source"]: t["target"]
                 for t in self.win.state.glossary.get_all_terms()}
        self.assertEqual(terms, {"house": "maison", "mouse": "souris"})
        info.assert_called_once()

    def test_batch_tmx_to_tm_imports_units(self):
        from unittest.mock import patch
        files = [
            self._tmx("memory.tmx",
                      [("Hello world", "Hola mundo"),
                       ("Good night", "Buenas noches")]),
        ]
        with patch.object(
            self.win, "_ask_import_languages", return_value=("en", "es")
        ), patch("cat_tool.ui.QMessageBox.information") as info:
            self.win._import_tmx_files_to_tm(files)
        matches = self.win.state.tm.get_fuzzy_matches("Hello world")
        self.assertEqual(matches[0]["target"], "Hola mundo")
        self.assertEqual(len(self.win.state.glossary.get_all_terms()), 0)
        info.assert_called_once()

    def test_batch_tmx_term_like_yes_goes_to_glossary(self):
        from unittest.mock import patch
        from PyQt5.QtWidgets import QMessageBox
        files = [self._tmx("terms.tmx", [("cat", "gato")])]
        with patch.object(
            self.win, "_ask_import_languages", return_value=("en", "es")
        ), patch("cat_tool.ui.QMessageBox.question",
                 return_value=QMessageBox.Yes) as question, patch(
                     "cat_tool.ui.QMessageBox.information"):
            self.win._import_tmx_files_to_tm(files)
        question.assert_called_once()
        terms = self.win.state.glossary.get_all_terms()
        self.assertEqual([(t["source"], t["target"]) for t in terms],
                         [("cat", "gato")])
        self.assertEqual(
            self.win.state.tm.get_fuzzy_matches("cat"), [])

    def test_batch_tmx_term_like_no_goes_to_tm(self):
        from unittest.mock import patch
        from PyQt5.QtWidgets import QMessageBox
        files = [self._tmx("terms.tmx", [("dog", "perro")])]
        with patch.object(
            self.win, "_ask_import_languages", return_value=("en", "es")
        ), patch("cat_tool.ui.QMessageBox.question",
                 return_value=QMessageBox.No), patch(
                     "cat_tool.ui.QMessageBox.information"):
            self.win._import_tmx_files_to_tm(files)
        matches = self.win.state.tm.get_fuzzy_matches("dog")
        self.assertEqual(matches[0]["target"], "perro")
        self.assertEqual(self.win.state.glossary.get_all_terms(), [])

    def test_batch_tmx_term_like_cancel_skips_file(self):
        from unittest.mock import patch
        from PyQt5.QtWidgets import QMessageBox
        files = [self._tmx("terms.tmx", [("bird", "pájaro")])]
        with patch.object(
            self.win, "_ask_import_languages", return_value=("en", "es")
        ), patch("cat_tool.ui.QMessageBox.question",
                 return_value=QMessageBox.Cancel), patch(
                     "cat_tool.ui.QMessageBox.information") as info:
            self.win._import_tmx_files_to_tm(files)
        info.assert_called_once()
        self.assertEqual(self.win.state.glossary.get_all_terms(), [])
        self.assertEqual(
            self.win.state.tm.get_fuzzy_matches("bird"), [])

    def test_batch_tmx_skips_empty_and_missing_files(self):
        from unittest.mock import patch
        empty = self._write(
            "empty.tmx",
            '<tmx version="1.4"><header srclang="en"/><body/></tmx>')
        missing = os.path.join(self.tmp.name, "missing.tmx")
        with patch.object(
            self.win, "_ask_import_languages", return_value=("en", "es")
        ), patch("cat_tool.ui.QMessageBox.warning") as warning:
            self.win._import_tmx_files_to_glossary([empty, missing])
        warning.assert_called_once()

    def test_batch_collection_import_creates_one_per_file(self):
        from unittest.mock import patch
        files = [
            self._tmx("legal.tmx", [("contract", "contrato")]),
            self._tmx("medical.tmx", [("fever", "fiebre")]),
        ]
        with patch(
            "cat_tool.ui.QFileDialog.getOpenFileNames",
            return_value=(files, ""),
        ), self._accepting_dialog(files), patch(
            "cat_tool.ui.QMessageBox.information"
        ) as info:
            self.win.import_collection_tmx()
        names = [c["name"]
                 for c in self.win.state.glossary.get_all_collections()]
        self.assertEqual(sorted(names), ["legal", "medical"])
        info.assert_called_once()

    def test_batch_collection_import_reports_duplicate_names(self):
        from unittest.mock import patch
        files = [self._tmx("dupe.tmx", [("one", "uno")])]
        self.win.state.glossary.create_collection("dupe")
        with patch(
            "cat_tool.ui.QFileDialog.getOpenFileNames",
            return_value=(files, ""),
        ), self._accepting_dialog(files), patch(
            "cat_tool.ui.QMessageBox.warning"
        ) as warning:
            self.win.import_collection_tmx()
        warning.assert_called_once()

    def test_import_dialog_cancel_does_nothing(self):
        from unittest.mock import MagicMock, patch
        dialog = MagicMock()
        dialog.exec_.return_value = 0  # QDialog.Rejected
        with patch(
            "cat_tool.ui.QFileDialog.getOpenFileNames",
            return_value=(["C:/tmp/one.tmx"], ""),
        ), patch("cat_tool.ui.MultiFileImportDialog", return_value=dialog), \
                patch.object(
                    self.win, "_import_tmx_files_to_glossary") as importer:
            self.win.import_tmx_to_glossary()
        importer.assert_not_called()

    def test_ask_import_languages_uses_detected_languages(self):
        from unittest.mock import patch
        info = {"source_lang": "en", "target_lang": "es", "count": 2}
        with patch("cat_tool.ui.LangDialog") as dialog:
            self.assertEqual(
                self.win._ask_import_languages(info), ("en", "es"))
        dialog.assert_not_called()

    def test_ask_import_languages_opens_dialog_for_ambiguity(self):
        from unittest.mock import MagicMock, patch
        dialog = MagicMock()
        dialog.exec_.return_value = 1
        dialog.src_combo.currentData.return_value = "en"
        dialog.tgt_combo.currentData.return_value = "fr"
        info = {"source_lang": "en", "target_lang": "es, fr", "count": 2}
        with patch("cat_tool.ui.LangDialog", return_value=dialog):
            result = self.win._ask_import_languages(info)
        self.assertEqual(result, ("en", "fr"))

    def test_ask_import_languages_cancel_returns_none(self):
        from unittest.mock import MagicMock, patch
        dialog = MagicMock()
        dialog.exec_.return_value = 0
        info = {"source_lang": "", "target_lang": "", "count": 1}
        with patch("cat_tool.ui.LangDialog", return_value=dialog):
            self.assertIsNone(self.win._ask_import_languages(info))

    def test_show_batch_result_truncates_long_error_list(self):
        from unittest.mock import patch
        errors = [f"file{i}.tmx: boom" for i in range(12)]
        with patch("cat_tool.ui.QMessageBox.warning") as warning:
            self.win._show_batch_import_result(
                "terms", 5, 12, ["skipped.tmx (empty)"], errors)
        message = warning.call_args[0][2]
        self.assertIn("...and 4 more.", message)
        self.assertIn("Skipped:", message)


class TestDialogCoverage(unittest.TestCase):
    def setUp(self):
        from PyQt5.QtWidgets import QApplication
        self.app = QApplication.instance()
        if self.app is None:
            self.app = QApplication(sys.argv)
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def test_glossary_dialog_get_data(self):
        from cat_tool.dialogs import GlossaryDialog
        dlg = GlossaryDialog()
        dlg.src_edit.setText("  house  ")
        dlg.tgt_edit.setText("  casa  ")
        dlg.desc_edit.setText("  A home.  ")
        src, tgt, desc, sl, tl = dlg.get_data()
        self.assertEqual((src, tgt, desc), ("house", "casa", "A home."))
        self.assertTrue(sl)
        self.assertTrue(tl)

    def test_new_project_dialog_data_and_clear(self):
        from cat_tool.dialogs import NewProjectDialog
        dlg = NewProjectDialog()
        dlg.name_edit.setText("  Demo  ")
        dlg.source_files = ["a.po", "b.po"]
        dlg.file_list.addItem("a.po")
        dlg.file_list.addItem("b.po")
        name, src, tgt, files = dlg.get_data()
        self.assertEqual(name, "Demo")
        self.assertEqual(src, "en")
        self.assertEqual(tgt, "es")
        self.assertEqual(files, ["a.po", "b.po"])
        dlg.clear_files()
        self.assertEqual(dlg.source_files, [])
        self.assertEqual(dlg.file_list.count(), 0)

    def test_new_project_dialog_requires_name(self):
        from unittest.mock import patch
        from PyQt5.QtWidgets import QDialog
        from cat_tool.dialogs import NewProjectDialog
        dlg = NewProjectDialog()
        with patch("PyQt5.QtWidgets.QMessageBox.warning") as warning:
            dlg._validate_and_accept()
        warning.assert_called_once()
        self.assertNotEqual(dlg.result(), QDialog.Accepted)
        dlg.name_edit.setText("Demo")
        dlg._validate_and_accept()
        self.assertEqual(dlg.result(), QDialog.Accepted)

    def test_new_project_dialog_browse_files_deduplicates(self):
        from unittest.mock import patch
        from cat_tool.dialogs import NewProjectDialog
        dlg = NewProjectDialog()
        paths = [os.path.join(self.tmp.name, "a.po"),
                 os.path.join(self.tmp.name, "b.po")]
        with patch(
            "cat_tool.dialogs.project_dialogs.QFileDialog.getOpenFileNames",
            return_value=(paths + [paths[0]], ""),
        ):
            dlg.browse_files()
            dlg.browse_files()
        self.assertEqual(dlg.source_files, paths)
        self.assertEqual(dlg.file_list.count(), 2)

    def test_settings_dialog_saves_values(self):
        from cat_tool.dialogs import SettingsDialog

        class FakeSettings(dict):
            saved = False

            def save(self):
                self.saved = True

        settings = FakeSettings(
            source_font_size=12, target_font_size=14,
            auto_save_on_segment_change=False,
            show_tag_placeholders=True,
        )
        dlg = SettingsDialog(settings)
        dlg.src_font_spin.setValue(16)
        dlg.tgt_font_spin.setValue(18)
        dlg.auto_save_cb.setChecked(True)
        dlg.show_tags_cb.setChecked(False)
        dlg._save()
        self.assertEqual(settings["source_font_size"], 16)
        self.assertEqual(settings["target_font_size"], 18)
        self.assertTrue(settings["auto_save_on_segment_change"])
        self.assertFalse(settings["show_tag_placeholders"])
        self.assertTrue(settings.saved)

    def test_project_settings_dialog_add_remove_apply(self):
        from unittest.mock import patch
        from cat_tool.dialogs import ProjectSettingsDialog

        class FakeProject:
            name = "Old"
            source_lang = "en"
            target_lang = "es"
            source_files = ["one.po"]

        project = FakeProject()
        dlg = ProjectSettingsDialog(project)
        new_path = os.path.join(self.tmp.name, "two.po")
        with patch(
            "cat_tool.dialogs.project_dialogs.QFileDialog.getOpenFileName",
            return_value=(new_path, ""),
        ):
            dlg.add_source_file()
        self.assertEqual(project.source_files, ["one.po", new_path])
        dlg.file_list.setCurrentRow(0)
        dlg.remove_source_file()
        self.assertEqual(project.source_files, [new_path])
        dlg.name_edit.setText("New name")
        dlg.apply()
        self.assertEqual(project.name, "New name")

    def test_tag_view_dialog_without_tags(self):
        from cat_tool.dialogs import TagViewDialog
        dlg = TagViewDialog({"all_tags": []}, 0)
        self.assertEqual(dlg.tag_list.count(), 1)
        self.assertFalse(
            bool(dlg.tag_list.item(0).flags() & 0x20))  # ItemIsSelectable

    def test_tag_view_dialog_inserts_placeholder(self):
        from PyQt5.QtWidgets import QTableWidget, QTableWidgetItem, QWidget
        from cat_tool.formats.tag_utils import PH_L, PH_R
        from cat_tool.dialogs import TagViewDialog

        class FakeParent(QWidget):
            def __init__(self):
                super().__init__()
                self.current_segment_index = 0
                self.table = QTableWidget(1, 2)
                self.table.setItem(0, 1, QTableWidgetItem("Existing "))

        parent = FakeParent()
        dlg = TagViewDialog({"all_tags": ["<b>"]}, 1, parent)
        dlg.tag_list.setCurrentRow(0)
        dlg._insert_selected_tag()
        self.assertEqual(parent.table.item(0, 1).text(),
                         f"Existing {PH_L}0{PH_R}")

    def test_chapter_view_copy_and_export(self):
        from unittest.mock import patch
        from cat_tool.dialogs import ChapterViewDialog
        bookmarks = [
            {"title": "Chapter One", "level": 0},
            {"title": "Section", "level": 1},
        ]
        dlg = ChapterViewDialog(bookmarks)
        dlg._copy_st_to_tt()
        self.assertEqual(dlg.table.item(0, 1).text(), "Chapter One")
        self.assertEqual(dlg.table.item(1, 1).text(), "Section")

        path = os.path.join(self.tmp.name, "chapters.csv")
        with patch(
            "PyQt5.QtWidgets.QFileDialog.getSaveFileName",
            return_value=(path, ""),
        ), patch("PyQt5.QtWidgets.QMessageBox.information"):
            dlg._export_csv()
        with open(path, encoding="utf-8") as f:
            content = f.read()
        self.assertIn("ST,TT", content)
        self.assertIn("Chapter One", content)

    def test_chapter_view_without_bookmarks(self):
        from cat_tool.dialogs import ChapterViewDialog
        dlg = ChapterViewDialog([])
        self.assertFalse(hasattr(dlg, "table"))

    def test_spellcheck_dialog_without_dictionary(self):
        from cat_tool.dialogs import SpellCheckDialog

        class NoDictSpell:
            loaded_names = []
            has_dict = False

        dlg = SpellCheckDialog([], NoDictSpell())
        self.assertFalse(hasattr(dlg, "results"))

    def test_spellcheck_dialog_reports_and_replaces_errors(self):
        from cat_tool.dialogs import SpellCheckDialog

        class FakeSpell:
            loaded_names = ["en_US"]
            has_dict = True

            def check_text(self, text):
                errors = []
                if "helo" in text:
                    errors.append(("helo", ["hello"]))
                if "wrold" in text:
                    errors.append(("wrold", ["world"]))
                return errors

        segments = [{"source": "Hello world", "target": "helo wrold",
                     "source_clean": "Hello world",
                     "target_clean": "helo wrold"}]
        dlg = SpellCheckDialog(segments, FakeSpell())
        self.assertEqual(len(dlg.results), 1)
        self.assertEqual(dlg.list_widget.count(), 1)
        dlg.list_widget.setCurrentRow(0)
        self.assertIn("helo", dlg.detail_label.text())
        self.assertFalse(dlg.suggestions_widget.isHidden())
        dlg._replace_word("helo", "hello")
        dlg._replace_word("wrold", "world")
        self.assertEqual(segments[0]["target_clean"], "hello world")
        self.assertEqual(dlg.results, [])
        self.assertEqual(dlg.detail_label.text(), "All errors corrected!")


if __name__ == "__main__":
    unittest.main()
