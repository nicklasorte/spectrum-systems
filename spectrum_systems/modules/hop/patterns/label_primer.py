"""Label-primer harness pattern.

Tags each user turn with a structural label (``question`` /
``statement``) and emits a Q/A pair only when:

- the user turn is labeled ``question`` (text ends with ``?``);
- the next assistant turn is labeled ``answer`` (non-empty, non-empty
  after stripping);

The labels are recorded internally and used to constrain extraction.
They are NOT written into the artifact — the schema does not allow
free-form labels — but they shape which pairs survive.

Determinism: labels are derived purely from textual structure
(trailing ``?``, non-emptiness, presence of an alphanumeric
character). No external models, no eval-set consultation, no I/O.

Used by candidates that benefit from making the user/assistant
classification explicit before the pair-extraction step.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

from spectrum_systems.modules.hop.artifacts import finalize_artifact, make_trace

PATTERN_ID = "pattern_label_primer_v1"
HARNESS_TYPE = "transcript_to_faq"
DECLARED_METHODS = ("run",)

_LABEL_QUESTION = "question"
_LABEL_STATEMENT = "statement"
_LABEL_ANSWER = "answer"
_LABEL_FILLER = "filler"


def _strip(text: str) -> str:
    return (text or "").strip()


def _has_alphanumeric(text: str) -> bool:
    return any(ch.isalnum() for ch in text)


def _label_user(turn_text: str) -> str:
    stripped = _strip(turn_text)
    if stripped.endswith("?") and _has_alphanumeric(stripped):
        return _LABEL_QUESTION
    return _LABEL_STATEMENT


def _label_assistant(turn_text: str) -> str:
    stripped = _strip(turn_text)
    if stripped and _has_alphanumeric(stripped):
        return _LABEL_ANSWER
    return _LABEL_FILLER


def _label_turns(turns: list[Any]) -> list[tuple[int, str, str, str]]:
    """Return ``(index, speaker, label, text)`` rows for each valid turn."""
    rows: list[tuple[int, str, str, str]] = []
    for idx, turn in enumerate(turns):
        if not isinstance(turn, dict):
            continue
        speaker = turn.get("speaker")
        text = turn.get("text", "")
        if speaker == "user":
            rows.append((idx, "user", _label_user(text), _strip(text)))
        elif speaker == "assistant":
            rows.append((idx, "assistant", _label_assistant(text), _strip(text)))
    return rows


def run(transcript: Mapping[str, Any], *, trace_id: str = "hop_pattern_label_primer") -> dict[str, Any]:
    """Execute the label-primer pattern on a transcript.

    Conforms to ``hop_harness_faq_output.schema.json``.
    """
    if not isinstance(transcript, dict):
        raise TypeError("label_primer_invalid_transcript:not_dict")
    transcript_id = transcript.get("transcript_id")
    turns = transcript.get("turns")
    if not isinstance(transcript_id, str) or not transcript_id:
        raise ValueError("label_primer_invalid_transcript:transcript_id")
    if not isinstance(turns, list):
        raise ValueError("label_primer_invalid_transcript:turns_not_list")

    rows = _label_turns(turns)
    items: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for cursor, (idx, speaker, label, text) in enumerate(rows):
        if speaker != "user" or label != _LABEL_QUESTION:
            continue
        # Find the next assistant turn that the labeler classified as an answer.
        match: tuple[int, str] | None = None
        for follow in rows[cursor + 1 :]:
            f_idx, f_speaker, f_label, f_text = follow
            if f_speaker == "assistant":
                if f_label == _LABEL_ANSWER:
                    match = (f_idx, f_text)
                break  # Only consider the *next* assistant turn.
        if match is None:
            continue
        key = (text, match[1])
        if key in seen:
            continue
        seen.add(key)
        items.append(
            {
                "question": text,
                "answer": match[1],
                "source_turn_indices": sorted({idx, match[0]}),
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
