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
1. Pipeline A     structural extraction + renders      ->  slide-tagger template <deck>.pptx > input.json
                                                            slide-tagger render <deck>.pptx
2. Enrichment     source deck + input.json + prompt    ->  vlm_out.json (all enrichment fields filled)
3. Merge guard    slide-tagger merge vlm_out.json input.json -o enriched.json  ->  re-imposes Pipeline A
                                                            structural fields (the VLM can't be trusted to copy them verbatim)
4. Validation     slide-tagger validate enriched.json  ->  schema check + completeness report
5. Scoring        slide-tagger score enriched.json <hand_label>.json  ->  per-field accuracy vs the answer key
                  slide-tagger eval                     ->  corpus scorecard: overall % vs 85% target + weakest fields
```

## Flow

1. **Generate the partial JSON** (Pipeline A structural + `_legend` + blank enrichment fields):
   `uv run slide-tagger template data/source/<deck>.pptx > input.json`
2. **Open claude.ai or Claude Code.** Model: **Claude Sonnet 4.6** by default; **Opus 4.7** for
   dense/hard decks where vision detail matters.
3. **Attach** `input.json` and the source deck (`.pptx`/`.pdf`); **paste** the prompt from
   [deck_tagging_prompt.md](deck_tagging_prompt.md).
4. **Read the returned JSON**, save it as `vlm_out.json` (a leading ```json code fence is fine — the
   next step tolerates it).
5. **Merge guard:** `uv run slide-tagger merge vlm_out.json input.json -o enriched.json`. This restores
   every Pipeline A structural field from the template, so a VLM that "helpfully" rewrote a title or a
   font can't corrupt the deterministic data (and any leftover non-structural schema issue is printed).
   Save `enriched.json` under `data/tagged/<hand_label_filename>` so `eval` can pair it by name.
6. **Validate:** `uv run slide-tagger validate enriched.json`.
7. **Score automatically:** `uv run slide-tagger score enriched.json
   reference_data/hand_labels/<deck>.json` for one deck, or `uv run slide-tagger eval` for the whole
   corpus (scores every `data/tagged/*.json` against the matching `reference_data/hand_labels/*.json`).
   Read the weakest-first per-field accuracy and the enum confusions, edit the prompt, re-run on the
   same deck first, then across deck types. Record the overall % and what changed in the
   [iteration log](#prompt-iteration-log). The [rubric](#rubric) below explains what each field
   *should* be; the scorer turns that into numbers (free-text fields are shown side-by-side for manual
   review, not scored).

> A **contact sheet** (all slides tiled as numbered thumbnails) helps the model judge deck-wide
> patterns — variety, density mix, overall aesthetic — that the `inferred_rules` and deck-level
> fields depend on. Render first (`slide-tagger render <deck>.pptx`), then build the sheet with
> `python scripts/make_contact_sheet.py data/renders/<deck>/ -o contact_sheet.png` and attach it
> alongside a few full-resolution slides.

## Automated benchmarking (`bench`) — measuring past run-to-run variance

A single manual run per deck turned out to be too noisy to measure a prompt edit:
nigeria scored 96% on one run and 77% on another with no change that explains the gap
(see the v1→v2 log rows). When run-to-run variance (~±20 pts) exceeds the effect of an
edit, you can't tell a good change from luck.

`bench` fixes the measurement: it calls the Claude API to run the enrichment prompt
**N times per deck** and reports **mean ± std**.

```bash
export ANTHROPIC_API_KEY=sk-...
uv run slide-tagger bench --runs 5            # nigeria + digital-auto, Opus
uv run slide-tagger bench --runs 5 --model claude-sonnet-4-6   # cheaper
```

- System prompt = the `## The Prompt` body of [deck_tagging_prompt.md](deck_tagging_prompt.md)
  (always the current version). The structural template is built in-memory from the `.pptx`;
  the deck PDF is uploaded once and reused across runs; prompt/PDF/template are cached so
  runs 2..N are cheap.
- Each run is auto-merged (structural guard) and enum-sanitized, then scored. Raw merged
  outputs are saved to `data/tagged/bench/<deck>/run_N.json`.
- Compare a prompt edit by running `bench` before and after: a change is real only if the
  mean moves by more than the std. Record the mean ± std in the [iteration log](#prompt-iteration-log).
- Decks come from `reference_data/hand_labels/<stem>.tagged.json` paired with
  `data/source/<source-stem>.{pptx,pdf}` (only nigeria is fully clean; see the note in the
  manual flow about digital-auto's labeler-authored structural fields).

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

Paste the `slide-tagger eval` overall semantic accuracy and the 2–3 weakest fields for each version.

| Version | Date | What changed | Semantic acc. (`eval`) | Weakest fields | Observed effect |
|---|---|---|---|---|---|
| v0 | 2026-05-24 | initial prompt (deck_tagging_prompt.md); nigeria only, Sonnet | 69% (1 deck) | placeholder_compliance 41% (Bespoke→Reusable ×16); reusability 38% (Low→Medium ×16); embedded_data_present 48% | baseline. Structural-integrity diffs traced to hand-label apostrophe/title_style normalization, not the VLM. enum-list fields look weak in the headline but F1 is 86–91% (all-or-nothing artifact). |
| v1 | 2026-05-24 | placeholder/reusability calibration + geography "(specify)" verbatim note | **nigeria 96% / digital-auto 63%** | digital-auto: slide_purpose 48% (Data presentation→Finding ×15), audience_level_slide 60% (→Same as deck ×15), placeholder 60% (Bespoke→Reusable ×15), dominant_visual 42% | **Does NOT generalize** — nigeria's 96% was optimistic/overfit. The Bespoke→Reusable and Low→Medium confusions v1 "fixed" on nigeria reappear on digital-auto, so the calibration wasn't robust. New failure mode: slide_position_role given slide_purpose-vocab values on 4 slides (4 nulled to score). Caveat: digital-auto is a noisier reference (labeler-authored titles; pptx grounding ≠ PDF) — part of the gap may be label/convention noise, not pure prompt. |
| v2 | 2026-05-24 | slide_purpose Finding-vs-Data-presentation rule; audience_level_slide default "Same as deck"; slide_position_role vocab guard. (Audited digital-auto: the Data presentation→Finding ×15 and →Same as deck ×15 confusions are real prompt gaps, confirmed from the slides' action-titles; deck audience_level disagreement left as label noise.) | **nigeria 77% / digital-auto 72%** (corpus 74%) | nigeria untargeted fields cratered: embedded_data 100→48, message_type 97→66, client_industry 100→0, audience_level 100→0 | **Targeted edits worked**: audience_level_slide digital-auto 60→100; slide_purpose digital-auto 48→80; slide_position_role crash fixed (→95%, no invalid enums). **But nigeria fell 96→77 entirely on fields v2 didn't touch → run-to-run variance (~±20) now exceeds edit effect size.** The v1 nigeria 96% was a lucky run. Conclusion: single manual runs are too noisy to drive further fine-tuning; need repeated runs / automation, or call the prompt good and port it. |

## Limitations

- **Rendering is built.** `slide-tagger render <deck>.pptx` produces per-slide full + thumbnail PNGs
  via LibreOffice + poppler (see the README for the system deps). Use those as the contact-sheet input
  and as VLM inputs instead of manual screenshots.
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
