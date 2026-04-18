from __future__ import annotations

from typing import Any, Dict, List

from spectrum_systems.modules.wpg.common import stable_hash
from spectrum_systems.modules.wpg.critique_memory import ingest_comment_matrix_signal
from spectrum_systems.orchestration.wpg_pipeline import run_wpg_pipeline


def _highest_control_outcome(actions: List[str]) -> str:
    if any(action in {"trigger_repair", "halt"} for action in actions):
        return "halt_or_repair"
    if any(action == "annotate" for action in actions):
        return "annotate"
    return "proceed"


def _context_bundle(trace_id: str, run_id: str) -> Dict[str, Any]:
    return {
        "artifact_type": "context_bundle_artifact",
        "schema_version": "1.0.0",
        "context_bundle_id": f"ctxb-{run_id}",
        "trace": {"trace_id": trace_id, "run_id": run_id},
        "created_at": "2026-04-18T00:00:00Z",
        "components": [
            {"component_type": "transcript", "required": True, "source_type": "transcript", "source_ref": "transcript_artifact", "captured_at": "2026-04-18T00:00:00Z", "content_hash": "h1", "provenance": {"source_uri": "artifact://transcript_artifact", "source_system": "wpg", "collected_by": "redteam", "collected_at": "2026-04-18T00:00:00Z", "attribution": "transcript_artifact"}},
            {"component_type": "meeting_minutes", "required": True, "source_type": "meeting_minutes", "source_ref": "meeting_minutes_artifact", "captured_at": "2026-04-18T00:00:00Z", "content_hash": "h2", "provenance": {"source_uri": "artifact://meeting_minutes_artifact", "source_system": "wpg", "collected_by": "redteam", "collected_at": "2026-04-18T00:00:00Z", "attribution": "meeting_minutes_artifact"}},
            {"component_type": "slides", "required": True, "source_type": "slides", "source_ref": "slides_artifact", "captured_at": "2026-04-18T00:00:00Z", "content_hash": "h3", "provenance": {"source_uri": "artifact://slides_artifact", "source_system": "wpg", "collected_by": "redteam", "collected_at": "2026-04-18T00:00:00Z", "attribution": "slides_artifact"}},
            {"component_type": "critique_artifacts", "required": True, "source_type": "critique_artifacts", "source_ref": "critique_artifact", "captured_at": "2026-04-18T00:00:00Z", "content_hash": "h4", "provenance": {"source_uri": "artifact://critique_artifact", "source_system": "wpg", "collected_by": "redteam", "collected_at": "2026-04-18T00:00:00Z", "attribution": "critique_artifact"}},
            {"component_type": "prior_wpg_outputs", "required": True, "source_type": "prior_wpg_outputs", "source_ref": "prior_working_paper_artifact", "captured_at": "2026-04-18T00:00:00Z", "content_hash": "h5", "provenance": {"source_uri": "artifact://prior_working_paper_artifact", "source_system": "wpg", "collected_by": "redteam", "collected_at": "2026-04-18T00:00:00Z", "attribution": "prior_working_paper_artifact"}},
            {"component_type": "eval_outputs", "required": True, "source_type": "eval_outputs", "source_ref": "eval_outputs_artifact", "captured_at": "2026-04-18T00:00:00Z", "content_hash": "h6", "provenance": {"source_uri": "artifact://eval_outputs_artifact", "source_system": "wpg", "collected_by": "redteam", "collected_at": "2026-04-18T00:00:00Z", "attribution": "eval_outputs_artifact"}},
        ],
    }


def run_wpg_redteam_suite() -> Dict[str, Any]:
    findings_artifact = run_redteam_eval_blind_spots()
    return {
        "artifact_type": "wpg_redteam_findings",
        "schema_version": "1.0.0",
        "suite_id": "RTX-05",
        "overall_verdict": "PASS" if findings_artifact["summary"]["fake_green_passes"] == 0 else "NEEDS_FIXES",
        "findings": findings_artifact["findings"],
        "signature": stable_hash(findings_artifact["findings"]),
    }


