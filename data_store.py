"""Data access for the CRM pages, backed by PostgreSQL.

``DataStore`` is the only class the pages talk to. Every list the pages show comes from
an SQL query (search, filters, duplicate checks included). Each method returns
``(headers, rows)``: header names plus rows of plain text, ready for the tables.

The column names shown in the tables are the same English names the Excel files had,
so the screens look exactly as before.

Applications from the old VIT lists (VIT1, VIT2) live in the same Basvurular table as the
form applications. They are told apart by the application period: the periods listed in
PAST_PERIODS are the old lists. "All Applications" and the mentor-meeting filters show the
form applications only (as the old Applications.xlsx did); "Previous VIT Check" and
"Different Record" use all of them.
"""
from datetime import date, datetime
from decimal import Decimal

from database import CrmRepositories

PAST_PERIODS = ["VIT1", "VIT2"]
CALENDAR_COLUMNS = ["Activity Name", "Start Time", "Participant Mail", "Organizer Mail"]
PEOPLE_HEADERS = ["Full Name", "Email", "Found In"]

# (header shown in the table, SQL expression) in the order of the old Applications.xlsx
APPLICATION_COLUMNS = [
    ("Timestamp", "b.ZamanDamgasi"),
    ("Full Name", "k.AdSoyad"),
    ("Email", "k.MailAdresi"),
    ("Phone", "k.TelefonNumarasi"),
    ("Postal Code", "k.PostaKodu"),
    ("Province", "k.YasadiginizEyalet"),
    ("Current Status", "b.SuAnkiDurum"),
    ("Desired Training", "b.KatilmakIstenenEgitim"),
    ("Financial Situation", "b.EkonomikDurum"),
    ("Currently in a Language Course", "b.DilKursunaDevamEdiyorMu"),
    ("English Level", "b.IngilizceSeviye"),
    ("Dutch Level", "b.HollandacaSeviye"),
    ("Municipal Pressure Regarding Work", "b.BelediyeBaskisi"),
    ("Completed Another IT Bootcamp", "b.BaskaITKursuBitirdiMi"),
    ("Followed an Online IT Course", "b.OnlineITKursuTakipEttiMi"),
    ("Prior IT Work Experience", "b.ITIsTecrubesi"),
    ("Currently Involved in Another Project", "b.BaskaProjedeMi"),
    ("Desired IT Department(s)", "b.ITBolumleri"),
    ("Reasons for Applying to VIT", "b.VITNedenleri"),
    ("Motivation", "b.Motivasyon"),
    ("Mentor Meeting", "b.MentorGorusmesi"),
    ("Application Period", "b.BasvuruDonemi"),
    ("Green Check", "b.YesilTikOlan"),
    ("Internal Tracking 1", "b.DahiliTakip1"),
    ("Internal Tracking 2", "b.DahiliTakip2"),
    ("Internal Tracking 3", "b.DahiliTakip3"),
    ("Processing Status", "b.IslemDurumu"),
]
MENTOR_COLUMNS = [
    ("Date", "m.GorusmeTarihi"),
    ("VIT Group", "m.VITGrubu"),
    ("Candidate Name", "k.AdSoyad"),
    ("Mentor Name", "m.MentorAdSoyad"),
    ("Score", "m.BilgiSahibiMi"),
    ("Recommendation", "m.VITProjesineKatilabilirMi"),
    ("Alternative Recommendation", "m.Dusunce"),
    ("Secondary Score", "m.YogunlukDurumu"),
    ("Notes", "m.Yorumlar"),
]
INTERVIEW_COLUMNS = [
    ("Full Name", "k.AdSoyad"),
    ("Project Sent Date", "u.ProjeGonderilisTarihi"),
    ("Project Received Date", "u.ProjeninGelisTarihi"),
]

# ----- helpers ------------------------------------------------------------------------

_ESCAPE = "!"


