import unittest
import os
import tempfile
from cat_tool.tm import TranslationMemory
from cat_tool.glossary import Glossary
from cat_tool.file_handler import CATFileHandler

class TestCATTool(unittest.TestCase):
    def setUp(self):
        # Create temp files for databases and PO files
        self.temp_dir = tempfile.TemporaryDirectory()
        self.tm_db = os.path.join(self.temp_dir.name, "test_tm.db")
        self.glossary_db = os.path.join(self.temp_dir.name, "test_glossary.db")
        
    def tearDown(self):
        self.temp_dir.cleanup()

    def test_translation_memory(self):
        tm = TranslationMemory(self.tm_db)
        tm.add_translation("The quick brown fox jumps over the lazy dog.", "El zorro marrón rápido salta sobre el perro perezoso.")
        tm.add_translation("Hello world", "Hola mundo")

        # Exact match
        matches = tm.get_fuzzy_matches("Hello world")
        self.assertTrue(len(matches) > 0)
        self.assertEqual(matches[0]["target"], "Hola mundo")
        self.assertEqual(matches[0]["score"], 100.0)

        # Fuzzy match
        matches_fuzzy = tm.get_fuzzy_matches("Hello worlds")
        self.assertTrue(len(matches_fuzzy) > 0)
        self.assertGreater(matches_fuzzy[0]["score"], 80)
        self.assertEqual(matches_fuzzy[0]["target"], "Hola mundo")

    def test_glossary(self):
        gl = Glossary(self.glossary_db)
        gl.add_term("cat", "gato", "feline companion")
        gl.add_term("quick brown fox", "zorro marrón rápido", "a fast fox")

        terms = gl.get_all_terms()
        self.assertEqual(len(terms), 2)

        # Token match single word
        matches = gl.check_segment("My cat is sleeping.")
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["source"], "cat")
        self.assertEqual(matches[0]["target"], "gato")

        # Multi-word match
        matches_multi = gl.check_segment("The quick brown fox is fast.")
        self.assertEqual(len(matches_multi), 1)
        self.assertEqual(matches_multi[0]["source"], "quick brown fox")

        # Non-match due to boundaries
        matches_none = gl.check_segment("Concatenation is a concept.")
        self.assertEqual(len(matches_none), 0)

    def test_file_handler(self):
        # Create a basic mock PO file content
        po_content = """
msgid ""
msgstr ""
"Project-Id-Version: Test\\n"
"MIME-Version: 1.0\\n"
"Content-Type: text/plain; charset=UTF-8\\n"
"Content-Transfer-Encoding: 8bit\\n"

#. Location of segment 1
#: src/main.c:10
msgid "Hello World!"
msgstr ""

#. Location of segment 2
#: src/main.c:20
msgid "Goodbye World!"
msgstr "Adiós Mundo!"
"""
        po_file_path = os.path.join(self.temp_dir.name, "test.po")
        with open(po_file_path, "w", encoding="utf-8") as f:
            f.write(po_content.strip())

        handler = CATFileHandler()
        segments = handler.load_file(po_file_path)

        self.assertEqual(len(segments), 2)
        self.assertEqual(segments[0]["source"], "Hello World!")
        self.assertEqual(segments[0]["target"], "")
        self.assertEqual(segments[1]["source"], "Goodbye World!")
        self.assertEqual(segments[1]["target"], "Adiós Mundo!")

        # Modify first segment target
        segments[0]["target"] = "Hola Mundo!"
        handler.save_file()

        # Reload and check
        handler2 = CATFileHandler()
        segments2 = handler2.load_file(po_file_path)
        self.assertEqual(segments2[0]["target"], "Hola Mundo!")

if __name__ == "__main__":
    unittest.main()
