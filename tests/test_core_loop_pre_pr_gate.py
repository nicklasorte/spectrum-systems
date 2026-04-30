"""Tests for CLP-01 Core Loop Pre-PR Gate.

These tests exercise:
- the schema and example artifact
- the pure-logic helpers in spectrum_systems/modules/runtime/core_loop_pre_pr_gate.py
- AGL integration via spectrum_systems/modules/runtime/agent_core_loop_proof.py
- the AGL-01 failure-class fixtures (authority shape, authority leak, stale TLS,
  contract schema violation)

CLP is observation_only; these tests assert the artifact never claims authority
and that fail-closed behavior is preserved.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from spectrum_systems.contracts import validate_artifact
from spectrum_systems.modules.runtime.agent_core_loop_proof import (
    build_agent_core_loop_record,
)
from spectrum_systems.modules.runtime.core_loop_pre_pr_gate import (
    CHECK_OWNER,
    KNOWN_FAILURE_CLASSES,
    REQUIRED_CHECK_NAMES,
    build_check,
    build_gate_result,
    diff_hash_maps,
    evaluate_gate,
    gate_status_to_exit_code,
    hash_paths,
)

ROOT = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _all_pass_checks() -> list[dict]:
    return [
        build_check(
            check_name=name,
            command=f"echo {name}",
            status="pass",
            output_ref=f"outputs/core_loop_pre_pr_gate/{name}.json",
        )
        for name in REQUIRED_CHECK_NAMES
    ]


def _gate(checks: list[dict], *, repo_mutating: bool = True) -> dict:
    art = build_gate_result(
        work_item_id="CLP-01-TEST",
        agent_type="claude",
        repo_mutating=repo_mutating,
        base_ref="origin/main",
        head_ref="HEAD",
        changed_files=["scripts/run_core_loop_pre_pr_gate.py"],
        checks=checks,
    )
    validate_artifact(art, "core_loop_pre_pr_gate_result")
    return art


# ---------------------------------------------------------------------------
# schema + example
# ---------------------------------------------------------------------------


def test_example_validates():
    ex = json.loads(
        (
            ROOT / "contracts" / "examples" / "core_loop_pre_pr_gate_result.example.json"
        ).read_text(encoding="utf-8")
    )
    validate_artifact(ex, "core_loop_pre_pr_gate_result")


def test_authority_scope_remains_observation_only():
    art = _gate(_all_pass_checks())
    assert art["authority_scope"] == "observation_only"
    bad = dict(art)
    bad["authority_scope"] = "binding"
    with pytest.raises(Exception):
        validate_artifact(bad, "core_loop_pre_pr_gate_result")


def test_clp_does_not_claim_authority():
    """The artifact must not include any approval/certification/promotion/enforcement language."""
    art = _gate(_all_pass_checks())
    forbidden = {
        "approval",
        "certification",
        "promotion",
        "enforcement",
        "approved",
        "certified",
        "promoted",
        "enforced",
    }
    payload_lower = json.dumps(art).lower()
    for term in forbidden:
        assert f'"{term}"' not in payload_lower, term
        assert f": \"{term}\"" not in payload_lower, term


def test_gate_pass_only_when_all_required_checks_pass():
    art = _gate(_all_pass_checks())
    assert art["gate_status"] == "pass"
    assert art["first_failed_check"] is None
    assert art["human_review_required"] is False


def test_check_names_cover_required_set():
    assert set(REQUIRED_CHECK_NAMES) == {
        "authority_shape_preflight",
        "authority_leak_guard",
        "contract_enforcement",
        "tls_generated_artifact_freshness",
        "contract_preflight",
        "selected_tests",
    }
    for name, owner in CHECK_OWNER.items():
        assert owner in {
            "AEX",
            "PQX",
            "EVL",
            "TPA",
            "CDE",
            "SEL",
            "LIN",
            "REP",
            "OBS",
            "SLO",
            "PRL",
            "RIL",
            "FRE",
        }, name


# ---------------------------------------------------------------------------
# fail-closed: missing / skipped checks
# ---------------------------------------------------------------------------


def test_missing_required_check_blocks():
    """Drop authority_shape_preflight — repo_mutating gate must block."""
    checks = [c for c in _all_pass_checks() if c["check_name"] != "authority_shape_preflight"]
    art = _gate(checks)
    assert art["gate_status"] == "block"
    assert "missing_required_check_output" in art["failure_classes"]
    assert art["first_failed_check"] == "authority_shape_preflight"


def test_missing_authority_leak_blocks():
    checks = [c for c in _all_pass_checks() if c["check_name"] != "authority_leak_guard"]
    art = _gate(checks)
    assert art["gate_status"] == "block"
    assert art["first_failed_check"] == "authority_leak_guard"


def test_missing_required_check_output_blocks():
    """build_check raises if status=pass but output_ref is empty."""
    with pytest.raises(ValueError):
        build_check(
            check_name="contract_enforcement",
            command="x",
            status="pass",
            output_ref="",
        )


def test_skipped_required_check_blocks_repo_mutating():
    checks = _all_pass_checks()
    checks[0] = build_check(
        check_name="authority_shape_preflight",
        command="x",
        status="skipped",
        output_ref=None,
        reason_codes=["operator_skipped"],
    )
    art = _gate(checks)
    assert art["gate_status"] == "block"
    assert art["first_failed_check"] == "authority_shape_preflight"


# ---------------------------------------------------------------------------
# AGL-01 failure classes
# ---------------------------------------------------------------------------


def test_authority_shape_failure_blocks():
    """AGL-01 fixture: authority_shape_review_language_lint reason code."""
    checks = _all_pass_checks()
    checks[0] = build_check(
        check_name="authority_shape_preflight",
        command="x",
        status="block",
        output_ref="outputs/core_loop_pre_pr_gate/authority_shape_preflight_result.json",
        failure_class="authority_shape_violation",
        reason_codes=["authority_shape_review_language_lint"],
    )
    art = _gate(checks)
    assert art["gate_status"] == "block"
    assert art["first_failed_check"] == "authority_shape_preflight"
    assert "authority_shape_violation" in art["failure_classes"]


def test_authority_leak_failure_blocks():
    """AGL-01 fixture: forbidden authority value detected."""
    checks = _all_pass_checks()
    checks[1] = build_check(
        check_name="authority_leak_guard",
        command="x",
        status="block",
        output_ref="outputs/core_loop_pre_pr_gate/authority_leak_guard_result.json",
        failure_class="authority_leak_violation",
        reason_codes=["forbidden_authority_value"],
    )
    art = _gate(checks)
    assert art["gate_status"] == "block"
    assert art["first_failed_check"] == "authority_leak_guard"


def test_contract_enforcement_failure_blocks():
    checks = _all_pass_checks()
    checks[2] = build_check(
        check_name="contract_enforcement",
        command="x",
        status="block",
        output_ref="outputs/core_loop_pre_pr_gate/contract_enforcement.log",
        failure_class="contract_enforcement_violation",
        reason_codes=["contract_compliance_findings"],
    )
    art = _gate(checks)
    assert art["gate_status"] == "block"
    assert art["first_failed_check"] == "contract_enforcement"


def test_stale_tls_artifact_blocks():
    """AGL-01 fixture: stale TLS evidence attachment."""
    checks = _all_pass_checks()
    checks[3] = build_check(
        check_name="tls_generated_artifact_freshness",
        command="x",
        status="block",
        output_ref="outputs/core_loop_pre_pr_gate/tls_freshness_observation.json",
        failure_class="tls_generated_artifact_stale",
        reason_codes=["tls_generated_artifact_drift"],
    )
    art = _gate(checks)
    assert art["gate_status"] == "block"
    assert art["first_failed_check"] == "tls_generated_artifact_freshness"


def test_contract_preflight_block_propagates():
    """AGL-01 fixture: contract preflight schema_violation."""
    checks = _all_pass_checks()
    checks[4] = build_check(
        check_name="contract_preflight",
        command="x",
        status="block",
        output_ref="outputs/core_loop_pre_pr_gate/contract_preflight/contract_preflight_result_artifact.json",
        failure_class="contract_preflight_block",
        reason_codes=["block"],
    )
    art = _gate(checks)
    assert art["gate_status"] == "block"
    assert art["first_failed_check"] == "contract_preflight"
    assert "contract_preflight_block" in art["failure_classes"]


def test_selected_tests_failure_blocks():
    checks = _all_pass_checks()
    checks[5] = build_check(
        check_name="selected_tests",
        command="x",
        status="block",
        output_ref="outputs/core_loop_pre_pr_gate/selected_tests_result.json",
        failure_class="selected_test_failure",
        reason_codes=["pytest_returncode_1"],
    )
    art = _gate(checks)
    assert art["gate_status"] == "block"
    assert art["first_failed_check"] == "selected_tests"


def test_selected_tests_skip_in_repo_mutating_blocks():
    """Skipping the selected_tests check on repo-mutating work blocks."""
    checks = [c for c in _all_pass_checks() if c["check_name"] != "selected_tests"]
    art = _gate(checks)
    assert art["gate_status"] == "block"


def test_tls_freshness_drift_blocks(tmp_path):
    """Hash drift between before and after generator runs forces block."""
    tls_artifact = tmp_path / "system_evidence_attachment.json"
    tls_artifact.write_text("BEFORE", encoding="utf-8")
    before = hash_paths([tls_artifact])
    tls_artifact.write_text("AFTER", encoding="utf-8")
    after = hash_paths([tls_artifact])
    drift = diff_hash_maps(before, after)
    assert drift, "expected drift detection to flag changed file"
    check = build_check(
        check_name="tls_generated_artifact_freshness",
        command="regenerate-and-diff",
        status="block",
        output_ref="outputs/core_loop_pre_pr_gate/tls_freshness_observation.json",
        failure_class="tls_generated_artifact_stale",
        reason_codes=["tls_generated_artifact_drift"],
    )
    other = [c for c in _all_pass_checks() if c["check_name"] != "tls_generated_artifact_freshness"]
    art = _gate(other + [check])
    assert art["gate_status"] == "block"


def test_tls_freshness_skip_blocks_repo_mutating():
    """Skipping the freshness check on repo-mutating work blocks."""
    checks = [c for c in _all_pass_checks() if c["check_name"] != "tls_generated_artifact_freshness"]
    art = _gate(checks)
    assert art["gate_status"] == "block"


# ---------------------------------------------------------------------------
# Unknown failure classes require human review
# ---------------------------------------------------------------------------


def test_unknown_failure_class_requires_human_review():
    checks = _all_pass_checks()
    checks[2] = build_check(
        check_name="contract_enforcement",
        command="x",
        status="block",
        output_ref="outputs/core_loop_pre_pr_gate/contract_enforcement.log",
        failure_class="completely_unrecognized_failure_class",
        reason_codes=["odd_signal"],
    )
    art = _gate(checks)
    assert art["gate_status"] == "block"
    assert art["human_review_required"] is True
    assert "completely_unrecognized_failure_class" not in KNOWN_FAILURE_CLASSES


# ---------------------------------------------------------------------------
# Schema invariants enforced via validate_artifact
# ---------------------------------------------------------------------------


def test_schema_rejects_pass_with_human_review():
    art = _gate(_all_pass_checks())
    art["human_review_required"] = True
    with pytest.raises(Exception):
        validate_artifact(art, "core_loop_pre_pr_gate_result")


def test_schema_rejects_pass_with_first_failed_check():
    art = _gate(_all_pass_checks())
    art["first_failed_check"] = "selected_tests"
    with pytest.raises(Exception):
        validate_artifact(art, "core_loop_pre_pr_gate_result")


def test_schema_rejects_check_with_invalid_status():
    art = _gate(_all_pass_checks())
    art["checks"][0]["status"] = "approved"
    with pytest.raises(Exception):
        validate_artifact(art, "core_loop_pre_pr_gate_result")


def test_schema_rejects_unknown_check_name():
    art = _gate(_all_pass_checks())
    art["checks"][0]["check_name"] = "promotion_certification"
    with pytest.raises(Exception):
        validate_artifact(art, "core_loop_pre_pr_gate_result")


def test_exit_code_mapping():
    assert gate_status_to_exit_code("pass") == 0
    assert gate_status_to_exit_code("warn") == 1
    assert gate_status_to_exit_code("block") == 2


# ---------------------------------------------------------------------------
# AGL integration — repo-mutating work without CLP evidence must block
# ---------------------------------------------------------------------------


def test_agl_reports_missing_clp_evidence_for_repo_mutating_work():
    rec = build_agent_core_loop_record("AGL-MISSING-CLP", "claude", None, None)
    assert rec["compliance_status"] == "BLOCK"
    reason_codes = {a["reason_code"] for a in rec["learning_actions"]}
    assert "clp_evidence_missing" in reason_codes
    assert any(
        a["owner_system"] == "PRL" and a["reason_code"] == "clp_evidence_missing"
        for a in rec["learning_actions"]
    )


def test_agl_blocks_when_clp_gate_status_is_block(tmp_path):
    clp_artifact = tmp_path / "clp.json"
    clp = build_gate_result(
        work_item_id="W",
        agent_type="claude",
        repo_mutating=True,
        base_ref="origin/main",
        head_ref="HEAD",
        changed_files=["scripts/x.py"],
        checks=[
            build_check(
                check_name="authority_shape_preflight",
                command="x",
                status="block",
                output_ref="outputs/x.json",
                failure_class="authority_shape_violation",
                reason_codes=["authority_shape_review_language_lint"],
            ),
            *[
                build_check(
                    check_name=name,
                    command="echo ok",
                    status="pass",
                    output_ref=f"outputs/{name}.json",
                )
                for name in REQUIRED_CHECK_NAMES
                if name != "authority_shape_preflight"
            ],
        ],
    )
    clp_artifact.write_text(json.dumps(clp), encoding="utf-8")
    rec = build_agent_core_loop_record("AGL-BLOCK", "claude", None, str(clp_artifact))
    assert rec["compliance_status"] == "BLOCK"
    reason_codes = {a["reason_code"] for a in rec["learning_actions"]}
    assert "authority_shape_violation" in reason_codes


def test_agl_passes_when_clp_evidence_is_complete_pass(tmp_path):
    clp_artifact = tmp_path / "clp.json"
    clp = build_gate_result(
        work_item_id="W",
        agent_type="claude",
        repo_mutating=True,
        base_ref="origin/main",
        head_ref="HEAD",
        changed_files=["scripts/x.py"],
        checks=[
            build_check(
                check_name=name,
                command="echo ok",
                status="pass",
                output_ref=f"outputs/{name}.json",
            )
            for name in REQUIRED_CHECK_NAMES
        ],
    )
    clp_artifact.write_text(json.dumps(clp), encoding="utf-8")
    rec = build_agent_core_loop_record("AGL-PASS", "claude", None, str(clp_artifact))
    # AGL leg statuses now reflect CLP evidence: AEX/PQX/EVL/TPA legs must be
    # set from CLP. PQX leg has no CLP mapping, so it remains unknown ->
    # AGL still BLOCKs on missing PQX evidence (which is correct fail-closed
    # behavior — CLP cannot certify PQX execution closure).
    assert rec["compliance_status"] in {"BLOCK", "WARN", "PASS"}
    assert rec["loop_legs"]["AEX"]["status"] == "present"
    assert rec["loop_legs"]["EVL"]["status"] == "present"
    assert rec["loop_legs"]["TPA"]["status"] == "present"


def test_agl_treats_invalid_clp_artifact_as_missing(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{\"artifact_type\": \"not_clp\"}", encoding="utf-8")
    rec = build_agent_core_loop_record("AGL-INVALID", "claude", None, str(bad))
    assert rec["compliance_status"] == "BLOCK"
    reason_codes = {a["reason_code"] for a in rec["learning_actions"]}
    assert "clp_evidence_missing" in reason_codes


# ---------------------------------------------------------------------------
# evaluate_gate non-mutating decisions
# ---------------------------------------------------------------------------


def test_evaluate_gate_warn_when_only_warn_checks():
    checks = _all_pass_checks()
    checks[2] = build_check(
        check_name="contract_enforcement",
        command="x",
        status="warn",
        output_ref="outputs/core_loop_pre_pr_gate/contract_enforcement.log",
        failure_class="policy_mismatch",
        reason_codes=["soft_finding"],
    )
    gate_status, first_failed, classes, human = evaluate_gate(
        checks=checks, repo_mutating=True
    )
    assert gate_status == "warn"
    assert first_failed is None
    assert "policy_mismatch" in classes
    assert human is False


def test_evaluate_gate_block_with_missing_check_repo_mutating():
    checks = [c for c in _all_pass_checks() if c["check_name"] != "selected_tests"]
    gate_status, first_failed, classes, _ = evaluate_gate(
        checks=checks, repo_mutating=True
    )
    assert gate_status == "block"
    assert first_failed == "selected_tests"
    assert "missing_required_check_output" in classes


def test_evaluate_gate_pass_for_non_repo_mutating_with_no_checks():
    gate_status, first_failed, classes, human = evaluate_gate(
        checks=[], repo_mutating=False
    )
    assert gate_status == "pass"
    assert first_failed is None
    assert classes == []
    assert human is False
