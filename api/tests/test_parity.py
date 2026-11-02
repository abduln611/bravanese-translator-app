"""The Python retrieval must give the same results as the website's JavaScript.

js_parity.json was produced by running index.html's own code on the sample
data (see fixtures/generate_parity.js). If you change the retrieval logic in
one place, change it in the other and regenerate the fixture.
"""
import json

import pytest

from app.prompt import lex_lines
from tests.conftest import FIXTURES

CASES = json.loads((FIXTURES / "js_parity.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("case", CASES, ids=[f"{c['direction']}:{c['sentence'][:30]}" for c in CASES])
def test_matches_javascript(dictionary, case):
    ctx = dictionary.index.build_context(case["sentence"], case["direction"])

    assert lex_lines(ctx) == case["lexLines"]
    assert ctx.unknown == case["unknown"]
    assert [
        {"score": pytest.approx(e.score), "source": e.source_text, "target": e.target_text, "community": e.community}
        for e in ctx.examples
    ] == case["examples"]


def test_community_entry_beats_dictionary(dictionary):
    """A community entry wins the word and its community example ranks first."""
    ctx = dictionary.index.build_context("muke", "b2e")
    assert ctx.matches[0].gloss == "TEST community gloss"
    assert ctx.matches[0].community is True
    assert ctx.examples[0].community is True


def test_community_headword_overrides_dictionary_headword(dictionary):
    hit = dictionary.index.lookup_bravanese("dhahamu")
    assert hit.gloss == "TEST community override" and hit.community
