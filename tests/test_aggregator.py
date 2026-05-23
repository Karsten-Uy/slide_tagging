"""Tests for deck-level aggregation (the DECK SUMMARY grounding block)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

from slide_tagger.extractors.structural.aggregator import summarize_deck
from slide_tagger.extractors.structural.pptx_parser import parse_pptx
from slide_tagger.schema.enums import DensityBucket

_ROOT = Path(__file__).resolve().parents[1]


def _load_sample_builder():
    spec = importlib.util.spec_from_file_location(
        "make_sample_deck", _ROOT / "scripts" / "make_sample_deck.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["make_sample_deck"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def summary(tmp_path_factory):
    builder = _load_sample_builder()
    path = tmp_path_factory.mktemp("deck") / "sample.pptx"
    builder.build(path)
    return summarize_deck(parse_pptx(path))


def test_counts(summary):
    assert summary.slide_count == 4
    assert summary.slides_with_charts == 1
    assert summary.slides_with_tables == 0
    assert summary.slides_with_images == 0


def test_density_distribution_sums_to_slide_count(summary):
    assert set(summary.density_distribution) == set(DensityBucket)
    assert sum(summary.density_distribution.values()) == summary.slide_count


def test_avg_word_count(summary):
    # title(8) + bullets(28) + chart-title(5) + appendix(1) = 42 / 4 = 10.5
    assert summary.avg_word_count == pytest.approx(10.5, abs=0.6)


def test_dominant_title_position_present(summary):
    assert summary.dominant_title_position is not None
