"""Declarative registry of which enrichment fields to score and how.

The single source of truth for the scorer and the report. Each `FieldSpec` says
where a field lives (dotted path, plus whether it is deck/slide/element level) and
how to compare it (its `kind`). Paths and `legend_key`s mirror
`schema/tagged.py` (`DeckTag`/`SlideTag`) and `legend()`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# Levels: where the field lives.
DECK = "deck"  # path is relative to the deck dict
SLIDE = "slide"  # path is relative to each slide dict (scored per slide, paired by index)
ELEMENT = "element"  # path is dotted into the deck dict (inferred_rules / design_system)

# Kinds: how the field is compared.
ENUM = "enum"  # single enumerated value -> exact match
ENUM_LIST = "enum_list"  # list of enumerated values -> set precision/recall/F1
BOOL = "bool"  # boolean -> exact match
FREE_TEXT = "free_text"  # reported side-by-side, excluded from the headline metric
STRUCTURAL = "structural"  # Pipeline A owns it -> integrity check (must be unchanged)

SCORED_KINDS = {ENUM, ENUM_LIST, BOOL}  # the kinds that feed the headline accuracy


@dataclass(frozen=True)
class FieldSpec:
    path: str
    level: str
    kind: str
    legend_key: str | None = None  # key into legend() for enum-discipline checks

    @property
    def label(self) -> str:
        return self.path if self.level != ELEMENT else self.path


FIELDS: list[FieldSpec] = [
    # --- deck-level semantic ---
    FieldSpec("client_industry", DECK, ENUM, "client_industry"),
    FieldSpec("client_type", DECK, ENUM, "client_type"),
    FieldSpec("engagement_stage", DECK, ENUM, "engagement_stage"),
    FieldSpec("audience_level", DECK, ENUM, "audience_level"),
    FieldSpec("deliverable_format", DECK, ENUM, "deliverable_format"),
    FieldSpec("geography", DECK, ENUM, "geography"),
    FieldSpec("confidentiality_tier", DECK, ENUM, "confidentiality_tier"),
    FieldSpec("content_area", DECK, ENUM_LIST, "content_area"),
    FieldSpec("client_sub_industry", DECK, FREE_TEXT),
    FieldSpec("inferred_publisher", DECK, FREE_TEXT),
    FieldSpec("deck_summary_one_sentence", DECK, FREE_TEXT),
    # --- slide-level semantic (scored per slide) ---
    FieldSpec("slide_purpose", SLIDE, ENUM, "slide_purpose"),
    FieldSpec("message_type", SLIDE, ENUM, "message_type"),
    FieldSpec("audience_level_slide", SLIDE, ENUM, "audience_level_slide"),
    FieldSpec("slide_position_role", SLIDE, ENUM, "slide_position_role"),
    FieldSpec("dominant_visual_element", SLIDE, ENUM, "dominant_visual_element"),
    FieldSpec("chart_type", SLIDE, ENUM, "chart_type"),
    FieldSpec("placeholder_compliance", SLIDE, ENUM, "placeholder_compliance"),
    FieldSpec("reusability_score_qualitative", SLIDE, ENUM, "reusability_score_qualitative"),
    FieldSpec("tier_match_difficulty", SLIDE, ENUM, "tier_match_difficulty"),
    FieldSpec("slot_types_present", SLIDE, ENUM_LIST, "slot_types_present"),
    FieldSpec("embedded_data_present", SLIDE, BOOL),
    FieldSpec("main_message", SLIDE, FREE_TEXT),
    # --- element-level inferred rules + design-system hand-labels ---
    FieldSpec(
        "inferred_rules.title.uses_action_titles",
        ELEMENT,
        ENUM,
        "inferred_rules.title.uses_action_titles",
    ),
    FieldSpec(
        "inferred_rules.chart_styling.uses_consistent_palette",
        ELEMENT,
        ENUM,
        "inferred_rules.chart_styling.uses_consistent_palette",
    ),
    FieldSpec(
        "inferred_rules.layout_conventions.uses_master_template",
        ELEMENT,
        ENUM,
        "inferred_rules.layout_conventions.uses_master_template",
    ),
    FieldSpec("design_system.grid", ELEMENT, ENUM, "design_system.grid"),
    # --- structural (Pipeline A owns; must be unchanged) ---
    FieldSpec("deck_length", DECK, STRUCTURAL),
    FieldSpec("design_system.title_style", DECK, STRUCTURAL),
    FieldSpec("design_system.body_style", DECK, STRUCTURAL),
    FieldSpec("design_system.color_palette", DECK, STRUCTURAL),
    FieldSpec("design_system.default_text_alignment", DECK, STRUCTURAL),
    FieldSpec("title_text", SLIDE, STRUCTURAL),
    FieldSpec("title_position", SLIDE, STRUCTURAL),
    FieldSpec("image_count", SLIDE, STRUCTURAL),
    FieldSpec("has_chart", SLIDE, STRUCTURAL),
    FieldSpec("has_table", SLIDE, STRUCTURAL),
    FieldSpec("density", SLIDE, STRUCTURAL),
]


def get_by_path(obj: dict[str, Any] | None, path: str) -> Any:
    """Walk a dotted path through nested dicts, returning None if any hop is absent."""
    cur: Any = obj
    for part in path.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur
