"""Tests for the full tagged-record schema and the template/validate helpers."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from slide_tagger.extractors.structural.pptx_parser import parse_pptx
from slide_tagger.schema.enums import (
    AudienceLevel,
    ClientIndustry,
    ClientType,
    ConfidentialityTier,
    ContentArea,
    DeliverableFormat,
    DominantVisualElement,
    EngagementStage,
    Geography,
    MessageType,
    SlidePositionRole,
    SlidePurpose,
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
    # deck_length mirrors the deterministic slide_count
    assert tag.deck_length == deck.slide_count
    # deck-level enrichment blank
    assert tag.client_industry is None
    assert tag.content_area == []
    # inferred_rules / provenance scaffolded but empty
    assert tag.inferred_rules is not None
    assert tag.inferred_rules.title.font_family_observed == []
    assert tag.provenance is not None
    assert tag.provenance.tagged_by is None
    for s, src in zip(tag.slides, deck.slides):
        # structural carried over
        assert s.density.word_count == src.density.word_count
        assert s.has_chart == src.has_chart
        # semantic blank
        assert s.slide_purpose is None
        assert s.message_type is None
        assert s.main_message is None
        assert s.dominant_visual_element is None
        assert s.zones == []
        assert s.slot_types_present == []


def test_legend_lists_all_fields():
    leg = legend()
    assert set(leg) == {
        "client_industry",
        "client_type",
        "engagement_stage",
        "content_area",
        "audience_level",
        "deliverable_format",
        "geography",
        "confidentiality_tier",
        "slide_purpose",
        "message_type",
        "audience_level_slide",
        "slide_position_role",
        "dominant_visual_element",
        "chart_type",
        "placeholder_compliance",
        "slot_types_present",
        "reusability_score_qualitative",
        "tier_match_difficulty",
        "inferred_rules.title.uses_action_titles",
        "inferred_rules.chart_styling.uses_consistent_palette",
        "inferred_rules.layout_conventions.uses_master_template",
        "design_system.grid",
        "design_system.recurring_elements[].type",
    }
    assert leg["slide_purpose"] == [e.value for e in SlidePurpose]
    assert all(values for values in leg.values())


def test_filled_tag_validates(deck):
    tag = blank_tag(deck)
    tag.client_industry = ClientIndustry.FINANCIAL_SERVICES
    tag.client_type = ClientType.PRIVATE_F500
    tag.engagement_stage = EngagementStage.FINAL_DELIVERY
    tag.content_area = [ContentArea.STRATEGY, ContentArea.MARKET_ANALYSIS]
    tag.audience_level = AudienceLevel.C_SUITE_BOARD
    tag.deliverable_format = DeliverableFormat.POWERPOINT
    tag.geography = Geography.GLOBAL
    tag.confidentiality_tier = ConfidentialityTier.PUBLIC
    tag.inferred_publisher = "PwC"
    tag.deck_summary_one_sentence = "Annual ranking of the world's largest companies."
    tag.slides[0].slide_purpose = SlidePurpose.TITLE
    tag.slides[0].message_type = MessageType.ASSERTION
    tag.slides[0].slide_position_role = SlidePositionRole.HERO_HEADLINE
    tag.slides[0].main_message = "Global Top 100 companies by market capitalisation."
    tag.slides[0].dominant_visual_element = DominantVisualElement.PURE_TEXT
    # round-trips through JSON and re-validates
    restored = DeckTag.model_validate_json(tag.model_dump_json())
    assert restored.client_industry == ClientIndustry.FINANCIAL_SERVICES
    assert restored.content_area == [ContentArea.STRATEGY, ContentArea.MARKET_ANALYSIS]
    assert restored.slides[0].slide_purpose == SlidePurpose.TITLE


def test_bad_enum_value_rejected():
    with pytest.raises(ValidationError):
        SlideTag(index=0, density={"word_count": 1, "text_blocks": 1,
                                   "visual_elements": 0, "whitespace_ratio_est": 0.5,
                                   "bucket": "sparse"}, slide_purpose="headline")


def test_provenance_new_fields_backward_compat():
    # an existing hand-label (no new provenance fields) still validates and gets
    # safe defaults — the automated `enrich` additions don't break old records.
    import json

    p = _ROOT / "reference_data" / "hand_labels" / "nigeria-economic-outlook-october-2023-v1.tagged.json"
    data = json.loads(p.read_text(encoding="utf-8"))
    data.pop("_legend", None)
    tag = DeckTag.model_validate(data)
    assert tag.provenance is not None
    assert tag.provenance.low_confidence_fields == []
    assert tag.provenance.prompt_version is None
    assert tag.provenance.enriched_by_model is None
