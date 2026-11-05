-- =====================================================================
-- CRM Projesi - PostgreSQL veritabanı şeması
-- =====================================================================
-- Kullanım:
--   1) Veritabanını oluştur (pgAdmin'de ya da terminalde):
--        createdb -U postgres crm_db
--   2) Bu dosyayı çalıştır:
--        psql -U postgres -d crm_db -f database/schema.sql
--
-- Not: PostgreSQL tırnaksız adları küçük harfe çevirir. Aşağıdaki
-- KursiyerID, AdSoyad gibi adlar veritabanında kursiyerid, adsoyad olur;
-- ödev PDF'indeki örnek INSERT sorguları olduğu gibi çalışır.
--
-- Tasarım kararları:
--   * Ödevdeki 5 tablo korunmuştur; ek tablo yoktur.
--   * Kursiyerler: kişi başına tek satır. Kimlik = ad + e-posta
--     (e-posta tek başına benzersiz DEĞİLDİR: iki farklı kişi aynı
--     e-postayı kullanabiliyor).
--   * Basvurular, Mentortablosu ve Mulakatlar kişiyi KursiyerID ile
--     tanır; ad/telefon gibi bilgiler tekrar edilmez.
--   * Basvurular'da benzersizlik kuralı YOKTUR: aynı başvurunun birden
--     fazla gelmesi uygulamadaki "Duplicate Records" filtresi için
--     korunur.
--   * VIT1 / VIT2 listeleri ayrı tablo değildir: BasvuruDonemi
--     sütununda "VIT1" / "VIT2" olarak Basvurular'a girer.
--   * Çok değerli alanlar (bölümler, nedenler) orijinal metin olarak
--     saklanır. Anket cevabı sütunları TEXT'tir: cevaplar serbest metin
--     olabiliyor (gerçek veride 79 karakterlik bir cevap vardı).
--   * basvuru_detay, mentor_detay, mulakat_detay görünümleri tabloları
--     ödevdeki düz (birleştirilmiş) sütun listesiyle gösterir.
--
-- Sıfırlamak için (DİKKAT: tüm veriyi siler):
--   DROP VIEW IF EXISTS basvuru_detay, mentor_detay, mulakat_detay;
--   DROP TABLE IF EXISTS Mulakatlar, Mentortablosu, Basvurular,
--                        Kullanicilar, Kursiyerler CASCADE;
--   DROP FUNCTION IF EXISTS arama_normalize(text);
-- =====================================================================


-- ---------------------------------------------------------------------
-- Yardımcı fonksiyon: arama için metni sadeleştirir.
-- Küçük harfe çevirir, Türkçe/aksanlı harfleri sade harfe indirger
-- (ör. "Şükrü" -> "sukru"). Uygulamadaki mevcut arama davranışıyla
-- aynıdır ve ek eklenti (unaccent) gerektirmez.
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION arama_normalize(metin text) RETURNS text AS $$
    SELECT lower(translate(
        metin,
        'İıÇçĞğÖöŞşÜüÂâÎîÛûÉéÈèÊêËëÁáÀàÄäÍíÓóÒòÔôÚúÙùÑñ',
        'iiCcGgOoSsUuAaIiUuEeEeEeEeAaAaAaIiOoOoOoUuUuNn'
    ));
$$ LANGUAGE sql IMMUTABLE;


-- ---------------------------------------------------------------------
-- 1) KURSIYERLER - kişi başına tek satır
-- ---------------------------------------------------------------------
CREATE TABLE Kursiyerler (
    KursiyerID          SERIAL PRIMARY KEY,
    AdSoyad             VARCHAR(150) NOT NULL,
    MailAdresi          VARCHAR(150) NOT NULL,
    TelefonNumarasi     VARCHAR(30),
    PostaKodu           VARCHAR(10),
    YasadiginizEyalet   VARCHAR(50)
);

-- Aynı kişi (ad + e-posta) iki kez eklenemez; e-posta tek başına serbest.
CREATE UNIQUE INDEX uq_kursiyerler_ad_mail
    ON Kursiyerler (arama_normalize(AdSoyad), lower(MailAdresi));
CREATE INDEX ix_kursiyerler_arama ON Kursiyerler (arama_normalize(AdSoyad) text_pattern_ops);


-- ---------------------------------------------------------------------
-- 2) BASVURULAR - her form başvurusu (ve VIT1/VIT2 geçmiş kayıtları)
-- ---------------------------------------------------------------------
CREATE TABLE Basvurular (
    BasvuruID                   SERIAL PRIMARY KEY,
    KursiyerID                  INTEGER NOT NULL
                                REFERENCES Kursiyerler (KursiyerID)
                                ON UPDATE CASCADE ON DELETE RESTRICT,
    ZamanDamgasi                TIMESTAMP,                 -- VIT1/VIT2 kayıtlarında boş
    SuAnkiDurum                 TEXT,
    KatilmakIstenenEgitim       TEXT,   -- ITPH Cybersecurity / Powerplatform vb.
    EkonomikDurum               TEXT,
    DilKursunaDevamEdiyorMu     TEXT,
    IngilizceSeviye             TEXT,
    HollandacaSeviye            TEXT,
    BelediyeBaskisi             TEXT,
    BaskaITKursuBitirdiMi       TEXT,
    OnlineITKursuTakipEttiMi    TEXT,
    ITIsTecrubesi               TEXT,
    BaskaProjedeMi              TEXT,               -- Excel'de ayrı sütun
    ITBolumleri                 TEXT,   -- virgülle ayrılmış liste, orijinal metin
    VITNedenleri                TEXT,   -- noktalı virgülle ayrılmış liste, orijinal metin
    Motivasyon                  TEXT,
    MentorGorusmesi             TEXT,
    BasvuruDonemi               VARCHAR(20) NOT NULL,      -- VIT1, VIT2, VIT3 ...
    YesilTikOlan                TEXT,
    DahiliTakip1                NUMERIC,                   -- ödevde yok, veri kaybolmasın diye
    DahiliTakip2                NUMERIC,
    DahiliTakip3                NUMERIC,
    IslemDurumu                 VARCHAR(50)
);

