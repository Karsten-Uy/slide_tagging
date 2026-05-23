"""Command-line entry point for Pipeline A.

    slide-tagger tag deck.pptx              # paste-ready STRUCTURAL DATA blocks
    slide-tagger tag deck.pptx --slide 2    # just one slide
    slide-tagger tag deck.pptx --json       # full structural JSON
    slide-tagger deck-summary deck.pptx     # paste-ready DECK SUMMARY block

The default outputs are the exact `STRUCTURAL DATA` / `DECK SUMMARY` blocks the
VLM prompt test (architecture/vlm_prompt_test.md) expects — copy them next to a
slide screenshot (per-slide pass) or a contact sheet (deck-level pass) in
claude.ai.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from slide_tagger.extractors.structural.aggregator import summarize_deck
from slide_tagger.extractors.structural.pptx_parser import parse_pptx
from slide_tagger.schema.enums import DensityBucket
from slide_tagger.schema.models import DeckSummary, SlideStructural


def structural_data_block(slide: SlideStructural) -> str:
    """Format one slide as the paste-ready STRUCTURAL DATA block."""
    d = slide.density
    title = slide.title_text or ""
    title_pos = slide.title_position.value if slide.title_position else ""
    charts = "yes" if slide.has_chart else "no"
    tables = "yes" if slide.has_table else "no"
    return "\n".join(
        [
            "STRUCTURAL DATA (from Pipeline A — context for your judgments; do NOT output these fields):",
            f"  word_count: {d.word_count}",
            f"  text_blocks: {d.text_blocks}",
            f"  visual_elements: {d.visual_elements}",
            f"  whitespace_ratio_est: {d.whitespace_ratio_est}",
            f"  density_bucket: {d.bucket.value}",
            f'  title_text: "{title}"',
            f"  title_position: {title_pos}",
            f"  images: {slide.image_count}   charts: {charts}   tables: {tables}",
        ]
    )


def deck_summary_block(summary: DeckSummary) -> str:
    """Format a deck as the paste-ready DECK SUMMARY block (deck-level pass)."""
    dd = summary.density_distribution
    dist = ", ".join(f"{b.value}={dd.get(b, 0)}" for b in DensityBucket)
    pos = summary.dominant_title_position.value if summary.dominant_title_position else ""
    return "\n".join(
        [
            "DECK SUMMARY (from Pipeline A — deterministic context; do NOT output these fields):",
            f"  slide_count: {summary.slide_count}",
            f"  density_distribution: {dist}",
            f"  slides_with_charts: {summary.slides_with_charts}   "
            f"slides_with_tables: {summary.slides_with_tables}   "
            f"slides_with_images: {summary.slides_with_images}",
            f"  dominant_title_position: {pos}",
            f"  avg_word_count: {summary.avg_word_count}",
        ]
    )


def _resolve_deck(deck: Path) -> Path | int:
    """Validate a deck path. Returns the path, or an error exit code."""
    suffix = deck.suffix.lower()
    if suffix == ".pdf":
        print(
            "PDF parsing is not implemented yet — Pipeline A currently supports .pptx. "
            "(See init.md open question on PDF support priority.)",
            file=sys.stderr,
        )
        return 2
    if suffix != ".pptx":
        print(f"Unsupported file type '{suffix}'. Expected a .pptx file.", file=sys.stderr)
        return 2
    if not deck.exists():
        print(f"File not found: {deck}", file=sys.stderr)
        return 2
    return deck


def _cmd_tag(args: argparse.Namespace) -> int:
    resolved = _resolve_deck(args.deck)
    if isinstance(resolved, int):
        return resolved
    deck = resolved

    result = parse_pptx(deck)

    if args.json:
        print(result.model_dump_json(indent=2))
        return 0

    slides = result.slides
    if args.slide is not None:
        if not 0 <= args.slide < len(slides):
            print(
                f"Slide index {args.slide} out of range (0..{len(slides) - 1}).",
                file=sys.stderr,
            )
            return 2
        slides = [slides[args.slide]]

    for slide in slides:
        print(f"# slide {slide.index}  ({result.source_filename})")
        print(structural_data_block(slide))
        print()
    return 0


def _cmd_deck_summary(args: argparse.Namespace) -> int:
    resolved = _resolve_deck(args.deck)
    if isinstance(resolved, int):
        return resolved

    summary = summarize_deck(parse_pptx(resolved))

    if args.json:
        print(summary.model_dump_json(indent=2))
        return 0

    print(deck_summary_block(summary))
    return 0


def main(argv: list[str] | None = None) -> int:
    # Emit UTF-8 regardless of the console code page (e.g. Windows cp932), so
    # the em-dash in the block header and non-ASCII slide titles print cleanly.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass

    parser = argparse.ArgumentParser(
        prog="slide-tagger",
        description="Pipeline A: deterministic structural extraction for slide decks.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_tag = sub.add_parser("tag", help="Extract structural data from a .pptx deck.")
    p_tag.add_argument("deck", type=Path, help="Path to a .pptx file")
    p_tag.add_argument(
        "--slide", type=int, default=None, help="Only this slide index (0-based)"
    )
    p_tag.add_argument(
        "--json",
        action="store_true",
        help="Emit the full structural JSON instead of paste-ready blocks",
    )
    p_tag.set_defaults(func=_cmd_tag)

    p_sum = sub.add_parser(
        "deck-summary",
        help="Emit a whole-deck DECK SUMMARY block for the deck-level VLM pass.",
    )
    p_sum.add_argument("deck", type=Path, help="Path to a .pptx file")
    p_sum.add_argument(
        "--json",
        action="store_true",
        help="Emit the deck-summary JSON instead of the paste-ready block",
    )
    p_sum.set_defaults(func=_cmd_deck_summary)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
