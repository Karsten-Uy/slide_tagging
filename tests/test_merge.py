"""Tests for the structural-merge guard (slide_tagger.merge)."""

from __future__ import annotations

from slide_tagger.merge import merge_structural


def _template() -> dict:
    return {
        "source_filename": "deck.pptx",
        "source_format": "pptx",
        "slide_count": 2,
        "deck_length": 2,
        "design_system": {
            "title_style": {"font_family": "Arial", "color_hex": "#FFFFFF", "alignment": None},
            "body_style": {"font_family": "Arial"},
            "color_palette": {"primary": "#C00000"},
            "default_text_alignment": "center",
            "grid": None,
            "recurring_elements": [{"phash": "abc", "type": None}],
        },
        "slides": [
            {"index": 0, "title_text": "Curly’s title", "image_count": 1,
             "has_chart": False, "density": {"word_count": 10}},
            {"index": 1, "title_text": "Second", "image_count": 0,
             "has_chart": True, "density": {"word_count": 99}},
        ],
    }


def _vlm() -> dict:
    # VLM kept enrichment but corrupted some structural fields and invented others.
    return {
        "source_filename": "deck.pptx",
        "source_format": "pptx",
        "slide_count": 2,
        "deck_length": 2,
        "client_industry": "Energy",  # enrichment
        "design_system": {
            "title_style": {"font_family": "Arial", "color_hex": "#000000", "alignment": "left"},  # CHANGED
            "body_style": {"font_family": "Comic Sans"},  # CHANGED
            "color_palette": {"primary": "#123456"},  # CHANGED
            "default_text_alignment": "left",  # CHANGED
            "grid": "12-column",  # enrichment (hand-labeled) -> keep
            "recurring_elements": [{"type": "footer", "value": "ACME"}],  # enrichment -> keep
        },
        "slides": [
            {"index": 0, "title_text": "Curly's title", "image_count": 9,  # CHANGED (straight quote + count)
             "has_chart": True, "density": {"word_count": 0},
             "slide_purpose": "Title"},  # enrichment -> keep
            {"index": 1, "title_text": "Edited", "image_count": 5,  # CHANGED
             "has_chart": False, "density": {"word_count": 1},
             "slide_purpose": "Finding"},  # enrichment -> keep
        ],
    }


def test_merge_reimposes_deck_and_design_system_structural():
    out = merge_structural(_vlm(), _template())
    ds = out["design_system"]
    # fonts/colors restored from template
    assert ds["title_style"]["color_hex"] == "#FFFFFF"
    assert ds["title_style"]["alignment"] is None
    assert ds["body_style"]["font_family"] == "Arial"
    assert ds["color_palette"]["primary"] == "#C00000"
    assert ds["default_text_alignment"] == "center"
    # grid + recurring_elements are enrichment -> kept from VLM
    assert ds["grid"] == "12-column"
    assert ds["recurring_elements"] == [{"type": "footer", "value": "ACME"}]


def test_merge_reimposes_per_slide_structural_keeps_enrichment():
    out = merge_structural(_vlm(), _template())
    s0, s1 = out["slides"]
    # structural restored from template (incl. the curly apostrophe)
    assert s0["title_text"] == "Curly’s title"
    assert s0["image_count"] == 1
    assert s0["has_chart"] is False
    assert s0["density"] == {"word_count": 10}
    assert s1["title_text"] == "Second"
    assert s1["has_chart"] is True
    # enrichment preserved
    assert s0["slide_purpose"] == "Title"
    assert s1["slide_purpose"] == "Finding"
    assert out["client_industry"] == "Energy"


def test_merge_does_not_mutate_inputs():
    vlm, tmpl = _vlm(), _template()
    merge_structural(vlm, tmpl)
    assert vlm["slides"][0]["title_text"] == "Curly's title"  # unchanged original
    assert tmpl["slides"][0]["image_count"] == 1
