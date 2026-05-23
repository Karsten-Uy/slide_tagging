# slide-tagger

Pipeline A for the slide-deck tagging service: **deterministic structural
extraction** from `.pptx` decks. No AI — it reads the file's own data, so the
structural fields are near-100% accurate. These are exactly the fields the VLM
(Pipeline B) must *not* guess; they're fed to it as grounding context instead.

See [`architecture/init.md`](architecture/init.md) for the full design and
[`architecture/vlm_prompt_test.md`](architecture/vlm_prompt_test.md) for the
manual VLM prompt-test loop this pipeline feeds.

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
# Per-slide STRUCTURAL DATA blocks (per-slide VLM pass):
uv run slide-tagger tag data/source/sample_deck.pptx
uv run slide-tagger tag data/source/sample_deck.pptx --slide 2   # one slide
uv run slide-tagger tag data/source/sample_deck.pptx --json      # full JSON

# Whole-deck DECK SUMMARY block (deck-level VLM pass):
uv run slide-tagger deck-summary data/source/sample_deck.pptx
uv run slide-tagger deck-summary data/source/sample_deck.pptx --json

# Contact sheet for the deck-level pass (tile slide PNGs you exported):
uv run python scripts/make_contact_sheet.py renders/<deck>/ -o contact_sheet.png
```

The default outputs are the exact `STRUCTURAL DATA` / `DECK SUMMARY` blocks the
VLM prompt test expects. Two passes (run deck-level first):

- **Deck-level:** `deck-summary` → paste next to a contact sheet of all slides.
- **Per-slide:** `tag --slide N` → paste next to a screenshot of slide N, plus
  the deck-level result as DECK CONTEXT.

See [`architecture/vlm_prompt_test.md`](architecture/vlm_prompt_test.md) for the
full prompts and rubrics.

## Manual tagging (hand-labeling reference decks)

init.md Phase 1: hand-fill the schema for a few reference decks before automating.
The schema is **structural (Pipeline A, prefilled) + semantic (you fill in)** —
defined in [`src/slide_tagger/schema/tagged.py`](src/slide_tagger/schema/tagged.py)
(`SlideTag` / `DeckTag`).

**Full step-by-step guide (where + how, with a field reference):**
[`docs/manual_tagging.md`](docs/manual_tagging.md). Quick version below.

```bash
# Make a blank template (structural filled, semantic = null) from a deck or a
# Pipeline A structural JSON. The template's "_legend" lists allowed values.
uv run slide-tagger template data/source/sample_deck.pptx > labels.json
uv run slide-tagger template tmp/pwc1.json > pwc_labels.json   # from existing structural JSON

# ...hand-fill the semantic fields in labels.json...

# Validate the schema and see what's still untagged:
uv run slide-tagger validate labels.json
```

Per slide, fill `role`, `layout_archetype`, `core_message`, `emphasis_techniques`.
Per deck, fill `deck_type`, `style_archetype`, `narrative_structure`,
`dominant_visual_mode`, plus the deck-wise `design_system.grid` and the `type` of
each detected `design_system.recurring_elements[]`. `validate` checks enum values
and reports completeness (including untyped recurring elements).

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
- Pydantic schema (incl. locked deck-level semantic enums), CLI (`tag`,
  `deck-summary`, `template`, `validate`), contact-sheet generator, sample deck,
  and tests.

**Deferred / known limits:**
- **PDF parsing** — `.pptx` only for now (init.md open question).
- **Slide rendering** to PNG — needs LibreOffice (not installed); use screenshots.
- **Recurring elements on the slide master/layout aren't detected** — only
  slide-level images are hashed. **Vector images (EMF/WMF) are skipped** — PIL
  can't rasterize them to hash. (Both common in polished corporate decks.)
- **`consistency_score`** and **`deviations_from_system`** — not yet computed.
- **Pipeline B** — the VLM calls themselves (this repo only grounds them).