CREATE INDEX ix_basvurular_kursiyer ON Basvurular (KursiyerID);
CREATE INDEX ix_basvurular_donem    ON Basvurular (BasvuruDonemi);


-- ---------------------------------------------------------------------
-- 3) MENTORTABLOSU - mentor görüşme kayıtları (bir kursiyerin birden
--    fazla görüşmesi olabilir)
-- ---------------------------------------------------------------------
CREATE TABLE Mentortablosu (
    MentorID                    SERIAL PRIMARY KEY,        -- görüşme kaydının numarası
    GorusmeTarihi               DATE,
    MentorAdSoyad               VARCHAR(100),
    KursiyerID                  INTEGER NOT NULL
                                REFERENCES Kursiyerler (KursiyerID)
                                ON UPDATE CASCADE ON DELETE RESTRICT,
    BilgiSahibiMi               SMALLINT,                  -- puan
    VITProjesineKatilabilirMi   TEXT,                      -- öneri
    Dusunce                     TEXT,                      -- alternatif öneri (serbest metin)
    YogunlukDurumu              SMALLINT,                  -- ikinci puan
    Yorumlar                    TEXT,
    VITGrubu                    VARCHAR(20)                -- ödevde yok, veri kaybolmasın diye
);

CREATE INDEX ix_mentortablosu_kursiyer ON Mentortablosu (KursiyerID);


-- ---------------------------------------------------------------------
-- 4) KULLANICILAR - giriş bilgileri (Parola sütununda hash saklanır)
-- ---------------------------------------------------------------------
CREATE TABLE Kullanicilar (
    Kullanici   VARCHAR(50) PRIMARY KEY,
    Parola      VARCHAR(255) NOT NULL,
    Yetki       VARCHAR(20) NOT NULL CHECK (Yetki IN ('admin', 'user'))
);

-- Kullanıcı adı büyük/küçük harfe duyarsız benzersiz olsun (girişteki gibi).
CREATE UNIQUE INDEX uq_kullanicilar_kullanici ON Kullanicilar (lower(Kullanici));


-- ---------------------------------------------------------------------
-- 5) MULAKATLAR - proje gönderiliş / geliş tarihleri
-- ---------------------------------------------------------------------
CREATE TABLE Mulakatlar (
    MulakatID               SERIAL PRIMARY KEY,
    KursiyerID              INTEGER NOT NULL
                            REFERENCES Kursiyerler (KursiyerID)
                            ON UPDATE CASCADE ON DELETE RESTRICT,
    ProjeGonderilisTarihi   DATE,
    ProjeninGelisTarihi     DATE
);

CREATE INDEX ix_mulakatlar_kursiyer ON Mulakatlar (KursiyerID);


-- ---------------------------------------------------------------------
-- Görünümler: ödevdeki düz sütun listesini (ad, e-posta ... dahil) verir
-- ---------------------------------------------------------------------
CREATE VIEW basvuru_detay AS
SELECT  b.BasvuruID,
        b.ZamanDamgasi,
        k.AdSoyad,
        k.MailAdresi,
        k.TelefonNumarasi,
        k.PostaKodu,
        k.YasadiginizEyalet,
        b.SuAnkiDurum, b.KatilmakIstenenEgitim, b.EkonomikDurum,
        b.DilKursunaDevamEdiyorMu, b.IngilizceSeviye, b.HollandacaSeviye,
        b.BelediyeBaskisi, b.BaskaITKursuBitirdiMi, b.OnlineITKursuTakipEttiMi,
        b.ITIsTecrubesi, b.BaskaProjedeMi, b.ITBolumleri, b.VITNedenleri,
        b.Motivasyon, b.MentorGorusmesi, b.BasvuruDonemi, b.YesilTikOlan,
        b.DahiliTakip1, b.DahiliTakip2, b.DahiliTakip3, b.IslemDurumu,
        b.KursiyerID
FROM    Basvurular b
JOIN    Kursiyerler k ON k.KursiyerID = b.KursiyerID;

CREATE VIEW mentor_detay AS
SELECT  m.MentorID, m.GorusmeTarihi, m.VITGrubu,
        k.AdSoyad AS KursiyerAdSoyad,
        m.MentorAdSoyad, m.BilgiSahibiMi, m.VITProjesineKatilabilirMi,
        m.Dusunce, m.YogunlukDurumu, m.Yorumlar,
        m.KursiyerID
FROM    Mentortablosu m
JOIN    Kursiyerler k ON k.KursiyerID = m.KursiyerID;

CREATE VIEW mulakat_detay AS
SELECT  u.MulakatID,
        k.AdSoyad,
        u.ProjeGonderilisTarihi, u.ProjeninGelisTarihi,
        u.KursiyerID
FROM    Mulakatlar u
JOIN    Kursiyerler k ON k.KursiyerID = u.KursiyerID;
