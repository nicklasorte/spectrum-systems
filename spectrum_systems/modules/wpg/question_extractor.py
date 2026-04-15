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
    segments = _segments(transcript_artifact)
    questions: List[Dict[str, Any]] = []
    for idx, seg in enumerate(segments, start=1):
        text = str(seg.get("text", "")).strip()
        if "?" not in text:
            continue
        questions.append(
            {
                "question_id": f"Q{idx:03d}",
                "question": text,
                "speaker": seg.get("speaker", "unknown"),
                "segment_ref": seg.get("segment_id", f"seg-{idx}"),
                "agency": seg.get("agency", "unknown"),
            }
        )

    eval_pack = make_eval_artifacts(
        "question_extraction",
        [
            {
                "description": "question quality includes question marks",
                "passed": all("?" in q["question"] for q in questions),
            },
            {
                "description": "non-empty output",
                "passed": len(questions) > 0,
                "failure_mode": "no_content",
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
        "provenance": stage_provenance("question_extraction", ctx, ["transcript"]),
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
