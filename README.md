# slide-tagger

Pipeline A for the slide-deck tagging service: **deterministic structural
extraction** from `.pptx` decks. No AI — it reads the file's own data, so the
structural fields are near-100% accurate. These are exactly the fields the VLM
(Pipeline B) must *not* guess; they're fed to it as grounding context instead.

See [`docs/init.md`](docs/init.md) for the full design and
[`docs/vlm_prompt_test.md`](docs/vlm_prompt_test.md) for the manual enrichment
prompt-test loop this pipeline feeds. The enrichment (Pipeline B) prompt itself
lives in [`docs/deck_tagging_prompt.md`](docs/deck_tagging_prompt.md).

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

# Contact sheet to help the enrichment pass judge deck-wide patterns:
uv run python scripts/make_contact_sheet.py renders/<deck>/ -o contact_sheet.png
```

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
  the deck-wise `design_system.grid` and the `type` of each detected
  `design_system.recurring_elements[]`.

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
  recurring-element detection via perceptual hash (pHash). `grid` and each
  recurring element's `type` are left for hand-labeling.
- Pydantic schema (incl. the locked enrichment vocabulary — deck-, slide-, and
  element-level enums), CLI (`tag`, `deck-summary`, `template`, `validate`),
  contact-sheet generator, sample deck, and tests.

**Deferred / known limits:**
- **PDF parsing** — `.pptx` only for now (init.md open question).
- **Slide rendering** to PNG — needs LibreOffice (not installed); use screenshots.
- **Recurring elements on the slide master/layout aren't detected** — only
  slide-level images are hashed. **Vector images (EMF/WMF) are skipped** — PIL
  can't rasterize them to hash. (Both common in polished corporate decks.)
- **`consistency_score`** and **`deviations_from_system`** — not yet computed.
- **Pipeline B** — the VLM calls themselves (this repo only grounds them).
