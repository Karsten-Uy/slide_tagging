# Deck Tagging Enrichment — Claude Code Prompt

A reusable prompt that takes the structural JSON `slide-tagger template` produces and enriches it with
the full three-level tagging schema (deck-level + slide-level + element-level rules). Designed to be
invoked from Claude Code with the source deck and the partial JSON as inputs. This is the **canonical
prompt** for the enrichment (semantic / VLM) pass; the field set here is mirrored 1:1 in
[`src/slide_tagger/schema/enums.py`](../src/slide_tagger/schema/enums.py) and
[`src/slide_tagger/schema/tagged.py`](../src/slide_tagger/schema/tagged.py).

## How to invoke

```bash
# 1. Produce the partial (structural) JSON with Pipeline A:
uv run slide-tagger template data/source/<deck>.pptx > input.json

# 2. Enrich it from the directory containing the deck and input.json:
claude "$(cat docs/deck_tagging_prompt.md)" \
  --include input.json \
  --include data/source/<deck>.pdf   # or .pptx
```

Or interactively in Claude Code, paste the prompt below and reference the two input files.

---

## The Prompt

You are an expert at tagging consulting and business presentation decks for a knowledge-retrieval and content-generation system. Your job is to take a partially-completed structural extraction JSON plus the source deck file, read the deck thoroughly, and output an enriched JSON with all tagging dimensions filled in.

### Inputs you will receive

1. **Partial JSON** (`input.json`) — produced by `slide-tagger template` (Pipeline A structural extraction). Contains: source filename, slide count, design system colors/fonts, per-slide structural metadata (title text, position, image/chart/table presence, density metrics). All enrichment fields are `null` / `[]` and need to be filled in.

2. **Source deck** (`.pdf` or `.pptx`) — the actual deck content. Read this thoroughly to understand the narrative, audience, and individual slide messages. Do not rely on the JSON alone for content tagging.

### Your task

Produce an enriched JSON that:
- Preserves every field in the input JSON exactly as-is (all Pipeline A structural fields, the `design_system` block, and `deck_length`)
- Fills in all `null` enrichment fields using the controlled vocabularies in `_legend`
- Fills the new deck-, slide-, and element-level fields specified below
- Fills the `provenance` block recording what was filled in by you vs. extracted by the script

### Schema (three levels)

#### Deck-level (top-level object)

```json
{
  "client_industry": "Financial Services | Tech | Healthcare | Public Sector | Industrials | Consumer | Energy | Education | Cross-industry",
  "client_sub_industry": "string (free text within the industry, e.g., 'Asset Management' for FS)",
  "client_type": "Public sector | Private F500 | Private mid-market | Government agency | Non-profit | Internal/thought-leadership",
  "engagement_stage": "RFP response | Pitch / opportunity dev | Kickoff | Mid-project readout | Weekly update | Final delivery | POV / thought leadership",
  "content_area": ["array of strings from: Strategy, Digital transformation, SDLC, AI/ML, ERP, M&A, Operational excellence, Org design, Cost reduction, Risk, Market analysis, ESG, Workforce, Financial reporting, Other"],
  "audience_level": "C-suite / board | Senior executives | Operating committee | Working team | External / public",
  "deliverable_format": "PowerPoint | PDF | Hybrid | Online interactive",
  "geography": "US | UK | EMEA | APAC | Global | Regional (specify)",
  "deck_length": "integer (matches slide_count; pre-filled by Pipeline A)",
  "confidentiality_tier": "Public | Internal | Client-confidential | Restricted",
  "inferred_publisher": "string (best guess at firm if not stated, e.g., 'PwC', 'McKinsey')",
  "deck_summary_one_sentence": "string (single sentence describing what this deck is)"
}
```

#### Slide-level (each object in `slides[]`)

