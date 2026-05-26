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

## Flow — the four-command paste harness (recommended)

The friction-heavy "template / paste / save vlm_out.json / merge / score" sequence
is now a four-command CLI harness. Same web UI, same $0 cost, but the prep/capture
/score/log steps are automated so the iteration loop matches `bench`'s rigor — no
hand-renaming files, no forgetting which deck a `vlm_out.json` was for, no
re-running merge by hand.

Layout per experiment: `data/paste/<deck-slug>/<variant>/`
- `in.md` — the paste-ready bundle (system prompt + grounding + template)
- `meta.json` — pack metadata (`prompt_version`, `source_pptx`, `pack_time_utc`)
- `run_1.json`, `run_2.json`, … — captured VLM outputs (auto-incrementing N)
- `score.md` — the most recent `score-paste` scorecard

```bash
# 1. PACK — build the paste bundle for one variant.
uv run slide-tagger pack nigeria-economic-outlook-october-2023-v1 \
    --variant baseline
# Wrote: data/paste/nigeria-…/baseline/in.md

# 2. INGEST — capture the model's JSON reply (file or stdin).
#    First, attach the deck PDF and paste in.md into Claude.ai. Save the reply.
uv run slide-tagger ingest nigeria-economic-outlook-october-2023-v1 \
    --variant baseline data/paste/nigeria-…/baseline/reply.json
#    or pipe from the clipboard (PowerShell shown; pbpaste / xclip -o on mac/Linux):
Get-Clipboard | uv run slide-tagger ingest nigeria-economic-outlook-october-2023-v1 \
    --variant baseline -

# 3. SCORE — score every run for the variant vs the hand-label answer key.
uv run slide-tagger score-paste nigeria-economic-outlook-october-2023-v1 \
    --variant baseline
# Writes: data/paste/nigeria-…/baseline/score.md

# 4. COMPARE — diff per-field accuracy across two variants of the same deck.
uv run slide-tagger compare-paste nigeria-economic-outlook-october-2023-v1 \
    --variants baseline,v2-deck-context
# Prints a per-field table with the delta and the headline-accuracy delta.
```

**Pairs with Claude.ai Projects:** set the system prompt as Project instructions
once, then ignore the `[FULL SYSTEM PROMPT]` block at the top of `in.md` and paste
only the `[USER MESSAGE]` half. Bundles for very-dense decks may otherwise hit
claude.ai's message-length cap.

The harness reuses the same `resolve_prompt` → `sanitize_enums` →
`merge_structural` → `build_enriched_record` chain as `enrich`/`bench`, so paste
runs validate as `DeckTag` and score with the exact same `score`/`eval` modules.
Provenance is stamped with `tagged_by: paste:<model>:<variant>` plus extras
(`paste_variant`, `paste_run_index`) so paste runs are distinguishable from API
runs.

## Manual flow (legacy, prefer the paste harness above)

If you want the lowest-level loop (no harness, no run-numbering), the original
sequence still works:

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
cp .env.example .env         # put your ANTHROPIC_API_KEY in .env (gitignored, auto-loaded)
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

## Refining the prompt (the v-by-v loop)

The enrichment prompt lives in [deck_tagging_prompt.md](deck_tagging_prompt.md) under `## The Prompt`.
`bench` reads that section live as the system prompt, so **you just edit the markdown and re-run —
no regeneration step.** Two good places to put a fix: the inline definition in the schema block (the
field's `"… | … | …"` string, read right next to the field) or a numbered rule under *Tagging
principles* (for emphasis / cross-field guidance). Don't add new enum **values** casually —
`schema/enums.py` is the locked vocabulary.

**The loop:**

1. **Baseline.** `uv run slide-tagger bench --runs 3 --model claude-sonnet-4-6 --effort medium --label v2`
   (cheap inner-loop config). Note the per-deck `mean ± std` and the per-field table. The **std is your
   noise floor**: an edit is real only if a field's mean moves by more than ~the std.
2. **Diagnose each weak field by *type*** (use the per-field table + the confusions from `score`):
   - **Bias / calibration** — one dominant, single-direction confusion (e.g. `Bespoke→Reusable`):
     add an explicit default / anti-bias rule.
   - **Definition gap** — the model doesn't know what a value means: add a one-line definition + one
     example. For **visual** fields (`dominant_visual_element`, `placeholder_compliance`), **render and
     look first** (`pdftoppm`/poppler is installed) — write the rule to match what the slides actually
     show, don't guess.
   - **Grounding gap** — the model contradicts Pipeline A (e.g. invents a `chart_type` when
     `has_chart` is false): strengthen "use the STRUCTURAL DATA verbatim."
   - **Label disagreement** — the hand-label is debatable (e.g. deck `audience_level`:
     `External / public` vs `C-suite / board` for a *published* report). **Don't touch the prompt** —
     fix or accept the label. Audit a slide before assuming the model is wrong.
   - **Scoring artifact** — `slot_types_present` "exact" is all-or-nothing (judge it by F1). Not a
     prompt problem.
3. **One lever per iteration.** Edit one field's guidance (or a batch of *independent* fields — never two
     competing edits on the same field). Re-run `bench` with a new `--label`.
