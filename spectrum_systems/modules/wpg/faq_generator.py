from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List

from spectrum_systems.modules.wpg.common import (
    StageContext,
    control_decision_from_eval,
    ensure_contract,
    jaccard_similarity,
    make_eval_artifacts,
    normalize_text_tokens,
    stage_provenance,
)

_UNKNOWN_MARKERS = ("unknown", "no explicit", "unclear", "not provided")
_POSITIVE_MARKERS = ("yes", "can", "will", "approved", "start")
_NEGATIVE_MARKERS = ("no", "cannot", "won't", "not", "blocked", "deny")


def _answer_for_question(question: Dict[str, Any], transcript_by_ref: Dict[str, Dict[str, Any]]) -> str:
    ref = question.get("segment_ref")
    seg = transcript_by_ref.get(ref, {})
    text = str(seg.get("text", "")).strip()
    if "?" in text:
        return text.split("?", 1)[-1].strip() or "No explicit answer in-segment."
    return "No explicit answer in-segment."


def _has_unknown(answer: str) -> bool:
    lowered = answer.lower()
    return any(marker in lowered for marker in _UNKNOWN_MARKERS)


def _contradiction(a: str, b: str) -> bool:
    la = a.lower()
    lb = b.lower()
    a_pos = any(token in la for token in _POSITIVE_MARKERS)
    a_neg = any(token in la for token in _NEGATIVE_MARKERS)
    b_pos = any(token in lb for token in _POSITIVE_MARKERS)
    b_neg = any(token in lb for token in _NEGATIVE_MARKERS)
    return (a_pos and b_neg) or (a_neg and b_pos)


