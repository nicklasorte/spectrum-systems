"""Deterministic baseline harness for the transcript -> FAQ golden workflow.

The baseline is intentionally simple and 100% deterministic so it can serve
as a stable reference point for HOP's frontier and as a regression baseline
for future candidates.

Rule set (in order):

1. Pair every ``user`` turn whose text ends with ``?`` (after stripping) with
   the *next* ``assistant`` turn. The ``?``-bearing line is the question; the
   following assistant line is the answer.
2. Skip user questions that have no answering assistant turn following them.
3. Collapse exact-duplicate (question, answer) pairs.
4. If the transcript is empty or yields zero pairs, the harness returns a
   FAQ artifact with an empty ``items`` list. (Rejection is the evaluator's
   job, not the harness's.)

The output conforms to ``contracts/schemas/hop/harness_faq_output.schema.json``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

from spectrum_systems.modules.hop.artifacts import finalize_artifact, make_trace

CANDIDATE_ID = "baseline_v1"
HARNESS_TYPE = "transcript_to_faq"
DECLARED_METHODS = ("run",)


def _strip(text: str) -> str:
    return (text or "").strip()


def run(transcript: Mapping[str, Any], *, trace_id: str = "hop_baseline") -> dict[str, Any]:
    """Execute the deterministic baseline harness on a transcript.

    ``transcript`` must follow the eval-case input shape::

        {"transcript_id": str, "turns": [{"speaker": "user"|"assistant", "text": str}]}
    """
    if not isinstance(transcript, dict):
        raise TypeError("baseline_harness_invalid_transcript:not_dict")
    transcript_id = transcript.get("transcript_id")
    turns = transcript.get("turns")
    if not isinstance(transcript_id, str) or not transcript_id:
        raise ValueError("baseline_harness_invalid_transcript:transcript_id")
    if not isinstance(turns, list):
        raise ValueError("baseline_harness_invalid_transcript:turns_not_list")

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
        # Find next assistant turn.
        answer_idx: int | None = None
        for j in range(idx + 1, len(turns)):
            nxt = turns[j]
            if isinstance(nxt, dict) and nxt.get("speaker") == "assistant":
                answer_idx = j
                break
        if answer_idx is None:
            continue
        answer = _strip(turns[answer_idx].get("text", ""))
        if not answer:
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
        "trace": make_trace(primary=trace_id),
        "transcript_id": transcript_id,
        "candidate_id": CANDIDATE_ID,
        "items": items,
        "generated_at": datetime.now(tz=timezone.utc)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z"),
    }
    finalize_artifact(payload, id_prefix="hop_faq_")
    return payload
