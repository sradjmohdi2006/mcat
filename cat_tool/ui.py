import os
import sys

parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QTableWidget, QTableWidgetItem, QSplitter, QTextEdit,
                             QPushButton, QLabel, QListWidget, QListWidgetItem,
                             QFileDialog, QStatusBar, QProgressBar, QMessageBox,
                             QCheckBox, QDialog, QFormLayout, QLineEdit, QHeaderView,
                             QComboBox, QDialogButtonBox, QMenu, QScrollArea, QSpinBox)
from PyQt5.QtCore import Qt, pyqtSignal, QThread, QTimer
from PyQt5.QtGui import QColor, QFont, QKeySequence

from cat_tool.file_handler import CATFileHandler, convert_to_po
from cat_tool.formats.tag_utils import PH_L, PH_R, extract_all_tags, apply_tags, restore_tags
from cat_tool import qa
from cat_tool.state_manager import AppState
from cat_tool.workers import SegmentationWorker, EmbeddingWorker, FuzzyMatchWorker

from cat_tool.dialogs import (
    GlossaryDialog, LangDialog, NewProjectDialog, ProjectSettingsDialog,
    ShortcutsDialog, QADialog, SpellCheckDialog, SettingsDialog, TagViewDialog,
    FILE_FILTER,
)


# Cached color constants for cell styling
_SRC_FUZZY_BG = QColor("#3d2e00")
_SRC_FUZZY_FG = QColor("#ff9800")
_SRC_TRANSLATED_BG = QColor("#002b00")
_SRC_TRANSLATED_FG = QColor("#28a745")
_SRC_DEFAULT_BG = QColor("#1a1a1e")
_SRC_DEFAULT_FG = QColor("#a0a0a8")
_TGT_FUZZY_BG = QColor("#3d2e00")
_TGT_FUZZY_FG = QColor("#ff9800")
_TGT_TRANSLATED_BG = QColor("#003300")
_TGT_TRANSLATED_FG = QColor("#ffffff")
_TGT_DEFAULT_BG = QColor("#1a1a1e")
_TGT_DEFAULT_FG = QColor("#808080")

DARK_STYLESHEET = """
QMainWindow {
    background-color: #121214;
}
QWidget {
    background-color: #1e1e24;
    color: #ffffff;
    font-family: "Segoe UI", Arial, sans-serif;
    font-size: 13px;
}
QTableWidget {
    background-color: #1a1a1e;
    gridline-color: #2c2c35;
    border: 1px solid #2c2c35;
    border-radius: 4px;
}
QTableWidget::item {
    padding: 8px;
    border-bottom: 1px solid #2c2c35;
}
QTableWidget::item:selected {
    background-color: #0078d4;
    color: white;
}
QHeaderView::section {
    background-color: #25252b;
    color: #b0b0b8;
    padding: 6px;
    border: 1px solid #2c2c35;
    font-weight: bold;
}
QTextEdit {
    background-color: #1a1a1e;
    border: 1px solid #2c2c35;
    border-radius: 4px;
    padding: 6px;
    font-size: 14px;
    color: #ffffff;
}
QTextEdit[readOnly="true"] {
    background-color: #151518;
    color: #a0a0a8;
}
QPushButton {
    background-color: #0078d4;
    color: white;
    border: none;
    padding: 8px 16px;
    border-radius: 4px;
    font-weight: bold;
}
QPushButton:hover {
    background-color: #1085e0;
}
QPushButton:pressed {
    background-color: #0066b3;
}
QPushButton:disabled {
    background-color: #3a3a42;
    color: #808088;
}
QListWidget {
    background-color: #1a1a1e;
    border: 1px solid #2c2c35;
    border-radius: 4px;
}
QListWidget::item {
    padding: 8px;
    border-bottom: 1px solid #2c2c35;
}
QListWidget::item:hover {
    background-color: #25252b;
}
QListWidget::item:selected {
    background-color: #0078d4;
    color: white;
}
QCheckBox {
    spacing: 5px;
}
QCheckBox::indicator {
    width: 18px;
    height: 18px;
}
QStatusBar {
    background-color: #121214;
    color: #b0b0b8;
}
QProgressBar {
    border: 1px solid #2c2c35;
    border-radius: 4px;
    text-align: center;
    background-color: #1a1a1e;
    color: white;
}
QProgressBar::chunk {
    background-color: #20c997;
    border-radius: 3px;
}
QLineEdit {
    background-color: #1a1a1e;
    border: 1px solid #2c2c35;
    border-radius: 4px;
    padding: 6px;
    color: white;
}
QLabel {
    font-weight: bold;
    color: #e0e0e8;
}
"""


