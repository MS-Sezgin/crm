"""Entry forms (pop-up windows) for adding and changing records.

Every form is a ``FormDialog``: fields on top, a red message line, Cancel and Save below.
Save runs the ``submit`` function the page passes in (a RecordService call). When that raises a
``ValidationError`` or ``DatabaseError`` the message is shown in the form and the form stays open,
so nothing the user typed is lost. After a successful save ``dialog.saved`` is True.

    ApplicationDialog   new / change an application (and its candidate)
    MentorDialog        new / change a mentor meeting
    InterviewDialog     new / change a project sent / received record
    UsersDialog         list of users with add, reset password and delete (Admin menu)
"""
from datetime import date

from PyQt6.QtCore import QDate, Qt
from PyQt6.QtWidgets import (QCheckBox, QComboBox, QCompleter, QDateEdit, QDialog, QFormLayout, QFrame,
                             QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPlainTextEdit, QPushButton,
                             QScrollArea, QTableWidget, QVBoxLayout, QWidget)

import icons
from database import DatabaseError, ValidationError
from pages.base_page import fill_table, style_table
from styles import THEMES, build_stylesheet

DATE_FORMAT = "dd.MM.yyyy"


# ----- small field helpers -------------------------------------------------------------------

def to_qdate(value):
    return QDate(value.year, value.month, value.day) if value else QDate.currentDate()


def from_qdate(qdate):
    return date(qdate.year(), qdate.month(), qdate.day())


def make_choice(options, value=None, editable=True):
    """Drop-down with suggestions. Editable, so a new value can simply be typed."""
    box = QComboBox()
    box.setEditable(editable)
    if editable:
        box.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
    box.addItem("")
    box.addItems([option for option in options if option])
    index = box.findText(str(value)) if value else 0
    if index >= 0:
        box.setCurrentIndex(index)
    elif editable:
        box.setCurrentText(str(value))  # a value that is not in the suggestions yet
    return box


def make_date(value=None):
    field = QDateEdit()
    field.setCalendarPopup(True)
    field.setDisplayFormat(DATE_FORMAT)
    field.setDate(to_qdate(value))
    return field


class OptionalDate(QWidget):
    """A date that can be left out: a check box plus a date field."""

    def __init__(self, value=None):
        super().__init__()
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(10)
        self.check = QCheckBox("Set")
        self.field = make_date(value)
        self.field.setEnabled(value is not None)
        self.check.setChecked(value is not None)
        self.check.toggled.connect(self.field.setEnabled)
        row.addWidget(self.check)
        row.addWidget(self.field, 1)

    def value(self):
        return from_qdate(self.field.date()) if self.check.isChecked() else None


class ScoreBox(QComboBox):
    """Whole number 0-10 that can also be 'not set' (a plain drop-down: no typing mistakes possible)."""

    def __init__(self, value=None):
        super().__init__()
        self.addItem("Not set", None)
        for number in range(11):
            self.addItem(str(number), number)
        if value is not None:
            self.setCurrentIndex(self.findData(int(value)))

    def score(self):
        return self.currentData()


class CandidateBox(QComboBox):
    """Candidate drop-down: type a few letters of the name to find the person."""

    def __init__(self, candidates, selected_id=None, locked=False):
        super().__init__()
        self.setEditable(True)
        self.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.addItem("")
        for kursiyer_id, label in candidates:
            self.addItem(label, kursiyer_id)
        completer = QCompleter(self.model(), self)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.setCompleter(completer)
        if selected_id is not None:
            index = self.findData(selected_id)
            if index >= 0:
                self.setCurrentIndex(index)
        self.setEnabled(not locked)

    def candidate_id(self):
        """KursiyerID of the chosen candidate, or None when the text matches nobody."""
        index = self.findText(self.currentText(), Qt.MatchFlag.MatchFixedString)  # ignores letter case
        return self.itemData(index) if index > 0 else None


def make_text(value=None, placeholder="", locked=False):
    field = QLineEdit(value or "")
    field.setPlaceholderText(placeholder)
    field.setEnabled(not locked)
    return field


def make_notes(value=None):
    field = QPlainTextEdit(value or "")
    field.setFixedHeight(96)
    field.setTabChangesFocus(True)
    return field


# ----- base form -----------------------------------------------------------------------------

