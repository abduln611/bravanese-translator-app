"""Dictionary retrieval: find the lexicon entries and example sentences that
are relevant to a sentence, so the model can translate from real data.

Port of the `Index` object in the website's index.html. Community submissions
(`"source": "user_added"`) are indexed first so they win any word they share
with the original dictionary, and they get a boost when examples are ranked.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from .text import STOPWORDS, clean_gloss, normalize_key, strip_diacritics, tokenize

Direction = Literal["b2e", "e2b"]
USER_EXAMPLE_BOOST = 0.25


def is_community(item: dict) -> bool:
    return bool(item) and item.get("source") == "user_added"


@dataclass
class BraHit:
    """A Bravanese word -> English gloss match."""
    gloss: str
    note: str
    community: bool


@dataclass
class EngHit:
    """An English word -> Bravanese word match."""
    bravanese: str
    note: str
    community: bool


@dataclass
class Example:
    score: float
    source_text: str   # the side in the input language (lowercased key)
    target_text: str   # the other side
    community: bool


@dataclass
class DictionaryMatch:
    token: str
    community: bool
    gloss: str | None = None                                # b2e
    note: str = ""                                          # b2e
    bravanese: list[EngHit] = field(default_factory=list)   # e2b


@dataclass
class Context:
    direction: Direction
    matches: list[DictionaryMatch]
    unknown: list[str]
    examples: list[Example]


class Index:
    def __init__(self) -> None:
        self.bra_to_eng: dict[str, BraHit] = {}
        self.eng_to_bra_exact: dict[str, list[EngHit]] = {}
        self.eng_to_bra_partial: dict[str, list[EngHit]] = {}
        self.phrase_bra_to_eng: dict[str, str] = {}
        self.phrase_eng_to_bra: dict[str, str] = {}
        self.user_phrase_keys: set[str] = set()

    # ---------- building ----------

    def _add_bra(self, key: str, gloss: str, note: str, user: bool) -> None:
        if key and gloss and key not in self.bra_to_eng:
            self.bra_to_eng[key] = BraHit(gloss, note, user)

    def _add_eng(self, gloss: str, bra_original: str, note: str, user: bool) -> None:
        words = tokenize(gloss)
        target = self.eng_to_bra_exact if len(words) == 1 else self.eng_to_bra_partial
        for w in words:
            if w in STOPWORDS or len(w) < 3:
                continue
            hits = target.setdefault(w, [])
            if not any(h.bravanese == bra_original for h in hits):
                hits.append(EngHit(bra_original, note, user))

    def _add_phrase(self, bra_original, bra_ascii, english, user: bool) -> None:
        if not bra_original or not english:
            return
        bra_ascii = bra_ascii or strip_diacritics(bra_original)
        eng_key = "".join(ch for ch in english.lower() if ch in "abcdefghijklmnopqrstuvwxyz0123456789 ").strip()
        bra_key = bra_ascii.lower().strip()
        if bra_key and bra_key not in self.phrase_bra_to_eng:
            self.phrase_bra_to_eng[bra_key] = english
            if user:
                self.user_phrase_keys.add("b:" + bra_key)
        if eng_key and eng_key not in self.phrase_eng_to_bra:
            self.phrase_eng_to_bra[eng_key] = bra_original
            if user:
                self.user_phrase_keys.add("e:" + eng_key)

    @classmethod
    def build(cls, lexicon: list[dict], parallel_rows: list[dict]) -> "Index":
        idx = cls()
        # Community entries first, so they win any key they share with the dictionary.
        lexicon = [e for e in lexicon if is_community(e)] + [e for e in lexicon if not is_community(e)]
        parallel_rows = [r for r in parallel_rows if is_community(r)] + [r for r in parallel_rows if not is_community(r)]

        for e in lexicon:
            u = is_community(e)
            headword = e.get("headword_original") or ""
            key = normalize_key(headword)
            gloss = clean_gloss(e.get("gloss") or "")
            if key and gloss:
                idx._add_bra(key, gloss, "", u)
                idx._add_eng(gloss, headword, "", u)
            if e.get("plural_form"):
                idx._add_bra(normalize_key(e["plural_form"]), gloss, "(plural)", u)
            if e.get("past_tense"):
                idx._add_bra(normalize_key(e["past_tense"]), gloss, "(past tense)", u)
            for rel in e.get("related_forms") or []:
                form = rel.get("form_raw") or rel.get("form")
                if not form:
                    continue
                rel_gloss = clean_gloss(rel.get("gloss") or "") or gloss
                deriv = rel.get("derivation") or []
                note = "(" + "/".join(deriv) + ")" if deriv else ""
                if rel_gloss:
                    idx._add_bra(normalize_key(form), rel_gloss, note, u)
                if rel.get("past_tense"):
                    idx._add_bra(normalize_key(rel["past_tense"]), rel_gloss, "(past tense)", u)
            for ex in e.get("examples") or []:
                idx._add_phrase(ex.get("bravanese_original"), ex.get("bravanese_ascii"), ex.get("english"), u)

        for r in parallel_rows:
            idx._add_phrase(r.get("bravanese_original"), r.get("bravanese_ascii"), r.get("english"), is_community(r))
        return idx

    # ---------- querying ----------

    def lookup_bravanese(self, word: str) -> BraHit | None:
        return self.bra_to_eng.get(normalize_key(word))

    def lookup_english(self, word: str) -> list[EngHit]:
        w = word.lower().strip()
        return self.eng_to_bra_exact.get(w) or self.eng_to_bra_partial.get(w) or []

    def closest_examples(self, tokens: list[str], direction: Direction, n: int = 5) -> list[Example]:
        phrases = self.phrase_bra_to_eng if direction == "b2e" else self.phrase_eng_to_bra
        prefix = "b:" if direction == "b2e" else "e:"
        token_set = set(tokens)
        scored = []
        for key, val in phrases.items():
            key_tokens = tokenize(key)
            overlap = sum(1 for t in key_tokens if t in token_set)
            if overlap > 0:
                u = (prefix + key) in self.user_phrase_keys
                score = overlap / max(len(key_tokens), len(tokens)) + (USER_EXAMPLE_BOOST if u else 0)
                scored.append(Example(score, key, val, u))
        scored.sort(key=lambda ex: ex.score, reverse=True)  # stable, like JS Array.sort
        return scored[:n]

    def build_context(self, sentence: str, direction: Direction) -> Context:
        tokens = tokenize(strip_diacritics(sentence)) if direction == "b2e" else tokenize(sentence)
        matches: list[DictionaryMatch] = []
        unknown: list[str] = []
        if direction == "b2e":
            for t in tokens:
                hit = self.bra_to_eng.get(normalize_key(t))
                if hit:
                    matches.append(DictionaryMatch(token=t, community=hit.community, gloss=hit.gloss, note=hit.note))
                else:
                    unknown.append(t)
        else:
            for t in tokens:
                if t in STOPWORDS:
                    continue
                hits = self.eng_to_bra_exact.get(t) or self.eng_to_bra_partial.get(t)
                if hits:
                    shown = hits[:3]
                    matches.append(DictionaryMatch(token=t, community=shown[0].community, bravanese=shown))
                else:
                    unknown.append(t)
        return Context(direction, matches, unknown, self.closest_examples(tokens, direction, 5))
