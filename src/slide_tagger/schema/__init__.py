"""Schema: the constrained vocabulary (enums) and Pydantic models for the
tagged-slide contract. Structural fields are produced by Pipeline A; the
semantic enums (role, emphasis, layout) belong to Pipeline B (the VLM) and live
here so the whole vocabulary is defined in one place (init.md decision)."""

from slide_tagger.schema.enums import (
    DeckType,
    DensityBucket,
    DominantVisualMode,
    EmphasisTechnique,
    FontWeight,
    Grid,
    LayoutArchetype,
    NarrativeStructure,
    Position,
    RecurringElementType,
    SlideRole,
    SourceFormat,
    StyleArchetype,
    TextAlignment,
)
from slide_tagger.schema.models import (
    ColorPalette,
    DeckStructural,
    DeckSummary,
    Density,
    DesignSystem,
    RecurringElement,
    SlideStructural,
    TextStyle,
)
from slide_tagger.schema.tagged import (
    DeckTag,
    SlideTag,
    blank_tag,
    legend,
)

__all__ = [
    "DeckType",
    "DensityBucket",
    "DominantVisualMode",
    "EmphasisTechnique",
    "FontWeight",
    "Grid",
    "LayoutArchetype",
    "NarrativeStructure",
    "Position",
    "RecurringElementType",
    "SlideRole",
    "SourceFormat",
    "StyleArchetype",
    "TextAlignment",
    "ColorPalette",
    "DeckStructural",
    "DeckSummary",
    "Density",
    "DesignSystem",
    "RecurringElement",
    "SlideStructural",
    "TextStyle",
    "DeckTag",
    "SlideTag",
    "blank_tag",
    "legend",
]
