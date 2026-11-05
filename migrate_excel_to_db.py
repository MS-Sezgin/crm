"""One-time migration: Excel files -> PostgreSQL.

    python migrate_excel_to_db.py --create-schema          first load into an empty database
    python migrate_excel_to_db.py --dry-run                try everything, then roll back
    python migrate_excel_to_db.py --truncate               empty the tables and load again

What it does
  * Reads Applications, Interviews, Mentor, Users (and VIT1 / VIT2 when present) from data/.
    The Excel files are only read, never changed; a copy goes to data_backup/ first.
  * One person = one Kursiyerler row (identified by name + e-mail).
  * Every application row is kept (VIT1 / VIT2 rows get BasvuruDonemi = "VIT1" / "VIT2").
  * Mentor and interview rows are linked to the trainee by name. A name that matches no
    trainee, or more than one, stops the migration with a list (or is skipped and listed
    in the report when --skip-unmatched is given).
  * Passwords are stored as hashes.
  * Everything runs in ONE transaction. Row counts are compared with the Excel files at the
    end; if anything differs, nothing is saved.
  * A text report (migration_report.txt) lists counts, conflicts, shared e-mails and skipped rows.
"""
import argparse
import os
import shutil
import sys
from collections import Counter
from datetime import date, datetime

from openpyxl import load_workbook

from database import ConfigError, CrmRepositories, Database, DatabaseError, DbConfig
from database.text_utils import normalize
from paths import app_dir

APPLICATIONS_FILE = "Applications.xlsx"
INTERVIEWS_FILE = "Interviews.xlsx"
MENTOR_FILE = "Mentor.xlsx"
USERS_FILE = "Users.xlsx"
VIT_FILES = ("VIT1.xlsx", "VIT2.xlsx")
SCHEMA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "database", "schema.sql")

# logical field -> accepted header names (written without accents and in lower case)
APPLICATION_SPEC = {
    "timestamp": ("timestamp", "zaman damgasi"),
    "name": ("full name", "adiniz soyadiniz", "ad soyad"),
    "email": ("email", "mail adresiniz"),
    "phone": ("phone", "telefon numaraniz"),
    "postal": ("postal code", "posta kodunuz"),
    "province": ("province", "yasadiginiz eyalet"),
    "current_status": ("current status", "su anki durumunuz"),
    "desired_training": ("desired training",),
    "financial": ("financial situation", "ekonomik durumunuz"),
    "language_course": ("currently in a language course",),
    "english": ("english level",),
    "dutch": ("dutch level",),
    "municipal": ("municipal pressure regarding work",),
    "bootcamp": ("completed another it bootcamp",),
    "online_course": ("followed an online it course",),
    "it_experience": ("prior it work experience",),
    "other_project": ("currently involved in another project",),
    "departments": ("desired it department(s)",),
    "reasons": ("reasons for applying to vit",),
    "motivation": ("motivation", "motivasyon"),
    "mentor_meeting": ("mentor meeting", "mentor gorusmesi"),
    "period": ("application period", "basvuru donemi"),
    "green_check": ("green check", "yesil tik olan"),
    "tracking1": ("internal tracking 1",),
    "tracking2": ("internal tracking 2",),
    "tracking3": ("internal tracking 3",),
    "status": ("processing status",),
}
APPLICATION_REQUIRED = ("name", "email", "period")

VIT_SPEC = {
    "period": ("vit group", "vit grubu"),
    "name": ("full name", "adiniz soyadiniz", "ad soyad"),
    "email": ("email", "mail adresiniz"),
    "phone": ("phone", "telefon numaraniz"),
    "province": ("province", "yasadiginiz eyalet"),
    "departments": ("desired it department(s)",),
    "status": ("processing status",),
}
VIT_REQUIRED = ("period", "name", "email")

INTERVIEW_SPEC = {
    "name": ("full name", "adiniz soyadiniz", "ad soyad"),
    "sent": ("project sent date", "proje gonderilis tarihi"),
    "received": ("project received date", "projenin gelis tarihi"),
}
INTERVIEW_REQUIRED = ("name",)

