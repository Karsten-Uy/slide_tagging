"""Pydantic models for Pipeline A's deterministic structural output.

These cover the structural subset of init.md's per-slide schema — the fields a
VLM should never guess. Semantic fields (role, layout_archetype, core_message,
emphasis_techniques) are added later by Pipeline B and merged in.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from slide_tagger.schema.enums import DensityBucket, Position, SourceFormat


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


class DeckStructural(BaseModel):
    """Deterministic deck-level structural data (Pipeline A output)."""

    source_filename: str
    source_format: SourceFormat
    slide_count: int
    slides: list[SlideStructural] = Field(default_factory=list)


class DeckSummary(BaseModel):
    """A deterministic, whole-deck overview that grounds the deck-level VLM pass.

    Aggregated from per-slide structural data — not a VLM output. Gives the
    deck-level classifier (deck_type, style, narrative, visual mode) a factual
    picture of the deck without re-deriving structure from the contact sheet.
    """

    source_filename: str
    slide_count: int
    density_distribution: dict[DensityBucket, int]
    slides_with_charts: int
    slides_with_tables: int
    slides_with_images: int
    dominant_title_position: Position | None = None
    avg_word_count: float
