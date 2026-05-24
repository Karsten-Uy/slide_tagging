"""Automated Pipeline B: call the Claude API to enrich a structural template.

Mirrors the manual claude.ai flow (paste prompt + input.json + deck PDF) so the
same enrichment prompt can be run many times per deck — which is what lets us
average out the large run-to-run variance that single manual runs can't measure.

Design:
- The prompt body ([docs/deck_tagging_prompt.md] "## The Prompt") is the **system**
  prompt — stable across every deck and run, so it caches globally.
- Each deck's source PDF is uploaded **once** via the Files API and referenced by
  `file_id` across all N runs (no re-upload).
- The PDF + the template JSON are cached per deck, so runs 2..N of a deck are a
  full cache hit on the whole prefix.
- The model returns JSON as text; thinking goes to separate thinking blocks. We
  concatenate text blocks, strip any stray ``` fence / `<thinking>` wrapper, and
  parse. `sanitize_enums` nulls any out-of-vocabulary enum value so a single bad
  value can't make the whole record unscorable (it scores as wrong, honestly).

`anthropic` is imported lazily so the rest of the package works without it.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from slide_tagger.schema import enums as E

# --- enum sanitation (shared by the bench runner; also used after manual runs) -

_DECK_ENUM = {
    "client_industry": E.ClientIndustry,
    "client_type": E.ClientType,
    "engagement_stage": E.EngagementStage,
    "audience_level": E.AudienceLevel,
    "deliverable_format": E.DeliverableFormat,
    "geography": E.Geography,
    "confidentiality_tier": E.ConfidentialityTier,
}
_SLIDE_ENUM = {
    "slide_purpose": E.SlidePurpose,
    "message_type": E.MessageType,
    "audience_level_slide": E.AudienceLevelSlide,
    "slide_position_role": E.SlidePositionRole,
    "dominant_visual_element": E.DominantVisualElement,
    "chart_type": E.ChartType,
    "placeholder_compliance": E.PlaceholderCompliance,
    "reusability_score_qualitative": E.ReusabilityScore,
    "tier_match_difficulty": E.TierMatchDifficulty,
}
_LIST_ENUM = {"content_area": E.ContentArea, "slot_types_present": E.SlotType}


def _allowed(enum_cls) -> set[str]:
    return {e.value for e in enum_cls}


def sanitize_enums(deck: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Null any out-of-vocabulary enum value and drop invalid enum-list members.

    Returns the (mutated) dict and a list of human-readable changes. A VLM that
    invents an enum value would otherwise make the whole record fail to load; this
    converts the invalid value to "no answer", which the scorer counts as wrong.
    """
    changes: list[str] = []
    for key, enum_cls in _DECK_ENUM.items():
        v = deck.get(key)
        if v is not None and v not in _allowed(enum_cls):
            changes.append(f"{key}={v!r}→null")
            deck[key] = None
    if isinstance(deck.get("content_area"), list):
        ok = [v for v in deck["content_area"] if v in _allowed(E.ContentArea)]
        if len(ok) != len(deck["content_area"]):
            dropped = [v for v in deck["content_area"] if v not in _allowed(E.ContentArea)]
            changes.append(f"content_area dropped {dropped}")
            deck["content_area"] = ok
    for s in deck.get("slides", []):
        idx = s.get("index")
        for key, enum_cls in _SLIDE_ENUM.items():
            v = s.get(key)
            if v is not None and v not in _allowed(enum_cls):
                changes.append(f"slide{idx}.{key}={v!r}→null")
                s[key] = None
        if isinstance(s.get("slot_types_present"), list):
            ok = [v for v in s["slot_types_present"] if v in _allowed(E.SlotType)]
            if len(ok) != len(s["slot_types_present"]):
                dropped = [v for v in s["slot_types_present"] if v not in _allowed(E.SlotType)]
                changes.append(f"slide{idx}.slot_types_present dropped {dropped}")
                s["slot_types_present"] = ok
    return deck, changes


# --- prompt + response plumbing --------------------------------------------------


def prompt_body(md_path: Path) -> str:
    """Extract the enrichment prompt body from docs/deck_tagging_prompt.md
    (everything between the "## The Prompt" and "## Notes on using this prompt"
    headers), so the canonical prompt file is the single source of truth."""
    text = md_path.read_text(encoding="utf-8")
    start = text.index("## The Prompt") + len("## The Prompt")
    end = text.index("## Notes on using this prompt at scale")
    body = text[start:end].strip().lstrip("-\n ").strip()
    if body.endswith("---"):
        body = body[:-3].rstrip()
    return body


def extract_json(text: str) -> dict[str, Any]:
    """Pull the JSON object out of a model text response, tolerating a ```json
    fence, a leading `<thinking>...</thinking>` wrapper, or surrounding prose."""
    text = re.sub(r"<thinking>.*?</thinking>", "", text, flags=re.DOTALL).strip()
    if text.startswith("```"):
        lines = text.splitlines()[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    first, last = text.find("{"), text.rfind("}")
    if first == -1 or last == -1 or last < first:
        raise ValueError("no JSON object found in model response")
    return json.loads(text[first : last + 1])


# --- API calls (lazy anthropic import) ------------------------------------------


def upload_pdf(client, pdf_path: Path) -> str:
    """Upload a deck PDF once; the returned file_id is reused across all runs."""
    uploaded = client.beta.files.upload(
        file=(pdf_path.name, open(pdf_path, "rb"), "application/pdf"),
    )
    return uploaded.id


def enrich_once(
    client,
    *,
    system: str,
    template: dict[str, Any],
    file_id: str,
    model: str,
    effort: str = "high",
    max_tokens: int = 64000,
) -> dict[str, Any]:
    """Run the enrichment prompt once and return the parsed (enum-sanitized) dict.

    The system prompt caches globally; the PDF + template cache per deck, so the
    2nd..Nth run of a deck is a full prefix cache hit.
    """
    template_json = json.dumps(template, ensure_ascii=False, sort_keys=True)
    with client.beta.messages.stream(
        model=model,
        max_tokens=max_tokens,
        betas=["files-api-2025-04-14"],
        thinking={"type": "adaptive"},
        output_config={"effort": effort},
        system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "document", "source": {"type": "file", "file_id": file_id}},
                    {
                        "type": "text",
                        "text": (
                            "Here is the partial structural JSON (input.json) to enrich. "
                            "The source deck is the attached PDF. Enrich every null field per "
                            "your instructions and return ONLY the resulting JSON:\n\n"
                            f"```json\n{template_json}\n```"
                        ),
                        "cache_control": {"type": "ephemeral"},
                    },
                ],
            }
        ],
    ) as stream:
        msg = stream.get_final_message()

    text = "".join(b.text for b in msg.content if b.type == "text")
    deck = extract_json(text)
    deck, _ = sanitize_enums(deck)
    return deck