MENTOR_SPEC = {
    "date": ("date", "gorusme tarihi"),
    "vit_group": ("vit group", "vit grubu"),
    "candidate": ("candidate name", "kursiyer", "adiniz soyadiniz"),
    "mentor": ("mentor name", "mentor ad soyad", "mentoradsoyad"),
    "score": ("score",),
    "recommendation": ("recommendation",),
    "alternative": ("alternative recommendation",),
    "secondary": ("secondary score",),
    "notes": ("notes", "yorumlar"),
}
MENTOR_REQUIRED = ("candidate",)

USER_SPEC = {
    "user": ("username", "kullanici"),
    "password": ("password", "parola"),
    "role": ("role", "yetki", "authority"),
}
USER_REQUIRED = ("user", "password", "role")

TIMESTAMP_FORMATS = ("%m/%d/%Y %H:%M", "%m/%d/%Y %H:%M:%S", "%m/%d/%Y", "%Y-%m-%d %H:%M:%S",
                     "%Y-%m-%d %H:%M", "%Y-%m-%d", "%d.%m.%Y %H:%M", "%d.%m.%Y")


class MigrationError(Exception):
    """A problem in the data or the setup that stops the migration."""


class DryRunDone(Exception):
    """Raised on purpose at the end of a dry run, so the transaction is rolled back."""


# ----- converting Excel cell values ---------------------------------------------------

def to_text(value):
    """Cell -> trimmed text, or None for an empty cell. 5551234.0 becomes '5551234'."""
    if value is None:
        return None
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    text = str(value).strip()
    return text or None


def to_datetime(value):
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day)
    text = str(value).strip()
    for pattern in TIMESTAMP_FORMATS:
        try:
            return datetime.strptime(text, pattern)
        except ValueError:
            continue
    raise ValueError(f"unreadable date/time '{text}'")


def to_date(value):
    moment = to_datetime(value)
    return moment.date() if moment else None


def to_int(value):
    text = to_text(value)
    if text is None:
        return None
    try:
        return int(float(text))
    except ValueError as error:
        raise ValueError(f"'{text}' is not a number") from error


def to_number(value):
    text = to_text(value)
    if text is None:
        return None
    try:
        return float(text)
    except ValueError as error:
        raise ValueError(f"'{text}' is not a number") from error


# ----- reading Excel ------------------------------------------------------------------

class Record:
    """One Excel data row: its line number in the file and its values by logical field."""

    def __init__(self, line, values):
        self.line = line
        self.values = values


class ExcelSheet:
    def __init__(self, file_name, headers, rows):
        self.file_name = file_name
        self.headers = headers
        self.rows = rows  # list of (line number, list of cell values)

    @classmethod
    def load(cls, folder, file_name):
        path = os.path.join(folder, file_name)
        if not os.path.exists(path):
            raise FileNotFoundError(f"{file_name} was not found in {folder}")
        workbook = load_workbook(path, read_only=True, data_only=True)
        try:
            raw = [(number, list(row)) for number, row in
                   enumerate(workbook.worksheets[0].iter_rows(values_only=True), start=1)]
        finally:
            workbook.close()
        raw = [(n, row) for n, row in raw if any(v not in (None, "") for v in row)]
        if not raw:
            raise MigrationError(f"{file_name} is empty.")
        headers = [str(h).strip() if h not in (None, "") else f"Column {i + 1}"
                   for i, h in enumerate(raw[0][1])]
        return cls(file_name, headers, raw[1:])

    def records(self, spec, required):
        """Rows as Record objects with values by logical field name."""
        normalized = [normalize(h) for h in self.headers]
        index = {}
        for field, aliases in spec.items():
            index[field] = next((i for i, h in enumerate(normalized) if h in aliases), None)
        missing = [field for field in required if index[field] is None]
        if missing:
            wanted = "; ".join(f"{f}: {' / '.join(spec[f])}" for f in missing)
            raise MigrationError(
                f"{self.file_name}: column(s) not found -> {wanted}. "
                f"Columns in the file: {', '.join(self.headers)}")
        records = []
        for number, row in self.rows:
            values = {field: (row[i] if i is not None and i < len(row) else None)
                      for field, i in index.items()}
            records.append(Record(number, values))
        return records

    def __len__(self):
        return len(self.rows)


# ----- report -------------------------------------------------------------------------

