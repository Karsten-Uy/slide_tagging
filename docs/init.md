# Slide Deck Tagging Service: Architecture

## Goal

Build a service that ingests slide decks (.pptx, .pdf) and produces structured design and semantic metadata. The output is a tagged corpus that downstream AI slide generators can retrieve from and condition on, so they produce slides that respect a real design system instead of generic defaults.

## Core insight

Most AI slide tools fail because they treat design as an aesthetic label ("minimalist", "modern") that gives a model nothing to act on. The leverage point is turning design into a spec the model can execute against: token-level decisions (color, type, spacing), composition patterns (layout archetypes per slide), and system-level rules (the standards a deck follows consistently).

Tags must be:
1. **Compositional**: design DNA can be applied to new content
2. **Actionable**: every tag changes what a model would generate
3. **Separable from content**: the schema describes the design, not the specific words

## Architecture overview

Two parallel extraction pipelines feeding one unified schema.

```
                    ┌──────────────────────┐
                    │   Deck (.pptx/.pdf)  │
                    └──────────┬───────────┘
                               │
                ┌──────────────┴──────────────┐
                │                             │
                ▼                             ▼
    ┌───────────────────────┐    ┌────────────────────────┐
    │   Pipeline A          │    │   Pipeline B           │
    │   Structural          │    │   Semantic (VLM)       │
    │   (deterministic)     │    │                        │
    │                       │    │                        │
    │ - parse source file   │    │ - render slides to PNG │
    │ - extract per-slide   │    │ - VLM call per slide   │
    │   structural data     │    │   with constrained     │
    │ - aggregate to        │    │   schema               │
    │   deck-level patterns │    │ - validate against     │
    │                       │    │   Pipeline A output    │
    └───────────┬───────────┘    └───────────┬────────────┘
                │                            │
                └────────────┬───────────────┘
                             ▼
                ┌────────────────────────┐
                │   Unified JSON schema  │
                │   (one file per deck)  │
                └────────────┬───────────┘
                             ▼
                ┌────────────────────────┐
                │   Storage + retrieval  │
                │   (JSON + embeddings)  │
                └────────────────────────┘
```

Pipeline A is deterministic and runs first. Pipeline B uses A's output to ground itself and avoid hallucination.

## The schema (the contract)

Everything in the system writes to this schema. Lock it before building anything else. Use Pydantic models for validation.

```json
{
  "deck": {
    "id": "uuid",
    "source_filename": "string",
    "source_format": "pptx | pdf",
    "slide_count": 24,
    "deck_type": "report | pitch | sales | conference | educational | internal_memo",
    "design_system": {
      "title_style": {
        "font_family": "Helvetica",
        "size_pt": 32,
        "weight": "regular | medium | bold",
        "color_hex": "#1A1A1A",
        "alignment": "left | center | right",
        "position": "top-left | top-center | top-right | center"
      },
      "body_style": {
        "font_family": "Helvetica",
        "size_pt": 14,
        "weight": "regular",
        "color_hex": "#333333",
        "alignment": "left",
        "line_height": 1.4
      },
      "color_palette": {
        "primary": "#1A1A1A",
        "accent": "#FF6B35",
        "neutrals": ["#FFFFFF", "#F5F5F5", "#E5E5E5"]
      },
      "grid": "12-column | 6-column | free",
      "default_text_alignment": "left",
      "recurring_elements": [
        {
          "type": "logo | page_number | footer | watermark",
          "position": "top-left | top-right | bottom-left | bottom-right",
          "appears_on_slides": [2, 3, 4, 5, 6, 7, 8]
        }
      ]
    },
    "consistency_score": 0.87,
    "extraction_metadata": {
      "extracted_at": "ISO-8601 timestamp",
      "pipeline_a_version": "0.1.0",
      "pipeline_b_version": "0.1.0",
      "vlm_used": "claude-sonnet-4-6"
    }
  },
  "slides": [
    {
      "index": 4,
      "thumbnail_path": "renders/deck_id/slide_004.png",
      "role": "title | section_divider | agenda | content | data | quote | image_led | comparison | timeline | summary | cta",
      "layout_archetype": "string identifier matching layout library",
      "core_message": "Enterprise revenue grew 40% YoY",
      "emphasis_techniques": [
        "hierarchy_by_size",
        "hierarchy_by_position",
        "hierarchy_by_color",
        "isolation_with_whitespace",
        "contrast",
        "repetition",
        "directional_cues"
      ],
      "density": {
        "word_count": 47,
        "text_blocks": 3,
        "visual_elements": 1,
        "whitespace_ratio_est": 0.65,
        "bucket": "sparse | balanced | dense | very_dense"
      },
      "deviations_from_system": [
        {
          "property": "title_position",
          "expected": "top-left",
          "actual": "center",
          "likely_intent": "section_divider"
        }
      ]
    }
  ]
}
```

Notes on the schema:
- `emphasis_techniques` is an enumerated list. The VLM picks from this set, not free-form.
- `layout_archetype` references a separate layout library (start small, maybe 15-20 archetypes, grow as you encounter new ones)
- `consistency_score` is computed: percentage of design properties where slides follow the modal value
- `deviations_from_system` flags intentional or unintentional breaks from the deck's own rules

