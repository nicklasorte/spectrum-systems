"""Domain-router harness pattern.

Routes each user question to a deterministic *domain* based on
textual cues, then applies a domain-specific extraction strategy
before merging the per-domain outputs into a single FAQ artifact.

Domains and cues (case-insensitive match against the question text):

- ``definition``: question contains ``what is`` / ``what's`` / ``define``.
- ``howto``: question contains ``how do`` / ``how to`` / ``how can``.
- ``yes_no``: question begins with ``is`` / ``are`` / ``do`` / ``does``
  / ``can`` / ``should``.
- ``general``: catch-all for anything else.

Each domain uses the same forward-scan extractor as the baseline but
applies a domain-specific *answer guard* that rejects an answer the
extractor produced if it is structurally inconsistent with the
question's domain (e.g. a ``yes_no`` answer that contains neither
``yes`` nor ``no`` is dropped).

The router never consults the eval set, never reads a file, and never
calls into the experience store. Routing is purely textual and
deterministic.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

from spectrum_systems.modules.hop.artifacts import finalize_artifact, make_trace

PATTERN_ID = "pattern_domain_router_v1"
HARNESS_TYPE = "transcript_to_faq"
DECLARED_METHODS = ("run",)

DOMAIN_DEFINITION = "definition"
DOMAIN_HOWTO = "howto"
DOMAIN_YES_NO = "yes_no"
DOMAIN_GENERAL = "general"

_DEFINITION_CUES: tuple[str, ...] = ("what is", "what's", "define ", "definition of")
_HOWTO_CUES: tuple[str, ...] = ("how do", "how to", "how can", "how should")
_YES_NO_PREFIXES: tuple[str, ...] = (
    "is ",
    "are ",
    "do ",
    "does ",
    "did ",
    "can ",
    "could ",
    "should ",
    "would ",
    "will ",
    "has ",
    "have ",
)


def _strip(text: str) -> str:
    return (text or "").strip()


def route_question(question: str) -> str:
    """Return the routing label for ``question``."""
    normalized = question.strip().lower()
    if not normalized:
        return DOMAIN_GENERAL
    for cue in _DEFINITION_CUES:
        if cue in normalized:
            return DOMAIN_DEFINITION
    for cue in _HOWTO_CUES:
        if cue in normalized:
            return DOMAIN_HOWTO
    for prefix in _YES_NO_PREFIXES:
        if normalized.startswith(prefix):
            return DOMAIN_YES_NO
    return DOMAIN_GENERAL


def _answer_passes_guard(domain: str, answer: str) -> bool:
    text = answer.strip().lower()
    if not text:
        return False
    if domain == DOMAIN_YES_NO:
        return ("yes" in text) or ("no" in text) or text.startswith(("y", "n"))
    if domain == DOMAIN_DEFINITION:
        # Definitions need at least one word of substance.
        return any(ch.isalpha() for ch in text) and len(text) >= 3
    if domain == DOMAIN_HOWTO:
        # Howto answers need at least a few words.
        return len(text.split()) >= 2
    return any(ch.isalnum() for ch in text)


def run(transcript: Mapping[str, Any], *, trace_id: str = "hop_pattern_domain_router") -> dict[str, Any]:
    """Execute the domain-router pattern on a transcript.

    Conforms to ``hop_harness_faq_output.schema.json``.
    """
    if not isinstance(transcript, dict):
        raise TypeError("domain_router_invalid_transcript:not_dict")
    transcript_id = transcript.get("transcript_id")
    turns = transcript.get("turns")
    if not isinstance(transcript_id, str) or not transcript_id:
        raise ValueError("domain_router_invalid_transcript:transcript_id")
    if not isinstance(turns, list):
        raise ValueError("domain_router_invalid_transcript:turns_not_list")

    items: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for idx, turn in enumerate(turns):
        if not isinstance(turn, dict):
            continue
        if turn.get("speaker") != "user":
            continue
        question = _strip(turn.get("text", ""))
        if not question.endswith("?"):
            continue
        domain = route_question(question)
        answer_idx: int | None = None
        for j in range(idx + 1, len(turns)):
            nxt = turns[j]
            if isinstance(nxt, dict) and nxt.get("speaker") == "assistant":
                answer_idx = j
                break
        if answer_idx is None:
            continue
        answer = _strip(turns[answer_idx].get("text", ""))
        if not _answer_passes_guard(domain, answer):
            continue
        key = (question, answer)
        if key in seen:
            continue
        seen.add(key)
        items.append(
            {
                "question": question,
                "answer": answer,
                "source_turn_indices": sorted({idx, answer_idx}),
            }
        )

    payload: dict[str, Any] = {
        "artifact_type": "hop_harness_faq_output",
        "schema_ref": "hop/harness_faq_output.schema.json",
        "schema_version": "1.0.0",
        "trace": make_trace(primary=trace_id, related=[PATTERN_ID]),
        "transcript_id": transcript_id,
        "candidate_id": PATTERN_ID,
        "items": items,
        "generated_at": datetime.now(tz=timezone.utc)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z"),
    }
    finalize_artifact(payload, id_prefix="hop_faq_")
    return payload
