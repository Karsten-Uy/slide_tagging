"""Re-impose Pipeline A's structural fields onto an enrichment (VLM) output.

The enrichment pass (Pipeline B) is told to copy every structural field verbatim,
but a VLM can't be trusted to faithfully echo 100+ deterministic fields — and it
shouldn't have to. `merge_structural` takes the VLM's enriched record and the
original `template` (Pipeline A's structural output) and returns a record that
keeps the VLM's *enrichment* fields while restoring every *structural* field from
the template. This guarantees the structural-integrity invariant
(`docs/vlm_prompt_test.md` rubric) regardless of what the VLM did.

Ownership (mirrors `schema/models.py` + `eval/fields.py`):
- **Structural (re-imposed from template):** the deck identity/length, the
  `design_system` fonts/colors, and the per-slide structural block.
- **Enrichment (kept from the VLM):** all deck-/slide-/element-level semantic
  fields, `design_system.grid` and `recurring_elements` (hand-labeled), and
  `provenance`.
"""

from __future__ import annotations

import copy
import sys
from typing import Any

# Deck-level fields Pipeline A owns.
_DECK_STRUCTURAL = ("source_filename", "source_format", "slide_count", "deck_length")

# design_system sub-fields Pipeline A owns. `grid` and `recurring_elements` are
# deliberately excluded — those are hand-labeled / VLM enrichment.
_DESIGN_SYSTEM_STRUCTURAL = (
    "title_style",
    "body_style",
    "color_palette",
    "default_text_alignment",
)

# Per-slide fields Pipeline A owns (paired by `index`).
_SLIDE_STRUCTURAL = (
    "index",
    "title_text",
    "title_position",
    "image_count",
    "has_chart",
    "has_table",
    "density",
    "render_path",
    "thumbnail_path",
)


def merge_structural(vlm: dict[str, Any], template: dict[str, Any]) -> dict[str, Any]:
    """Return a record with the VLM's enrichment but template's structural fields.

    `vlm` and `template` are raw dicts (no `_legend`). Slides are paired by `index`;
    a slide present in `vlm` but not in `template` keeps its own structural fields
    (with a warning), and vice-versa.
    """
    out = copy.deepcopy(vlm)

    for key in _DECK_STRUCTURAL:
        if key in template:
            out[key] = copy.deepcopy(template[key])

    tmpl_ds = template.get("design_system") or {}
    if tmpl_ds:
        out_ds = out.get("design_system")
        if not isinstance(out_ds, dict):
            out_ds = {}
            out["design_system"] = out_ds
        for key in _DESIGN_SYSTEM_STRUCTURAL:
            if key in tmpl_ds:
                out_ds[key] = copy.deepcopy(tmpl_ds[key])

    tmpl_slides = {s.get("index"): s for s in template.get("slides", [])}
    vlm_indices = set()
    for slide in out.get("slides", []):
        idx = slide.get("index")
        vlm_indices.add(idx)
        tmpl_slide = tmpl_slides.get(idx)
        if tmpl_slide is None:
            print(
                f"# merge: slide index {idx} not in template — keeping its structural fields as-is",
                file=sys.stderr,
            )
            continue
        for key in _SLIDE_STRUCTURAL:
            if key in tmpl_slide:
                slide[key] = copy.deepcopy(tmpl_slide[key])

    missing_in_vlm = [i for i in tmpl_slides if i not in vlm_indices]
    if missing_in_vlm:
        print(
            f"# merge: template slide indices {sorted(missing_in_vlm)} have no VLM "
            "counterpart — not added (enrichment would be empty)",
            file=sys.stderr,
        )

    return out
