# Manual Tagging Guide

How to hand-label a slide deck — and where to actually do it.

## Why hand-label

init.md Phase 1: build a manual reference set *before* automating. Hand-labels are the **ground
truth** the enrichment prompt is scored against (see [vlm_prompt_test.md](vlm_prompt_test.md)) and the
target Pipeline B must hit. Hand-labeling also surfaces gaps in the schema before you build on it.
**Don't skip it** — init.md calls this the most common failure mode.

Aim for ~5 reference decks of different types (report, pitch, sales, …).

## What you produce

One JSON file per deck following the `DeckTag` schema
([src/slide_tagger/schema/tagged.py](../src/slide_tagger/schema/tagged.py)):

- **Structural fields** — `density`, `title_*`, `has_chart`, `design_system` fonts/colors, etc.
  These are **already filled by Pipeline A. Don't touch them.**
- **Enrichment fields** — the deck-, slide-, and element-level semantic fields. **You fill these
  in.** They start as `null` / `[]`. Three levels:
  - *Deck-level:* `client_industry`, `client_sub_industry`, `client_type`, `engagement_stage`,
    `content_area`, `audience_level`, `deliverable_format`, `geography`, `confidentiality_tier`,
    `inferred_publisher`, `deck_summary_one_sentence`. (`deck_length` is pre-filled = `slide_count`.)
  - *Slide-level (per object in `slides[]`):* `slide_purpose`, `message_type`, `audience_level_slide`,
    `slide_position_role`, `main_message`, `dominant_visual_element`, `chart_type`,
    `placeholder_compliance`, `embedded_data_present`, `zones`, `slot_types_present`,
    `reusability_score_qualitative`, `tier_match_difficulty`.
  - *Element-level (`inferred_rules`):* `title`, `body_text`, `color_palette`, `chart_styling`,
    `layout_conventions` — deck-wide style observations, each flagged `scope_tag: "inferred"`.
  - *`provenance`:* who tagged it and any low-confidence notes.
- The deck-wise `design_system.grid` and each `design_system.recurring_elements[].type` are also
  hand-labeled (Pipeline A detects *where* each element repeats; you say *what* it is).

## Where to do it

There is no separate GUI — you tag by **editing the generated JSON template in your code editor**
(VS Code), while **looking at the slides** in another window:

1. The JSON template (one object per slide under `slides`, plus deck-level fields at the top,
   `inferred_rules`, and `provenance`).
2. The slide images. Rendering isn't built yet, so open the source `.pptx` in
   PowerPoint / LibreOffice / Google Slides, or screenshot slides. **Slide `index` is 0-based** —
   `index: 0` is the first slide.

Keep finished labels in `reference_data/hand_labels/<deck_id>.json` (tracked in git — this is
ground truth worth keeping).

## Workflow

### 1. Generate a template

```bash
# From a deck (includes the auto-extracted design_system):
uv run slide-tagger template data/source/your-deck.pptx > reference_data/hand_labels/your-deck.json

# Or from an existing Pipeline A structural JSON:
uv run slide-tagger template tmp/pwc1.json > reference_data/hand_labels/pwc.json
```

The template has every structural field filled and every enrichment field set to `null` / `[]`. A
`_legend` block at the top lists the allowed values for each enumerated field (it's ignored on
validation, so you can leave it or delete it).

### 2. Fill in the enrichment fields

Open the JSON and the slides side by side.

