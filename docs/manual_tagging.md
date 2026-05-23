# Manual Tagging Guide

How to hand-label a slide deck — and where to actually do it.

## Why hand-label

init.md Phase 1: build a manual reference set *before* automating. Hand-labels are the **ground
truth** the VLM prompts are scored against (see [vlm_prompt_test.md](vlm_prompt_test.md)) and the
target Pipeline B must hit (85%+ match). Hand-labeling also surfaces gaps in the schema before you
build on it. **Don't skip it** — init.md calls this the most common failure mode.

Aim for ~5 reference decks of different types (report, pitch, sales, …).

## What you produce

One JSON file per deck following the `DeckTag` schema
([src/slide_tagger/schema/tagged.py](../src/slide_tagger/schema/tagged.py)):

- **Structural fields** — `density`, `title_*`, `has_chart`, `design_system` fonts/colors, etc.
  These are **already filled by Pipeline A. Don't touch them.**
- **Semantic fields** — `role`, `layout_archetype`, `core_message`, `emphasis_techniques` per slide;
  `deck_type`, `style_archetype`, `narrative_structure`, `dominant_visual_mode` per deck; plus the
  deck-wise `design_system.grid` and each `design_system.recurring_elements[].type`. **You fill
  these in.** They start as `null` / `[]`.

## Where to do it

There is no separate GUI — you tag by **editing the generated JSON template in your code editor**
(VS Code), while **looking at the slides** in another window:

1. The JSON template (one object per slide under `slides`, plus deck-level fields at the top).
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

The template has every structural field filled and every semantic field set to `null` / `[]`. A
`_legend` block at the top lists the allowed values for each field (it's ignored on validation, so
you can leave it or delete it).

> A ready-made example already exists: [tmp/pwc1_template.json](../tmp/pwc1_template.json) (the PwC
> Global Top 100 deck).

### 2. Fill in the semantic fields

Open the JSON and the slides side by side. For **each slide object**, set:

| Field | What to put |
|---|---|
| `role` | The slide's communicative function (one value — see [reference](#slide-fields)). |
| `layout_archetype` | The visual layout pattern (one value). |
| `core_message` | ONE factual sentence about the slide's **content**, not its design. |
| `emphasis_techniques` | A list of the attention-directing techniques actually visible (0 or more). |

At the **top of the file**, set the deck-level fields: `deck_type`, `style_archetype`,
`narrative_structure`, `dominant_visual_mode`.

In **`design_system`**, set the hand-label fields: `grid`, and the `type` of each entry in
`recurring_elements` (Pipeline A detected *where* each repeats; you say *what* it is). Leave the
auto-extracted fonts/colors as they are — fix one only if it's clearly wrong.

Leave all other (structural) fields untouched.

### 3. Validate

```bash
uv run slide-tagger validate reference_data/hand_labels/your-deck.json
```

It checks every value against the allowed set (catching typos like `role: "headline"`) and reports
completeness:

```
✓ Schema valid: your-deck.json
Deck-level: 2/4 filled  (missing: narrative_structure, dominant_visual_mode)
Slides fully tagged: 18/22  (incomplete: [7, 12, 19, 21])
Recurring elements typed: 0/1  (untyped indices: [0])  · grid: unset
```

Repeat fill → validate until everything reads as complete.

## Field reference

Pick **only** these values (the `_legend` block in your template lists them too). Definitions match
[vlm_prompt_test.md](vlm_prompt_test.md).

### Slide fields

**`role`** — one of:

| Value | Meaning |
|---|---|
| `title` | Opening slide; deck/section title, author, date. |
| `section_divider` | Marks the start of a new section; large label, heavy whitespace. |
| `agenda` | List of the deck's sections / table of contents. |
| `content` | General explanatory slide (text, bullets, mixed). |
| `data` | Slide whose point is a chart, table, or set of metrics. |
| `quote` | A pull quote or testimonial as the central element. |
| `image_led` | A photo or illustration is the dominant element. |
| `comparison` | Two or more things set against each other. |
| `timeline` | A sequence of events along an axis. |
| `summary` | Recap / key takeaways / conclusions. |
| `cta` | A call to action (next steps, contact, the ask). |

**`layout_archetype`** — one of: `title_centered`, `title_left`, `section_divider`,
`single_statement`, `stat_hero`, `two_column`, `three_column`, `bulleted_list`, `image_text_split`,
`full_bleed_image`, `image_grid`, `chart_focus`, `table`, `quote`, `comparison`, `timeline`,
`process_diagram`. (Definitions: [vlm_prompt_test.md → Starter layout_archetype enum](vlm_prompt_test.md).)
If none fit, pick the closest and note it.

**`emphasis_techniques`** — zero or more of:

| Value | Meaning |
|---|---|
| `hierarchy_by_size` | Important elements are larger. |
| `hierarchy_by_position` | Important elements sit where the eye lands first. |
| `hierarchy_by_color` | Color ranks or foregrounds elements. |
| `isolation_with_whitespace` | Whitespace isolates a key element. |
| `contrast` | Strong tonal/color/scale contrast pulls the eye. |
| `repetition` | A repeated visual motif creates rhythm or grouping. |
| `directional_cues` | Arrows, lines, gaze, or shapes point at content. |

### Deck fields

| Field | Allowed values |
|---|---|
| `deck_type` | report · pitch · sales · conference · educational · internal_memo · one_pager |
| `style_archetype` | editorial · corporate · minimalist · data_heavy · playful · technical · luxury |
| `narrative_structure` | problem_solution_cta · data_led_conclusion · chronological · comparison · tutorial · narrative_arc · reference |
| `dominant_visual_mode` | text_led · data_led · image_led · mixed |

### Design-system hand-label fields

| Field | Allowed values | What it is |
|---|---|---|
| `design_system.grid` | 12-column · 6-column · free | The deck's underlying column grid (eyeball it). |
| `design_system.recurring_elements[].type` | logo · page_number · footer · watermark | What each detected repeating element is. |

## Tips

- **`core_message`** = what the slide *says*, in one sentence (e.g. "Enterprise revenue grew 40% YoY"),
  not how it looks. Skip slides that have no message (a bare section divider can be `""`).
- **`emphasis_techniques`** = only techniques you can actually see being used; an empty list is fine.
- **Be consistent across decks** — the same kind of slide should get the same tags. That consistency
  is what makes the reference set useful.
- **When unsure**, pick the closest value and add a note in `notes` (per slide) — those notes flag
  where the schema's vocabulary may need to grow.

## How this feeds the rest

Your hand-labels are the answer key. The VLM prompt loop in
[vlm_prompt_test.md](vlm_prompt_test.md) is scored against them, and Pipeline B's accuracy target is
measured against them. Tag deliberately — everything downstream trusts these labels.
