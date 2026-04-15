from __future__ import annotations

from typing import Any, Dict, List

from spectrum_systems.modules.wpg.common import (
    StageContext,
    control_decision_from_eval,
    ensure_contract,
    make_eval_artifacts,
    stage_provenance,
)


def _segments(transcript_artifact: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [seg for seg in transcript_artifact.get("outputs", {}).get("segments", []) if isinstance(seg, dict)]


def extract_questions(transcript_artifact: Dict[str, Any], ctx: StageContext) -> Dict[str, Any]:
    ensure_contract(transcript_artifact, "transcript_artifact")
    segments = _segments(transcript_artifact)
    questions: List[Dict[str, Any]] = []
    for idx, seg in enumerate(segments, start=1):
        text = str(seg.get("text", "")).strip()
        if "?" not in text:
            continue
        questions.append(
            {
                "question_id": f"Q{idx:03d}",
                "question": text.split("?", 1)[0].strip() + "?",
                "speaker": seg.get("speaker", "unknown"),
                "segment_ref": seg.get("segment_id", f"seg-{idx}"),
                "agency": seg.get("agency", "unknown"),
                "sequence": idx,
            }
        )

    eval_pack = make_eval_artifacts(
        "question_extraction",
        [
            {
                "description": "question text ends with question mark",
                "passed": all(q["question"].endswith("?") for q in questions),
                "failure_mode": "question_parse_failure",
            },
            {
                "description": "question output exists",
                "passed": len(questions) > 0,
                "failure_mode": "no_content",
            },
            {
                "description": "all segment references resolve in transcript",
                "passed": all(
                    any(seg.get("segment_id") == q.get("segment_ref") for seg in segments)
                    for q in questions
                ),
                "failure_mode": "dangling_segment_reference",
            },
        ],
        ctx,
    )
    control = control_decision_from_eval(
        stage="question_extraction",
        eval_summary=eval_pack["eval_summary"],
        no_content=len(questions) == 0,
    )

    artifact = {
        "artifact_type": "question_set_artifact",
        "schema_version": "1.0.0",
        "trace_id": ctx.trace_id,
        "inputs_ref": [transcript_artifact.get("artifact_type", "transcript")],
        "outputs": {"questions": questions},
        "provenance": stage_provenance("question_extraction", ctx, ["transcript_artifact"]),
        "evaluation_refs": {
            **eval_pack,
            "control_decision": control,
            "replay": {
                "policy_version": ctx.policy_version,
                "eval_version": ctx.eval_version,
                "trace_linkage": ctx.trace_id,
            },
        },
    }
    return ensure_contract(artifact, "question_set_artifact")
