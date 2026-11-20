"""GUI tests for manual segmentation and the New Project checkbox."""
import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from PyQt5.QtWidgets import QApplication, QDialog, QMessageBox

from cat_tool.manual_segmentation import ManualSegmenter
from cat_tool.manual_segmentation_view import ManualSegmentationView
from cat_tool.project import Project
from cat_tool.state_manager import AppState


def ensure_app():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


def set_cursor(view, position):
    cursor = view.document.textCursor()
    cursor.setPosition(position)
    view.document.setTextCursor(cursor)


class TestNewProjectCheckbox(unittest.TestCase):
    def setUp(self):
        self.app = ensure_app()

    def test_checkbox_defaults_to_automatic(self):
        from cat_tool.dialogs import NewProjectDialog
        dlg = NewProjectDialog()
        self.assertFalse(dlg.manual_seg_checkbox.isChecked())
        self.assertFalse(dlg.is_manual_segmentation())

    def test_checkbox_reports_manual_segmentation(self):
        from cat_tool.dialogs import NewProjectDialog
        dlg = NewProjectDialog()
        dlg.manual_seg_checkbox.setChecked(True)
        self.assertTrue(dlg.is_manual_segmentation())
        self.assertEqual(len(dlg.get_data()), 4)

    def test_checkbox_label_mentions_segmenting_manually(self):
        from cat_tool.dialogs import NewProjectDialog
        dlg = NewProjectDialog()
        self.assertIn("manually", dlg.manual_seg_checkbox.text().lower())


