"""Tests for the prompt-resolution chokepoint (slide_tagger.prompt_source).

The prompt is a file-based artifact tuned by a separate system; both `enrich` and
`bench` resolve it here so they always run the same thing (no train/serve skew)."""

from __future__ import annotations

from pathlib import Path

import pytest

from slide_tagger.prompt_source import PromptArtifact, resolve_prompt

_FAKE = "# Heading\n\n## The Prompt\n\n{body}\n\n## Notes on using this prompt at scale\n\nignored\n"


def _write_prompt(path: Path, body: str) -> Path:
    path.write_text(_FAKE.format(body=body), encoding="utf-8")
    return path


def test_resolve_explicit_path(tmp_path, monkeypatch):
    monkeypatch.delenv("SLIDE_TAGGER_PROMPT", raising=False)
    p = _write_prompt(tmp_path / "prompt.md", "You are a tagger.")
    art = resolve_prompt(p)
    assert isinstance(art, PromptArtifact)
    assert art.text == "You are a tagger."  # body between the two headers
    assert len(art.version) == 12 and all(c in "0123456789abcdef" for c in art.version)
    assert art.source == f"file:{p}"


def test_real_prompt_resolves():
    # the canonical prompt parses and yields a stable 12-char version
    art = resolve_prompt(Path("docs/deck_tagging_prompt.md"))
    assert art.text.startswith("You are an expert")
    assert len(art.version) == 12


def test_env_override(tmp_path, monkeypatch):
    p = _write_prompt(tmp_path / "env_prompt.md", "Env body.")
    monkeypatch.setenv("SLIDE_TAGGER_PROMPT", str(p))
    art = resolve_prompt()  # no explicit path → env wins over default
    assert art.text == "Env body."
    assert art.source == f"file:{p}"


def test_explicit_path_wins_over_env(tmp_path, monkeypatch):
    env_p = _write_prompt(tmp_path / "env.md", "from env")
    arg_p = _write_prompt(tmp_path / "arg.md", "from arg")
    monkeypatch.setenv("SLIDE_TAGGER_PROMPT", str(env_p))
    assert resolve_prompt(arg_p).text == "from arg"


def test_missing_raises(tmp_path, monkeypatch):
    monkeypatch.delenv("SLIDE_TAGGER_PROMPT", raising=False)
    with pytest.raises(FileNotFoundError):
        resolve_prompt(tmp_path / "nope.md")


def test_version_stable_and_content_sensitive(tmp_path, monkeypatch):
    monkeypatch.delenv("SLIDE_TAGGER_PROMPT", raising=False)
    a = _write_prompt(tmp_path / "a.md", "same body")
    b = _write_prompt(tmp_path / "b.md", "same body")
    c = _write_prompt(tmp_path / "c.md", "different body")
    assert resolve_prompt(a).version == resolve_prompt(b).version  # tracks content, not path
    assert resolve_prompt(a).version != resolve_prompt(c).version
