"""The single chokepoint for resolving the enrichment prompt.

Both the production tagger (`enrich`) and the tuning harness (`bench`) load the
system prompt through `resolve_prompt`, so you always run *exactly* what you tuned
— no train/serve skew. The prompt itself is a file-based artifact owned by a
separate tuning system; this module just reads it and stamps a content version.

Swapping to a non-file source later (a registry, an HTTP endpoint, a DB row) means
editing only `resolve_prompt` — its `PromptArtifact` return contract stays the same,
so neither `enrich` nor `bench` changes.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path

from slide_tagger.enrich import prompt_body

# Default location of the canonical prompt file (relative to the run cwd, which is
# the slide_tagging/ project root — matches `bench`'s --prompt default).
_DEFAULT_PROMPT = Path("docs/deck_tagging_prompt.md")
# Env var to point the resolver at a different file without touching code/flags.
_ENV_VAR = "SLIDE_TAGGER_PROMPT"


@dataclass(frozen=True)
class PromptArtifact:
    """A resolved prompt plus the metadata callers stamp into provenance."""

    text: str  # the extracted system-prompt body
    version: str  # content hash — stable identity recorded per tagged deck
    source: str  # where it came from, e.g. "file:docs/deck_tagging_prompt.md"
    model: str | None = None  # optional tuned default the source may carry (unused today)
    effort: str | None = None


def _version(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def resolve_prompt(path: Path | None = None) -> PromptArtifact:
    """Resolve the enrichment prompt to a `PromptArtifact`.

    Resolution order: explicit `path` arg → `$SLIDE_TAGGER_PROMPT` → the default
    `docs/deck_tagging_prompt.md`. Parsing reuses `enrich.prompt_body` so the body
    is identical to what's always been used. Raises `FileNotFoundError` (with the
    resolved path) if the file doesn't exist.
    """
    resolved = path or (Path(os.environ[_ENV_VAR]) if os.environ.get(_ENV_VAR) else _DEFAULT_PROMPT)
    if not resolved.exists():
        raise FileNotFoundError(
            f"Enrichment prompt not found: {resolved} "
            f"(set {_ENV_VAR}, pass --prompt, or run from the slide_tagging/ dir)."
        )
    text = prompt_body(resolved)
    return PromptArtifact(text=text, version=_version(text), source=f"file:{resolved}")
