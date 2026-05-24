"""Atomic comparison primitives used by the scorer. Pure, no I/O."""

from __future__ import annotations

from typing import Any


def enum_match(predicted: Any, truth: Any) -> bool:
    """Exact match for single-valued (enum / bool) fields."""
    return predicted == truth


def set_prf(
    predicted: list[Any] | None, truth: list[Any] | None
) -> tuple[float, float, float]:
    """Set precision / recall / F1 for list-valued (enum-list) fields.

    Two empty lists count as a perfect match (1, 1, 1).
    """
    pred_set = set(predicted or [])
    truth_set = set(truth or [])
    if not pred_set and not truth_set:
        return 1.0, 1.0, 1.0

    true_positives = len(pred_set & truth_set)
    precision = true_positives / len(pred_set) if pred_set else 0.0
    recall = true_positives / len(truth_set) if truth_set else 0.0
    denom = precision + recall
    f1 = (2 * precision * recall / denom) if denom else 0.0
    return precision, recall, f1
