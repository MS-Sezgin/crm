"""CRM Capstone (PostgreSQL version).

Run:
    python main.py        -> pages built in Python code (.py versions)
    python main.py --ui   -> pages loaded from the Qt Designer files in ui/

The database settings come from the environment or from a .env file next to this
program (see .env.example). Load the old Excel data once with migrate_excel_to_db.py.
"""
import sys

from PyQt6.QtWidgets import QApplication, QMainWindow, QMessageBox, QStackedWidget

from data_store import DataStore
from database import ConfigError, Database, DatabaseError, DbConfig
from pages.login_page import LoginPage
from pages.preferences_page import PreferencesPage
from pages.preferences_admin_page import PreferencesAdminPage
from pages.applications_page import ApplicationsPage
from pages.mentor_interview_page import MentorInterviewPage
from pages.interviews_page import InterviewsPage
from pages.admin_menu_page import AdminMenuPage


class MainWindow(QMainWindow):
    def __init__(self, store, use_ui_file=False):
        super().__init__()
        self.store = store
        self.setWindowTitle("CRM Capstone")
        self.resize(1100, 780)
        self.setMinimumSize(820, 600)
        self.is_admin = False

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        self.pages = {
            "login": LoginPage(use_ui_file, store),
            "preferences": PreferencesPage(use_ui_file, store),
            "preferences_admin": PreferencesAdminPage(use_ui_file, store),
            "applications": ApplicationsPage(use_ui_file, store),
            "mentor_interview": MentorInterviewPage(use_ui_file, store),
            "interviews": InterviewsPage(use_ui_file, store),
            "admin_menu": AdminMenuPage(use_ui_file, store),
        }
        for page in self.pages.values():
            page.navigate.connect(self.handle_navigation)
            page.message.connect(self.statusBar().showMessage)
            self.stack.addWidget(page)

        self.show_page("login")

    def closeEvent(self, event):
        """Close the database connection when the window closes."""
        self.store.db.close()
        event.accept()

    def show_page(self, name):
        self.stack.setCurrentWidget(self.pages[name])

    def handle_navigation(self, target):
        if target == "exit":
            self.close()
            return
        if target == "return_preferences":
            target = "preferences_admin" if self.is_admin else "preferences"
        if target == "preferences":
            self.is_admin = False
        elif target == "preferences_admin":
            self.is_admin = True
        if target == "login":
            self.is_admin = False
            self.pages["login"].reset()
        self.show_page(target)


def open_store():
    """Read the settings and connect. Raises ConfigError or DatabaseError with a readable message."""
    db = Database(DbConfig.load())
    db.connect()
    return DataStore(db)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    try:
        store = open_store()
    except (ConfigError, DatabaseError) as error:
        QMessageBox.critical(None, "CRM - database connection", str(error))
        sys.exit(1)
    window = MainWindow(store, use_ui_file="--ui" in sys.argv)
    window.showMaximized()
    window.statusBar().showMessage(store.describe())
    sys.exit(app.exec())