def cell_text(value):
    """One database value as table text (empty cell for NULL, dd.mm.yyyy for dates)."""
    if value is None:
        return ""
    if isinstance(value, datetime):
        if value.hour == 0 and value.minute == 0:
            return value.strftime("%d.%m.%Y")
        return value.strftime("%d.%m.%Y %H:%M")
    if isinstance(value, date):
        return value.strftime("%d.%m.%Y")
    if isinstance(value, Decimal):
        return format(value.normalize(), "f")
    return str(value).strip()


def name_search(columns, text):
    """SQL condition + parameters: a name (or one of its words) starts with the typed text.

    'as' finds 'Asli Kaya' and 'Ali As'. Case and accents are ignored ('sukru' finds 'Şükrü').
    The text is passed as a parameter and the LIKE wildcards in it are escaped, so typing
    % or ' cannot change the query. Returns ("", []) when nothing was typed.
    """
    typed = (text or "").strip()
    if not typed:
        return "", []
    safe = typed.replace(_ESCAPE, _ESCAPE * 2).replace("%", _ESCAPE + "%").replace("_", _ESCAPE + "_")
    parts, params = [], []
    for column in columns:
        normalized = f"arama_normalize({column})"
        parts.append(f"{normalized} LIKE arama_normalize(%s) ESCAPE '{_ESCAPE}'")
        parts.append(f"{normalized} LIKE '%% ' || arama_normalize(%s) ESCAPE '{_ESCAPE}'")
        params += [safe + "%", safe + "%"]
    return "(" + " OR ".join(parts) + ")", params


