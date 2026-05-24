"""Render output path convention.

Pure and deterministic — the single source of the naming rule, shared by the
render step (to decide where to write PNGs) and the schema-population step (to
record where renders live in the tagged JSON), so the two can never drift.

Paths are returned with forward slashes and relative to the render root, matching
how `mcp-slide-corpus` resolves them (`THUMBNAIL_BASE_PATH + thumbnail_path`).
"""

from __future__ import annotations

import re
from pathlib import Path


def deck_slug(source_filename: str) -> str:
    """Slugify a deck's source-filename stem: lowercase, runs of non-alphanumerics
    collapse to single hyphens, with no leading/trailing hyphen.

    `"PwC Global Top 100 (2023).pptx"` -> `"pwc-global-top-100-2023"`.
    Falls back to `"deck"` if nothing survives.
    """
    stem = Path(source_filename).stem
    slug = re.sub(r"[^a-z0-9]+", "-", stem.lower()).strip("-")
    return slug or "deck"


def _slide_name(index: int) -> str:
    """`slide_NNN.png`, 0-based and zero-padded to 3 digits to match `SlideTag.index`."""
    return f"slide_{index:03d}.png"


def render_rel_path(slug: str, index: int) -> str:
    """Relative path of a slide's full-resolution render."""
    return f"{slug}/{_slide_name(index)}"


def thumb_rel_path(slug: str, index: int) -> str:
    """Relative path of a slide's thumbnail."""
    return f"{slug}/thumb/{_slide_name(index)}"
