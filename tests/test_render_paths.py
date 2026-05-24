"""Tests for the render path convention and the template command's path attachment.

These are pure / CLI-level tests with no LibreOffice or poppler dependency.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

from slide_tagger.cli import main as cli_main
from slide_tagger.extractors.render.paths import (
    deck_slug,
    render_rel_path,
    thumb_rel_path,
)

_ROOT = Path(__file__).resolve().parents[1]


def _load_sample_builder():
    spec = importlib.util.spec_from_file_location(
        "make_sample_deck", _ROOT / "scripts" / "make_sample_deck.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["make_sample_deck"] = module
    spec.loader.exec_module(module)
    return module


def test_deck_slug_normalizes():
    assert deck_slug("PwC Global Top 100 (2023).pptx") == "pwc-global-top-100-2023"
    assert deck_slug("My Deck.pptx") == "my-deck"
    assert deck_slug("  spaced  name .pptx") == "spaced-name"
    assert deck_slug("UPPER_snake.PPTX") == "upper-snake"


def test_deck_slug_fallback():
    # A stem with no alphanumerics falls back to "deck".
    assert deck_slug("___.pptx") == "deck"
    assert deck_slug("   .pptx") == "deck"


def test_rel_paths_zero_padded_and_separated():
    assert render_rel_path("d", 0) == "d/slide_000.png"
    assert render_rel_path("d", 12) == "d/slide_012.png"
    assert thumb_rel_path("d", 0) == "d/thumb/slide_000.png"
    assert thumb_rel_path("d", 125) == "d/thumb/slide_125.png"


def test_template_attaches_render_paths(tmp_path, capsys):
    builder = _load_sample_builder()
    deck = tmp_path / "My Deck.pptx"
    builder.build(deck)

    rc = cli_main(["template", str(deck)])
    assert rc == 0

    data = json.loads(capsys.readouterr().out)
    slides = data["slides"]
    assert len(slides) == 4
    assert slides[0]["render_path"] == "my-deck/slide_000.png"
    assert slides[0]["thumbnail_path"] == "my-deck/thumb/slide_000.png"
    assert slides[3]["render_path"] == "my-deck/slide_003.png"
    assert slides[3]["thumbnail_path"] == "my-deck/thumb/slide_003.png"
