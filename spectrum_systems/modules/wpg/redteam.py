from __future__ import annotations

from typing import Any, Dict, List

from spectrum_systems.modules.wpg.common import stable_hash
from spectrum_systems.modules.wpg.critique_memory import ingest_comment_matrix_signal
from spectrum_systems.orchestration.wpg_pipeline import run_wpg_pipeline


def _highest_decision(decisions: List[str]) -> str:
    if any(d in {"BLOCK", "FREEZE"} for d in decisions):
        return "BLOCK"
    if any(d == "WARN" for d in decisions):
        return "WARN"
    return "ALLOW"


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
            "expect_non_allow": True,
        },
        {
            "scenario_id": "unsupported_claims",
            "severity": "HIGH",
            "transcript": {"segments": [{"segment_id": "s3", "speaker": "C", "agency": "NTIA", "text": "What is the schedule? Schedule is unknown."}]},
            "expect_non_allow": True,
        },
        {
            "scenario_id": "missing_context_answers",
            "severity": "MEDIUM",
            "transcript": {"segments": [{"segment_id": "s4", "speaker": "D", "agency": "FCC", "text": "Who owns approval?"}]},
            "expect_non_allow": True,
        },
        {
            "scenario_id": "overconfident_unknowns",
            "severity": "HIGH",
            "transcript": {"segments": [{"segment_id": "s5", "speaker": "E", "agency": "NOAA", "text": "When is release? It is definitely unknown and certainly approved."}]},
            "expect_non_allow": True,
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
        )
        decisions = [
            artifact.get("evaluation_refs", {}).get("control_decision", {}).get("decision")
            for artifact in run["artifact_chain"].values()
            if isinstance(artifact, dict)
        ]
        decision = _highest_decision([d for d in decisions if d])
        fake_green = bool(scenario.get("expect_non_allow")) and decision == "ALLOW"
        if fake_green:
            fake_green_passes += 1
        findings.append(
            {
                "scenario_id": scenario["scenario_id"],
                "severity": scenario["severity"],
                "decision": decision,
                "fake_green": fake_green,
                "stage_decisions": decisions,
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
            "status": "PASS" if fake_green_passes == 0 else "BLOCK",
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
    decision = signal["evaluation_refs"]["control_decision"]["decision"]
    finding = {
        "scenario_id": "bad_retrieve_matrix_shape",
        "severity": "high",
        "decision": decision,
        "passed": decision == "BLOCK",
        "attack_class": "bad_retrieve",
    }
    return {
        "artifact_type": "wpg_redteam_findings_phase_c",
        "schema_version": "1.0.0",
        "trace_id": "rtx-13",
        "overall_verdict": "PASS" if finding["passed"] else "NEEDS_FIXES",
        "findings": [finding],
    }
