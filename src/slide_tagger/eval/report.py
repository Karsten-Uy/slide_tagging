"""Render a CorpusScore as a console scorecard, JSON, or Markdown.

The console view is the prompt-optimization signal: overall accuracy vs the 85%
target, per-field accuracy ranked weakest-first, the enum confusions behind the
weak fields, the two rubric checks, and free-text pairs for manual review.
"""

from __future__ import annotations

import json
from typing import Any

from slide_tagger.eval.fields import ENUM_LIST, SCORED_KINDS
from slide_tagger.eval.score import CorpusScore, FieldResult

TARGET = 0.85


def _pct(value: float | None) -> str:
    return "—" if value is None else f"{value * 100:.0f}%"


def _show(value: Any) -> str:
    if value is None:
        return "(missing)"
    if isinstance(value, list):
        return "[" + ", ".join(str(v) for v in value) + "]"
    return str(value)


def _scored_fields(score: CorpusScore) -> list[FieldResult]:
    rows = [r for r in score.results.values() if r.kind in SCORED_KINDS and r.scored]
    # weakest first; ties broken by larger sample (more decisive) first
    return sorted(rows, key=lambda r: (r.accuracy or 0.0, -r.scored))


def render_console(score: CorpusScore) -> str:
    lines: list[str] = []
    names = ", ".join(score.deck_names) or "(none)"
    lines.append(
        f"Eval scorecard — {len(score.deck_names)} deck(s), {score.n_slides} slide(s): {names}"
    )
    lines.append("")

    acc = score.headline_accuracy
    scored = sum(r.scored for r in score.results.values() if r.kind in SCORED_KINDS)
    correct = sum(r.correct for r in score.results.values() if r.kind in SCORED_KINDS)
    flag = "PASS" if (acc is not None and acc >= TARGET) else "BELOW"
    lines.append(
        f"Semantic accuracy: {_pct(acc)}  (target {_pct(TARGET)})  [{flag}]   "
        f"{correct}/{scored} scored field instances"
    )
    lines.append("")

    lines.append("Per-field accuracy (weakest first):")
    lines.append(f"  {'field':<48}{'level':<9}{'kind':<11}{'n':>4}  {'acc':>5}  {'meanF1':>7}")
    for r in _scored_fields(score):
        mean_f1 = _pct(r.mean_f1) if r.kind == ENUM_LIST else ""
        lines.append(
            f"  {r.path:<48}{r.level:<9}{r.kind:<11}{r.scored:>4}  {_pct(r.accuracy):>5}  {mean_f1:>7}"
        )
    lines.append("")

    confused = [r for r in _scored_fields(score) if r.confusions]
    if confused:
        lines.append("Top confusions (predicted → truth):")
        for r in confused:
            for (pred, truth), n in r.confusions.most_common(5):
                lines.append(f"  {r.path}: {_show(pred)} → {_show(truth)} ×{n}")
        lines.append("")

    lines.append("Rubric check — structural integrity (Pipeline A fields unchanged):")
    if score.structural_diffs:
        lines.append(f"  FAIL ({len(score.structural_diffs)} changed):")
        for d in score.structural_diffs:
            lines.append(f"    - {d}")
    else:
        lines.append("  PASS")
    lines.append("")

    if score.free_text:
        lines.append("Free-text (manual review, not scored):")
        for pair in score.free_text:
            where = pair.path if pair.index is None else f"slide {pair.index} · {pair.path}"
            tag = f"[{pair.deck}] " if pair.deck else ""
            lines.append(f"  {tag}{where}")
            lines.append(f"    pred:  {_show(pair.predicted)}")
            lines.append(f"    truth: {_show(pair.truth)}")

    return "\n".join(lines)


def render_json(score: CorpusScore) -> str:
    payload = {
        "decks": score.deck_names,
        "n_slides": score.n_slides,
        "headline_accuracy": score.headline_accuracy,
        "target": TARGET,
        "fields": [
            {
                "path": r.path,
                "level": r.level,
                "kind": r.kind,
                "scored": r.scored,
                "correct": r.correct,
                "accuracy": r.accuracy,
                "mean_f1": r.mean_f1 if r.kind == ENUM_LIST else None,
                "confusions": [
                    {"predicted": p, "truth": t, "count": n}
                    for (p, t), n in r.confusions.most_common()
                ],
            }
            for r in _scored_fields(score)
        ],
        "structural_diffs": score.structural_diffs,
        "free_text": [
            {
                "deck": pair.deck,
                "path": pair.path,
                "index": pair.index,
                "predicted": pair.predicted,
                "truth": pair.truth,
            }
            for pair in score.free_text
        ],
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)


def render_markdown(score: CorpusScore) -> str:
    acc = score.headline_accuracy
    flag = "PASS" if (acc is not None and acc >= TARGET) else "BELOW"
    lines: list[str] = []
    lines.append("# Eval scorecard")
    lines.append("")
    lines.append(f"- Decks: {', '.join(score.deck_names) or '(none)'} ({score.n_slides} slides)")
    lines.append(f"- **Semantic accuracy: {_pct(acc)}** (target {_pct(TARGET)}) — {flag}")
    lines.append("")
    lines.append("## Per-field accuracy (weakest first)")
    lines.append("")
    lines.append("| field | level | kind | n | accuracy | mean F1 |")
    lines.append("|---|---|---|--:|--:|--:|")
    for r in _scored_fields(score):
        mean_f1 = _pct(r.mean_f1) if r.kind == ENUM_LIST else ""
        lines.append(
            f"| {r.path} | {r.level} | {r.kind} | {r.scored} | {_pct(r.accuracy)} | {mean_f1} |"
        )
    lines.append("")
    lines.append("## Rubric check — structural integrity")
    lines.append("")
    lines.append(
        f"- Structural integrity: {'PASS' if not score.structural_diffs else 'FAIL — ' + ', '.join(score.structural_diffs)}"
    )
    return "\n".join(lines)
