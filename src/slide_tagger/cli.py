"""Command-line entry point for Pipeline A.

    slide-tagger tag deck.pptx              # paste-ready STRUCTURAL DATA blocks
    slide-tagger tag deck.pptx --slide 2    # just one slide
    slide-tagger tag deck.pptx --json       # full structural JSON
    slide-tagger deck-summary deck.pptx     # paste-ready DECK SUMMARY block
    slide-tagger template deck.pptx         # blank hand-tagging template (JSON)
    slide-tagger validate labels.json       # validate a hand-tagged file
    slide-tagger render deck.pptx           # per-slide PNGs (full + thumbnail)
    slide-tagger merge vlm.json input.json  # re-impose Pipeline A fields on VLM output
    slide-tagger score pred.json truth.json # score enriched output vs hand-label
    slide-tagger eval                       # score data/tagged/* vs hand_labels/*
    slide-tagger bench --runs 3             # API: N runs/deck, mean±std (needs ANTHROPIC_API_KEY)

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

from slide_tagger.eval import score_corpus, score_deck
from slide_tagger.eval.report import render_console, render_json, render_markdown
from slide_tagger.extractors.render.paths import deck_slug, render_rel_path, thumb_rel_path
from slide_tagger.extractors.structural.aggregator import summarize_deck
from slide_tagger.extractors.structural.pptx_parser import parse_pptx
from slide_tagger.merge import merge_structural
from slide_tagger.enrich import enrich_once, prompt_body, upload_pdf
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


def _load_tag(path: Path) -> DeckTag | int:
    """Load a tagged-deck JSON (stripping the template `_legend`) into a DeckTag,
    or return an error exit code (2 not-found, 1 invalid JSON / schema)."""
    if not path.exists():
        print(f"File not found: {path}", file=sys.stderr)
        return 2
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"Invalid JSON in {path.name}: {exc}", file=sys.stderr)
        return 1
    data.pop("_legend", None)  # template helper, not part of the schema
    try:
        return DeckTag.model_validate(data)
    except ValidationError as exc:
        print(f"✗ Schema errors in {path.name}:\n{exc}", file=sys.stderr)
        return 1


def _cmd_validate(args: argparse.Namespace) -> int:
    path: Path = args.labels
    tag = _load_tag(path)
    if isinstance(tag, int):
        return tag

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


def _read_json_lenient(path: Path) -> dict | int:
    """Read a JSON file into a raw dict, tolerating a leading ```json code fence
    (the web GUI often wraps output in one) and stripping the template `_legend`.
    Returns an error exit code on failure."""
    if not path.exists():
        print(f"File not found: {path}", file=sys.stderr)
        return 2
    text = path.read_text(encoding="utf-8").strip()
    if text.startswith("```"):
        lines = text.splitlines()
        lines = lines[1:]  # drop the opening ``` / ```json
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        print(f"Invalid JSON in {path.name}: {exc}", file=sys.stderr)
        return 1
    if not isinstance(data, dict):
        print(f"Expected a JSON object in {path.name}, got {type(data).__name__}.", file=sys.stderr)
        return 1
    data.pop("_legend", None)
    return data


def _cmd_merge(args: argparse.Namespace) -> int:
    vlm = _read_json_lenient(args.vlm_output)
    if isinstance(vlm, int):
        return vlm
    template = _read_json_lenient(args.template)
    if isinstance(template, int):
        return template

    merged = merge_structural(vlm, template)

    out_text = json.dumps(merged, indent=2, ensure_ascii=False)
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(out_text + "\n", encoding="utf-8")
        print(f"# wrote merged record -> {args.out}", file=sys.stderr)
    else:
        print(out_text)

    # Best-effort validation so the user sees any *remaining* (non-structural)
    # problems — e.g. an out-of-enum value the VLM produced — right away.
    try:
        DeckTag.model_validate(merged)
        print("# structural fields re-imposed from template; result validates.", file=sys.stderr)
    except ValidationError as exc:
        n = len(exc.errors())
        print(
            f"# structural fields re-imposed, but {n} schema issue(s) remain "
            "(not structural — fix in the VLM output or prompt):",
            file=sys.stderr,
        )
        for err in exc.errors()[:10]:
            print(f"#   {'.'.join(str(x) for x in err['loc'])}: {err['msg']}", file=sys.stderr)
    return 0


# Maps a hand-label stem (reference_data/hand_labels/<stem>.tagged.json) to the
# source file stem in reference_data/hand_labels/sources/ (they differ for
# ereadiness). The clean, index-aligned decks default on; the others are opt-in.
_BENCH_DECKS = {
    "nigeria-economic-outlook-october-2023-v1": "nigeria-economic-outlook-october-2023-v1",
    "digital-auto-report-2023": "digital-auto-report-2023",
    "electric-vehicle-sales-review-q4-2022": "electric-vehicle-sales-review-q4-2022",
    "ereadiness-study-2023": "strategyand-ereadiness-study-2023",
}
_BENCH_DEFAULT = ["nigeria-economic-outlook-october-2023-v1", "digital-auto-report-2023"]


