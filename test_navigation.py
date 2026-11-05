"""Navigation, database and Google-mock smoke test, run for both code mode and .ui mode.

Run:  python test_navigation.py

Needs a running PostgreSQL and the same settings as the app (CRM_DB_PASSWORD, ...; see
.env.example). The test builds its own temporary schema ("crm_test_<number>") with
database/schema.sql, fills it with sample rows and drops it at the end, so your real
tables are not touched. Google calls are replaced with fake functions.
"""
import dataclasses
import os
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["CRM_CREDENTIALS_DIR"] = tempfile.mkdtemp(prefix="crm_creds_")

from PyQt6.QtWidgets import QApplication, QTextEdit  # noqa: E402

import google_services  # noqa: E402
from data_store import DataStore, cell_text, name_search  # noqa: E402
from database import (ConfigError, CrmRepositories, Database, DatabaseError,  # noqa: E402
                      DbConfig, PasswordHasher)
from main import MainWindow  # noqa: E402

SCHEMA_NAME = f"crm_test_{os.getpid()}"
SCHEMA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "database", "schema.sql")

FAKE_EVENTS = [
    {"name": "Mentor Kickoff", "start": "20.10.2026 10:00", "participants": ["p1@x.com", "p2@x.com"], "organizer": "org@x.com"},
    {"name": "Interview Day", "start": "22.10.2026 14:00", "participants": [], "organizer": "org@x.com"},
]
SENT = []
google_services.fetch_events = lambda *a, **k: list(FAKE_EVENTS)
google_services.send_email = lambda to, subject, body: SENT.append((list(to), subject))


def check(condition, message):
    if not condition:
        raise AssertionError(message)


# ----- test database --------------------------------------------------------------------

def base_config():
    try:
        return DbConfig.load()
    except ConfigError as error:
        raise SystemExit(f"Cannot run the tests: {error}")


def create_test_schema(config):
    """Create the temporary schema and the tables. Returns a Database that uses it."""
    admin = Database(dataclasses.replace(config, schema=""))
    try:
        admin.execute(f"CREATE SCHEMA {SCHEMA_NAME}")
    except DatabaseError as error:
        raise SystemExit(f"Cannot run the tests: {error}")
    finally:
        admin.close()
    db = Database(dataclasses.replace(config, schema=SCHEMA_NAME))
    db.execute_script(SCHEMA_FILE)
    return db


def drop_test_schema(config):
    admin = Database(dataclasses.replace(config, schema=""))
    try:
        admin.execute(f"DROP SCHEMA IF EXISTS {SCHEMA_NAME} CASCADE")
    finally:
        admin.close()


def fill_sample_data(db):
    repos = CrmRepositories(db)
    k, b = repos.kursiyerler, repos.basvurular
    ali = k.add("Ali As", "a@x.com", "111", "1000AA", "Utrecht")
    asli = k.add("Asli Kaya", "b@x.com")
    mehmet = k.add("Mehmet Demir", "c@x.com")
    zeynep = k.add("Zeynep Can", "z@x.com")
    sukru = k.add("Şükrü Işık", "s@x.com")
    ayse = k.add("Ayse Yildiz", "y@x.com")

    # form applications (period VIT3): Ali twice (an exact copy), two with a mentor meeting
    form = {"BasvuruDonemi": "VIT3"}
    b.add(ali, {**form, "MentorGorusmesi": "Yes"})
    b.add(asli, dict(form))
    b.add(mehmet, {**form, "MentorGorusmesi": "Yes"})
    b.add(ali, dict(form))
    b.add(sukru, dict(form))
    # old VIT lists
    for kid in (ali, asli, zeynep):
        b.add(kid, {"BasvuruDonemi": "VIT1"})
    for kid in (ali, mehmet):
        b.add(kid, {"BasvuruDonemi": "VIT2"})

    repos.mulakatlar.add(ali, "2023-06-13", "2023-08-07")
    repos.mulakatlar.add(ayse, "2023-06-18", None)
    repos.mentor.add(zeynep, "2023-05-05", "Ibrahim Sahin", 5, "Mentor Meetings", "x", 3, "note")
    repos.mentor.add(ayse, "2023-05-10", "Harun", 7, "Follow-up")
    repos.kullanicilar.add("student", "1234", "user")
    repos.kullanicilar.add("admin", "admin", "admin")


