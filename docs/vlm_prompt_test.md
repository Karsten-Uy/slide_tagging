# VLM Prompt Test Harness (Pipeline B)

A manual loop for refining Pipeline B's enrichment prompt. Pipeline A (deterministic structural
extraction) is already built, so you can ground the prompt with **real structural data** the way
production will. Pipeline B is a **single enrichment pass**: it reads the source deck plus Pipeline
A's structural JSON and fills in the three-level tagging schema (deck-level + slide-level +
element-level `inferred_rules`), plus a `provenance` block.

The canonical prompt lives in [deck_tagging_prompt.md](deck_tagging_prompt.md). This file is the
**test/iteration harness** around it: attach the inputs, run the prompt, score the JSON against the
rubric, tweak, repeat. This is the "prompt iteration against a hand-labeled set" work that
[init.md](init.md) (Phase 3) calls for.

## Purpose

- **What:** how to iterate on the enrichment prompt and score its output.
- **Why:** find the prompt that produces clean, schema-conformant tags before wiring it into a
  `src/slide_tagger/extractors/semantic/` client. init.md's guidance: *hand-label before automating.*
- **Division of labor:** Pipeline A (deterministic) owns all structural fields — per-slide density,
  title text/position, image/chart/table presence, and the `design_system` fonts/colors. Pipeline B
  returns **only** the semantic judgments it uniquely can make (the deck-, slide-, and element-level
  enrichment fields). Pipeline A's data is **given as context and preserved verbatim**, never
  re-derived or overwritten (init.md: "VLMs should only do what they uniquely can").

## Pipeline ordering

```
1. Pipeline A     deterministic structural extraction  ->  slide-tagger template <deck>.pptx > input.json
2. Enrichment     source deck + input.json + prompt    ->  enriched.json (all enrichment fields filled)
3. Validation     slide-tagger validate enriched.json  ->  schema check + completeness report
```

## Flow

1. **Generate the partial JSON** (Pipeline A structural + `_legend` + blank enrichment fields):
   `uv run slide-tagger template data/source/<deck>.pptx > input.json`
2. **Open claude.ai or Claude Code.** Model: **Claude Sonnet 4.6** by default; **Opus 4.7** for
   dense/hard decks where vision detail matters.
3. **Attach** `input.json` and the source deck (`.pptx`/`.pdf`); **paste** the prompt from
   [deck_tagging_prompt.md](deck_tagging_prompt.md).
4. **Read the returned JSON**, save it as `enriched.json`.
5. **Validate:** `uv run slide-tagger validate enriched.json`.
6. **Score** against the [rubric](#rubric) below; note what failed, edit the prompt, re-run on the
   same deck first, then across deck types. Record each change in the
   [iteration log](#prompt-iteration-log).

> A **contact sheet** (all slides tiled as numbered thumbnails) helps the model judge deck-wide
> patterns — variety, density mix, overall aesthetic — that the `inferred_rules` and deck-level
> fields depend on. Build one with
> `python scripts/make_contact_sheet.py renders/<deck>/ -o contact_sheet.png` and attach it alongside
> a few full-resolution slides.

## Schema being filled

The enrichment fields, by level (see [deck_tagging_prompt.md](deck_tagging_prompt.md) for the full
enum lists and definitions, and `_legend` in the template for allowed values):

- **Deck-level:** `client_industry`, `client_sub_industry`, `client_type`, `engagement_stage`,
  `content_area`, `audience_level`, `deliverable_format`, `geography`, `confidentiality_tier`,
  `inferred_publisher`, `deck_summary_one_sentence` (`deck_length` is pre-filled from `slide_count`).
- **Slide-level:** `slide_purpose`, `message_type`, `audience_level_slide`, `slide_position_role`,
  `main_message`, `dominant_visual_element`, `chart_type`, `placeholder_compliance`,
  `embedded_data_present`, `zones`, `slot_types_present`, `reusability_score_qualitative`,
  `tier_match_difficulty`.
- **Element-level (`inferred_rules`):** `title`, `body_text`, `color_palette`, `chart_styling`,
  `layout_conventions` — each flagged `scope_tag: "inferred"`.
- **`provenance`:** `tagged_by`, `input_json_source`, `fields_filled_by_ai`, `confidence_notes`.

## Rubric

Score each output:

- [ ] **Valid JSON**, parses cleanly, no fences or prose. `slide-tagger validate` passes.
- [ ] **Structural fields untouched** — every Pipeline A field (`density`, `title_*`, `has_chart`,
      `design_system` fonts/colors, `deck_length`) is byte-for-byte what the template emitted.
- [ ] **Enum discipline** — every enumerated field uses only values from `_legend`; no invented values.
- [ ] **`main_message`** is a single factual sentence about the slide's *content* (verbatim title when
      the title is already an action title; otherwise inferred from the slide).
- [ ] **`dominant_visual_element` / `chart_type` consistent with Pipeline A** — a slide Pipeline A
      reports `has_chart: false` should not claim a real `chart_type`; `chart_type` is `N/A` unless
      `dominant_visual_element` is `Chart`.
- [ ] **`audience_level` honest** — not every important deck is `C-suite / board`.
- [ ] **`placeholder_compliance` honest** — custom text boxes (not master placeholders) are
      `Reusable`/`Bespoke`, not `Pristine`.
- [ ] **`inferred_rules` are deck-wide aggregates**, not single-slide observations; `scope_tag` is
      `inferred`.
- [ ] **`provenance.confidence_notes`** flags any low-confidence fields for human review.

If a check fails, that's the signal for what to tweak in the prompt. Re-run on the same deck first,
then across deck types.

## Prompt iteration log

| Version | Date | What changed | Observed effect |
|---|---|---|---|
| v0 | | initial prompt (deck_tagging_prompt.md) | baseline |
| | | | |

## Limitations

- **Rendering not built.** No LibreOffice on this machine, so slide PNGs (and the contact sheet) come
  from manual screenshots/exports for now.
- **Clean separation.** The VLM never produces structural fields — Pipeline A owns them and they're
  preserved verbatim in the enriched record (init.md: "VLMs should only do what they uniquely can").
- **`design_system` vs. `inferred_rules`.** Pipeline A's `design_system` is deterministic (modal
  title/body fonts, color palette, default alignment, pHash recurring-element detection). The
  enrichment `inferred_rules` block is the VLM's *observed* style patterns across the deck — additive
  and explicitly non-authoritative (`scope_tag: "inferred"`), kept separate from `design_system`.
  (Recurring-element detection only sees slide-level raster images — logos on the slide master or
  vector EMF/WMF images aren't hashed.)
- **Next step:** once the prompt is solid, port it into `src/slide_tagger/extractors/semantic/`; the
  enrichment enums are already locked in [`src/slide_tagger/schema/enums.py`](../src/slide_tagger/schema/enums.py).
