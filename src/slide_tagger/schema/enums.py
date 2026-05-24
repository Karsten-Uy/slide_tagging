"""Constrained vocabulary for the slide-tagging schema.

Every enumerated field draws from one of these sets. Add new values
deliberately, never ad hoc (init.md: "constrained vocabulary throughout").

Two families live here:
- Structural (Pipeline A): SourceFormat, DensityBucket, Position, and the
  design-system enums (FontWeight, TextAlignment, Grid, RecurringElementType).
- Semantic enrichment (Pipeline B / VLM / hand-label): the deck-level,
  slide-level, and inferred-rules vocabularies. These mirror the controlled
  vocabularies in docs/deck_tagging_prompt.md.
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


# --- Deck-level enrichment vocabulary (Pipeline B / VLM produces these). These
# --- need a whole-deck view; a single slide can't yield them.


class ClientIndustry(str, Enum):
    FINANCIAL_SERVICES = "Financial Services"
    TECH = "Tech"
    HEALTHCARE = "Healthcare"
    PUBLIC_SECTOR = "Public Sector"
    INDUSTRIALS = "Industrials"
    CONSUMER = "Consumer"
    ENERGY = "Energy"
    EDUCATION = "Education"
    CROSS_INDUSTRY = "Cross-industry"


class ClientType(str, Enum):
    PUBLIC_SECTOR = "Public sector"
    PRIVATE_F500 = "Private F500"
    PRIVATE_MID_MARKET = "Private mid-market"
    GOVERNMENT_AGENCY = "Government agency"
    NON_PROFIT = "Non-profit"
    INTERNAL_THOUGHT_LEADERSHIP = "Internal/thought-leadership"


class EngagementStage(str, Enum):
    RFP_RESPONSE = "RFP response"
    PITCH_OPPORTUNITY_DEV = "Pitch / opportunity dev"
    KICKOFF = "Kickoff"
    MID_PROJECT_READOUT = "Mid-project readout"
    WEEKLY_UPDATE = "Weekly update"
    FINAL_DELIVERY = "Final delivery"
    POV_THOUGHT_LEADERSHIP = "POV / thought leadership"


class ContentArea(str, Enum):
    STRATEGY = "Strategy"
    DIGITAL_TRANSFORMATION = "Digital transformation"
    SDLC = "SDLC"
    AI_ML = "AI/ML"
    ERP = "ERP"
    M_AND_A = "M&A"
    OPERATIONAL_EXCELLENCE = "Operational excellence"
    ORG_DESIGN = "Org design"
    COST_REDUCTION = "Cost reduction"
    RISK = "Risk"
    MARKET_ANALYSIS = "Market analysis"
    ESG = "ESG"
    WORKFORCE = "Workforce"
    FINANCIAL_REPORTING = "Financial reporting"
    OTHER = "Other"


class AudienceLevel(str, Enum):
    C_SUITE_BOARD = "C-suite / board"
    SENIOR_EXECUTIVES = "Senior executives"
    OPERATING_COMMITTEE = "Operating committee"
    WORKING_TEAM = "Working team"
    EXTERNAL_PUBLIC = "External / public"


class DeliverableFormat(str, Enum):
    POWERPOINT = "PowerPoint"
    PDF = "PDF"
    HYBRID = "Hybrid"
    ONLINE_INTERACTIVE = "Online interactive"


class Geography(str, Enum):
    US = "US"
    UK = "UK"
    EMEA = "EMEA"
    APAC = "APAC"
    GLOBAL = "Global"
    REGIONAL = "Regional (specify)"


class ConfidentialityTier(str, Enum):
    PUBLIC = "Public"
    INTERNAL = "Internal"
    CLIENT_CONFIDENTIAL = "Client-confidential"
    RESTRICTED = "Restricted"


# --- Slide-level enrichment vocabulary (Pipeline B / VLM produces these). ---


class SlidePurpose(str, Enum):
    TITLE = "Title"
    SECTION_DIVIDER = "Section divider"
    AGENDA_CONTENTS = "Agenda / Contents"
    EXEC_SUMMARY = "Exec summary"
    CONTEXT_SETTING = "Context-setting"
    CURRENT_STATE = "Current state"
    FINDING = "Finding"
    INSIGHT = "Insight"
    RECOMMENDATION = "Recommendation"
    FRAMEWORK = "Framework"
    ROADMAP = "Roadmap"
    TIMELINE = "Timeline"
    COMPARISON = "Comparison"
    DECISION_MATRIX = "Decision matrix"
    DATA_PRESENTATION = "Data presentation"
    CASE_STUDY = "Case study"
    TEAM_INTRO = "Team intro"
    METHODOLOGY = "Methodology"
    PRICING = "Pricing"
    QA = "Q&A"
    APPENDIX_REFERENCE = "Appendix / reference"
    CLOSING_CONTACTS = "Closing / contacts"


class MessageType(str, Enum):
    ASSERTION = "Assertion"
    COMPARISON = "Comparison"
    SEQUENCE_TIMELINE = "Sequence / timeline"
    DECOMPOSITION = "Decomposition (parts of whole)"
    CAUSATION = "Causation"
    TREND_OVER_TIME = "Trend over time"
    TRADE_OFF = "Trade-off"
    PROCESS_FLOW = "Process flow"
    LISTING_ENUMERATION = "Listing / enumeration"
    SINGLE_STATISTIC_HERO = "Single statistic / hero number"
    NO_CLEAR_MESSAGE = "No clear message"


class AudienceLevelSlide(str, Enum):
    C_SUITE_BOARD = "C-suite / board"
    SENIOR_EXECUTIVES = "Senior executives"
    OPERATING_COMMITTEE = "Operating committee"
    WORKING_TEAM = "Working team"
    EXTERNAL_PUBLIC = "External / public"
    SAME_AS_DECK = "Same as deck"


class SlidePositionRole(str, Enum):
    HERO_HEADLINE = "Hero / headline"
    BUILD_SETUP = "Build / setup"
    EVIDENCE_BACKUP = "Evidence / backup"
    SYNTHESIS_TAKEAWAY = "Synthesis / takeaway"
    TRANSITION_DIVIDER = "Transition / divider"


class DominantVisualElement(str, Enum):
    CHART = "Chart"
    DIAGRAM = "Diagram"
    TABLE = "Table"
    IMAGE = "Image"
    ICON_BASED = "Icon-based"
    FRAMEWORK_GRAPHIC = "Framework graphic"
    PURE_TEXT = "Pure text"
    MIXED = "Mixed"


class ChartType(str, Enum):
    LINE = "Line"
    BAR = "Bar"
    STACKED_BAR = "Stacked bar"
    PIE = "Pie"
    WATERFALL = "Waterfall"
    SCATTER = "Scatter"
    BUBBLE = "Bubble"
    TREEMAP = "Treemap"
    HEAT_MAP = "Heat map"
    SANKEY = "Sankey"
    OTHER = "Other"
    NA = "N/A"


class PlaceholderCompliance(str, Enum):
    PRISTINE = "Pristine"
    REUSABLE = "Reusable"
    BESPOKE = "Bespoke"
    BROKEN = "Broken"


class SlotType(str, Enum):
    TITLE = "title"
    SUBTITLE = "subtitle"
    BODY_TEXT = "body-text"
    BULLET_LIST = "bullet-list"
    CHART = "chart"
    IMAGE = "image"
    TABLE = "table"
    CALLOUT_BOX = "callout-box"
    CITATION = "citation"
    FOOTER = "footer"
    PAGE_NUMBER = "page-number"


class ReusabilityScore(str, Enum):
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


class TierMatchDifficulty(str, Enum):
    TIER_1 = "Likely Tier 1 candidate"
    TIER_2 = "Likely Tier 2"
    TIER_3 = "Likely Tier 3"
    TIER_4 = "Likely Tier 4"


# --- Inferred-rules vocabulary (element-level style observations, scope=inferred).


class UsesActionTitles(str, Enum):
    ALWAYS = "always"
    SOMETIMES = "sometimes"
    RARELY = "rarely"


class ChartPaletteConsistency(str, Enum):
    TRUE = "true"
    FALSE = "false"
    NA = "n/a"


class MasterTemplateUsage(str, Enum):
    TRUE = "true"
    FALSE = "false"
    MIXED = "mixed"


# --- Design-system vocabulary (deck-level structural, Pipeline A) ---


class FontWeight(str, Enum):
    REGULAR = "regular"
    MEDIUM = "medium"
    BOLD = "bold"


class TextAlignment(str, Enum):
    LEFT = "left"
    CENTER = "center"
    RIGHT = "right"
    JUSTIFY = "justify"


class Grid(str, Enum):
    TWELVE_COLUMN = "12-column"
    SIX_COLUMN = "6-column"
    FREE = "free"


class RecurringElementType(str, Enum):
    """What a detected recurring element is — hand-labeled (pHash finds it; a
    human/VLM says what it is)."""

    LOGO = "logo"
    PAGE_NUMBER = "page_number"
    FOOTER = "footer"
    WATERMARK = "watermark"
