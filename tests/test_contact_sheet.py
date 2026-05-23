"""Tests for the contact-sheet tiling helper."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest
from PIL import Image

_ROOT = Path(__file__).resolve().parents[1]


def _load_contact_sheet():
    spec = importlib.util.spec_from_file_location(
        "make_contact_sheet", _ROOT / "scripts" / "make_contact_sheet.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["make_contact_sheet"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def cs():
    return _load_contact_sheet()


def _dummy_pngs(dir_path: Path, n: int) -> list[Path]:
    paths = []
    for i in range(n):
        p = dir_path / f"slide_{i}.png"
        Image.new("RGB", (640, 360), (i * 20 % 255, 100, 150)).save(p)
        paths.append(p)
    return paths


def test_sheet_dimensions(cs, tmp_path):
    paths = _dummy_pngs(tmp_path, 6)
    sheet = cs.make_contact_sheet(paths, cols=3, thumb=(320, 180), gap=10)
    # 3 cols x 2 rows
    assert sheet.width == 3 * 320 + 4 * 10
    assert sheet.height == 2 * 180 + 3 * 10


def test_cols_clamped_to_image_count(cs, tmp_path):
    paths = _dummy_pngs(tmp_path, 2)
    sheet = cs.make_contact_sheet(paths, cols=5, thumb=(100, 100), gap=5)
    # only 2 images -> 2 columns, 1 row
    assert sheet.width == 2 * 100 + 3 * 5


def test_empty_raises(cs):
    with pytest.raises(ValueError):
        cs.make_contact_sheet([])


def test_natural_sort(cs, tmp_path):
    for name in ("slide_10.png", "slide_2.png", "slide_1.png"):
        Image.new("RGB", (10, 10), "white").save(tmp_path / name)
    ordered = [p.name for p in cs.collect_images(tmp_path)]
    assert ordered == ["slide_1.png", "slide_2.png", "slide_10.png"]