class FormDialog(QDialog):
    """Pop-up form. Subclasses add fields with ``add_row`` and return them from ``values()``."""

    def __init__(self, parent, title, submit, intro="", width=600):
        super().__init__(parent)
        self.setObjectName("pageRoot")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(width)
        self.submit = submit
        self.saved = False

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 20)
        root.setSpacing(12)
        heading = QLabel(title)
        heading.setObjectName("dialogTitle")
        root.addWidget(heading)
        if intro:
            note = QLabel(intro)
            note.setObjectName("dialogIntro")
            note.setWordWrap(True)
            root.addWidget(note)

        holder = QWidget()
        self.form = QFormLayout(holder)
        self.form.setContentsMargins(0, 6, 8, 6)
        self.form.setHorizontalSpacing(16)
        self.form.setVerticalSpacing(10)
        self.form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(holder)
        root.addWidget(scroll, 1)

        self.labelWarning = QLabel("")
        self.labelWarning.setObjectName("labelWarning")
        self.labelWarning.setWordWrap(True)
        root.addWidget(self.labelWarning)

        buttons = QHBoxLayout()
        buttons.addStretch()
        self.btnCancel = QPushButton("Cancel")
        self.btnCancel.setProperty("variant", "secondary")
        self.btnSave = QPushButton("Save")
        self.btnSave.setIcon(icons.icon("check", "#FFFFFF", 18))
        self.btnSave.setDefault(True)
        self.btnCancel.clicked.connect(self.reject)
        self.btnSave.clicked.connect(self.accept)
        buttons.addWidget(self.btnCancel)
        buttons.addWidget(self.btnSave)
        root.addLayout(buttons)
        self.setStyleSheet(build_stylesheet(THEMES["applications"]))

    def add_row(self, label, widget):
        self.form.addRow(label, widget)
        return widget

    def values(self):
        raise NotImplementedError

    def accept(self):
        try:
            self.submit(self.values())
        except (ValidationError, DatabaseError) as error:
            self.labelWarning.setText(str(error))
            return
        self.saved = True
        super().accept()


# ----- applications --------------------------------------------------------------------------

class ApplicationDialog(FormDialog):
    def __init__(self, parent, store, submit, initial=None):
        self.editing = initial is not None
        initial = initial or {}
        super().__init__(
            parent, "Edit application" if self.editing else "New application", submit,
            "Name and e-mail identify the candidate and cannot be changed here." if self.editing else
            "A candidate who is already registered (same name and e-mail) is reused, not added twice.")
        locked = self.editing
        self.inputName = self.add_row("Full name *", make_text(initial.get("name"), "e.g. Ayse Yilmaz", locked))
        self.inputEmail = self.add_row("E-mail *", make_text(initial.get("email"), "name@example.com", locked))
        self.inputPhone = self.add_row("Phone", make_text(initial.get("phone"), "e.g. 0612345678"))
        self.inputPostal = self.add_row("Postal code", make_text(initial.get("postal_code"), "e.g. 1011AB"))
        self.comboProvince = self.add_row("Province", make_choice(store.application_choices("province"),
                                                                  initial.get("province")))
        periods = store.application_choices("period")
        self.comboPeriod = self.add_row("Application period *", make_choice(
            periods, initial.get("period") or (periods[-1] if periods else "")))
        self.comboStatus = self.add_row("Current status", make_choice(store.application_choices("status"),
                                                                      initial.get("status")))
        self.comboTraining = self.add_row("Desired training", make_choice(store.application_choices("training"),
                                                                          initial.get("training")))
        self.comboEnglish = self.add_row("English level", make_choice(store.application_choices("english"),
                                                                      initial.get("english")))
        self.comboDutch = self.add_row("Dutch level", make_choice(store.application_choices("dutch"),
                                                                  initial.get("dutch")))
        self.comboDepartments = self.add_row("IT department(s)", make_choice(
            store.application_choices("departments"), initial.get("departments")))
        self.inputMotivation = self.add_row("Motivation", make_notes(initial.get("motivation")))
        self.comboMeeting = self.add_row("Mentor meeting", make_choice(store.application_choices("mentor_meeting"),
                                                                       initial.get("mentor_meeting")))
        self.comboProcessing = self.add_row("Processing status", make_choice(
            store.application_choices("processing"), initial.get("processing")))
        self.resize(640, 720)

    def values(self):
        return {
            "name": self.inputName.text(), "email": self.inputEmail.text(),
            "phone": self.inputPhone.text(), "postal_code": self.inputPostal.text(),
            "province": self.comboProvince.currentText(), "period": self.comboPeriod.currentText(),
            "status": self.comboStatus.currentText(), "training": self.comboTraining.currentText(),
            "english": self.comboEnglish.currentText(), "dutch": self.comboDutch.currentText(),
            "departments": self.comboDepartments.currentText(),
            "motivation": self.inputMotivation.toPlainText(),
            "mentor_meeting": self.comboMeeting.currentText(), "processing": self.comboProcessing.currentText(),
        }


