"""Web-UI testing harness for Pipeline B prompt iteration ($0 cost).

Same prompt + same template + same record-assembly as `enrich`/`bench`, but runs
against the Claude.ai web UI instead of the API — so prompt / grounding / pre-fill
tweaks can be A/B-tested without paying per call. The harness wraps the existing
`resolve_prompt` → paste-into-claude.ai → capture-JSON → `merge_structural` →
`score` loop, records run numbers per variant, and stamps provenance so paste-run
records are scorable by the same `eval` modules that score API runs.

Layout: `data/paste/<deck-slug>/<variant>/`
  - `in.md`       paste bundle (system prompt + user message + template)
  - `meta.json`   pack metadata (prompt_version, source_pptx, pack_time_utc, …)
  - `run_N.json`  captured VLM outputs after `ingest` (1-indexed, monotonic)
  - `score.md`    last `score-paste` run's report
"""

from __future__ import annotations

import datetime as dt
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from slide_tagger.enrich import extract_json, sanitize_enums
from slide_tagger.prompt_source import PromptArtifact
from slide_tagger.provenance import build_enriched_record

PASTE_DIR_DEFAULT = Path("data/paste")

_PASTE_SEPARATOR = "# -------- PASTE START --------"
_USER_INSTRUCTION = (
    "Here is the partial structural JSON (input.json) to enrich. "
    "The source deck is the attached PDF. Enrich every null field per "
    "your instructions and return ONLY the resulting JSON:"
)
_RUN_RE = re.compile(r"^run_(\d+)\.json$")


@dataclass
class PasteMeta:
    """What `pack` writes alongside `in.md` so later commands (ingest/score-paste)
    can stamp provenance correctly without re-deriving anything."""

    deck_slug: str
    variant: str
    prompt_version: str
    prompt_source: str
    source_pptx: str
    pack_time_utc: str


def variant_dir(deck_slug: str, variant: str, base: Path = PASTE_DIR_DEFAULT) -> Path:
    """Per-variant output directory: `base/<deck>/<variant>/`."""
    return base / deck_slug / variant


def _now_utc_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def render_paste_bundle(
    *,
    artifact: PromptArtifact,
    template: dict[str, Any],
    deck_slug: str,
    variant: str,
    source_pptx: Path,
    pack_time_utc: str | None = None,
) -> str:
    """Format the single paste-ready bundle: a header (deck/variant/prompt_version +
    workflow notes, all in `#` comments so it's clearly out-of-band), then the
    system prompt body, then the user-message + template — exactly the two halves
    `enrich_once` sends to the API, so the web-UI conversation matches the API
    call as closely as possible. Pure function — no I/O — so it's easy to test.
    """
    template_core = {k: v for k, v in template.items() if k != "_legend"}
    template_json = json.dumps(template_core, ensure_ascii=False, indent=2, sort_keys=True)
    pack_time = pack_time_utc or _now_utc_iso()

    header_lines = [
        f"# deck: {deck_slug}",
        f"# variant: {variant}",
        f"# prompt_version: {artifact.version}",
        f"# prompt_source: {artifact.source}",
        f"# source_pptx: {source_pptx}",
        f"# pack_time_utc: {pack_time}",
        "#",
        "# Workflow:",
        "#   1. Open Claude.ai in a fresh chat (or a Project where the system",
        "#      prompt is preloaded — then SKIP the [FULL SYSTEM PROMPT] block).",
        f"#   2. Attach the deck PDF: {source_pptx.with_suffix('.pdf')}",
        "#   3. Paste everything below this line.",
        "#   4. Save the model's JSON reply (or copy it to clipboard), then run:",
        f"#        slide-tagger ingest {deck_slug} --variant {variant} <reply.json>",
        "#      or pipe via stdin (macOS: pbpaste, Linux: xclip -o, Windows PowerShell: Get-Clipboard):",
        f"#        Get-Clipboard | slide-tagger ingest {deck_slug} --variant {variant} -",
    ]
    return (
        "\n".join(header_lines)
        + f"\n{_PASTE_SEPARATOR}\n\n"
        + "[FULL SYSTEM PROMPT — skip if you've preloaded it as a Claude.ai Project instruction]\n\n"
        + artifact.text.rstrip()
        + "\n\n[USER MESSAGE]\n\n"
        + _USER_INSTRUCTION
        + f"\n\n```json\n{template_json}\n```\n"
    )


