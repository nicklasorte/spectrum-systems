"""Draft / verify harness pattern.

Two-pass deterministic transcript -> FAQ pipeline:

1. **Draft pass.** Walk the transcript and pair every user question
   (text ending in ``?``) with the next assistant turn. Identical to
   the baseline harness's first pass.
2. **Verify pass.** Drop any draft pair whose answer is empty, whose
   answer text is identical to the question, or whose answer is the
   exact string ``"unknown"`` (case-insensitive). Verification is a
   structural check — it does not consult the eval set or any
   external resource.

The pattern is callable as ``run(transcript)`` and produces a
schema-valid ``hop_harness_faq_output`` artifact. It NEVER calls the
evaluator, the experience store, or reads raw eval files.

Used by candidates that want a deterministic refusal for
low-confidence answers without baking in any eval-derived knowledge.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

from spectrum_systems.modules.hop.artifacts import finalize_artifact, make_trace

PATTERN_ID = "pattern_draft_verify_v1"
HARNESS_TYPE = "transcript_to_faq"
DECLARED_METHODS = ("run",)

_LOW_CONFIDENCE_TOKENS: frozenset[str] = frozenset(
    {"unknown", "n/a", "i don't know", "i do not know"}
)


def _strip(text: str) -> str:
    return (text or "").strip()


def _is_low_confidence(answer: str) -> bool:
    normalized = answer.strip().lower().rstrip(".!")
    return normalized in _LOW_CONFIDENCE_TOKENS


def _draft_pass(turns: list[Any]) -> list[dict[str, Any]]:
    drafts: list[dict[str, Any]] = []
    for idx, turn in enumerate(turns):
        if not isinstance(turn, dict):
            continue
        if turn.get("speaker") != "user":
            continue
        question = _strip(turn.get("text", ""))
        if not question.endswith("?"):
            continue
        answer_idx: int | None = None
        for j in range(idx + 1, len(turns)):
            nxt = turns[j]
            if isinstance(nxt, dict) and nxt.get("speaker") == "assistant":
                answer_idx = j
                break
        if answer_idx is None:
            continue
        answer = _strip(turns[answer_idx].get("text", ""))
        drafts.append(
            {
                "question": question,
                "answer": answer,
                "source_turn_indices": sorted({idx, answer_idx}),
            }
        )
    return drafts


def _verify_pass(drafts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    verified: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for draft in drafts:
        question = draft["question"]
        answer = draft["answer"]
        if not answer:
            continue
        if answer.strip() == question.strip():
            continue
        if _is_low_confidence(answer):
            continue
        key = (question, answer)
        if key in seen:
            continue
        seen.add(key)
        verified.append(draft)
    return verified


def run(transcript: Mapping[str, Any], *, trace_id: str = "hop_pattern_draft_verify") -> dict[str, Any]:
    """Execute the draft/verify pattern on a transcript.

    Conforms to ``hop_harness_faq_output.schema.json``.
    """
    if not isinstance(transcript, dict):
        raise TypeError("draft_verify_invalid_transcript:not_dict")
    transcript_id = transcript.get("transcript_id")
    turns = transcript.get("turns")
    if not isinstance(transcript_id, str) or not transcript_id:
        raise ValueError("draft_verify_invalid_transcript:transcript_id")
    if not isinstance(turns, list):
        raise ValueError("draft_verify_invalid_transcript:turns_not_list")

    drafts = _draft_pass(turns)
    items = _verify_pass(drafts)

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