At the **top of the file**, set the deck-level fields and the `inferred_rules` block (deck-wide style
aggregates — e.g. "titles range 22-32pt, most commonly 28pt, in Arial"). In **`design_system`**, set
`grid` and the `type` of each entry in `recurring_elements`; leave the auto-extracted fonts/colors as
they are (fix one only if it's clearly wrong).

For **each slide object**, set the slide-level fields (see the [reference](#slide-fields)).

Fill in `provenance.tagged_by` (e.g. "hand-labeled, <your name>, <date>") and note any low-confidence
calls in `provenance.confidence_notes`. Leave all other (structural) fields untouched.

### 3. Validate

```bash
uv run slide-tagger validate reference_data/hand_labels/your-deck.json
```

It checks every value against the allowed set (catching typos like `slide_purpose: "headline"`) and
reports completeness:

```
✓ Schema valid: your-deck.json
Deck-level: 9/11 filled  (missing: client_sub_industry, inferred_publisher)
Slides fully tagged: 18/22  (incomplete: [7, 12, 19, 21])
Recurring elements typed: 0/1  (untyped indices: [0])  · grid: unset
Inferred rules: populated  ·  provenance: set
```

A slide counts as "fully tagged" once its core fields (`slide_purpose`, `message_type`,
`main_message`, `dominant_visual_element`) are set. Repeat fill → validate until everything reads as
complete.

## Field reference

Pick **only** these values (the `_legend` block in your template lists them too). Definitions match
[deck_tagging_prompt.md](deck_tagging_prompt.md).

### Slide fields

| Field | What to put |
|---|---|
| `slide_purpose` | The slide's function (one of: Title, Section divider, Agenda / Contents, Exec summary, Context-setting, Current state, Finding, Insight, Recommendation, Framework, Roadmap, Timeline, Comparison, Decision matrix, Data presentation, Case study, Team intro, Methodology, Pricing, Q&A, Appendix / reference, Closing / contacts). |
| `message_type` | The kind of point it makes (Assertion · Comparison · Sequence / timeline · Decomposition (parts of whole) · Causation · Trend over time · Trade-off · Process flow · Listing / enumeration · Single statistic / hero number · No clear message). |
| `audience_level_slide` | Who this slide targets (same options as deck `audience_level`, plus "Same as deck"). |
| `slide_position_role` | Its role in the flow (Hero / headline · Build / setup · Evidence / backup · Synthesis / takeaway · Transition / divider). |
| `main_message` | ONE factual sentence: the action title verbatim if the title already makes a point; otherwise infer from content. |
| `dominant_visual_element` | Chart · Diagram · Table · Image · Icon-based · Framework graphic · Pure text · Mixed. |
| `chart_type` | Line · Bar · Stacked bar · Pie · Waterfall · Scatter · Bubble · Treemap · Heat map · Sankey · Other · N/A (use N/A unless `dominant_visual_element` is Chart). |
| `placeholder_compliance` | Pristine (master placeholders) · Reusable (custom but consistent) · Bespoke (one-off) · Broken (won't survive a content swap). |
| `embedded_data_present` | `true` if charts contain real data, `false` if they're images/screenshots. |
| `zones` | List of `{ "name": ..., "region": ... }` for the slide's regions (e.g. title / main-content / callout / footer). |
| `slot_types_present` | List from: title, subtitle, body-text, bullet-list, chart, image, table, callout-box, citation, footer, page-number. |
| `reusability_score_qualitative` | High · Medium · Low — how reusable this slide is across contexts. |
| `tier_match_difficulty` | Likely Tier 1 candidate · Likely Tier 2 · Likely Tier 3 · Likely Tier 4 — how hard to find a near-match in a corpus. |

### Deck fields

| Field | Allowed values |
|---|---|
| `client_industry` | Financial Services · Tech · Healthcare · Public Sector · Industrials · Consumer · Energy · Education · Cross-industry |
| `client_sub_industry` | Free text within the industry (e.g. "Asset Management"). |
| `client_type` | Public sector · Private F500 · Private mid-market · Government agency · Non-profit · Internal/thought-leadership |
| `engagement_stage` | RFP response · Pitch / opportunity dev · Kickoff · Mid-project readout · Weekly update · Final delivery · POV / thought leadership |
| `content_area` | List from: Strategy, Digital transformation, SDLC, AI/ML, ERP, M&A, Operational excellence, Org design, Cost reduction, Risk, Market analysis, ESG, Workforce, Financial reporting, Other |
| `audience_level` | C-suite / board · Senior executives · Operating committee · Working team · External / public |
| `deliverable_format` | PowerPoint · PDF · Hybrid · Online interactive |
| `geography` | US · UK · EMEA · APAC · Global · Regional (specify) |
| `confidentiality_tier` | Public · Internal · Client-confidential · Restricted |
| `inferred_publisher` | Free text — best guess at the firm (e.g. "PwC"). |
| `deck_summary_one_sentence` | Free text — one sentence describing what this deck is. |

### Element-level (`inferred_rules`) fields

Deck-wide style aggregates — observe across **all** slides, not one. Enumerated sub-fields:

| Field | Allowed values |
|---|---|
| `inferred_rules.title.position_most_common` | top-left · top-center · top-right (any `Position` value) |
| `inferred_rules.title.alignment_most_common` | left · center · right (any `TextAlignment` value) |
| `inferred_rules.title.uses_action_titles` | always · sometimes · rarely |
| `inferred_rules.body_text.alignment_most_common` | left · center · right · justify |
| `inferred_rules.chart_styling.uses_consistent_palette` | true · false · n/a |
| `inferred_rules.layout_conventions.uses_master_template` | true · false · mixed |

The `*_observed` arrays (fonts, weights, hexes), `size_pt_range`/`size_pt_most_common`,
`max_chars_observed`, and `notes` are free observations. Keep every `scope_tag` as `inferred`.

### Design-system hand-label fields

| Field | Allowed values | What it is |
|---|---|---|
| `design_system.grid` | 12-column · 6-column · free | The deck's underlying column grid (eyeball it). |
| `design_system.recurring_elements[].type` | logo · page_number · footer · watermark | What each detected repeating element is. |

## Tips

- **`main_message`** = what the slide *says*, in one sentence (e.g. "Enterprise revenue grew 40% YoY"),
  not how it looks. Use the title verbatim when it's already an action title.
- **`inferred_rules`** = patterns across the whole deck, not one slide. "Titles 22-32pt, mostly 28pt,
  Arial" — not "slide 5 was Arial 24pt".
- **`audience_level`** isn't always "C-suite / board" — judge honestly.
- **Be consistent across decks** — the same kind of slide should get the same tags. That consistency
  is what makes the reference set useful.
- **When unsure**, pick the closest value and flag it in `provenance.confidence_notes` — those notes
  show where the schema's vocabulary may need to grow.

## How this feeds the rest

Your hand-labels are the answer key. The enrichment prompt loop in
[vlm_prompt_test.md](vlm_prompt_test.md) is scored against them, and Pipeline B's accuracy is measured
against them. Tag deliberately — everything downstream trusts these labels.
