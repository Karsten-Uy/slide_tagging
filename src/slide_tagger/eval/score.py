"""Score a predicted (VLM-enriched) DeckTag against a hand-labeled ground-truth
DeckTag, field by field.

Only fields the ground truth actually fills are scored (the hand-label is the
answer key). Enum/bool fields use exact match; enum-list fields use set F1; free
-text fields are collected for side-by-side review, not scored. A structural-
integrity check runs alongside: Pipeline A's fields must be byte-identical between
prediction and truth (the VLM must not touch them).

Note: "valid JSON" and "enum discipline" (rubric items 1 and 3) are enforced
upstream at load time — a file with malformed JSON or an out-of-legend enum value
fails `DeckTag` validation with a precise field error before it ever reaches here.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from slide_tagger.eval.compare import enum_match, set_prf
from slide_tagger.eval.fields import (
    ENUM,
    ENUM_LIST,
    FREE_TEXT,
    SCORED_KINDS,
    STRUCTURAL,
    FIELDS,
    get_by_path,
)
from slide_tagger.schema.tagged import DeckTag


def _is_filled(value: Any) -> bool:
    """A ground-truth field counts as scorable when it carries a value."""
    if value is None:
        return False
    if isinstance(value, (str, list, dict)):
        return len(value) > 0
    return True


@dataclass
class FieldResult:
    path: str
    level: str
    kind: str
    scored: int = 0
    correct: int = 0
    f1_sum: float = 0.0
    confusions: Counter[tuple[Any, Any]] = field(default_factory=Counter)

    @property
    def accuracy(self) -> float | None:
        return self.correct / self.scored if self.scored else None

    @property
    def mean_f1(self) -> float | None:
        return self.f1_sum / self.scored if self.scored else None

    def merge(self, other: "FieldResult") -> None:
        self.scored += other.scored
        self.correct += other.correct
        self.f1_sum += other.f1_sum
        self.confusions.update(other.confusions)


@dataclass
class FreeTextPair:
    path: str
    index: int | None
    predicted: Any
    truth: Any
    deck: str = ""


@dataclass
class DeckScore:
    name: str
    n_slides: int
    results: dict[str, FieldResult]
    free_text: list[FreeTextPair]
    structural_diffs: list[str]


@dataclass
class CorpusScore:
    deck_names: list[str]
    n_slides: int
    results: dict[str, FieldResult]
    free_text: list[FreeTextPair]
    structural_diffs: list[str]

    @property
    def headline_accuracy(self) -> float | None:
        scored = sum(r.scored for r in self.results.values() if r.kind in SCORED_KINDS)
        correct = sum(r.correct for r in self.results.values() if r.kind in SCORED_KINDS)
        return correct / scored if scored else None


def _score_one(result: FieldResult, predicted: Any, truth: Any) -> None:
    """Update a FieldResult with one (predicted, truth) instance where truth is filled."""
    result.scored += 1
    if result.kind == ENUM_LIST:
        _, _, f1 = set_prf(predicted, truth)
        result.f1_sum += f1
        if f1 >= 1.0:
            result.correct += 1
    else:  # ENUM or BOOL
        if enum_match(predicted, truth):
            result.correct += 1
        elif result.kind == ENUM:
            result.confusions[(predicted, truth)] += 1


def score_deck(predicted: DeckTag, truth: DeckTag, name: str = "") -> DeckScore:
    pred_d = predicted.model_dump(mode="json")
    truth_d = truth.model_dump(mode="json")

    pred_slides = {s["index"]: s for s in pred_d.get("slides", [])}
    truth_slides = truth_d.get("slides", [])

    results: dict[str, FieldResult] = {
        s.path: FieldResult(s.path, s.level, s.kind)
        for s in FIELDS
        if s.kind in SCORED_KINDS
    }
    free_text: list[FreeTextPair] = []
    structural_diffs: list[str] = []

    def handle(spec, pred_val, truth_val, index: int | None) -> None:
        if spec.kind in SCORED_KINDS:
            if _is_filled(truth_val):
                _score_one(results[spec.path], pred_val, truth_val)
        elif spec.kind == FREE_TEXT:
            if _is_filled(truth_val) or _is_filled(pred_val):
                free_text.append(FreeTextPair(spec.path, index, pred_val, truth_val, name))
        elif spec.kind == STRUCTURAL:
            if pred_val != truth_val:
                loc = spec.path if index is None else f"slides[{index}].{spec.path}"
                structural_diffs.append(loc)

    for spec in FIELDS:
        if spec.level in ("deck", "element"):
            handle(spec, get_by_path(pred_d, spec.path), get_by_path(truth_d, spec.path), None)
        else:  # slide
            for tslide in truth_slides:
                idx = tslide["index"]
                pslide = pred_slides.get(idx, {})
                handle(spec, get_by_path(pslide, spec.path), get_by_path(tslide, spec.path), idx)

    return DeckScore(
        name=name,
        n_slides=len(truth_slides),
        results=results,
        free_text=free_text,
        structural_diffs=structural_diffs,
    )


def score_corpus(decks: list[DeckScore]) -> CorpusScore:
    merged: dict[str, FieldResult] = {}
    free_text: list[FreeTextPair] = []
    structural_diffs: list[str] = []
    n_slides = 0

    for deck in decks:
        n_slides += deck.n_slides
        for path, res in deck.results.items():
            if path not in merged:
                merged[path] = FieldResult(res.path, res.level, res.kind)
            merged[path].merge(res)
        free_text.extend(deck.free_text)
        structural_diffs.extend(f"{deck.name}: {d}" for d in deck.structural_diffs)

    return CorpusScore(
        deck_names=[d.name for d in decks],
        n_slides=n_slides,
        results=merged,
        free_text=free_text,
        structural_diffs=structural_diffs,
    )