```json
{
  "slide_purpose": "Title | Section divider | Agenda / Contents | Exec summary | Context-setting | Current state | Finding | Insight | Recommendation | Framework | Roadmap | Timeline | Comparison | Decision matrix | Data presentation | Case study | Team intro | Methodology | Pricing | Q&A | Appendix / reference | Closing / contacts",
  "message_type": "Assertion | Comparison | Sequence / timeline | Decomposition (parts of whole) | Causation | Trend over time | Trade-off | Process flow | Listing / enumeration | Single statistic / hero number | No clear message",
  "audience_level_slide": "C-suite / board | Senior executives | Operating committee | Working team | External / public | Same as deck",
  "slide_position_role": "Hero / headline | Build / setup | Evidence / backup | Synthesis / takeaway | Transition / divider",
  "main_message": "string (action title or one-sentence summary of the slide's main point — extract from title if it's an action title, otherwise infer from content)",
  "dominant_visual_element": "Chart | Diagram | Table | Image | Icon-based | Framework graphic | Pure text | Mixed",
  "chart_type": "Line | Bar | Stacked bar | Pie | Waterfall | Scatter | Bubble | Treemap | Heat map | Sankey | Other | N/A (if dominant_visual_element != Chart)",
  "placeholder_compliance": "Pristine (uses master placeholders) | Reusable (custom but consistent) | Bespoke (one-off layout) | Broken (would not survive content swap)",
  "embedded_data_present": "true if chart objects contain real data, false if charts are images/screenshots",
  "zones": [
    {"name": "string (e.g., 'title', 'main-content', 'callout', 'footer')", "region": "string (e.g., 'top-band', 'center-2col-left', 'bottom-band')"}
  ],
  "slot_types_present": ["array from: title, subtitle, body-text, bullet-list, chart, image, table, callout-box, citation, footer, page-number"],
  "reusability_score_qualitative": "High | Medium | Low (your judgment of how reusable this slide is across contexts)",
  "tier_match_difficulty": "Likely Tier 1 candidate | Likely Tier 2 | Likely Tier 3 | Likely Tier 4 (your judgment of how hard it would be to find a near-match for this slide in a corpus)"
}
```

#### Element-level (`inferred_rules` block)

Extract style rules from observed practice across the deck. These are *inferred* (not authoritative) and flagged as such (`scope_tag: "inferred"`) for human curation against the firm's brand guide.

```json
{
  "inferred_rules": {
    "title": {
      "font_family_observed": ["array of fonts observed"],
      "size_pt_range": [min, max],
      "size_pt_most_common": number,
      "weight_observed": ["array of weights observed"],
      "color_hex_observed": ["array of colors observed"],
      "position_most_common": "top-left | top-center | top-right",
      "alignment_most_common": "left | center | right",
      "uses_action_titles": "always | sometimes | rarely (based on whether titles are full sentences making a point)",
      "max_chars_observed": number,
      "scope_tag": "inferred"
    },
    "body_text": {
      "font_family_observed": ["array"],
      "size_pt_range": [min, max],
      "size_pt_most_common": number,
      "color_hex_observed": ["array"],
      "alignment_most_common": "left | center | right | justify",
      "scope_tag": "inferred"
    },
    "color_palette": {
      "primary_observed": "string hex",
      "accent_observed": "string hex",
      "neutrals_observed": ["array of hexes"],
      "notes": "any observations about how colors are used (e.g., 'primary used only for highlights')",
      "scope_tag": "inferred"
    },
    "chart_styling": {
      "uses_consistent_palette": "true | false | n/a",
      "notes": "string observations",
      "scope_tag": "inferred"
    },
    "layout_conventions": {
      "uses_master_template": "true | false | mixed (observation about placeholder_compliance distribution across slides)",
      "no_fly_zones_observed": "string description of areas kept clear",
      "scope_tag": "inferred"
    }
  }
}
```

#### Provenance block (top level)

```json
{
  "provenance": {
    "tagged_by": "claude (model name and date)",
    "input_json_source": "automated structural extraction",
    "fields_filled_by_ai": ["list of field paths that were null in input and were filled by you"],
    "confidence_notes": "string — flag any fields where you had low confidence and recommend human review"
  }
}
```

### Tagging principles

1. **Preserve everything from the input JSON.** Do not modify existing populated fields. Do not remove the `_legend` block. Only add or fill in `null` / `[]` fields.

