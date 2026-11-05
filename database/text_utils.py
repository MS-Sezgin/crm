"""Small text helpers shared by the database code."""
import unicodedata


def normalize(value):
    """Lower-case text without accents, so 'Şükrü' and 'sukru' compare equal.

    Same rule the search and the duplicate checks have always used.
    """
    text = "" if value is None else str(value)
    decomposed = unicodedata.normalize("NFKD", text)
    plain = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return plain.replace("ı", "i").lower().strip()
