"""Keyword-based baseline harness for the transcript -> extraction workflow.

Intentionally imperfect (HOP-006 design §9):
- Single-turn scanning only; no multi-turn reasoning.
- Hard-coded keyword sets; first match per keyword group per turn.
- confidence_signal always medium; ambiguity_signal always none.
- evidence_refs from the matched keyword's character offset.

Expected failure surface (by construction):
- All ambiguous_attribution, competing_actions, paraphrased_duplicate cases.
- All negation_attempted cases (emits a risk item for negated language).
- All distractor_statement cases where authority-shaped substrings overlap the
  keyword set.

The output conforms to contracts/schemas/hop/harness_extraction_signal.schema.json.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any, Mapping

from spectrum_systems.modules.hop.artifacts import finalize_artifact, make_trace

CANDIDATE_ID = "extraction_baseline_v1"
HARNESS_TYPE = "transcript_to_extraction"
DECLARED_METHODS = ("run",)

_RISK_KEYWORDS = ("risk", "concern", "danger")
_ACTION_KEYWORDS = ("we will", "i'll", "let's", "todo")
_ASSUMPTION_KEYWORDS = ("assume", "assuming")
_ISSUE_KEYWORDS = ("issue", "problem", "bug", "broken")

_ALL_KEYWORDS = (
    *_RISK_KEYWORDS,
    *_ACTION_KEYWORDS,
    *_ASSUMPTION_KEYWORDS,
    *_ISSUE_KEYWORDS,
)


def _find_first_keyword(text: str, keywords: tuple[str, ...]) -> tuple[int, int] | None:
    lower = text.lower()
    for kw in keywords:
        idx = lower.find(kw)
        if idx != -1:
            return idx, idx + len(kw)
    return None


def _has_any_keyword(text: str) -> bool:
    lower = text.lower()
    return any(kw in lower for kw in _ALL_KEYWORDS)


def _make_item_id(turn_index: int, category: str, char_start: int) -> str:
    raw = f"{turn_index}:{category}:{char_start}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return f"hop_extract_{digest}"


def _make_extraction_item(
    *,
    category: str,
    description: str,
    turn_index: int,
    char_start: int,
    char_end: int,
) -> dict[str, Any]:
    return {
        "item_id": _make_item_id(turn_index, category, char_start),
        "category": category,
        "description": description,
        "evidence_refs": [
            {"turn_index": turn_index, "char_start": char_start, "char_end": char_end}
        ],
        "source_turn_indices": [turn_index],
        "owner_text": None,
        "due_date_text": None,
        "confidence_signal": "medium",
        "ambiguity_signal": "none",
    }


def run(
    transcript: Mapping[str, Any], *, trace_id: str = "hop_extraction_baseline"
) -> dict[str, Any]:
    """Execute the keyword-based baseline harness on a transcript.

    ``transcript`` must follow the eval-case input shape::

        {"transcript_id": str, "turns": [{"speaker": "user"|"assistant", "text": str}]}
    """
    if not isinstance(transcript, dict):
        raise TypeError("extraction_baseline_invalid_transcript:not_dict")
    transcript_id = transcript.get("transcript_id")
    turns = transcript.get("turns")
    if not isinstance(transcript_id, str) or not transcript_id:
        raise ValueError("extraction_baseline_invalid_transcript:transcript_id")
    if not isinstance(turns, list):
        raise ValueError("extraction_baseline_invalid_transcript:turns_not_list")

    items: list[dict[str, Any]] = []

    for idx, turn in enumerate(turns):
        if not isinstance(turn, dict):
            continue
        text: str = turn.get("text", "") or ""
        speaker: str = turn.get("speaker", "") or ""

        match = _find_first_keyword(text, _RISK_KEYWORDS)
        if match:
            cs, ce = match
            items.append(_make_extraction_item(
                category="risk",
                description=text.strip(),
                turn_index=idx,
                char_start=cs,
                char_end=ce,
            ))

        match = _find_first_keyword(text, _ACTION_KEYWORDS)
        if match:
            cs, ce = match
            items.append(_make_extraction_item(
                category="action",
                description=text.strip(),
                turn_index=idx,
                char_start=cs,
                char_end=ce,
            ))

        match = _find_first_keyword(text, _ASSUMPTION_KEYWORDS)
        if match:
            cs, ce = match
            items.append(_make_extraction_item(
                category="assumption",
                description=text.strip(),
                turn_index=idx,
                char_start=cs,
                char_end=ce,
            ))

        match = _find_first_keyword(text, _ISSUE_KEYWORDS)
        if match:
            cs, ce = match
            items.append(_make_extraction_item(
                category="issue",
                description=text.strip(),
                turn_index=idx,
                char_start=cs,
                char_end=ce,
            ))

        # open_question: user turn ending with '?' and no assistant turn in
        # [idx+1, idx+3] carrying any keyword (deliberately weak: misses
        # answered questions whose answer contains no keywords).
        if speaker == "user" and text.strip().endswith("?"):
            has_keyword_answer = False
            for j in range(idx + 1, min(idx + 4, len(turns))):
                nxt = turns[j]
                if isinstance(nxt, dict) and nxt.get("speaker") == "assistant":
                    if _has_any_keyword(nxt.get("text", "") or ""):
                        has_keyword_answer = True
                        break
            if not has_keyword_answer:
                stripped = text.strip()
                char_start = len(stripped) - 1
                char_end = len(stripped)
                items.append(_make_extraction_item(
                    category="open_question",
                    description=stripped,
                    turn_index=idx,
                    char_start=char_start,
                    char_end=char_end,
                ))

    payload: dict[str, Any] = {
        "artifact_type": "hop_harness_extraction_signal",
        "schema_ref": "hop/harness_extraction_signal.schema.json",
        "schema_version": "1.0.0",
        "trace": make_trace(primary=trace_id),
        "advisory_only": True,
        "delegates_to": ["JSX", "EVL"],
        "transcript_id": transcript_id,
        "candidate_id": CANDIDATE_ID,
        "items": items,
        "generated_at": datetime.now(tz=timezone.utc)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z"),
    }
    finalize_artifact(payload, id_prefix="hop_extract_")
    return payload
