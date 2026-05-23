"""Constrained vocabulary for the slide-tagging schema.

Every enumerated field draws from one of these sets. Add new values
deliberately, never ad hoc (init.md: "constrained vocabulary throughout").
"""

from __future__ import annotations

from enum import Enum


class SourceFormat(str, Enum):
    PPTX = "pptx"
    PDF = "pdf"


class DensityBucket(str, Enum):
    SPARSE = "sparse"
    BALANCED = "balanced"
    DENSE = "dense"
    VERY_DENSE = "very_dense"


class Position(str, Enum):
    """Coarse 3x3 quadrant of a shape's center on the slide."""

    TOP_LEFT = "top-left"
    TOP_CENTER = "top-center"
    TOP_RIGHT = "top-right"
    MIDDLE_LEFT = "middle-left"
    CENTER = "center"
    MIDDLE_RIGHT = "middle-right"
    BOTTOM_LEFT = "bottom-left"
    BOTTOM_CENTER = "bottom-center"
    BOTTOM_RIGHT = "bottom-right"


# --- Semantic vocabulary (Pipeline B / the VLM produces these). Defined here so
# --- the schema's full constrained vocabulary lives in one place. Pipeline A
# --- does not assign these.


class SlideRole(str, Enum):
    TITLE = "title"
    SECTION_DIVIDER = "section_divider"
    AGENDA = "agenda"
    CONTENT = "content"
    DATA = "data"
    QUOTE = "quote"
    IMAGE_LED = "image_led"
    COMPARISON = "comparison"
    TIMELINE = "timeline"
    SUMMARY = "summary"
    CTA = "cta"


class EmphasisTechnique(str, Enum):
    HIERARCHY_BY_SIZE = "hierarchy_by_size"
    HIERARCHY_BY_POSITION = "hierarchy_by_position"
    HIERARCHY_BY_COLOR = "hierarchy_by_color"
    ISOLATION_WITH_WHITESPACE = "isolation_with_whitespace"
    CONTRAST = "contrast"
    REPETITION = "repetition"
    DIRECTIONAL_CUES = "directional_cues"


class LayoutArchetype(str, Enum):
    """Starter layout library (17 archetypes), mirroring the set defined in
    architecture/vlm_prompt_test.md. Grow deliberately as new patterns appear."""

    TITLE_CENTERED = "title_centered"
    TITLE_LEFT = "title_left"
    SECTION_DIVIDER = "section_divider"
    SINGLE_STATEMENT = "single_statement"
    STAT_HERO = "stat_hero"
    TWO_COLUMN = "two_column"
    THREE_COLUMN = "three_column"
    BULLETED_LIST = "bulleted_list"
    IMAGE_TEXT_SPLIT = "image_text_split"
    FULL_BLEED_IMAGE = "full_bleed_image"
    IMAGE_GRID = "image_grid"
    CHART_FOCUS = "chart_focus"
    TABLE = "table"
    QUOTE = "quote"
    COMPARISON = "comparison"
    TIMELINE = "timeline"
    PROCESS_DIAGRAM = "process_diagram"


# --- Deck-level semantic vocabulary (Pipeline B, deck-level pass). These need a
# --- whole-deck view (contact sheet), so a single slide can't yield them.


class DeckType(str, Enum):
    REPORT = "report"
    PITCH = "pitch"
    SALES = "sales"
    CONFERENCE = "conference"
    EDUCATIONAL = "educational"
    INTERNAL_MEMO = "internal_memo"
    ONE_PAGER = "one_pager"


class StyleArchetype(str, Enum):
    EDITORIAL = "editorial"
    CORPORATE = "corporate"
    MINIMALIST = "minimalist"
    DATA_HEAVY = "data_heavy"
    PLAYFUL = "playful"
    TECHNICAL = "technical"
    LUXURY = "luxury"


class NarrativeStructure(str, Enum):
    PROBLEM_SOLUTION_CTA = "problem_solution_cta"
    DATA_LED_CONCLUSION = "data_led_conclusion"
    CHRONOLOGICAL = "chronological"
    COMPARISON = "comparison"
    TUTORIAL = "tutorial"
    NARRATIVE_ARC = "narrative_arc"
    REFERENCE = "reference"


class DominantVisualMode(str, Enum):
    TEXT_LED = "text_led"
    DATA_LED = "data_led"
    IMAGE_LED = "image_led"
    MIXED = "mixed"