class MigrationReport:
    def __init__(self):
        self.notes = []       # information only
        self.conflicts = []   # same person, different contact data
        self.skipped = []     # rows left out on request (--skip-unmatched)
        self.warnings = []

    def write(self, path, header_lines, table_rows):
        lines = ["CRM Excel -> PostgreSQL migration report",
                 f"Created: {datetime.now():%Y-%m-%d %H:%M:%S}", ""]
        lines += header_lines
        lines += ["", f"{'Table':16} {'Excel expected':>15} {'Database':>10}"]
        lines += [f"{name:16} {expected:>15} {actual:>10}" for name, expected, actual in table_rows]
        for title, items in (("Contact data conflicts (first value kept)", self.conflicts),
                             ("Skipped rows", self.skipped),
                             ("Warnings", self.warnings),
                             ("Notes", self.notes)):
            lines += ["", f"{title}: {len(items)}"]
            lines += [f"  - {item}" for item in items]
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("\n".join(lines) + "\n")


# ----- the migrator -------------------------------------------------------------------

class ExcelMigrator:
    def __init__(self, db, data_dir, report_path=None, skip_unmatched=False):
        self.db = db
        self.repos = CrmRepositories(db)
        self.data_dir = data_dir
        self.report_path = report_path or os.path.join(app_dir(), "migration_report.txt")
        self.skip_unmatched = skip_unmatched
        self.report = MigrationReport()
        self.unmatched = []        # (file, line, name, reason)
        self.skipped_mentor = 0
        self.skipped_interviews = 0
        self._expected_after_skip = {}

    def run(self, truncate=False, dry_run=False, create_schema=False):
        sheets = self._read_excel_files()          # nothing is written before the files are valid
        if not dry_run:
            self._backup_files(sheets)
        expected = self._expected_counts(sheets)
        try:
            with self.db.transaction():
                self._prepare_tables(truncate, create_schema)
                self._load_users(sheets["users"])
                self._load_applications(sheets["applications"])
                for sheet in sheets["vit"]:
                    self._load_vit(sheet)
                self._load_interviews(sheets["interviews"])
                self._load_mentor(sheets["mentor"])
                self._check_unmatched()
                self._add_informational_notes(sheets["applications"])
                actual = self.repos.counts()
                self._verify(expected, actual, sheets)
                self._write_report(actual, dry_run)
                if dry_run:
                    raise DryRunDone()
        except DryRunDone:
            return expected, actual, True
        return expected, actual, False

    # ----- steps ------------------------------------------------------------------

    def _read_excel_files(self):
        sheets = {
            "applications": ExcelSheet.load(self.data_dir, APPLICATIONS_FILE),
            "interviews": ExcelSheet.load(self.data_dir, INTERVIEWS_FILE),
            "mentor": ExcelSheet.load(self.data_dir, MENTOR_FILE),
            "users": ExcelSheet.load(self.data_dir, USERS_FILE),
            "vit": [],
        }
        for name in VIT_FILES:
            if os.path.exists(os.path.join(self.data_dir, name)):
                sheets["vit"].append(ExcelSheet.load(self.data_dir, name))
            else:
                self.report.warnings.append(f"{name} was not found and was skipped (optional file).")
        return sheets

    def _backup_files(self, sheets):
        folder = os.path.join(app_dir(), "data_backup", datetime.now().strftime("%Y%m%d_%H%M%S"))
        os.makedirs(folder, exist_ok=True)
        names = [sheets[k].file_name for k in ("applications", "interviews", "mentor", "users")]
        names += [s.file_name for s in sheets["vit"]]
        for name in names:
            shutil.copy2(os.path.join(self.data_dir, name), folder)
        self.report.notes.append(f"Excel files copied to {folder} before loading.")

    def _prepare_tables(self, truncate, create_schema):
        if not self.db.table_exists("Kursiyerler"):
            if not create_schema:
                raise MigrationError("The tables do not exist yet. Run once with --create-schema "
                                     "(or run database/schema.sql yourself).")
            self.db.execute_script(SCHEMA_FILE)
            self.report.notes.append("Tables created from database/schema.sql.")
        counts = self.repos.counts()
        if any(counts.values()):
            if not truncate:
                filled = ", ".join(f"{k}={v}" for k, v in counts.items() if v)
                raise MigrationError(f"The database already has data ({filled}). "
                                     "Use --truncate to empty the tables and load again.")
            self.db.execute("TRUNCATE Mulakatlar, Mentortablosu, Basvurular, Kullanicilar, "
                            "Kursiyerler RESTART IDENTITY CASCADE")
            self.report.notes.append("Existing table content was removed (--truncate).")

    def _load_users(self, sheet):
        seen = set()
        for rec in sheet.records(USER_SPEC, USER_REQUIRED):
            v = rec.values
            name, password, role = to_text(v["user"]), to_text(v["password"]), to_text(v["role"])
            if not name or not password:
                raise MigrationError(f"{sheet.file_name} row {rec.line}: username and password are required.")
            if normalize(name) in seen:
                raise MigrationError(f"{sheet.file_name} row {rec.line}: username '{name}' appears twice.")
            seen.add(normalize(name))
            self._insert(self.repos.kullanicilar.add, sheet, rec,
                         name, password, "admin" if "admin" in normalize(role) else "user")

    def _load_applications(self, sheet):
        for rec in sheet.records(APPLICATION_SPEC, APPLICATION_REQUIRED):
            v = rec.values
            kursiyer_id = self._person(sheet.file_name, rec.line, v["name"], v["email"],
                                       v["phone"], v["postal"], v["province"])
            period = to_text(v["period"])
            if not period:
                raise MigrationError(f"{sheet.file_name} row {rec.line}: Application Period is empty.")
            try:
                values = {
                    "ZamanDamgasi": to_datetime(v["timestamp"]),
                    "SuAnkiDurum": to_text(v["current_status"]),
                    "KatilmakIstenenEgitim": to_text(v["desired_training"]),
                    "EkonomikDurum": to_text(v["financial"]),
                    "DilKursunaDevamEdiyorMu": to_text(v["language_course"]),
                    "IngilizceSeviye": to_text(v["english"]),
                    "HollandacaSeviye": to_text(v["dutch"]),
                    "BelediyeBaskisi": to_text(v["municipal"]),
                    "BaskaITKursuBitirdiMi": to_text(v["bootcamp"]),
                    "OnlineITKursuTakipEttiMi": to_text(v["online_course"]),
                    "ITIsTecrubesi": to_text(v["it_experience"]),
                    "BaskaProjedeMi": to_text(v["other_project"]),
                    "ITBolumleri": to_text(v["departments"]),
                    "VITNedenleri": to_text(v["reasons"]),
                    "Motivasyon": to_text(v["motivation"]),
                    "MentorGorusmesi": to_text(v["mentor_meeting"]),
                    "BasvuruDonemi": period,
                    "YesilTikOlan": to_text(v["green_check"]),
                    "DahiliTakip1": to_number(v["tracking1"]),
                    "DahiliTakip2": to_number(v["tracking2"]),
                    "DahiliTakip3": to_number(v["tracking3"]),
                    "IslemDurumu": to_text(v["status"]),
                }
            except ValueError as error:
                raise MigrationError(f"{sheet.file_name} row {rec.line}: {error}") from error
            self._insert(self.repos.basvurular.add, sheet, rec, kursiyer_id, values)

    def _load_vit(self, sheet):
        for rec in sheet.records(VIT_SPEC, VIT_REQUIRED):
            v = rec.values
            kursiyer_id = self._person(sheet.file_name, rec.line, v["name"], v["email"],
                                       v["phone"], None, v["province"])
            values = {"BasvuruDonemi": to_text(v["period"]),
                      "ITBolumleri": to_text(v["departments"]),
                      "IslemDurumu": to_text(v["status"])}
            if not values["BasvuruDonemi"]:
                raise MigrationError(f"{sheet.file_name} row {rec.line}: VIT Group is empty.")
            self._insert(self.repos.basvurular.add, sheet, rec, kursiyer_id, values)

    def _load_interviews(self, sheet):
        for rec in sheet.records(INTERVIEW_SPEC, INTERVIEW_REQUIRED):
            kursiyer_id = self._find_trainee(sheet.file_name, rec.line, rec.values["name"])
            if kursiyer_id is None:
                self.skipped_interviews += 1
                continue
            try:
                sent, received = to_date(rec.values["sent"]), to_date(rec.values["received"])
            except ValueError as error:
                raise MigrationError(f"{sheet.file_name} row {rec.line}: {error}") from error
            self._insert(self.repos.mulakatlar.add, sheet, rec, kursiyer_id, sent, received)

    def _load_mentor(self, sheet):
        for rec in sheet.records(MENTOR_SPEC, MENTOR_REQUIRED):
            v = rec.values
            kursiyer_id = self._find_trainee(sheet.file_name, rec.line, v["candidate"])
            if kursiyer_id is None:
                self.skipped_mentor += 1
                continue
            try:
                kwargs = dict(
                    gorusme_tarihi=to_date(v["date"]), mentor_adsoyad=to_text(v["mentor"]),
                    bilgi_sahibi=to_int(v["score"]), vit_katilabilir=to_text(v["recommendation"]),
                    dusunce=to_text(v["alternative"]), yogunluk=to_int(v["secondary"]),
                    yorumlar=to_text(v["notes"]), vit_grubu=to_text(v["vit_group"]))
            except ValueError as error:
                raise MigrationError(f"{sheet.file_name} row {rec.line}: {error}") from error
            self._insert(self.repos.mentor.add, sheet, rec, kursiyer_id, **kwargs)

    # ----- helpers ----------------------------------------------------------------

    def _insert(self, method, sheet, rec, *args, **kwargs):
        """Run one INSERT; a database error is reported with the file and row."""
        try:
            return method(*args, **kwargs)
        except DatabaseError as error:
            raise MigrationError(f"{sheet.file_name} row {rec.line}: {error}") from error

    def _person(self, source, line, name, mail, phone, postal, province):
        """Find the trainee (name + e-mail) or create it. Keeps the first contact data."""
        name, mail = to_text(name), to_text(mail)
        if not name or not mail:
            raise MigrationError(f"{source} row {line}: name and e-mail are both required.")
        phone, postal, province = to_text(phone), to_text(postal), to_text(province)
        repo = self.repos.kursiyerler
        try:
            kursiyer_id = repo.find(name, mail)
            if kursiyer_id is None:
                return repo.add(name, mail, phone, postal, province)
            current = repo.contact(kursiyer_id)
            for label, old, new in zip(("phone", "postal code", "province"), current,
                                       (phone, postal, province)):
                if old and new and self._clean_compare(label, old) != self._clean_compare(label, new):
                    self.report.conflicts.append(
                        f"{name} <{mail}>: {label} is '{old}' but {source} row {line} says '{new}'. "
                        "The first value was kept.")
            repo.fill_missing(kursiyer_id, phone, postal, province)
            return kursiyer_id
        except DatabaseError as error:
            raise MigrationError(f"{source} row {line}: {error}") from error

    @staticmethod
    def _clean_compare(label, value):
        if label == "phone":
            return "".join(ch for ch in value if ch.isdigit())
        return normalize(value).replace(" ", "")

    def _find_trainee(self, source, line, name):
        name = to_text(name)
        if not name:
            self.unmatched.append((source, line, "(empty)", "no name"))
            return None
        ids = self.repos.kursiyerler.find_by_name(name)
        if len(ids) == 1:
            return ids[0]
        reason = "no trainee with this name" if not ids else f"{len(ids)} trainees share this name"
        self.unmatched.append((source, line, name, reason))
        return None

    def _check_unmatched(self):
        if not self.unmatched:
            return
        if not self.skip_unmatched:
            listing = "\n".join(f"  {f} row {n}: '{name}' ({why})" for f, n, name, why in self.unmatched)
            raise MigrationError(
                f"{len(self.unmatched)} row(s) could not be linked to a trainee:\n{listing}\n"
                "Fix the names in the Excel file, or use --skip-unmatched to leave them out "
                "(they will be listed in the report).")
        for f, n, name, why in self.unmatched:
            self.report.skipped.append(f"{f} row {n}: '{name}' ({why})")

    def _add_informational_notes(self, applications):
        rows = Counter(tuple(to_text(c) for c in row) for _, row in applications.rows)
        extra = sum(count - 1 for count in rows.values() if count > 1)
        self.report.notes.append(
            f"{extra} application row(s) are exact copies of another row; they were kept "
            "(the 'Duplicate Records' filter needs them).")
        for mail, names, phones in self.repos.kursiyerler.shared_emails():
            hint = (" (same phone number: possibly the same person with a typo, please check)"
                    if phones <= 1 else " (different phone numbers: probably different people)")
            self.report.notes.append(f"E-mail {mail} is used by: {names}{hint}")

    # ----- verification -----------------------------------------------------------

    def _expected_counts(self, sheets):
        people = set()
        for rec in sheets["applications"].records(APPLICATION_SPEC, APPLICATION_REQUIRED):
            people.add((normalize(rec.values["name"]), normalize(rec.values["email"])))
        for sheet in sheets["vit"]:
            for rec in sheet.records(VIT_SPEC, VIT_REQUIRED):
                people.add((normalize(rec.values["name"]), normalize(rec.values["email"])))
        return {
            "Kursiyerler": len(people),
            "Basvurular": len(sheets["applications"]) + sum(len(s) for s in sheets["vit"]),
            "Mentortablosu": len(sheets["mentor"]),
            "Mulakatlar": len(sheets["interviews"]),
            "Kullanicilar": len(sheets["users"]),
        }

    def _verify(self, expected, actual, sheets):
        expected = dict(expected)
        if self.skip_unmatched:
            expected["Mentortablosu"] -= self.skipped_mentor
            expected["Mulakatlar"] -= self.skipped_interviews
        self._expected_after_skip = expected
        wrong = [f"{t}: Excel {expected[t]}, database {actual[t]}" for t in expected
                 if expected[t] != actual[t]]
        if wrong:
            raise MigrationError("Row counts do not match, nothing was saved:\n  " + "\n  ".join(wrong))
        periods = self.repos.basvurular.count_by_period()
        in_excel = Counter()
        for rec in sheets["applications"].records(APPLICATION_SPEC, APPLICATION_REQUIRED):
            in_excel[to_text(rec.values["period"])] += 1
        for sheet in sheets["vit"]:
            for rec in sheet.records(VIT_SPEC, VIT_REQUIRED):
                in_excel[to_text(rec.values["period"])] += 1
        if dict(in_excel) != periods:
            raise MigrationError(f"Application counts per period differ: Excel {dict(in_excel)}, "
                                 f"database {periods}. Nothing was saved.")

    def _write_report(self, actual, dry_run):
        rows = [(t, self._expected_after_skip[t], actual[t]) for t in actual]
        header = ["Mode: DRY RUN (everything was rolled back)" if dry_run
                  else "Mode: data saved to the database",
                  f"Data folder: {self.data_dir}",
                  f"Applications per period: {self.repos.basvurular.count_by_period()}"]
        self.report.write(self.report_path, header, rows)


