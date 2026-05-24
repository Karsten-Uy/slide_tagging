# Design: deterministic slide-render step for `slide_tagging`

**Date:** 2026-05-23
**Status:** approved
**Scope:** Add a deterministic `.pptx` → PNG render step to `slide_tagging`, and link
the rendered images back to the tagged JSON so the `mcp-slide-corpus` server can
resolve them.

## Goal & pipeline placement

A new deterministic render step, a sibling of Pipeline A (not part of it —
Pipeline A reads the file's XML; this rasterizes pixels). It converts a `.pptx`
into per-slide PNGs that two downstream consumers reuse:

- **Pipeline B** (VLM enrichment) — needs the rendered image as model input.
- **`mcp-slide-corpus`** — CLIP visual embeddings + visual examples returned to
  the generating agent.

Render once, two consumers.

## Rendering mechanics

`.pptx` → **LibreOffice headless** (`soffice --headless --convert-to pdf`) →
**pdf2image / poppler** (PDF pages → PNG at a configurable DPI) → **Pillow**
downscales each full render to a thumbnail.

Two outputs per slide:

```
data/renders/<deck-slug>/slide_000.png         # full, native aspect, ~150 DPI
data/renders/<deck-slug>/thumb/slide_000.png   # thumbnail, ~512px long edge
```

- `<deck-slug>` = slugified source-filename stem
  (e.g. `pwc-global-top-100-companies-2023`).
- Slide number is **0-based, zero-padded to 3 digits**, matching the schema's
  `index` so a path maps 1:1 to its slide record.

### Engine & licensing decisions

- **LibreOffice** (not Aspose.Slides): Aspose's eval mode watermarks every render
  and a license is ~$1,200+/yr. LibreOffice is free and cross-platform.
- **pdf2image + poppler** (not PyMuPDF): pdf2image is MIT; poppler is invoked as a
  separate binary (no linking), which is clean for a commercial product. PyMuPDF
  is AGPL-3.0 / commercial-dual — the same licensing risk that ruled out Aspose.

## Module structure (small, testable units)

```
src/slide_tagger/extractors/render/
  __init__.py      # render_deck(pptx, out_root, dpi, thumb_px, only_index) -> DeckRender
  paths.py         # deck_slug(); render_rel_path(slug, i); thumb_rel_path(slug, i)  — pure
  soffice.py       # find_soffice(); pptx_to_pdf(pptx, out_dir) -> Path
  rasterize.py     # pdf_to_pngs(pdf, out_root, slug, dpi, thumb_px, only_index) -> list[SlideRender]
```

`paths.py` is the **single source of the naming convention**, imported by both the
render step (to decide where to write) and the schema-population step (to record
where renders live), so the two can never drift.

`render_deck` returns a small result model:

```python
class SlideRender(BaseModel):
    index: int
    render_path: str       # relative to out_root, e.g. "<slug>/slide_000.png"
    thumbnail_path: str    # relative to out_root, e.g. "<slug>/thumb/slide_000.png"

class DeckRender(BaseModel):
    deck_slug: str
    out_root: str
    slides: list[SlideRender]
```

## CLI surface

Consistent with the existing `tag` / `deck-summary` / `template` / `validate`
subcommands:

```
slide-tagger render <deck.pptx> [--out data/renders] [--dpi 150] [--thumb 512] [--slide N]
```

- Renders all slides, or one with `--slide` (0-based, matching `tag --slide`).
- Prints a summary of files written.
- Reuses the existing `.pptx`-only validation and exit-code conventions
  (`_resolve_deck`): exit 2 for unsupported/missing input.

## Schema ↔ JSON link

Add two optional fields to **`SlideTag`** (in `schema/tagged.py`), *not*
`SlideStructural` — these are render artifacts, not file-structure facts:

```python
render_path: str | None = None       # "<slug>/slide_000.png"      (relative to render root)
thumbnail_path: str | None = None    # "<slug>/thumb/slide_000.png"
```

`blank_tag()` (and therefore the `template` command) populates them via `paths.py`,
deterministically from the deck slug + each slide's `index`. The paths are filled
whether or not the PNGs exist yet — they describe where renders live. No in-place
JSON rewriting.

The `mcp-slide-corpus` server resolves them with `THUMBNAIL_BASE_PATH +
thumbnail_path`, exactly as its config already expects.

## Configuration

- **LibreOffice discovery:** `find_soffice()` checks, in order: `LIBREOFFICE_PATH`
  env var, `soffice`/`libreoffice` on PATH, then the platform default
  (`C:\Program Files\LibreOffice\program\soffice.exe` on Windows).
- **poppler:** pdf2image finds `pdftoppm` on PATH; an optional `--poppler-path`
  flag (and `POPPLER_PATH` env var) is forwarded to pdf2image for Windows installs
  that aren't on PATH.

## Error handling

- **LibreOffice missing:** `find_soffice()` raises a clear, actionable error;
  the CLI maps it to exit 2 with an install hint.
- **poppler missing:** catch pdf2image's failure; message points to install
  poppler or pass `--poppler-path`.
- **Page/slide mismatch:** warn (stderr) if the rendered page count differs from
  the deck's `slide_count`; still write what was produced.
- **soffice subprocess:** bounded timeout; a non-zero exit surfaces captured
  stderr.

## Testing

- **`paths.py`** — pure unit tests: slug normalization (spaces, case, punctuation),
  zero-padding, thumb subdir.
- **schema** — `blank_tag` populates `render_path` / `thumbnail_path` for the
  sample deck; values match `paths.py`.
- **`soffice.py`** — `find_soffice()` discovery order via monkeypatched env/PATH;
  command construction. Actual conversion is integration-only.
- **`rasterize.py`** — tiny fixture PDF → N full PNGs + N thumbs; thumb long edge
  ≤ `thumb_px`. `skipif` poppler absent.
- **end-to-end** — render the `make_sample_deck.py` deck; assert 4 fulls + 4
  thumbs. `skipif` LibreOffice or poppler absent, so CI without them still passes.

## Dependencies & docs

- **pip (`pyproject.toml`):** add `pdf2image` and `pillow` (Pillow is already
  present transitively via `imagehash`; declaring it is honest since we use it
  directly).
- **system (runtime):** LibreOffice + poppler — documented in the README; update
  the "deferred → implemented" note for rendering.

## Scope guardrails (YAGNI)

Out of scope: PDF *input* support (still `.pptx`-only), animation/build-state
handling, cloud rendering, and re-render caching / incremental skip. Just
deterministic `.pptx` → PNGs plus the schema link.
