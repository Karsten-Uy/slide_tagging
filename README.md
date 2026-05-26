# slide-tagger

Pipeline A for the slide-deck tagging service: **deterministic structural
extraction** from `.pptx` decks. No AI — it reads the file's own data, so the
structural fields are near-100% accurate. These are exactly the fields the VLM
(Pipeline B) must *not* guess; they're fed to it as grounding context instead.

See [`docs/init.md`](docs/init.md) for the full design and
[`docs/vlm_prompt_test.md`](docs/vlm_prompt_test.md) for the manual enrichment
prompt-test loop this pipeline feeds. The enrichment (Pipeline B) prompt itself
lives in [`docs/deck_tagging_prompt.md`](docs/deck_tagging_prompt.md). To tag a
fresh deck end-to-end (Pipeline A + B) in one command, see
[`docs/enrich.md`](docs/enrich.md).

## Setup

```bash
uv sync                       # create venv, install deps
```

## Generate a sample deck

No deck handy? Make one:

```bash
uv run python scripts/make_sample_deck.py data/source/sample_deck.pptx
```

## Run Pipeline A

```bash
# Per-slide STRUCTURAL DATA grounding blocks:
uv run slide-tagger tag data/source/sample_deck.pptx
uv run slide-tagger tag data/source/sample_deck.pptx --slide 2   # one slide
uv run slide-tagger tag data/source/sample_deck.pptx --json      # full JSON

# Whole-deck DECK SUMMARY grounding block:
uv run slide-tagger deck-summary data/source/sample_deck.pptx
uv run slide-tagger deck-summary data/source/sample_deck.pptx --json

# Render each slide to PNG (full + thumbnail) for the VLM pass and the MCP corpus:
uv run slide-tagger render data/source/sample_deck.pptx              # -> data/renders/<deck>/
uv run slide-tagger render data/source/sample_deck.pptx --slide 2   # just one slide

# Contact sheet to help the enrichment pass judge deck-wide patterns:
uv run python scripts/make_contact_sheet.py data/renders/<deck>/ -o contact_sheet.png
```

### Rendering (slide → PNG)

`render` turns a `.pptx` into per-slide PNGs — a full render (`slide_NNN.png`, native
aspect, default 150 DPI) and a thumbnail (`thumb/slide_NNN.png`, default 512px long
edge) — under `data/renders/<deck-slug>/`. These feed both the VLM enrichment pass
(Pipeline B) and the `mcp_slide_tagging` server (CLIP embeddings + agent previews).
The `template` command records each slide's `render_path`/`thumbnail_path` so the
tagged JSON points at them.

Rendering needs two system dependencies:

- **LibreOffice** (`.pptx` → PDF). Auto-discovered on PATH, at the Windows default
  install path, or via `LIBREOFFICE_PATH`.