class DataStore:
    """Read side of the CRM: the lists the pages show, plus the login check."""

    def __init__(self, db):
        self.db = db
        self.repos = CrmRepositories(db)

    # ----- generic ----------------------------------------------------------------

    def _table(self, headers, sql, params):
        rows = self.db.fetch_all(sql, params)
        return headers, [[cell_text(value) for value in row] for row in rows]

    def _select(self, columns, source, conditions, params, order):
        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        select = ", ".join(expression for _, expression in columns)
        return f"SELECT {select} FROM {source}{where} ORDER BY {order}", params

    # ----- login ------------------------------------------------------------------

    def check_login(self, username, password):
        """Return "admin", "user", or None when the username or password is wrong."""
        return self.repos.kullanicilar.authenticate(username, password)

    # ----- applications -----------------------------------------------------------

    _APPLICATION_SOURCE = "Basvurular b JOIN Kursiyerler k ON k.KursiyerID = b.KursiyerID"
    _FORM_ONLY = "b.BasvuruDonemi <> ALL(%s)"   # form applications, not the old VIT lists

    def applications(self, view="all", search=""):
        """Applications for one view: all, defined, not_defined, duplicates or unique."""
        conditions, params = [self._FORM_ONLY], [PAST_PERIODS]
        if view == "defined":
            conditions.append("b.MentorGorusmesi IS NOT NULL")
        elif view == "not_defined":
            conditions.append("b.MentorGorusmesi IS NULL")
        elif view == "duplicates":
            conditions.append(
                "b.KursiyerID IN (SELECT KursiyerID FROM Basvurular WHERE BasvuruDonemi <> ALL(%s) "
                "GROUP BY KursiyerID HAVING count(*) > 1)")
            params.append(PAST_PERIODS)
        elif view == "unique":
            conditions.append(
                "b.BasvuruID IN (SELECT DISTINCT ON (arama_normalize(k2.AdSoyad)) b2.BasvuruID "
                "FROM Basvurular b2 JOIN Kursiyerler k2 ON k2.KursiyerID = b2.KursiyerID "
                "WHERE b2.BasvuruDonemi <> ALL(%s) ORDER BY arama_normalize(k2.AdSoyad), b2.BasvuruID)")
            params.append(PAST_PERIODS)
        elif view != "all":
            raise ValueError(f"Unknown applications view: {view}")
        condition, extra = name_search(["k.AdSoyad"], search)
        if condition:
            conditions.append(condition)
            params += extra
        sql, params = self._select(APPLICATION_COLUMNS, self._APPLICATION_SOURCE, conditions, params,
                                   "b.BasvuruID")
        return self._table([header for header, _ in APPLICATION_COLUMNS], sql, params)

    def application_counts(self):
        """(all, mentor meeting defined, not defined) for the filter buttons."""
        row = self.db.fetch_one(
            "SELECT count(*), count(MentorGorusmesi), count(*) - count(MentorGorusmesi) "
            "FROM Basvurular WHERE BasvuruDonemi <> ALL(%s)", (PAST_PERIODS,))
        return tuple(row)

    def people(self, view, search=""):
        """People across the form applications and the old VIT lists.

        view "previous_vit": found in at least two of Applications, VIT1, VIT2.
        view "different":    found in exactly one of the VIT lists (not common to both).
        """
        if view == "previous_vit":
            having = "count(*) >= 2"
        elif view == "different":
            having = "count(*) FILTER (WHERE s.source = ANY(%s)) = 1"
        else:
            raise ValueError(f"Unknown people view: {view}")
        condition, extra = name_search(["k.AdSoyad"], search)
        sql = (
            "WITH src AS (SELECT b.KursiyerID, min(b.BasvuruID) AS first_id, "
            "  CASE WHEN b.BasvuruDonemi = ANY(%s) THEN b.BasvuruDonemi ELSE 'Applications' END AS source "
            "  FROM Basvurular b GROUP BY 1, 3) "
            "SELECT k.AdSoyad, k.MailAdresi, "
            "  string_agg(s.source, ', ' ORDER BY (s.source <> 'Applications'), s.source) "
            "FROM src s JOIN Kursiyerler k ON k.KursiyerID = s.KursiyerID "
            + (f"WHERE {condition} " if condition else "")
            + f"GROUP BY k.KursiyerID, k.AdSoyad, k.MailAdresi HAVING {having} "
            "ORDER BY min(s.first_id)")
        params = [PAST_PERIODS] + extra + ([PAST_PERIODS] if view == "different" else [])
        return self._table(PEOPLE_HEADERS, sql, params)

    # ----- interviews -------------------------------------------------------------

    def interviews(self, kind=None, search=""):
        """kind: "sent", "received", or None for all rows."""
        conditions, params = [], []
        if kind == "sent":
            conditions.append("u.ProjeGonderilisTarihi IS NOT NULL")
        elif kind == "received":
            conditions.append("u.ProjeninGelisTarihi IS NOT NULL")
        elif kind is not None:
            raise ValueError(f"Unknown interviews view: {kind}")
        condition, extra = name_search(["k.AdSoyad"], search)
        if condition:
            conditions.append(condition)
            params += extra
        sql, params = self._select(INTERVIEW_COLUMNS,
                                   "Mulakatlar u JOIN Kursiyerler k ON k.KursiyerID = u.KursiyerID",
                                   conditions, params, "u.MulakatID")
        return self._table([header for header, _ in INTERVIEW_COLUMNS], sql, params)

    # ----- mentor conversations ---------------------------------------------------

    def mentor_categories(self):
        """Distinct recommendations, used for the tab combo box."""
        rows = self.db.fetch_all(
            "SELECT DISTINCT VITProjesineKatilabilirMi FROM Mentortablosu "
            "WHERE VITProjesineKatilabilirMi IS NOT NULL ORDER BY 1")
        return [row[0] for row in rows]

    def mentor(self, category=None, search=""):
        """Mentor conversations for one recommendation, or all when category is None.

        The search looks at the candidate name and the mentor name."""
        conditions, params = [], []
        if category is not None:
            conditions.append("m.VITProjesineKatilabilirMi = %s")
            params.append(category)
        condition, extra = name_search(["k.AdSoyad", "m.MentorAdSoyad"], search)
        if condition:
            conditions.append(condition)
            params += extra
        sql, params = self._select(MENTOR_COLUMNS,
                                   "Mentortablosu m JOIN Kursiyerler k ON k.KursiyerID = m.KursiyerID",
                                   conditions, params, "m.MentorID")
        return self._table([header for header, _ in MENTOR_COLUMNS], sql, params)

    # ----- connection info --------------------------------------------------------

    def describe(self):
        cfg = self.db.config
        return f"Connected to PostgreSQL: {cfg.dbname} on {cfg.host}:{cfg.port}"
