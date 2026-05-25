# digital-auto-report-2023 — hand-label review

Evidence-based audit of `digital-auto-report-2023.tagged.json` against the rendered
slides (poppler) and the VLM consensus across 5 bench runs. Purpose: find places the
**hand-label is wrong** so the answer key can be corrected — the v2 prompt was being
penalized for being right on several fields.

**Verdict key:** 🔴 label wrong (fix it) · 🟡 contested / labeler-systematic (your call) ·
⚪ genuinely borderline (pick a convention or leave).

## Status: applied 2026-05-24
The 🔴 `dominant_visual_element` fixes (slides 0, 3, 19, 20, 21, 27, 33, 38, 39) plus slide 19's
`chart_type`→Pie and `embedded_data_present`→true were applied to the JSON. **Re-scoring the existing
5 bench predictions against the corrected labels: digital-auto 70.9% → 73.1%** (no new API spend).
**Skipped on re-inspection:** slide 4 (`dom` is genuinely `Mixed`, so `chart_type=N/A` is
convention-correct — only `embedded` was debatable, left alone) and slide 31 (`dom=Mixed`, so
`chart_type=N/A` is correct; the VLM's "Waterfall" was *it* breaking the convention). The 🟡 and ⚪
items below are left for your judgment.

Slide index is 0-based (= PDF page − 1). VLM value is the modal across 5 runs.

**Alignment verified (not an off-by-one).** Matching each `main_message` against the pptx slide
text scores 73% at offset 0 vs ~20% at ±1 — and `main_message[i]` describes the same slide its
other fields do (e.g. `main_message[21]` = "Getting the user interface right" sits on the photo
divider that is pptx slide #22 / index 21). So these are genuine per-field value errors, not a
slide-number shift; fix the **values**, don't renumber.

---

## 🔴 High-confidence label errors — fix these

The labeler called every **section-header / photo / cover** slide `Pure text` (ignoring
the photo), and marked two **chart** slides as text with no data. The VLM is correct.

| slide | field | current label | should be | what the slide actually shows |
|---|---|---|---|---|
| 0 | dominant_visual_element | Pure text | **Image** | full-bleed aerial-city photo cover |
| 3 | dominant_visual_element | Pure text | **Image** (≥ Mixed) | "Contents" with a large car-interior photo |
| 19 | dominant_visual_element | Pure text | **Chart** | donut/pie charts of CO₂ % by country |
| 19 | chart_type | N/A | **Pie** | the donut charts above |
| 19 | embedded_data_present | false | **true** | real % survey data in the charts |
| 20 | dominant_visual_element | Pure text | **Image** (≥ Mixed) | "Contents" with a car-interior photo |
| 21 | dominant_visual_element | Pure text | **Image** | full-bleed photo, "Getting the user interface right" |
| 27 | dominant_visual_element | Pure text | **Image** | full-bleed car photo, "Rethinking vehicle sales" |
| 33 | dominant_visual_element | Pure text | **Image** | full-bleed dashboard photo, "Going beyond the vehicle" |
| 38 | dominant_visual_element | Pure text | **Framework graphic** | radial prosumer-ecosystem diagram |
| 39 | dominant_visual_element | Pure text | **Mixed** (≥ Image) | grid of contact headshots |
| 4 | chart_type | N/A | **Bar** / Stacked bar | survey bar charts |
| 4 | embedded_data_present | false | **true** | survey bar data |
| 31 | chart_type | N/A | **a real chart** (≈ Waterfall) | waterfall/stacked chart present |

That's ~9 `dominant_visual_element` + 4 chart/data fixes. Applying them **raises** digital-auto's
score (the VLM was right). The prompt needs no change for these.

---

## 🟡 Contested / labeler-systematic — review, but do NOT tune the prompt to them

These look like *labeler conventions* that are debatable; on the evidence the VLM is often as
defensible as the label. Decide your convention, then fix whichever side you choose — but don't
chase them with prompt edits.

- **`placeholder_compliance` — blanket `Reusable` (slides 1, 4, 22–26, 28–32, 34, 36–38).** The
  labeler marked nearly everything `Reusable`; the VLM says `Bespoke`. For the standard
  title-band + chart + right-callout slides, `Reusable` is right. But slides 22/23/24/29/30/34/37/38
  are genuinely **one-off custom infographics** (radial diagrams, the 3×3 lifecycle, the stakeholder
  map) — `Bespoke` is defensible there. Your call hinges on whether "reusable" means the *skeleton*
  or the *whole slide*.
- **`tier_match_difficulty` — VLM rates one tier harder almost everywhere** (Tier2→3, Tier3→4). Given
  how custom these infographics are, the VLM's "harder to find a near-match" is arguably more honest.
- **`slide_purpose`:** slide 20 `Section divider`→**`Agenda / Contents`** (VLM right — it's a contents
  page); slides 6 & 10 `Comparison`→`Finding` (both defensible — they compare regions *and* state a
  takeaway); slide 1 `Methodology`→`Context-setting`.
- **`message_type`:** slides 15 & 17 `Trend over time`→`Comparison` (they compare 3 regions, not a
  time series — VLM defensible); slides 23/26/30 `Trade-off`↔`Sequence/timeline` etc. — taxonomy calls.

---

## ⚪ Genuinely borderline visual — no clear winner

Matrices and diagrams that legitimately sit between two enum values. Pick a convention (e.g. "rows×cols
of cells = Table; boxes+arrows conveying a model = Framework graphic; flow/network schematic = Diagram")
and apply it consistently; otherwise leave as-is.

| slide | label ↔ VLM | what it is |
|---|---|---|
| 24 | Framework graphic ↔ Table | portfolio matrix (rows × columns) |
| 30 | Table ↔ Framework graphic | 3×3 lifecycle matrix + ownership table |
| 29, 32, 37 | Framework graphic ↔ Diagram | flow / two-column / stakeholder schematics |
| 35 | Chart ↔ Mixed | bar chart + supporting text |

---

## Bottom line
- **Fix the 🔴 rows** (~13 cells, mostly `dominant_visual_element`) — those are real answer-key errors.
- **Don't change the prompt** for any of this; the v2 prompt is already correct where the label is wrong.
- After fixing, re-run `bench` — digital-auto's number should rise, and it becomes a trustworthy
  second reference alongside nigeria.
- The systematic nature of these errors (every section-header → "Pure text") suggests the *other*
  slide-level fields on this deck deserve a spot-check too.
