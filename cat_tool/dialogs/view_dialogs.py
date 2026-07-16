from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
                             QLabel, QTableWidget, QTableWidgetItem,
                             QHeaderView, QListWidget, QListWidgetItem)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor

from cat_tool.formats.tag_utils import PH_L, PH_R


class ShortcutsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Keyboard Shortcuts")
        self.setMinimumSize(500, 400)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        table = QTableWidget()
        table.setColumnCount(2)
        table.setHorizontalHeaderLabels(["Shortcut", "Action"])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectRows)

        shortcuts = [
            ("Ctrl+N", "New Project"),
            ("Ctrl+Shift+O", "Open Project"),
            ("Ctrl+Shift+S", "Save Project"),
            ("Ctrl+O", "Open File"),
            ("Ctrl+S", "Save File"),
            ("Ctrl+R", "Render Translated File"),
            ("Ctrl+Down", "Next Segment"),
            ("Ctrl+Up", "Previous Segment"),
            ("Ctrl+U", "Next Untranslated Segment"),
            ("Ctrl+Enter", "Confirm and Next"),
            ("Ctrl+F", "Toggle Fuzzy / Needs Review"),
            ("Ctrl+G", "Add Glossary Term"),
            ("Ctrl+Shift+G", "View/Manage Glossary"),
            ("Ctrl+M", "Import PO into TM"),
            ("Ctrl+Shift+T", "Segmentation Rules"),
            ("Ctrl+Home", "Go to First Segment"),
            ("Ctrl+End", "Go to Last Segment"),
            ("Ctrl+Shift+Q", "Quality Assurance Check"),
            ("F1 / Ctrl+Shift+H", "Show Keyboard Shortcuts"),
        ]

        table.setRowCount(len(shortcuts))
        for i, (shortcut, action) in enumerate(shortcuts):
            table.setItem(i, 0, QTableWidgetItem(shortcut))
            table.setItem(i, 1, QTableWidgetItem(action))

        layout.addWidget(table)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)


class QADialog(QDialog):
    def __init__(self, issues, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Quality Assurance Results")
        self.resize(900, 500)
        self._issues = issues
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        summary = QLabel(
            f"Found {len(self._issues)} issue(s)"
            if self._issues else "No issues found."
        )
        summary.setStyleSheet("font-weight: bold; font-size: 14px; padding: 4px;")
        layout.addWidget(summary)

        self.qa_table = QTableWidget()
        self.qa_table.setColumnCount(6)
        self.qa_table.setHorizontalHeaderLabels(["", "Severity", "Check", "#", "Source", "Target", "Description"])
        self.qa_table.setColumnHidden(0, True)
        self.qa_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.qa_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self.qa_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.qa_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.qa_table.setSelectionMode(QTableWidget.SingleSelection)
        self.qa_table.cellDoubleClicked.connect(self._on_double_click)
        self.qa_table.setRowCount(len(self._issues))

        for i, issue in enumerate(self._issues):
            sev_item = QTableWidgetItem(issue.severity.upper())
            if issue.severity == "error":
                sev_item.setForeground(QColor("#ff4444"))
            else:
                sev_item.setForeground(QColor("#ffaa00"))

            idx_item = QTableWidgetItem(str(issue.segment_index))
            idx_item.setTextAlignment(Qt.AlignCenter)

            self.qa_table.setItem(i, 1, sev_item)
            self.qa_table.setItem(i, 2, QTableWidgetItem(issue.check_name))
            self.qa_table.setItem(i, 3, idx_item)
            self.qa_table.setItem(i, 4, QTableWidgetItem(issue.source[:120] if issue.source else ""))
            self.qa_table.setItem(i, 5, QTableWidgetItem(issue.target[:120] if issue.target else ""))
            self.qa_table.setItem(i, 6, QTableWidgetItem(issue.description))

            hidden_item = QTableWidgetItem(str(issue.segment_index))
            self.qa_table.setItem(i, 0, hidden_item)

        layout.addWidget(self.qa_table)

        btn_layout = QHBoxLayout()
        go_btn = QPushButton("Go to Selected Segment")
        go_btn.setStyleSheet("background-color: #0078d4;")
        go_btn.clicked.connect(self._go_to_segment)
        btn_layout.addWidget(go_btn)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)

        layout.addLayout(btn_layout)

    def _go_to_segment(self):
        row = self.qa_table.currentRow()
        if row < 0:
            return
        seg_idx = int(self.qa_table.item(row, 0).text())
        main_win = self.parent()
        if main_win and hasattr(main_win, "navigate_to_segment"):
            main_win.navigate_to_segment(seg_idx)
        self.accept()

    def _on_double_click(self, row, col):
        self._go_to_segment()


