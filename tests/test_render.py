"""Tests for the render step: LibreOffice discovery (mocked), PDF rasterization,
and an end-to-end render. The rasterize / e2e tests skip when poppler or
LibreOffice are not installed, so CI without them still passes.
"""

from __future__ import annotations

import importlib.util
import shutil
import sys
from pathlib import Path

import pytest
from PIL import Image

from slide_tagger.extractors.render import render_deck
from slide_tagger.extractors.render.rasterize import pdf_to_pngs
from slide_tagger.extractors.render.soffice import (
    LibreOfficeNotFound,
    find_soffice,
)

_ROOT = Path(__file__).resolve().parents[1]
_SOFFICE_MOD = "slide_tagger.extractors.render.soffice"


def _poppler_available() -> bool:
    return shutil.which("pdftoppm") is not None


def _soffice_available() -> bool:
    try:
        find_soffice()
        return True
    except LibreOfficeNotFound:
        return False


def _load_sample_builder():
    spec = importlib.util.spec_from_file_location(
        "make_sample_deck", _ROOT / "scripts" / "make_sample_deck.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["make_sample_deck"] = module
    spec.loader.exec_module(module)
    return module


# --- LibreOffice discovery (no real binary needed) ---


def test_find_soffice_uses_env(tmp_path, monkeypatch):
    fake = tmp_path / "soffice.exe"
    fake.write_text("x")
    monkeypatch.setenv("LIBREOFFICE_PATH", str(fake))
    assert find_soffice() == str(fake)


def test_find_soffice_env_not_a_file(monkeypatch):
    monkeypatch.setenv("LIBREOFFICE_PATH", "Z:/nope/soffice.exe")
    with pytest.raises(LibreOfficeNotFound):
        find_soffice()


def test_find_soffice_falls_back_to_path(tmp_path, monkeypatch):
    monkeypatch.delenv("LIBREOFFICE_PATH", raising=False)
    fake = str(tmp_path / "soffice")
    monkeypatch.setattr(
        f"{_SOFFICE_MOD}.shutil.which", lambda name: fake if name == "soffice" else None
    )
    assert find_soffice() == fake


def test_find_soffice_not_found(monkeypatch):
    monkeypatch.delenv("LIBREOFFICE_PATH", raising=False)
    monkeypatch.setattr(f"{_SOFFICE_MOD}.shutil.which", lambda name: None)
    monkeypatch.setattr(f"{_SOFFICE_MOD}._WINDOWS_DEFAULT", Path("Z:/nope/soffice.exe"))
    with pytest.raises(LibreOfficeNotFound):
        find_soffice()


# --- PDF -> PNG rasterization (needs poppler) ---


@pytest.mark.skipif(not _poppler_available(), reason="poppler (pdftoppm) not installed")
def test_pdf_to_pngs_writes_full_and_thumb(tmp_path):
    page1 = Image.new("RGB", (800, 600), "white")
    page2 = Image.new("RGB", (800, 600), "navy")
    pdf = tmp_path / "doc.pdf"
    page1.save(pdf, save_all=True, append_images=[page2])

    out = tmp_path / "renders"
    results = pdf_to_pngs(pdf, out, "mydeck", dpi=72, thumb_px=128)

    assert [r[0] for r in results] == [0, 1]
    assert (out / "mydeck" / "slide_000.png").is_file()
    assert (out / "mydeck" / "slide_001.png").is_file()
    assert (out / "mydeck" / "thumb" / "slide_000.png").is_file()

    thumb = Image.open(out / "mydeck" / "thumb" / "slide_000.png")
    assert max(thumb.size) <= 128


@pytest.mark.skipif(not _poppler_available(), reason="poppler (pdftoppm) not installed")
def test_pdf_to_pngs_only_index(tmp_path):
    pages = [Image.new("RGB", (400, 300), c) for c in ("white", "navy", "green")]
    pdf = tmp_path / "doc.pdf"
    pages[0].save(pdf, save_all=True, append_images=pages[1:])

    out = tmp_path / "renders"
    results = pdf_to_pngs(pdf, out, "d", dpi=72, only_index=1)

    assert [r[0] for r in results] == [1]
    assert (out / "d" / "slide_001.png").is_file()
    assert not (out / "d" / "slide_000.png").exists()


# --- End-to-end (needs LibreOffice + poppler) ---


@pytest.mark.skipif(
    not (_soffice_available() and _poppler_available()),
    reason="LibreOffice and/or poppler not installed",
)
def test_render_deck_end_to_end(tmp_path):
    builder = _load_sample_builder()
    deck = tmp_path / "sample.pptx"
    builder.build(deck)

    out = tmp_path / "renders"
    result = render_deck(deck, out_root=out)

    assert result.deck_slug == "sample"
    assert len(result.slides) == 4
    for slide in result.slides:
        assert (out / slide.render_path).is_file()
        assert (out / slide.thumbnail_path).is_file()
