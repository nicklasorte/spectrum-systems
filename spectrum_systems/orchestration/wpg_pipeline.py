from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from spectrum_systems.modules.wpg import (
    StageContext,
    WPGError,
    assemble_working_paper,
    build_faq,
    cluster_faqs,
    extract_questions,
    format_faq_for_report,
    write_sections,
)
from spectrum_systems.modules.wpg.common import ensure_contract, normalize_transcript_payload, stable_hash


REQUIRED_ENFORCEMENT = {"ALLOW": "proceed", "WARN": "annotate", "BLOCK": "trigger_repair", "FREEZE": "halt"}


def _assert_stage_control(name: str, artifact: Dict[str, Any]) -> None:
    control = artifact.get("evaluation_refs", {}).get("control_decision")
    if not control:
        raise WPGError(f"missing control_decision on stage artifact: {name}")
    decision = control.get("decision")
    if decision not in REQUIRED_ENFORCEMENT:
        raise WPGError(f"invalid control decision on {name}: {decision}")
    enforcement = control.get("enforcement", {}).get("action")
    if REQUIRED_ENFORCEMENT[decision] != enforcement:
        raise WPGError(f"enforcement mismatch for {name}: {decision} -> {enforcement}")


def _build_phase_a_assurance_artifacts(
    *,
    faq_bundle: Dict[str, Any],
    sections: Dict[str, Any],
    working_paper: Dict[str, Any],
    trace_id: str,
) -> Dict[str, Any]:
    conflict_rows = faq_bundle["faq_conflict_artifact"]["outputs"].get("conflicts", [])
    confidence_rows = faq_bundle["faq_confidence_artifact"]["outputs"].get("confidence_rows", [])
    unknown_count = sum(1 for row in confidence_rows if row.get("unknown"))

    grounding_eval = ensure_contract(
        {
            "artifact_type": "wpg_grounding_eval_case",
            "schema_version": "1.0.0",
            "trace_id": trace_id,
            "outputs": {
                "faq_grounding_failures": sum(1 for row in confidence_rows if not row.get("grounded", False) and not row.get("unknown", False)),
                "supported_claim_ratio": round(
                    sum(1 for row in confidence_rows if row.get("grounded", False)) / max(len(confidence_rows), 1), 3
                ),
            },
        },
        "wpg_grounding_eval_case",
    )

    contradiction_propagation = ensure_contract(
        {
            "artifact_type": "wpg_contradiction_propagation_record",
            "schema_version": "1.0.0",
            "trace_id": trace_id,
            "outputs": {
                "conflict_count": len(conflict_rows),
                "faq_conflict_ids": [f"conflict-{i+1:02d}" for i in range(len(conflict_rows))],
                "section_conflict_annotation": len(working_paper["outputs"].get("conflicts", [])),
                "paper_conflict_annotation": len(working_paper["outputs"].get("conflicts", [])),
            },
        },
        "wpg_contradiction_propagation_record",
    )

    uncertainty_control = ensure_contract(
        {
            "artifact_type": "wpg_uncertainty_control_record",
            "schema_version": "1.0.0",
            "trace_id": trace_id,
            "outputs": {
                "unknown_count": unknown_count,
                "low_confidence_count": sum(1 for row in confidence_rows if row.get("confidence", 0.0) < 0.6),
                "max_confidence": max((row.get("confidence", 0.0) for row in confidence_rows), default=0.0),
                "narrative_warning_present": "Unknowns requiring follow-up:" in working_paper["outputs"].get("content", ""),
            },
        },
        "wpg_uncertainty_control_record",
    )

    chronology = [s.get("chronology", {}) for s in sections["outputs"].get("sections", [])]
    narrative_integrity = ensure_contract(
        {
            "artifact_type": "narrative_integrity_record",
            "schema_version": "1.0.0",
            "trace_id": trace_id,
            "outputs": {
                "section_count": len(sections["outputs"].get("sections", [])),
                "chronology_justifications": [c.get("justification", "") for c in chronology],
                "synthetic_ordering_rationale_present": all(bool(c.get("justification")) for c in chronology),
            },
        },
        "narrative_integrity_record",
    )

    return {
        "wpg_grounding_eval_case": grounding_eval,
        "wpg_contradiction_propagation_record": contradiction_propagation,
        "wpg_uncertainty_control_record": uncertainty_control,
        "narrative_integrity_record": narrative_integrity,
    }


