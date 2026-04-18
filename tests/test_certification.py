from spectrum_systems.modules.runtime.bne02_full_wave import (
    build_certification_record,
    fix_eval_blind_spots,
    run_eval_redteam_blind_spots,
)
from spectrum_systems.modules.governance.done_certification import (
    issue_canonical_certification_decision_from_evidence,
)


def test_redteam_findings_must_map_to_fixes() -> None:
    redteam = run_eval_redteam_blind_spots(
        eval_cases=[
            {"eval_id": "eval.policy", "status": "pass", "grounded": False},
            {"eval_id": "eval.lineage", "status": "pass", "grounded": True},
        ]
    )
    findings = redteam["findings"]
    fix_result = fix_eval_blind_spots(findings=findings, existing_eval_ids=["eval.policy"])

    record = build_certification_record(
        trace_id="trace-1",
        run_id="run-1",
        checks={
            "eval_coverage": True,
            "promotion_prereqs": True,
            "policy_coverage": True,
            "context_integrity": True,
            "drift_control": True,
        },
        redteam_findings=findings,
        fixes=fix_result["fixes"],
        remaining_risks=[],
    )
    assert record["gate_status"] == "pass"
    assert record["redteam_findings"] == [{"finding_id": findings[0]["finding_id"], "status": "fixed"}]
    decision = issue_canonical_certification_decision_from_evidence(
        evidence=record,
        artifact_id="cde-cert-1",
    )
    assert decision["status"] == "pass"


def test_certification_blocks_when_open_findings_or_unmet_checks() -> None:
    record = build_certification_record(
        trace_id="trace-2",
        run_id="run-2",
        checks={
            "eval_coverage": True,
            "promotion_prereqs": False,
            "policy_coverage": True,
            "context_integrity": True,
            "drift_control": True,
        },
        redteam_findings=[{"finding_id": "RTX-14-1"}],
        fixes=[],
        remaining_risks=["promotion bypass uncertainty"],
    )
    assert record["gate_status"] == "fail"
    assert record["redteam_findings"] == [{"finding_id": "RTX-14-1", "status": "open"}]


def test_certification_normalizes_blank_remaining_risks_before_gate_status() -> None:
    record = build_certification_record(
        trace_id="trace-3",
        run_id="run-3",
        checks={
            "eval_coverage": True,
            "promotion_prereqs": True,
            "policy_coverage": True,
            "context_integrity": True,
            "drift_control": True,
        },
        redteam_findings=[],
        fixes=[],
        remaining_risks=["", "   ", "\n"],
    )
    assert record["remaining_risks"] == []
    assert record["gate_status"] == "pass"