- **poppler** (`pdftoppm`, PDF → PNG). On PATH, or pass `--poppler-path <bin>` /
  set `POPPLER_PATH` (handy on Windows). Install: `apt-get install poppler-utils`
  (Linux) or unzip the [poppler-windows](https://github.com/oschwartz10612/poppler-windows/releases)
  release and point `--poppler-path` at its `Library\bin`.

### Extracting logos / branding images (`extract-assets`)

The MCP server can serve a deck's logos so a generated deck carries real branding.
`extract-assets` finds **recurring branding images** — scanning slides **plus the
slide masters/layouts and recursing into group shapes** — at a logo-tuned recurrence
threshold (default 25% of slides, lower than the design-system pHash threshold),
saves a PNG per group, and records `image_path`/`source`/auto-`type` on
`design_system.recurring_elements`.

```bash
# Extract to reference_data/assets/<deck-slug>/ and print the new recurring_elements:
uv run slide-tagger extract-assets data/source/<deck>.pptx

# Lower the recurrence bar, write a captioned grid to eyeball the catches, and merge
# the image elements straight into a hand-label (deduped by pHash):
uv run slide-tagger extract-assets data/source/<deck>.pptx --fraction 0.2 \
    --contact-sheet --into reference_data/hand_labels/<deck>.tagged.json
```

Each extracted element gets `type` (auto-guessed: `logo`/`footer`/…), `value`
(text, hand-filled), `phash`, `position`, `appears_on_slides`, `image_path`
(`assets/<slug>/recurring_NN.png`), and `source` (`slide`/`master`/`layout`).
**Vector/grouped logos** (EMF/WMF, no raster blob — common in polished corporate
decks) can't be rasterized; those decks correctly yield **no** asset and rely on
the footer wordmark text downstream (manual drop-in covered in
[`docs/manual_tagging.md`](docs/manual_tagging.md)). Curate so only true branding
keeps a `type:"logo"` — see
[Manual tagging](#manual-tagging-hand-labeling-reference-decks) below.

### Scoring the enrichment prompt (Pipeline B)

Once you have hand-labeled decks in `reference_data/hand_labels/` (the answer key),
`score` / `eval` turn the manual rubric into measured per-field accuracy, so you can
optimize the enrichment prompt against real numbers. VLM output is still produced
manually (paste the prompt into Claude.ai) and saved to `data/tagged/`; the harness
scores it — no API key required.

```bash
# Guard: re-impose Pipeline A structural fields the VLM may have altered, then save
# under the hand-label's filename so `eval` pairs them. (Tolerates a ```json fence.)
uv run slide-tagger merge vlm_out.json input.json -o data/tagged/<deck>.json

# One deck: predicted (VLM-enriched) vs its hand-label
uv run slide-tagger score data/tagged/<deck>.json reference_data/hand_labels/<deck>.json

# Whole corpus: every data/tagged/*.json against the matching hand_labels/*.json
uv run slide-tagger eval                                   # console scorecard
uv run slide-tagger eval --json report.json --markdown report.md
```

**Automated benchmarking (`bench`).** Single manual runs have large run-to-run
variance (a deck can swing ~±20 points), which swamps the effect of a prompt edit.
`bench` calls the Claude API to run the enrichment prompt **N times per deck** and
reports **mean ± std**, so prompt changes become measurable. Needs
`ANTHROPIC_API_KEY`; the deck PDF is uploaded once and reused across runs, and the
prompt/PDF/template are prompt-cached so runs 2..N are cheap.

```bash
cp .env.example .env        # then put your key in .env (gitignored, auto-loaded)
uv run slide-tagger bench                                  # nigeria + digital-auto, 3 runs each, Opus
uv run slide-tagger bench --runs 5 --model claude-sonnet-4-6   # more runs, cheaper model
uv run slide-tagger bench --deck nigeria-economic-outlook-october-2023-v1  # one deck
```

Each run is structurally merged + enum-sanitized + scored; raw merged outputs land
in `data/tagged/bench/<deck>/run_N.json`. The system prompt is the `## The Prompt`
body of [docs/deck_tagging_prompt.md](docs/deck_tagging_prompt.md), so it always
tracks the current prompt version.

The scorecard gives overall **semantic accuracy vs the 85% target**, per-field
accuracy ranked weakest-first, the enum confusions behind the weak fields (e.g.
`audience_level: C-suite / board → Senior executives`), a structural-integrity
check (Pipeline A fields must be untouched), and free-text fields side-by-side for
manual review. Workflow and rubric: [docs/vlm_prompt_test.md](docs/vlm_prompt_test.md).
Predictions are matched to hand-labels by **identical filename**.

`tag` / `deck-summary` emit paste-ready `STRUCTURAL DATA` / `DECK SUMMARY`
grounding blocks for inspecting Pipeline A's output. The enrichment workflow
proper runs off `template` → enrich → `validate` (below).

See [`docs/vlm_prompt_test.md`](docs/vlm_prompt_test.md) for the enrichment
prompt-test loop and rubric, and [`docs/deck_tagging_prompt.md`](docs/deck_tagging_prompt.md)
for the prompt itself.

## Manual tagging (hand-labeling reference decks)

init.md Phase 1: hand-fill the schema for a few reference decks before automating.
The schema is **structural (Pipeline A, prefilled) + enrichment (you fill in)** —
defined in [`src/slide_tagger/schema/tagged.py`](src/slide_tagger/schema/tagged.py)
(`SlideTag` / `DeckTag`).

**Full step-by-step guide (where + how, with a field reference):**
[`docs/manual_tagging.md`](docs/manual_tagging.md). Quick version below.

```bash
# Make a blank template (structural filled, enrichment = null) from a deck or a
# Pipeline A structural JSON. The template's "_legend" lists allowed values.
uv run slide-tagger template data/source/sample_deck.pptx > labels.json
uv run slide-tagger template tmp/pwc1.json > pwc_labels.json   # from existing structural JSON

# ...hand-fill the enrichment fields in labels.json...

# Validate the schema and see what's still untagged:
uv run slide-tagger validate labels.json
```

The enrichment schema has three levels (full field list in
[`docs/manual_tagging.md`](docs/manual_tagging.md)):

- **Deck-level:** `client_industry`, `client_type`, `engagement_stage`,
  `content_area`, `audience_level`, `deliverable_format`, `geography`,
  `confidentiality_tier`, plus free-text `client_sub_industry`,
  `inferred_publisher`, `deck_summary_one_sentence`.
- **Slide-level:** `slide_purpose`, `message_type`, `audience_level_slide`,
  `slide_position_role`, `main_message`, `dominant_visual_element`, `chart_type`,
  `placeholder_compliance`, `embedded_data_present`, `zones`, `slot_types_present`,
  `reusability_score_qualitative`, `tier_match_difficulty`.
- **Element-level:** the `inferred_rules` block (deck-wide style aggregates) plus
  the deck-wise `design_system.grid` and the `type` (and text `value`, where it has
  one) of each `design_system.recurring_elements[]`.

A `provenance` block records who tagged it. `validate` checks enum values and
reports completeness.

## Tests

```bash
uv run pytest -q
```

## What's implemented vs. deferred

**Implemented (Pipeline A):**
- *Per-slide structural:* word count, text-block count, visual-element count,
  whitespace estimate, density bucket, title text + position, image count,
  chart/table presence.
- *Deck-level summary:* slide count, density distribution, chart/table/image
  prevalence, dominant title position, average word count.
- *Design system:* modal title/body text styles (font, size, weight, color,
  alignment), color palette (primary/accent/neutrals), default alignment, and
  recurring-element detection via perceptual hash (pHash). **Font names are
  normalized to installable families** (`"Arial MT"`/`"Arial-BoldMT"` → `"Arial"`)
  and the title family falls back to the deck's dominant (body) font when the title
  placeholder carries none, so `run.font.name` matches an installed font downstream
  instead of silently falling back. `grid` and each recurring element's `type` (and
  text `value`) are left for hand-labeling.
