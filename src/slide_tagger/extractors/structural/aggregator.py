"""Deck-level aggregation of per-slide structural data.

Currently a lightweight summary (density mix, visual-element prevalence, title
consistency) — enough to ground the deck-level VLM pass. The fuller deck-level
extraction init.md describes (modal design system, recurring-element pHash,
consistency score) is a later addition.
"""

from __future__ import annotations

from collections import Counter

from slide_tagger.schema.enums import DensityBucket, Position
from slide_tagger.schema.models import DeckStructural, DeckSummary


def summarize_deck(deck: DeckStructural) -> DeckSummary:
    """Aggregate a parsed deck into a whole-deck structural overview."""
    slides = deck.slides
    n = len(slides)

    bucket_counts = Counter(s.density.bucket for s in slides)
    density_distribution = {b: bucket_counts.get(b, 0) for b in DensityBucket}

    positions = [s.title_position for s in slides if s.title_position is not None]
    dominant_title_position: Position | None = (
        Counter(positions).most_common(1)[0][0] if positions else None
    )

    avg_word_count = (
        round(sum(s.density.word_count for s in slides) / n, 1) if n else 0.0
    )

    return DeckSummary(
        source_filename=deck.source_filename,
        slide_count=deck.slide_count,
        density_distribution=density_distribution,
        slides_with_charts=sum(1 for s in slides if s.has_chart),
        slides_with_tables=sum(1 for s in slides if s.has_table),
        slides_with_images=sum(1 for s in slides if s.image_count > 0),
        dominant_title_position=dominant_title_position,
        avg_word_count=avg_word_count,
    )
