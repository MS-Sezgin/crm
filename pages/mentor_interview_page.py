from PyQt6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QLineEdit, QPushButton, QTableWidget, QVBoxLayout

from database import DatabaseError
from dialogs import MentorDialog
from pages.base_page import BasePage, fill_table
from pages.record_actions import RecordActionsMixin
from styles import THEMES


class MentorInterviewPage(RecordActionsMixin, BasePage):
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
        self.setup_record_actions(self.tableConversations, "meeting", self.on_new, self.on_edit,
                                  self.on_delete, "mentor_meetings.csv")
        self.route(self.btnReturn, "return_preferences")
        self.btnRefresh.clicked.connect(self.on_refresh)
        self.route(self.btnExit, "exit")
        self.current_category = None
        self.load_tabs()
        self.btnSearch.clicked.connect(self.refresh)
        self.inputSearch.returnPressed.connect(self.refresh)
        self.btnAllConversations.clicked.connect(self.show_all)
        self.comboTabs.currentIndexChanged.connect(self.on_tab_changed)

    def on_show(self):
        self.load_tabs()  # the categories may have changed since the last visit
        self.current_category = None
        self.refresh()

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

    # ----- add, change, delete ------------------------------------------------------------

    def show_everything(self):
        """All conversations, no search text: the view in which a changed row is surely visible."""
        self.inputSearch.clear()
        self.load_tabs()  # a new recommendation text becomes a new tab
        self.current_category = None
        self.refresh()

    def on_new(self):
        saved = {}
        def save(values):
            saved["id"] = self.store.records.add_mentor_meeting(values)
        if self.open_form(MentorDialog(self, self.store, save)):
            self.show_everything()
            self.select_record(saved["id"])
            self.show_message("Mentor meeting saved.")

    def on_edit(self):
        record_id, initial = self.load_for_edit(self.store.records.get_mentor_meeting)
        if record_id is None:
            return
        dialog = MentorDialog(
            self, self.store, lambda values: self.store.records.update_mentor_meeting(record_id, values), initial)
        if self.open_form(dialog):
            self.show_everything()
            self.select_record(record_id)
            self.show_message("The mentor meeting was updated.")

    def on_delete(self):
        name = self.selected_row_text(2)
        date = self.selected_row_text(0)
        if self.delete_selected(f"the mentor meeting of {name} ({date})", self.store.records.delete_mentor_meeting):
            self.show_everything()

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
        self.mark_segment(self.btnAllConversations if self.current_category is None else None)
        self.labelMuted.setText(message)
        self.show_message(message)
        return message
