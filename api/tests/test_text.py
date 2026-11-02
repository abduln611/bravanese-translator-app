from app.text import clean_gloss, normalize_key, strip_diacritics, tokenize


def test_strip_diacritics():
    assert strip_diacritics("lfuwooní") == "lfuwooni"
    assert strip_diacritics("kuzóola") == "kuzoola"
    assert strip_diacritics("ðaŋa") == "dhanga"


def test_normalize_key_removes_hyphens_parens_spaces():
    assert normalize_key("Ø-mbeene") == "ømbeene"
    assert normalize_key("ma-tunda (pl.)") == "matunda"
    assert normalize_key("  Muke ") == "muke"
    assert normalize_key("") == ""


def test_tokenize_keeps_only_ascii_letters_and_apostrophes():
    assert tokenize("What's your NAME?") == ["what's", "your", "name"]
    assert tokenize("123 !!") == []


def test_clean_gloss_takes_first_meaning():
    assert clean_gloss("(cl.5) 1. stone; rock") == "stone"
    assert clean_gloss("to pick, gather") == "to pick"
    assert clean_gloss("") == ""
