"""Density bucketing — derive a coarse density label from deterministic counts.

Thresholds mirror the density guide documented in
architecture/vlm_prompt_test.md and init.md.
"""

from __future__ import annotations

from slide_tagger.schema.enums import DensityBucket

_VERY_DENSE_WORDS = 90
_DENSE_WORDS = 50
_BALANCED_WORDS = 20
_VERY_DENSE_VISUALS = 6


def density_bucket(word_count: int, visual_elements: int) -> DensityBucket:
    """Bucket a slide by how much it asks the viewer to process.

    sparse <~20 words; balanced ~20-50; dense ~50-90; very_dense >~90 words
    (or a visually crowded slide).
    """
    if word_count > _VERY_DENSE_WORDS or visual_elements >= _VERY_DENSE_VISUALS:
        return DensityBucket.VERY_DENSE
    if word_count >= _DENSE_WORDS:
        return DensityBucket.DENSE
    if word_count >= _BALANCED_WORDS:
        return DensityBucket.BALANCED
    return DensityBucket.SPARSE
