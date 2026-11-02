"""Text normalization helpers.

These are line-for-line ports of the helpers in the website's index.html, so
the API and the web page find exactly the same dictionary matches. The parity
tests in tests/test_parity.py check that they stay in sync.
"""
import re
import unicodedata

# Characters the dictionary uses that NFD decomposition alone doesn't handle.
_SPECIAL = {"ʰ": "", "ʼ": "'", "’": "'", "ʻ": "'", "ˈ": "", "ð": "dh", "Ð": "Dh", "ŋ": "ng"}
_COMBINING = re.compile("[̀-ͯ]")

STOPWORDS = frozenset(
    "a an the to of in on at is are was were be been and or but it its s lit also".split()
)


def strip_diacritics(s: str) -> str:
    """'lfuwooní' -> 'lfuwooni'. Keeps the base letters, drops accent marks."""
    if not s:
        return s
    for k, v in _SPECIAL.items():
        s = s.replace(k, v)
    return _COMBINING.sub("", unicodedata.normalize("NFD", s))


def normalize_key(s: str) -> str:
    """Lookup key for a Bravanese word: no parentheses, hyphens, accents or spaces; lowercase."""
    if not s:
        return ""
    s = re.sub(r"\(.*?\)", "", s)
    s = s.replace("-", "")
    s = strip_diacritics(s)
    s = re.sub(r"\s+", "", s)
    return s.lower().strip()


def tokenize(s: str) -> list[str]:
    """Lowercase ASCII word tokens (apostrophes kept), like the JS /[a-z']+/g."""
    return re.findall(r"[a-z']+", s.lower())


def clean_gloss(gloss: str) -> str:
    """Shorten a dictionary gloss to its first meaning.

    '(cl.5) 1. stone; rock' -> 'stone'
    """
    if not gloss:
        return ""
    gloss = re.sub(r"^\([^)]*\)\s*", "", gloss.strip())
    gloss = re.sub(r"^[0-9]+(/[0-9]+)?\.?\s+", "", gloss)
    for part in re.split(r"[;,(]", gloss):
        if part.strip():
            return part.strip()
    return gloss.strip()
