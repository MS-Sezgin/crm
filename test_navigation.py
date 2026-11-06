"""Navigation, database and Google-mock smoke test, run for both code mode and .ui mode.

Run:  python test_navigation.py

Needs a running PostgreSQL and the same settings as the app (CRM_DB_PASSWORD, ...; see
.env.example). The test builds its own temporary schema ("crm_test_<number>") with
database/schema.sql, fills it with sample rows and drops it at the end, so your real
tables are not touched. Google calls are replaced with fake functions.
"""
import csv
import dataclasses
import datetime
import os
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["CRM_CREDENTIALS_DIR"] = tempfile.mkdtemp(prefix="crm_creds_")

from PyQt6.QtWidgets import QApplication, QTextEdit  # noqa: E402

import google_services  # noqa: E402
from data_store import DataStore, cell_text, name_search  # noqa: E402
from database import (ConfigError, CrmRepositories, Database, DatabaseError,  # noqa: E402
                      DbConfig, PasswordHasher, RecordService, ValidationError)
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

    check(win.sidebar.isHidden(), "the side menu must be hidden on the login page")
    check(not login.btnClose.isHidden(), "the login page keeps its own Close button")
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
    check(not win.sidebar.isHidden(), "the side menu should show after login")
    check(win.sidebar.userName.text().lower() == "student", "the side menu should show the user name")
    check(win.sidebar.adminButtons[0].isHidden(), "a normal user must not see the Admin entry")
    check(win.sidebar.buttons["home"].isChecked(), "Home should be lit on the home page")
    check("5 applications" in pages["preferences"].tile_texts["btnApplications"].text(),
          "the Applications card should show the live count")
    check("2 projects sent" in pages["preferences"].tile_texts["btnInterviews"].text(),
          "the Interviews card should show the live count")
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
    check(apps.btnAllApplications.isChecked() and not apps.btnMeetingDefined.isChecked(),
          "the chosen filter button should look selected")
    check(apps.btnReturn.isHidden() and apps.btnExit.isHidden(), "the side menu replaces Return and Exit")
    check(apps.tableApplications.editTriggers() == apps.tableApplications.EditTrigger.NoEditTriggers,
          "tables must be read-only")
    apps.btnMeetingDefined.click()
    check(apps.btnMeetingDefined.isChecked() and not apps.btnAllApplications.isChecked(),
          "the selected filter should move to the clicked button")
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
    check(not any(button.isChecked() for button in apps.segments), "an extra filter lights no button")
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
    # the side menu opens every page and lights its own entry
    for key, page_name in (("applications", "applications"), ("mentor_interview", "mentor_interview"),
                           ("interviews", "interviews"), ("home", "preferences")):
        win.sidebar.buttons[key].click()
        check(current() is pages[page_name], f"side menu entry {key} should open {page_name}")
        check(win.sidebar.buttons[key].isChecked(), f"side menu entry {key} should be lit")
    win.sidebar.buttons["applications"].click()
    # opening a page loads its list again and keeps the last chosen view (Application Filter: 4 names)
    check(pages["applications"].tableApplications.rowCount() == 4, "a page should load its list when opened")
    win.sidebar.buttons["home"].click()

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
    check(not win.sidebar.adminButtons[0].isHidden(), "an admin should see the Admin entry")
    check(win.sidebar.userRole.text() == "Administrator", "the side menu should show the role")
    win.sidebar.buttons["admin_menu"].click()
    check(current() is pages["admin_menu"], "the Admin entry should open the Admin Menu")
    check("Event Record" in pages["admin_menu"].labelHint.text(), "the Admin page should explain the empty table")
    win.sidebar.buttons["home"].click()
    check(current() is pages["preferences_admin"], "admin Home should go to the admin home page")
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

    win.sidebar.btnLogout.click()
    check(current() is login and win.sidebar.isHidden(), "Log out in the side menu should return to the login page")

    # the window must not close the shared connection before the next run
    win.store = DataStore(Database(store.db.config))
    win.close()
    print(f"[{'UI files' if use_ui_file else 'code'}] all checks OK")


# ----- adding, changing and deleting records ---------------------------------------------------

def expect_invalid(call, fragment, message):
    """``call`` must raise a ValidationError whose text contains ``fragment``."""
    try:
        call()
    except ValidationError as error:
        check(fragment.lower() in str(error).lower(), f"{message}: wrong message '{error}'")
        return
    raise AssertionError(f"{message}: the input was accepted")


