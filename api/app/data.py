"""Loads lexicon.json and parallel_sentences.jsonl and builds the search index."""
import json
from dataclasses import dataclass
from pathlib import Path

from .retrieval import Index, is_community


@dataclass
class Dictionary:
    lexicon: list[dict]
    parallel_rows: list[dict]
    index: Index

    @property
    def stats(self) -> dict:
        return {
            "entries": len(self.lexicon),
            "example_pairs": len(self.parallel_rows),
            "community_entries": sum(1 for e in self.lexicon if is_community(e)),
            "community_example_pairs": sum(1 for r in self.parallel_rows if is_community(r)),
        }


def load_dictionary(data_dir: Path) -> Dictionary:
    lexicon = json.loads((data_dir / "lexicon.json").read_text(encoding="utf-8"))
    rows = []
    with (data_dir / "parallel_sentences.jsonl").open(encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                rows.append(json.loads(line))
    return Dictionary(lexicon, rows, Index.build(lexicon, rows))
