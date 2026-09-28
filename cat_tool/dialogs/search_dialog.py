"""
Search Dialog for mcat.

Provides a unified search interface across:
- In-memory segments (currently loaded file)
- TM Sources (translation memory source segments)
- TM Targets (translation memory target segments)
"""
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QComboBox,
    QCheckBox, QLabel, QSplitter, QWidget, QTabWidget,
    QSpinBox, QDoubleSpinBox, QGroupBox, QFormLayout,
    QDialogButtonBox, QMenu, QAction
)
from PyQt5.QtCore import Qt, pyqtSignal, QThread, QTimer
from PyQt5.QtGui import QColor, QFont, QKeySequence

from cat_tool.search_fetcher import SearchFetcher


class SearchWorker(QThread):
    """Background worker for search operations."""
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)
    
    def __init__(self, fetcher: SearchFetcher, query: str, segments: list, params: dict):
        super().__init__()
        self.fetcher = fetcher
        self.query = query
        self.segments = segments
        self.params = params
    
    def run(self):
        try:
            results = self.fetcher.search_all(
                self.query,
                in_memory_segments=self.segments,
                **self.params
            )
            self.finished.emit(results)
        except Exception as e:
            self.error.emit(str(e))


class SearchDialog(QDialog):
    """Main search dialog with results table and filters."""
    
    # Signal emitted when user wants to navigate to a segment
    navigate_to_segment = pyqtSignal(int)  # segment index in current file
    
    def __init__(self, parent=None, fetcher: SearchFetcher = None, segments: list = None,
                 tm_sl: str = "", tm_tl: str = ""):
        super().__init__(parent)
        self.setWindowTitle("Search")
        self.resize(900, 600)
        self.setMinimumSize(700, 450)
        
        self.fetcher = fetcher or SearchFetcher()
        self.segments = segments or []
        self.tm_sl = tm_sl
        self.tm_tl = tm_tl
        self._search_worker = None
        self._debounce_timer = QTimer()
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(300)
        self._debounce_timer.timeout.connect(self._perform_search)
        self._current_results = {"all": [], "in_memory": [], "tm_sources": [], "tm_targets": []}
        
        self.init_ui()
        self._apply_stylesheet()
    
    def _apply_stylesheet(self):
        self.setStyleSheet("""
            QDialog {
                background-color: #1e1e24;
                color: #ffffff;
            }
            QLineEdit {
                background-color: #1a1a1e;
                border: 1px solid #2c2c35;
                border-radius: 4px;
                padding: 8px;
                color: white;
                font-size: 14px;
            }
            QLineEdit:focus {
                border-color: #0078d4;
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
            QTableWidget {
                background-color: #1a1a1e;
                gridline-color: #2c2c35;
                border: 1px solid #2c2c35;
                border-radius: 4px;
            }
            QTableWidget::item {
                padding: 6px;
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
            QComboBox {
                background-color: #1a1a1e;
                border: 1px solid #2c2c35;
                border-radius: 4px;
                padding: 6px;
                color: white;
            }
            QComboBox::drop-down {
                border: none;
            }
            QCheckBox {
                spacing: 6px;
                color: #e0e0e8;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
            }
            QSpinBox, QDoubleSpinBox {
                background-color: #1a1a1e;
                border: 1px solid #2c2c35;
                border-radius: 4px;
                padding: 4px;
                color: white;
            }
            QGroupBox {
                border: 1px solid #2c2c35;
                border-radius: 4px;
                margin-top: 10px;
                padding-top: 10px;
                color: #e0e0e8;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
            QTabWidget::pane {
                border: 1px solid #2c2c35;
                border-radius: 4px;
                background-color: #1a1a1e;
            }
            QTabBar::tab {
                background-color: #25252b;
                color: #b0b0b8;
                padding: 8px 16px;
                border: 1px solid #2c2c35;
                border-bottom: none;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            QTabBar::tab:selected {
                background-color: #1a1a1e;
                color: #ffffff;
                border-bottom: 1px solid #1a1a1e;
            }
            QLabel {
                color: #e0e0e8;
            }
        """)
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)
        
        # ===== SEARCH BAR =====
        search_layout = QHBoxLayout()
        search_layout.setSpacing(8)
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search in memory, TM sources, TM targets... (Enter to search)")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.returnPressed.connect(self._on_search_entered)
        self.search_input.textChanged.connect(self._on_search_text_changed)
        search_layout.addWidget(self.search_input, 1)
        
        self.search_btn = QPushButton("Search")
        self.search_btn.clicked.connect(self._perform_search)
        search_layout.addWidget(self.search_btn)
        
        self.clear_btn = QPushButton("Clear")
        self.clear_btn.clicked.connect(self._clear_search)
        search_layout.addWidget(self.clear_btn)
        
        layout.addLayout(search_layout)
        
        # ===== FILTER BAR =====
        filter_widget = QWidget()
        filter_layout = QHBoxLayout(filter_widget)
        filter_layout.setContentsMargins(0, 0, 0, 0)
        filter_layout.setSpacing(12)
        
        # Search scope checkboxes
        scope_group = QGroupBox("Search In")
        scope_layout = QHBoxLayout(scope_group)
        scope_layout.setSpacing(16)
        
        self.cb_in_memory = QCheckBox("In-Memory")
        self.cb_in_memory.setChecked(True)
        self.cb_in_memory.setToolTip("Search in currently loaded file segments")
        scope_layout.addWidget(self.cb_in_memory)
        
        self.cb_tm_sources = QCheckBox("TM Sources")
        self.cb_tm_sources.setChecked(True)
        self.cb_tm_sources.setToolTip("Search in Translation Memory source segments")
        scope_layout.addWidget(self.cb_tm_sources)
        
        self.cb_tm_targets = QCheckBox("TM Targets")
        self.cb_tm_targets.setChecked(True)
        self.cb_tm_targets.setToolTip("Search in Translation Memory target (translated) segments")
        scope_layout.addWidget(self.cb_tm_targets)
        
        self.cb_glossary = QCheckBox("Glossary")
        self.cb_glossary.setChecked(True)
        self.cb_glossary.setToolTip("Search in glossary terminology database")
        scope_layout.addWidget(self.cb_glossary)
        
        filter_layout.addWidget(scope_group)
        
        # In-memory field selector
        field_group = QGroupBox("In-Memory Fields")
        field_layout = QHBoxLayout(field_group)
        
        self.field_combo = QComboBox()
        self.field_combo.addItems(["Both", "Source Only", "Target Only"])
        self.field_combo.setCurrentIndex(0)
        self.field_combo.setToolTip("Which fields to search in the current file")
        field_layout.addWidget(self.field_combo)
        
        filter_layout.addWidget(field_group)
        
        # Glossary field selector
        glossary_field_group = QGroupBox("Glossary Fields")
        glossary_field_layout = QHBoxLayout(glossary_field_group)
        
        self.glossary_field_combo = QComboBox()
        self.glossary_field_combo.addItems(["Source + Target", "Source Only", "Target Only", "Description", "All Fields"])
        self.glossary_field_combo.setCurrentIndex(0)
        self.glossary_field_combo.setToolTip("Which fields to search in the glossary")
        glossary_field_layout.addWidget(self.glossary_field_combo)
        
        filter_layout.addWidget(glossary_field_group)
        
        # Match type
        match_group = QGroupBox("Match Type")
        match_layout = QHBoxLayout(match_group)
        
        self.cb_fuzzy = QCheckBox("Fuzzy")
        self.cb_fuzzy.setChecked(True)
        self.cb_fuzzy.setToolTip("Use fuzzy matching (rapidfuzz)")
        match_layout.addWidget(self.cb_fuzzy)
        
        self.cb_semantic = QCheckBox("Semantic")
        self.cb_semantic.setChecked(False)
        self.cb_semantic.setToolTip("Use semantic vector search (requires embedding model)")
        match_layout.addWidget(self.cb_semantic)
        
        filter_layout.addWidget(match_group)
        
        # Score threshold
        score_group = QGroupBox("Min Score")
        score_layout = QHBoxLayout(score_group)
        
        self.score_spin = QDoubleSpinBox()
        self.score_spin.setRange(0, 100)
        self.score_spin.setValue(30)
        self.score_spin.setSingleStep(5)
        self.score_spin.setSuffix("%")
        score_layout.addWidget(self.score_spin)
        
        filter_layout.addWidget(score_group)
        
        # Limit
        limit_group = QGroupBox("Max Results")
        limit_layout = QHBoxLayout(limit_group)
        
        self.limit_spin = QSpinBox()
        self.limit_spin.setRange(10, 500)
        self.limit_spin.setValue(50)
        self.limit_spin.setSingleStep(10)
        limit_layout.addWidget(self.limit_spin)
        
        filter_layout.addWidget(limit_group)
        
        filter_layout.addStretch()
        layout.addWidget(filter_widget)
        
        # ===== RESULTS TABS =====
        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(False)
        
        # All results tab
        self.all_table = self._create_results_table()
        self.tabs.addTab(self.all_table, "All Results")
        
        # In-memory tab
        self.memory_table = self._create_results_table()
        self.tabs.addTab(self.memory_table, "In-Memory")
        
        # TM Sources tab
        self.tm_sources_table = self._create_results_table()
        self.tabs.addTab(self.tm_sources_table, "TM Sources")
        
        # TM Targets tab
        self.tm_targets_table = self._create_results_table()
        self.tabs.addTab(self.tm_targets_table, "TM Targets")
        
        # Glossary tab
        self.glossary_table = self._create_results_table()
        self.tabs.addTab(self.glossary_table, "Glossary")
        
        layout.addWidget(self.tabs, 1)
        
        # ===== STATUS BAR =====
        status_layout = QHBoxLayout()
        
        self.status_label = QLabel("Ready. Enter a search query.")
        self.status_label.setStyleSheet("color: #b0b0b8; font-size: 12px;")
        status_layout.addWidget(self.status_label)
        
        status_layout.addStretch()
        
        self.result_count_label = QLabel("0 results")
        self.result_count_label.setStyleSheet("color: #b0b0b8; font-size: 12px; font-weight: bold;")
        status_layout.addWidget(self.result_count_label)
        
        layout.addLayout(status_layout)
        
        # ===== BUTTON BAR =====
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        self.goto_btn = QPushButton("Go to Segment")
        self.goto_btn.setEnabled(False)
        self.goto_btn.clicked.connect(self._goto_selected_segment)
        btn_layout.addWidget(self.goto_btn)
        
        self.apply_tm_btn = QPushButton("Apply TM Match")
        self.apply_tm_btn.setEnabled(False)
        self.apply_tm_btn.clicked.connect(self._apply_tm_match)
        btn_layout.addWidget(self.apply_tm_btn)
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)
        
        layout.addLayout(btn_layout)
        
        # Connect signals
        self.tabs.currentChanged.connect(self._on_tab_changed)
        for table in [self.all_table, self.memory_table, self.tm_sources_table, self.tm_targets_table, self.glossary_table]:
            table.itemSelectionChanged.connect(self._on_selection_changed)
            table.itemDoubleClicked.connect(self._on_double_click)
            table.setContextMenuPolicy(Qt.CustomContextMenu)
            table.customContextMenuRequested.connect(self._show_context_menu)
    
    def _create_results_table(self) -> QTableWidget:
        """Create a configured results table."""
        table = QTableWidget()
        table.setColumnCount(7)
        table.setHorizontalHeaderLabels([
            "Score", "Source", "Target", "Context", "Match Type", "Lang", "Index"
        ])
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeToContents)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setSelectionMode(QTableWidget.SingleSelection)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setAlternatingRowColors(True)
        table.setSortingEnabled(True)
        table.verticalHeader().setVisible(False)
        return table
    
    def _on_search_text_changed(self, text: str):
        """Debounced search on text change."""
        if len(text.strip()) >= 2:
            self._debounce_timer.start()
        else:
            self._debounce_timer.stop()
            if not text.strip():
                self._clear_results()
    
    def _on_search_entered(self):
        """Immediate search on Enter key."""
        self._debounce_timer.stop()
        self._perform_search()
    
    def _perform_search(self):
        """Execute the search with current parameters."""
        query = self.search_input.text().strip()
        if not query:
            self._clear_results()
            return
        
        if len(query) < 2:
            self.status_label.setText("Query too short (min 2 characters)")
            return
        
        # Disable search button during search
        self.search_btn.setEnabled(False)
        self.search_btn.setText("Searching...")
        self.status_label.setText(f"Searching for: {query}...")
        
        # Build search parameters
        params = {
            "min_score": self.score_spin.value(),
            "limit": self.limit_spin.value(),
            "source_lang": self.tm_sl or None,
            "target_lang": self.tm_tl or None,
            "search_in_memory": self.cb_in_memory.isChecked(),
            "search_tm_sources": self.cb_tm_sources.isChecked(),
            "search_tm_targets": self.cb_tm_targets.isChecked(),
            "search_glossary": self.cb_glossary.isChecked(),
            "in_memory_search_in": ["both", "source", "target"][self.field_combo.currentIndex()],
            "glossary_search_in": ["both", "source", "target", "description", "all"][self.glossary_field_combo.currentIndex()],
            "use_fuzzy": self.cb_fuzzy.isChecked(),
            "use_semantic": self.cb_semantic.isChecked(),
        }
        
        # Run search in background thread
        self._search_worker = SearchWorker(self.fetcher, query, self.segments, params)
        self._search_worker.finished.connect(self._on_search_finished)
        self._search_worker.error.connect(self._on_search_error)
        self._search_worker.start()
    
    def _on_search_finished(self, results: dict):
        """Handle search completion."""
        self._current_results = results
        self.search_btn.setEnabled(True)
        self.search_btn.setText("Search")
        
        total = len(results.get("all", []))
        self.result_count_label.setText(f"{total} result{'s' if total != 1 else ''}")
        self.status_label.setText(f"Found {total} matches")
        
        # Populate all tables
        self._populate_table(self.all_table, results.get("all", []))
        self._populate_table(self.memory_table, results.get("in_memory", []))
        self._populate_table(self.tm_sources_table, results.get("tm_sources", []))
        self._populate_table(self.tm_targets_table, results.get("tm_targets", []))
        self._populate_table(self.glossary_table, results.get("glossary", []))
        
        # Update tab labels with counts
        self.tabs.setTabText(0, f"All Results ({len(results.get('all', []))})")
        self.tabs.setTabText(1, f"In-Memory ({len(results.get('in_memory', []))})")
        self.tabs.setTabText(2, f"TM Sources ({len(results.get('tm_sources', []))})")
        self.tabs.setTabText(3, f"TM Targets ({len(results.get('tm_targets', []))})")
        self.tabs.setTabText(4, f"Glossary ({len(results.get('glossary', []))})")
    
    def _on_search_error(self, error: str):
        """Handle search error."""
        self.search_btn.setEnabled(True)
        self.search_btn.setText("Search")
        self.status_label.setText(f"Search error: {error}")
        from PyQt5.QtWidgets import QMessageBox
        QMessageBox.critical(self, "Search Error", error)
    
    def _populate_table(self, table: QTableWidget, matches: list):
        """Populate a results table with matches."""
        table.setSortingEnabled(False)
        table.setRowCount(len(matches))
        
        for row, match in enumerate(matches):
            # Score
            score_item = QTableWidgetItem(f"{match.get('score', 0)}%")
            score_item.setTextAlignment(Qt.AlignCenter)
            score = match.get('score', 0)
            if score >= 90:
                score_item.setForeground(QColor("#28a745"))
            elif score >= 70:
                score_item.setForeground(QColor("#ff9800"))
            else:
                score_item.setForeground(QColor("#ffaa00"))
            table.setItem(row, 0, score_item)
            
            # Source
            source = match.get('source', '')
            src_item = QTableWidgetItem(source[:500] + ("..." if len(source) > 500 else ""))
            src_item.setToolTip(source)
            table.setItem(row, 1, src_item)
            
            # Target
            target = match.get('target', '')
            tgt_item = QTableWidgetItem(target[:500] + ("..." if len(target) > 500 else ""))
            tgt_item.setToolTip(target)
            table.setItem(row, 2, tgt_item)
            
            # Context (where the match was found)
            context = match.get('context', match.get('search_source', ''))
            ctx_item = QTableWidgetItem(context.replace('_', ' ').title())
            ctx_item.setTextAlignment(Qt.AlignCenter)
            table.setItem(row, 3, ctx_item)
            
            # Match type
            match_type = match.get('match_type', 'fuzzy')
            type_item = QTableWidgetItem(match_type.title())
            type_item.setTextAlignment(Qt.AlignCenter)
            table.setItem(row, 4, type_item)
            
            # Languages
            sl = match.get('source_lang', '')
            tl = match.get('target_lang', '')
            lang_text = f"{sl} → {tl}" if sl and tl else (sl or tl or "—")
            lang_item = QTableWidgetItem(lang_text)
            lang_item.setTextAlignment(Qt.AlignCenter)
            table.setItem(row, 5, lang_item)
            
            # Index (for in-memory results)
            index = match.get('index', match.get('rowid', ''))
            idx_item = QTableWidgetItem(str(index) if index != '' else "—")
            idx_item.setTextAlignment(Qt.AlignCenter)
            table.setItem(row, 6, idx_item)
            
            # Store full match data in first column for retrieval
            score_item.setData(Qt.UserRole, match)
        
        table.setSortingEnabled(True)
        table.resizeColumnsToContents()
        # Ensure source/target columns get enough space
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
    
    def _clear_results(self):
        """Clear all results tables."""
        for table in [self.all_table, self.memory_table, self.tm_sources_table, self.tm_targets_table, self.glossary_table]:
            table.setRowCount(0)
        self._current_results = {"all": [], "in_memory": [], "tm_sources": [], "tm_targets": [], "glossary": []}
        self.result_count_label.setText("0 results")
        self.status_label.setText("Ready. Enter a search query.")
        self.goto_btn.setEnabled(False)
        self.apply_tm_btn.setEnabled(False)
        
        # Reset tab labels
        self.tabs.setTabText(0, "All Results")
        self.tabs.setTabText(1, "In-Memory")
        self.tabs.setTabText(2, "TM Sources")
        self.tabs.setTabText(3, "TM Targets")
        self.tabs.setTabText(4, "Glossary")
    
    def _clear_search(self):
        """Clear search input and results."""
        self.search_input.clear()
        self._clear_results()
    
    def _on_tab_changed(self, index: int):
        """Handle tab change - update button states."""
        self._on_selection_changed()
    
    def _on_selection_changed(self):
        """Update button states based on selection."""
        current_table = self.tabs.currentWidget()
        has_selection = current_table.currentRow() >= 0
        
        # "Go to Segment" only works for in-memory results
        current_tab = self.tabs.currentIndex()
        is_memory_tab = current_tab in (0, 1)  # All or In-Memory
        
        self.goto_btn.setEnabled(has_selection and is_memory_tab)
        
        # "Apply TM Match" works for TM results with a target
        has_target = False
        if has_selection:
            item = current_table.item(current_table.currentRow(), 0)
            if item:
                match_data = item.data(Qt.UserRole)
                if match_data and match_data.get('target'):
                    has_target = True
        
        self.apply_tm_btn.setEnabled(has_selection and has_target)
    
    def _on_double_click(self, item: QTableWidgetItem):
        """Handle double-click on result."""
        row = item.row()
        table = self.tabs.currentWidget()
        match_item = table.item(row, 0)
        if not match_item:
            return
        
        match_data = match_item.data(Qt.UserRole)
        if not match_data:
            return
        
        current_tab = self.tabs.currentIndex()
        
        # For in-memory results, navigate to segment
        if current_tab in (0, 1) and 'index' in match_data:
            self.navigate_to_segment.emit(match_data['index'])
            self.accept()
        # For TM results, apply the match
        elif match_data.get('target'):
            self._apply_tm_match()
    
    def _goto_selected_segment(self):
        """Navigate to selected in-memory segment."""
        current_table = self.tabs.currentWidget()
        row = current_table.currentRow()
        if row < 0:
            return
        
        item = current_table.item(row, 0)
        if not item:
            return
        
        match_data = item.data(Qt.UserRole)
        if match_data and 'index' in match_data:
            self.navigate_to_segment.emit(match_data['index'])
            self.accept()
    
    def _apply_tm_match(self):
        """Apply selected TM match to current segment."""
        current_table = self.tabs.currentWidget()
        row = current_table.currentRow()
        if row < 0:
            return
        
        item = current_table.item(row, 0)
        if not item:
            return
        
        match_data = item.data(Qt.UserRole)
        if not match_data or not match_data.get('target'):
            return
        
        # Emit signal with the target text for parent to apply
        self.tm_match_selected = getattr(self, 'tm_match_selected', None)
        if self.tm_match_selected:
            self.tm_match_selected.emit(match_data['target'])
        
        self.status_label.setText(f"Applied TM match: {match_data['target'][:50]}...")
    
    def _show_context_menu(self, pos):
        """Show context menu for results table."""
        table = self.tabs.currentWidget()
        item = table.itemAt(pos)
        if not item:
            return
        
        row = item.row()
        match_item = table.item(row, 0)
        if not match_item:
            return
        
        match_data = match_item.data(Qt.UserRole)
        if not match_data:
            return
        
        menu = QMenu(self)
        
        # Copy actions
        copy_source = menu.addAction("Copy Source")
        copy_source.triggered.connect(lambda: self._copy_to_clipboard(match_data.get('source', '')))
        
        copy_target = menu.addAction("Copy Target")
        copy_target.triggered.connect(lambda: self._copy_to_clipboard(match_data.get('target', '')))
        copy_target.setEnabled(bool(match_data.get('target')))
        
        copy_both = menu.addAction("Copy Both (Tab-separated)")
        copy_both.triggered.connect(lambda: self._copy_to_clipboard(
            f"{match_data.get('source', '')}\t{match_data.get('target', '')}"
        ))
        copy_both.setEnabled(bool(match_data.get('target')))
        
        menu.addSeparator()
        
        # Navigation actions
        if 'index' in match_data:
            goto_action = menu.addAction("Go to Segment")
            goto_action.triggered.connect(lambda: self.navigate_to_segment.emit(match_data['index']))
            goto_action.setEnabled(self.tabs.currentIndex() in (0, 1))
        
        if match_data.get('target'):
            apply_action = menu.addAction("Apply Target to Current Segment")
            apply_action.triggered.connect(self._apply_tm_match)
        
        menu.exec_(table.viewport().mapToGlobal(pos))
    
    def _copy_to_clipboard(self, text: str):
        """Copy text to clipboard."""
        from PyQt5.QtWidgets import QApplication
        QApplication.clipboard().setText(text)
        self.status_label.setText("Copied to clipboard")
    
    def update_segments(self, segments: list):
        """Update the in-memory segments for search."""
        self.segments = segments
    
    def update_tm_langs(self, source_lang: str, target_lang: str):
        """Update TM language filters."""
        self.tm_sl = source_lang
        self.tm_tl = target_lang
    
    def closeEvent(self, event):
        """Clean up on close."""
        if self._search_worker and self._search_worker.isRunning():
            self._search_worker.terminate()
            self._search_worker.wait(1000)
        super().closeEvent(event)


# Convenience function to show search dialog
def show_search_dialog(parent, fetcher: SearchFetcher, segments: list, tm_sl: str, tm_tl: str) -> SearchDialog:
    """Create and show a search dialog."""
    dialog = SearchDialog(parent, fetcher, segments, tm_sl, tm_tl)
    return dialog