def _build_template(pptx: Path) -> dict:
    """Pipeline A structural template + _legend, identical to `template` output."""
    tag = blank_tag(parse_pptx(pptx))
    _attach_render_paths(tag)
    return {"_legend": legend(), **tag.model_dump(mode="json")}


def _cmd_bench(args: argparse.Namespace) -> int:
    import statistics
    from collections import defaultdict

    try:
        import anthropic
    except ImportError:
        print("`bench` needs the anthropic SDK — run `uv sync` (it's now a dependency).", file=sys.stderr)
        return 2

    if not args.prompt.exists():
        print(f"Prompt file not found: {args.prompt}", file=sys.stderr)
        return 2
    system = prompt_body(args.prompt)

    try:
        client = anthropic.Anthropic()
    except Exception as exc:  # missing/invalid key surfaces here
        print(f"Could not init Anthropic client (is ANTHROPIC_API_KEY set?): {exc}", file=sys.stderr)
        return 2

    decks = args.deck or _BENCH_DEFAULT
    deck_scores: dict[str, list[float]] = {}
    per_field: dict[str, list[float]] = defaultdict(list)

    for stem in decks:
        src = _BENCH_DECKS.get(stem, stem)
        pptx, pdf = args.sources / f"{src}.pptx", args.sources / f"{src}.pdf"
        label = args.labels / f"{stem}.tagged.json"
        if not (pptx.exists() and pdf.exists() and label.exists()):
            print(f"# skip {stem}: need {pptx.name}, {pdf.name}, {label.name}", file=sys.stderr)
            continue
        truth = _load_tag(label)
        if isinstance(truth, int):
            return truth
        template = _build_template(pptx)
        template_core = {k: v for k, v in template.items() if k != "_legend"}

        print(f"# {stem}: uploading PDF…", file=sys.stderr)
        try:
            file_id = upload_pdf(client, pdf)
        except Exception as exc:  # auth / network / API errors surface here
            print(f"# {stem}: upload failed ({exc}). Is ANTHROPIC_API_KEY set and valid?", file=sys.stderr)
            return 2
        (args.out / stem).mkdir(parents=True, exist_ok=True)
        scores: list[float] = []
        for k in range(args.runs):
            try:
                enriched = enrich_once(
                    client, system=system, template=template,
                    file_id=file_id, model=args.model, effort=args.effort,
                )
            except Exception as exc:
                print(f"# {stem} run {k + 1}/{args.runs} FAILED: {exc}", file=sys.stderr)
                continue
            enriched.pop("_legend", None)
            merged = merge_structural(enriched, template_core)
            try:
                pred = DeckTag.model_validate(merged)
            except ValidationError as exc:
                print(f"# {stem} run {k + 1}: invalid after sanitize ({len(exc.errors())} errs) — skipped", file=sys.stderr)
                continue
            ds = score_deck(pred, truth, name=f"{stem}#{k + 1}")
            acc = score_corpus([ds]).headline_accuracy or 0.0
            scores.append(acc)
            for path, fr in ds.results.items():
                if fr.scored and fr.accuracy is not None:
                    per_field[path].append(fr.accuracy)
            (args.out / stem / f"run_{k + 1}.json").write_text(
                json.dumps(merged, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            print(f"# {stem} run {k + 1}/{args.runs}: {acc:.0%}", file=sys.stderr)
        try:
            client.beta.files.delete(file_id)
        except Exception:
            pass
        if scores:
            deck_scores[stem] = scores

    if not deck_scores:
        print("No successful runs.", file=sys.stderr)
        return 1

    print("\n=== bench report ===")
    print(f"prompt: {args.prompt}  ·  model: {args.model}  ·  effort: {args.effort}  ·  runs/deck: {args.runs}")
    deck_means = []
    for stem, scores in deck_scores.items():
        mean = statistics.mean(scores)
        sd = statistics.pstdev(scores) if len(scores) > 1 else 0.0
        deck_means.append(mean)
        runs_str = ", ".join(f"{s:.0%}" for s in scores)
        print(f"  {stem}: {mean:.1%} ± {sd:.1%}  (runs: {runs_str})")
    if deck_means:
        print(f"  CORPUS (mean of deck means): {statistics.mean(deck_means):.1%}")

    print("\nPer-field mean accuracy across all runs (weakest first):")
    rows = sorted(((p, statistics.mean(v), len(v)) for p, v in per_field.items()), key=lambda r: r[1])
    for path, mean, n in rows:
        print(f"  {path:48} {mean:.0%}  (n_runs={n})")
    return 0


def _cmd_score(args: argparse.Namespace) -> int:
    pred = _load_tag(args.predicted)
    if isinstance(pred, int):
        return pred
    truth = _load_tag(args.truth)
    if isinstance(truth, int):
        return truth
    deck = score_deck(pred, truth, name=args.predicted.stem)
    print(render_console(score_corpus([deck])))
    return 0


def _cmd_eval(args: argparse.Namespace) -> int:
    labels_dir: Path = args.labels
    pred_dir: Path = args.pred_dir
    if not labels_dir.is_dir():
        print(f"Labels dir not found: {labels_dir}", file=sys.stderr)
        return 2
    if not pred_dir.is_dir():
        print(f"Predictions dir not found: {pred_dir}", file=sys.stderr)
        return 2

    label_files = sorted(labels_dir.glob("*.json"))
    if not label_files:
        print(f"No hand-label JSON files in {labels_dir}", file=sys.stderr)
        return 2

    deck_scores = []
    for label_file in label_files:
        pred_file = pred_dir / label_file.name  # predictions share the hand-label filename
        if not pred_file.exists():
            print(f"# skip {label_file.name}: no prediction at {pred_file}", file=sys.stderr)
            continue
        truth = _load_tag(label_file)
        if isinstance(truth, int):
            return truth
        pred = _load_tag(pred_file)
        if isinstance(pred, int):
            return pred
        deck_scores.append(score_deck(pred, truth, name=label_file.stem))

    if not deck_scores:
        print("No matched (prediction, hand-label) pairs found.", file=sys.stderr)
        return 2

    corpus = score_corpus(deck_scores)
    print(render_console(corpus))
    if args.json:
        Path(args.json).write_text(render_json(corpus), encoding="utf-8")
        print(f"\n# wrote JSON report -> {args.json}", file=sys.stderr)
    if args.markdown:
        Path(args.markdown).write_text(render_markdown(corpus), encoding="utf-8")
        print(f"# wrote Markdown report -> {args.markdown}", file=sys.stderr)
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

    p_merge = sub.add_parser(
        "merge",
        help="Re-impose Pipeline A structural fields from the template onto a VLM "
        "output (so the VLM can't corrupt deterministic fields).",
    )
    p_merge.add_argument(
        "vlm_output", type=Path, help="The enriched JSON returned by the VLM"
    )
    p_merge.add_argument(
        "template",
        type=Path,
        help="The Pipeline A template (input.json) the VLM enriched",
    )
    p_merge.add_argument(
        "-o",
        "--out",
        type=Path,
        default=None,
        help="Write merged JSON here (default: stdout). Status goes to stderr.",
    )
    p_merge.set_defaults(func=_cmd_merge)

    p_score = sub.add_parser(
        "score",
        help="Score one enriched (VLM) deck against its hand-label, field by field.",
    )
    p_score.add_argument("predicted", type=Path, help="Predicted (VLM-enriched) .json")
    p_score.add_argument("truth", type=Path, help="Hand-label ground-truth .json")
    p_score.set_defaults(func=_cmd_score)

    p_eval = sub.add_parser(
        "eval",
        help="Score every prediction against its hand-label and print a corpus scorecard.",
    )
    p_eval.add_argument(
        "--labels",
        type=Path,
        default=Path("reference_data/hand_labels"),
        help="Hand-label dir (default: reference_data/hand_labels)",
    )
    p_eval.add_argument(
        "--pred-dir",
        dest="pred_dir",
        type=Path,
        default=Path("data/tagged"),
        help="Predictions dir; files share the hand-label filename (default: data/tagged)",
    )
    p_eval.add_argument(
        "--json", type=Path, default=None, help="Also write a JSON report to this path"
    )
    p_eval.add_argument(
        "--markdown",
        type=Path,
        default=None,
        help="Also write a Markdown report to this path",
    )
    p_eval.set_defaults(func=_cmd_eval)

    p_bench = sub.add_parser(
        "bench",
        help="Run the enrichment prompt via the Claude API N times per deck and "
        "report mean ± std accuracy (averages out run-to-run variance).",
    )
    p_bench.add_argument(
        "--deck", action="append", default=None,
        help=f"Hand-label stem to run (repeatable). Default: {', '.join(_BENCH_DEFAULT)}",
    )
    p_bench.add_argument("--runs", type=int, default=3, help="Runs per deck (default: 3)")
    p_bench.add_argument(
        "--model", default="claude-opus-4-7",
        help="Model (default: claude-opus-4-7; pass claude-sonnet-4-6 for lower cost)",
    )
    p_bench.add_argument(
        "--effort", default="high", choices=["low", "medium", "high", "max"],
        help="Thinking/output effort (default: high)",
    )
    p_bench.add_argument(
        "--prompt", type=Path, default=Path("docs/deck_tagging_prompt.md"),
        help="Prompt markdown; its '## The Prompt' body is used as the system prompt",
    )
    p_bench.add_argument(
        "--sources", type=Path, default=Path("data/source"),
        help="Dir holding each deck's .pptx and .pdf (default: data/source)",
    )
    p_bench.add_argument(
        "--labels", type=Path, default=Path("reference_data/hand_labels"),
        help="Hand-label dir (the answer key)",
    )
    p_bench.add_argument(
        "--out", type=Path, default=Path("data/tagged/bench"),
        help="Where to write each run's merged JSON (default: data/tagged/bench)",
    )
    p_bench.set_defaults(func=_cmd_bench)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
