from PyQt6.QtWidgets import (QComboBox, QHBoxLayout, QLabel, QLineEdit, QPushButton,
                             QTableWidget, QVBoxLayout)

from database import DatabaseError
from dialogs import ApplicationDialog
from pages.base_page import BasePage, fill_table
from pages.record_actions import RecordActionsMixin
from styles import THEMES

EXTRA_FILTERS = [
    ("More filters...", None),
    ("Duplicate Records", "duplicates"),
    ("Previous VIT Check", "previous_vit"),
    ("Different Record", "different"),
    ("Application Filter", "unique"),
]


class ApplicationsPage(RecordActionsMixin, BasePage):
    UI_FILE = "applications_page.ui"
    THEME = THEMES["applications"]

    def build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 20, 16, 20)
        root.setSpacing(16)
        root.addWidget(self.make_header("Applications", "Search and review submitted applications"))

        card = self.make_card()
        body = QVBoxLayout(card)
        body.setContentsMargins(20, 20, 20, 20)
        body.setSpacing(14)

        search_row = QHBoxLayout()
        self.inputSearch = QLineEdit()
        self.inputSearch.setPlaceholderText("Search applications...")
        self.btnSearch = QPushButton("Search")
        search_row.addWidget(self.inputSearch, 1)
        search_row.addWidget(self.btnSearch)
        body.addLayout(search_row)

        filter_row = QHBoxLayout()
        self.btnAllApplications = QPushButton("All Applications")
        self.btnMeetingDefined = QPushButton("Mentor Meeting Defined")
        self.btnMeetingNotDefined = QPushButton("Mentor Meeting Not Defined")
        for button in (self.btnAllApplications, self.btnMeetingDefined, self.btnMeetingNotDefined):
            filter_row.addWidget(button)
        body.addLayout(filter_row)

        combo_row = QHBoxLayout()
        self.labelFilter = QLabel("Filter")
        self.comboFilters = QComboBox()
        self.comboFilters.addItems([label for label, _ in EXTRA_FILTERS])
        combo_row.addWidget(self.labelFilter)
        combo_row.addWidget(self.comboFilters, 1)
        body.addLayout(combo_row)

        self.tableApplications = QTableWidget(0, 0)
        self.tableApplications.setAlternatingRowColors(True)
        self.tableApplications.verticalHeader().setVisible(False)
        body.addWidget(self.tableApplications, 1)
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
        self.add_detail_panel(self.tableApplications)
        self.setup_record_actions(self.tableApplications, "application", self.on_new, self.on_edit,
                                  self.on_delete, "applications.csv")
        self.route(self.btnReturn, "return_preferences")
        self.btnRefresh.clicked.connect(self.on_refresh)
        self.route(self.btnExit, "exit")
        self.current_view = "all"
        self.btnSearch.clicked.connect(self.refresh)
        self.inputSearch.returnPressed.connect(self.refresh)
        self.btnAllApplications.clicked.connect(lambda: self.set_view("all"))
        self.btnMeetingDefined.clicked.connect(lambda: self.set_view("defined"))
        self.btnMeetingNotDefined.clicked.connect(lambda: self.set_view("not_defined"))
        self.comboFilters.currentIndexChanged.connect(self.on_extra_filter)
        self.update_counts()

    def mark_view(self):
        """Fill the button of the current view; extra filters from the combo box have no button."""
        buttons = {"all": self.btnAllApplications, "defined": self.btnMeetingDefined,
                   "not_defined": self.btnMeetingNotDefined}
        self.mark_segment(buttons.get(self.current_view))

    def on_show(self):
        self.update_counts()
        self.refresh()

    def on_extra_filter(self, index):
        view = EXTRA_FILTERS[index][1]
        if view:
            self.set_view(view)

    def update_counts(self):
        """Show how many records each filter button has."""
        try:
            total, defined, not_defined = self.store.application_counts()
        except DatabaseError:
            total = defined = not_defined = None
        def label(text, count):
            return f"{text} ({count})" if count is not None else text
        self.btnAllApplications.setText(label("All Applications", total))
        self.btnMeetingDefined.setText(label("Mentor Meeting Defined", defined))
        self.btnMeetingNotDefined.setText(label("Mentor Meeting Not Defined", not_defined))

    def set_view(self, view):
        self.current_view = view
        self.refresh()

    def load_view(self):
        """Run the SQL query of the current view; the search text is part of the query."""
        view, search = self.current_view, self.inputSearch.text()
        if view in ("previous_vit", "different"):
            return self.store.people(view, search)
        return self.store.applications(view, search)

    # ----- add, change, delete ------------------------------------------------------------

    def on_new(self):
        saved = {}
        def save(values):
            saved["result"] = self.store.records.add_application(values)
            saved["name"] = values["name"].strip()
        if not self.open_form(ApplicationDialog(self, self.store, save)):
            return
        application_id, _, is_new, earlier = saved["result"]
        self.current_view = "all"            # show the new row: all form applications, no search text
        self.inputSearch.clear()
        self.comboFilters.blockSignals(True)
        self.comboFilters.setCurrentIndex(0)
        self.comboFilters.blockSignals(False)
        self.update_counts()
        self.refresh()
        self.select_record(application_id)
        who = "a new candidate" if is_new else f"an existing candidate ({earlier} earlier application(s))"
        self.show_message(f"Application saved for {saved['name']}, {who}.")

    def on_edit(self):
        record_id, initial = self.load_for_edit(self.store.records.get_application)
        if record_id is None:
            return
        dialog = ApplicationDialog(
            self, self.store, lambda values: self.store.records.update_application(record_id, values), initial)
        if self.open_form(dialog):
            self.update_counts()
            self.refresh()
            self.select_record(record_id)
            self.show_message("The application was updated.")

    def on_delete(self):
        name = self.selected_row_text(1)
        if self.delete_selected(f"the application of {name}", self.store.records.delete_application):
            self.update_counts()
            self.refresh()

    def on_refresh(self, *_):
        self.update_counts()
        text = self.refresh()
        self.show_message(f"Data reloaded from the database. {text}" if text else "Data reloaded")

    def refresh(self, *_):
        try:
            headers, rows = self.load_view()
        except DatabaseError as error:
            fill_table(self.tableApplications, [], [])
            self.show_message(str(error))
            return
        fill_table(self.tableApplications, headers, rows)
        message = f"{len(rows)} record(s) shown"
        self.mark_view()
        self.labelMuted.setText(message)
        self.show_message(message)
        return message
