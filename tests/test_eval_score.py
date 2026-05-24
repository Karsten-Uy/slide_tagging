"""Tests for the scorer: a predicted DeckTag is scored against a ground-truth one
with known, deliberate differences."""

from __future__ import annotations

import json

from slide_tagger.cli import main as cli_main
from slide_tagger.eval import score_corpus, score_deck
from slide_tagger.schema.tagged import DeckTag


def _density(word_count: int, visual_elements: int, bucket: str) -> dict:
    return {
        "word_count": word_count,
        "text_blocks": 1,
        "visual_elements": visual_elements,
        "whitespace_ratio_est": 0.7,
        "bucket": bucket,
    }


def _truth_dict() -> dict:
    return {
        "source_filename": "d.pptx",
        "source_format": "pptx",
        "slide_count": 2,
        "deck_length": 2,
        "client_industry": "Tech",
        "audience_level": "Senior executives",
        "content_area": ["Strategy", "AI/ML"],
        "deck_summary_one_sentence": "A deck about strategy.",
        "slides": [
            {
                "index": 0,
                "title_text": "Intro",
                "density": _density(5, 0, "sparse"),
                "slide_purpose": "Title",
                "message_type": "Assertion",
                "dominant_visual_element": "Pure text",
                "embedded_data_present": False,
                "slot_types_present": ["title", "subtitle"],
                "main_message": "Welcome",
            },
            {
                "index": 1,
                "title_text": "Revenue up",
                "density": _density(40, 1, "balanced"),
                "slide_purpose": "Finding",
                "message_type": "Trend over time",
                "dominant_visual_element": "Chart",
                "chart_type": "Bar",
                "embedded_data_present": True,
                "slot_types_present": ["title", "chart"],
                "main_message": "Revenue grew",
            },
        ],
    }


def _tag(d: dict) -> DeckTag:
    return DeckTag.model_validate(d)


def test_score_perfect_match():
    corpus = score_corpus([score_deck(_tag(_truth_dict()), _tag(_truth_dict()), "d")])
    assert corpus.headline_accuracy == 1.0
    assert corpus.structural_diffs == []


def test_score_detects_wrong_enum_and_confusion():
    pred = _truth_dict()
    pred["audience_level"] = "C-suite / board"  # wrong; truth is "Senior executives"
    ds = score_deck(_tag(pred), _tag(_truth_dict()), "d")
    res = ds.results["audience_level"]
    assert res.scored == 1
    assert res.correct == 0
    assert res.confusions[("C-suite / board", "Senior executives")] == 1


def test_score_enum_list_partial():
    pred = _truth_dict()
    pred["content_area"] = ["Strategy"]  # missing "AI/ML"
    ds = score_deck(_tag(pred), _tag(_truth_dict()), "d")
    res = ds.results["content_area"]
    assert res.correct == 0
    assert res.mean_f1 is not None and 0.66 < res.mean_f1 < 0.67


def test_score_structural_diff_detected():
    pred = _truth_dict()
    pred["slides"][0]["density"]["word_count"] = 999  # VLM mutated a Pipeline A field
    ds = score_deck(_tag(pred), _tag(_truth_dict()), "d")
    assert any("slides[0].density" in d for d in ds.structural_diffs)


def test_score_slide_enum_paired_by_index():
    pred = _truth_dict()
    pred["slides"][1]["message_type"] = "Assertion"  # wrong; truth is "Trend over time"
    ds = score_deck(_tag(pred), _tag(_truth_dict()), "d")
    res = ds.results["message_type"]
    assert res.scored == 2  # both slides have message_type in truth
    assert res.correct == 1  # slide 0 right, slide 1 wrong


def test_cli_score(tmp_path, capsys):
    truth_path = tmp_path / "truth.json"
    pred_path = tmp_path / "pred.json"
    truth_path.write_text(json.dumps(_truth_dict()), encoding="utf-8")
    pred = _truth_dict()
    pred["audience_level"] = "C-suite / board"
    pred_path.write_text(json.dumps(pred), encoding="utf-8")

    rc = cli_main(["score", str(pred_path), str(truth_path)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Semantic accuracy" in out
    assert "audience_level" in out