def run_record_checks(db):
    """The write side (RecordService): validation, person matching, transactions, cleanup."""
    service = RecordService(CrmRepositories(db))
    repos = service.repos
    counts_before = repos.counts()
    good = {"name": "Test Person", "email": "test.person@example.com", "phone": "0612345678",
            "postal_code": "1011AB", "province": "Utrecht", "period": "VIT4", "status": "Testing"}

    # applications: every bad input is refused and leaves nothing behind
    for change, fragment in (({"name": " "}, "full name"), ({"name": "A"}, "full name"),
                             ({"email": ""}, "e-mail"), ({"email": "not-an-email"}, "valid e-mail"),
                             ({"phone": "abc"}, "phone"), ({"postal_code": "12345678901"}, "postal"),
                             ({"period": ""}, "period"), ({"period": "VIT1"}, "old list"),
                             ({"period": "vit2"}, "old list"), ({"period": "bad;period"}, "period")):
        expect_invalid(lambda c=change: service.add_application({**good, **c}), fragment, f"application {change}")
    check(repos.counts() == counts_before, "refused applications must not change the database")

    # a new person: one candidate row + one application, time stamp filled in
    application, person, is_new, earlier = service.add_application(good)
    check(is_new and earlier == 0, "a new candidate should be reported as new")
    check(repos.kursiyerler.count() == counts_before["Kursiyerler"] + 1, "a new candidate row")
    check(db.fetch_value("SELECT ZamanDamgasi IS NOT NULL FROM Basvurular WHERE BasvuruID = %s", (application,)),
          "the application time stamp should be set automatically")
    # same person typed differently (case, accents, spaces): reused, not duplicated; contact only fills gaps
    again, person_again, is_new, earlier = service.add_application(
        {**good, "name": "  TEST   person ", "email": "TEST.Person@Example.com", "phone": "0699999999"})
    check(person_again == person and not is_new and earlier == 1, "a known candidate must be reused")
    check(repos.kursiyerler.count() == counts_before["Kursiyerler"] + 1, "no second candidate row")
    check(repos.kursiyerler.contact(person)[0] == "0612345678", "an existing phone number must be kept")
    # a known person without phone gets it filled in
    asli = repos.kursiyerler.find("Asli Kaya", "b@x.com")
    service.add_application({**good, "name": "ASLI kaya", "email": "B@x.com", "phone": "0611111111", "period": "VIT4"})
    check(repos.kursiyerler.contact(asli)[0] == "0611111111", "an empty phone number should be filled in")
    # a failure in the middle rolls the new candidate back
    people_before = repos.kursiyerler.count()
    original_add = repos.basvurular.add
    def broken(*_a, **_k):
        raise DatabaseError("simulated failure")
    repos.basvurular.add = broken
    try:
        service.add_application({**good, "name": "Rollback Person", "email": "rollback@example.com"})
    except DatabaseError:
        pass
    repos.basvurular.add = original_add
    check(repos.kursiyerler.count() == people_before, "a failed application must not leave a candidate behind")

    # change an application
    form = service.get_application(application)
    check(form["name"] == "Test Person" and form["period"] == "VIT4" and form["status"] == "Testing",
          "get_application should return the form values")
    service.update_application(application, {**form, "status": "  Moved   in  ", "phone": "0622222222", "motivation": "Line 1\n\n Line 2 "})
    form = service.get_application(application)
    check(form["status"] == "Moved in" and form["phone"] == "0622222222", "the update should be saved")
    check(form["motivation"] == "Line 1\n\nLine 2", "line breaks of the motivation text are kept")
    check(form["name"] == "Test Person", "the name never changes through an update")
    expect_invalid(lambda: service.update_application(application, {**form, "period": "VIT1"}), "old list", "update to old list")
    expect_invalid(lambda: service.update_application(999999, form), "no longer exists", "update of a missing record")

    # delete: the candidate goes with their last record, but not before
    check(service.delete_application(again) is False, "the candidate still has another application")
    check(service.delete_application(application) is True, "the candidate has no records left: removed too")
    check(repos.kursiyerler.get(person) is None, "the candidate row should be gone")
    expect_invalid(lambda: service.delete_application(application), "no longer exists", "double delete")
    for row in db.fetch_all("SELECT BasvuruID FROM Basvurular WHERE BasvuruDonemi = 'VIT4'"):
        service.delete_application(row[0])
    # people with old records are never removed by deleting a newer application
    ali = repos.kursiyerler.find("Ali As", "a@x.com")
    extra, *_ = service.add_application({**good, "name": "Ali As", "email": "a@x.com"})
    check(service.delete_application(extra) is False, "Ali has other records and must stay")
    check(repos.kursiyerler.get(ali) is not None, "Ali must still exist")

    # mentor meetings
    ayse = repos.kursiyerler.find("Ayse Yildiz", "y@x.com")
    meeting = {"kursiyer_id": ayse, "date": datetime.date(2026, 11, 1), "mentor": "Test Mentor", "score": 8,
               "recommendation": "Follow-up", "notes": "ok"}
    for change, fragment in (({"kursiyer_id": None}, "candidate"), ({"kursiyer_id": 999999}, "candidate"),
                             ({"date": None}, "date"), ({"mentor": ""}, "mentor"), ({"score": 11}, "score"),
                             ({"score": -1}, "score"), ({"secondary_score": 99}, "secondary"),
                             ({"date": "2026-11-01"}, "date")):
        expect_invalid(lambda c=change: service.add_mentor_meeting({**meeting, **c}), fragment, f"meeting {change}")
    meeting_id = service.add_mentor_meeting(meeting)
    check(service.get_mentor_meeting(meeting_id)["mentor"] == "Test Mentor", "the meeting should be saved")
    service.update_mentor_meeting(meeting_id, {**meeting, "score": 3, "mentor": " Other  Mentor "})
    check(service.get_mentor_meeting(meeting_id)["score"] == 3
          and service.get_mentor_meeting(meeting_id)["mentor"] == "Other Mentor", "the meeting update should be saved")
    check(service.delete_mentor_meeting(meeting_id) is False, "Ayse has an interview, so she stays")
    expect_invalid(lambda: service.delete_mentor_meeting(meeting_id), "no longer exists", "double meeting delete")

    # interviews
    zeynep = repos.kursiyerler.find("Zeynep Can", "z@x.com")
    day = datetime.date
    for change, fragment in (({"kursiyer_id": None}, "candidate"), ({"sent": None, "received": None}, "at least one"),
                             ({"sent": day(2026, 5, 2), "received": day(2026, 5, 1)}, "before")):
        expect_invalid(lambda c=change: service.add_interview({"kursiyer_id": zeynep, "sent": day(2026, 5, 1), **c}),
                       fragment, f"interview {change}")
    interview = service.add_interview({"kursiyer_id": zeynep, "sent": day(2026, 5, 1), "received": None})
    service.update_interview(interview, {"kursiyer_id": zeynep, "sent": day(2026, 5, 1), "received": day(2026, 5, 9)})
    check(service.get_interview(interview)["received"] == day(2026, 5, 9), "the interview update should be saved")
    check(service.delete_interview(interview) is False, "Zeynep has other records")

    # a candidate is removed only when no record of any kind is left
    app_id, lone, *_ = service.add_application({**good, "name": "Lone Person", "email": "lone@example.com"})
    m_id = service.add_mentor_meeting({**meeting, "kursiyer_id": lone})
    i_id = service.add_interview({"kursiyer_id": lone, "sent": day(2026, 5, 1), "received": None})
    check(service.delete_application(app_id) is False and repos.kursiyerler.get(lone), "other records keep the candidate")
    check(service.delete_interview(i_id) is False and repos.kursiyerler.get(lone), "a mentor meeting keeps the candidate")
    check(service.delete_mentor_meeting(m_id) is True and repos.kursiyerler.get(lone) is None,
          "the last record takes the candidate along")

    # users
    expect_invalid(lambda: service.add_user("a", "secret1", "user"), "username", "short username")
    expect_invalid(lambda: service.add_user("two words", "secret1", "user"), "spaces", "username with a space")
    expect_invalid(lambda: service.add_user("newbie", "123", "user"), "password", "short password")
    expect_invalid(lambda: service.add_user("newbie", "secret1", "root"), "role", "invalid role")
    expect_invalid(lambda: service.add_user("STUDENT", "secret1", "user"), "taken", "duplicate user (any letter case)")
    service.add_user("newbie", "secret1", "user")
    check(stored_is_hash(db, "newbie") and DataStore(db).check_login("NEWBIE", "secret1") == "user",
          "a new user is stored hashed and can log in")
    service.reset_password("newbie", "another1")
    check(DataStore(db).check_login("newbie", "secret1") is None and DataStore(db).check_login("newbie", "another1") == "user",
          "the old password must stop working after a reset")
    expect_invalid(lambda: service.reset_password("newbie", "x"), "password", "short reset password")
    expect_invalid(lambda: service.reset_password("ghost", "another1"), "no longer exists", "reset of a missing user")
    expect_invalid(lambda: service.delete_user("newbie", "NewBie"), "signed in", "deleting yourself")
    expect_invalid(lambda: service.delete_user("admin", "student"), "last administrator", "deleting the last admin")
    service.add_user("boss", "secret1", "admin")
    service.delete_user("admin", "boss")            # a second admin exists now
    expect_invalid(lambda: service.delete_user("boss", "student"), "last administrator", "deleting the new last admin")
    service.delete_user("newbie", "boss")
    expect_invalid(lambda: service.delete_user("newbie", "boss"), "no longer exists", "deleting a missing user")
    # put the original accounts back
    repos.kullanicilar.add("admin", "admin", "admin")
    service.delete_user("boss", "admin")

    # everything is back as before
    check(repos.counts() == counts_before, f"the checks must leave the data as it was: {repos.counts()} != {counts_before}")
    print("[records] checks OK")


