"""Rasterize a PDF's pages to per-slide full + thumbnail PNGs (pdf2image + Pillow).

The render step's second stage. pdf2image shells out to poppler's `pdftoppm`;
Pillow downscales each full render to a thumbnail (aspect preserved).
"""

from __future__ import annotations

import os
from pathlib import Path

from pdf2image import convert_from_path

from slide_tagger.extractors.render.paths import render_rel_path, thumb_rel_path


def pdf_to_pngs(
    pdf: str | Path,
    out_root: str | Path,
    slug: str,
    dpi: int = 150,
    thumb_px: int = 512,
    only_index: int | None = None,
    poppler_path: str | None = None,
) -> list[tuple[int, str, str]]:
    """Render `pdf` pages under `out_root` as `<slug>/slide_NNN.png` (full) and
    `<slug>/thumb/slide_NNN.png` (thumbnail).

    Returns `(index, render_rel_path, thumbnail_rel_path)` per written slide.
    `poppler_path` (or the `POPPLER_PATH` env var) points pdf2image at poppler's
    `bin/` when it is not on PATH (common on Windows).
    """
    out_root = Path(out_root)
    poppler_path = poppler_path or os.environ.get("POPPLER_PATH")

    pages = convert_from_path(str(pdf), dpi=dpi, fmt="png", poppler_path=poppler_path)

    results: list[tuple[int, str, str]] = []
    for index, page in enumerate(pages):
        if only_index is not None and index != only_index:
            continue

        render_rel = render_rel_path(slug, index)
        thumb_rel = thumb_rel_path(slug, index)
        render_abs = out_root / render_rel
        thumb_abs = out_root / thumb_rel
        render_abs.parent.mkdir(parents=True, exist_ok=True)
        thumb_abs.parent.mkdir(parents=True, exist_ok=True)

        page.save(render_abs, "PNG")

        thumb = page.copy()
        thumb.thumbnail((thumb_px, thumb_px))  # in place; preserves aspect ratio
        thumb.save(thumb_abs, "PNG")

        results.append((index, render_rel, thumb_rel))

    return results
