# VLM Prompt Test Harness (Pipeline B)

A manual loop for refining Pipeline B's VLM prompts **in claude.ai (web)**. Pipeline A
(deterministic structural extraction) is already built, so you can ground the prompts with **real
structural data** the way production will. Pipeline B is **two VLM passes**:

1. a **deck-level pass** — classify the whole deck (type, style, narrative, visual mode) from a
   contact sheet; run this *first*; and
2. a **per-slide pass** — tag each slide (role, layout, message, emphasis), enriched with the
   deck-level result.

For each, attach the image(s), paste the prompt block with Pipeline A's grounding filled in, read
back JSON, score it, tweak, repeat. This is the "prompt iteration against a hand-labeled set" work
that [init.md](init.md) (Phase 3) calls for.

## Purpose

- **What:** copy-paste prompts + scoring rubrics for Pipeline B's two VLM passes.
- **Why:** find the prompts that produce clean, schema-conformant tags before porting them into
  `src/extractors/semantic/prompts.py`. init.md's guidance: *hand-label before automating.*
- **Division of labor:** Pipeline A (deterministic) owns all structural fields — per-slide density
  *and* the deck-level summary (slide count, density mix, chart/table/image prevalence). The VLM
  (Pipeline B) returns **only** the semantic judgments it uniquely can make: per slide `role`,
  `layout_archetype`, `core_message`, `emphasis_techniques`; per deck `deck_type`, `style_archetype`,
  `narrative_structure`, `dominant_visual_mode`. Pipeline A's data is **given as context**, never
  re-output or guessed (init.md: "VLMs should only do what they uniquely can").
- **Fallback (no grounding):** if you don't have a Pipeline A run, leave the grounding section blank.
  The VLM still returns only its semantic fields — it just has less context, so accuracy may drop.

**Scope:** the **semantic** fields the VLM uniquely produces — per slide (`role`, `layout_archetype`,
`core_message`, `emphasis_techniques`) and per deck (`deck_type`, `style_archetype`,
`narrative_structure`, `dominant_visual_mode`). Pipeline A's structural fields (per-slide `density`,
the deck summary, and — later — `design_system`/`consistency_score`/`deviations_from_system`) are
grounding context, not produced here.

## Pipeline ordering (run deck-level first)

The deck-level pass runs before the per-slide pass, because each per-slide judgment is better when
the VLM knows what kind of deck the slide lives in. A sparse, image-led slide means something
different in a sales pitch than in an internal report.

```
1. Pipeline A          deterministic structural extraction (per-slide + deck summary)
2. Deck-level VLM pass  contact sheet + DECK SUMMARY  ->  deck_type, style, narrative, visual_mode
3. Per-slide VLM pass   each slide + STRUCTURAL DATA + DECK CONTEXT (from step 2)
4. Cross-validation     check VLM output against Pipeline A's numbers
```

---

# Deck-level pass

Classify the whole deck. This needs a bird's-eye view, so the key input is a **contact sheet**: all
slides tiled as numbered thumbnails into one image. Patterns the VLM needs here — variety, density
mix, overall aesthetic — emerge across slides, not within any one.

### Inputs (one claude.ai message)

