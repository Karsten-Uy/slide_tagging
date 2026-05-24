"""Tests for the non-API parts of the enrichment automation (slide_tagger.enrich):
enum sanitation and JSON extraction. The API call itself is not unit-tested here."""

from __future__ import annotations

from pathlib import Path

from slide_tagger.enrich import extract_json, prompt_body, sanitize_enums


def test_sanitize_nulls_invalid_deck_and_slide_enums():
    deck = {
        "geography": "Regional (Nigeria)",  # invalid literal
        "audience_level": "C-suite / board",  # valid
        "content_area": ["Strategy", "Bananas"],  # one invalid member
        "slides": [
            {"index": 0, "slide_position_role": "Insight",  # slide_purpose value, invalid here
             "slide_purpose": "Finding",  # valid
             "slot_types_present": ["title", "icon-based"]},  # one invalid member
        ],
    }
    clean, changes = sanitize_enums(deck)
    assert clean["geography"] is None
    assert clean["audience_level"] == "C-suite / board"
    assert clean["content_area"] == ["Strategy"]
    assert clean["slides"][0]["slide_position_role"] is None
    assert clean["slides"][0]["slide_purpose"] == "Finding"
    assert clean["slides"][0]["slot_types_present"] == ["title"]
    # every change is reported
    assert any("geography" in c for c in changes)
    assert any("slide0.slide_position_role" in c for c in changes)
    assert any("content_area" in c for c in changes)


def test_sanitize_leaves_valid_record_untouched():
    deck = {"geography": "Global", "slides": [{"index": 0, "chart_type": "Bar"}]}
    _, changes = sanitize_enums(deck)
    assert changes == []


def test_extract_json_strips_fence_and_thinking():
    raw = '<thinking>let me reason</thinking>\n```json\n{"a": 1, "b": [2, 3]}\n```'
    assert extract_json(raw) == {"a": 1, "b": [2, 3]}


def test_extract_json_handles_surrounding_prose():
    raw = 'Here is the JSON you asked for:\n{"x": "y"}\nLet me know if you need changes.'
    assert extract_json(raw) == {"x": "y"}


def test_prompt_body_extracts_section():
    body = prompt_body(Path("docs/deck_tagging_prompt.md"))
    assert body.startswith("You are an expert")
    assert "## Notes on using this prompt at scale" not in body
    assert "Finding, NOT Data presentation" in body  # v2 edit is in the body
