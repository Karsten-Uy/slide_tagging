"""Tests for Pipeline A's structural extraction against a generated sample deck."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

from slide_tagger.extractors.structural.density import density_bucket
from slide_tagger.extractors.structural.pptx_parser import parse_pptx
from slide_tagger.schema.enums import DensityBucket, SourceFormat

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
def deck(tmp_path_factory):
    builder = _load_sample_builder()
    path = tmp_path_factory.mktemp("deck") / "sample.pptx"
    builder.build(path)
    return parse_pptx(path)


def test_deck_level(deck):
    assert deck.source_format == SourceFormat.PPTX
    assert deck.slide_count == 4
    assert len(deck.slides) == 4
    assert deck.source_filename.endswith(".pptx")


def test_title_slide_is_sparse(deck):
    s0 = deck.slides[0]
    assert s0.title_text == "Q3 Business Review"
    assert s0.density.visual_elements == 0
    assert s0.density.bucket == DensityBucket.SPARSE


def test_content_slide_has_multiple_text_blocks(deck):
    s1 = deck.slides[1]
    assert s1.title_text == "Priorities for next quarter"
    assert s1.density.text_blocks >= 2
    assert s1.density.word_count > 5


def test_chart_slide_detected(deck):
    chart_slides = [s for s in deck.slides if s.has_chart]
    assert len(chart_slides) == 1
    assert chart_slides[0].density.visual_elements >= 1
    assert chart_slides[0].image_count == 0


def test_whitespace_ratio_in_range(deck):
    for s in deck.slides:
        assert 0.0 <= s.density.whitespace_ratio_est <= 1.0


def test_density_bucket_thresholds():
    assert density_bucket(0, 0) == DensityBucket.SPARSE
    assert density_bucket(19, 0) == DensityBucket.SPARSE
    assert density_bucket(20, 0) == DensityBucket.BALANCED
    assert density_bucket(50, 0) == DensityBucket.DENSE
    assert density_bucket(91, 0) == DensityBucket.VERY_DENSE
    assert density_bucket(5, 6) == DensityBucket.VERY_DENSE
