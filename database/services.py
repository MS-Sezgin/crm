"""Business rules for adding, changing and deleting records (the write side of the CRM).

``RecordService`` sits between the screens and the repositories. It checks the input,
finds or creates the person behind an application, and groups the statements that belong
together in one transaction. Problems the user can fix raise ``ValidationError`` with a
readable message; the forms show that message and stay open.

Form values arrive as plain dictionaries with short English keys (see the *_FIELDS tables).
"""
import re
from datetime import date, datetime

from database.repositories import CrmRepositories

# Applications of these periods come from the old VIT lists. They are history: the screens
# do not add, change or delete them.
OLD_LIST_PERIODS = ("VIT1", "VIT2")

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_PATTERN = re.compile(r"^[0-9+()\-\s]{6,30}$")
PERIOD_PATTERN = re.compile(r"^[A-Za-z0-9 _-]{1,20}$")
MIN_PASSWORD_LENGTH = 6

# form key -> Basvurular column (the optional free-choice answers of an application)
APPLICATION_FIELDS = {
    "status": "SuAnkiDurum",
    "training": "KatilmakIstenenEgitim",
    "english": "IngilizceSeviye",
    "dutch": "HollandacaSeviye",
    "departments": "ITBolumleri",
    "motivation": "Motivasyon",
    "mentor_meeting": "MentorGorusmesi",
    "processing": "IslemDurumu",
}


class ValidationError(Exception):
    """The input is not acceptable; the message tells the user what to change."""


def clean(value):
    """Text without surrounding blanks and with inner blanks collapsed; "" and None become None."""
    if value is None:
        return None
    text = " ".join(str(value).split())
    return text or None


def clean_multiline(value):
    """Like clean() but keeps the line breaks (motivation texts)."""
    if value is None:
        return None
    text = "\n".join(" ".join(line.split()) for line in str(value).strip().splitlines()).strip()
    return text or None


def require(value, label, minimum=1):
    text = clean(value)
    if not text or len(text) < minimum:
        raise ValidationError(f"{label} is required.")
    return text


def check_score(value, label):
    if value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= 10:
        raise ValidationError(f"{label} must be a whole number from 0 to 10.")
    return value


def check_date(value, label):
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    raise ValidationError(f"{label} is not a valid date.")


