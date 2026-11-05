from PyQt6.QtWidgets import QHeaderView, QComboBox, QHBoxLayout, QLabel, QLineEdit, QPushButton, QTableWidget, QVBoxLayout

from database import DatabaseError
from pages.base_page import BasePage, fill_table
from styles import THEMES


HEADER_QSS = "QHeaderView::section { background-color: #D7F0FB; color: #0F172A; font-weight: 600; font-size: 12px; padding: 10px 12px; border: none; border-right: 1px solid #94A3B8; border-bottom: 2px solid #0EA5E9; }"


def style_table(table):
    """Make header labels readable: fixed default width, wrapped text, no clipping."""
    header = table.horizontalHeader()
    header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
    header.setDefaultSectionSize(150)
    header.setMinimumSectionSize(120)
    header.setStretchLastSection(False)
    header.setHighlightSections(False)
    header.setMinimumHeight(44)
    table.setStyleSheet(HEADER_QSS)



class MentorInterviewPage(BasePage):
    UI_FILE = "mentor_interview_page.ui"
    THEME = THEMES["mentor_interview"]

    def build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 20, 16, 20)
        root.setSpacing(16)
        root.addWidget(self.make_header("Mentor Interview", "Mentor conversations and sessions"))

        card = self.make_card()
        body = QVBoxLayout(card)
        body.setContentsMargins(20, 20, 20, 20)
        body.setSpacing(14)

        search_row = QHBoxLayout()
        self.inputSearch = QLineEdit()
        self.inputSearch.setPlaceholderText("Search conversations...")
        self.btnSearch = QPushButton("Search")
        search_row.addWidget(self.inputSearch, 1)
        search_row.addWidget(self.btnSearch)
        body.addLayout(search_row)

        filter_row = QHBoxLayout()
        self.labelFilter = QLabel("Tab")
        self.comboTabs = QComboBox()
        self.comboTabs.addItem("All Tabs")
        self.btnAllConversations = QPushButton("All Conversations")
        filter_row.addWidget(self.labelFilter)
        filter_row.addWidget(self.comboTabs, 1)
        filter_row.addWidget(self.btnAllConversations)
        body.addLayout(filter_row)

        self.tableConversations = QTableWidget(0, 0)
        self.tableConversations.setAlternatingRowColors(True)
        self.tableConversations.verticalHeader().setVisible(False)
        body.addWidget(self.tableConversations, 1)
        self.labelMuted = QLabel("")
        self.labelMuted.setObjectName("labelMuted")
        body.addWidget(self.labelMuted)
        root.addWidget(card, 1)

        self.btnRefresh = QPushButton("Refresh")
        self.btnReturn = QPushButton("Return to Preferences Screen")
        self.btnExit = QPushButton("Exit")
        self.btnExit.setObjectName("btnExit")
        root.addLayout(self.make_footer(self.btnRefresh, self.btnReturn, self.btnExit))

    def connect_signals(self):
        self.add_detail_panel(self.tableConversations)
        style_table(self.tableConversations)
        self.route(self.btnReturn, "return_preferences")
        self.btnRefresh.clicked.connect(self.on_refresh)
        self.route(self.btnExit, "exit")
        self.current_category = None
        self.load_tabs()
        self.btnSearch.clicked.connect(self.refresh)
        self.inputSearch.returnPressed.connect(self.refresh)
        self.btnAllConversations.clicked.connect(self.show_all)
        self.comboTabs.currentIndexChanged.connect(self.on_tab_changed)

    def load_tabs(self):
        try:
            categories = self.store.mentor_categories()
        except DatabaseError as error:
            categories = []
            self.show_message(str(error))
        self.comboTabs.blockSignals(True)
        self.comboTabs.clear()
        self.comboTabs.addItem("All Tabs")
        self.comboTabs.addItems(categories)
        self.comboTabs.blockSignals(False)

    def on_tab_changed(self, index):
        self.current_category = self.comboTabs.itemText(index) if index > 0 else None
        self.refresh()

    def show_all(self):
        self.comboTabs.blockSignals(True)
        self.comboTabs.setCurrentIndex(0)
        self.comboTabs.blockSignals(False)
        self.current_category = None
        self.refresh()

    def on_refresh(self, *_):
        self.load_tabs()  # recommendation categories may have changed in the database
        self.current_category = None
        text = self.refresh()
        self.show_message(f"Data reloaded from the database. {text}" if text else "Data reloaded")

    def refresh(self, *_):
        try:
            headers, rows = self.store.mentor(self.current_category, self.inputSearch.text())
        except DatabaseError as error:
            fill_table(self.tableConversations, [], [])
            self.show_message(str(error))
            return
        fill_table(self.tableConversations, headers, rows)
        message = f"{len(rows)} conversation(s) shown"
        self.labelMuted.setText(message)
        self.show_message(message)
        return message
