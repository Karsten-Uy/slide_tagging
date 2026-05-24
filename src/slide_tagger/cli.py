"""Command-line entry point for Pipeline A.

    slide-tagger tag deck.pptx              # paste-ready STRUCTURAL DATA blocks
    slide-tagger tag deck.pptx --slide 2    # just one slide
    slide-tagger tag deck.pptx --json       # full structural JSON
    slide-tagger deck-summary deck.pptx     # paste-ready DECK SUMMARY block
    slide-tagger template deck.pptx         # blank hand-tagging template (JSON)
    slide-tagger validate labels.json       # validate a hand-tagged file
    slide-tagger render deck.pptx           # per-slide PNGs (full + thumbnail)

`tag`/`deck-summary` emit paste-ready `STRUCTURAL DATA` / `DECK SUMMARY` grounding
blocks for inspecting Pipeline A's output. `template`/`validate` drive the
enrichment + hand-labeling workflow (docs/vlm_prompt_test.md, docs/manual_tagging.md,
docs/deck_tagging_prompt.md) — `template` emits a blank record (structural filled,
enrichment null) and `validate` checks it against the schema (init.md Phase 1).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pydantic import ValidationError

from slide_tagger.extractors.render.paths import deck_slug, render_rel_path, thumb_rel_path
from slide_tagger.extractors.structural.aggregator import summarize_deck
from slide_tagger.extractors.structural.pptx_parser import parse_pptx
from slide_tagger.schema.enums import DensityBucket
from slide_tagger.schema.models import DeckStructural, DeckSummary, SlideStructural
from slide_tagger.schema.tagged import DeckTag, blank_tag, legend


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


def _load_structural(src: Path) -> DeckStructural | int:
    """Load structural data from a .pptx (parse) or a Pipeline A .json (load)."""
    suffix = src.suffix.lower()
    if suffix == ".json":
        if not src.exists():
            print(f"File not found: {src}", file=sys.stderr)
            return 2
        try:
            return DeckStructural.model_validate_json(src.read_text(encoding="utf-8"))
        except ValidationError as exc:
            print(f"Not a valid Pipeline A structural JSON:\n{exc}", file=sys.stderr)
            return 1
    resolved = _resolve_deck(src)
    if isinstance(resolved, int):
        return resolved
    return parse_pptx(resolved)


def _attach_render_paths(tag: DeckTag) -> None:
    """Fill each slide's render_path/thumbnail_path from the deck slug + index, so
    the template already references where renders live (whether or not they exist
    yet). The downstream MCP server resolves them via THUMBNAIL_BASE_PATH."""
    slug = deck_slug(tag.source_filename)
    for slide in tag.slides:
        slide.render_path = render_rel_path(slug, slide.index)
        slide.thumbnail_path = thumb_rel_path(slug, slide.index)


def _cmd_template(args: argparse.Namespace) -> int:
    deck = _load_structural(args.source)
    if isinstance(deck, int):
        return deck
    tag = blank_tag(deck)
    _attach_render_paths(tag)
    out = {"_legend": legend(), **tag.model_dump(mode="json")}
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0


def _cmd_render(args: argparse.Namespace) -> int:
    resolved = _resolve_deck(args.deck)
    if isinstance(resolved, int):
        return resolved

    # Imported lazily so `tag`/`template` work even if pdf2image isn't installed.
    from slide_tagger.extractors.render import render_deck
    from slide_tagger.extractors.render.soffice import LibreOfficeNotFound, RenderError

    try:
        result = render_deck(
            resolved,
            out_root=args.out,
            dpi=args.dpi,
            thumb_px=args.thumb,
            only_index=args.slide,
            poppler_path=args.poppler_path,
        )
    except LibreOfficeNotFound as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except RenderError as exc:
        print(f"Render failed: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # pdf2image / poppler failures surface here
        print(
            f"Render failed (is poppler installed? pass --poppler-path to its bin/): {exc}",
            file=sys.stderr,
        )
        return 1

    dest = Path(args.out) / result.deck_slug
    print(f"# rendered {len(result.slides)} slide(s) from {Path(resolved).name} -> {dest}")
    for slide in result.slides:
        print(f"  slide {slide.index}: {slide.render_path}  ·  {slide.thumbnail_path}")
    return 0


def _is_filled(value: object) -> bool:
    """A field counts as filled if it's a non-empty value (str/enum/list)."""
    if value is None:
        return False
    if isinstance(value, (str, list, dict)):
        return len(value) > 0
    return True


