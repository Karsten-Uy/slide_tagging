"""Tests for the Web-UI paste harness (slide_tagger.paste + the 4 CLI commands).

No network: we never hit Claude.ai. The "VLM reply" is a hand-crafted JSON dict
that mimics what a real model would return after seeing the paste bundle. The
full flow (pack → ingest → score-paste → compare-paste) runs against a freshly
built sample .pptx, so every public API surface is exercised end-to-end."""

from __future__ import annotations

import importlib.util
import io
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from slide_tagger import cli, paste
from slide_tagger.cli import _build_template, main
from slide_tagger.extractors.structural.pptx_parser import parse_pptx
from slide_tagger.prompt_source import resolve_prompt
from slide_tagger.schema.tagged import DeckTag

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
    path = tmp_path_factory.mktemp("pastedeck") / "sample.pptx"
    builder.build(path)
    return path


def _fake_vlm_reply(template: dict) -> dict:
    """A 'model response' that fills the core enrichment fields plausibly.
    Mirrors what a real VLM would write back after seeing the template."""
    deck = {k: v for k, v in template.items() if k != "_legend"}
    deck.update(
        client_industry="Tech",
        client_type="Private F500",
        engagement_stage="Mid-project readout",
        content_area=["Strategy"],
        audience_level="Senior executives",
        geography="Global",
        deck_summary_one_sentence="A sample test deck used by the paste harness suite.",
    )
    for s in deck.get("slides", []):
        s["slide_purpose"] = "Finding"
        s["message_type"] = "Assertion"
        s["main_message"] = "Sample finding for slide " + str(s.get("index"))
        s["slide_position_role"] = "Evidence / backup"
        s["dominant_visual_element"] = "Pure text"
    return deck


# --- paste module unit tests ----------------------------------------------------


def test_render_paste_bundle_has_header_and_both_halves(sample_pptx):
    artifact = resolve_prompt(_PROMPT)
    template = _build_template(sample_pptx)
    bundle = paste.render_paste_bundle(
        artifact=artifact, template=template,
        deck_slug="sample", variant="baseline", source_pptx=sample_pptx,
    )
    assert "# deck: sample" in bundle
    assert "# variant: baseline" in bundle
    assert f"# prompt_version: {artifact.version}" in bundle
    assert paste._PASTE_SEPARATOR in bundle
    assert "[FULL SYSTEM PROMPT" in bundle
    assert "[USER MESSAGE]" in bundle
    # The template body is embedded as JSON.
    assert "```json" in bundle
    # _legend is stripped from the embedded template (it's a tagging aid only).
    assert '"_legend"' not in bundle


def test_write_pack_writes_in_md_and_meta(sample_pptx, tmp_path):
    artifact = resolve_prompt(_PROMPT)
    template = _build_template(sample_pptx)
    in_path, meta = paste.write_pack(
        artifact=artifact, template=template,
        deck_slug="sample", variant="v1", source_pptx=sample_pptx, base=tmp_path,
    )
    assert in_path.exists() and in_path.name == "in.md"
    meta_path = in_path.parent / "meta.json"
    assert meta_path.exists()
    on_disk = json.loads(meta_path.read_text(encoding="utf-8"))
    assert on_disk["deck_slug"] == "sample"
    assert on_disk["variant"] == "v1"
    assert on_disk["prompt_version"] == artifact.version
    assert meta.prompt_version == artifact.version


def test_next_run_index_starts_at_one_and_increments(tmp_path):
    vdir = tmp_path / "deck" / "v1"
    vdir.mkdir(parents=True)
    assert paste.next_run_index(vdir) == 1
    (vdir / "run_1.json").write_text("{}")
    (vdir / "run_2.json").write_text("{}")
    (vdir / "run_5.json").write_text("{}")  # gap is fine; next == max + 1
    assert paste.next_run_index(vdir) == 6


def test_read_vlm_output_from_stdin_and_file(tmp_path, monkeypatch):
    payload = '{"client_industry": "Tech", "slides": []}'
    # file path
    p = tmp_path / "reply.json"
    p.write_text(payload, encoding="utf-8")
    assert paste.read_vlm_output(p)["client_industry"] == "Tech"
    # stdin
    monkeypatch.setattr("sys.stdin", io.StringIO(payload))
    assert paste.read_vlm_output("-")["client_industry"] == "Tech"


def test_read_vlm_output_tolerates_fence_and_thinking(tmp_path):
    raw = '<thinking>...</thinking>\n```json\n{"a": 1}\n```\n'
    p = tmp_path / "reply.md"
    p.write_text(raw, encoding="utf-8")
    assert paste.read_vlm_output(p) == {"a": 1}


def test_ingest_run_stamps_paste_provenance(sample_pptx, tmp_path):
    artifact = resolve_prompt(_PROMPT)
    template = _build_template(sample_pptx)
    paste.write_pack(
        artifact=artifact, template=template,
        deck_slug="sample", variant="v1", source_pptx=sample_pptx, base=tmp_path,
    )
    template_core = {k: v for k, v in template.items() if k != "_legend"}
    vlm_out = _fake_vlm_reply(template)
    out_path, record, changes = paste.ingest_run(
        vlm_output=vlm_out, template_core=template_core, artifact=artifact,
        deck_slug="sample", variant="v1", model="claude-ai-web", base=tmp_path,
    )
    assert out_path.exists() and out_path.name == "run_1.json"
    # Provenance carries paste-specific extras + the standard fields.
    prov = record["provenance"]
    assert prov["paste_variant"] == "v1"
    assert prov["paste_run_index"] == 1
    assert prov["prompt_version"] == artifact.version
    assert prov["tagged_by"].startswith("paste:claude-ai-web:v1")
    # Record validates against the schema (so score-paste can consume it).
    DeckTag.model_validate(record)


