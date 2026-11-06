from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QMessageBox, QPushButton, QTableWidget, QVBoxLayout

import google_services
from data_store import CALENDAR_COLUMNS
from dialogs import UsersDialog
from pages.base_page import BasePage, fill_table, fit_columns, find_layout
from styles import THEMES


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
        self.route(self.btnReturnAdmin, "preferences_admin")
        self.route(self.btnExit, "exit")
        self.events = []
        self.btnEventRecord.clicked.connect(self.on_event_record)
        self.btnMail.clicked.connect(self.on_mail)
        # "Users" sits next to Mail; added by code so it exists in code mode and in .ui mode
        self.btnUsers = QPushButton("Users")
        self.btnUsers.clicked.connect(self.on_users)
        row = find_layout(self.btnMail.parentWidget().layout(), self.btnMail)
        row.insertWidget(row.indexOf(self.btnMail) + 1, self.btnUsers)

    def decorate(self):
        super().decorate()
        # a line under the table: explains the empty screen first, then reports what was loaded
        self.labelHint = QLabel("Click \"Event Record\" to load the events of your Google Calendar.")
        self.labelHint.setObjectName("labelMuted")
        self.labelHint.setWordWrap(True)
        fit_columns(self.tableCalendar)
        self.findChild(QFrame, "card").layout().addWidget(self.labelHint)

    def on_users(self, *_):
        dialog = UsersDialog(self, self.store, self.current_user)
        self.run_dialog(dialog)

    def confirm(self, text):
        answer = QMessageBox.question(self, "Send mail", text)
        return answer == QMessageBox.StandardButton.Yes

    def on_event_record(self, *_):
        try:
            self.events = google_services.fetch_events()
        except google_services.GoogleSetupError as error:
            self.show_message(str(error))
            self.labelHint.setText(str(error))
            return
        except Exception as error:  # network or API errors
            self.show_message(f"Google Calendar error: {error}")
            self.labelHint.setText(f"Google Calendar error: {error}")
            return
        rows = [[e["name"], e["start"], ", ".join(e["participants"]), e["organizer"]] for e in self.events]
        fill_table(self.tableCalendar, CALENDAR_COLUMNS, rows)
        self.show_message(f"{len(rows)} event(s) loaded from Google Calendar")
        self.labelHint.setText(f"{len(rows)} event(s) loaded from Google Calendar. "
                               "Select one and press Mail to send a reminder.")

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
