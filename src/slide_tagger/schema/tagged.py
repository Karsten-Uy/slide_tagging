"""The full tagged-record schema — structural (Pipeline A) + semantic enrichment
(Pipeline B / VLM or hand-labeled). This is the schema you fill in when manually
tagging reference decks (init.md Phase 1) and the shape the enrichment prompt
(docs/deck_tagging_prompt.md) writes back.

Enrichment fields are Optional: they're `null`/empty until filled, so a freshly
generated template validates, and `validate` can report what's still untagged.
The three enrichment levels are: deck-level (on DeckTag), slide-level (on
SlideTag), and element-level (the `inferred_rules` block). A `provenance` block
records what was filled in by the tagger.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from slide_tagger.schema.enums import (
    AudienceLevel,
    AudienceLevelSlide,
    ChartPaletteConsistency,
    ChartType,
    ClientIndustry,
    ClientType,
    ConfidentialityTier,
    ContentArea,
    DeliverableFormat,
    DominantVisualElement,
    EngagementStage,
    Geography,
    Grid,
    MasterTemplateUsage,
    MessageType,
    PlaceholderCompliance,
    Position,
    RecurringElementType,
    ReusabilityScore,
    SlidePositionRole,
    SlidePurpose,
    SlotType,
    SourceFormat,
    TextAlignment,
    TierMatchDifficulty,
    UsesActionTitles,
)
from slide_tagger.schema.models import DeckStructural, DesignSystem, SlideStructural


class Zone(BaseModel):
    """A named region of a slide (e.g. title, main-content, callout, footer)."""

    name: str
    region: str


class SlideTag(SlideStructural):
    """A slide's structural fields plus the semantic fields to enrich/hand-label."""

    slide_purpose: SlidePurpose | None = None
    message_type: MessageType | None = None
    audience_level_slide: AudienceLevelSlide | None = None
    slide_position_role: SlidePositionRole | None = None
    main_message: str | None = None
    dominant_visual_element: DominantVisualElement | None = None
    chart_type: ChartType | None = None
    placeholder_compliance: PlaceholderCompliance | None = None
    embedded_data_present: bool | None = None
    zones: list[Zone] = Field(default_factory=list)
    slot_types_present: list[SlotType] = Field(default_factory=list)
    reusability_score_qualitative: ReusabilityScore | None = None
    tier_match_difficulty: TierMatchDifficulty | None = None
    # Render artifacts (filled by the `template` command / render step; paths are
    # relative to the render root, resolved downstream via THUMBNAIL_BASE_PATH).
    render_path: str | None = None
    thumbnail_path: str | None = None


# --- Element-level inferred style rules. Aggregated observations across the
# --- whole deck; flagged scope="inferred" (not authoritative) for human
# --- curation against the firm's brand guide.


class InferredTitleRule(BaseModel):
    font_family_observed: list[str] = Field(default_factory=list)
    size_pt_range: list[float] | None = None  # [min, max]
    size_pt_most_common: float | None = None
    weight_observed: list[str] = Field(default_factory=list)
    color_hex_observed: list[str] = Field(default_factory=list)
    position_most_common: Position | None = None
    alignment_most_common: TextAlignment | None = None
    uses_action_titles: UsesActionTitles | None = None
    max_chars_observed: int | None = None
    scope_tag: str = "inferred"


class InferredBodyTextRule(BaseModel):
    font_family_observed: list[str] = Field(default_factory=list)
    size_pt_range: list[float] | None = None  # [min, max]
    size_pt_most_common: float | None = None
    color_hex_observed: list[str] = Field(default_factory=list)
    alignment_most_common: TextAlignment | None = None
    scope_tag: str = "inferred"


class InferredColorPaletteRule(BaseModel):
    primary_observed: str | None = None
    accent_observed: str | None = None
    neutrals_observed: list[str] = Field(default_factory=list)
    notes: str | None = None
    scope_tag: str = "inferred"


class InferredChartStylingRule(BaseModel):
    uses_consistent_palette: ChartPaletteConsistency | None = None
    notes: str | None = None
    scope_tag: str = "inferred"


class InferredLayoutConventionsRule(BaseModel):
    uses_master_template: MasterTemplateUsage | None = None
    no_fly_zones_observed: str | None = None
    scope_tag: str = "inferred"