def test_load_meta_raises_clear_error_when_unpacked(tmp_path):
    with pytest.raises(FileNotFoundError) as excinfo:
        paste.load_meta("unknown-deck", "v1", base=tmp_path)
    msg = str(excinfo.value)
    assert "pack" in msg and "unknown-deck" in msg


# --- CLI end-to-end -------------------------------------------------------------


def test_cli_pack_then_ingest_then_score_paste(sample_pptx, tmp_path, capsys):
    paste_dir = tmp_path / "paste"
    labels_dir = tmp_path / "labels"
    labels_dir.mkdir()
    # Hand-label = the fake VLM reply itself, so score-paste should report ~100%
    # on every scored field (sanity test that the pipeline plumbing is faithful).
    template = _build_template(sample_pptx)
    reply = _fake_vlm_reply(template)
    # The label file needs to be a valid DeckTag — build it via the same path
    # ingest uses (merge + provenance stamp), then write it where score-paste
    # looks for it (reference_data/hand_labels/<deck>.tagged.json).
    artifact = resolve_prompt(_PROMPT)
    from slide_tagger.provenance import build_enriched_record
    label_record = build_enriched_record(
        dict(reply),
        {k: v for k, v in template.items() if k != "_legend"},
        [], artifact, model="hand", tagged_by="hand",
    )
    label_path = labels_dir / "sample.tagged.json"
    label_path.write_text(json.dumps(label_record, indent=2), encoding="utf-8")

    # 1) pack
    rc = main([
        "pack", str(sample_pptx), "--variant", "baseline",
        "--prompt", str(_PROMPT), "--paste-dir", str(paste_dir),
    ])
    assert rc == 0
    assert (paste_dir / "sample" / "baseline" / "in.md").exists()
    assert (paste_dir / "sample" / "baseline" / "meta.json").exists()

    # 2) ingest (from a file)
    reply_path = tmp_path / "reply.json"
    reply_path.write_text(json.dumps(reply), encoding="utf-8")
    rc = main([
        "ingest", "sample", "--variant", "baseline", str(reply_path),
        "--prompt", str(_PROMPT), "--paste-dir", str(paste_dir),
    ])
    assert rc == 0
    assert (paste_dir / "sample" / "baseline" / "run_1.json").exists()

    # 3) score-paste against the hand-label we just wrote
    rc = main([
        "score-paste", "sample", "--variant", "baseline",
        "--labels", str(labels_dir), "--paste-dir", str(paste_dir),
    ])
    assert rc == 0
    out = capsys.readouterr().out
    # The console scorecard includes a headline accuracy line; with self-as-truth
    # it should be perfect (or near it modulo any structural-only diffs).
    assert "accuracy" in out.lower()
    assert (paste_dir / "sample" / "baseline" / "score.md").exists()


def test_cli_ingest_from_stdin(sample_pptx, tmp_path, monkeypatch):
    paste_dir = tmp_path / "paste"
    template = _build_template(sample_pptx)
    reply = _fake_vlm_reply(template)

    rc = main([
        "pack", str(sample_pptx), "--variant", "v-stdin",
        "--prompt", str(_PROMPT), "--paste-dir", str(paste_dir),
    ])
    assert rc == 0

    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(reply)))
    rc = main([
        "ingest", "sample", "--variant", "v-stdin", "-",
        "--prompt", str(_PROMPT), "--paste-dir", str(paste_dir),
    ])
    assert rc == 0
    assert (paste_dir / "sample" / "v-stdin" / "run_1.json").exists()


def test_cli_compare_paste_reports_per_field_delta(sample_pptx, tmp_path, capsys):
    paste_dir = tmp_path / "paste"
    labels_dir = tmp_path / "labels"
    labels_dir.mkdir()

    template = _build_template(sample_pptx)
    artifact = resolve_prompt(_PROMPT)
    from slide_tagger.provenance import build_enriched_record

    reply_good = _fake_vlm_reply(template)
    # variant 'bad' = same shape but with a wrong slide_purpose so it scores lower
    reply_bad = json.loads(json.dumps(reply_good))
    for s in reply_bad["slides"]:
        s["slide_purpose"] = "Title"  # wrong on purpose
    label_record = build_enriched_record(
        dict(reply_good),
        {k: v for k, v in template.items() if k != "_legend"},
        [], artifact, model="hand", tagged_by="hand",
    )
    (labels_dir / "sample.tagged.json").write_text(
        json.dumps(label_record, indent=2), encoding="utf-8"
    )

    # Two variants, each ingested once.
    for variant, reply in [("good", reply_good), ("bad", reply_bad)]:
        main(["pack", str(sample_pptx), "--variant", variant,
              "--prompt", str(_PROMPT), "--paste-dir", str(paste_dir)])
        rp = tmp_path / f"reply_{variant}.json"
        rp.write_text(json.dumps(reply), encoding="utf-8")
        main(["ingest", "sample", "--variant", variant, str(rp),
              "--prompt", str(_PROMPT), "--paste-dir", str(paste_dir)])

    capsys.readouterr()  # drain pack/ingest stderr
    rc = main([
        "compare-paste", "sample", "--variants", "good,bad",
        "--labels", str(labels_dir), "--paste-dir", str(paste_dir),
    ])
    assert rc == 0
    out = capsys.readouterr().out
    assert "compare-paste" in out
    assert "good" in out and "bad" in out
    # The bad variant flipped every slide's slide_purpose, so the per-field row
    # must show 1.000 -> 0.000 (a -1.000 delta) for that field specifically.
    purpose_line = next(line for line in out.splitlines() if line.startswith("slide_purpose"))
    assert "1.000" in purpose_line and "0.000" in purpose_line and "-1.000" in purpose_line
