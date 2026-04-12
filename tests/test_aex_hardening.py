from __future__ import annotations

from copy import deepcopy

from spectrum_systems.aex.engine import AEXEngine
from spectrum_systems.aex.hardening import (
    build_admission_authenticity_record,
    build_admission_bundle,
    build_candidate_admission_readiness,
    compute_admission_effectiveness,
    detect_duplicate_or_replay_attack,
    enforce_aex_tlc_handoff_integrity,
    evaluate_admission_bundle,
    run_boundary_redteam,
    run_semantic_redteam,
    track_admission_rejection_debt,
    reset_duplicate_registry_state,
    validate_admission_replay,
    verify_authenticity_rotation_and_expiry,
)
from tests.helpers_repo_write_lineage import build_valid_repo_write_lineage


def _admitted() -> dict[str, object]:
    result = AEXEngine().admit_codex_request(
        {
            "request_id": "req-aex-hardening-1",
            "prompt_text": "modify contracts and tests and commit",
            "trace_id": "trace-aex-hardening-1",
            "created_at": "2026-04-12T00:00:00Z",
            "produced_by": "codex",
            "target_paths": ["contracts/schemas/build_admission_record.schema.json"],
            "requested_outputs": ["patch", "tests"],
        }
    )
    assert result.accepted
    assert result.build_admission_record is not None
    assert result.normalized_execution_request is not None
    return {
        "build_admission_record": result.build_admission_record,
        "normalized_execution_request": result.normalized_execution_request,
    }


def test_admission_eval_bundle_replay_and_readiness_flow_passes() -> None:
    lineage = build_valid_repo_write_lineage(request_id="req-aex-hardening-1", trace_id="trace-aex-hardening-1")
    auth = build_admission_authenticity_record(
        build_admission_record=lineage["build_admission_record"],
        normalized_execution_request=lineage["normalized_execution_request"],
        created_at="2026-04-12T00:00:00Z",
    )
    bundle = build_admission_bundle(
        build_admission_record=lineage["build_admission_record"],
        normalized_execution_request=lineage["normalized_execution_request"],
        admission_authenticity_record=auth,
        admission_rejection_record=None,
        created_at="2026-04-12T00:00:00Z",
    )
    eval_record = evaluate_admission_bundle(
        admission_bundle=bundle,
        build_admission_record=lineage["build_admission_record"],
        normalized_execution_request=lineage["normalized_execution_request"],
        admission_authenticity_record=auth,
        tlc_handoff_record=lineage["tlc_handoff_record"],
        created_at="2026-04-12T00:00:00Z",
    )
    replay = validate_admission_replay(
        prior_bundle=bundle,
        replay_bundle=deepcopy(bundle),
        prior_eval=eval_record,
        replay_eval=deepcopy(eval_record),
        created_at="2026-04-12T00:00:00Z",
    )
    readiness = build_candidate_admission_readiness(
        admission_eval_record=eval_record,
        admission_authenticity_record=auth,
        created_at="2026-04-12T00:00:00Z",
    )
    handoff = enforce_aex_tlc_handoff_integrity(
        build_admission_record=lineage["build_admission_record"],
        normalized_execution_request=lineage["normalized_execution_request"],
        tlc_handoff_record=lineage["tlc_handoff_record"],
        created_at="2026-04-12T00:00:00Z",
    )

    assert eval_record["evaluation_status"] == "pass"
    assert replay["replay_match"] is True
    assert readiness["readiness_status"] == "candidate_only"
    assert handoff["integrity_status"] == "pass"


def test_duplicate_guard_rejection_debt_effectiveness_and_auth_expiry_signals() -> None:
    admitted = _admitted()
    reset_duplicate_registry_state()
    first = detect_duplicate_or_replay_attack(
        request_id="req-aex-hardening-dup",
        context_digest="sha256:ctx-1",
        payload_digest="sha256:payload-1",
    )
    second = detect_duplicate_or_replay_attack(
        request_id="req-aex-hardening-dup",
        context_digest="sha256:ctx-2",
        payload_digest="sha256:payload-1",
    )
    debt = track_admission_rejection_debt(
        rejection_records=[
            {"rejection_reason_codes": ["unknown_execution_type"]},
            {"rejection_reason_codes": ["unknown_execution_type", "missing_required_field"]},
        ],
        created_at="2026-04-12T00:00:00Z",
    )
    effectiveness = compute_admission_effectiveness(
        outcomes=[
            {"expected": "reject", "actual": "reject"},
            {"expected": "accept", "actual": "accept"},
            {"expected": "accept", "actual": "reject"},
        ],
        created_at="2026-04-12T00:00:00Z",
    )
    expiry = verify_authenticity_rotation_and_expiry(authenticity=admitted["build_admission_record"]["authenticity"])

    assert first["blocked"] is False
    assert second["blocked"] is True
    assert debt["debt_status"] == "elevated"
    assert effectiveness["false_rejections"] == 1
    assert expiry["status"] in {"valid", "invalid"}


def test_redteam_rounds_capture_fail_open_semantic_drift_regressions() -> None:
    rt1_findings = run_boundary_redteam(
        fixtures=[
            {"fixture_id": "RT1-01", "exploit": "missing_authenticity", "should_fail_closed": True, "observed": "accepted"},
            {"fixture_id": "RT1-02", "exploit": "schema_gap", "should_fail_closed": True, "observed": "blocked"},
        ]
    )
    rt2_findings = run_semantic_redteam(
        fixtures=[
            {"fixture_id": "RT2-01", "semantic_drift": True, "observed": "accepted"},
            {"fixture_id": "RT2-02", "semantic_drift": True, "observed": "blocked"},
        ]
    )

    assert [row["fixture_id"] for row in rt1_findings] == ["RT1-01"]
    assert [row["fixture_id"] for row in rt2_findings] == ["RT2-01"]
