"""Tests for the background spell worker and learned spelling index."""
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

from PyQt5.QtWidgets import QApplication

from cat_tool.spellcheck import SpellChecker
from cat_tool.workers import SpellWorker


def ensure_app():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


class TestLearnedSpellingIndex(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = self.tmp.name
        dicts_dir = os.path.join(base, "dicts")
        personal_dir = os.path.join(dicts_dir, "personal")
        self.dic_path = os.path.join(personal_dir, "personal.dic")
        self.aff_path = os.path.join(personal_dir, "personal.aff")
        self.patches = [
            patch("cat_tool.spellcheck.DICTS_DIR", dicts_dir),
            patch("cat_tool.spellcheck.PERSONAL_DIC_DIR", personal_dir),
            patch("cat_tool.spellcheck.PERSONAL_DIC_PATH", self.dic_path),
            patch("cat_tool.spellcheck.PERSONAL_AFF_PATH", self.aff_path),
        ]
        for item in self.patches:
            item.start()
        self.checker = SpellChecker()

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()
        self.tmp.cleanup()

    def _make_hunspell_dict(self, words):
        dic_dir = os.path.join(os.path.dirname(self.dic_path), "..", "en_US")
        dic_dir = os.path.normpath(dic_dir)
        dic_path = os.path.join(dic_dir, "en_US.dic")
        aff_path = os.path.join(dic_dir, "en_US.aff")
        os.makedirs(dic_dir, exist_ok=True)
        with open(aff_path, "w", encoding="utf-8") as handle:
            handle.write("SET UTF-8\n")
        with open(dic_path, "w", encoding="utf-8") as handle:
            handle.write(f"{len(words)}\n")
            for word in words:
                handle.write(word + "\n")
        self.checker.auto_load()
        self.assertTrue(self.checker.has_dict)

    def test_first_translation_indexes_segment_and_words(self):
        self.checker.index_translation("Hello", "Hola mundo")
        indexed = self.checker.indexed_words
        self.assertIn("hola", indexed)
        self.assertIn("mundo", indexed)
        segments = self.checker.indexed_segments
        self.assertIn("Hello", segments)
        self.assertEqual(segments["Hello"]["target"], "Hola mundo")
        self.assertTrue(os.path.exists(self.dic_path))

    def test_reentry_replaces_entry_without_duplicate(self):
        self.checker.index_translation("Hello", "Hola mundo")
        self.checker.index_translation("Hello", "Hola mundo.")
        segments = self.checker.indexed_segments
        self.assertEqual(len(segments), 1)
        self.assertEqual(segments["Hello"]["target"], "Hola mundo.")

    def test_correction_replaces_indexed_word(self):
        self.checker.index_translation("Hello", "helo wrold")
        self.checker.index_correction("Hello", "wrold", "world")
        indexed = self.checker.indexed_words
        self.assertNotIn("wrold", indexed)
        self.assertIn("world", indexed)
        self.assertEqual(
            self.checker.indexed_segments["Hello"]["target"], "helo world")
        with open(self.dic_path, encoding="utf-8") as handle:
            content = handle.read().lower()
        self.assertNotIn("wrold", content)
        self.assertIn("world", content)

    def test_indexed_word_is_accepted_by_spell_check(self):
        self._make_hunspell_dict(["hello", "world"])
        self.assertEqual(
            [w for w, _ in self.checker.check_text("hello worlt")], ["worlt"])
        self.checker.index_translation("x", "worlt")
        self.assertTrue(self.checker.check("worlt"))
        self.assertEqual(self.checker.check_text("hello worlt"), [])

    def test_personal_dic_is_reloaded_by_new_checker(self):
        self.checker.index_translation("Hello", "Hola mundo")
        restored = SpellChecker()
        self.assertIn("hola", restored.indexed_words)
        self.assertIn("mundo", restored.indexed_words)

    def test_clearing_translation_removes_its_words(self):
        self.checker.index_translation("Hello", "Hola mundo")
        self.checker.index_translation("Hello", "", previous_target="Hola mundo")
        indexed = self.checker.indexed_words
        self.assertNotIn("hola", indexed)
        self.assertNotIn("mundo", indexed)


class TestSpellWorker(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = ensure_app()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        personal_dir = os.path.join(self.tmp.name, "personal")
        self.patches = [
            patch("cat_tool.spellcheck.DICTS_DIR", os.path.join(self.tmp.name, "dicts")),
            patch("cat_tool.spellcheck.PERSONAL_DIC_DIR", personal_dir),
            patch("cat_tool.spellcheck.PERSONAL_DIC_PATH", os.path.join(personal_dir, "personal.dic")),
            patch("cat_tool.spellcheck.PERSONAL_AFF_PATH", os.path.join(personal_dir, "personal.aff")),
        ]
        for item in self.patches:
            item.start()
        self.checker = SpellChecker()
        self.worker = SpellWorker(self.checker)

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()
        self.tmp.cleanup()

    def test_check_segments_emits_results(self):
        received = []
        self.worker.finished.connect(received.append)
        segments = [
            {"target": "hello world", "target_clean": "hello world"},
            {"target": "hi", "target_clean": "hi"},
        ]
        errors = []
        self.checker.check_text = lambda text: [("bad", [])] if "bad" in text else []
        segments[1]["target"] = "bad text"
        segments[1]["target_clean"] = "bad text"
        self.worker.check_segments(segments)
        self.assertEqual(len(received), 1)
        self.assertEqual(received[0][0][0], 1)

    def test_index_translation_slot_updates_checker(self):
        indexed = []
        self.worker.indexed.connect(lambda: indexed.append(True))
        self.worker.index_translation("Hello", "", "Hola")
        self.assertEqual(indexed, [True])
        self.assertIn("hola", self.checker.indexed_words)
        self.assertEqual(self.checker.indexed_segments["Hello"]["target"], "Hola")

    def test_index_correction_slot_updates_checker(self):
        self.worker.index_translation("Hello", "", "helo wrold")
        self.worker.index_correction("Hello", "wrold", "world")
        self.assertIn("world", self.checker.indexed_words)
        self.assertNotIn("wrold", self.checker.indexed_words)


if __name__ == "__main__":
    unittest.main()