2. **Use the `_legend` enums.** Every enumerated field must use ONLY values listed in the `_legend` block (which is generated from the schema). Do not invent new enum values. If a value doesn't fit, use the closest (or "Other" where offered) and explain in `confidence_notes`.

3. **Read the actual deck content** for fields requiring semantic understanding (`main_message`, `message_type`, `audience_level`, `content_area`, `deck_summary_one_sentence`). Do not infer these from title text alone — open the source deck.

4. **For `main_message`:** if the slide's title is already an action title (a full sentence making a point), use the title verbatim. If it's a descriptive title ("Highlights", "Methodology"), infer the main message from the slide's content and write it as a single sentence.

5. **For `tier_match_difficulty`:** consider whether this slide's combination of purpose + layout + message type + density is common (Tier 1-2 likely) or unusual (Tier 3-4 likely). Section dividers, title slides, agenda slides, and standard data tables are usually Tier 1-2. Bespoke diagrams, unusual charts, custom infographics are usually Tier 3-4.

6. **For `inferred_rules`:** aggregate observations across ALL slides to extract patterns. A rule isn't "the title on slide 5 was Arial 24pt" — it's "across the deck, titles range from 22-32pt, most commonly 28pt, in Arial." Keep `scope_tag` as `inferred` always — these are observations, not authoritative rules.

7. **For low-confidence tags, populate them but flag in `confidence_notes`.** Better a best-guess with a flag than a null field.

### Output format

Return ONLY the enriched JSON. Do not include any explanatory text, markdown formatting, or code fences in the output. The JSON should be valid, parseable, and ready to write to disk. Start the response with `{` and end with `}`.

Validate the result with:

```bash
uv run slide-tagger validate enriched.json
```

### Brief reasoning step (before output)

Before producing the JSON, briefly think through (in `<thinking>` tags that won't appear in the final output): (1) what kind of deck is this (industry, purpose, audience)? (2) what's the narrative arc? (3) what slide types are present and what's the overall structure? (4) what style patterns are observable? Then produce the JSON.

---

## Notes on using this prompt at scale

### When this prompt works well
- The source deck content is accessible (PDF readable, PPTX text extractable)
- The deck has a clear purpose and audience
- The deck has consistent styling (helps `inferred_rules` extraction)

### When it needs human review
- Cross-industry decks where `client_industry` is ambiguous
- Decks with non-English content
- Highly stylized or unconventional decks (Tier 3-4 territory)
- Decks where `placeholder_compliance` is "Bespoke" for many slides (suggests the structural extraction may have been imprecise)

### Batch invocation pattern

For tagging a corpus of decks, invoke this prompt per-deck rather than batching multiple decks into one call. This keeps context per-deck clean and prevents cross-deck contamination of `inferred_rules`.

```bash
for json_file in extractions/*.json; do
  deck_name=$(basename "$json_file" .json)
  pdf_file="decks/${deck_name}.pdf"

  claude "$(cat docs/deck_tagging_prompt.md)" \
    --include "$json_file" \
    --include "$pdf_file" \
    > "enriched/${deck_name}.enriched.json"
done
```

### Next pipeline step

Once you have a corpus of enriched JSON files, the natural next step is:
1. **Aggregate `inferred_rules` across the corpus** — true firm-wide rules emerge from frequency, not from any single deck. A deck-level inferred rule has scope `inferred`; an aggregated rule across N decks with X% consistency becomes `firm_inferred` or `firm_observed`.
2. **Build the retrieval index** — embed slide-level `main_message` + `slide_purpose` into a vector store; index deck-level tags for filtering.
3. **Stand up the Tier 1-4 routing** — given a new storyboard point, query the index, calculate match scores, route to the appropriate generation tier.

### Calibration tip

Run this prompt on 3-5 decks you know well, then audit the output by hand. Tune the schema or prompt language for any fields where the model consistently misclassifies. Typical first-pass issues:
- `audience_level` over-defaulting to "C-suite / board" — not every important deck is C-suite.
- `message_type` confusion between "Assertion" and "Trend over time" — add examples.
- `placeholder_compliance` over-marking slides as "Pristine" — custom text boxes (not master placeholders) = Reusable or Bespoke, not Pristine.
