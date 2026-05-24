"""Deterministic .pptx -> per-slide PNG render step.

A sibling of Pipeline A (structural extraction): both are deterministic, but
Pipeline A reads the file's XML while this rasterizes pixels. The PNGs feed two
consumers: Pipeline B (VLM input) and `mcp-slide-corpus` (CLIP embeddings +
visual examples).

Pipeline: `.pptx` --LibreOffice--> PDF --pdf2image/poppler--> full PNG
--Pillow--> thumbnail.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from pydantic import BaseModel

from slide_tagger.extractors.render.paths import deck_slug
from slide_tagger.extractors.render.rasterize import pdf_to_pngs
from slide_tagger.extractors.render.soffice import pptx_to_pdf


class SlideRender(BaseModel):
    """Where one slide's images were written (paths relative to the render root)."""

    index: int
    render_path: str
    thumbnail_path: str


class DeckRender(BaseModel):
    """Result of rendering a deck."""

    deck_slug: str
    out_root: str
    slides: list[SlideRender]


def render_deck(
    pptx: str | Path,
    out_root: str | Path = "data/renders",
    dpi: int = 150,
    thumb_px: int = 512,
    only_index: int | None = None,
    soffice: str | None = None,
    poppler_path: str | None = None,
) -> DeckRender:
    """Render every slide of `pptx` (or just `only_index`) to full + thumbnail PNGs
    under `out_root/<deck-slug>/`. The intermediate PDF is discarded.
    """
    pptx = Path(pptx)
    out_root = Path(out_root)
    slug = deck_slug(pptx.name)

    with tempfile.TemporaryDirectory(prefix="slide_render_") as tmp:
        pdf = pptx_to_pdf(pptx, Path(tmp), soffice=soffice)
        rendered = pdf_to_pngs(
            pdf,
            out_root,
            slug,
            dpi=dpi,
            thumb_px=thumb_px,
            only_index=only_index,
            poppler_path=poppler_path,
        )

    slides = [
        SlideRender(index=i, render_path=r, thumbnail_path=t) for (i, r, t) in rendered
    ]
    return DeckRender(deck_slug=slug, out_root=str(out_root), slides=slides)
