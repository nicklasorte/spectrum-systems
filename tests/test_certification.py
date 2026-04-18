from spectrum_systems.modules.runtime.bne02_full_wave import (
    build_certification_record,
    fix_eval_blind_spots,
    run_eval_redteam_blind_spots,
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
            "promotion_gates": True,
            "policy_enforcement": True,
            "context_integrity": True,
            "drift_control": True,
        },
        redteam_findings=findings,
        fixes=fix_result["fixes"],
        remaining_risks=[],
    )
    assert record["verdict"] == "CERTIFIED"
    assert record["redteam_findings"] == [{"finding_id": findings[0]["finding_id"], "status": "fixed"}]


def test_certification_blocks_when_open_findings_or_unmet_checks() -> None:
    record = build_certification_record(
        trace_id="trace-2",
        run_id="run-2",
        checks={
            "eval_coverage": True,
            "promotion_gates": False,
            "policy_enforcement": True,
            "context_integrity": True,
            "drift_control": True,
        },
        redteam_findings=[{"finding_id": "RTX-14-1"}],
        fixes=[],
        remaining_risks=["promotion bypass uncertainty"],
    )
    assert record["verdict"] == "BLOCKED"
    assert record["redteam_findings"] == [{"finding_id": "RTX-14-1", "status": "open"}]
