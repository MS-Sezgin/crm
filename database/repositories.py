"""One repository class per table. All SQL lives here, written with %s parameters,
so user input is never pasted into a query (no SQL injection).

``CrmRepositories`` bundles the five repositories around one Database object.
"""
from database.security import PasswordHasher


class BaseRepository:
    TABLE = ""

    def __init__(self, db):
        self.db = db

    def count(self):
        return self.db.fetch_value(f"SELECT count(*) FROM {self.TABLE}")


class KursiyerRepository(BaseRepository):
    """Trainees: one row per person. A person is identified by name + e-mail
    (the e-mail alone is not unique: two people can share one address)."""
    TABLE = "Kursiyerler"

    # Compare names without case or accents, e-mail without case (same as the unique index).
    _SAME_PERSON = "arama_normalize(AdSoyad) = arama_normalize(%s) AND lower(MailAdresi) = lower(%s)"

    def find(self, ad_soyad, mail):
        return self.db.fetch_value(
            f"SELECT KursiyerID FROM Kursiyerler WHERE {self._SAME_PERSON}", (ad_soyad, mail))

    def find_by_name(self, ad_soyad):
        """All KursiyerIDs with this name (more than one means the name is ambiguous)."""
        rows = self.db.fetch_all(
            "SELECT KursiyerID FROM Kursiyerler WHERE arama_normalize(AdSoyad) = arama_normalize(%s) "
            "ORDER BY KursiyerID", (ad_soyad,))
        return [row[0] for row in rows]

    def add(self, ad_soyad, mail, telefon=None, posta_kodu=None, eyalet=None):
        return self.db.fetch_value(
            "INSERT INTO Kursiyerler (AdSoyad, MailAdresi, TelefonNumarasi, PostaKodu, YasadiginizEyalet) "
            "VALUES (%s, %s, %s, %s, %s) RETURNING KursiyerID",
            (ad_soyad, mail, telefon, posta_kodu, eyalet))

    def contact(self, kursiyer_id):
        """(phone, postal code, province) of one trainee."""
        return self.db.fetch_one(
            "SELECT TelefonNumarasi, PostaKodu, YasadiginizEyalet FROM Kursiyerler WHERE KursiyerID = %s",
            (kursiyer_id,))

    def fill_missing(self, kursiyer_id, telefon, posta_kodu, eyalet):
        """Fill only the empty contact fields; a value that is already there is kept."""
        self.db.execute(
            "UPDATE Kursiyerler SET TelefonNumarasi = COALESCE(TelefonNumarasi, %s), "
            "PostaKodu = COALESCE(PostaKodu, %s), YasadiginizEyalet = COALESCE(YasadiginizEyalet, %s) "
            "WHERE KursiyerID = %s", (telefon, posta_kodu, eyalet, kursiyer_id))

    def shared_emails(self):
        """E-mail addresses used by more than one trainee: (mail, names, number of phones)."""
        return self.db.fetch_all(
            "SELECT lower(MailAdresi), string_agg(AdSoyad, ' / ' ORDER BY KursiyerID), "
            "count(DISTINCT TelefonNumarasi) FROM Kursiyerler "
            "GROUP BY lower(MailAdresi) HAVING count(*) > 1 ORDER BY 1")