def run_redteam_eval_blind_spots() -> Dict[str, Any]:
    scenarios: List[Dict[str, Any]] = [
        {
            "scenario_id": "conflicting_answers",
            "severity": "HIGH",
            "transcript": {
                "segments": [
                    {"segment_id": "s1", "speaker": "A", "agency": "FAA", "text": "Can we deploy now? Yes we can deploy now."},
                    {"segment_id": "s2", "speaker": "B", "agency": "DoD", "text": "Can we deploy now? No we cannot deploy now."},
                ]
            },
            "expect_requires_review": True,
        },
        {
            "scenario_id": "unsupported_claims",
            "severity": "HIGH",
            "transcript": {"segments": [{"segment_id": "s3", "speaker": "C", "agency": "NTIA", "text": "What is the schedule? Schedule is unknown."}]},
            "expect_requires_review": True,
        },
        {
            "scenario_id": "missing_context_answers",
            "severity": "MEDIUM",
            "transcript": {"segments": [{"segment_id": "s4", "speaker": "D", "agency": "FCC", "text": "Who owns approval?"}]},
            "expect_requires_review": True,
        },
        {
            "scenario_id": "overconfident_unknowns",
            "severity": "HIGH",
            "transcript": {"segments": [{"segment_id": "s5", "speaker": "E", "agency": "NOAA", "text": "When is release? It is definitely unknown and certainly approved."}]},
            "expect_requires_review": True,
        },
    ]

    findings: List[Dict[str, Any]] = []
    fake_green_passes = 0
    for scenario in scenarios:
        run = run_wpg_pipeline(
            scenario["transcript"],
            run_id=f"rtx-28-{scenario['scenario_id']}",
            trace_id=f"rtx-28-{scenario['scenario_id']}",
            mode="working_paper",
            context_bundle_artifact=_context_bundle(
                trace_id=f"rtx-28-{scenario['scenario_id']}",
                run_id=f"rtx-28-{scenario['scenario_id']}",
            ),
        )
        actions = [
            artifact.get("evaluation_refs", {}).get("control_decision", {}).get("enforcement", {}).get("action")
            for artifact in run["artifact_chain"].values()
            if isinstance(artifact, dict)
        ]
        control_outcome = _highest_control_outcome([a for a in actions if a])
        fake_green = bool(scenario.get("expect_requires_review")) and control_outcome == "proceed"
        if fake_green:
            fake_green_passes += 1
        findings.append(
            {
                "scenario_id": scenario["scenario_id"],
                "severity": scenario["severity"],
                "control_outcome": control_outcome,
                "fake_green": fake_green,
                "stage_enforcement_actions": actions,
            }
        )

    return {
        "artifact_type": "eval_redteam_findings",
        "schema_version": "1.0.0",
        "suite_id": "RTX-28",
        "findings": findings,
        "summary": {
            "scenario_count": len(findings),
            "fake_green_passes": fake_green_passes,
            "status": "PASS" if fake_green_passes == 0 else "REVIEW_REQUIRED",
        },
    }


def run_wpg_phase_c_redteam() -> Dict[str, Any]:
    malformed = {
        "artifact_type": "comment_resolution_matrix",
        "schema_version": "1.0.0",
        "trace_id": "rtx-13",
        "outputs": {"rows": [{"issue_class": "bias"}]},
    }
    signal = ingest_comment_matrix_signal(malformed, type("Ctx", (), {"run_id": "rtx-13", "trace_id": "rtx-13"})())
    control_action = signal["evaluation_refs"]["control_decision"]["enforcement"]["action"]
    finding = {
        "scenario_id": "bad_retrieve_matrix_shape",
        "severity": "high",
        "control_outcome": control_action,
        "passed": control_action == "trigger_repair",
        "attack_class": "bad_retrieve",
    }
    return {
        "artifact_type": "wpg_redteam_findings_phase_c",
        "schema_version": "1.0.0",
        "trace_id": "rtx-13",
        "overall_verdict": "PASS" if finding["passed"] else "NEEDS_FIXES",
        "findings": [finding],
    }
