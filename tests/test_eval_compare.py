"""Tests for the atomic comparison primitives."""

from __future__ import annotations

from slide_tagger.eval.compare import enum_match, set_prf


def test_enum_match():
    assert enum_match("A", "A")
    assert not enum_match("A", "B")
    assert enum_match(None, None)
    assert not enum_match(None, "A")


def test_set_prf_exact():
    assert set_prf(["a", "b"], ["b", "a"]) == (1.0, 1.0, 1.0)


def test_set_prf_partial():
    precision, recall, f1 = set_prf(["a"], ["a", "b"])
    assert precision == 1.0
    assert recall == 0.5
    assert abs(f1 - (2 / 3)) < 1e-9


def test_set_prf_disjoint():
    assert set_prf(["a"], ["b"]) == (0.0, 0.0, 0.0)


def test_set_prf_both_empty():
    assert set_prf([], []) == (1.0, 1.0, 1.0)
    assert set_prf(None, None) == (1.0, 1.0, 1.0)