## Pipeline A: Structural extraction

Deterministic extraction directly from the source file. No AI involved. Near-100% accuracy because you're reading the file's own data.

### Per-slide observations

For each slide, extract:
- Title text frame: position (normalized 0-1), font family, size, weight, color, alignment
- Body text frames: same properties, plus paragraph count and word count
- Shapes: type, position, dimensions, fill color
- Images: position, dimensions, perceptual hash (for matching across slides)
- Charts and tables: detect presence, extract data if accessible

### Deck-level aggregation

For each design property, compute the modal value across slides. If 75%+ of slides share a value (within tolerance), it becomes a deck-level standard. Tolerance bands:
- Font size: ±2pt
- Position: ±5% of slide dimension
- Color: exact match required (no fuzzy color matching at this stage)

### Logo and recurring element detection

Compute a perceptual hash (pHash) for every image. Group images by hash. If an image appears in the same approximate position (±5%) across 60%+ of slides, classify as a recurring element. Label by quadrant.

### Density metrics

For each slide:
- `word_count`: total words across all text frames
- `text_blocks`: count of distinct text frames
- `visual_elements`: count of images, charts, tables, non-decorative shapes
- `whitespace_ratio_est`: 1 minus (sum of content bounding box area / slide area)
- `bucket`: derived from word_count and visual_elements thresholds

### Library

- `python-pptx` for .pptx parsing
- `pdfplumber` for .pdf text and structure
- `Pillow` for image processing
- `imagehash` for perceptual hashing

## Pipeline B: Semantic extraction (VLM)

Renders each slide to a PNG and sends it to a vision language model with a constrained schema. The VLM fills in the fields Pipeline A cannot: core message, emphasis techniques, slide role, layout archetype.

### Rendering

- Use LibreOffice headless to convert .pptx to PDF, then `pdf2image` to render PDF pages to PNG at 200 DPI
- Standard resolution: 1920x1080 or native deck aspect ratio
- Store renders in `renders/{deck_id}/slide_{NNN}.png`

### VLM call structure

For each slide, send:
1. The rendered PNG
2. The Pipeline A structural data for that slide (word count, text blocks, etc.) so the VLM doesn't re-count or hallucinate
3. The constrained schema with enumerated options for every field
4. Brief definitions of each enum value (one sentence each)

The VLM is told to fill in the schema, not write prose. Use Anthropic's tool-use API or `response_format` with a Pydantic schema to enforce structured output.

### Prompt skeleton

```
You are analyzing a single slide from a presentation. The slide image is attached.

Structural data from deterministic extraction (use this, do not recompute):
- Word count: 47
- Text blocks: 3
- Visual elements: 1
- Density bucket: sparse

Fill in the following schema. Pick from enumerated options only. Do not invent new values.

[schema with enums and one-line definitions]

Return only valid JSON matching the schema.
```

### Model choice

For prototyping: Claude Sonnet 4.6 ($3/$15 per million tokens). Good balance of quality and cost. Use Anthropic's batch API for 50% discount when processing in bulk.

For high-stakes semantic fields where accuracy matters most: Claude Opus 4.7 ($5/$25). Higher vision resolution helps on dense slides.

For cost-sensitive scale or open-source preference: Qwen 2.5-VL 72B via Replicate or Together. Validate quality first against hand-labeled set.

Consider a two-tier router later: cheap model for easy fields (slide role, density bucket), premium model for hard fields (core message, emphasis techniques). Can cut costs 60-70%.

### Validation against Pipeline A

After the VLM returns its output, validate:
- Word count claimed by VLM matches Pipeline A within 10% (catches hallucinations)
- Slide role is consistent with structural cues (e.g., role=title should have ≤15 words and ≥40% whitespace)
- Layout archetype matches the actual element positions

Flag any record where validation fails. Manual review queue.

## Storage and retrieval

### Initial setup

- One JSON file per deck in `data/tagged/{deck_id}.json`
- Slide renders alongside in `data/renders/{deck_id}/`
- Original source files in `data/source/{deck_id}.{ext}`

### Retrieval layer (later)

For generation to use this corpus, you need fast retrieval. Build this as a separate module after the tagging pipeline is stable.

Options:
1. **Structured filters only**: SQLite or Postgres with the schema fields indexed. Good for "find me sparse data slides from report-style decks". Easy to build.
2. **Vector similarity**: embed slide thumbnails with CLIP, embed core_message text with a sentence transformer. Postgres + pgvector. Good for "find slides similar to this concept".
3. **Hybrid**: structured filters narrow the candidate set, vector similarity ranks within it. Standard RAG pattern.

Start with option 1. Add option 2 when you actually have a generator that needs it.

## Implementation phases

### Phase 1: Schema lock (week 1)
- Write Pydantic models for the full schema
- Build a JSON validator
- Hand-fill the schema for 5 reference decks of different types. This will surface gaps in the schema before you build anything.

