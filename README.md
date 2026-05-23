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
- Pydantic schema (incl. locked deck-level semantic enums), CLI (`tag`,
  `deck-summary`), contact-sheet generator, sample deck, and tests.

**Deferred:**
- **PDF parsing** — `.pptx` only for now (init.md open question).
- **Slide rendering** to PNG — needs LibreOffice (not installed); use screenshots.
- **Full deck-level extraction** — modal `design_system` (fonts/colors),
  recurring-element detection via perceptual hashing, `consistency_score`.
- **Pipeline B** — the VLM calls themselves (this repo only grounds them).