- *Logo / branding extraction:* `extract-assets` finds recurring branding images
  (scanning slides + masters/layouts, recursing groups), saves a PNG per group, and
  records `image_path`/`source`/auto-`type` on `recurring_elements` for the MCP
  server to serve. Vector/grouped logos (no raster blob) fall back to a manual
  drop-in.
- *Rendering:* `.pptx` → per-slide PNGs (full + thumbnail) via LibreOffice +
  poppler, written to `data/renders/<deck>/` and recorded as
  `render_path`/`thumbnail_path` in the tagged JSON.
- *Merge guard:* `merge` re-imposes Pipeline A's structural fields from the template
  onto a VLM output, so the enrichment pass can't corrupt deterministic fields.
- *Eval harness:* `score` / `eval` compare VLM-enriched output against hand-labels
  field-by-field (enum exact match, enum-list set-F1), with a structural-integrity
  check and per-enum confusions — the signal for prompt optimization.
- *API benchmark:* `bench` runs the enrichment prompt via the Claude API N times per
  deck and reports mean ± std accuracy, averaging out run-to-run variance (the merge
  guard + enum sanitation are applied automatically). Needs `ANTHROPIC_API_KEY`.
- *Automated tagging:* `enrich` takes an unlabeled `.pptx` and writes a finished
  tagged JSON (Pipeline A + B in one shot — no hand-label), stamping the prompt
  version + low-confidence fields into `provenance`; `--into-corpus` ingests it into
  the served corpus. The prompt resolves through one chokepoint shared with `bench`.
  Full guide: [`docs/enrich.md`](docs/enrich.md). Needs `ANTHROPIC_API_KEY`.
- Pydantic schema (incl. the locked enrichment vocabulary — deck-, slide-, and
  element-level enums), CLI (`tag`, `deck-summary`, `template`, `validate`,
  `render`, `extract-assets`, `merge`, `score`, `eval`, `bench`, `enrich`),
  contact-sheet generator, sample deck, and tests.

**Deferred / known limits:**
- **PDF parsing** — `.pptx` only for now (init.md open question).
- **Vector images (EMF/WMF) are skipped** — PIL can't rasterize them to hash, so
  vector/grouped logos yield no extracted asset (manual drop-in instead). Common in
  polished corporate decks. (Slide *and* master/layout images, incl. those inside
  group shapes, are now scanned by `extract-assets`.)
- **`consistency_score`** and **`deviations_from_system`** — not yet computed.
- **Pipeline B** — the VLM calls themselves (this repo only grounds them).