# ----- mentor meetings -----------------------------------------------------------------------

class MentorDialog(FormDialog):
    def __init__(self, parent, store, submit, initial=None):
        self.editing = initial is not None
        initial = initial or {}
        super().__init__(
            parent, "Edit mentor meeting" if self.editing else "New mentor meeting", submit,
            "The candidate must already be registered. Add the application first if the name is missing.")
        self.comboCandidate = self.add_row("Candidate *", CandidateBox(
            store.candidates(), initial.get("kursiyer_id"), locked=self.editing))
        self.inputDate = self.add_row("Meeting date *", make_date(initial.get("date")))
        self.comboMentor = self.add_row("Mentor name *", make_choice(store.mentor_choices("mentor"),
                                                                     initial.get("mentor")))
        self.comboScore = self.add_row("Score (0-10)", ScoreBox(initial.get("score")))
        self.comboRecommendation = self.add_row("Recommendation", make_choice(
            store.mentor_choices("recommendation"), initial.get("recommendation")))
        self.inputAlternative = self.add_row("Alternative recommendation", make_text(initial.get("alternative")))
        self.comboSecondary = self.add_row("Secondary score (0-10)", ScoreBox(initial.get("secondary_score")))
        self.inputNotes = self.add_row("Notes", make_notes(initial.get("notes")))
        self.comboGroup = self.add_row("VIT group", make_choice(store.mentor_choices("group"), initial.get("group")))
        self.resize(640, 680)

    def values(self):
        return {
            "kursiyer_id": self.comboCandidate.candidate_id(), "date": from_qdate(self.inputDate.date()),
            "mentor": self.comboMentor.currentText(), "score": self.comboScore.score(),
            "recommendation": self.comboRecommendation.currentText(),
            "alternative": self.inputAlternative.text(), "secondary_score": self.comboSecondary.score(),
            "notes": self.inputNotes.toPlainText(), "group": self.comboGroup.currentText(),
        }


# ----- interviews ----------------------------------------------------------------------------

class InterviewDialog(FormDialog):
    def __init__(self, parent, store, submit, initial=None):
        self.editing = initial is not None
        initial = initial or {}
        super().__init__(
            parent, "Edit interview record" if self.editing else "New interview record", submit,
            "Enter the date the project was sent, the date it came back, or both.")
        self.comboCandidate = self.add_row("Candidate *", CandidateBox(
            store.candidates(), initial.get("kursiyer_id"), locked=self.editing))
        self.inputSent = self.add_row("Project sent", OptionalDate(initial.get("sent")))
        self.inputReceived = self.add_row("Project received", OptionalDate(initial.get("received")))
        self.resize(600, 340)

    def values(self):
        return {"kursiyer_id": self.comboCandidate.candidate_id(), "sent": self.inputSent.value(),
                "received": self.inputReceived.value()}


# ----- users (Admin menu) --------------------------------------------------------------------

class UserDialog(FormDialog):
    """New user: name, password (typed twice) and role."""

    def __init__(self, parent, submit):
        super().__init__(parent, "New user", submit, "Passwords are stored as salted hashes, never as plain text.",
                         width=460)
        self.inputUsername = self.add_row("Username *", make_text(placeholder="no spaces"))
        self.inputPassword = self.add_row("Password *", make_text(placeholder="at least 6 characters"))
        self.inputRepeat = self.add_row("Repeat password *", make_text())
        for field in (self.inputPassword, self.inputRepeat):
            field.setEchoMode(QLineEdit.EchoMode.Password)
        self.comboRole = self.add_row("Role *", QComboBox())
        self.comboRole.addItems(["user", "admin"])
        self.resize(460, 330)

    def values(self):
        if self.inputPassword.text() != self.inputRepeat.text():
            raise ValidationError("The two passwords are not the same.")
        return {"username": self.inputUsername.text(), "password": self.inputPassword.text(),
                "role": self.comboRole.currentText()}