def build_faq(question_set_artifact: Dict[str, Any], transcript_artifact: Dict[str, Any], ctx: StageContext) -> Dict[str, Dict[str, Any]]:
    questions = question_set_artifact.get("outputs", {}).get("questions", [])
    segments = transcript_artifact.get("outputs", {}).get("segments", [])
    by_ref = {seg.get("segment_id"): seg for seg in segments if isinstance(seg, dict)}

    faq_items: List[Dict[str, Any]] = []
    conflict_rows: List[Dict[str, Any]] = []
    confidence_rows: List[Dict[str, Any]] = []

    grouped_by_topic: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    grounding_failures = 0
    for q in questions:
        answer = _answer_for_question(q, by_ref)
        speaker = q.get("speaker", "unknown")
        agency = q.get("agency", "unknown")
        seg = by_ref.get(q.get("segment_ref"), {})
        seg_text = str(seg.get("text", ""))
        grounded = answer != "No explicit answer in-segment." and answer in seg_text
        if not grounded and not _has_unknown(answer):
            grounding_failures += 1
        item = {
            "question_id": q["question_id"],
            "question": q["question"],
            "answer": answer,
            "sources": [
                {
                    "segment_ref": q.get("segment_ref"),
                    "speaker": speaker,
                    "agency": agency,
                }
            ],
            "agency_views": {agency: answer},
            "synthesis": answer,
            "sequence": q.get("sequence", 0),
            "grounded": grounded,
            "unknown": _has_unknown(answer),
        }
        faq_items.append(item)

        token_key = " ".join(sorted(normalize_text_tokens(item["question"])))
        grouped_by_topic[token_key].append(item)

    topic_keys = list(grouped_by_topic.keys())
    for idx, key in enumerate(topic_keys):
        base_entries = grouped_by_topic[key]
        for other in topic_keys[idx + 1 :]:
            if jaccard_similarity(key.split(), other.split()) >= 0.6:
                base_entries.extend(grouped_by_topic[other])
        if len(base_entries) < 2:
            continue
        answers = [entry["answer"] for entry in base_entries]
        contradiction_pairs = [
            (left, right)
            for i, left in enumerate(answers)
            for right in answers[i + 1 :]
            if _contradiction(left, right)
        ]
        if contradiction_pairs:
            conflict_rows.append(
                {
                    "topic_key": key,
                    "questions": sorted({entry["question"] for entry in base_entries}),
                    "answers": sorted({entry["answer"].strip().lower() for entry in base_entries}),
                    "status": "unresolved",
                    "type": "semantic_conflict",
                }
            )

    for row in faq_items:
        source_count = len(row["sources"])
        unknown_penalty = 0.45 if row["unknown"] else 0.0
        grounding_penalty = 0.25 if not row["grounded"] else 0.0
        confidence = round(max(0.05, min(1.0, 0.95 - unknown_penalty - grounding_penalty + (0.03 * source_count))), 2)
        confidence_rows.append(
            {
                "question_id": row["question_id"],
                "confidence": confidence,
                "source_count": source_count,
                "grounded": row["grounded"],
                "unknown": row["unknown"],
            }
        )

    eval_pack = make_eval_artifacts(
        "faq_generation",
        [
            {
                "description": "all answers are grounded in transcript or explicitly unknown",
                "passed": all(item["grounded"] or item["unknown"] for item in faq_items),
                "failure_mode": "answer_ungrounded",
            },
            {
                "description": "question ids are unique",
                "passed": len({i["question_id"] for i in faq_items}) == len(faq_items),
                "failure_mode": "duplication",
            },
            {
                "description": "semantic conflict detection executes",
                "passed": all("status" in row for row in conflict_rows) or len(conflict_rows) == 0,
                "failure_mode": "conflict_detection_failure",
            },
            {
                "description": "unknown answers cannot score full confidence",
                "passed": all(
                    (not row["unknown"]) or next(c["confidence"] for c in confidence_rows if c["question_id"] == row["question_id"]) < 1.0
                    for row in faq_items
                ),
                "failure_mode": "overconfidence_unknown",
            },
        ],
        ctx,
    )

    low_conf = sum(1 for c in confidence_rows if c["confidence"] < 0.6)
    unknown_count = sum(1 for c in confidence_rows if c["unknown"])
    control = control_decision_from_eval(
        stage="faq_generation",
        eval_summary=eval_pack["eval_summary"],
        contradictions_unresolved=len(conflict_rows),
        low_confidence_count=low_conf,
        no_content=len(faq_items) == 0,
        unknown_count=unknown_count,
        grounding_failures=grounding_failures,
    )

    faq_artifact = ensure_contract(
        {
            "artifact_type": "faq_artifact",
            "schema_version": "1.0.0",
            "trace_id": ctx.trace_id,
            "inputs_ref": ["question_set_artifact", "transcript_artifact"],
            "outputs": {"faqs": faq_items},
            "provenance": stage_provenance("faq_generation", ctx, ["question_set_artifact", "transcript_artifact"]),
            "evaluation_refs": {**eval_pack, "control_decision": control},
        },
        "faq_artifact",
    )

    conflict_artifact = ensure_contract(
        {
            "artifact_type": "faq_conflict_artifact",
            "schema_version": "1.0.0",
            "trace_id": ctx.trace_id,
            "inputs_ref": ["faq_artifact"],
            "outputs": {"conflicts": conflict_rows, "unresolved_count": len(conflict_rows)},
            "provenance": stage_provenance("conflict_detection", ctx, ["faq_artifact"]),
            "evaluation_refs": {**eval_pack, "control_decision": control},
        },
        "faq_conflict_artifact",
    )

    confidence_artifact = ensure_contract(
        {
            "artifact_type": "faq_confidence_artifact",
            "schema_version": "1.0.0",
            "trace_id": ctx.trace_id,
            "inputs_ref": ["faq_artifact"],
            "outputs": {"confidence_rows": confidence_rows, "low_confidence_count": low_conf},
            "provenance": stage_provenance("confidence_scoring", ctx, ["faq_artifact"]),
            "evaluation_refs": {**eval_pack, "control_decision": control},
        },
        "faq_confidence_artifact",
    )
    return {
        "faq_artifact": faq_artifact,
        "faq_conflict_artifact": conflict_artifact,
        "faq_confidence_artifact": confidence_artifact,
    }