1. **The contact sheet** (required) — whole-deck overview.
   `python scripts/make_contact_sheet.py renders/<deck>/ -o contact_sheet.png`
   (A 24-slide deck at 5 columns is ~1660×920 — well within Claude's vision limits.)
2. **2–3 representative slides at full resolution** (optional but recommended) — e.g. the title, a
   middle content slide, and the closing/CTA — so the VLM can see detail the thumbnails lose.
3. **The DECK SUMMARY** grounding block (paste into the prompt).
   `slide-tagger deck-summary <deck>.pptx`

### Deck-level flow

1. **Export every slide to a PNG** into one folder (screenshot/export; rendering isn't built — see
   [Limitations](#limitations)).
2. **Build the contact sheet** with `make_contact_sheet.py`.
3. **Get the DECK SUMMARY** with `slide-tagger deck-summary`.
4. **Open claude.ai → new chat** (Sonnet 4.6 default; Opus 4.7 for finer aesthetic calls).
5. **Attach** the contact sheet (+ the 2–3 hi-res slides). **Paste** the deck-level prompt with the
   DECK SUMMARY filled in.
6. **Read the JSON**, score it against the [deck-level rubric](#deck-level-rubric), iterate.

### Deck-level prompt block

```
You are a presentation-design analyst. You are shown a CONTACT SHEET of every slide in one deck
(numbered thumbnails), and possibly a few full-resolution slides. Classify the DECK AS A WHOLE and
return a single JSON object.

Rules:
- Pick values ONLY from the enumerated options for each field. Do not invent new values.
- The DECK SUMMARY block below is deterministic context from Pipeline A. USE it to inform your
  judgments, but do NOT echo or output those numbers. (If blank, judge from the images alone.)
- Judge the whole deck, not any single slide.
- Return ONLY the JSON object — no prose, no markdown code fences, no commentary.

DECK SUMMARY (from Pipeline A — deterministic context; do NOT output these fields):
  slide_count: <int or blank>
  density_distribution: <e.g. sparse=10, balanced=9, dense=4, very_dense=1, or blank>
  slides_with_charts: <int>   slides_with_tables: <int>   slides_with_images: <int>
  dominant_title_position: <e.g. top-left, or blank>
  avg_word_count: <float or blank>

FIELDS

deck_type — what this deck is for. One of:
  report          periodic results / status; data plus narrative
  pitch           fundraising or startup pitch; problem -> solution -> ask
  sales           selling a product or service to a prospect
  conference      talk slides for a live audience
  educational     teaching or explaining a topic; course/tutorial material
  internal_memo   internal update or decision doc, low polish
  one_pager       a single dense overview

style_archetype — the deck's overall aesthetic. One of:
  editorial    magazine-like; strong type, generous whitespace, photography
  corporate    conventional business template; brand colors, safe layouts
  minimalist   very sparse; few elements, lots of whitespace
  data_heavy   dominated by charts, tables, dashboards
  playful      bright colors, illustration, informal tone
  technical    diagrams, code, dense engineering detail
  luxury       premium feel; refined type, restrained palette, imagery

narrative_structure — how the deck is organized. One of:
  problem_solution_cta   sets up a problem, presents a solution, asks for action
  data_led_conclusion    builds from data/evidence toward a conclusion
  chronological          ordered by time (timeline, roadmap, history)
  comparison             structured around comparing options or items
  tutorial               step-by-step how-to
  narrative_arc          story-driven (setup -> tension -> resolution)
  reference              reference/catalog with no single throughline

dominant_visual_mode — what carries the deck. One of:
  text_led    mostly text and bullets
  data_led    mostly charts, tables, metrics
  image_led   mostly photography or illustration
  mixed       no single mode dominates

confidence — your confidence per field; each one of: high | medium | low
  keys: deck_type, style_archetype, narrative_structure, dominant_visual_mode

notes — optional free text: anything ambiguous or that the enums don't capture. "" if none.

Return EXACTLY this shape:

{
  "deck_type": "...",
  "style_archetype": "...",
  "narrative_structure": "...",
  "dominant_visual_mode": "...",
  "confidence": {
    "deck_type": "...",
    "style_archetype": "...",
    "narrative_structure": "...",
    "dominant_visual_mode": "..."
  },
  "notes": ""
}
```

### Example DECK SUMMARY block

What `slide-tagger deck-summary` prints (here, the bundled 4-slide sample deck), ready to drop into
the prompt's `DECK SUMMARY` section:

```
DECK SUMMARY (from Pipeline A — deterministic context; do NOT output these fields):
  slide_count: 4
  density_distribution: sparse=3, balanced=1, dense=0, very_dense=0
  slides_with_charts: 1   slides_with_tables: 0   slides_with_images: 0
  dominant_title_position: top-center
  avg_word_count: 10.5
```

### Deck-level enum definitions

New deck-level vocabulary (not in init.md beyond `deck_type`; lock these in `src/schema/enums.py`).
Keep enums narrow — you can split a value later (e.g. `minimalist` → `swiss_minimalist`) if your
corpus shows real separation. Don't add granularity speculatively.

| Field | Values |
|---|---|
| `deck_type` | report · pitch · sales · conference · educational · internal_memo · one_pager |
| `style_archetype` | editorial · corporate · minimalist · data_heavy · playful · technical · luxury |
| `narrative_structure` | problem_solution_cta · data_led_conclusion · chronological · comparison · tutorial · narrative_arc · reference |
| `dominant_visual_mode` | text_led · data_led · image_led · mixed |

### Deck-level rubric

- [ ] **Valid JSON**, parses cleanly, no fences or prose.
- [ ] **Deck-semantic-only** — exactly `deck_type`, `style_archetype`, `narrative_structure`,
      `dominant_visual_mode` (+ `confidence`, `notes`); does NOT echo any DECK SUMMARY number.
- [ ] **Enum discipline** — all four fields use only allowed values.
- [ ] **`dominant_visual_mode` consistent with DECK SUMMARY** — e.g. high `slides_with_charts`
      ⇒ `data_led`; high `slides_with_images` ⇒ `image_led`; mostly text ⇒ `text_led`.
- [ ] **`deck_type` plausible vs. the summary** — e.g. a data-heavy, chart-laden deck is more likely
      `report`/`sales` than `internal_memo`.
- [ ] **Confidence is honest** — ambiguous calls are `medium`/`low`, not `high`.

---

# Per-slide pass

Tag each slide individually, enriched with the deck-level result from above. Run after the
deck-level pass.

## Per-slide flow

1. **Get a slide PNG.** Screenshot one slide, or export a single slide to an image. Any deck works.
2. **Run Pipeline A** for that slide's grounding: `slide-tagger tag <deck>.pptx --slide N`. Paste it
   into the `STRUCTURAL DATA` section of the prompt (see the
   [example block](#example-structural-data-block)). No Pipeline A run? Leave it blank — the VLM
   judges from the image alone (fallback).
3. **Paste the deck-level result** (from the deck-level pass) into the `DECK CONTEXT` section, so the
   VLM interprets this slide within the right kind of deck. (Blank is fine.)
4. **Open claude.ai → new chat.** Model: **Claude Sonnet 4.6** by default; **Opus 4.7** for
   dense/hard slides where vision detail matters.
5. **Attach the PNG** and **paste the [prompt block](#per-slide-prompt-block)** (grounding filled
   in) into the same message; send.
6. **Read the returned JSON.**
7. **Score it** against the [per-slide rubric](#per-slide-rubric).
8. **Iterate:** note what failed, edit the prompt, re-run on the *same* slide, then across slide
   types (title / dense data / image-led). Record each change in the
   [iteration log](#prompt-iteration-log).

> Copy **only** the fenced block in the next section — it is standalone and contains every enum
> definition the model needs.

## Per-slide prompt block

```
You are a presentation-design analyst. You will be shown ONE slide image. Analyze its visual
composition and meaning, then return a single JSON object describing it.

Rules:
- Pick values ONLY from the enumerated options given for each field. Do not invent new values.
- The STRUCTURAL DATA block below is context from Pipeline A's deterministic extraction. USE it to
  inform your judgments, but do NOT echo, recompute, or output those numbers — they are not part of
  your output. (If the block is blank, judge from the image alone.)
- The DECK CONTEXT block tells you what kind of deck this slide belongs to (from the deck-level
  pass). Use it to interpret the slide, but do NOT output it. (Blank is fine.)
- core_message describes the slide's CONTENT (what it says), not its design.
- Return ONLY the JSON object — no prose, no markdown code fences, no commentary.

STRUCTURAL DATA (from Pipeline A — context for your judgments; do NOT output these fields):
  word_count: <int or blank>
  text_blocks: <int or blank>
  visual_elements: <int or blank>
  whitespace_ratio_est: <0.0-1.0 or blank>
  density_bucket: <sparse | balanced | dense | very_dense, or blank>
  title_text: "<verbatim title, or blank>"
  title_position: <e.g. top-left, or blank>
  images: <count / positions, or blank>   charts: <yes/no>   tables: <yes/no>

DECK CONTEXT (from the deck-level pass — interpret this slide within it; do NOT output):
  deck_type: <e.g. report, or blank>
  style_archetype: <e.g. corporate, or blank>
  narrative_structure: <e.g. data_led_conclusion, or blank>
  dominant_visual_mode: <e.g. data_led, or blank>

FIELDS

role — the slide's communicative function. One of:
  title            opening slide; deck/section title, author, date
  section_divider  marks the start of a new section; large label, heavy whitespace
  agenda           list of the deck's sections / table of contents
  content          general explanatory slide (text, bullets, mixed)
  data             slide whose point is a chart, table, or set of metrics
  quote            a pull quote or testimonial as the central element
  image_led        a photo or illustration is the dominant element
  comparison       two or more things set against each other
  timeline         a sequence of events along an axis
  summary          recap / key takeaways / conclusions
  cta              a call to action (next steps, contact, the ask)

layout_archetype — the visual layout pattern. One of:
  title_centered    large title (and optional subtitle) centered, little else
  title_left        title anchored top/left
  section_divider   full-slide divider; large label, heavy whitespace
  single_statement  one short sentence or phrase fills the slide
  stat_hero         one big number/metric dominates, with a small caption
  two_column        content split into two side-by-side columns
  three_column      three side-by-side columns
  bulleted_list     a single region of bulleted or numbered points
  image_text_split  image on one side, text on the other
  full_bleed_image  one image fills the slide edge-to-edge (optional overlaid text)
  image_grid        multiple images arranged in a grid or gallery
  chart_focus       a single chart or graph is dominant
  table             a data table is dominant
  quote             a pull quote with attribution, centered
  comparison        side-by-side or columned comparison of items
  timeline          events laid out along a horizontal or vertical axis
  process_diagram   boxes/arrows showing a flow or sequence of steps
  If none fit well: pick the closest, set confidence.layout_archetype to "low", and describe the
  real layout in notes.

core_message — ONE factual sentence stating what this slide communicates (its content, not its
  design). Example: "Enterprise revenue grew 40% year over year."

emphasis_techniques — the techniques the slide uses to direct attention. Zero or more of:
  hierarchy_by_size          important elements are larger
  hierarchy_by_position      important elements sit where the eye lands first
  hierarchy_by_color         color is used to rank or foreground elements
  isolation_with_whitespace  whitespace isolates a key element
  contrast                   strong tonal/color/scale contrast pulls the eye
  repetition                 a repeated visual motif creates rhythm or grouping
  directional_cues           arrows, lines, gaze, or shapes point at content

(Density and other structural fields are NOT yours to output — they come from Pipeline A. Use the
STRUCTURAL DATA block only as context.)

confidence — your confidence in each hard field; each one of: high | medium | low
  keys: role, layout_archetype, core_message, emphasis_techniques

notes — optional free text: anything ambiguous, off-template, or a role/layout the enums don't
  capture well. Use "" if there is nothing to note.

Return EXACTLY this shape (semantic fields only — no density or other structural fields):

{
  "role": "...",
  "layout_archetype": "...",
  "core_message": "...",
  "emphasis_techniques": ["..."],
  "confidence": {
    "role": "...",
    "layout_archetype": "...",
    "core_message": "...",
    "emphasis_techniques": "..."
  },
  "notes": ""
}
```

## Example structural-data block

What `slide-tagger tag <deck>.pptx --slide N` prints for one slide, ready to drop into the prompt's
`STRUCTURAL DATA` section:

```
STRUCTURAL DATA (from Pipeline A — context for your judgments; do NOT output these fields):
  word_count: 47
  text_blocks: 3
  visual_elements: 1
  whitespace_ratio_est: 0.55
  density_bucket: balanced
  title_text: "Enterprise revenue grew 40% YoY"
  title_position: top-left
  images: 0   charts: yes   tables: no
```

## Per-slide test schema

**What the VLM returns** (Pipeline B — semantic fields only). `confidence` and `notes` are
test-harness aids that surface weak outputs during iteration; they are not part of init.md's locked
schema.

```json
{
  "role": "data",
  "layout_archetype": "chart_focus",
  "core_message": "Enterprise revenue grew 40% year over year.",
  "emphasis_techniques": ["hierarchy_by_size", "hierarchy_by_color"],
  "confidence": {
    "role": "high",
    "layout_archetype": "high",
    "core_message": "medium",
    "emphasis_techniques": "medium"
  },
  "notes": ""
}
```

**The final per-slide record** merges that with Pipeline A's structural fields (`density`, positions,
fonts, etc.) — which the VLM never produces. Merged, it matches init.md's per-slide object:

```json
{
  "role": "data",
  "layout_archetype": "chart_focus",
  "core_message": "Enterprise revenue grew 40% year over year.",
  "emphasis_techniques": ["hierarchy_by_size", "hierarchy_by_color"],
  "density": {
    "word_count": 47,
    "text_blocks": 3,
    "visual_elements": 1,
    "whitespace_ratio_est": 0.55,
    "bucket": "balanced"
  }
}
```

The first block is from Pipeline B (the VLM); `density` in the second comes entirely from Pipeline A.

## Starter `layout_archetype` enum

init.md leaves `layout_archetype` as an undefined "separate layout library (start small, maybe 15-20
archetypes)". This is that starting set — 17 archetypes, mirrored in `src/slide_tagger/schema/enums.py`.
Watch the `notes` field for layouts that don't fit; those are candidates to add.

| Archetype | Definition |
|---|---|
| `title_centered` | Large title (and optional subtitle) centered, little else. |
| `title_left` | Title anchored top/left. |
| `section_divider` | Full-slide divider; large label, heavy whitespace. |
| `single_statement` | One short sentence or phrase fills the slide. |
| `stat_hero` | One big number/metric dominates, with a small caption. |
| `two_column` | Content split into two side-by-side columns. |
| `three_column` | Three side-by-side columns. |
| `bulleted_list` | A single region of bulleted or numbered points. |
| `image_text_split` | Image on one side, text on the other. |
| `full_bleed_image` | One image fills the slide edge-to-edge (optional overlaid text). |
| `image_grid` | Multiple images arranged in a grid or gallery. |
| `chart_focus` | A single chart or graph is dominant. |
| `table` | A data table is dominant. |
| `quote` | A pull quote with attribution, centered. |
| `comparison` | Side-by-side or columned comparison of items. |
| `timeline` | Events laid out along a horizontal or vertical axis. |
| `process_diagram` | Boxes/arrows showing a flow or sequence of steps. |

## Per-slide enum definitions (reference)

These reuse init.md's locked vocabulary verbatim — no new values except `layout_archetype` above.

**`role`** — `title`, `section_divider`, `agenda`, `content`, `data`, `quote`, `image_led`,
`comparison`, `timeline`, `summary`, `cta`. (Definitions inline in the prompt block.)

**`emphasis_techniques`** (pick zero or more):

| Technique | Definition |
|---|---|
| `hierarchy_by_size` | Important elements are larger. |
| `hierarchy_by_position` | Important elements sit where the eye lands first. |
| `hierarchy_by_color` | Color ranks or foregrounds elements. |
| `isolation_with_whitespace` | Whitespace isolates a key element. |
| `contrast` | Strong tonal/color/scale contrast pulls the eye. |
| `repetition` | A repeated visual motif creates rhythm or grouping. |
| `directional_cues` | Arrows, lines, gaze, or shapes point at content. |

**`density.bucket`** — `sparse`, `balanced`, `dense`, `very_dense`. Rough guide: `sparse` <~20 words;
`balanced` ~20-50; `dense` ~50-90; `very_dense` >~90 words or visually crowded. **Produced by
Pipeline A, not the VLM** — listed here for reference and shown in the STRUCTURAL DATA context block.

## Per-slide rubric

Score each output. The VLM returns only semantic fields; structural fields stay with Pipeline A.
Cross-check the semantic output against Pipeline A's numbers (init.md's "Validation against
Pipeline A").

- [ ] **Valid JSON**, parses cleanly, no markdown fences or prose around it.
- [ ] **Semantic-only** — output is exactly `role`, `layout_archetype`, `core_message`,
      `emphasis_techniques` (+ `confidence`, `notes`). It does NOT echo `density`, counts, or any
      structural field from the context block.
- [ ] **Correct types** for each field.
- [ ] **Enum discipline** — `role`, `layout_archetype`, and `emphasis_techniques` use only allowed
      values (no invented ones).
- [ ] **`core_message`** is a single factual sentence about *content*, not design or layout.
- [ ] **Emphasis grounded** — every listed technique is actually visible in the image; none are
      missing that obviously apply.
- [ ] **Role consistent with Pipeline A** — cross-check against the provided numbers: `role: title`
      ⇒ ≤15 words and ≥40% whitespace; `role: data` ⇒ a chart/table/metrics present.
- [ ] **Layout consistent with Pipeline A** — the chosen `layout_archetype` matches the element
      positions/counts Pipeline A reports.
- [ ] **Confidence is honest** — genuinely ambiguous calls are marked `medium`/`low`, not `high`.

If a check fails, that's the signal for what to tweak in the prompt block. Re-run on the same slide
first, then across slide types.

---

## Prompt iteration log

Track both passes here.

| Pass | Version | Date | What changed | Observed effect |
|---|---|---|---|---|
| per-slide | v0 | | initial prompt (this file) | baseline |
| deck-level | v0 | | initial prompt (this file) | baseline |
| | | | | |

## Limitations

- **Deck-level via contact sheet.** Thumbnails lose detail; attach 2–3 full-resolution slides for
  aesthetic calls that need it. Very large decks may need a smaller thumbnail size or multiple sheets.
- **DECK SUMMARY is currently lightweight.** It covers slide count, density mix, chart/table/image
  prevalence, title-position consistency, and average word count. The fuller deck-level extraction
  init.md describes — modal `design_system` (fonts/colors), recurring-element pHash,
  `consistency_score`, `deviations_from_system` — is still to be added to Pipeline A.
- **Rendering not built.** No LibreOffice on this machine, so slide PNGs (and thus the contact
  sheet) come from manual screenshots/exports for now.
- **Clean separation.** The VLM never produces structural fields — Pipeline A owns them and they're
  merged into the record afterward (init.md: "VLMs should only do what they uniquely can"). Both
  prompts port to `src/extractors/semantic/prompts.py` directly. The fallback (blank grounding) only
  drops context; the VLM still returns semantic fields only.
- **Next step:** once the prompts are solid, port them into `src/extractors/semantic/prompts.py`;
  the deck-level and per-slide enums are already locked in `src/slide_tagger/schema/enums.py`.