def _cmd_validate(args: argparse.Namespace) -> int:
    path: Path = args.labels
    if not path.exists():
        print(f"File not found: {path}", file=sys.stderr)
        return 2
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"Invalid JSON: {exc}", file=sys.stderr)
        return 1
    data.pop("_legend", None)  # template helper, not part of the schema

    try:
        tag = DeckTag.model_validate(data)
    except ValidationError as exc:
        print(f"✗ Schema errors in {path.name}:\n{exc}", file=sys.stderr)
        return 1

    # Deck-level enrichment fields the tagger fills in (deck_length is auto-set
    # from slide_count, so it isn't counted here).
    deck_fields = {
        "client_industry": tag.client_industry,
        "client_sub_industry": tag.client_sub_industry,
        "client_type": tag.client_type,
        "engagement_stage": tag.engagement_stage,
        "content_area": tag.content_area,
        "audience_level": tag.audience_level,
        "deliverable_format": tag.deliverable_format,
        "geography": tag.geography,
        "confidentiality_tier": tag.confidentiality_tier,
        "inferred_publisher": tag.inferred_publisher,
        "deck_summary_one_sentence": tag.deck_summary_one_sentence,
    }
    deck_missing = [k for k, v in deck_fields.items() if not _is_filled(v)]

    # A slide counts as fully tagged once its core enrichment fields are set.
    incomplete = [
        s.index
        for s in tag.slides
        if not _is_filled(s.slide_purpose)
        or not _is_filled(s.message_type)
        or not _is_filled(s.main_message)
        or not _is_filled(s.dominant_visual_element)
    ]

    print(f"✓ Schema valid: {path.name}")
    deck_done = len(deck_fields) - len(deck_missing)
    line = f"Deck-level: {deck_done}/{len(deck_fields)} filled"
    if deck_missing:
        line += f"  (missing: {', '.join(deck_missing)})"
    print(line)
    done = len(tag.slides) - len(incomplete)
    line = f"Slides fully tagged: {done}/{len(tag.slides)}"
    if incomplete:
        line += f"  (incomplete: {incomplete})"
    print(line)

    ds = tag.design_system
    if ds is not None and ds.recurring_elements:
        untyped = [i for i, r in enumerate(ds.recurring_elements) if r.type is None]
        typed = len(ds.recurring_elements) - len(untyped)
        line = f"Recurring elements typed: {typed}/{len(ds.recurring_elements)}"
        if untyped:
            line += f"  (untyped indices: {untyped})"
        if ds.grid is None:
            line += "  · grid: unset"
        print(line)

    ir = tag.inferred_rules
    ir_populated = ir is not None and (
        _is_filled(ir.title.font_family_observed)
        or _is_filled(ir.title.size_pt_most_common)
        or _is_filled(ir.body_text.font_family_observed)
        or _is_filled(ir.color_palette.primary_observed)
    )
    prov_set = tag.provenance is not None and _is_filled(tag.provenance.tagged_by)
    print(
        f"Inferred rules: {'populated' if ir_populated else 'empty'}  ·  "
        f"provenance: {'set' if prov_set else 'unset'}"
    )
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

    p_tpl = sub.add_parser(
        "template",
        help="Emit a blank hand-tagging template (structural filled, semantics null).",
    )
    p_tpl.add_argument(
        "source", type=Path, help="A .pptx deck or a Pipeline A structural .json"
    )
    p_tpl.set_defaults(func=_cmd_template)

    p_val = sub.add_parser(
        "validate", help="Validate a hand-tagged JSON file and report completeness."
    )
    p_val.add_argument("labels", type=Path, help="Path to a hand-tagged .json file")
    p_val.set_defaults(func=_cmd_validate)

    p_render = sub.add_parser(
        "render",
        help="Render a .pptx to per-slide PNGs (full + thumbnail) via LibreOffice.",
    )
    p_render.add_argument("deck", type=Path, help="Path to a .pptx file")
    p_render.add_argument(
        "--out",
        type=Path,
        default=Path("data/renders"),
        help="Render output root (default: data/renders)",
    )
    p_render.add_argument(
        "--dpi", type=int, default=150, help="Full-render DPI (default: 150)"
    )
    p_render.add_argument(
        "--thumb", type=int, default=512, help="Thumbnail long-edge px (default: 512)"
    )
    p_render.add_argument(
        "--slide", type=int, default=None, help="Only this slide index (0-based)"
    )
    p_render.add_argument(
        "--poppler-path",
        dest="poppler_path",
        type=str,
        default=None,
        help="Path to poppler's bin/ if pdftoppm is not on PATH (common on Windows)",
    )
    p_render.set_defaults(func=_cmd_render)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
