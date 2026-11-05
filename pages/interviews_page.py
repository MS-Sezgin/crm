from PyQt6.QtWidgets import QHeaderView, QHBoxLayout, QLineEdit, QPushButton, QTableWidget, QVBoxLayout, QLabel

from database import DatabaseError
from pages.base_page import BasePage, fill_table
from styles import THEMES


HEADER_QSS = "QHeaderView::section { background-color: #DBEAFE; color: #0F172A; font-weight: 600; font-size: 12px; padding: 10px 12px; border: none; border-right: 1px solid #94A3B8; border-bottom: 2px solid #3B82F6; }"


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



class InterviewsPage(BasePage):
    UI_FILE = "interviews_page.ui"
    THEME = THEMES["interviews"]

    def build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 20, 16, 20)
        root.setSpacing(16)
        root.addWidget(self.make_header("Interviews", "Project exchange between students and mentors"))

        card = self.make_card()
        body = QVBoxLayout(card)
        body.setContentsMargins(20, 20, 20, 20)
        body.setSpacing(14)

        search_row = QHBoxLayout()
        self.inputSearch = QLineEdit()
        self.inputSearch.setPlaceholderText("Search interviews...")
        self.btnSearch = QPushButton("Search")
        search_row.addWidget(self.inputSearch, 1)
        search_row.addWidget(self.btnSearch)
        body.addLayout(search_row)

        button_row = QHBoxLayout()
        self.btnProjectSent = QPushButton("Project Sent")
        self.btnProjectReceived = QPushButton("Project Received")
        button_row.addWidget(self.btnProjectSent)
        button_row.addWidget(self.btnProjectReceived)
        body.addLayout(button_row)

        self.tableInterviews = QTableWidget(0, 0)
        self.tableInterviews.setAlternatingRowColors(True)
        self.tableInterviews.verticalHeader().setVisible(False)
        body.addWidget(self.tableInterviews, 1)
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
        self.add_detail_panel(self.tableInterviews)
        style_table(self.tableInterviews)
        self.route(self.btnReturn, "return_preferences")
        self.btnRefresh.clicked.connect(self.on_refresh)
        self.route(self.btnExit, "exit")
        self.current_view = None
        self.btnSearch.clicked.connect(self.refresh)
        self.inputSearch.returnPressed.connect(self.refresh)
        self.btnProjectSent.clicked.connect(lambda: self.set_view("sent"))
        self.btnProjectReceived.clicked.connect(lambda: self.set_view("received"))

    def set_view(self, view):
        self.current_view = view
        self.refresh()

    def on_refresh(self, *_):
        text = self.refresh()
        self.show_message(f"Data reloaded from the database. {text}" if text else "Data reloaded")

    def refresh(self, *_):
        try:
            headers, rows = self.store.interviews(self.current_view, self.inputSearch.text())
        except DatabaseError as error:
            fill_table(self.tableInterviews, [], [])
            self.show_message(str(error))
            return
        fill_table(self.tableInterviews, headers, rows)
        message = f"{len(rows)} interview record(s) shown"
        self.labelMuted.setText(message)
        self.show_message(message)
        return message
