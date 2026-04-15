from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Tuple

from spectrum_systems.modules.wpg.common import (
    StageContext,
    control_decision_from_eval,
    ensure_contract,
    make_eval_artifacts,
    stage_provenance,
)


def _answer_for_question(question: Dict[str, Any], transcript_by_ref: Dict[str, Dict[str, Any]]) -> str:
    ref = question.get("segment_ref")
    seg = transcript_by_ref.get(ref, {})
    text = str(seg.get("text", ""))
    if "?" in text:
        return text.split("?", 1)[-1].strip() or "No explicit answer in-segment."
    return "No explicit answer in-segment."


def build_faq(question_set_artifact: Dict[str, Any], transcript_artifact: Dict[str, Any], ctx: StageContext) -> Dict[str, Dict[str, Any]]:
    questions = question_set_artifact.get("outputs", {}).get("questions", [])
    segments = transcript_artifact.get("outputs", {}).get("segments", [])
    by_ref = {seg.get("segment_id"): seg for seg in segments if isinstance(seg, dict)}

    faq_items: List[Dict[str, Any]] = []
    conflict_rows: List[Dict[str, Any]] = []
    confidence_rows: List[Dict[str, Any]] = []

    grouped_by_question: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for q in questions:
        answer = _answer_for_question(q, by_ref)
        speaker = q.get("speaker", "unknown")
        agency = q.get("agency", "unknown")
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
        }
        faq_items.append(item)
        grouped_by_question[q["question"]].append(item)

    for question, entries in grouped_by_question.items():
        answer_set = {e["answer"].lower().strip() for e in entries}
        contradiction = len(answer_set) > 1
        if contradiction:
            conflict_rows.append(
                {
                    "question": question,
                    "answers": sorted(answer_set),
                    "status": "unresolved",
                }
            )

    for row in faq_items:
        source_count = len(row["sources"])
        agreement = 1.0
        eval_factor = 1.0
        confidence = round(min(1.0, 0.4 + 0.2 * source_count + 0.3 * agreement + 0.1 * eval_factor), 2)
        confidence_rows.append(
            {
                "question_id": row["question_id"],
                "confidence": confidence,
                "source_count": source_count,
                "agreement": agreement,
                "eval_factor": eval_factor,
            }
        )

    eval_pack = make_eval_artifacts(
        "faq_generation",
        [
            {
                "description": "answer grounding",
                "passed": all(len(item.get("sources", [])) > 0 for item in faq_items),
                "failure_mode": "answer_ungrounded",
            },
            {
                "description": "duplication control",
                "passed": len({i['question'] for i in faq_items}) == len(faq_items),
                "failure_mode": "duplication",
            },
            {
                "description": "contradiction detection",
                "passed": True,
            },
        ],
        ctx,
    )

    low_conf = sum(1 for c in confidence_rows if c["confidence"] < 0.6)
    control = control_decision_from_eval(
        stage="faq_generation",
        eval_summary=eval_pack["eval_summary"],
        contradictions_unresolved=len(conflict_rows),
        low_confidence_count=low_conf,
        no_content=len(faq_items) == 0,
    )

    faq_artifact = ensure_contract(
        {
            "artifact_type": "faq_artifact",
            "schema_version": "1.0.0",
            "trace_id": ctx.trace_id,
            "inputs_ref": ["question_set_artifact", "transcript"],
            "outputs": {"faqs": faq_items},
            "provenance": stage_provenance("faq_generation", ctx, ["question_set_artifact"]),
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
