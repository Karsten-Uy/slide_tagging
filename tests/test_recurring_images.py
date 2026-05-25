"""Tests for recurring-image (logo) detection (slide_tagger.extractors.structural.recurring_images)."""

from __future__ import annotations

from types import SimpleNamespace

import imagehash
from pptx.enum.shapes import MSO_SHAPE_TYPE

from slide_tagger.extractors.structural.recurring_images import (
    LogoGroup,
    RawLogoImage,
    auto_label,
    cluster_recurring,
    iter_picture_shapes,
)
from slide_tagger.schema.enums import Position, RecurringElementType
from slide_tagger.schema.models import RecurringElement

_H = imagehash.hex_to_hash("ffffffffffffffff")  # one hash
_H_FAR = imagehash.hex_to_hash("0000000000000000")  # hamming 64 away


def _img(idx, *, source="slide", pos=Position.TOP_RIGHT, area=0.02, h=_H):
    return RawLogoImage(phash=h, position=pos, slide_index=idx, source=source, blob=b"x", area_frac=area)


def test_iter_picture_shapes_recurses_into_groups():
    pic = SimpleNamespace(shape_type=MSO_SHAPE_TYPE.PICTURE)
    nested = SimpleNamespace(shape_type=MSO_SHAPE_TYPE.PICTURE)
    group = SimpleNamespace(shape_type=MSO_SHAPE_TYPE.GROUP, shapes=[nested])
    text = SimpleNamespace(shape_type=MSO_SHAPE_TYPE.TEXT_BOX)
    found = list(iter_picture_shapes([pic, group, text]))
    assert found == [pic, nested]  # the grouped picture is reached


def test_cluster_threshold_keeps_30pct_at_025_drops_at_06():
    imgs = [_img(0), _img(1), _img(2)]  # same logo on 3 of 10 slides = 30%
    kept = cluster_recurring(imgs, slide_count=10, fraction=0.25)
    assert len(kept) == 1 and kept[0].slide_indices == [0, 1, 2]
    dropped = cluster_recurring(imgs, slide_count=10, fraction=0.6)
    assert dropped == []


def test_master_source_kept_even_with_zero_slide_coverage():
    imgs = [_img(None, source="master")]
    kept = cluster_recurring(imgs, slide_count=10, fraction=0.6)
    assert len(kept) == 1 and kept[0].source == "master"


def test_clustering_separates_distinct_hashes():
    imgs = [_img(0), _img(1, h=_H_FAR), _img(2, h=_H_FAR)]
    kept = cluster_recurring(imgs, slide_count=4, fraction=0.25)
    # the _H group (1 slide = 25%) and the _H_FAR group (2 slides = 50%) both kept
    assert len(kept) == 2


def test_auto_label_logo_vs_not():
    logo = LogoGroup(phash="x", position=Position.TOP_RIGHT, source="slide",
                     slide_indices=[0, 1, 2], area_frac=0.02, blob=b"", type=None)
    assert auto_label(logo, slide_count=4, fraction=0.25) == RecurringElementType.LOGO

    big_centered = LogoGroup(phash="y", position=Position.CENTER, source="slide",
                             slide_indices=[0, 1, 2], area_frac=0.5, blob=b"", type=None)
    assert auto_label(big_centered, slide_count=4, fraction=0.25) is None


def test_recurring_element_with_image_path_round_trips():
    r = RecurringElement(
        type=RecurringElementType.LOGO, image_path="assets/x/recurring_00.png", source="slide"
    )
    d = r.model_dump(mode="json")
    assert d["image_path"] == "assets/x/recurring_00.png"
    assert d["source"] == "slide"
    assert d["type"] == "logo"
