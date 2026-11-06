"""CRM Capstone (PostgreSQL version).

Run:
    python main.py        -> pages built in Python code (.py versions)
    python main.py --ui   -> pages loaded from the Qt Designer files in ui/

The database settings come from the environment or from a .env file next to this
program (see .env.example). Load the old Excel data once with migrate_excel_to_db.py.
"""
import sys

import icons
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (QApplication, QHBoxLayout, QLabel, QMainWindow, QMessageBox, QStackedWidget,
                             QWidget)

from data_store import DataStore
from database import ConfigError, Database, DatabaseError, DbConfig
from pages.login_page import LoginPage
from pages.preferences_page import PreferencesPage
from pages.preferences_admin_page import PreferencesAdminPage
from pages.applications_page import ApplicationsPage
from pages.mentor_interview_page import MentorInterviewPage
from pages.interviews_page import InterviewsPage
from pages.admin_menu_page import AdminMenuPage
from sidebar import Sidebar
from styles import STATUSBAR_QSS

FONT_FAMILIES = ["Segoe UI Variable Text", "Segoe UI", "Inter", "Helvetica Neue", "Arial"]


class MainWindow(QMainWindow):
    """Side menu on the left, the current page on the right (the login page uses the whole window)."""

    def __init__(self, store, use_ui_file=False):
        super().__init__()
        self.store = store
        self.setWindowTitle("CRM Capstone")
        self.setWindowIcon(icons.app_icon())
        self.resize(1280, 800)
        self.setMinimumSize(1000, 680)
        self.is_admin = False
        self.user_name = ""

        central = QWidget()
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.sidebar = Sidebar()
        self.sidebar.navigate.connect(self.handle_navigation)
        self.stack = QStackedWidget()
        layout.addWidget(self.sidebar)
        layout.addWidget(self.stack, 1)
        self.setCentralWidget(central)

        status = self.statusBar()
        status.setStyleSheet(STATUSBAR_QSS)
        status.setSizeGripEnabled(False)
        self.labelDatabase = QLabel(store.describe_short())
        self.labelDatabase.setToolTip("PostgreSQL connection of this window")
        status.addPermanentWidget(self.labelDatabase)

        self.pages = {
            "login": LoginPage(use_ui_file, store),
            "preferences": PreferencesPage(use_ui_file, store),
            "preferences_admin": PreferencesAdminPage(use_ui_file, store),
            "applications": ApplicationsPage(use_ui_file, store),
            "mentor_interview": MentorInterviewPage(use_ui_file, store),
            "interviews": InterviewsPage(use_ui_file, store),
            "admin_menu": AdminMenuPage(use_ui_file, store),
        }
        for name, page in self.pages.items():
            page.navigate.connect(self.handle_navigation)
            page.message.connect(self.statusBar().showMessage)
            if name != "login":
                page.set_embedded()  # the side menu replaces their Return / Exit buttons
            self.stack.addWidget(page)

        self.show_page("login")

    def closeEvent(self, event):
        """Close the database connection when the window closes."""
        self.store.db.close()
        event.accept()

    def show_page(self, name):
        page = self.pages[name]
        on_login = name == "login"
        self.sidebar.setVisible(not on_login)
        if not on_login:
            self.sidebar.set_active(name)
        self.stack.setCurrentWidget(page)
        self.statusBar().clearMessage()  # drop the note of the previous page
        page.on_show()

    def handle_navigation(self, target):
        if target == "exit":
            self.close()
            return
        if target == "return_preferences":
            target = "preferences_admin" if self.is_admin else "preferences"
        coming_from_login = self.stack.currentWidget() is self.pages["login"]
        if target == "preferences":
            self.is_admin = False
        elif target == "preferences_admin":
            self.is_admin = True
        if coming_from_login and target in ("preferences", "preferences_admin"):
            self.user_name = self.pages["login"].username
            self.sidebar.set_user(self.user_name, self.is_admin)
            for home in ("preferences", "preferences_admin"):
                self.pages[home].set_user(self.user_name)
        if target == "login":
            self.is_admin = False
            self.user_name = ""
            self.pages["login"].reset()
        for page in self.pages.values():  # Edit / Delete / Users are for administrators only
            page.set_role(self.is_admin, self.user_name)
        self.show_page(target)


def open_store():
    """Read the settings and connect. Raises ConfigError or DatabaseError with a readable message."""
    db = Database(DbConfig.load())
    db.connect()
    return DataStore(db)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    font = QFont()
    font.setFamilies(FONT_FAMILIES)
    font.setPointSize(10)
    app.setFont(font)
    app.setWindowIcon(icons.app_icon())
    try:
        store = open_store()
    except (ConfigError, DatabaseError) as error:
        QMessageBox.critical(None, "CRM - database connection", str(error))
        sys.exit(1)
    window = MainWindow(store, use_ui_file="--ui" in sys.argv)
    window.showMaximized()
    window.statusBar().showMessage(store.describe())
    sys.exit(app.exec())