class TestProjectPersistence(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def test_manual_fields_roundtrip(self):
        project = Project()
        project.new("Manual", "en", "es", ["a.txt"], manual_segmentation=True)
        self.assertEqual(project.segmentation_mode, "manual")
        project.manual_files["a.txt"] = {
            "done": True,
            "segments": [{"source": "Hello", "target": "Hola"}],
        }
        path = os.path.join(self.tmp.name, "manual.mcatproj")
        project.save(path)

        loaded = Project.load(path)
        self.assertEqual(loaded.segmentation_mode, "manual")
        self.assertTrue(loaded.manual_files["a.txt"]["done"])
        self.assertEqual(
            loaded.manual_files["a.txt"]["segments"][0]["target"], "Hola")

    def test_old_project_defaults_to_automatic(self):
        project = Project.from_dict({
            "name": "Old", "source_lang": "en", "target_lang": "es",
            "source_files": ["a.txt"],
        })
        self.assertEqual(project.segmentation_mode, "auto")
        self.assertEqual(project.manual_files, {})


class TestStateManualPersistence(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.source = os.path.join(self.tmp.name, "doc.txt")
        with open(self.source, "w", encoding="utf-8") as handle:
            handle.write("Hello world. Bye now.")

    def tearDown(self):
        self.tmp.cleanup()

    def test_new_project_sets_manual_mode(self):
        state = AppState()
        state.new_project("M", "en", "es", [self.source],
                          manual_segmentation=True)
        self.assertTrue(state.is_manual_project)
        self.assertFalse(state.file_handler.segments)

    def test_automatic_project_is_not_manual(self):
        state = AppState()
        state.new_project("A", "en", "es", [self.source])
        self.assertFalse(state.is_manual_project)

    def test_load_manual_document_returns_blocks(self):
        state = AppState()
        state.new_project("M", "en", "es", [self.source],
                          manual_segmentation=True)
        blocks, segments, label, done, error = state.load_manual_document(0)
        self.assertIsNone(error)
        self.assertEqual(label, "doc.txt")
        self.assertFalse(done)
        self.assertEqual(segments, [])
        self.assertTrue(blocks)
        self.assertIn("Hello world.", blocks[0]["text"])

    def test_save_manual_document_persists_targets(self):
        state = AppState()
        state.new_project("M", "en", "es", [self.source],
                          manual_segmentation=True)
        state.load_manual_document(0)
        segments = [{
            "source": "Hello", "target": "Hola", "extra": "dropped",
            "all_tags": None, "source_location": None,
        }]
        state.save_manual_document(0, segments, done=True)
        saved = state.project.manual_files[self.source]
        self.assertTrue(saved["done"])
        self.assertEqual(saved["segments"][0]["target"], "Hola")
        self.assertNotIn("extra", saved["segments"][0])
        self.assertEqual(saved["segments"][0]["all_tags"], [])
        self.assertEqual(saved["segments"][0]["source_location"], {})

    def test_sync_manual_state_uses_table_segments(self):
        state = AppState()
        state.new_project("M", "en", "es", [self.source],
                          manual_segmentation=True)
        state.load_manual_document(0)
        state.file_handler.segments = [{
            "source": "Hello", "target": "Hola",
        }]
        state.sync_manual_state()
        saved = state.project.manual_files[self.source]
        self.assertEqual(saved["segments"][0]["target"], "Hola")
        self.assertFalse(saved["done"])

    def test_reopen_keeps_unsaved_table_translations(self):
        state = AppState()
        state.new_project("M", "en", "es", [self.source],
                          manual_segmentation=True)
        state.load_manual_document(0)
        state.file_handler.segments = [{
            "source": "Hello", "target": "Hola",
        }]
        state.save_manual_document(0, state.file_handler.segments, done=True)

        # Simulate reopening the same file in the same session.
        blocks, segments, label, done, error = state.load_manual_document(0)
        self.assertIsNone(error)
        self.assertTrue(done)
        self.assertEqual(segments[0]["target"], "Hola")

    def test_manual_segments_are_used_when_opening_source_file(self):
        state = AppState()
        state.new_project("M", "en", "es", [self.source],
                          manual_segmentation=True)
        state.save_manual_document(0, [{
            "source": "Hello", "target": "Hola",
        }], done=True)
        segments, label, ok, error = state.open_project_source_file(0)
        self.assertTrue(ok)
        self.assertIsNone(error)
        self.assertEqual(label, "doc.txt")
        self.assertEqual(segments[0]["target"], "Hola")


class TestManualView(unittest.TestCase):
    def setUp(self):
        self.app = ensure_app()
        self.view = ManualSegmentationView()

    def tearDown(self):
        self.view.deleteLater()

    def _load(self, text="Hello world. Bye now.", saved=None, done=False):
        self.view.load_document([{"text": text}], saved, label="doc",
                                done=done)

    def test_mark_start_and_end_creates_marked_unit(self):
        self._load()
        set_cursor(self.view, 0)
        self.view.mark_start()
        self.assertEqual(self.view.segmenter.active_start["text"], "Hello")
        set_cursor(self.view, 4)
        self.view.mark_end()
        self.assertEqual(len(self.view.segmenter.marked), 1)
        self.assertEqual(
            self.view.segmenter.unit_source(self.view.segmenter.marked[0]),
            "Hello")

    def test_split_emits_segments(self):
        self._load()
        received = []
        self.view.segmentsChanged.connect(received.append)
        set_cursor(self.view, 0)
        self.view.mark_start()
        set_cursor(self.view, 4)
        self.view.mark_end()
        self.view.split()
        self.assertEqual(len(received), 1)
        self.assertEqual(received[0][0]["source"], "Hello")

    def test_split_all_includes_gaps(self):
        self._load()
        received = []
        self.view.segmentsChanged.connect(received.append)
        set_cursor(self.view, 0)
        self.view.mark_start()
        set_cursor(self.view, 4)
        self.view.mark_end()
        set_cursor(self.view, 6)
        self.view.mark_start()
        set_cursor(self.view, len("Hello world."))
        self.view.mark_end()
        self.view.split_all()
        self.assertEqual(
            [seg["source"] for seg in received[-1]],
            ["Hello", "world.", "Bye now."])

    def test_finish_fills_gaps_when_confirmed(self):
        self._load()
        set_cursor(self.view, 0)
        self.view.mark_start()
        set_cursor(self.view, 4)
        self.view.mark_end()
        self.view.split()
        finished = []
        self.view.finished.connect(lambda: finished.append(True))
        with patch(
            "cat_tool.manual_segmentation_view.QMessageBox.question",
            return_value=QMessageBox.Yes,
        ):
            self.view.finish_segmentation()
        self.assertTrue(finished)
        self.assertTrue(self.view.is_done)
        self.assertFalse(self.view.segmenter.has_unsegmented_text())
        self.assertGreater(len(self.view.segments), 1)

    def test_finish_without_filling_gaps_keeps_gap(self):
        self._load()
        set_cursor(self.view, 0)
        self.view.mark_start()
        set_cursor(self.view, 4)
        self.view.mark_end()
        self.view.split()
        with patch(
            "cat_tool.manual_segmentation_view.QMessageBox.question",
            return_value=QMessageBox.No,
        ):
            self.view.finish_segmentation()
        self.assertTrue(self.view.is_done)
        self.assertTrue(self.view.segmenter.has_unsegmented_text())

    def test_finish_with_pending_unit_warns(self):
        self._load()
        set_cursor(self.view, 0)
        self.view.mark_start()
        set_cursor(self.view, 4)
        self.view.mark_end()
        with patch(
            "cat_tool.manual_segmentation_view.QMessageBox.warning"
        ) as warning:
            self.view.finish_segmentation()
        warning.assert_called_once()
        self.assertFalse(self.view.is_done)

    def test_finish_without_units_warns(self):
        self._load()
        with patch(
            "cat_tool.manual_segmentation_view.QMessageBox.warning"
        ) as warning:
            self.view.finish_segmentation()
        warning.assert_called_once()
        self.assertFalse(self.view.is_done)

    def test_finish_cancel_does_not_lock(self):
        self._load()
        set_cursor(self.view, 0)
        self.view.mark_start()
        set_cursor(self.view, 4)
        self.view.mark_end()
        self.view.split()
        with patch(
            "cat_tool.manual_segmentation_view.QMessageBox.question",
            return_value=QMessageBox.Cancel,
        ):
            self.view.finish_segmentation()
        self.assertFalse(self.view.is_done)

    def test_locked_view_ignores_boundary_actions(self):
        self._load(saved=[{
            "start": 0, "end": 5, "block_index": 0,
            "block_start": 0, "block_end": 5, "target": "Hola",
        }], done=True)
        set_cursor(self.view, 6)
        self.view.mark_start()
        self.assertIsNone(self.view.segmenter.active_start)
        self.assertTrue(self.view.is_done)
        self.assertFalse(self.view.edit_btn.isHidden())
        self.assertTrue(self.view.finish_btn.isHidden())

    def test_edit_segmentation_no_keeps_lock(self):
        self._load(saved=[{
            "start": 0, "end": 5, "block_index": 0,
            "block_start": 0, "block_end": 5,
        }], done=True)
        with patch(
            "cat_tool.manual_segmentation_view.QMessageBox.warning",
            return_value=QMessageBox.No,
        ):
            self.view.edit_segmentation()
        self.assertTrue(self.view.is_done)

    def test_edit_segmentation_yes_unlocks_and_emits(self):
        self._load(saved=[{
            "start": 0, "end": 5, "block_index": 0,
            "block_start": 0, "block_end": 5,
        }], done=True)
        emitted = []
        self.view.editStarted.connect(lambda: emitted.append(True))
        with patch(
            "cat_tool.manual_segmentation_view.QMessageBox.warning",
            return_value=QMessageBox.Yes,
        ):
            self.view.edit_segmentation()
        self.assertFalse(self.view.is_done)
        self.assertEqual(emitted, [True])

    def test_load_restores_units_and_targets(self):
        self._load(saved=[{
            "start": 0, "end": 5, "block_index": 0,
            "block_start": 0, "block_end": 5, "target": "Hola",
        }])
        self.assertEqual(len(self.view.segmenter.units), 1)
        self.assertEqual(self.view.segments[0]["target"], "Hola")

    def test_file_combo_emits_change_request(self):
        received = []
        self.view.fileChangeRequested.connect(received.append)
        self.view.set_file_list(["a.txt", "b.txt"], 0)
        self.view.file_combo.setCurrentIndex(1)
        self.assertEqual(received, [1])

    def test_clear_document_resets_view(self):
        self._load()
        self.view.clear_document()
        self.assertIsNone(self.view.segmenter)
        self.assertEqual(self.view.segments, [])
        self.assertFalse(self.view.is_done)


class TestMainWindowIntegration(unittest.TestCase):
    def setUp(self):
        self.app = ensure_app()
        self.tmp = tempfile.TemporaryDirectory()
        self.source = os.path.join(self.tmp.name, "doc.txt")
        with open(self.source, "w", encoding="utf-8") as handle:
            handle.write("Hello world. Bye now.")

    def tearDown(self):
        self.tmp.cleanup()

    def _window(self):
        from cat_tool.ui import MainWindow
        return MainWindow()

    def test_new_project_dialog_opens_manual_view(self):
        window = self._window()
        dial = MagicMock()
        dial.exec_.return_value = QDialog.Accepted
        dial.get_data.return_value = ("Manual", "en", "es", [self.source])
        dial.is_manual_segmentation.return_value = True
        with patch("cat_tool.ui.NewProjectDialog", return_value=dial):
            window.new_project()
        self.assertTrue(window.state.is_manual_project)
        self.assertIs(window.view_stack.currentWidget(), window.manual_view)
        self.assertTrue(window.manual_seg_action.isEnabled())
        window.close()

    def test_automatic_project_stays_on_table(self):
        window = self._window()
        dial = MagicMock()
        dial.exec_.return_value = QDialog.Accepted
        dial.get_data.return_value = ("Auto", "en", "es", [self.source])
        dial.is_manual_segmentation.return_value = False
        with patch("cat_tool.ui.NewProjectDialog", return_value=dial):
            window.new_project()
        self.assertFalse(window.state.is_manual_project)
        self.assertIs(window.view_stack.currentWidget(), window.main_view)
        self.assertFalse(window.manual_seg_action.isEnabled())
        window.close()

    def test_manual_split_updates_table_and_finish_saves(self):
        window = self._window()
        window.state.new_project(
            "Manual", "en", "es", [self.source], manual_segmentation=True)
        window.manual_seg_action.setEnabled(True)
        window._open_manual_project_file(0)
        view = window.manual_view

        set_cursor(view, 0)
        view.mark_start()
        set_cursor(view, 4)
        view.mark_end()
        view.split()
        self.assertEqual(window.table.rowCount(), 1)

        set_cursor(view, 6)
        view.mark_start()
        set_cursor(view, len("Hello world."))
        view.mark_end()
        view.split_all()
        self.assertEqual(
            [seg["source"] for seg in window.state.file_handler.segments],
            ["Hello", "world.", "Bye now."])

        with patch(
            "cat_tool.manual_segmentation_view.QMessageBox.question",
            return_value=QMessageBox.Yes,
        ):
            view.finish_segmentation()
        state = window.state.project.manual_files[self.source]
        self.assertTrue(state["done"])
        self.assertIs(window.view_stack.currentWidget(), window.main_view)
        window.close()

    def test_translation_survives_file_switch(self):
        second = os.path.join(self.tmp.name, "second.txt")
        with open(second, "w", encoding="utf-8") as handle:
            handle.write("Second document here.")

        window = self._window()
        window.state.new_project(
            "Manual", "en", "es", [self.source, second],
            manual_segmentation=True)
        window.manual_seg_action.setEnabled(True)
        window._open_manual_project_file(0)
        view = window.manual_view

        set_cursor(view, 0)
        view.mark_start()
        set_cursor(view, 4)
        view.mark_end()
        view.split()
        window.state.file_handler.segments[0]["target"] = "Hola"

        window._open_manual_project_file(1)
        saved = window.state.project.manual_files[self.source]
        self.assertEqual(saved["segments"][0]["target"], "Hola")

        window._open_manual_project_file(0)
        self.assertEqual(
            window.state.file_handler.segments[0]["target"], "Hola")
        self.assertEqual(view.segments[0]["target"], "Hola")
        window.close()

    def test_translation_survives_reopen(self):
        window = self._window()
        window.state.new_project(
            "Manual", "en", "es", [self.source], manual_segmentation=True)
        window.manual_seg_action.setEnabled(True)
        window._open_manual_project_file(0)
        view = window.manual_view

        set_cursor(view, 0)
        view.mark_start()
        set_cursor(view, 4)
        view.mark_end()
        view.split()
        window.state.file_handler.segments[0]["target"] = "Hola"
        window.state.file_handler.segments[0]["translated"] = True
        window.state.save_manual_document(
            self.source, window.state.file_handler.segments, done=True)

        # Reopen the same document in the same session.
        view.clear_document()
        blocks, segments, label, done, error = \
            window.state.load_manual_document(0)
        view.load_document(blocks, segments, label=label, done=done)
        self.assertTrue(done)
        self.assertEqual(view.segments[0]["target"], "Hola")
        window.close()


if __name__ == "__main__":
    unittest.main()
