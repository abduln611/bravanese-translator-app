#!/usr/bin/env python3
"""Fold approved submissions into lexicon.json and parallel_sentences.jsonl.

Reads every submissions/words/*.json and submissions/examples/*.json,
merges them into the data files (keeping the existing formatting exactly),
then deletes the processed submission files.

Run by .github/workflows/merge-submissions.yml after a submission PR is
merged, but it also works locally:  python scripts/merge_submissions.py
"""
import json
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LEXICON = ROOT / "lexicon.json"
PARALLEL = ROOT / "parallel_sentences.jsonl"
SUB_DIR = ROOT / "submissions"


def ascii_fold(s):
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def norm(s):
    return ascii_fold(s or "").lower().strip()


def nz(v):
    v = (v or "").strip() if isinstance(v, str) else v
    return v if v not in ("", None) else None


def word_to_entry(sub):
    head = sub["bravanese_form"].strip()
    entry = {
        "headword_original": head,
        "headword_ascii": ascii_fold(head),
        "pos": None,
        "etymology_raw": [],
        "gloss": sub["english_form"].strip(),
        "related_forms": [],
        "examples": [],
        "page": None,
        "past_tense": nz(sub.get("past_tense")),
        "is_infinitive_verb": bool(sub.get("is_infinitive_verb")),
        "size_class": nz(sub.get("size_class")),
        "noun_class": nz(sub.get("noun_class")),
        "plural_form": nz(sub.get("plural_form")),
        "source": "user_added",
    }
    if nz(sub.get("submitted_by")):
        entry["submitted_by"] = sub["submitted_by"].strip()
    return entry


def main():
    word_files = sorted((SUB_DIR / "words").glob("*.json"))
    example_files = sorted((SUB_DIR / "examples").glob("*.json"))
    if not word_files and not example_files:
        print("No submissions to merge.")
        return 0

    lexicon = json.loads(LEXICON.read_text(encoding="utf-8"))
    by_head = {}
    for e in lexicon:
        by_head.setdefault(norm(e.get("headword_original")), []).append(e)

    added_words = updated_words = 0
    for f in word_files:
        sub = json.loads(f.read_text(encoding="utf-8"))
        new = word_to_entry(sub)
        match = next((e for e in by_head.get(norm(new["headword_original"]), [])
                      if norm(e.get("gloss")) == norm(new["gloss"])), None)
        if match:
            # Same headword + gloss already exists: only fill in blanks.
            for k in ("past_tense", "size_class", "noun_class", "plural_form"):
                if new[k] and not match.get(k):
                    match[k] = new[k]
            if new["is_infinitive_verb"] and not match.get("is_infinitive_verb"):
                match["is_infinitive_verb"] = True
            updated_words += 1
        else:
            lexicon.append(new)
            by_head.setdefault(norm(new["headword_original"]), []).append(new)
            added_words += 1

    existing_pairs = set()
    with PARALLEL.open(encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                r = json.loads(line)
                existing_pairs.add((norm(r.get("bravanese_original")), norm(r.get("english"))))

    new_rows, attached = [], 0
    for f in example_files:
        sub = json.loads(f.read_text(encoding="utf-8"))
        bra = sub["bravanese_sentence"].strip()
        eng = sub["english_translation"].strip()
        hint = nz(sub.get("headword_hint"))
        key = (norm(bra), norm(eng))
        if key in existing_pairs:
            continue
        existing_pairs.add(key)
        row = {
            "bravanese_original": bra,
            "bravanese_ascii": ascii_fold(bra),
            "english": eng,
            "register": "",
            "headword": hint or "",
            "page": None,
            "source": "user_added",
        }
        if nz(sub.get("past_tense")):
            row["past_tense"] = sub["past_tense"].strip()
        new_rows.append(row)
        if hint and by_head.get(norm(hint)):
            by_head[norm(hint)][0].setdefault("examples", []).append({
                "bravanese_original": bra,
                "bravanese_ascii": ascii_fold(bra),
                "english": eng,
                "register": None,
            })
            attached += 1

    LEXICON.write_text(json.dumps(lexicon, ensure_ascii=False, indent=1), encoding="utf-8")
    if new_rows:
        with PARALLEL.open("a", encoding="utf-8") as fh:
            for r in new_rows:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    for f in word_files + example_files:
        f.unlink()

    print(f"Words: {added_words} added, {updated_words} merged into existing entries. "
          f"Examples: {len(new_rows)} added to parallel_sentences.jsonl, "
          f"{attached} also attached to a lexicon headword.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