4. **Keep or revert by the numbers.** Keep the edit only if the target field's mean rose by more than
     the std **and** no other field regressed (check the *whole* table — fixes can have side effects).
     Make **generalizable** edits (definitions, rules), never deck-specific patches, and confirm the
     change helps digital-auto *without* tanking nigeria.
5. **Log it.** Every `bench` run appends a row to `logs/bench_results.md`; the canonical narrative goes
     in the [iteration log](#prompt-iteration-log) above.
6. **Confirm the winner once on Opus.** The inner loop runs on Sonnet/medium for cost; do a single
     `--runs 5 --model claude-opus-4-7 --effort high` sweep before declaring a version done. Pin one
     model across any two runs you compare.

**When to stop:** when the headline plateaus and the remaining misses are label-debatable or artifacts.
A real part of the current 74%→85% gap is label noise (deck-level `audience_level` / `grid` /
`deliverable_format`, all n=2 and judgment calls) — chasing those with prompt edits fits noise rather
than improving the model.

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
| v2 (manual, 1 run) | 2026-05-24 | slide_purpose Finding-vs-Data-presentation rule; audience_level_slide default "Same as deck"; slide_position_role vocab guard. (Audited digital-auto: the Data presentation→Finding ×15 and →Same as deck ×15 confusions are real prompt gaps; deck audience_level left as label noise.) | nigeria 77% / digital-auto 72% | (single noisy draws) | Targeted edits worked: audience_level_slide digital-auto 60→100; slide_purpose digital-auto 48→80; slide_position_role crash fixed. Single-run field numbers (embedded_data 48, client_industry 0) turned out to be outlier draws — see the bench row. |
| **v2 (API bench, Opus high, 5×)** | 2026-05-24 | same v2 prompt, measured properly | **nigeria 77.6% ± 1.4% / digital-auto 70.9% ± 1.8%** (corpus 74.2%, $6.99) | message_type 69%, dominant_visual_element 70%, placeholder_compliance 72% (slot_types_present 13% = all-or-nothing artifact). Deck-level audience_level/grid/deliverable 0–50% are n=2 and largely **label-debatable**. | **Run-to-run variance is small (~±1.5%), NOT ±20** — my earlier conclusion was wrong; it came from comparing noisy single manual runs under different (claude.ai) conditions. The v1 nigeria 96% was a non-reproducible outlier. Bench is the reliable measure; **3 runs suffice** (drop runs + use Sonnet/medium for the inner loop to cut the ~$7/sweep cost). |
| (answer-key fix, not a prompt change) | 2026-05-24 | corrected digital-auto labels: 9 section-header/cover/chart slides were mislabeled `dominant_visual_element: "Pure text"` (audited against rendered slides; the VLM was right) + slide 19 chart_type/embedded. Off-by-one ruled out (main_message aligns at offset 0). See `reference_data/hand_labels/digital-auto-label-review.md`. | **digital-auto 70.9% → 73.1%** (same v2 predictions, re-scored — no API spend) | — | Confirms the v2 prompt was under-credited by bad labels. nigeria unaffected. Remaining digital-auto gap is contested labels (blanket `placeholder_compliance: Reusable`, `tier_match_difficulty`) + hard taxonomy (`message_type`). |

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
