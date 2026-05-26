"""Provenance + record assembly shared by the API tagger and the paste harness.

`enrich` (API path) and the `paste` harness (Web-UI path) both produce a tagged
record from the same three inputs — the VLM's raw JSON, the Pipeline A template,
and the resolved `PromptArtifact` — and both must stamp identical provenance fields
so downstream scoring/validation treats them the same. Lifting these helpers out
of `cli.py` gives both call sites one source of truth (no train/serve skew).
"""

from __future__ import annotations

from typing import Any

from slide_tagger.merge import merge_structural

# Core enrichment fields whose absence after merge counts as low-confidence —
# mirrors the canonical set the API tagger has always watched.
DECK_ENRICHMENT_FIELDS = (
    "client_industry", "client_sub_industry", "client_type", "engagement_stage",
    "content_area", "audience_level", "deliverable_format", "geography",
    "confidentiality_tier", "inferred_publisher", "deck_summary_one_sentence",
)
# Core per-slide fields (mirrors the completeness check in `validate`).
SLIDE_ENRICHMENT_FIELDS = (
    "slide_purpose", "message_type", "main_message", "dominant_visual_element",
)


def is_filled(value: object) -> bool:
    """A field counts as filled if it's a non-empty value (str/enum/list/dict)."""
    if value is None:
        return False
    if isinstance(value, (str, list, dict)):
        return len(value) > 0
    return True


def change_field(change: str) -> str | None:
    """Field path out of a `sanitize_enums` change string, e.g.
    "client_industry='X'→null" → "client_industry"; "slide3.slot_types_present
    dropped [...]" → "slide3.slot_types_present"."""
    head = change.split("=", 1)[0].split(" dropped", 1)[0].strip()
    return head or None


def unfilled_enrichment_fields(deck: dict) -> set[str]:
    """Core enrichment fields still empty after merge (deck + per-slide)."""
    out = {f for f in DECK_ENRICHMENT_FIELDS if not is_filled(deck.get(f))}
    for s in deck.get("slides", []):
        for f in SLIDE_ENRICHMENT_FIELDS:
            if not is_filled(s.get(f)):
                out.add(f"slide{s.get('index')}.{f}")
    return out


def filled_enrichment_fields(deck: dict) -> list[str]:
    """Enrichment field names the model actually populated (for provenance)."""
    out = [f for f in DECK_ENRICHMENT_FIELDS if is_filled(deck.get(f))]
    slide_fields = {
        f for s in deck.get("slides", []) for f in SLIDE_ENRICHMENT_FIELDS if is_filled(s.get(f))
    }
    return out + [f"slides[].{f}" for f in sorted(slide_fields)]


def build_enriched_record(
    enriched: dict,
    template_core: dict,
    sanitizer_changes: list[str],
    artifact,  # PromptArtifact (avoid hard import to keep this module light)
    model: str,
    tagged_by: str | None = None,
    extra_provenance: dict[str, Any] | None = None,
) -> dict:
    """Re-impose Pipeline A structural fields, compute a confidence signal, and
    stamp provenance. Returns the (not-yet-validated) record dict. Pure — no I/O.

    `extra_provenance` lets callers (e.g. the paste harness) add their own
    bookkeeping fields (variant name, run index) without breaking the contract
    `enrich` relies on.
    """
    enriched.pop("_legend", None)
    merged = merge_structural(enriched, template_core)

    flagged = {f for c in sanitizer_changes if (f := change_field(c))}  # invented enums
    flagged |= unfilled_enrichment_fields(merged)  # left blank
    low_conf = sorted(flagged)

    notes = (
        f"{len(sanitizer_changes)} enum(s) nulled by sanitizer; "
        f"{len(low_conf)} field(s) flagged for human review."
    )
    prov = merged.get("provenance") or {}
    prov.update(
        {
            "tagged_by": tagged_by or f"auto:{model}",
            "input_json_source": "automated structural extraction",
            "fields_filled_by_ai": filled_enrichment_fields(merged),
            "confidence_notes": notes,
            "prompt_version": artifact.version,
            "enriched_by_model": model,
            "low_confidence_fields": low_conf,
        }
    )
    if extra_provenance:
        prov.update(extra_provenance)
    merged["provenance"] = prov
    return merged
