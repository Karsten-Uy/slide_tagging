"""Tests for the full tagged-record schema and the template/validate helpers."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from slide_tagger.extractors.structural.pptx_parser import parse_pptx
from slide_tagger.schema.enums import (
    DeckType,
    DominantVisualMode,
    LayoutArchetype,
    NarrativeStructure,
    SlideRole,
    StyleArchetype,
)
from slide_tagger.schema.tagged import DeckTag, SlideTag, blank_tag, legend

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


def test_blank_tag_preserves_structural_clears_semantic(deck):
    tag = blank_tag(deck)
    assert tag.slide_count == deck.slide_count
    assert tag.deck_type is None
    for s, src in zip(tag.slides, deck.slides):
        # structural carried over
        assert s.density.word_count == src.density.word_count
        assert s.has_chart == src.has_chart
        # semantic blank
        assert s.role is None
        assert s.layout_archetype is None
        assert s.core_message is None
        assert s.emphasis_techniques == []


def test_legend_lists_all_fields():
    leg = legend()
    assert set(leg) == {
        "deck_type",
        "style_archetype",
        "narrative_structure",
        "dominant_visual_mode",
        "role",
        "layout_archetype",
        "emphasis_techniques",
        "design_system.grid",
        "design_system.recurring_elements[].type",
    }
    assert leg["role"] == [e.value for e in SlideRole]
    assert all(values for values in leg.values())


def test_filled_tag_validates(deck):
    tag = blank_tag(deck)
    tag.deck_type = DeckType.REPORT
    tag.style_archetype = StyleArchetype.CORPORATE
    tag.narrative_structure = NarrativeStructure.DATA_LED_CONCLUSION
    tag.dominant_visual_mode = DominantVisualMode.DATA_LED
    tag.slides[0].role = SlideRole.TITLE
    tag.slides[0].layout_archetype = LayoutArchetype.TITLE_CENTERED
    tag.slides[0].core_message = "Q3 business review."
    # round-trips through JSON and re-validates
    restored = DeckTag.model_validate_json(tag.model_dump_json())
    assert restored.deck_type == DeckType.REPORT
    assert restored.slides[0].role == SlideRole.TITLE


def test_bad_enum_value_rejected():
    with pytest.raises(ValidationError):
        SlideTag(index=0, density={"word_count": 1, "text_blocks": 1,
                                   "visual_elements": 0, "whitespace_ratio_est": 0.5,
                                   "bucket": "sparse"}, role="headline")