class MainWindow(QMainWindow):
    _seg_requested = pyqtSignal(str)
    _emb_requested = pyqtSignal(str, int)
    _fuzzy_requested = pyqtSignal(str, str, str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("mcat")
        self.resize(1100, 750)
        self.setStyleSheet(DARK_STYLESHEET)

        self.state = AppState()
        self.current_segment_index = -1
        self.modified = False
        self._seg_thread = None
        self._seg_worker = None
        self._emb_thread = None
        self._emb_worker = None
        self._fuzzy_thread = None
        self._fuzzy_worker = None
        self._pending_fuzzy_source = ""

        self._selection_debounce = QTimer()
        self._selection_debounce.setSingleShot(True)
        self._selection_debounce.setInterval(80)
        self._selection_debounce.timeout.connect(self._on_selection_debounced)

        self._model_idle_timer = QTimer()
        self._model_idle_timer.setSingleShot(True)
        self._model_idle_timer.setInterval(300000)
        self._model_idle_timer.timeout.connect(self._unload_idle_model)

        self.init_menu()
        self.init_ui()
        self._apply_settings()
        self.update_stats()

    def _ensure_seg_worker(self):
        if self._seg_thread is not None:
            return
        self._seg_thread = QThread()
        self._seg_worker = SegmentationWorker()
        self._seg_worker.moveToThread(self._seg_thread)
        self._seg_requested.connect(self._seg_worker.load_file)
        self._seg_worker.chunk_ready.connect(self._on_segmentation_chunk)
        self._seg_worker.finished.connect(self._on_segmentation_finished)
        self._seg_worker.error.connect(self._on_segmentation_error)
        self._seg_thread.start()

    def _ensure_emb_worker(self):
        if self._emb_thread is not None:
            return
        self._emb_thread = QThread()
        self._emb_worker = EmbeddingWorker(self.state.tm.db_path)
        self._emb_worker.moveToThread(self._emb_thread)
        self._emb_requested.connect(self._emb_worker.add_embedding)
        self._emb_thread.start()

    def _ensure_fuzzy_worker(self):
        if self._fuzzy_thread is not None:
            return
        self._fuzzy_thread = QThread()
        self._fuzzy_worker = FuzzyMatchWorker(self.state.tm.db_path)
        self._fuzzy_worker.moveToThread(self._fuzzy_thread)
        self._fuzzy_requested.connect(self._fuzzy_worker.find_matches)
        self._fuzzy_worker.finished.connect(self._on_fuzzy_matches_ready)
        self._fuzzy_thread.start()

    def _stop_threads(self):
        if self._seg_thread is not None and self._seg_thread.isRunning():
            self._seg_thread.quit()
            self._seg_thread.wait(2000)
        if self._emb_thread is not None and self._emb_thread.isRunning():
            self._emb_thread.quit()
            self._emb_thread.wait(2000)
        if self._fuzzy_thread is not None and self._fuzzy_thread.isRunning():
            self._fuzzy_thread.quit()
            self._fuzzy_thread.wait(2000)

    def cleanup(self):
        self._stop_threads()

    def changeEvent(self, event):
        if event.type() == event.WindowStateChange and self.isMinimized():
            self._unload_idle_model()
        super().changeEvent(event)

    def closeEvent(self, event):
        self._model_idle_timer.stop()
        self._stop_threads()
        super().closeEvent(event)

    def init_menu(self):
        menubar = self.menuBar()

        # File Menu
        file_menu = menubar.addMenu("&File")

        self.new_project_action = file_menu.addAction("&New Project...")
        self.new_project_action.setShortcut(QKeySequence("Ctrl+N"))
        self.new_project_action.setStatusTip("Create a new translation project")
        self.new_project_action.triggered.connect(self.new_project)

        self.open_project_action = file_menu.addAction("&Open Project...")
        self.open_project_action.setShortcut(QKeySequence("Ctrl+Shift+O"))
        self.open_project_action.setStatusTip("Open an existing project")
        self.open_project_action.triggered.connect(self.open_project)

        self.save_project_action = file_menu.addAction("&Save Project")
        self.save_project_action.setShortcut(QKeySequence("Ctrl+Shift+S"))
        self.save_project_action.setStatusTip("Save the current project")
        self.save_project_action.triggered.connect(self.save_project)

        self.save_project_as_action = file_menu.addAction("Save Project &As...")
        self.save_project_as_action.setStatusTip("Save the project with a new name")
        self.save_project_as_action.triggered.connect(self.save_project_as)

        self.close_project_action = file_menu.addAction("&Close Project")
        self.close_project_action.setStatusTip("Close the current project")
        self.close_project_action.triggered.connect(self.close_project)

        file_menu.addSeparator()

        self.project_settings_action = file_menu.addAction("Project &Settings...")
        self.project_settings_action.triggered.connect(self.project_settings)

        file_menu.addSeparator()

        self.recent_menu = file_menu.addMenu("&Recent Projects")

        file_menu.addSeparator()

        import_menu = file_menu.addMenu("&Import Project")

        import_omegat_action = import_menu.addAction("Import Omega&T Project...")
        import_omegat_action.triggered.connect(self.import_omegat_project)

        import_menu.addSeparator()

        import_memoq_action = import_menu.addAction("Import &memoQ Project...")
        import_memoq_action.triggered.connect(self.import_memoq_project)

        import_menu.addSeparator()

        import_sdl_action = import_menu.addAction("Import &SDL Trados SDLXLIFF...")
        import_sdl_action.triggered.connect(self.import_sdlxliff)

        file_menu.addSeparator()

        open_action = file_menu.addAction("&Open File...")
        open_action.setShortcut(QKeySequence.Open)
        open_action.setStatusTip("Open a translation file (PO, MQXLIFF, SDLXLIFF, etc.)")
        open_action.triggered.connect(self.open_file)

        save_action = file_menu.addAction("&Save File")
        save_action.setShortcut(QKeySequence.Save)
        save_action.setStatusTip("Save the current translation file")
        save_action.triggered.connect(self.save_file)

        save_as_action = file_menu.addAction("Save File &As...")
        save_as_action.setStatusTip("Save the translation file in a different format")
        save_as_action.triggered.connect(self.save_file_as)

        file_menu.addSeparator()

        self.render_action = file_menu.addAction("&Render Translated File...")
        self.render_action.setShortcut(QKeySequence("Ctrl+R"))
        self.render_action.triggered.connect(self.render_translated_file)

        file_menu.addSeparator()
        exit_action = file_menu.addAction("E&xit")
        exit_action.triggered.connect(self.close)

        # Go / Navigation Menu
        go_menu = menubar.addMenu("&Go")

        self.next_seg_action = go_menu.addAction("&Next Segment")
        self.next_seg_action.setShortcut(QKeySequence("Ctrl+Down"))
        self.next_seg_action.triggered.connect(self._go_next_segment)

        self.prev_seg_action = go_menu.addAction("&Previous Segment")
        self.prev_seg_action.setShortcut(QKeySequence("Ctrl+Up"))
        self.prev_seg_action.triggered.connect(self._go_prev_segment)

        go_menu.addSeparator()

        self.next_untranslated_action = go_menu.addAction("Next &Untranslated")
        self.next_untranslated_action.setShortcut(QKeySequence("Ctrl+U"))
        self.next_untranslated_action.triggered.connect(self._go_next_untranslated)

        go_menu.addSeparator()

        self.toggle_fuzzy_action = go_menu.addAction("Toggle &Fuzzy")
        self.toggle_fuzzy_action.setShortcut(QKeySequence("Ctrl+F"))
        self.toggle_fuzzy_action.triggered.connect(self._toggle_fuzzy)

        go_menu.addSeparator()

        self.first_seg_action = go_menu.addAction("&First Segment")
        self.first_seg_action.setShortcut(QKeySequence("Ctrl+Home"))
        self.first_seg_action.triggered.connect(self._go_first_segment)

        self.last_seg_action = go_menu.addAction("&Last Segment")
        self.last_seg_action.setShortcut(QKeySequence("Ctrl+End"))
        self.last_seg_action.triggered.connect(self._go_last_segment)

        # TM Menu
        tm_menu = menubar.addMenu("&Translation Memory")
        import_tm_action = tm_menu.addAction("&Import PO into TM...")
        import_tm_action.setShortcut(QKeySequence("Ctrl+M"))
        import_tm_action.triggered.connect(self.import_po_to_tm)

        clear_tm_action = tm_menu.addAction("&Clear TM Database")
        clear_tm_action.triggered.connect(self.clear_tm)

        # Glossary Menu
        glossary_menu = menubar.addMenu("&Glossary")
        add_term_action = glossary_menu.addAction("&Add Term...")
        add_term_action.setShortcut(QKeySequence("Ctrl+G"))
        add_term_action.triggered.connect(self.add_glossary_term)

        view_all_action = glossary_menu.addAction("&View/Manage Glossary")
        view_all_action.setShortcut(QKeySequence("Ctrl+Shift+G"))
        view_all_action.triggered.connect(self.view_glossary)

        glossary_menu.addSeparator()
        import_tmx_action = glossary_menu.addAction("Import &TMX into Glossary...")
        import_tmx_action.triggered.connect(self.import_tmx_to_glossary)
        export_tmx_action = glossary_menu.addAction("E&xport Glossary as TMX...")
        export_tmx_action.triggered.connect(self.export_glossary_as_tmx)

        glossary_menu.addSeparator()
        collections_menu = glossary_menu.addMenu("&Collections")
        create_coll_action = collections_menu.addAction("&Create Collection...")
        create_coll_action.triggered.connect(self.create_collection_dialog)
        manage_coll_action = collections_menu.addAction("&Manage Collections...")
        manage_coll_action.triggered.connect(self.manage_collections)
        collections_menu.addSeparator()
        import_coll_tmx_action = collections_menu.addAction("&Import Collection as TMX...")
        import_coll_tmx_action.triggered.connect(self.import_collection_tmx)
        export_coll_tmx_action = collections_menu.addAction("E&xport Collection as TMX...")
        export_coll_tmx_action.triggered.connect(self.export_collection_tmx)

        # Tools Menu
        tools_menu = menubar.addMenu("&Tools")
        seg_rules_action = tools_menu.addAction("&Segmentation Rules...")
        seg_rules_action.setShortcut(QKeySequence("Ctrl+Shift+T"))
        seg_rules_action.triggered.connect(self.open_segmentation_rules)

        tools_menu.addSeparator()

        self.qa_action = tools_menu.addAction("&Quality Assurance...")
        self.qa_action.setShortcut(QKeySequence("Ctrl+Shift+Q"))
        self.qa_action.setStatusTip("Run quality assurance checks on the translation")
        self.qa_action.triggered.connect(self.run_qa)

        tools_menu.addSeparator()
        self.import_dict_action = tools_menu.addAction("&Import Dictionary...")
        self.import_dict_action.triggered.connect(self.import_dictionary)

        tools_menu.addSeparator()
        self.spellcheck_action = tools_menu.addAction("&Spell Check...")
        self.spellcheck_action.setShortcut(QKeySequence("F7"))
        self.spellcheck_action.triggered.connect(self.run_spellcheck)

        tools_menu.addSeparator()
        self.clear_caches_action = tools_menu.addAction("Clear &Caches")
        self.clear_caches_action.setShortcut(QKeySequence("Ctrl+Shift+C"))
        self.clear_caches_action.setStatusTip("Free memory by clearing TM cache and unloading the embedding model")
        self.clear_caches_action.triggered.connect(self.clear_caches)

        tools_menu.addSeparator()
        self.options_action = tools_menu.addAction("&Options...")
        self.options_action.setShortcut(QKeySequence("Ctrl+,"))
        self.options_action.triggered.connect(self.show_options)

        # Help Menu
        help_menu = menubar.addMenu("&Help")
        self.shortcuts_action = help_menu.addAction("&Keyboard Shortcuts...")
        self.shortcuts_action.setShortcuts(["F1", "Ctrl+Shift+H"])
        self.shortcuts_action.triggered.connect(self.show_shortcuts)

        help_menu.addSeparator()
        get_dicts_action = help_menu.addAction("&Get Dictionaries...")
        get_dicts_action.triggered.connect(self._open_dicts_page)

        self._update_recent_menu()

    def init_ui(self):
        main_splitter = QSplitter(Qt.Horizontal)

        # ----------------- LEFT PANEL: 2-Column Editable Table -----------------
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        self.table = QTableWidget()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["Source Segment", "Translation"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.itemSelectionChanged.connect(self.segment_selected)
        self.table.cellChanged.connect(self._on_target_cell_changed)
        self.table.setToolTip("Main translation table: source segments (left) and your translations (right). Select a row to edit.")
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._table_context_menu)

        sl = self.state.project.source_lang if self.state.project else None
        tl = self.state.project.target_lang if self.state.project else None
        from cat_tool.suggest import CompletionDelegate
        self.completion_delegate = CompletionDelegate(self.table, self.state.tm, self.state.glossary, self.state.spellchecker, self.state.settings, source_lang=sl, target_lang=tl)
        self.table.setItemDelegateForColumn(1, self.completion_delegate)

        seg_label = QLabel("Segments")
        left_layout.addWidget(seg_label)
        left_layout.addWidget(self.table)

        # Bottom button bar
        btn_layout = QHBoxLayout()
        self.fuzzy_checkbox = QCheckBox("Fuzzy / Needs Review")
        self.fuzzy_checkbox.setToolTip("Mark this segment as fuzzy or needing review")
        self.fuzzy_checkbox.stateChanged.connect(self.fuzzy_state_changed)

        self.confirm_btn = QPushButton("Confirm & Next (Ctrl+Enter)")
        self.confirm_btn.setToolTip("Confirm the current translation and move to the next segment")
        self.confirm_btn.clicked.connect(self.confirm_active_segment)
        self.confirm_btn.setShortcut(QKeySequence("Ctrl+Return"))

        btn_layout.addWidget(self.fuzzy_checkbox)
        btn_layout.addStretch()
        btn_layout.addWidget(self.confirm_btn)
        left_layout.addLayout(btn_layout)

        # ----------------- RIGHT PANEL: Sidebars -----------------
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)

        tm_label = QLabel("TM Fuzzy Matches (Double-click to apply)")
        right_layout.addWidget(tm_label)
        self.tm_list = QListWidget()
        self.tm_list.itemDoubleClicked.connect(self.apply_tm_suggestion)
        right_layout.addWidget(self.tm_list)

        glossary_label = QLabel("Detected Terminology / Glossary")
        right_layout.addWidget(glossary_label)
        self.glossary_table = QTableWidget()
        self.glossary_table.setColumnCount(2)
        self.glossary_table.setHorizontalHeaderLabels(["Source Term", "Translation"])
        self.glossary_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.glossary_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.glossary_table.setSelectionMode(QTableWidget.SingleSelection)
        self.glossary_table.itemDoubleClicked.connect(self.insert_glossary_term)
        right_layout.addWidget(self.glossary_table)

        main_splitter.addWidget(left_widget)
        main_splitter.addWidget(right_widget)
        main_splitter.setStretchFactor(0, 2)
        main_splitter.setStretchFactor(1, 1)

        self.setCentralWidget(main_splitter)

        # ----------------- STATUS BAR -----------------
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximumWidth(200)
        self.progress_bar.setValue(0)
        self.status_bar.addPermanentWidget(self.progress_bar)

        self.status_label = QLabel("Ready")
        self.status_bar.addWidget(self.status_label)

    # ----------------- BACKGROUND WORKER CALLBACKS -----------------
    def _on_segmentation_chunk(self, chunk, total, label):
        self.table.blockSignals(True)
        self.table.setUpdatesEnabled(False)

        start_row = len(self.state.file_handler.segments)
        self.state.file_handler.segments.extend(chunk)

        self.table.setRowCount(len(self.state.file_handler.segments))
        for idx, seg in enumerate(chunk):
            row = start_row + idx
            src_text = seg.get("source_clean", seg["source"])
            src_item = QTableWidgetItem(src_text)
            src_item.setFlags(src_item.flags() & ~Qt.ItemIsEditable)
            self.set_source_cell_style(src_item, seg)
            self.table.setItem(row, 0, src_item)

            tgt_text = seg.get("target_clean", seg["target"])
            tgt_item = QTableWidgetItem(tgt_text)
            tgt_item.setFlags(tgt_item.flags() | Qt.ItemIsEditable)
            self.set_target_cell_style(tgt_item, seg)
            self.table.setItem(row, 1, tgt_item)

        self.table.setUpdatesEnabled(True)
        self.table.blockSignals(False)

        self.completion_delegate.set_source_texts([
            s.get("source_clean", s["source"]) for s in self.state.file_handler.segments
        ])

    def _on_segmentation_finished(self, segments, label):
        self.state.file_handler.segments = segments
        self.state.file_handler.current_file_path = label if os.path.isfile(label) else None
        self.modified = False
        self.update_stats()
        self.status_label.setText(f"Loaded: {os.path.basename(label) if os.path.isfile(label) else label}")
        if segments:
            self.table.selectRow(0)

    def _on_segmentation_error(self, error_msg):
        QMessageBox.critical(self, "Error Loading File", error_msg)
        self.status_label.setText("Load failed")

    def _on_embedding_finished(self, row_id):
        pass

    def _on_embedding_error(self, error_msg, row_id):
        print(f"Embedding error for row {row_id}: {error_msg}")

    def _touch_model_timer(self):
        self._model_idle_timer.stop()
        self._model_idle_timer.start()

    def _unload_idle_model(self):
        self.state.tm.unload_model()
        if self._emb_worker is not None:
            self._emb_worker.unload_model()
        self._model_idle_timer.stop()

    def clear_caches(self):
        self.state.tm.clear_cache()
        self._unload_idle_model()
        self.status_label.setText("Caches cleared, embedding model unloaded.")

    def _on_selection_debounced(self):
        if self.current_segment_index < 0:
            return
        seg = self.state.file_handler.segments[self.current_segment_index]
        self._pending_fuzzy_source = seg["source"]
        self._touch_model_timer()
        self.update_fuzzy_matches(seg["source"])
        self.update_glossary_matches(seg["source"])

    # ----------------- FILE OPERATIONS -----------------
    def open_file(self):
        if self.modified:
            reply = QMessageBox.question(
                self, "Unsaved Changes",
                "You have unsaved changes. Open a new file anyway?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.No:
                return

        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open Translation File", "", FILE_FILTER
        )
        if not file_path:
            return

        self.state.file_handler.segments = []
        self.table.setRowCount(0)
        self.status_label.setText("Loading file...")
        self._ensure_seg_worker()
        self._seg_requested.emit(file_path)

    def open_file_path(self, file_path):
        if not os.path.exists(file_path):
            return
        self.state.file_handler.segments = []
        self.table.setRowCount(0)
        self.status_label.setText("Loading file...")
        self._ensure_seg_worker()
        self._seg_requested.emit(file_path)

    def populate_table(self, segments):
        self.table.blockSignals(True)
        self.table.setUpdatesEnabled(False)
        self.table.setRowCount(len(segments))
        for idx, seg in enumerate(segments):
            src_text = seg.get("source_clean", seg["source"])
            src_item = QTableWidgetItem(src_text)
            src_item.setFlags(src_item.flags() & ~Qt.ItemIsEditable)
            self.set_source_cell_style(src_item, seg)
            self.table.setItem(idx, 0, src_item)

            tgt_text = seg.get("target_clean", seg["target"])
            tgt_item = QTableWidgetItem(tgt_text)
            tgt_item.setFlags(tgt_item.flags() | Qt.ItemIsEditable)
            self.set_target_cell_style(tgt_item, seg)
            self.table.setItem(idx, 1, tgt_item)

        self.table.setUpdatesEnabled(True)
        self.table.blockSignals(False)

        source_texts = [seg.get("source_clean", seg["source"]) for seg in segments]
        self.completion_delegate.set_source_texts(source_texts)

    def get_status_text(self, seg):
        if seg["fuzzy"]:
            return "Fuzzy"
        elif seg["target"] and seg["target"].strip():
            return "Translated"
        else:
            return "Untranslated"

    def set_source_cell_style(self, item, seg):
        if seg["fuzzy"]:
            item.setBackground(_SRC_FUZZY_BG)
            item.setForeground(_SRC_FUZZY_FG)
        elif seg.get("translated", False) or (seg["target"] and seg["target"].strip()):
            item.setBackground(_SRC_TRANSLATED_BG)
            item.setForeground(_SRC_TRANSLATED_FG)
        else:
            item.setBackground(_SRC_DEFAULT_BG)
            item.setForeground(_SRC_DEFAULT_FG)

    def set_target_cell_style(self, item, seg):
        if seg["fuzzy"]:
            item.setBackground(_TGT_FUZZY_BG)
            item.setForeground(_TGT_FUZZY_FG)
        elif seg.get("translated", False) or (seg["target"] and seg["target"].strip()):
            item.setBackground(_TGT_TRANSLATED_BG)
            item.setForeground(_TGT_TRANSLATED_FG)
        else:
            item.setBackground(_TGT_DEFAULT_BG)
            item.setForeground(_TGT_DEFAULT_FG)

    def _on_target_cell_changed(self, row, col):
        if col != 1:
            return
        seg = self.state.file_handler.segments[row]
        item = self.table.item(row, 1)
        if item is None:
            return

        new_text = item.text().strip()
        tags = seg.get("all_tags", [])
        restored = restore_tags(new_text, tags)

        if seg["target"] == restored:
            return

        seg["target"] = restored
        seg["translated"] = bool(restored)
        new_tgt_tags = extract_all_tags(restored)
        all_tags = list(tags)
        for t in new_tgt_tags:
            if t not in all_tags:
                all_tags.append(t)
        seg["all_tags"] = all_tags
        seg["target_clean"] = apply_tags(restored, all_tags)

        if restored:
            row_id = self.state.tm.add_translation(seg["source"], restored, self.state.tm_sl, self.state.tm_tl)
            if row_id is not None:
                self._ensure_emb_worker()
                self._touch_model_timer()
                self._emb_requested.emit(seg["source"], row_id)

        item.setText(seg["target_clean"])
        self.set_target_cell_style(item, seg)
        self.set_source_cell_style(self.table.item(row, 0), seg)

        self.modified = True
        self.update_stats()

    def save_file(self):
        if not self.state.file_handler.current_file_path:
            self.save_file_as()
            return
        try:
            self.state.file_handler.save_file()
            self.modified = False
            self.status_label.setText(f"Saved: {os.path.basename(self.state.file_handler.current_file_path)}")
        except Exception as e:
            QMessageBox.critical(self, "Error Saving File", str(e))

    def save_file_as(self):
        file_path, selected_filter = QFileDialog.getSaveFileName(
            self, "Save Translation File As", "",
            "MCAT Project (*.mcat.db);;PO Files (*.po);;memoQ MQXLIFF (*.mqxliff);;SDL Trados SDLXLIFF (*.sdlxliff);;OmegaT Project folder;;All Files (*)"
        )
        if not file_path:
            return
        try:
            src_lang = self.state.project.source_lang if self.state.project else "en"
            tgt_lang = self.state.project.target_lang if self.state.project else "es"

            if "OmegaT" in selected_filter:
                dir_path = QFileDialog.getExistingDirectory(
                    self, "Select folder to create OmegaT project in",
                    os.path.dirname(file_path) if os.path.dirname(file_path) else ""
                )
                if not dir_path:
                    return
                target_dir = os.path.join(dir_path, os.path.splitext(os.path.basename(file_path))[0])
                p = self.state.project if self.state.project else Project()
                if not self.state.project:
                    p.new(os.path.basename(target_dir), src_lang, tgt_lang, [])
                p.save_as_omegat(target_dir)
                self.status_label.setText(f"OmegaT project saved: {target_dir}")
                QMessageBox.information(self, "Success",
                    f"Exported to OmegaT format:\n{target_dir}")
                return
            elif "MCAT" in selected_filter:
                if not file_path.lower().endswith(".mcat.db"):
                    file_path += ".mcat.db"
                self.state.file_handler.save_file(file_path)
            elif "MQXLIFF" in selected_filter:
                if not file_path.endswith(".mqxliff"):
                    file_path += ".mqxliff"
                self.state.file_handler.save_as_mqxliif(file_path, src_lang, tgt_lang)
            elif "SDLXLIFF" in selected_filter:
                if not file_path.endswith(".sdlxliff"):
                    file_path += ".sdlxliff"
                from cat_tool.formats.sdlxliff import SdlxliffHandler
                SdlxliffHandler().save(self.state.file_handler.segments, file_path, src_lang, tgt_lang)
                self.state.file_handler.current_file_path = file_path
            else:
                self.state.file_handler.save_file(file_path)
            self.modified = False
            self.status_label.setText(f"Saved: {os.path.basename(file_path)}")
            QMessageBox.information(self, "Success", "File saved successfully.")
        except Exception as e:
            QMessageBox.critical(self, "Error Saving File", str(e))

    # ----------------- RENDER TRANSLATED -----------------
    def render_translated_file(self):
        if not self.state.file_handler.segments:
            QMessageBox.warning(self, "No Data", "No file loaded. Open a file first.")
            return
        ext = os.path.splitext(self.state.file_handler.current_file_path or "")[1].lower()
        ext_filter = f"Translated {ext.upper()} (*{ext})" if ext else "All Files (*)"
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Translated File As", f"translated{ext}", ext_filter
        )
        if not file_path:
            return
        try:
            self.state.file_handler.render_translated(file_path)
            self.status_label.setText(f"Rendered: {os.path.basename(file_path)}")
            QMessageBox.information(self, "Success", f"Translated file saved:\n{file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Render Error", str(e))

    # ----------------- SELECTION & CONFIRMATION -----------------
    def segment_selected(self):
        row = self.table.currentRow()
        if row < 0:
            return

        self.current_segment_index = row
        seg = self.state.file_handler.segments[row]

        self.fuzzy_checkbox.blockSignals(True)
        self.fuzzy_checkbox.setChecked(seg["fuzzy"])
        self.fuzzy_checkbox.blockSignals(False)

        self._selection_debounce.start()

    def fuzzy_state_changed(self, state):
        if self.current_segment_index < 0:
            return
        seg = self.state.file_handler.segments[self.current_segment_index]
        seg["fuzzy"] = (state == Qt.Checked)
        self.modified = True
        self.update_table_row_status(self.current_segment_index, seg)
        self.update_stats()

    def update_table_row_status(self, row, seg):
        self.table.blockSignals(True)
        item = self.table.item(row, 1)
        if item:
            item.setText(seg.get("target_clean", seg["target"]))
            self.set_target_cell_style(item, seg)
        src_item = self.table.item(row, 0)
        if src_item:
            self.set_source_cell_style(src_item, seg)
        self.table.blockSignals(False)

    def confirm_active_segment(self):
        if self.current_segment_index < 0:
            return

        row = self.current_segment_index
        item = self.table.item(row, 1)
        cell_text = item.text().strip() if item else ""

        seg = self.state.file_handler.segments[row]
        tags = seg.get("all_tags", [])
        restored = restore_tags(cell_text, tags)
        if seg["target"] == restored and seg["translated"] == bool(restored):
            pass
        else:
            seg["target"] = restored
            seg["translated"] = bool(restored)
            new_tgt_tags = extract_all_tags(restored)
            all_tags = list(tags)
            for t in new_tgt_tags:
                if t not in all_tags:
                    all_tags.append(t)
            seg["all_tags"] = all_tags
            seg["target_clean"] = apply_tags(restored, all_tags)
            if restored:
                row_id = self.state.tm.add_translation(seg["source"], restored, self.state.tm_sl, self.state.tm_tl)
                if row_id is not None:
                    self._ensure_emb_worker()
                    self._emb_requested.emit(seg["source"], row_id)

            self.modified = True
            if item:
                item.setText(seg["target_clean"])
            self.update_table_row_status(row, seg)

        self.update_stats()

        if row < len(self.state.file_handler.segments) - 1:
            self.table.selectRow(row + 1)
            self._edit_target_cell(row + 1)
        else:
            self.status_label.setText("Reached the end of the file!")

    # ----------------- SEGMENT NAVIGATION -----------------
    def _edit_target_cell(self, row):
        idx = self.table.model().index(row, 1)
        self.table.edit(idx)

    def _go_next_segment(self):
        if not self.state.file_handler.segments:
            return
        next_idx = self.current_segment_index + 1
        if next_idx < len(self.state.file_handler.segments):
            self.table.selectRow(next_idx)
            self._edit_target_cell(next_idx)
        else:
            self.status_label.setText("Already at the last segment.")

    def _go_prev_segment(self):
        if not self.state.file_handler.segments:
            return
        prev_idx = self.current_segment_index - 1
        if prev_idx >= 0:
            self.table.selectRow(prev_idx)
            self._edit_target_cell(prev_idx)
        else:
            self.status_label.setText("Already at the first segment.")

    def _go_next_untranslated(self):
        if not self.state.file_handler.segments:
            return
        start = self.current_segment_index + 1
        for i in range(start, len(self.state.file_handler.segments)):
            seg = self.state.file_handler.segments[i]
            if not seg.get("translated", False) or not seg.get("target", "").strip():
                self.table.selectRow(i)
                self._edit_target_cell(i)
                return
        self.status_label.setText("No more untranslated segments.")

    # ----------------- CONTEXT MENU -----------------
    def _table_context_menu(self, pos):
        index = self.table.indexAt(pos)
        if not index.isValid():
            return
        row = index.row()
        col = index.column()
        if row < 0 or row >= len(self.state.file_handler.segments):
            return
        seg = self.state.file_handler.segments[row]
        self.table.selectRow(row)

        menu = QMenu(self)
        view_action = menu.addAction("View Tags")
        if col == 0:
            view_action.triggered.connect(lambda: TagViewDialog(seg, 0, self).exec_())
        else:
            view_action.triggered.connect(lambda: self._show_tag_dialog_for_target(seg))
        menu.addSeparator()
        spell_action = menu.addAction("Spell Check Segment")
        spell_action.triggered.connect(lambda: self._spellcheck_segment(seg))
        menu.exec_(self.table.viewport().mapToGlobal(pos))

    def _show_tag_dialog_for_target(self, seg):
        dlg = TagViewDialog(seg, 1, self)
        dlg.exec_()

    def _spellcheck_segment(self, seg):
        dlg = SpellCheckDialog([seg], self.state.spellchecker, self)
        dlg.exec_()
        self.populate_table(self.state.file_handler.segments)

    def show_options(self):
        dlg = SettingsDialog(self.state.settings, self)
        if dlg.exec_() == QDialog.Accepted:
            self._apply_settings()

    def _apply_settings(self):
        font = self.table.font()
        font.setPointSize(self.state.settings["source_font_size"])
        self.table.horizontalHeaderItem(0).setFont(font) if self.table.horizontalHeaderItem(0) else None
        if self.state.settings["source_font_size"] != self.state.settings["target_font_size"]:
            tgt_font = QFont(font)
            tgt_font.setPointSize(self.state.settings["target_font_size"])
            self.table.horizontalHeaderItem(1).setFont(tgt_font) if self.table.horizontalHeaderItem(1) else None
        self.table.setFont(font)

    # ----------------- SIDEBAR SUGGESTIONS & INTERACTIONS -----------------
    def update_fuzzy_matches(self, source_text):
        self._ensure_fuzzy_worker()
        self._fuzzy_requested.emit(
            source_text,
            self.state.tm_sl or "",
            self.state.tm_tl or ""
        )

    def _on_fuzzy_matches_ready(self, matches):
        if self.current_segment_index < 0:
            return
        current_source = self.state.file_handler.segments[self.current_segment_index]["source"]
        if current_source != self._pending_fuzzy_source:
            return
        self.tm_list.clear()
        for m in matches:
            item = QListWidgetItem(f"[{m['score']}% Match] {m['target']}\n(From: \"{m['source']}\")")
            item.setData(Qt.UserRole, m["target"])
            self.tm_list.addItem(item)

    def apply_tm_suggestion(self, item):
        target_suggestion = item.data(Qt.UserRole)
        if target_suggestion and self.current_segment_index >= 0:
            tgt_item = self.table.item(self.current_segment_index, 1)
            if tgt_item:
                tgt_item.setText(target_suggestion)
                self._edit_target_cell(self.current_segment_index)

    def update_glossary_matches(self, source_text):
        self.glossary_table.setRowCount(0)
        matches = self.state.glossary.check_segment(source_text)
        self.glossary_table.setRowCount(len(matches))
        for idx, m in enumerate(matches):
            src_item = QTableWidgetItem(m["source"])
            tgt_item = QTableWidgetItem(m["target"])
            src_item.setFlags(src_item.flags() & ~Qt.ItemIsEditable)
            tgt_item.setFlags(tgt_item.flags() & ~Qt.ItemIsEditable)
            if m["description"]:
                src_item.setToolTip(m["description"])
                tgt_item.setToolTip(m["description"])
            self.glossary_table.setItem(idx, 0, src_item)
            self.glossary_table.setItem(idx, 1, tgt_item)

    def insert_glossary_term(self, item):
        glossary_row = item.row()
        term_item = self.glossary_table.item(glossary_row, 1)
        if not term_item or self.current_segment_index < 0:
            return
        tgt_item = self.table.item(self.current_segment_index, 1)
        if tgt_item:
            current = tgt_item.text()
            tgt_item.setText(current + term_item.text())
            self._edit_target_cell(self.current_segment_index)

    # ----------------- GLOSSARY MANAGEMENT -----------------
    def add_glossary_term(self):
        src_lang = self.state.project.source_lang if self.state.project else "en"
        tgt_lang = self.state.project.target_lang if self.state.project else ""
        dial = GlossaryDialog(self, source_lang=src_lang, target_lang=tgt_lang)
        if dial.exec_() == QDialog.Accepted:
            src, tgt, desc, sl, tl = dial.get_data()
            if src and tgt:
                self.state.glossary.add_term(src, tgt, desc, source_lang=sl, target_lang=tl)
                self.status_label.setText(f"Added glossary term: '{src}'")
                if self.current_segment_index >= 0:
                    seg = self.state.file_handler.segments[self.current_segment_index]
                    self.update_glossary_matches(seg["source"])
            else:
                QMessageBox.warning(self, "Invalid Input", "Source and Target cannot be empty.")

    def import_tmx_to_glossary(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Import TMX into Glossary", "",
            "TMX Files (*.tmx);;All Files (*)")
        if not path:
            return
        try:
            info = self.state.glossary.peek_tmx(path)
            if info["count"] == 0 and not info.get("source_lang"):
                QMessageBox.information(self, "No Terms",
                    "No translatable term pairs found in this TMX file.")
                return

            sl = info["source_lang"] or (self.state.project.source_lang if self.state.project else "en")
            tl = info["target_lang"] or ""

            dlg = LangDialog(sl, tl, info["count"], self)
            if dlg.exec_() != QDialog.Accepted:
                return

            source_lang = dlg.src_combo.currentData() or sl
            target_lang = dlg.tgt_combo.currentData() or tl

            count = self.state.glossary.import_tmx(path, source_lang=source_lang)
            QMessageBox.information(
                self, "Import Complete",
                f"Imported {count} terms from TMX into glossary.\n"
                f"Source: {source_lang}  |  Target: {target_lang}")
        except Exception as e:
            QMessageBox.critical(self, "Import Error", f"Failed to import TMX:\n{e}")

    def export_glossary_as_tmx(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Glossary as TMX", "",
            "TMX Files (*.tmx);;All Files (*)")
        if not path:
            return
        if not path.lower().endswith(".tmx"):
            path += ".tmx"
        try:
            count = self.state.glossary.export_tmx(path)
            if count:
                QMessageBox.information(self, "Export Complete", f"Exported {count} terms to TMX.")
            else:
                QMessageBox.information(self, "Export Complete", "Glossary is empty — no terms exported.")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to export TMX:\n{e}")

    # ----------------- COLLECTIONS MANAGEMENT -----------------
    def create_collection_dialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Create Collection")
        dialog.setMinimumWidth(400)
        layout = QFormLayout(dialog)
        name_edit = QLineEdit()
        name_edit.setPlaceholderText("My Collection")
        desc_edit = QLineEdit()
        desc_edit.setPlaceholderText("Optional description")
        layout.addRow("Collection Name:", name_edit)
        layout.addRow("Description:", desc_edit)
        btn_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btn_box.accepted.connect(dialog.accept)
        btn_box.rejected.connect(dialog.reject)
        layout.addRow(btn_box)
        if dialog.exec_() != QDialog.Accepted:
            return
        name = name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Invalid", "Collection name cannot be empty.")
            return
        coll_id = self.state.glossary.create_collection(name, desc_edit.text().strip())
        if coll_id is None:
            QMessageBox.warning(self, "Duplicate", f"Collection '{name}' already exists.")
            return
        self.status_label.setText(f"Created collection: '{name}'")

    def manage_collections(self):
        collections = self.state.glossary.get_all_collections()
        if not collections:
            if QMessageBox.question(self, "No Collections",
                    "No collections yet. Create one now?",
                    QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
                self.create_collection_dialog()
                collections = self.state.glossary.get_all_collections()
            if not collections:
                return

        dialog = QDialog(self)
        dialog.setWindowTitle("Manage Collections")
        dialog.setMinimumSize(700, 450)
        layout = QVBoxLayout(dialog)
        hsplit = QSplitter(Qt.Horizontal)

        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(QLabel("Collections:"))
        coll_list = QListWidget()
        left_layout.addWidget(coll_list)
        coll_btn_layout = QHBoxLayout()
        create_btn = QPushButton("Create")
        create_btn.setToolTip("Create a new collection")
        delete_btn = QPushButton("Delete")
        delete_btn.setToolTip("Delete the selected collection")
        coll_btn_layout.addWidget(create_btn)
        coll_btn_layout.addWidget(delete_btn)
        left_layout.addLayout(coll_btn_layout)

        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.addWidget(QLabel("Terms in collection:"))
        terms_tbl = QTableWidget()
        terms_tbl.setColumnCount(4)
        terms_tbl.setHorizontalHeaderLabels(["Source", "Translation", "SL", "TL"])
        terms_tbl.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        right_layout.addWidget(terms_tbl)
        term_btn_layout = QHBoxLayout()
        add_term_btn = QPushButton("Add Term...")
        add_term_btn.setToolTip("Select a glossary term to add to this collection")
        rem_term_btn = QPushButton("Remove Selected")
        rem_term_btn.setToolTip("Remove the selected term from this collection")
        term_btn_layout.addWidget(add_term_btn)
        term_btn_layout.addWidget(rem_term_btn)
        term_btn_layout.addStretch()
        right_layout.addLayout(term_btn_layout)

        hsplit.addWidget(left_widget)
        hsplit.addWidget(right_widget)
        hsplit.setStretchFactor(0, 1)
        hsplit.setStretchFactor(1, 2)
        layout.addWidget(hsplit)

        btn_layout = QHBoxLayout()
        close_btn = QPushButton("Close")
        close_btn.setToolTip("Close collections manager")
        close_btn.clicked.connect(dialog.accept)
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

        coll_map = {}
        def refresh_collection_list():
            coll_list.clear()
            coll_map.clear()
            for c in self.state.glossary.get_all_collections():
                coll_list.addItem(f"{c['name']}  ({c['description']})" if c['description'] else c['name'])
                coll_map[coll_list.count() - 1] = c["id"]

        def refresh_terms():
            terms_tbl.setRowCount(0)
            sel = coll_list.currentRow()
            if sel < 0 or sel not in coll_map:
                return
            cid = coll_map[sel]
            terms = self.state.glossary.get_collection_terms(cid)
            terms_tbl.setRowCount(len(terms))
            for idx, t in enumerate(terms):
                terms_tbl.setItem(idx, 0, QTableWidgetItem(t["source"]))
                terms_tbl.setItem(idx, 1, QTableWidgetItem(t["target"]))
                terms_tbl.setItem(idx, 2, QTableWidgetItem(t.get("source_lang", "")))
                terms_tbl.setItem(idx, 3, QTableWidgetItem(t.get("target_lang", "")))

        def on_coll_selected():
            refresh_terms()

        def do_create():
            dialog.close()
            self.create_collection_dialog()
            refresh_collection_list()

        def do_delete():
            sel = coll_list.currentRow()
            if sel < 0 or sel not in coll_map:
                return
            cid = coll_map[sel]
            name = coll_list.currentItem().text().split("  (")[0] if coll_list.currentItem() else ""
            if QMessageBox.question(dialog, "Confirm Delete",
                    f"Delete collection '{name}' and all its term associations?",
                    QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
                return
            self.state.glossary.delete_collection(cid)
            self.status_label.setText(f"Deleted collection: '{name}'")
            refresh_collection_list()
            terms_tbl.setRowCount(0)

        def do_add_term():
            sel = coll_list.currentRow()
            if sel < 0 or sel not in coll_map:
                QMessageBox.information(dialog, "No Collection", "Select a collection first.")
                return
            cid = coll_map[sel]
            all_terms = self.state.glossary.get_all_terms()
            if not all_terms:
                QMessageBox.information(dialog, "No Terms", "The glossary is empty.")
                return
            existing = {t["source"] for t in self.state.glossary.get_collection_terms(cid)}
            available = [t for t in all_terms if t["source"] not in existing]
            if not available:
                QMessageBox.information(dialog, "All Added", "All glossary terms are already in this collection.")
                return
            picker = QDialog(dialog)
            picker.setWindowTitle("Add Term to Collection")
            picker.setMinimumWidth(450)
            ply = QVBoxLayout(picker)
            ply.addWidget(QLabel("Select a term to add:"))
            pick_list = QListWidget()
            for t in available:
                pick_list.addItem(f"{t['source']} → {t['target']}")
            ply.addWidget(pick_list)
            pb = QHBoxLayout()
            ok_btn = QPushButton("Add")
            ok_btn.clicked.connect(picker.accept)
            cancel_btn = QPushButton("Cancel")
            cancel_btn.clicked.connect(picker.reject)
            pb.addWidget(ok_btn)
            pb.addWidget(cancel_btn)
            ply.addLayout(pb)
            if picker.exec_() != QDialog.Accepted or pick_list.currentRow() < 0:
                return
            selected_term = available[pick_list.currentRow()]["source"]
            self.state.glossary.add_term_to_collection(cid, selected_term)
            self.status_label.setText(f"Added '{selected_term}' to collection")
            refresh_terms()

        def do_remove_term():
            sel = coll_list.currentRow()
            if sel < 0 or sel not in coll_map:
                return
            cid = coll_map[sel]
            row = terms_tbl.currentRow()
            if row < 0:
                return
            src = terms_tbl.item(row, 0).text()
            if QMessageBox.question(dialog, "Confirm Remove",
                    f"Remove '{src}' from this collection? (Term stays in glossary)",
                    QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
                return
            self.state.glossary.remove_term_from_collection(cid, src)
            self.status_label.setText(f"Removed '{src}' from collection")
            refresh_terms()

        coll_list.currentRowChanged.connect(on_coll_selected)
        create_btn.clicked.connect(do_create)
        delete_btn.clicked.connect(do_delete)
        add_term_btn.clicked.connect(do_add_term)
        rem_term_btn.clicked.connect(do_remove_term)

        refresh_collection_list()
        if coll_list.count() > 0:
            coll_list.setCurrentRow(0)
        dialog.exec_()

    def import_collection_tmx(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Import Collection as TMX", "",
            "TMX Files (*.tmx);;All Files (*)")
        if not path:
            return
        try:
            count, coll_id = self.state.glossary.import_collection_tmx(path)
            if coll_id is None:
                QMessageBox.warning(self, "Import Failed",
                    "Could not create collection. Name may already exist.")
                return
            if count:
                QMessageBox.information(self, "Import Complete",
                    f"Imported {count} terms into a new collection.")
            else:
                QMessageBox.information(self, "No Terms",
                    "No translatable term pairs found in that TMX.")
        except Exception as e:
            QMessageBox.critical(self, "Import Error", str(e))

    def export_collection_tmx(self):
        collections = self.state.glossary.get_all_collections()
        if not collections:
            QMessageBox.information(self, "No Collections", "No collections to export.")
            return
        coll_names = [c["name"] for c in collections]
        picker = QDialog(self)
        picker.setWindowTitle("Export Collection as TMX")
        picker.setMinimumWidth(400)
        ply = QVBoxLayout(picker)
        ply.addWidget(QLabel("Select a collection to export:"))
        pick_list = QListWidget()
        for n in coll_names:
            pick_list.addItem(n)
        ply.addWidget(pick_list)
        pb = QHBoxLayout()
        ok_btn = QPushButton("Export")
        ok_btn.clicked.connect(picker.accept)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(picker.reject)
        pb.addWidget(ok_btn)
        pb.addWidget(cancel_btn)
        ply.addLayout(pb)
        if picker.exec_() != QDialog.Accepted or pick_list.currentRow() < 0:
            return
        coll = collections[pick_list.currentRow()]
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Collection TMX", f"{coll['name']}.tmx",
            "TMX Files (*.tmx);;All Files (*)")
        if not path:
            return
        if not path.lower().endswith(".tmx"):
            path += ".tmx"
        try:
            count = self.state.glossary.export_collection_tmx(coll["id"], path)
            if count:
                QMessageBox.information(self, "Export Complete",
                    f"Exported {count} terms from '{coll['name']}' to TMX.")
            else:
                QMessageBox.information(self, "Empty Collection", "That collection has no terms.")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", str(e))

    def view_glossary(self):
        terms = self.state.glossary.get_all_terms()
        dialog = QDialog(self)
        dialog.setWindowTitle("Glossary Terms List")
        dialog.setMinimumSize(650, 400)
        layout = QVBoxLayout(dialog)
        tbl = QTableWidget()
        tbl.setColumnCount(5)
        tbl.setHorizontalHeaderLabels(["Source Term", "SL", "Target Translation", "TL", "Description"])
        tbl.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        tbl.setRowCount(len(terms))

        for idx, t in enumerate(terms):
            tbl.setItem(idx, 0, QTableWidgetItem(t["source"]))
            tbl.setItem(idx, 1, QTableWidgetItem(t.get("source_lang", "")))
            tbl.setItem(idx, 2, QTableWidgetItem(t["target"]))
            tbl.setItem(idx, 3, QTableWidgetItem(t.get("target_lang", "")))
            tbl.setItem(idx, 4, QTableWidgetItem(t["description"]))

        layout.addWidget(tbl)
        btn_layout = QHBoxLayout()
        del_btn = QPushButton("Delete Selected", dialog)
        del_btn.setToolTip("Remove the selected glossary term")

        def delete_selected():
            selected_items = tbl.selectedItems()
            if not selected_items:
                return
            row = selected_items[0].row()
            src = tbl.item(row, 0).text()
            confirm = QMessageBox.question(
                dialog, "Confirm Delete",
                f"Delete glossary term '{src}'?",
                QMessageBox.Yes | QMessageBox.No)
            if confirm != QMessageBox.Yes:
                return
            self.state.glossary.remove_term(src)
            tbl.removeRow(row)
            self.status_label.setText(f"Deleted term: '{src}'")
            if self.current_segment_index >= 0:
                seg = self.state.file_handler.segments[self.current_segment_index]
                self.update_glossary_matches(seg["source"])

        del_btn.clicked.connect(delete_selected)
        btn_layout.addWidget(del_btn)
        close_btn = QPushButton("Close", dialog)
        close_btn.setToolTip("Close the glossary list")
        close_btn.clicked.connect(dialog.accept)
        btn_layout.addWidget(close_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        dialog.exec_()

    # ----------------- TM MANAGEMENT -----------------
    def import_po_to_tm(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Import PO for Translation Memory", "", "PO Files (*.po);;All Files (*)"
        )
        if not file_path:
            return
        try:
            imported_count, segments = self.state.import_po_to_tm(file_path)
            QMessageBox.information(
                self, "Success", f"Imported {imported_count} translations into translation memory."
            )
            if self.current_segment_index >= 0:
                seg = self.state.file_handler.segments[self.current_segment_index]
                self.update_fuzzy_matches(seg["source"])
        except Exception as e:
            QMessageBox.critical(self, "Import Error", str(e))

    def clear_tm(self):
        reply = QMessageBox.question(
            self, "Confirm Delete", "Are you sure you want to clear the entire Translation Memory?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.state.clear_tm()
            self.status_label.setText("Translation Memory cleared.")
            if self.current_segment_index >= 0:
                seg = self.state.file_handler.segments[self.current_segment_index]
                self.update_fuzzy_matches(seg["source"])

    def _toggle_fuzzy(self):
        if self.current_segment_index >= 0:
            self.fuzzy_checkbox.toggle()

    def _go_first_segment(self):
        if self.state.file_handler.segments:
            self.table.selectRow(0)
            self._edit_target_cell(0)

    def _go_last_segment(self):
        if self.state.file_handler.segments:
            last = len(self.state.file_handler.segments) - 1
            self.table.selectRow(last)
            self._edit_target_cell(last)

    def show_shortcuts(self):
        dlg = ShortcutsDialog(self)
        dlg.exec_()

    def _open_dicts_page(self):
        import webbrowser
        webbrowser.open("https://extensions.libreoffice.org/en?Tags%5B%5D=50")

    def navigate_to_segment(self, segment_index):
        if 0 <= segment_index < len(self.state.file_handler.segments):
            self.table.selectRow(segment_index)
            self._edit_target_cell(segment_index)

    def run_qa(self):
        if not self.state.file_handler.segments:
            QMessageBox.warning(self, "No Data", "Open a file first before running QA.")
            return
        issues = qa.run_all_checks(self.state.file_handler.segments, glossary=self.state.glossary)
        dlg = QADialog(issues, self)
        dlg.exec_()

    def import_dictionary(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Import Dictionary", "",
            "Dictionary (*.oxt *.zip *.dic);;All Files (*)"
        )
        if not path:
            return
        if path.endswith(".dic"):
            ok = self.state.spellchecker.load_dictionary(path)
        else:
            ok = self.state.spellchecker.load_from_archive(path)
        if ok:
            names = self.state.spellchecker.loaded_names
            QMessageBox.information(
                self, "Success",
                f"Dictionary imported.\nLoaded: {', '.join(names)}"
            )
        else:
            QMessageBox.warning(self, "Error", "Failed to load dictionary.\n\n"
                                "Make sure the file contains valid .dic/.aff files.")

    def _load_spelling_dict_for_language(self, lang_code):
        found = self.state.load_spelling_dict(lang_code)
        if found:
            self.status_label.setText(f"Loaded spelling dictionary: {found}")
        elif lang_code:
            self.status_label.setText(
                f"No spelling dictionary found for '{lang_code}'. "
                f"Use Tools > Import Dictionary to add one."
            )

    def run_spellcheck(self):
        if not self.state.file_handler.segments:
            QMessageBox.warning(self, "No Data", "Open a file first before spell check.")
            return
        dlg = SpellCheckDialog(self.state.file_handler.segments, self.state.spellchecker, self)
        dlg.exec_()
        self.populate_table(self.state.file_handler.segments)

    # ----------------- STATS UPDATE -----------------
    def update_stats(self):
        stats = self.state.compute_stats()
        if stats["total"] == 0:
            self.progress_bar.setValue(0)
            self.progress_bar.setFormat("No file loaded")
            return

        self.progress_bar.setValue(stats["percent"])
        self.progress_bar.setFormat(f"%p% ({stats['translated']}/{stats['total']})")

        proj_name = self.state.project.name if self.state.project else "No Project"
        self.status_label.setText(
            f"[{proj_name}] "
            f"Active File: {os.path.basename(self.state.file_handler.current_file_path or 'None')} | "
            f"Translated: {stats['translated']} | Fuzzy: {stats['fuzzy']} | Total: {stats['total']} | "
            f"Words: {stats['total_words']} | Chars: {stats['total_chars']}"
        )
        title = f"mcat - {proj_name}"
        if self.state.file_handler.current_file_path:
            title += f" [{os.path.basename(self.state.file_handler.current_file_path)}]"
        self.setWindowTitle(title)

    # ----------------- PROJECT OPERATIONS -----------------
    def close_project(self):
        if not self.state.project:
            return
        if self.modified:
            reply = QMessageBox.question(
                self, "Unsaved Changes",
                "You have unsaved changes. Save before closing?",
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel
            )
            if reply == QMessageBox.Cancel:
                return
            if reply == QMessageBox.Yes:
                self.save_project()

        proj_name = self.state.close_project()
        self.current_segment_index = -1
        self.modified = False
        self.table.setRowCount(0)
        self.tm_list.clear()
        self.glossary_table.setRowCount(0)
        self.status_label.setText(f"Project closed: {proj_name}")

    def new_project(self):
        if self.modified:
            reply = QMessageBox.question(
                self, "Unsaved Changes",
                "You have unsaved changes. Start a new project anyway?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.No:
                return

        dial = NewProjectDialog(self)
        if dial.exec_() != QDialog.Accepted:
            return

        name, src_lang, tgt_lang, src_files = dial.get_data()
        self.state.new_project(name, src_lang, tgt_lang, src_files)
        self.current_segment_index = -1
        self.modified = False

        if src_files:
            self._open_project_source_file(0)
        else:
            self.table.setRowCount(0)

        self.update_stats()
        self._load_spelling_dict_for_language(tgt_lang)
        self.status_label.setText(f"Created project: {name}")

    def open_project(self):
        if self.modified:
            reply = QMessageBox.question(
                self, "Unsaved Changes",
                "You have unsaved changes. Open a different project anyway?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.No:
                return

        filter_str = "CAT Project (*.mcatproj);;OmegaT Project (folder with omegat.project);;memoQ Project (folder with manifest.xml)"
        file_path, selected_filter = QFileDialog.getOpenFileName(
            self, "Open Project", "", filter_str
        )
        if not file_path:
            return

        if "OmegaT" in selected_filter:
            dir_path = QFileDialog.getExistingDirectory(
                self, "Select OmegaT Project Folder (contains omegat.project)"
            )
            if not dir_path:
                return
            proj_file = os.path.join(dir_path, "omegat.project")
            if not os.path.exists(proj_file):
                QMessageBox.warning(self, "Invalid Project",
                                    "Selected folder does not contain omegat.project")
                return
            self._load_omegat(dir_path)
        elif "memoQ" in selected_filter:
            dir_path = QFileDialog.getExistingDirectory(
                self, "Select memoQ Project Folder (contains manifest.xml)"
            )
            if not dir_path:
                return
            manifest_file = os.path.join(dir_path, "manifest.xml")
            if not os.path.exists(manifest_file):
                QMessageBox.warning(self, "Invalid Project",
                                    "Selected folder does not contain manifest.xml")
                return
            self._load_memoq(dir_path)
        else:
            self._load_project(file_path)

    def _load_project(self, file_path):
        try:
            self.state.load_project(file_path)
            self.current_segment_index = -1
            self.modified = False

            if self.state.project.source_files:
                self._open_project_source_file(0)
            else:
                self.table.setRowCount(0)

            self._update_recent_menu()
            self.update_stats()
            self._load_spelling_dict_for_language(self.state.project.target_lang)
            self.status_label.setText(f"Opened project: {self.state.project.name}")
        except Exception as e:
            QMessageBox.critical(self, "Error Opening Project", str(e))

    def _load_omegat(self, dir_path):
        try:
            self.state.load_omegat(dir_path)
            self.current_segment_index = -1
            self.modified = False

            if self.state.project.source_files:
                self._open_project_source_file(0)
            else:
                self.table.setRowCount(0)

            self._update_recent_menu()
            self.update_stats()
            self._load_spelling_dict_for_language(self.state.project.target_lang)
            self.status_label.setText(f"Opened OmegaT project: {self.state.project.name}")
        except Exception as e:
            QMessageBox.critical(self, "Error Opening Project", str(e))

    def project_settings(self):
        if not self.state.project:
            QMessageBox.information(self, "No Project", "No project is currently open.")
            return

        dial = ProjectSettingsDialog(self.state.project, self)
        if dial.exec_() != QDialog.Accepted:
            return

        dial.apply()
        self.modified = True
        self.update_stats()
        self._load_spelling_dict_for_language(self.state.project.target_lang)
        self.status_label.setText("Project settings updated.")

    def _open_project_source_file(self, index):
        segments, label, ok, error = self.state.open_project_source_file(index)
        if not ok:
            if error and "not found" in error.lower():
                QMessageBox.warning(self, "File Not Found", error)
            else:
                QMessageBox.critical(self, "Error Loading Source File", error or "Unknown error")
            return

        self.populate_table(segments)
        if segments:
            self.table.selectRow(0)
        self.update_stats()
        self.status_label.setText(f"Loaded: {label}")

    def save_project(self):
        if not self.state.project:
            QMessageBox.information(self, "No Project", "No project is currently open.")
            return
        if not self.state.project.file_path:
            self.save_project_as()
            return
        try:
            self.state.save_project()
            self.modified = False
            self._update_recent_menu()
            self.update_stats()
            self.status_label.setText(f"Project saved: {self.state.project.name}")
        except Exception as e:
            QMessageBox.critical(self, "Error Saving Project", str(e))

    def save_project_as(self):
        if not self.state.project:
            QMessageBox.information(self, "No Project", "No project is currently open.")
            return
        filter_str = "CAT Project (*.mcatproj);;OmegaT Project folder;;memoQ Project folder"
        file_path, selected_filter = QFileDialog.getSaveFileName(
            self, "Save Project As", f"{self.state.project.name}.mcatproj", filter_str
        )
        if not file_path:
            return

        if "OmegaT" in selected_filter:
            dir_path = QFileDialog.getExistingDirectory(
                self, "Select folder to create OmegaT project in",
                os.path.dirname(file_path) if os.path.dirname(file_path) else ""
            )
            if not dir_path:
                return
            target_dir = os.path.join(dir_path, self.state.project.name)
            try:
                self.state.save_project_as_omegat(target_dir)
                self.modified = False
                self._update_recent_menu()
                self.update_stats()
                self.status_label.setText(f"OmegaT project saved: {target_dir}")
                QMessageBox.information(
                    self, "Success",
                    f"Project exported to OmegaT format:\n{target_dir}\n\n"
                    f"Source files copied to '{target_dir}\\source\\'.\n"
                    f"You can open this folder directly in OmegaT."
                )
            except Exception as e:
                QMessageBox.critical(self, "Export Error", str(e))
        elif "memoQ" in selected_filter:
            dir_path = QFileDialog.getExistingDirectory(
                self, "Select folder to create memoQ project in",
                os.path.dirname(file_path) if os.path.dirname(file_path) else ""
            )
            if not dir_path:
                return
            target_dir = os.path.join(dir_path, self.state.project.name)
            try:
                self.state.save_project_as_memoq(target_dir, self.state.file_handler)
                self.modified = False
                self._update_recent_menu()
                self.update_stats()
                self.status_label.setText(f"memoQ project saved: {target_dir}")
                QMessageBox.information(
                    self, "Success",
                    f"Project exported to memoQ format:\n{target_dir}\n\n"
                    f"Source files copied to '{target_dir}\\source\\'.\n"
                    f"Translations saved as MQXLIFF in '{target_dir}\\target\\'.\n"
                    f"You can open the .mqxliff file directly in memoQ."
                )
            except Exception as e:
                QMessageBox.critical(self, "Export Error", str(e))
        else:
            if not file_path.endswith(".mcatproj"):
                file_path += ".mcatproj"
            try:
                self.state.save_project_as_mcatproj(file_path)
                self.modified = False
                self._update_recent_menu()
                self.update_stats()
                self.status_label.setText(f"Project saved: {self.state.project.name}")
            except Exception as e:
                QMessageBox.critical(self, "Error Saving Project", str(e))

    def open_segmentation_rules(self):
        code = self.state.current_lang_code
        from cat_tool.segmentation import AdvancedRulesDialog
        dlg = AdvancedRulesDialog(self, self.state.segmentation_rules, lang_code=code)
        if dlg.exec_() == QDialog.Accepted:
            self.state.segmentation_rules = dlg.get_rules()
            self.status_label.setText(
                f"Segmentation rules saved to {code}.json ({len(self.state.segmentation_rules)} rules)"
            )

    def import_omegat_project(self):
        dir_path = QFileDialog.getExistingDirectory(
            self, "Select OmegaT Project Folder (contains omegat.project)"
        )
        if not dir_path:
            return
        proj_file = os.path.join(dir_path, "omegat.project")
        if not os.path.exists(proj_file):
            QMessageBox.warning(self, "Invalid Project",
                                "Selected folder does not contain omegat.project")
            return
        try:
            self.state.load_omegat(dir_path)
            self.current_segment_index = -1
            self.modified = False
            if self.state.project.source_files:
                self._open_project_source_file(0)
            else:
                self.table.setRowCount(0)
            self._update_recent_menu()
            self.update_stats()
            self.status_label.setText(f"Imported OmegaT project: {self.state.project.name}")
        except Exception as e:
            QMessageBox.critical(self, "Import Error", str(e))

    # ----------------- MEMOQ PROJECTS -----------------
    def import_memoq_project(self):
        dir_path = QFileDialog.getExistingDirectory(
            self, "Select memoQ Project Folder (contains manifest.xml)"
        )
        if not dir_path:
            return
        manifest_file = os.path.join(dir_path, "manifest.xml")
        if not os.path.exists(manifest_file):
            QMessageBox.warning(self, "Invalid Project",
                                "Selected folder does not contain manifest.xml")
            return
        self._load_memoq(dir_path)

    def _load_memoq(self, dir_path):
        try:
            self.state.load_memoq(dir_path)
            self.current_segment_index = -1
            self.modified = False

            if self.state.project.mqxliff_files:
                self.state.file_handler.load_file(self.state.project.mqxliff_files[0])
                self.populate_table(self.state.file_handler.segments)
                if self.state.file_handler.segments:
                    self.table.selectRow(0)
            elif self.state.project.source_files:
                self._open_project_source_file(0)
            else:
                self.table.setRowCount(0)

            self._update_recent_menu()
            self.update_stats()
            self._load_spelling_dict_for_language(self.state.project.target_lang)
            self.status_label.setText(f"Opened memoQ project: {self.state.project.name}")
        except Exception as e:
            QMessageBox.critical(self, "Error Opening memoQ Project", str(e))

    # ----------------- SDL TRADOS -----------------
    def import_sdlxliff(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open SDL Trados SDLXLIFF", "", "SDLXLIFF (*.sdlxliff);;All Files (*)"
        )
        if not file_path:
            return
        self.status_label.setText("Loading SDLXLIFF...")
        self._ensure_seg_worker()
        self._seg_requested.emit(file_path)

    def _update_recent_menu(self):
        self.recent_menu.clear()
        from cat_tool.project import Project
        recents = Project.get_recent()
        if not recents:
            action = self.recent_menu.addAction("(No recent projects)")
            action.setEnabled(False)
            return
        for r in recents:
            path = r.get("path", "")
            name = r.get("name", os.path.basename(path))
            action = self.recent_menu.addAction(f"{name}  [{os.path.basename(os.path.dirname(path))}]")
            action.setData(path)
            action.triggered.connect(lambda checked, p=path: self._load_project(p))
