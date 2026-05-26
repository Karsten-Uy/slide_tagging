# Automated tagging: the `enrich` command

`slide-tagger enrich <deck.pptx>` takes an **unlabeled** `.pptx` and writes a
finished, schema-valid tagged JSON — Pipeline A (structural) **and** Pipeline B
(semantic enrichment) in one shot, no hand-label required. This is what closes the
"occasionally feed in a deck → update the corpus the MCP server serves" loop.

It is distinct from [`bench`](vlm_prompt_test.md): `bench` is an *eval harness* that
needs a hand-label answer key and runs the prompt N× to measure accuracy/variance.
`enrich` is the *production tagger* — one run, no scoring, writes the record.

## What it runs

```
.pptx ─ parse_pptx ─ blank_tag (Pipeline A structural template, with _legend)
      │
      ├─ resolve_prompt()  ── the file-based system prompt + a content version
      ├─ pptx → PDF (LibreOffice)  ── or supply one with --pdf
      ├─ upload_pdf  ── Files API
      ├─ enrich_once ── Claude API returns enriched JSON (enum-sanitized)
      ├─ merge_structural ── re-imposes Pipeline A fields (the VLM can't corrupt them)
      ├─ confidence + provenance stamp
      └─ DeckTag.validate → write data/tagged/<slug>.tagged.json
```

Every reused step already existed ([`enrich.py`](../src/slide_tagger/enrich.py),
[`merge.py`](../src/slide_tagger/merge.py),
[`extractors/render/soffice.py`](../src/slide_tagger/extractors/render/soffice.py));
the command is in [`cli.py`](../src/slide_tagger/cli.py) (`_cmd_enrich`).

## Prerequisites

- **`ANTHROPIC_API_KEY`** — put it in `.env` (gitignored, auto-loaded) or the
  environment. The `anthropic` SDK is already a dependency.
- **LibreOffice** — used to convert the `.pptx` to the PDF the model reads
  (auto-discovered on PATH, the Windows default install path, or via
  `LIBREOFFICE_PATH`). If it isn't installed, pre-convert the deck and pass
  `--pdf <file>` instead.

## Usage

```bash
# Minimal: tag a deck, write data/tagged/<slug>.tagged.json
uv run slide-tagger enrich data/source/<deck>.pptx

# Skip LibreOffice by supplying a PDF; choose a cheaper model / explicit output
uv run slide-tagger enrich data/source/<deck>.pptx --pdf data/source/<deck>.pdf \
    --model claude-sonnet-4-6 --out data/tagged/<deck>.tagged.json

# Ingest straight into the corpus the MCP server serves (JSON + extracted logos)
uv run slide-tagger enrich data/source/<deck>.pptx --into-corpus

# Inspect what it produced
uv run slide-tagger validate data/tagged/<deck>.tagged.json
```

## The prompt is a swappable, file-based artifact

The enrichment prompt is **not** owned by the tagger. Both `enrich` and `bench`
resolve it through a single chokepoint —
[`prompt_source.resolve_prompt()`](../src/slide_tagger/prompt_source.py) — so you
always run *exactly* what you tuned (no train/serve skew).

Resolution order: `--prompt <path>` → `$SLIDE_TAGGER_PROMPT` →
`docs/deck_tagging_prompt.md` (the default). The returned `PromptArtifact` carries
the prompt text plus a **content hash** (`version`) that is stamped into every deck
it tags.

This keeps prompt-tuning a separate system you can replace later: the tuning loop
([`bench`/`eval`](vlm_prompt_test.md) against
[`reference_data/hand_labels/`](../reference_data/hand_labels/)) just edits the
prompt file the resolver reads; the tagger picks up the new version automatically
and records it. Swapping the prompt *source* (to a registry, an HTTP endpoint, a DB
row) later means editing only `resolve_prompt` — the `enrich`/`bench` callers don't
change.

## Confidence flagging (for unsupervised tagging)

Because there's no human in the loop, each record's `provenance` records what to
spot-review:

| field | meaning |
|---|---|
| `prompt_version` | content hash of the prompt that produced this deck — lets you later find & re-tag decks made with an older prompt |
| `enriched_by_model` | the model used |
| `low_confidence_fields` | fields worth a human glance: enum values the model invented (the sanitizer nulled them) **plus** core enrichment fields left blank after merge |
| `confidence_notes` | one-line summary (counts of nulled enums / flagged fields) |
| `tagged_by` | `auto:<model>` unless `--tagged-by` is given |

`validate` reports completeness as usual; `low_confidence_fields` narrows a review
to just the shaky parts instead of re-reading the whole deck.

## `--into-corpus` and the answer-key boundary

`--into-corpus` copies the tagged JSON into the served corpus dir and runs logo
extraction ([`extract-assets`](manual_tagging.md) logic) into
`<corpus>/assets/<slug>/`, merging the image elements (deduped by pHash) into the
corpus copy. The directory defaults to `$SLIDE_TAGGER_CORPUS_DIR`, else
`../mcp_slide_tagging/corpus` (the deploy snapshot the server reads with
`CORPUS_PATH=corpus`).

> **It never writes to `reference_data/hand_labels/`.** That directory is the eval
> **answer key** — mixing auto-tagged output into it would corrupt scoring. The
> served corpus and the answer key are deliberately separate.

After ingesting, the MCP server picks the deck up:

```bash
cd ../mcp_slide_tagging && CORPUS_PATH=corpus uv run python scripts/poc_demo.py
# the new deck appears in list_decks(); get_deck(<slug>) shows its design system;
# get_deck_assets(<slug>) returns its logo if one was extractable.
```

## Behavior on schema problems

`merge_structural` guarantees the structural fields, so failures here are
non-structural (e.g. an enrichment field the prompt mis-shaped). By default the
command **warns and still writes** the record (a long API call isn't thrown away);
pass `--strict` to exit non-zero instead.

## Flags

| flag | default | purpose |
|---|---|---|
| `deck` | — | the `.pptx` to tag (positional) |
| `--pdf` | — | pre-converted PDF to upload (skips LibreOffice) |
| `--model` | `claude-opus-4-7` | model (`claude-sonnet-4-6` for lower cost) |
| `--effort` | `high` | thinking/output effort (`low`/`medium`/`high`/`max`) |
| `--prompt` | resolver default | prompt markdown (else `$SLIDE_TAGGER_PROMPT` / `docs/deck_tagging_prompt.md`) |
| `--timeout` | `900` | per-request timeout (s); a hang errors out instead of stalling |
| `--quiet` | off | suppress the streaming heartbeat |
| `--out` | `data/tagged/<slug>.tagged.json` | output JSON path |
| `--strict` | off | exit non-zero on schema validation failure |
| `--tagged-by` | `auto:<model>` | `provenance.tagged_by` value |
| `--into-corpus` | off | also copy result + logo assets into the served corpus dir |
| `--corpus-dir` | `$SLIDE_TAGGER_CORPUS_DIR` or `../mcp_slide_tagging/corpus` | target for `--into-corpus` |
| `--fraction` | `0.25` | min slide-coverage to treat an image as a recurring logo |
| `--render` | off | also render slide PNGs (images aren't served yet, so off by default) |
| `--poppler-path` | — | poppler `bin/` for `--render` (handy on Windows) |
