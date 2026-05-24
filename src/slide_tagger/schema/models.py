"""Pydantic models for Pipeline A's deterministic structural output.

These cover the structural subset of the per-slide schema — the fields a VLM
should never guess. The semantic enrichment fields (deck-, slide-, and
element-level; see schema/tagged.py) are added later by Pipeline B and merged in.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from slide_tagger.schema.enums import (
    DensityBucket,
    FontWeight,
    Grid,
    Position,
    RecurringElementType,
    SourceFormat,
    TextAlignment,
)


class Density(BaseModel):
    """How much a slide asks the viewer to process. All values deterministic."""

    word_count: int
    text_blocks: int
    visual_elements: int
    whitespace_ratio_est: float
    bucket: DensityBucket


class SlideStructural(BaseModel):
    """Deterministic per-slide structural data (Pipeline A output)."""

    index: int
    title_text: str | None = None
    title_position: Position | None = None
    image_count: int = 0
    has_chart: bool = False
    has_table: bool = False
    density: Density


class TextStyle(BaseModel):
    """Modal text styling for a role (title or body). All best-effort; any field
    may be None when the source doesn't declare it."""

    font_family: str | None = None
    size_pt: float | None = None
    weight: FontWeight | None = None
    color_hex: str | None = None
    alignment: TextAlignment | None = None


class ColorPalette(BaseModel):
    primary: str | None = None
    accent: str | None = None
    neutrals: list[str] = Field(default_factory=list)


class RecurringElement(BaseModel):
    """An image that repeats across the deck (logo/footer/watermark/…).

    `phash`, `position`, and `appears_on_slides` are deterministic (Pipeline A);
    `type` is hand-labeled — pHash finds the element, a human says what it is."""

    phash: str
    position: Position | None = None
    appears_on_slides: list[int] = Field(default_factory=list)
    type: RecurringElementType | None = None


class DesignSystem(BaseModel):
    """Deck-level design DNA, aggregated deterministically from the source file.

    `grid` and each recurring element's `type` are left for hand-labeling — they
    aren't reliably derivable from the file."""

    title_style: TextStyle = Field(default_factory=TextStyle)
    body_style: TextStyle = Field(default_factory=TextStyle)
    color_palette: ColorPalette = Field(default_factory=ColorPalette)
    default_text_alignment: TextAlignment | None = None
    grid: Grid | None = None
    recurring_elements: list[RecurringElement] = Field(default_factory=list)


class DeckStructural(BaseModel):
    """Deterministic deck-level structural data (Pipeline A output)."""

    source_filename: str
    source_format: SourceFormat
    slide_count: int
    design_system: DesignSystem | None = None
    slides: list[SlideStructural] = Field(default_factory=list)


class DeckSummary(BaseModel):
    """A deterministic, whole-deck overview that grounds the enrichment pass.

    Aggregated from per-slide structural data — not a VLM output. Gives the
    deck-level enrichment (client_industry, audience_level, …) a factual picture
    of the deck without re-deriving structure from the contact sheet.
    """

    source_filename: str
    slide_count: int
    density_distribution: dict[DensityBucket, int]
    slides_with_charts: int
    slides_with_tables: int
    slides_with_images: int
    dominant_title_position: Position | None = None
    avg_word_count: float