class PasswordDialog(FormDialog):
    """New password for an existing user."""

    def __init__(self, parent, username, submit):
        super().__init__(parent, f"New password for {username}", submit, width=440)
        self.inputPassword = self.add_row("New password *", make_text(placeholder="at least 6 characters"))
        self.inputRepeat = self.add_row("Repeat password *", make_text())
        for field in (self.inputPassword, self.inputRepeat):
            field.setEchoMode(QLineEdit.EchoMode.Password)
        self.resize(440, 260)

    def values(self):
        if self.inputPassword.text() != self.inputRepeat.text():
            raise ValidationError("The two passwords are not the same.")
        return {"password": self.inputPassword.text()}


class UsersDialog(QDialog):
    """All users with Add, Reset password and Delete. ``current_user`` cannot be deleted."""

    HEADERS = ["Username", "Role"]

    def __init__(self, parent, store, current_user=""):
        super().__init__(parent)
        self.store = store
        self.current_user = current_user
        self.setObjectName("pageRoot")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setWindowTitle("Users")
        self.setModal(True)
        self.resize(520, 480)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 20)
        root.setSpacing(12)
        heading = QLabel("Users")
        heading.setObjectName("dialogTitle")
        root.addWidget(heading)
        self.tableUsers = QTableWidget(0, 2)
        style_table(self.tableUsers)
        root.addWidget(self.tableUsers, 1)
        self.labelWarning = QLabel("")
        self.labelWarning.setObjectName("labelWarning")
        self.labelWarning.setWordWrap(True)
        root.addWidget(self.labelWarning)

        buttons = QHBoxLayout()
        self.btnAdd = QPushButton("New user")
        self.btnAdd.setIcon(icons.icon("plus", "#FFFFFF", 18))
        self.btnReset = QPushButton("Reset password")
        self.btnReset.setProperty("variant", "secondary")
        self.btnReset.setIcon(icons.icon("lock", "#334155", 18))
        self.btnDelete = QPushButton("Delete")
        self.btnDelete.setObjectName("btnDelete")
        self.btnDelete.setIcon(icons.icon("trash", "#FFFFFF", 18))
        self.btnClose = QPushButton("Close")
        self.btnClose.setProperty("variant", "secondary")
        for button in (self.btnAdd, self.btnReset, self.btnDelete):
            buttons.addWidget(button)
        buttons.addStretch()
        buttons.addWidget(self.btnClose)
        root.addLayout(buttons)
        self.btnAdd.clicked.connect(self.on_add)
        self.btnReset.clicked.connect(self.on_reset)
        self.btnDelete.clicked.connect(self.on_delete)
        self.btnClose.clicked.connect(self.accept)
        self.setStyleSheet(build_stylesheet(THEMES["admin_menu"]))
        self.reload()

    # these two are replaced in the tests, so no window has to be opened by hand
    def exec_dialog(self, dialog):
        dialog.exec()

    def confirm(self, text):
        return QMessageBox.question(self, "Delete user", text) == QMessageBox.StandardButton.Yes

    def reload(self):
        try:
            rows = [[name, "Administrator" if role == "admin" else "User"]
                    for name, role in self.store.repos.kullanicilar.all_users()]
        except DatabaseError as error:
            self.labelWarning.setText(str(error))
            return
        fill_table(self.tableUsers, self.HEADERS, rows)

    def selected_user(self):
        row = self.tableUsers.currentRow()
        item = self.tableUsers.item(row, 0) if row >= 0 else None
        return item.text() if item else None

    def on_add(self, *_):
        self.labelWarning.setText("")
        dialog = UserDialog(self, lambda v: self.store.records.add_user(v["username"], v["password"], v["role"]))
        self.exec_dialog(dialog)
        if dialog.saved:
            self.reload()

    def on_reset(self, *_):
        name = self.selected_user()
        if not name:
            self.labelWarning.setText("Select a user first.")
            return
        self.labelWarning.setText("")
        dialog = PasswordDialog(self, name, lambda v: self.store.records.reset_password(name, v["password"]))
        self.exec_dialog(dialog)

    def on_delete(self, *_):
        name = self.selected_user()
        if not name:
            self.labelWarning.setText("Select a user first.")
            return
        if not self.confirm(f"Delete the user '{name}'? This cannot be undone."):
            return
        try:
            self.store.records.delete_user(name, self.current_user)
        except (ValidationError, DatabaseError) as error:
            self.labelWarning.setText(str(error))
            return
        self.labelWarning.setText("")
        self.reload()
