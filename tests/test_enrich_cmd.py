"""Integration-style tests for the `enrich` command and its pure helpers.

No network and no LibreOffice: the Anthropic client, PDF upload, and the API call
are monkeypatched; the pptx→PDF step is either bypassed (--pdf) or patched to fail."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from slide_tagger import cli
from slide_tagger.cli import _finalize_enrich, main
from slide_tagger.extractors.render.soffice import LibreOfficeNotFound
from slide_tagger.schema.tagged import DeckTag, blank_tag
from slide_tagger.extractors.structural.pptx_parser import parse_pptx

_ROOT = Path(__file__).resolve().parents[1]
_PROMPT = _ROOT / "docs" / "deck_tagging_prompt.md"


def _load_sample_builder():
    spec = importlib.util.spec_from_file_location(
        "make_sample_deck", _ROOT / "scripts" / "make_sample_deck.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["make_sample_deck"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def sample_pptx(tmp_path_factory):
    builder = _load_sample_builder()
    path = tmp_path_factory.mktemp("enrichdeck") / "sample.pptx"
    builder.build(path)
    return path


class _FakeAnthropic:
    """Only `beta.files.delete` is exercised (upload/enrich are patched separately)."""

    def __init__(self, *a, **k) -> None:
        self.beta = SimpleNamespace(files=SimpleNamespace(delete=lambda fid: None))


def _patch_api(monkeypatch, enriched: dict, changes: list[str]):
    monkeypatch.setattr("anthropic.Anthropic", _FakeAnthropic, raising=False)
    monkeypatch.setattr(cli, "upload_pdf", lambda client, pdf: "file_fake")
    monkeypatch.setattr(
        cli, "enrich_once", lambda *a, **k: (dict(enriched), list(changes))
    )


def test_finalize_enrich_flags_low_confidence(sample_pptx):
    template_core = blank_tag(parse_pptx(sample_pptx)).model_dump(mode="json")
    artifact = SimpleNamespace(version="abc123def456")
    enriched = {"client_industry": "Tech", "slides": []}
    changes = ["geography='X'→null", "slide0.slide_purpose='Y'→null"]

    tag = _finalize_enrich(enriched, template_core, changes, artifact, "test-model")

    assert tag.provenance.prompt_version == "abc123def456"
    assert tag.provenance.enriched_by_model == "test-model"
    assert tag.provenance.tagged_by == "auto:test-model"
    low = tag.provenance.low_confidence_fields
    assert "geography" in low  # invented enum (from sanitizer changes)
    assert "slide0.slide_purpose" in low  # invented enum on a slide
    assert "client_industry" not in low  # it was filled


def test_enrich_writes_valid_stamped_json(sample_pptx, tmp_path, monkeypatch):
    _patch_api(monkeypatch, {"client_industry": "Tech", "slides": []}, [])
    out = tmp_path / "out.tagged.json"
    pdf = tmp_path / "dummy.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")

    rc = main(["enrich", str(sample_pptx), "--pdf", str(pdf), "--prompt", str(_PROMPT),
               "--out", str(out), "--quiet"])

    assert rc == 0
    data = json.loads(out.read_text(encoding="utf-8"))
    data.pop("_legend", None)
    tag = DeckTag.model_validate(data)  # validates against the schema
    assert len(tag.provenance.prompt_version) == 12
    assert tag.provenance.enriched_by_model == "claude-opus-4-7"
    # structural fields were re-imposed from the template (merge guard)
    assert tag.source_filename == "sample.pptx"
    assert tag.slide_count == len(parse_pptx(sample_pptx).slides)


def test_enrich_into_corpus(sample_pptx, tmp_path, monkeypatch):
    _patch_api(monkeypatch, {"client_industry": "Tech", "slides": []}, [])
    corpus = tmp_path / "corpus"
    rc = main(["enrich", str(sample_pptx), "--pdf", str(_mk_pdf(tmp_path)),
               "--prompt", str(_PROMPT), "--out", str(tmp_path / "o.json"),
               "--into-corpus", "--corpus-dir", str(corpus), "--quiet"])
    assert rc == 0
    dest = corpus / "sample.tagged.json"
    assert dest.exists()
    data = json.loads(dest.read_text(encoding="utf-8"))
    data.pop("_legend", None)
    DeckTag.model_validate(data)  # corpus copy is valid too


def test_enrich_no_libreoffice_errors(sample_pptx, tmp_path, monkeypatch):
    _patch_api(monkeypatch, {"slides": []}, [])

    def _boom(pptx, out_dir):
        raise LibreOfficeNotFound("no soffice")

    monkeypatch.setattr(cli, "_convert_pptx_to_pdf", _boom)
    # no --pdf → must convert → LibreOffice missing → clean exit code 2
    rc = main(["enrich", str(sample_pptx), "--prompt", str(_PROMPT),
               "--out", str(tmp_path / "o.json"), "--quiet"])
    assert rc == 2


def _mk_pdf(tmp_path: Path) -> Path:
    p = tmp_path / "dummy2.pdf"
    p.write_bytes(b"%PDF-1.4 fake")
    return p