# ----- command line -------------------------------------------------------------------

def main(argv=None):
    parser = argparse.ArgumentParser(description="Load the Excel data into PostgreSQL (one time).")
    parser.add_argument("--data-dir", default=os.environ.get("CRM_DATA_DIR", os.path.join(app_dir(), "data")))
    parser.add_argument("--create-schema", action="store_true", help="create the tables from database/schema.sql")
    parser.add_argument("--truncate", action="store_true", help="empty the tables before loading")
    parser.add_argument("--dry-run", action="store_true", help="do everything, then roll back")
    parser.add_argument("--skip-unmatched", action="store_true",
                        help="leave out mentor/interview rows whose name matches no trainee")
    parser.add_argument("--report", default=None, help="path of the report file")
    args = parser.parse_args(argv)

    try:
        config = DbConfig.load()
        with Database(config) as db:
            migrator = ExcelMigrator(db, args.data_dir, args.report, args.skip_unmatched)
            expected, actual, dry = migrator.run(args.truncate, args.dry_run, args.create_schema)
    except (ConfigError, DatabaseError, MigrationError, FileNotFoundError) as error:
        print(f"ERROR: {error}")
        return 1

    print("DRY RUN finished, nothing was saved." if dry else "Migration finished, data saved.")
    for table, count in actual.items():
        print(f"  {table:15} {count:>4}")
    print(f"Report: {migrator.report_path}")
    for line in migrator.report.skipped + migrator.report.conflicts:
        print("  !", line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