class TagViewDialog(QDialog):
    def __init__(self, segment, column, parent=None):
        super().__init__(parent)
        self.segment = segment
        self.column = column
        self.setWindowTitle("View Tags")
        self.setAccessibleName("Tag Viewer")
        self.setAccessibleDescription(
            "Lists all tags in this segment. Select a tag and press Insert to add its placeholder to the translation." if column == 1
            else "Lists all tags in this segment for reference.")
        self.setMinimumWidth(500)
        self.setMinimumHeight(350)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        tags = self.segment.get("all_tags", [])
        label = QLabel(f"Tags in this segment ({len(tags)}):")
        label.setAccessibleName("Tags heading")
        layout.addWidget(label)

        self.tag_list = QListWidget()
        self.tag_list.setAccessibleName("Tag list")
        self.tag_list.setAccessibleDescription(
            "Select a tag from the list, then press the Insert button to add it to your translation." if self.column == 1
            else "List of tags found in the source segment.")
        if not tags:
            item = QListWidgetItem("No tags in this segment")
            self.tag_list.addItem(item)
            self.tag_list.item(0).setFlags(Qt.NoItemFlags)
        else:
            for i, tag in enumerate(tags):
                ph = f"{PH_L}{i}{PH_R}"
                display = f"{ph}  =  {tag}"
                item = QListWidgetItem(display)
                item.setData(Qt.UserRole, i)
                item.setToolTip(f"Placeholder: {ph}" if self.column == 0 else f"Click to select, then press Insert to add {ph} to the target")
                self.tag_list.addItem(item)

        layout.addWidget(self.tag_list)

        btn_layout = QHBoxLayout()
        if self.column == 1 and tags:
            self.insert_btn = QPushButton("Insert")
            self.insert_btn.setAccessibleName("Insert tag")
            self.insert_btn.setAccessibleDescription("Inserts the selected tag placeholder into your translation.")
            self.insert_btn.setToolTip("Insert selected tag at cursor in the target cell")
            self.insert_btn.clicked.connect(self._insert_selected_tag)
            self.insert_btn.setEnabled(False)
            self.tag_list.itemClicked.connect(lambda _: self.insert_btn.setEnabled(True))
            self.tag_list.itemDoubleClicked.connect(self._insert_selected_tag)
            btn_layout.addWidget(self.insert_btn)

        close_btn = QPushButton("Close")
        close_btn.setAccessibleName("Close tag viewer")
        close_btn.setAccessibleDescription("Closes this tag viewer dialog.")
        close_btn.clicked.connect(self.accept)
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

    def _insert_selected_tag(self):
        item = self.tag_list.currentItem()
        if item is None:
            return
        tag_idx = item.data(Qt.UserRole)
        if tag_idx is None:
            return
        parent = self.parent()
        if not parent or not hasattr(parent, 'table') or parent.current_segment_index < 0:
            return
        cell_item = parent.table.item(parent.current_segment_index, 1)
        if cell_item is None:
            return
        ph = f"{PH_L}{tag_idx}{PH_R}"
        old = cell_item.text()
        new = old + ph
        cell_item.setText(new)