### Phase 2: Pipeline A (week 2)
- python-pptx parser walking all slides and shapes
- Per-slide structural extraction
- Deck-level aggregation logic
- Outputs valid JSON matching the schema for the structural fields
- Test against the 5 hand-labeled decks: structural fields should match within tolerance

### Phase 3: Pipeline B (week 3)
- Rendering pipeline (LibreOffice + pdf2image)
- VLM client with constrained schema
- Prompt iteration against hand-labeled set
- Target: 85%+ match with hand-labels on semantic fields

### Phase 4: Validation and consistency (week 4)
- Cross-validate Pipeline B output against Pipeline A
- Compute consistency_score
- Detect and tag deviations_from_system

### Phase 5: Scale (week 5+)
- Batch API integration for cost
- Process 100-500 decks
- Manual spot-check sample, iterate prompts
- Build retrieval layer

## Suggested file structure

```
slide-tagger/
├── src/
│   ├── schema/
│   │   ├── models.py              # Pydantic models for the full schema
│   │   ├── enums.py               # Enum definitions for roles, archetypes, etc.
│   │   └── layout_library.py      # Layout archetype definitions
│   ├── extractors/
│   │   ├── structural/
│   │   │   ├── pptx_parser.py     # python-pptx based extraction
│   │   │   ├── pdf_parser.py      # pdfplumber based extraction
│   │   │   ├── aggregator.py      # per-slide → deck-level patterns
│   │   │   └── density.py         # density computation
│   │   └── semantic/
│   │       ├── renderer.py        # slide → PNG
│   │       ├── vlm_client.py      # Anthropic SDK wrapper
│   │       ├── prompts.py         # prompt templates
│   │       └── validator.py       # cross-validate against Pipeline A
│   ├── storage/
│   │   ├── filesystem.py          # JSON + render file management
│   │   └── retrieval.py           # query interface (Phase 5)
│   └── cli.py                     # entry point: tag a deck end-to-end
├── data/
│   ├── source/                    # original .pptx/.pdf files
│   ├── renders/                   # PNG renders per slide
│   └── tagged/                    # output JSON per deck
├── tests/
│   ├── fixtures/                  # 5 hand-labeled reference decks
│   ├── test_pipeline_a.py
│   └── test_pipeline_b.py
├── reference_data/
│   └── hand_labels/               # ground truth annotations
├── pyproject.toml
└── README.md
```

## Tech stack

- Python 3.11+
- python-pptx for .pptx parsing
- pdfplumber for .pdf parsing
- LibreOffice (headless) for .pptx → PDF conversion
- pdf2image for PDF → PNG rendering
- Pillow and imagehash for image processing
- Pydantic for schema validation
- Anthropic SDK for VLM calls
- pytest for testing
- JSON files for storage (Phase 1-4), Postgres + pgvector later

## Key design decisions and rationale

**Two separate pipelines, not one VLM pass**: Structural data is deterministic and free. Sending a slide to a VLM and asking "what font is the title in" is wasteful and less accurate than reading the file. VLMs should only do what they uniquely can: visual reasoning over composition and meaning.

**Constrained vocabulary throughout**: Free-form tags become noise at scale. Every enum should have a fixed set of values defined in `src/schema/enums.py`. When you discover a new pattern, add it to the enum deliberately, not by accident.

**Validate Pipeline B against Pipeline A**: VLMs hallucinate. Pipeline A gives you ground truth for the easy stuff. Use it to catch when the VLM is making things up.

**Deck-level aggregation matters more than per-slide tagging**: The most useful tags describe the *system* the deck follows, not individual slide instances. Generation downstream wants to apply the system to new content.

**Lock the schema first**: Changes to the schema invalidate every record extracted before the change. Pay the upfront cost of getting it right.

**Hand-label before automating**: Build the manual reference set first. It tells you what tags actually matter and what you thought mattered but doesn't. Skipping this step is the most common failure mode.

## Open questions to resolve early

1. **PDF support priority**: how much of the input corpus is .pdf vs .pptx? PDF extraction is significantly harder (no semantic structure, just rendered pages). Decide whether to defer PDF support to a later phase.
2. **Multi-language**: do decks need to be language-agnostic? Affects VLM prompt design and OCR fallback strategy.
3. **Animation and build sequences**: .pptx supports complex animations. Are these part of the design DNA worth tagging, or do they get flattened to the final state?
4. **Chart data extraction**: do we extract underlying chart data (numbers, labels) or just classify the chart type? Affects whether downstream generation can recreate equivalent charts.
5. **Brand identity attribution**: do we tag which brand each deck belongs to? Useful for "make me a deck in Stripe's style" but raises licensing questions if the corpus includes copyrighted material.

## Starting point for Claude Code

When picking this up, start in this order:

1. Read this whole doc
2. Set up the project skeleton matching the file structure above
3. Implement the Pydantic schema in `src/schema/models.py` first
4. Hand-label one reference deck by manually filling in the schema (you can use a sample .pptx as input)
5. Build Pipeline A to reproduce the structural fields of that hand-label
6. Only then move to Pipeline B

Do not skip the hand-labeling step.