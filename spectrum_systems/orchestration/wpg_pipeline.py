from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from spectrum_systems.modules.wpg import (
    StageContext,
    assemble_working_paper,
    build_faq,
    cluster_faqs,
    extract_questions,
    format_faq_for_report,
    write_sections,
)
from spectrum_systems.modules.wpg.common import deterministic_copy, stable_hash


REQUIRED_ENFORCEMENT = {"ALLOW": "proceed", "WARN": "annotate", "BLOCK": "trigger_repair", "FREEZE": "halt"}


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
    transcript_artifact = {
        "artifact_type": "transcript_artifact",
        "schema_version": "1.0.0",
        "trace_id": trace_id,
        "outputs": deterministic_copy(transcript_payload),
    }

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

    artifact_chain = {
        "question_set_artifact": question_set,
        **faq_bundle,
        "faq_report_artifact": faq_report,
        **cluster_bundle,
        "working_section_artifact": sections,
        **assembly,
    }
    failure_capture = []
    repair_suggestions = []
    for name, artifact in artifact_chain.items():
        control = artifact.get("evaluation_refs", {}).get("control_decision")
        if not control:
            continue
        decision = control.get("decision")
        if decision in {"BLOCK", "FREEZE"}:
            failure_capture.append({"artifact": name, "decision": decision, "reasons": control.get("reasons", [])})
            repair_suggestions.append({"artifact": name, "suggestion": "increase grounding evidence and resolve contradictions"})
        enforcement = control.get("enforcement", {}).get("action")
        if enforcement and REQUIRED_ENFORCEMENT.get(decision) != enforcement:
            raise ValueError(f"enforcement mismatch for {name}: {decision} -> {enforcement}")

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