class BasvuruRepository(BaseRepository):
    TABLE = "Basvurular"
    COLUMNS = (
        "ZamanDamgasi", "SuAnkiDurum", "KatilmakIstenenEgitim", "EkonomikDurum",
        "DilKursunaDevamEdiyorMu", "IngilizceSeviye", "HollandacaSeviye", "BelediyeBaskisi",
        "BaskaITKursuBitirdiMi", "OnlineITKursuTakipEttiMi", "ITIsTecrubesi", "BaskaProjedeMi",
        "ITBolumleri", "VITNedenleri", "Motivasyon", "MentorGorusmesi", "BasvuruDonemi",
        "YesilTikOlan", "DahiliTakip1", "DahiliTakip2", "DahiliTakip3", "IslemDurumu",
    )

    def add(self, kursiyer_id, values):
        """Insert one application. ``values`` maps column name -> value; missing ones stay empty."""
        unknown = set(values) - set(self.COLUMNS)
        if unknown:
            raise ValueError(f"Unknown Basvurular column(s): {', '.join(sorted(unknown))}")
        names = [c for c in self.COLUMNS if c in values]
        sql = (f"INSERT INTO Basvurular (KursiyerID, {', '.join(names)}) "
               f"VALUES (%s, {', '.join(['%s'] * len(names))}) RETURNING BasvuruID")
        return self.db.fetch_value(sql, (kursiyer_id, *[values[c] for c in names]))

    def count_by_period(self):
        return dict(self.db.fetch_all(
            "SELECT BasvuruDonemi, count(*) FROM Basvurular GROUP BY BasvuruDonemi ORDER BY 1"))


class MentorRepository(BaseRepository):
    TABLE = "Mentortablosu"

    def add(self, kursiyer_id, gorusme_tarihi=None, mentor_adsoyad=None, bilgi_sahibi=None,
            vit_katilabilir=None, dusunce=None, yogunluk=None, yorumlar=None, vit_grubu=None):
        return self.db.fetch_value(
            "INSERT INTO Mentortablosu (KursiyerID, GorusmeTarihi, MentorAdSoyad, BilgiSahibiMi, "
            "VITProjesineKatilabilirMi, Dusunce, YogunlukDurumu, Yorumlar, VITGrubu) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING MentorID",
            (kursiyer_id, gorusme_tarihi, mentor_adsoyad, bilgi_sahibi, vit_katilabilir,
             dusunce, yogunluk, yorumlar, vit_grubu))


class MulakatRepository(BaseRepository):
    TABLE = "Mulakatlar"

    def add(self, kursiyer_id, proje_gonderilis=None, proje_gelis=None):
        return self.db.fetch_value(
            "INSERT INTO Mulakatlar (KursiyerID, ProjeGonderilisTarihi, ProjeninGelisTarihi) "
            "VALUES (%s, %s, %s) RETURNING MulakatID", (kursiyer_id, proje_gonderilis, proje_gelis))


class KullaniciRepository(BaseRepository):
    TABLE = "Kullanicilar"

    def __init__(self, db, hasher=None):
        super().__init__(db)
        self.hasher = hasher or PasswordHasher()

    def add(self, kullanici, parola, yetki):
        """Store a user. ``parola`` is the plain password; only its hash is saved."""
        self.db.execute("INSERT INTO Kullanicilar (Kullanici, Parola, Yetki) VALUES (%s, %s, %s)",
                        (kullanici, self.hasher.hash(parola), yetki))

    def authenticate(self, kullanici, parola):
        """Return "admin", "user", or None when the username or password is wrong."""
        row = self.db.fetch_one(
            "SELECT Parola, Yetki FROM Kullanicilar WHERE lower(Kullanici) = lower(%s)",
            (kullanici.strip(),))
        if row and self.hasher.verify(parola, row[0]):
            return row[1]
        return None


class CrmRepositories:
    """All repositories of the CRM, sharing one database connection."""

    def __init__(self, db):
        self.db = db
        self.kursiyerler = KursiyerRepository(db)
        self.basvurular = BasvuruRepository(db)
        self.mentor = MentorRepository(db)
        self.mulakatlar = MulakatRepository(db)
        self.kullanicilar = KullaniciRepository(db)

    def counts(self):
        """Row count of every table."""
        return {
            "Kursiyerler": self.kursiyerler.count(),
            "Basvurular": self.basvurular.count(),
            "Mentortablosu": self.mentor.count(),
            "Mulakatlar": self.mulakatlar.count(),
            "Kullanicilar": self.kullanicilar.count(),
        }