class RecordService:
    """Add, change and delete applications, mentor meetings, interviews and users."""

    def __init__(self, repos):
        self.repos = repos
        self.db = repos.db

    # ----- helpers ----------------------------------------------------------------------

    def _person_exists(self, kursiyer_id):
        if not kursiyer_id or self.repos.kursiyerler.get(kursiyer_id) is None:
            raise ValidationError("Choose a candidate from the list.")

    @staticmethod
    def _gone(changed):
        if not changed:
            raise ValidationError("This record no longer exists. Refresh the list and try again.")

    def _check_person(self, form):
        name = require(form.get("name"), "Full name", 2)
        mail = require(form.get("email"), "E-mail")
        if not EMAIL_PATTERN.match(mail):
            raise ValidationError("Enter a valid e-mail address, for example name@example.com.")
        return (name, mail) + self._check_contact(form)

    @staticmethod
    def _check_contact(form):
        phone = clean(form.get("phone"))
        if phone and not PHONE_PATTERN.match(phone):
            raise ValidationError("The phone number may only contain digits, spaces, + - ( ) (6-30 characters).")
        postal = clean(form.get("postal_code"))
        if postal and len(postal) > 10:
            raise ValidationError("The postal code can be 10 characters at most.")
        province = clean(form.get("province"))
        if province and len(province) > 50:
            raise ValidationError("The province can be 50 characters at most.")
        return phone, postal, province

    def _check_application(self, form):
        period = require(form.get("period"), "Application period")
        if not PERIOD_PATTERN.match(period):
            raise ValidationError("The application period may only contain letters, digits, space, _ and -.")
        if period.upper() in OLD_LIST_PERIODS:
            raise ValidationError(f"{period} is an old list that is kept as history. Use a newer period.")
        values = {"BasvuruDonemi": period}
        for key, column in APPLICATION_FIELDS.items():
            raw = form.get(key)
            values[column] = clean_multiline(raw) if key == "motivation" else clean(raw)
        return values

    # ----- applications -----------------------------------------------------------------

    def add_application(self, form):
        """Add an application. The person is found by name + e-mail (accents and letter case are
        ignored) and created when new; a known person only gets empty contact fields filled in.

        Returns (BasvuruID, KursiyerID, is_new_person, earlier_applications)."""
        name, mail, phone, postal, province = self._check_person(form)
        values = self._check_application(form)
        values["ZamanDamgasi"] = datetime.now().replace(microsecond=0)
        people, applications = self.repos.kursiyerler, self.repos.basvurular
        with self.db.transaction():
            person = people.find(name, mail)
            is_new = person is None
            if is_new:
                person = people.add(name, mail, phone, postal, province)
                earlier = 0
            else:
                people.fill_missing(person, phone, postal, province)
                earlier = self.db.fetch_value(
                    "SELECT count(*) FROM Basvurular WHERE KursiyerID = %s AND BasvuruDonemi <> ALL(%s)",
                    (person, list(OLD_LIST_PERIODS)))
            application = applications.add(person, values)
        return application, person, is_new, earlier

    def get_application(self, basvuru_id):
        """The values of one application in form shape, or None."""
        row = self.repos.basvurular.get(basvuru_id)
        if row is None:
            return None
        person = self.repos.kursiyerler.get(row["KursiyerID"])
        form = {"name": person["AdSoyad"], "email": person["MailAdresi"],
                "phone": person["TelefonNumarasi"], "postal_code": person["PostaKodu"],
                "province": person["YasadiginizEyalet"], "period": row["BasvuruDonemi"]}
        for key, column in APPLICATION_FIELDS.items():
            form[key] = row[column]
        return form

    def update_application(self, basvuru_id, form):
        """Change one application and the contact fields of its person (name and e-mail stay)."""
        current = self.repos.basvurular.get(basvuru_id)
        self._gone(current)
        phone, postal, province = self._check_contact(form)
        values = self._check_application(form)
        with self.db.transaction():
            self.repos.basvurular.update(basvuru_id, values)
            self.repos.kursiyerler.update_contact(current["KursiyerID"], phone, postal, province)

    def delete_application(self, basvuru_id):
        """Delete an application. The person is removed too when nothing else refers to them.
        Returns True when the person was removed as well."""
        current = self.repos.basvurular.get(basvuru_id)
        self._gone(current)
        with self.db.transaction():
            self._gone(self.repos.basvurular.delete(basvuru_id))
            return self.repos.kursiyerler.delete_if_unused(current["KursiyerID"])

    # ----- mentor meetings --------------------------------------------------------------

    def _check_meeting(self, form):
        self._person_exists(form.get("kursiyer_id"))
        meeting_date = check_date(form.get("date"), "Meeting date")
        if meeting_date is None:
            raise ValidationError("Meeting date is required.")
        return {
            "KursiyerID": form["kursiyer_id"],
            "GorusmeTarihi": meeting_date,
            "MentorAdSoyad": require(form.get("mentor"), "Mentor name", 2),
            "BilgiSahibiMi": check_score(form.get("score"), "Score"),
            "VITProjesineKatilabilirMi": clean(form.get("recommendation")),
            "Dusunce": clean(form.get("alternative")),
            "YogunlukDurumu": check_score(form.get("secondary_score"), "Secondary score"),
            "Yorumlar": clean_multiline(form.get("notes")),
            "VITGrubu": clean(form.get("group")),
        }

    def add_mentor_meeting(self, form):
        v = self._check_meeting(form)
        return self.repos.mentor.add(
            v["KursiyerID"], v["GorusmeTarihi"], v["MentorAdSoyad"], v["BilgiSahibiMi"],
            v["VITProjesineKatilabilirMi"], v["Dusunce"], v["YogunlukDurumu"], v["Yorumlar"], v["VITGrubu"])

    def get_mentor_meeting(self, mentor_id):
        row = self.repos.mentor.get(mentor_id)
        if row is None:
            return None
        return {"kursiyer_id": row["KursiyerID"], "date": row["GorusmeTarihi"], "mentor": row["MentorAdSoyad"],
                "score": row["BilgiSahibiMi"], "recommendation": row["VITProjesineKatilabilirMi"],
                "alternative": row["Dusunce"], "secondary_score": row["YogunlukDurumu"],
                "notes": row["Yorumlar"], "group": row["VITGrubu"]}

    def update_mentor_meeting(self, mentor_id, form):
        self._gone(self.repos.mentor.get(mentor_id))
        self._gone(self.repos.mentor.update(mentor_id, self._check_meeting(form)))

    def delete_mentor_meeting(self, mentor_id):
        """Returns True when the candidate was removed as well (nothing else referred to them)."""
        current = self.repos.mentor.get(mentor_id)
        self._gone(current)
        with self.db.transaction():
            self._gone(self.repos.mentor.delete(mentor_id))
            return self.repos.kursiyerler.delete_if_unused(current["KursiyerID"])

    # ----- interviews (project sent / received) -----------------------------------------

    def _check_interview(self, form):
        self._person_exists(form.get("kursiyer_id"))
        sent = check_date(form.get("sent"), "Project sent date")
        received = check_date(form.get("received"), "Project received date")
        if sent is None and received is None:
            raise ValidationError("Enter at least one date: project sent or project received.")
        if sent and received and received < sent:
            raise ValidationError("The project cannot be received before it was sent.")
        return {"KursiyerID": form["kursiyer_id"], "ProjeGonderilisTarihi": sent, "ProjeninGelisTarihi": received}

    def add_interview(self, form):
        v = self._check_interview(form)
        return self.repos.mulakatlar.add(v["KursiyerID"], v["ProjeGonderilisTarihi"], v["ProjeninGelisTarihi"])

    def get_interview(self, mulakat_id):
        row = self.repos.mulakatlar.get(mulakat_id)
        if row is None:
            return None
        return {"kursiyer_id": row["KursiyerID"], "sent": row["ProjeGonderilisTarihi"],
                "received": row["ProjeninGelisTarihi"]}

    def update_interview(self, mulakat_id, form):
        self._gone(self.repos.mulakatlar.get(mulakat_id))
        self._gone(self.repos.mulakatlar.update(mulakat_id, self._check_interview(form)))

    def delete_interview(self, mulakat_id):
        current = self.repos.mulakatlar.get(mulakat_id)
        self._gone(current)
        with self.db.transaction():
            self._gone(self.repos.mulakatlar.delete(mulakat_id))
            return self.repos.kursiyerler.delete_if_unused(current["KursiyerID"])

    # ----- users ------------------------------------------------------------------------

    @staticmethod
    def _check_password(password):
        if password is None or len(password) < MIN_PASSWORD_LENGTH:
            raise ValidationError(f"The password needs at least {MIN_PASSWORD_LENGTH} characters.")
        return password

    def add_user(self, username, password, role):
        name = require(username, "Username", 2)
        if len(name) > 50 or " " in name:
            raise ValidationError("The username has no spaces and is 50 characters at most.")
        if role not in ("admin", "user"):
            raise ValidationError("Choose a role: admin or user.")
        self._check_password(password)
        if self.repos.kullanicilar.exists(name):
            raise ValidationError(f"The username '{name}' is already taken.")
        self.repos.kullanicilar.add(name, password, role)

    def reset_password(self, username, password):
        self._check_password(password)
        self._gone(self.repos.kullanicilar.set_password(username, password))

    def delete_user(self, username, acting_user):
        """Delete a user. Nobody can delete their own account, and the last admin always stays."""
        if clean(username) and clean(acting_user) and username.strip().lower() == acting_user.strip().lower():
            raise ValidationError("You cannot delete the account you are signed in with.")
        role = self.repos.kullanicilar.role_of(username)
        if role is None:
            raise ValidationError("This user no longer exists. Refresh the list and try again.")
        if role == "admin" and self.repos.kullanicilar.count_admins() <= 1:
            raise ValidationError("The last administrator cannot be deleted.")
        self.repos.kullanicilar.delete_user(username)


def make_service(db):
    """A RecordService on its own repositories (handy for scripts and tests)."""
    return RecordService(CrmRepositories(db))