# ----- the screens ------------------------------------------------------------------------

def run_flow(use_ui_file, store):
    app = QApplication.instance() or QApplication(sys.argv)
    win = MainWindow(store, use_ui_file=use_ui_file)
    pages = win.pages
    login = pages["login"]

    def current():
        return win.stack.currentWidget()

    login.inputUsername.setText("student")
    login.inputPassword.setText("wrong")
    login.btnLogin.click()
    check(current() is pages["login"], "wrong password should not navigate")
    check("Incorrect" in login.labelWarning.text(), "wrong password should show a warning")
    login.checkShowPassword.setChecked(True)
    check(login.inputPassword.echoMode() != login.inputPassword.EchoMode.Password, "show password should reveal text")
    login.checkShowPassword.setChecked(False)
    check(login.inputPassword.echoMode() == login.inputPassword.EchoMode.Password, "hide password should mask text")

    login.inputUsername.setText("student")
    login.inputPassword.setText("1234")
    login.btnLogin.click()
    check(current() is pages["preferences"], "user should reach Preferences")
    pages["preferences"].btnLogout.click()
    check(current() is pages["login"], "log out should return to login")
    check(login.inputUsername.text() == "", "log out should clear the login form")
    login.inputUsername.setText("STUDENT")  # the user name ignores letter case
    login.inputPassword.setText("1234")
    login.btnLogin.click()
    check(current() is pages["preferences"], "user should log in again after log out (any letter case)")

    pages["preferences"].btnApplications.click()
    apps = pages["applications"]
    check("(5)" in apps.btnAllApplications.text(), "the All button should show the count of form applications")
    apps.btnAllApplications.click()
    check(apps.tableApplications.rowCount() == 5, "All Applications should show the 5 form applications")
    check(apps.tableApplications.columnCount() == 27, "Applications should show 27 columns")
    apps.tableApplications.selectRow(0)
    detail = apps.findChild(QTextEdit, "detailText")
    check(not detail.isHidden(), "selected row should show the detail panel")
    check("Full Name:" in detail.toPlainText() and "Ali As" in detail.toPlainText(), "detail should list the fields")
    apps.btnRefresh.click()
    check(apps.tableApplications.rowCount() == 5, "Refresh should keep the current view")
    apps.btnMeetingDefined.click()
    check(apps.tableApplications.rowCount() == 2, "Mentor Meeting Defined should show 2 rows")
    apps.btnMeetingNotDefined.click()
    check(apps.tableApplications.rowCount() == 3, "Mentor Meeting Not Defined should show 3 rows")
    apps.btnAllApplications.click()
    apps.inputSearch.setText("as")
    apps.btnSearch.click()
    check(apps.tableApplications.rowCount() == 3, "search 'as' should find 3 rows (Ali As x2, Asli)")
    apps.inputSearch.setText("sukru")
    apps.btnSearch.click()
    check(apps.tableApplications.rowCount() == 1, "search 'sukru' should find 'Şükrü' (accents ignored)")
    apps.inputSearch.setText("'; DROP TABLE Kursiyerler; --")
    apps.btnSearch.click()
    check(apps.tableApplications.rowCount() == 0, "a hostile search text should just find nothing")
    apps.inputSearch.setText("%")
    apps.btnSearch.click()
    check(apps.tableApplications.rowCount() == 0, "'%' must be searched as a character, not a wildcard")
    apps.inputSearch.setText("")
    apps.comboFilters.setCurrentIndex(1)  # Duplicate Records
    check(apps.tableApplications.rowCount() == 2, "duplicates should show 2 rows")
    apps.comboFilters.setCurrentIndex(2)  # Previous VIT Check
    check(apps.tableApplications.rowCount() == 3, "previous VIT check should show 3 people")
    check(apps.tableApplications.columnCount() == 3, "people views should show 3 columns")
    apps.comboFilters.setCurrentIndex(3)  # Different Record
    check(apps.tableApplications.rowCount() == 3, "different record should show 3 people")
    apps.comboFilters.setCurrentIndex(4)  # Application Filter
    check(apps.tableApplications.rowCount() == 4, "application filter should show each name once")
    apps.inputSearch.setText("")
    check(apps.btnExit is not None, "Applications should have an Exit button")
    apps.btnReturn.click()
    check(current() is pages["preferences"], "Applications return failed")

    pages["preferences"].btnInterviews.click()
    iv = pages["interviews"]
    iv.btnProjectSent.click()
    check(iv.tableInterviews.rowCount() == 2, "Project Sent should show 2 rows")
    iv.btnRefresh.click()
    check(iv.tableInterviews.rowCount() == 2, "Refresh should keep Project Sent view")
    iv.btnProjectReceived.click()
    check(iv.tableInterviews.rowCount() == 1, "Project Received should show 1 row")
    check(iv.tableInterviews.item(0, 1).text() == "13.06.2023", "dates should be shown as dd.mm.yyyy")
    iv.btnReturn.click()

    pages["preferences"].btnMentorInterview.click()
    mt = pages["mentor_interview"]
    check(mt.comboTabs.count() == 3, "tab combo should have All Tabs + 2 categories")
    mt.btnAllConversations.click()
    check(mt.tableConversations.rowCount() == 2, "All Conversations should show 2 rows")
    mt.btnRefresh.click()
    check(mt.tableConversations.rowCount() == 2, "Refresh should reload all conversations")
    mt.comboTabs.setCurrentIndex(1)
    check(mt.tableConversations.rowCount() == 1, "category filter should show 1 row")
    mt.btnAllConversations.click()
    mt.inputSearch.setText("harun")
    mt.btnSearch.click()
    check(mt.tableConversations.rowCount() == 1, "mentor search should also look at the mentor name")
    mt.btnReturn.click()

    # Admin with mocked Google
    login.inputUsername.setText("admin")
    login.inputPassword.setText("admin")
    win.show_page("login")
    login.btnLogin.click()
    check(current() is pages["preferences_admin"], "admin should reach admin Preferences")
    pages["preferences_admin"].btnAdmin.click()
    adm = pages["admin_menu"]
    check(current() is adm, "Admin Menu not opened")

    adm.btnEventRecord.click()
    adm.tableCalendar.selectRow(0)
    check(not adm.findChild(QTextEdit, "detailText").isHidden(), "event detail should show")
    check(adm.tableCalendar.columnCount() == 4, "Admin table should have 4 columns")
    check(adm.tableCalendar.rowCount() == 2, "Event Record should show 2 events")

    adm.tableCalendar.selectRow(1)  # event without participants
    before = len(SENT)
    adm.confirm = lambda text: True
    adm.btnMail.click()
    check(len(SENT) == before, "event without participants must not send mail")

    adm.tableCalendar.selectRow(0)
    adm.confirm = lambda text: False
    adm.btnMail.click()
    check(len(SENT) == before, "cancelled confirmation must not send mail")

    adm.confirm = lambda text: True
    adm.btnMail.click()
    check(len(SENT) == before + 1, "confirmed mail should be sent once")
    check(SENT[-1][0] == ["p1@x.com", "p2@x.com"], "mail should go to the event participants")

    adm.btnReturnAdmin.click()
    check(current() is pages["preferences_admin"], "Admin Menu return failed")
    pages["preferences_admin"].btnApplications.click()
    pages["applications"].btnReturn.click()
    check(current() is pages["preferences_admin"], "admin return should go to admin Preferences")

    # the window must not close the shared connection before the next run
    win.store = DataStore(Database(store.db.config))
    win.close()
    print(f"[{'UI files' if use_ui_file else 'code'}] all checks OK")


