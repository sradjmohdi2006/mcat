"""Read-only document view used to define manual translation units."""
import os

from PyQt5.QtCore import QEvent, Qt, pyqtSignal
from PyQt5.QtGui import QColor, QKeySequence, QTextCursor
from PyQt5.QtWidgets import (
    QComboBox, QHBoxLayout, QLabel, QListWidget, QMenu, QMessageBox,
    QPushButton, QShortcut, QSplitter, QTextEdit, QVBoxLayout, QWidget,
)

from cat_tool.manual_segmentation import (
    ManualSegmentationError, ManualSegmenter,
)

_COMMITTED_COLOR = QColor("#1f3a5f")
_MARKED_COLOR = QColor("#594a00")
_START_COLOR = QColor("#145a32")
_TEXT_COLOR = QColor("#ffffff")


class ManualSegmentationView(QWidget):
    """Document view where translation-unit boundaries are defined."""

    segmentsChanged = pyqtSignal(list)
    editStarted = pyqtSignal()
    finished = pyqtSignal()
    fileChangeRequested = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.segmenter = None
        self.segments = []
        self._done = False
        self._loading = False
        self.setAccessibleName("Manual Segmentation")
        self.setAccessibleDescription(
            "Define translation units by placing the cursor on a word or "
            "punctuation mark and choosing Set Unit Start and Set Unit End.")
        self._build_ui()
        self._install_shortcuts()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        top = QHBoxLayout()
        top.addWidget(QLabel("File:"))
        self.file_combo = QComboBox()
        self.file_combo.setMinimumWidth(280)
        self.file_combo.currentIndexChanged.connect(self._on_file_changed)
        top.addWidget(self.file_combo)
        top.addStretch()
        self.stage_label = QLabel("Naming \u2014 define translation units")
        top.addWidget(self.stage_label)
        layout.addLayout(top)

        splitter = QSplitter(Qt.Horizontal)

        self.document = QTextEdit()
        self.document.setReadOnly(True)
        self.document.setTextInteractionFlags(
            self.document.textInteractionFlags()
            | Qt.TextSelectableByKeyboard)
        self.document.setAcceptRichText(False)
        self.document.setAccessibleName("Document text")
        self.document.setAccessibleDescription(
            "Read-only document text. Place the cursor on a word or "
            "punctuation mark, then use the context menu or the buttons.")
        self.document.setContextMenuPolicy(Qt.CustomContextMenu)
        self.document.customContextMenuRequested.connect(
            self._show_context_menu_at)
        self.document.installEventFilter(self)
        splitter.addWidget(self.document)

        preview_panel = QWidget()
        preview_layout = QVBoxLayout(preview_panel)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        preview_layout.addWidget(QLabel("Defined units"))
        self.preview = QListWidget()
        self.preview.setAccessibleName("Defined units")
        preview_layout.addWidget(self.preview)
        self.count_label = QLabel("Committed: 0   Marked: 0")
        preview_layout.addWidget(self.count_label)
        splitter.addWidget(preview_panel)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter, 1)

        button_row = QHBoxLayout()
        self.start_btn = QPushButton("Set Unit Start")
        self.end_btn = QPushButton("Set Unit End")
        self.split_btn = QPushButton("Split")
        self.split_all_btn = QPushButton("Split All")
        self.clear_btn = QPushButton("Clear Pending")
        self.undo_btn = QPushButton("Undo")
        self.finish_btn = QPushButton("Finish Segmentation")
        self.edit_btn = QPushButton("Edit Segmentation")
        self.edit_btn.setVisible(False)

        self.start_btn.clicked.connect(self.mark_start)
        self.end_btn.clicked.connect(self.mark_end)
        self.split_btn.clicked.connect(self.split)
        self.split_all_btn.clicked.connect(self.split_all)
        self.clear_btn.clicked.connect(self.clear_pending)
        self.undo_btn.clicked.connect(self.undo)
        self.finish_btn.clicked.connect(self.finish_segmentation)
        self.edit_btn.clicked.connect(self.edit_segmentation)

        button_row.addWidget(self.start_btn)
        button_row.addWidget(self.end_btn)
        button_row.addWidget(self.split_btn)
        button_row.addWidget(self.split_all_btn)
        button_row.addStretch()
        button_row.addWidget(self.clear_btn)
        button_row.addWidget(self.undo_btn)
        button_row.addWidget(self.finish_btn)
        button_row.addWidget(self.edit_btn)
        layout.addLayout(button_row)

        self.status_label = QLabel(
            "Place the cursor on a word, then set a unit start and unit end.")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

    def _install_shortcuts(self):
        shortcuts = [
            ("Ctrl+[", self.mark_start),
            ("Ctrl+]", self.mark_end),
            ("Ctrl+Return", self.split),
            ("Ctrl+Shift+Return", self.split_all),
            ("Esc", self.clear_pending),
            ("Ctrl+Z", self.undo),
        ]
        for sequence, callback in shortcuts:
            shortcut = QShortcut(QKeySequence(sequence), self)
            shortcut.setContext(Qt.WidgetWithChildrenShortcut)
            shortcut.activated.connect(callback)

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------
    def set_file_list(self, files, current_index=0):
        self._loading = True
        try:
            self.file_combo.clear()
            for path in files:
                self.file_combo.addItem(os.path.basename(path), path)
            if files:
                self.file_combo.setCurrentIndex(
                    max(0, min(current_index, len(files) - 1)))
        finally:
            self._loading = False

    def load_document(self, blocks, saved_segments=None, label="", done=False):
        self.segmenter = ManualSegmenter(blocks)
        self.segmenter.load_units(saved_segments or [])
        self.document.setPlainText(self.segmenter.text)
        self._done = bool(done)
        self.segments = self.segmenter.to_segments()
        self.document.moveCursor(QTextCursor.Start)
        self._refresh()
        if label:
            self.status_label.setText(
                f"Loaded {label}. Place the cursor on a word to begin.")
        if self._done:
            self.status_label.setText(
                "Segmentation is locked. Choose Edit Segmentation to change it.")

    def clear_document(self):
        self.segmenter = None
        self.segments = []
        self._done = False
        self.document.clear()
        self.preview.clear()
        self.count_label.setText("Committed: 0   Marked: 0")
        self._update_controls()

    @property
    def is_done(self):
        return self._done

    # ------------------------------------------------------------------
    # Boundary actions
    # ------------------------------------------------------------------
    def _report_error(self, error):
        self.status_label.setText(str(error))

    def mark_start(self):
        if self._done or self.segmenter is None:
            return
        try:
            token = self.segmenter.set_start(
                self.document.textCursor().position())
        except ManualSegmentationError as error:
            self._report_error(error)
            return
        self.status_label.setText(
            f"Unit start: \u201c{token['text']}\u201d. Now set the unit end.")
        self._refresh()

    def mark_end(self):
        if self._done or self.segmenter is None:
            return
        try:
            unit = self.segmenter.set_end(
                self.document.textCursor().position())
        except ManualSegmentationError as error:
            self._report_error(error)
            return
        source = self.segmenter.unit_source(unit)
        self.status_label.setText(
            f"Unit marked: \u201c{source}\u201d. Press Split or mark another unit.")
        self._refresh()

    def split(self):
        if self._done or self.segmenter is None:
            return
        try:
            unit = self.segmenter.split()
        except ManualSegmentationError as error:
            self._report_error(error)
            return
        self.status_label.setText(
            f"Split: \u201c{self.segmenter.unit_source(unit)}\u201d")
        self._emit_segments()

    def split_all(self):
        if self._done or self.segmenter is None:
            return
        try:
            count = self.segmenter.split_all()
        except ManualSegmentationError as error:
            self._report_error(error)
            return
        self.status_label.setText(
            f"Split All created {count} unit(s), including the remaining gaps.")
        self._emit_segments()

    def clear_pending(self):
        if self._done or self.segmenter is None:
            return
        self.segmenter.clear_pending()
        self.status_label.setText("Pending boundaries cleared.")
        self._refresh()

    def undo(self):
        if self._done or self.segmenter is None:
            return
        try:
            self.segmenter.undo()
        except ManualSegmentationError as error:
            self._report_error(error)
            return
        self.status_label.setText("Undid the last segmentation action.")
        self._emit_segments()

    # ------------------------------------------------------------------
    # Completion
    # ------------------------------------------------------------------
    def finish_segmentation(self):
        if self._done or self.segmenter is None:
            return
        if self.segmenter.active_start is not None or self.segmenter.marked:
            QMessageBox.warning(
                self, "Pending Units",
                "Split or clear the marked units before finishing.")
            return
        if not self.segmenter.units:
            QMessageBox.warning(
                self, "No Units", "Define at least one translation unit first.")
            return

        if self.segmenter.has_unsegmented_text():
            reply = QMessageBox.question(
                self, "Unsegmented Text",
                "Some text is not part of a unit.\n\n"
                "Create units from the remaining gaps?",
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel)
            if reply == QMessageBox.Cancel:
                return
            if reply == QMessageBox.Yes:
                self.segmenter.fill_gaps()
                self._emit_segments()

        self._done = True
        self._refresh()
        self.status_label.setText(
            "Segmentation finished and locked. The translation table is ready.")
        self.finished.emit()

    def edit_segmentation(self):
        if not self._done:
            return
        reply = QMessageBox.warning(
            self, "Edit Segmentation",
            "Editing the segmentation after translation can change existing "
            "rows and may discard translations that no longer fit.\n\n"
            "Continue?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply != QMessageBox.Yes:
            return
        self._done = False
        self._refresh()
        self.status_label.setText(
            "Segmentation unlocked. Existing rows are preserved where possible.")
        self.editStarted.emit()

    def _emit_segments(self):
        self.segments = self.segmenter.to_segments()
        self.segmentsChanged.emit(self.segments)
        self._refresh()

    # ------------------------------------------------------------------
    # Context menu and keyboard
    # ------------------------------------------------------------------
    def eventFilter(self, obj, event):
        if obj is self.document and event.type() == QEvent.KeyPress:
            is_menu_key = event.key() == Qt.Key_Menu
            is_shift_f10 = (
                event.key() == Qt.Key_F10
                and bool(event.modifiers() & Qt.ShiftModifier))
            if is_menu_key or is_shift_f10:
                self._show_context_menu_at_cursor()
                return True
        return super().eventFilter(obj, event)

    def _show_context_menu_at(self, position):
        self.document.setTextCursor(
            self.document.cursorForPosition(position))
        self._show_context_menu(
            self.document.mapToGlobal(position))

    def _show_context_menu_at_cursor(self):
        rect = self.document.cursorRect()
        self._show_context_menu(
            self.document.mapToGlobal(rect.center()))

    def _show_context_menu(self, global_position):
        menu = QMenu(self)
        start_action = menu.addAction("Set Unit Start\tCtrl+[")
        end_action = menu.addAction("Set Unit End\tCtrl+]")
        menu.addSeparator()
        split_action = menu.addAction("Split\tCtrl+Enter")
        split_all_action = menu.addAction("Split All\tCtrl+Shift+Enter")
        menu.addSeparator()
        clear_action = menu.addAction("Clear Pending Boundaries\tEsc")
        undo_action = menu.addAction("Undo Last Segmentation\tCtrl+Z")

        has_pending = self.segmenter is not None and (
            self.segmenter.active_start is not None
            or bool(self.segmenter.marked))
        has_marked = self.segmenter is not None and bool(self.segmenter.marked)
        has_start = self.segmenter is not None and (
            self.segmenter.active_start is not None)

        start_action.setEnabled(not self._done)
        end_action.setEnabled(not self._done and has_start)
        split_action.setEnabled(not self._done and has_marked)
        split_all_action.setEnabled(not self._done and has_marked)
        clear_action.setEnabled(not self._done and has_pending)
        undo_action.setEnabled(
            not self._done and self.segmenter is not None
            and self.segmenter.can_undo)

        start_action.triggered.connect(self.mark_start)
        end_action.triggered.connect(self.mark_end)
        split_action.triggered.connect(self.split)
        split_all_action.triggered.connect(self.split_all)
        clear_action.triggered.connect(self.clear_pending)
        undo_action.triggered.connect(self.undo)
        menu.exec_(global_position)

    def _on_file_changed(self, index):
        if self._loading or index < 0:
            return
        self.fileChangeRequested.emit(index)

    # ------------------------------------------------------------------
    # Display
    # ------------------------------------------------------------------
    def _refresh(self):
        self._refresh_highlights()
        self._refresh_preview()
        self._update_controls()

    def _refresh_highlights(self):
        if self.segmenter is None:
            self.document.setExtraSelections([])
            return
        selections = []
        for unit in self.segmenter.units:
            selections.append(self._selection(
                unit.start, unit.end, _COMMITTED_COLOR))
        for unit in self.segmenter.marked:
            selections.append(self._selection(
                unit.start, unit.end, _MARKED_COLOR))
        if self.segmenter.active_start is not None:
            start = self.segmenter.active_start
            selections.append(self._selection(
                start["start"], start["end"], _START_COLOR))
        self.document.setExtraSelections(selections)

    def _selection(self, start, end, color):
        cursor = QTextCursor(self.document.document())
        cursor.setPosition(start)
        cursor.setPosition(end, QTextCursor.KeepAnchor)
        selection = QTextEdit.ExtraSelection()
        selection.cursor = cursor
        selection.format.setBackground(color)
        selection.format.setForeground(_TEXT_COLOR)
        return selection

    def _refresh_preview(self):
        self.preview.clear()
        if self.segmenter is None:
            self.count_label.setText("Committed: 0   Marked: 0")
            return
        for index, unit in enumerate(self.segmenter.units):
            text = self.segmenter.unit_source(unit).replace("\n", " ")
            self.preview.addItem(f"{index + 1}. {text[:120]}")
        for unit in self.segmenter.marked:
            text = self.segmenter.unit_source(unit).replace("\n", " ")
            self.preview.addItem(f"[marked] {text[:120]}")
        self.count_label.setText(
            f"Committed: {len(self.segmenter.units)}   "
            f"Marked: {len(self.segmenter.marked)}")

    def _update_controls(self):
        enabled = not self._done and self.segmenter is not None
        self.start_btn.setEnabled(enabled)
        self.end_btn.setEnabled(
            enabled and self.segmenter.active_start is not None)
        self.split_btn.setEnabled(
            enabled and bool(self.segmenter.marked))
        self.split_all_btn.setEnabled(
            enabled and bool(self.segmenter.marked))
        self.clear_btn.setEnabled(
            enabled and (
                self.segmenter.active_start is not None
                or bool(self.segmenter.marked)))
        self.undo_btn.setEnabled(enabled and self.segmenter.can_undo)
        self.finish_btn.setVisible(not self._done)
        self.edit_btn.setVisible(self._done)
        self.document.setReadOnly(True)
        self.stage_label.setText(
            "Segmentation locked" if self._done
            else "Naming \u2014 define translation units")