def run_wpg_pipeline(
    transcript_payload: Dict[str, Any],
    *,
    run_id: str,
    trace_id: str,
    mode: str = "working_paper",
    prior_working_paper: Dict[str, Any] | None = None,
    resolved_comments: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    ctx = StageContext(run_id=run_id, trace_id=trace_id)

    transcript_artifact = ensure_contract(normalize_transcript_payload(transcript_payload, trace_id=trace_id), "transcript_artifact")

    question_set = extract_questions(transcript_artifact, ctx)
    faq_bundle = build_faq(question_set, transcript_artifact, ctx)
    faq_report = format_faq_for_report(faq_bundle["faq_artifact"], ctx, mode=mode)
    cluster_bundle = cluster_faqs(faq_report, ctx)
    sections = write_sections(cluster_bundle["faq_cluster_artifact"], ctx)
    assembly = assemble_working_paper(
        sections,
        cluster_bundle["unknowns_artifact"],
        faq_bundle["faq_conflict_artifact"],
        resolved_comments or {"resolved_comments": []},
        prior_working_paper,
        ctx,
        mode,
    )
    assurance = _build_phase_a_assurance_artifacts(
        faq_bundle=faq_bundle,
        sections=sections,
        working_paper=assembly["working_paper_artifact"],
        trace_id=trace_id,
    )

    artifact_chain = {
        "transcript_artifact": transcript_artifact,
        "question_set_artifact": question_set,
        **faq_bundle,
        "faq_report_artifact": faq_report,
        **cluster_bundle,
        "working_section_artifact": sections,
        **assembly,
        **assurance,
    }
    failure_capture = []
    repair_suggestions = []
    for name, artifact in artifact_chain.items():
        if "evaluation_refs" in artifact:
            _assert_stage_control(name, artifact)
            control = artifact.get("evaluation_refs", {}).get("control_decision") or {}
            decision = control.get("decision")
            if decision in {"BLOCK", "FREEZE"}:
                failure_capture.append({"artifact": name, "decision": decision, "reasons": control.get("reasons", [])})
                repair_suggestions.append({"artifact": name, "suggestion": "increase grounding evidence and resolve contradictions"})

    replay_signature = stable_hash(artifact_chain)
    return {
        "artifact_type": "wpg_pipeline_bundle",
        "run_id": run_id,
        "trace_id": trace_id,
        "mode": mode,
        "artifact_chain": artifact_chain,
        "failure_artifacts": failure_capture,
        "repair_suggestions": repair_suggestions,
        "replay": {
            "policy_version": ctx.policy_version,
            "eval_version": ctx.eval_version,
            "trace_linkage": trace_id,
            "signature": replay_signature,
        },
    }


def run_wpg_pipeline_from_file(input_path: Path, output_dir: Path, mode: str = "working_paper") -> Dict[str, Any]:
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    run_id = str(payload.get("run_id", "wpg-run-001"))
    trace_id = str(payload.get("trace_id", "wpg-trace-001"))

    if payload.get("artifact_type") == "transcript_artifact":
        transcript = payload.get("outputs", {})
    else:
        transcript = payload.get("transcript", payload)

    prior = payload.get("prior_working_paper_artifact")
    resolved_comments = payload.get("resolved_comments", {"resolved_comments": []})

    bundle = run_wpg_pipeline(
        transcript,
        run_id=run_id,
        trace_id=trace_id,
        mode=mode,
        prior_working_paper=prior,
        resolved_comments=resolved_comments,
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    for name, artifact in bundle["artifact_chain"].items():
        (output_dir / f"{name}.json").write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    (output_dir / "wpg_pipeline_bundle.json").write_text(json.dumps(bundle, indent=2), encoding="utf-8")
    return bundle