class InferredRules(BaseModel):
    """Element-level style rules extracted from observed practice across the deck."""

    title: InferredTitleRule = Field(default_factory=InferredTitleRule)
    body_text: InferredBodyTextRule = Field(default_factory=InferredBodyTextRule)
    color_palette: InferredColorPaletteRule = Field(default_factory=InferredColorPaletteRule)
    chart_styling: InferredChartStylingRule = Field(default_factory=InferredChartStylingRule)
    layout_conventions: InferredLayoutConventionsRule = Field(
        default_factory=InferredLayoutConventionsRule
    )


class Provenance(BaseModel):
    """Records what was filled in by the tagger vs. extracted by the script."""

    tagged_by: str | None = None
    input_json_source: str = "automated structural extraction"
    fields_filled_by_ai: list[str] = Field(default_factory=list)
    confidence_notes: str | None = None


class DeckTag(BaseModel):
    """A fully tagged deck: deck-level enrichment + per-slide tagged records +
    element-level inferred rules + provenance."""

    source_filename: str
    source_format: SourceFormat
    slide_count: int
    # deck-level enrichment (VLM / hand-label)
    client_industry: ClientIndustry | None = None
    client_sub_industry: str | None = None
    client_type: ClientType | None = None
    engagement_stage: EngagementStage | None = None
    content_area: list[ContentArea] = Field(default_factory=list)
    audience_level: AudienceLevel | None = None
    deliverable_format: DeliverableFormat | None = None
    geography: Geography | None = None
    deck_length: int | None = None  # matches slide_count
    confidentiality_tier: ConfidentialityTier | None = None
    inferred_publisher: str | None = None
    deck_summary_one_sentence: str | None = None
    # deck design DNA: auto-filled by Pipeline A; `grid` and each recurring
    # element's `type` are left for hand-labeling.
    design_system: DesignSystem | None = None
    # element-level inferred style rules (VLM / hand-label)
    inferred_rules: InferredRules | None = None
    slides: list[SlideTag] = Field(default_factory=list)
    # provenance for the enrichment pass
    provenance: Provenance | None = None


def blank_tag(deck: DeckStructural) -> DeckTag:
    """Build a DeckTag from Pipeline A's structural output, enrichment unset.

    `deck_length` mirrors the deterministic slide_count; `inferred_rules` and
    `provenance` are scaffolded (empty) so the template shows their shape.
    """
    return DeckTag(
        source_filename=deck.source_filename,
        source_format=deck.source_format,
        slide_count=deck.slide_count,
        deck_length=deck.slide_count,
        design_system=deck.design_system,
        inferred_rules=InferredRules(),
        provenance=Provenance(),
        slides=[SlideTag(**s.model_dump()) for s in deck.slides],
    )


def legend() -> dict[str, list[str]]:
    """Allowed values for every enumerated enrichment field, for the template header."""
    return {
        # deck-level enrichment
        "client_industry": [e.value for e in ClientIndustry],
        "client_type": [e.value for e in ClientType],
        "engagement_stage": [e.value for e in EngagementStage],
        "content_area": [e.value for e in ContentArea],
        "audience_level": [e.value for e in AudienceLevel],
        "deliverable_format": [e.value for e in DeliverableFormat],
        "geography": [e.value for e in Geography],
        "confidentiality_tier": [e.value for e in ConfidentialityTier],
        # slide-level enrichment
        "slide_purpose": [e.value for e in SlidePurpose],
        "message_type": [e.value for e in MessageType],
        "audience_level_slide": [e.value for e in AudienceLevelSlide],
        "slide_position_role": [e.value for e in SlidePositionRole],
        "dominant_visual_element": [e.value for e in DominantVisualElement],
        "chart_type": [e.value for e in ChartType],
        "placeholder_compliance": [e.value for e in PlaceholderCompliance],
        "slot_types_present": [e.value for e in SlotType],
        "reusability_score_qualitative": [e.value for e in ReusabilityScore],
        "tier_match_difficulty": [e.value for e in TierMatchDifficulty],
        # element-level inferred rules
        "inferred_rules.title.uses_action_titles": [e.value for e in UsesActionTitles],
        "inferred_rules.chart_styling.uses_consistent_palette": [
            e.value for e in ChartPaletteConsistency
        ],
        "inferred_rules.layout_conventions.uses_master_template": [
            e.value for e in MasterTemplateUsage
        ],
        # design-system hand-label fields (Pipeline A, preserved)
        "design_system.grid": [e.value for e in Grid],
        "design_system.recurring_elements[].type": [e.value for e in RecurringElementType],
    }
