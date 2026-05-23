"""The full tagged-record schema — structural (Pipeline A) + semantic (Pipeline B
or hand-labeled). This is the schema you fill in when manually tagging reference
decks (init.md Phase 1).

Semantic fields are Optional: they're `null`/empty until filled, so a freshly
generated template validates, and `validate` can report what's still untagged.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from slide_tagger.schema.enums import (
    DeckType,
    DominantVisualMode,
    EmphasisTechnique,
    Grid,
    LayoutArchetype,
    NarrativeStructure,
    RecurringElementType,
    SlideRole,
    SourceFormat,
    StyleArchetype,
)
from slide_tagger.schema.models import DeckStructural, DesignSystem, SlideStructural


class SlideTag(SlideStructural):
    """A slide's structural fields plus the semantic fields to hand-label."""

    role: SlideRole | None = None
    layout_archetype: LayoutArchetype | None = None
    core_message: str | None = None
    emphasis_techniques: list[EmphasisTechnique] = Field(default_factory=list)


class DeckTag(BaseModel):
    """A fully tagged deck: deck-level semantics + per-slide tagged records."""

    source_filename: str
    source_format: SourceFormat
    slide_count: int
    # deck-level semantic fields (hand-label / deck-level VLM pass)
    deck_type: DeckType | None = None
    style_archetype: StyleArchetype | None = None
    narrative_structure: NarrativeStructure | None = None
    dominant_visual_mode: DominantVisualMode | None = None
    # deck design DNA: auto-filled by Pipeline A; `grid` and each recurring
    # element's `type` are left for hand-labeling.
    design_system: DesignSystem | None = None
    slides: list[SlideTag] = Field(default_factory=list)


def blank_tag(deck: DeckStructural) -> DeckTag:
    """Build a DeckTag from Pipeline A's structural output, semantics unset."""
    return DeckTag(
        source_filename=deck.source_filename,
        source_format=deck.source_format,
        slide_count=deck.slide_count,
        design_system=deck.design_system,
        slides=[SlideTag(**s.model_dump()) for s in deck.slides],
    )


def legend() -> dict[str, list[str]]:
    """Allowed values for every hand-labeled field, for the template header."""
    return {
        "deck_type": [e.value for e in DeckType],
        "style_archetype": [e.value for e in StyleArchetype],
        "narrative_structure": [e.value for e in NarrativeStructure],
        "dominant_visual_mode": [e.value for e in DominantVisualMode],
        "role": [e.value for e in SlideRole],
        "layout_archetype": [e.value for e in LayoutArchetype],
        "emphasis_techniques": [e.value for e in EmphasisTechnique],
        "design_system.grid": [e.value for e in Grid],
        "design_system.recurring_elements[].type": [e.value for e in RecurringElementType],
    }
