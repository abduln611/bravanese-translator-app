"""Builds the prompt sent to the model. Same wording as the website."""
import json
from pathlib import Path

from .retrieval import Context

GRAMMAR_NOTES = " ".join(json.loads((Path(__file__).parent / "grammar_notes.json").read_text(encoding="utf-8")))

DIRECTION_LABELS = {
    "b2e": "Chimiini/Bravanese into natural English",
    "e2b": "English into Chimiini/Bravanese",
}


def lex_lines(ctx: Context) -> list[str]:
    """The DICTIONARY MATCHES lines, formatted exactly like the website."""
    lines = []
    for m in ctx.matches:
        if ctx.direction == "b2e":
            lines.append(("[community] " if m.community else "") + f'{m.token} = "{m.gloss}" {m.note}')
        else:
            shown = [("[community] " if h.community else "") + h.bravanese + (" " + h.note if h.note else "") for h in m.bravanese]
            lines.append(m.token + " = " + " / ".join(shown))
    return lines


def build_prompt(sentence: str, ctx: Context) -> str:
    lines = lex_lines(ctx)
    parts = [
        f"You are a linguistic assistant helping translate {DIRECTION_LABELS[ctx.direction]}.",
        "Use the dictionary matches and example sentences below as ground truth for vocabulary and grammar -- they come directly from a real Chimiini/Bravanese dictionary and corpus, retrieved specifically for this sentence.",
        "Lines tagged [community] were contributed by Chimiini speakers and reviewed by the site owner. They are the most trusted source: when a [community] entry disagrees with an untagged dictionary entry or example, follow the [community] one.",
        "If a word in the input has no matching lexicon entry below, say so explicitly in your answer rather than inventing a translation for it.",
        "",
        "GRAMMAR BACKGROUND: " + GRAMMAR_NOTES,
        "",
        "DICTIONARY MATCHES for words in this sentence:",
        "\n".join(lines) if lines else "(none found)",
    ]
    if ctx.unknown:
        parts.append("\nWords with NO dictionary match: " + ", ".join(ctx.unknown))
    parts.append("\nRELEVANT EXAMPLE SENTENCES from the corpus (for grammar/word-order reference):")
    parts.append(
        "\n".join(("[community] " if e.community else "") + f"{e.source_text}  =  {e.target_text}" for e in ctx.examples)
        if ctx.examples else "(none found)"
    )
    parts += [
        "",
        f'SENTENCE TO TRANSLATE: "{sentence}"',
        "",
        "Give: 1) your best translation, 2) a one-sentence note on any word you could not ground in the dictionary matches above, if any. Keep it concise. Write plain text only: no Markdown, no asterisks, no # headings.",
    ]
    return "\n".join(parts)
