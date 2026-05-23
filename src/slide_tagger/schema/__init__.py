"""Schema: the constrained vocabulary (enums) and Pydantic models for the
tagged-slide contract. Structural fields are produced by Pipeline A; the
semantic enums (role, emphasis, layout) belong to Pipeline B (the VLM) and live
here so the whole vocabulary is defined in one place (init.md decision)."""

from slide_tagger.schema.enums import (
    DeckType,
    DensityBucket,
    DominantVisualMode,
    EmphasisTechnique,
    LayoutArchetype,
    NarrativeStructure,
    Position,
    SlideRole,
    SourceFormat,
    StyleArchetype,
)
from slide_tagger.schema.models import (
    DeckStructural,
    DeckSummary,
    Density,
    SlideStructural,
)

__all__ = [
    "DeckType",
    "DensityBucket",
    "DominantVisualMode",
    "EmphasisTechnique",
    "LayoutArchetype",
    "NarrativeStructure",
    "Position",
    "SlideRole",
    "SourceFormat",
    "StyleArchetype",
    "DeckStructural",
    "DeckSummary",
    "Density",
    "SlideStructural",
]
