"""Pipeline B eval harness: score VLM-enriched decks against hand-labels.

`score_deck` / `score_corpus` compute per-field accuracy (the prompt-optimization
signal); `report` renders the scorecard. No VLM calls — enriched JSON is produced
manually for now.
"""

from __future__ import annotations

from slide_tagger.eval.score import (
    CorpusScore,
    DeckScore,
    score_corpus,
    score_deck,
)

__all__ = ["CorpusScore", "DeckScore", "score_corpus", "score_deck"]
