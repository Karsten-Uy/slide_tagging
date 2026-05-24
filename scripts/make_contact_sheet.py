"""Tile slide PNGs into a single contact sheet for the enrichment (VLM) pass.

The deck-level enrichment fields (client_industry, audience_level, …) and the
deck-wide `inferred_rules` need a bird's-eye view of the whole deck. Rendering
isn't built yet (no LibreOffice), so screenshot/export each slide to a folder,
then tile them here.

Usage:
    python scripts/make_contact_sheet.py <slides_dir> -o contact_sheet.png
    python scripts/make_contact_sheet.py renders/deck1 -o sheet.png --cols 5 --thumb 320x180

Thumbnails are numbered (0-based) so the VLM can reference specific slides.
"""

from __future__ import annotations

import argparse
import math
import re
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}


def _natural_key(path: Path):
    """Sort 'slide_2' before 'slide_10'."""
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", path.name)]


def collect_images(source: Path) -> list[Path]:
    if source.is_dir():
        return sorted(
            (p for p in source.iterdir() if p.suffix.lower() in _IMAGE_EXTS),
            key=_natural_key,
        )
    if source.is_file():
        return [source]
    # treat as a glob relative to cwd
    return sorted(Path().glob(str(source)), key=_natural_key)


def make_contact_sheet(
    image_paths: list[Path],
    cols: int = 5,
    thumb: tuple[int, int] = (320, 180),
    gap: int = 10,
    labels: bool = True,
) -> Image.Image:
    if not image_paths:
        raise ValueError("No images to tile.")

    cols = max(1, min(cols, len(image_paths)))
    rows = math.ceil(len(image_paths) / cols)
    tw, th = thumb
    w = cols * tw + (cols + 1) * gap
    h = rows * th + (rows + 1) * gap
    sheet = Image.new("RGB", (w, h), "white")
    draw = ImageDraw.Draw(sheet)

    try:
        font = ImageFont.load_default(size=16)
    except TypeError:  # older Pillow: load_default takes no size
        font = ImageFont.load_default()

    for i, p in enumerate(image_paths):
        r, c = divmod(i, cols)
        x = gap + c * (tw + gap)
        y = gap + r * (th + gap)
        with Image.open(p) as im:
            sheet.paste(im.convert("RGB").resize(thumb, Image.Resampling.LANCZOS), (x, y))
        if labels:
            tag = str(i)
            draw.rectangle([x, y, x + 11 * len(tag) + 6, y + 20], fill="black")
            draw.text((x + 3, y + 2), tag, fill="white", font=font)

    return sheet


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Tile slide PNGs into a contact sheet.")
    parser.add_argument("source", type=Path, help="Folder of slide images (or a single image / glob)")
    parser.add_argument("-o", "--out", type=Path, default=Path("contact_sheet.png"))
    parser.add_argument("--cols", type=int, default=5)
    parser.add_argument("--thumb", default="320x180", help="WxH per thumbnail, e.g. 320x180")
    parser.add_argument("--gap", type=int, default=10)
    parser.add_argument("--no-labels", action="store_true", help="Do not number thumbnails")
    args = parser.parse_args(argv)

    images = collect_images(args.source)
    if not images:
        print(f"No images found at {args.source}", file=sys.stderr)
        return 2

    tw, _, thh = args.thumb.partition("x")
    thumb = (int(tw), int(thh))

    sheet = make_contact_sheet(
        images, cols=args.cols, thumb=thumb, gap=args.gap, labels=not args.no_labels
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(args.out)
    print(f"Wrote {args.out}  ({sheet.width}x{sheet.height}, {len(images)} slides)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