def write_pack(
    *,
    artifact: PromptArtifact,
    template: dict[str, Any],
    deck_slug: str,
    variant: str,
    source_pptx: Path,
    base: Path = PASTE_DIR_DEFAULT,
) -> tuple[Path, PasteMeta]:
    """Build the paste bundle + meta and write them under `base/<deck>/<variant>/`.
    Returns `(in.md path, PasteMeta)`. Overwrites `in.md` and `meta.json` if a
    variant is re-packed; existing `run_*.json` are untouched."""
    vdir = variant_dir(deck_slug, variant, base)
    vdir.mkdir(parents=True, exist_ok=True)

    pack_time = _now_utc_iso()
    bundle = render_paste_bundle(
        artifact=artifact, template=template, deck_slug=deck_slug,
        variant=variant, source_pptx=source_pptx, pack_time_utc=pack_time,
    )
    in_path = vdir / "in.md"
    in_path.write_text(bundle, encoding="utf-8")

    meta = PasteMeta(
        deck_slug=deck_slug, variant=variant,
        prompt_version=artifact.version, prompt_source=artifact.source,
        source_pptx=str(source_pptx), pack_time_utc=pack_time,
    )
    (vdir / "meta.json").write_text(
        json.dumps(asdict(meta), indent=2) + "\n", encoding="utf-8"
    )
    return in_path, meta


def next_run_index(vdir: Path) -> int:
    """Auto-incrementing run number (1-indexed) for the next `ingest`."""
    nums: list[int] = []
    if vdir.is_dir():
        for f in vdir.glob("run_*.json"):
            m = _RUN_RE.match(f.name)
            if m:
                nums.append(int(m.group(1)))
    return (max(nums) + 1) if nums else 1


def read_vlm_output(source: str | Path) -> dict[str, Any]:
    """Read the VLM output as a dict. `source` may be a file path, '-' for stdin,
    or any path-like. Reuses `enrich.extract_json` so a ```json fence, leading
    `<thinking>` wrapper, or surrounding prose is tolerated."""
    if str(source) == "-":
        text = sys.stdin.read()
    else:
        text = Path(source).read_text(encoding="utf-8")
    return extract_json(text)


def load_meta(deck_slug: str, variant: str, base: Path = PASTE_DIR_DEFAULT) -> PasteMeta:
    """Load the `meta.json` written by `write_pack`. Raises FileNotFoundError with
    a clear message if the variant wasn't packed."""
    meta_path = variant_dir(deck_slug, variant, base) / "meta.json"
    if not meta_path.exists():
        raise FileNotFoundError(
            f"No paste bundle for deck={deck_slug!r} variant={variant!r} at {meta_path}. "
            f"Run `slide-tagger pack {deck_slug} --variant {variant}` first."
        )
    return PasteMeta(**json.loads(meta_path.read_text(encoding="utf-8")))


def ingest_run(
    *,
    vlm_output: dict[str, Any],
    template_core: dict[str, Any],
    artifact: PromptArtifact,
    deck_slug: str,
    variant: str,
    model: str = "claude-ai-web",
    tagged_by: str | None = None,
    base: Path = PASTE_DIR_DEFAULT,
) -> tuple[Path, dict[str, Any], list[str]]:
    """Sanitize the VLM output, merge Pipeline A structural fields back on, stamp
    provenance (with the paste variant + run index as extras), and write
    `run_N.json`. Returns `(out_path, record, sanitizer_changes)`. Validation of
    the record as a `DeckTag` is the caller's responsibility (so the CLI can
    choose strict-error vs warn-and-write, mirroring `enrich`)."""
    vdir = variant_dir(deck_slug, variant, base)
    vdir.mkdir(parents=True, exist_ok=True)

    sanitized, changes = sanitize_enums(vlm_output)
    n = next_run_index(vdir)
    record = build_enriched_record(
        sanitized, template_core, changes, artifact, model,
        tagged_by=tagged_by or f"paste:{model}:{variant}",
        extra_provenance={"paste_variant": variant, "paste_run_index": n},
    )

    out_path = vdir / f"run_{n}.json"
    out_path.write_text(
        json.dumps(record, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return out_path, record, changes


def list_runs(deck_slug: str, variant: str, base: Path = PASTE_DIR_DEFAULT) -> list[Path]:
    """All `run_N.json` paths for a variant, ordered by N."""
    vdir = variant_dir(deck_slug, variant, base)
    if not vdir.is_dir():
        return []
    runs = []
    for f in vdir.glob("run_*.json"):
        m = _RUN_RE.match(f.name)
        if m:
            runs.append((int(m.group(1)), f))
    runs.sort()
    return [f for _, f in runs]