# ----- database layer ------------------------------------------------------------------------

def run_database_checks(db, config):
    store = DataStore(db)
    # passwords are hashes, and the old plain value still logs in
    stored = db.fetch_value("SELECT Parola FROM Kullanicilar WHERE Kullanici = 'student'")
    check(stored != "1234" and stored.startswith("pbkdf2_sha256$"), "the password must be stored as a hash")
    check(PasswordHasher().hash("x") != PasswordHasher().hash("x"), "every hash needs its own salt")
    check(store.check_login("admin", "admin") == "admin", "admin role should be returned")
    check(store.check_login("student", "1234") == "user", "user role should be returned")
    check(store.check_login("student", "") is None, "empty password must not log in")
    check(store.check_login("nobody", "1234") is None, "unknown user must not log in")

    # constraints
    for sql, message in (
        ("INSERT INTO Kursiyerler (AdSoyad, MailAdresi) VALUES ('ALI as', 'A@X.com')", "same name + e-mail twice"),
        ("INSERT INTO Basvurular (KursiyerID, BasvuruDonemi) VALUES (999999, 'VIT3')", "application for an unknown trainee"),
        ("INSERT INTO Kullanicilar (Kullanici, Parola, Yetki) VALUES ('x', 'h', 'root')", "an invalid role"),
        ("DELETE FROM Kursiyerler WHERE AdSoyad = 'Ali As'", "deleting a trainee that has applications"),
    ):
        try:
            db.execute(sql)
        except DatabaseError:
            continue
        raise AssertionError(f"the database accepted: {message}")
    db.execute("INSERT INTO Kursiyerler (AdSoyad, MailAdresi) VALUES ('Ali As', 'other@x.com')")
    check(len(db.fetch_all("SELECT 1 FROM Kursiyerler WHERE AdSoyad = 'Ali As'")) == 2,
          "the same name with another e-mail is a different person")

    # a failed transaction leaves nothing behind
    before = db.fetch_value("SELECT count(*) FROM Kursiyerler")
    try:
        with db.transaction():
            db.execute("INSERT INTO Kursiyerler (AdSoyad, MailAdresi) VALUES ('Temp One', 't1@x.com')")
            db.execute("INSERT INTO Basvurular (KursiyerID, BasvuruDonemi) VALUES (999999, 'VIT3')")
    except DatabaseError:
        pass
    check(db.fetch_value("SELECT count(*) FROM Kursiyerler") == before, "a failed transaction must roll back")

    # the helpers
    check(name_search(["k.AdSoyad"], "   ") == ("", []), "blank search text adds no condition")
    check(cell_text(None) == "" and cell_text(22) == "22", "cell_text basics")

    # reconnect after the server dropped the connection
    db._connection.close()
    try:
        store.application_counts()
    except DatabaseError:
        pass  # the first call after a drop may fail, but it must not leave a broken connection
    check(store.application_counts()[0] == 5, "the store should reconnect by itself after a dropped connection")

    # wrong password gives a readable error
    try:
        Database(dataclasses.replace(config, password="definitely-wrong")).connect()
    except DatabaseError as error:
        check("Could not connect" in str(error), "connection errors should be readable")
    else:
        raise AssertionError("a wrong password must not connect")
    print("[database] checks OK")


if __name__ == "__main__":
    config = base_config()
    db = create_test_schema(config)
    try:
        fill_sample_data(db)
        run_database_checks(db, config)
        store = DataStore(db)
        run_flow(False, store)
        run_flow(True, store)
    finally:
        db.close()
        drop_test_schema(config)
    print("All checks passed.")