def stored_is_hash(db, username):
    value = db.fetch_value("SELECT Parola FROM Kullanicilar WHERE Kullanici = %s", (username,))
    return value.startswith("pbkdf2_sha256$")


def login_as(win, user, password):
    login = win.pages["login"]
    win.show_page("login")
    login.inputUsername.setText(user)
    login.inputPassword.setText(password)
    login.btnLogin.click()


def submit_form(**fields):
    """A stand-in for run_dialog: fill the form fields, press Save, return the dialog."""
    def run(dialog):
        for name, value in fields.items():
            widget = getattr(dialog, name)
            if hasattr(widget, "setCurrentText"):
                if widget.isEditable():
                    widget.setCurrentText(str(value))
                else:
                    widget.setCurrentIndex(widget.findText(str(value)))
            elif hasattr(widget, "setPlainText"):
                widget.setPlainText(value)
            elif hasattr(widget, "setText"):
                widget.setText(value)
            elif hasattr(widget, "setValue"):
                widget.setValue(value)
            elif hasattr(widget, "setDate"):
                widget.setDate(value)
        run.dialog = dialog
        dialog.accept()
    return run


def run_record_flow(use_ui_file, store):
    """Add / change / delete through the screens, for a normal user and for an administrator."""
    from PyQt6.QtCore import QDate
    app = QApplication.instance() or QApplication(sys.argv)
    win = MainWindow(store, use_ui_file=use_ui_file)
    pages = win.pages
    apps, mentor, iv, adm = (pages["applications"], pages["mentor_interview"], pages["interviews"], pages["admin_menu"])
    db = store.db
    people_before = db.fetch_value("SELECT count(*) FROM Kursiyerler")

    # ---- a normal user: New and Export work, Edit and Delete stay off
    login_as(win, "student", "1234")
    win.sidebar.buttons["applications"].click()
    check(apps.btnNew.isEnabled() and apps.btnExport.isEnabled(), "a user can add records and export")
    apps.btnAllApplications.click()
    apps.tableApplications.selectRow(0)
    check(not apps.btnEdit.isEnabled() and not apps.btnDelete.isEnabled(), "a user must not edit or delete")
    check("administrators" in apps.btnEdit.toolTip(), "the disabled Edit button should explain why")
    out = os.path.join(tempfile.mkdtemp(prefix="crm_csv_"), "applications.csv")
    apps.ask_save_path = lambda name: out
    check(apps.export_csv() == out, "Export CSV should write the file")
    with open(out, encoding="utf-8-sig", newline="") as handle:
        exported = list(csv.reader(handle, delimiter=";"))
    check(len(exported) == 6 and len(exported[0]) == 27 and exported[0][1] == "Full Name"
          and exported[1][1] == "Ali As", "the CSV should hold the header and the 5 rows on screen")
    apps.ask_save_path = lambda name: ""
    check(apps.export_csv() is None, "cancelling the file dialog exports nothing")
    # a user adds an application (the admin buttons stay off for the new row as well)
    apps.run_dialog = submit_form(inputName="Flow Person", inputEmail="flow@example.com", inputPhone="0612345678",
                                  comboPeriod="VIT4", comboStatus="Testing")
    apps.btnNew.click()
    check(apps.tableApplications.rowCount() == 6, "the new application should appear in the table")
    check(apps.tableApplications.currentRow() >= 0 and apps.selected_row_text(1) == "Flow Person",
          "the new row should be selected")
    check("(6)" in apps.btnAllApplications.text(), "the filter button count should include the new row")
    check(not apps.btnDelete.isEnabled(), "still no Delete for a user")
    win.sidebar.btnLogout.click()

    # ---- the administrator
    login_as(win, "admin", "admin")
    win.sidebar.buttons["applications"].click()
    apps.btnAllApplications.click()
    apps.inputSearch.setText("flow")
    apps.btnSearch.click()
    apps.tableApplications.selectRow(0)
    check(apps.btnEdit.isEnabled() and apps.btnDelete.isEnabled(), "an administrator can edit and delete")
    # a bad form keeps the dialog open with a message and changes nothing
    apps.run_dialog = submit_form(inputName="Bad Mail", inputEmail="nope", comboPeriod="VIT4")
    apps.btnNew.click()
    dialog = apps.run_dialog.dialog
    check(not dialog.saved and "e-mail" in dialog.labelWarning.text().lower(), "an invalid form shows its message")
    check(db.fetch_value("SELECT count(*) FROM Kursiyerler") == people_before + 1, "an invalid form saves nothing")
    # change it
    apps.run_dialog = submit_form(comboStatus="Moved into housing", inputPhone="0699999999")
    apps.btnEdit.click()
    dialog = apps.run_dialog.dialog
    check(dialog.saved and not dialog.inputName.isEnabled() and not dialog.inputEmail.isEnabled(),
          "the change should be saved, name and e-mail stay locked")
    check(dialog.inputName.text() == "Flow Person" and dialog.comboPeriod.currentText() == "VIT4",
          "the edit form should start with the saved values")
    row = apps.tableApplications.currentRow()
    check(apps.tableApplications.item(row, 6).text() == "Moved into housing"
          and apps.tableApplications.item(row, 3).text() == "0699999999", "the table should show the change")
    # delete it: cancelled first, then confirmed
    apps.ask_confirm = lambda title, text: False
    apps.btnDelete.click()
    check(apps.tableApplications.rowCount() == 1, "a cancelled delete keeps the row")
    apps.ask_confirm = lambda title, text: True
    apps.btnDelete.click()
    check(apps.tableApplications.rowCount() == 0, "the deleted application should be gone")
    check(db.fetch_value("SELECT count(*) FROM Kursiyerler") == people_before, "the candidate without records is removed")
    apps.inputSearch.setText("")
    apps.btnAllApplications.click()
    check("(5)" in apps.btnAllApplications.text() and apps.tableApplications.rowCount() == 5, "back to 5 applications")
    # the people views are not single records: nothing to edit there
    apps.comboFilters.setCurrentIndex(2)
    apps.tableApplications.selectRow(0)
    check(not apps.btnEdit.isEnabled() and not apps.btnDelete.isEnabled(), "rows of the people views cannot be edited")
    apps.btnAllApplications.click()

    # ---- mentor meetings
    win.sidebar.buttons["mentor_interview"].click()
    check(mentor.tableConversations.rowCount() == 2, "two mentor conversations at the start")
    label = next(text for kid, text in store.candidates() if text.startswith("Ayse Yildiz"))
    mentor.run_dialog = submit_form(comboCandidate=label, comboMentor="Flow Mentor", comboScore=8,
                                    comboRecommendation="Brand New Tab", inputDate=QDate(2026, 11, 1))
    mentor.btnNew.click()
    check(mentor.tableConversations.rowCount() == 3, "the new meeting should show up")
    check("Brand New Tab" in [mentor.comboTabs.itemText(i) for i in range(mentor.comboTabs.count())],
          "a new recommendation text becomes a new tab")
    check(mentor.selected_row_text(2) == "Ayse Yildiz" and mentor.selected_row_text(3) == "Flow Mentor",
          "the new meeting should be selected")
    mentor.run_dialog = submit_form(comboScore=5)
    mentor.btnEdit.click()
    check(mentor.run_dialog.dialog.saved and not mentor.run_dialog.dialog.comboCandidate.isEnabled(),
          "the meeting change is saved, the candidate stays locked")
    check(mentor.selected_row_text(4) == "5", "the table should show the new score")
    mentor.run_dialog = submit_form(comboCandidate="nobody at all", comboMentor="X Y")
    mentor.btnNew.click()
    check("candidate" in mentor.run_dialog.dialog.labelWarning.text().lower(), "an unknown candidate is refused")
    mentor.ask_confirm = lambda title, text: True
    mentor.btnDelete.click()
    check(mentor.tableConversations.rowCount() == 2, "the meeting should be deleted")

    # ---- interviews
    win.sidebar.buttons["interviews"].click()
    check(iv.tableInterviews.rowCount() == 2, "two interview records at the start")
    label = next(text for kid, text in store.candidates() if text.startswith("Zeynep Can"))
    iv.run_dialog = submit_form(comboCandidate=label)  # no date at all
    iv.btnNew.click()
    check("at least one" in iv.run_dialog.dialog.labelWarning.text().lower(), "a record without any date is refused")
    def with_dates(dialog):
        dialog.comboCandidate.setCurrentText(label)
        dialog.inputSent.check.setChecked(True)
        dialog.inputSent.field.setDate(QDate(2026, 5, 10))
        dialog.inputReceived.check.setChecked(True)
        dialog.inputReceived.field.setDate(QDate(2026, 5, 1))   # before it was sent
        with_dates.first = dialog
        dialog.accept()
        check(not dialog.saved and "before" in dialog.labelWarning.text(), "received before sent is refused")
        dialog.inputReceived.field.setDate(QDate(2026, 5, 20))
        dialog.accept()
    iv.run_dialog = with_dates
    iv.btnNew.click()
    check(iv.tableInterviews.rowCount() == 3 and iv.selected_row_text(1) == "10.05.2026"
          and iv.selected_row_text(2) == "20.05.2026", "the new interview record should show up with its dates")
    iv.ask_confirm = lambda title, text: True
    iv.btnDelete.click()
    check(iv.tableInterviews.rowCount() == 2, "the interview record should be deleted")

    # ---- users (Admin menu)
    from dialogs import UsersDialog
    win.sidebar.buttons["admin_menu"].click()
    shown = {}
    adm.run_dialog = lambda dialog: shown.update(dialog=dialog)
    adm.btnUsers.click()
    users = shown["dialog"]
    check(isinstance(users, UsersDialog) and users.current_user == "admin", "the Users window knows who is signed in")
    check(users.tableUsers.rowCount() == 2 and users.tableUsers.item(0, 0).text() == "admin"
          and users.tableUsers.item(0, 1).text() == "Administrator", "the Users window lists the users, admins first")
    users.exec_dialog = lambda dialog: (setattr(dialog, "_ran", True),
                                        dialog.inputUsername.setText("tmpuser"),
                                        dialog.inputPassword.setText("secret1"),
                                        dialog.inputRepeat.setText("different"),
                                        dialog.accept(),
                                        check("not the same" in dialog.labelWarning.text(), "mismatching passwords are refused"),
                                        dialog.inputRepeat.setText("secret1"),
                                        dialog.accept())
    users.btnAdd.click()
    check(users.tableUsers.rowCount() == 3, "the new user should be listed")
    check(store.check_login("tmpuser", "secret1") == "user", "the new user can log in")
    users.tableUsers.selectRow(next(r for r in range(3) if users.tableUsers.item(r, 0).text() == "admin"))
    users.confirm = lambda text: True
    users.btnDelete.click()
    check("signed in" in users.labelWarning.text() and users.tableUsers.rowCount() == 3, "you cannot delete yourself")
    users.tableUsers.selectRow(next(r for r in range(3) if users.tableUsers.item(r, 0).text() == "tmpuser"))
    users.btnDelete.click()
    check(users.tableUsers.rowCount() == 2 and store.check_login("tmpuser", "secret1") is None, "the user should be deleted")
    users.close()

    win.sidebar.btnLogout.click()
    check(not apps.btnEdit.isEnabled() and not apps.is_admin, "after logging out nobody is an administrator")
    win.store = DataStore(Database(store.db.config))
    win.close()
    print(f"[{'UI files' if use_ui_file else 'code'}] record screens OK")


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

    summary = store.summary()
    check(summary == {"applications": 5, "meeting_defined": 2, "mentor": 2, "sent": 2, "received": 1},
          f"the home screen numbers are wrong: {summary}")

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
        run_record_checks(db)
        run_record_flow(False, store)
        run_record_flow(True, store)
        check(CrmRepositories(db).counts() == {"Kursiyerler": 7, "Basvurular": 10, "Mentortablosu": 2,
                                               "Mulakatlar": 2, "Kullanicilar": 2},
              "the tests must leave the sample data unchanged")
    finally:
        db.close()
        drop_test_schema(config)
    print("All checks passed.")
