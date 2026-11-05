from PyQt6.QtWidgets import (QHeaderView, QAbstractItemView, QHBoxLayout, QMessageBox, QPushButton,
                             QTableWidget, QVBoxLayout)

import google_services
from data_store import CALENDAR_COLUMNS
from pages.base_page import BasePage, fill_table
from styles import THEMES


HEADER_QSS = "QHeaderView::section { background-color: #D5DCE8; color: #0F172A; font-weight: 600; font-size: 12px; padding: 10px 12px; border: none; border-right: 1px solid #94A3B8; border-bottom: 2px solid #0B2545; }"


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



class AdminMenuPage(BasePage):
    UI_FILE = "admin_menu_page.ui"
    THEME = THEMES["admin_menu"]

    def build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 20, 16, 20)
        root.setSpacing(16)
        root.addWidget(self.make_header("Admin Menu", "Calendar records and participant mail"))

        card = self.make_card()
        body = QVBoxLayout(card)
        body.setContentsMargins(20, 20, 20, 20)
        body.setSpacing(14)

        button_row = QHBoxLayout()
        self.btnEventRecord = QPushButton("Event Record")
        self.btnMail = QPushButton("Mail")
        button_row.addWidget(self.btnEventRecord)
        button_row.addWidget(self.btnMail)
        button_row.addStretch()
        body.addLayout(button_row)

        self.tableCalendar = QTableWidget(0, len(CALENDAR_COLUMNS))
        self.tableCalendar.setHorizontalHeaderLabels(CALENDAR_COLUMNS)
        self.tableCalendar.setAlternatingRowColors(True)
        self.tableCalendar.verticalHeader().setVisible(False)
        body.addWidget(self.tableCalendar, 1)
        root.addWidget(card, 1)

        self.btnReturnAdmin = QPushButton("Return to Admin Screen")
        self.btnExit = QPushButton("Exit")
        self.btnExit.setObjectName("btnExit")
        root.addLayout(self.make_footer(self.btnReturnAdmin, self.btnExit))

    def connect_signals(self):
        self.add_detail_panel(self.tableCalendar)
        style_table(self.tableCalendar)
        self.route(self.btnReturnAdmin, "preferences_admin")
        self.route(self.btnExit, "exit")
        self.events = []
        self.tableCalendar.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tableCalendar.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.btnEventRecord.clicked.connect(self.on_event_record)
        self.btnMail.clicked.connect(self.on_mail)

    def confirm(self, text):
        answer = QMessageBox.question(self, "Send mail", text)
        return answer == QMessageBox.StandardButton.Yes

    def on_event_record(self, *_):
        try:
            self.events = google_services.fetch_events()
        except google_services.GoogleSetupError as error:
            self.show_message(str(error))
            return
        except Exception as error:  # network or API errors
            self.show_message(f"Google Calendar error: {error}")
            return
        rows = [[e["name"], e["start"], ", ".join(e["participants"]), e["organizer"]] for e in self.events]
        fill_table(self.tableCalendar, CALENDAR_COLUMNS, rows)
        self.show_message(f"{len(rows)} event(s) loaded from Google Calendar")

    def on_mail(self, *_):
        row = self.tableCalendar.currentRow()
        if row < 0 or row >= len(self.events):
            self.show_message("Select an event in the table first.")
            return
        event = self.events[row]
        recipients = event["participants"]
        if not recipients:
            self.show_message("This event has no participant e-mail addresses.")
            return

        subject = f"Reminder: {event['name']}"
        body = (
            "Hello,\n\n"
            f"This is a reminder for \"{event['name']}\" scheduled for {event['start']}.\n\n"
            "Best regards,\nCRM Team"
        )
        if not self.confirm(f"Send this mail to {len(recipients)} participant(s)?\n\n" + ", ".join(recipients)):
            self.show_message("Mail cancelled.")
            return
        try:
            google_services.send_email(recipients, subject, body)
        except google_services.GoogleSetupError as error:
            self.show_message(str(error))
            return
        except Exception as error:
            self.show_message(f"Mail could not be sent: {error}")
            return
        self.show_message(f"Mail sent to {len(recipients)} participant(s)")
