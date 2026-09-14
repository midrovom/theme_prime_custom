import re
import unicodedata


def normalize_client_name(value):
    """Stable exact-match key for client exclusions.

    We intentionally do not use fuzzy matching: different customers with similar
    names must never be excluded accidentally. Case, accents, punctuation and
    repeated whitespace are ignored.
    """
    text = str(value or "").strip().upper()
    if not text:
        return ""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = re.sub(r"[^A-Z0-9]+", " ", text)
    return " ".join(text.split())
