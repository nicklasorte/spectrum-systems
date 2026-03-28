"""Tests for BU — Governor Enforcement Bridge (evaluation_enforcement_bridge.py).

Coverage manifest (current behavior):
1. Decision/action loading and validation fail closed on malformed or missing inputs.
2. Scope resolution supports release/promotion/schema_change and rejects unknown scopes.
3. Canonical control_loop responses map to stable enforcement actions (allow/warn/block/freeze).
4. Promotion scope applies done certification gating:
   - certified/pass preserves allow/warn semantics and allows proceed
   - missing/malformed/blocked/uncertified artifacts fail closed to block
5. CLI exit behavior:
   - exit 0 for allowed outcomes (allow, warn, certified promotion pass)
   - exit 2 for blocked/freeze/invalid/unsupported override paths
6. Override authorization artifacts and applicability checks are validated directly.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

from spectrum_systems.modules.runtime.evaluation_enforcement_bridge import (  # noqa: E402
    EnforcementBridgeError,
    InvalidDecisionError,
    build_enforcement_action,
    determine_enforcement_scope,
    enforce_budget_decision,
    load_budget_decision,
    load_override_authorization,
    run_enforcement_bridge,
    validate_budget_decision,
    validate_enforcement_action,
    validate_override_authorization,
    verify_override_applicability,
)

# ---------------------------------------------------------------------------
# Fixture paths
# ---------------------------------------------------------------------------

_FIXTURE_DIR = _REPO_ROOT / "tests" / "fixtures" / "evaluation_enforcement_bridge"
_ALLOW = _FIXTURE_DIR / "decision_allow.json"
_WARN = _FIXTURE_DIR / "decision_warn.json"
_REVIEW = _FIXTURE_DIR / "decision_require_review.json"
_FREEZE = _FIXTURE_DIR / "decision_freeze_changes.json"
_BLOCK = _FIXTURE_DIR / "decision_block_release.json"
_INVALID = _FIXTURE_DIR / "invalid_decision.json"
_OVERRIDE_AUTHORIZATION = _FIXTURE_DIR / "override_authorization.json"
_DONE_CERTIFICATION_RECORD = _REPO_ROOT / "contracts" / "examples" / "done_certification_record.json"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_json(path: Path) -> Dict[str, Any]:
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def _make_decision(
    *,
    decision_dialect: str = "control_loop",
    decision_id: str = "test-decision-001",
    summary_id: str = "test-summary-001",
    status: str = "healthy",
    system_response: str = "allow",
    reasons: list | None = None,
    triggered_thresholds: list | None = None,
) -> Dict[str, Any]:
    resolved_triggered_thresholds = (
        triggered_thresholds
        if triggered_thresholds is not None
        else ([] if status == "healthy" else ["threshold-triggered"])
    )
    return {
        "decision_dialect": decision_dialect,
        "decision_id": decision_id,
        "summary_id": summary_id,
        "trace_id": "trace-test-001",
        "timestamp": "2026-03-23T00:00:00Z",
        "status": status,
        "system_response": system_response,
        "reasons": reasons if reasons is not None else ["All signals healthy."],
        "triggered_thresholds": resolved_triggered_thresholds,
    }


def _make_override_auth(
    *,
    override_id: str = "test-override-auth-001",
    decision_id: str = "test-decision-001",
    summary_id: str = "test-summary-001",
    action_id: str = "test-action-override-001",
    approved_by: str = "test-approver",
    justification: str = "Risk accepted for test.",
    scope: str = "release",
    allowed_actions: list | None = None,
    expires_at: str = "2099-12-31T23:59:59Z",
    created_at: str = "2025-01-01T00:00:00Z",
) -> Dict[str, Any]:
    return {
        "override_id": override_id,
        "decision_id": decision_id,
        "summary_id": summary_id,
        "action_id": action_id,
        "approved_by": approved_by,
        "justification": justification,
        "scope": scope,
        "allowed_actions": allowed_actions if allowed_actions is not None else ["block"],
        "expires_at": expires_at,
        "created_at": created_at,
    }


def _write_certification_pack(
    tmp_path: Path,
    *,
    decision: str = "pass",
    certification_status: str = "certified",
) -> Path:
    payload = _load_json(_DONE_CERTIFICATION_RECORD)
    payload["final_status"] = "PASSED" if decision == "pass" and certification_status == "certified" else "FAILED"
    payload["system_response"] = "allow" if payload["final_status"] == "PASSED" else "block"
    payload["blocking_reasons"] = [] if payload["final_status"] == "PASSED" else ["done gate failed"]
    out = tmp_path / f"cert-{decision}-{certification_status}.json"
    out.write_text(json.dumps(payload), encoding="utf-8")
    return out


def _write_certification_payload(tmp_path: Path, filename: str, payload: Dict[str, Any]) -> Path:
    out = tmp_path / filename
    out.write_text(json.dumps(payload), encoding="utf-8")
    return out


# ---------------------------------------------------------------------------
# 1–3. load_budget_decision
# ---------------------------------------------------------------------------


def test_load_budget_decision_valid():
    decision = load_budget_decision(_ALLOW)
    assert decision["decision_id"] == "decision-allow-001"


def test_load_budget_decision_missing_file():
    with pytest.raises(EnforcementBridgeError, match="not found"):
        load_budget_decision("/nonexistent/path/decision.json")


def test_load_budget_decision_invalid_raises():
    with pytest.raises(InvalidDecisionError):
        load_budget_decision(_INVALID)


# ---------------------------------------------------------------------------
# 4–5. validate_budget_decision
# ---------------------------------------------------------------------------


def test_validate_budget_decision_valid():
    decision = _load_json(_ALLOW)
    errors = validate_budget_decision(decision)
    assert errors == [], f"Unexpected errors: {errors}"


def test_validate_budget_decision_invalid():
    errors = validate_budget_decision({"bad": "data"})
    assert len(errors) > 0


def test_budget_decision_missing_dialect_fails_closed():
    decision = _make_decision()
    decision.pop("decision_dialect")
    with pytest.raises(InvalidDecisionError):
        enforce_budget_decision(decision)


def test_budget_decision_rejects_mixed_dialect_and_response_vocab():
    decision = _make_decision(decision_dialect="legacy", system_response="warn")
    with pytest.raises(InvalidDecisionError):
        enforce_budget_decision(decision)


# ---------------------------------------------------------------------------
# 6–7. validate_enforcement_action
# ---------------------------------------------------------------------------


def test_validate_enforcement_action_valid():
    action = build_enforcement_action(
        decision_id="dec-001",
        summary_id="sum-001",
        system_response="allow",
        enforcement_scope="release",
        reasons=["All healthy."],
        required_human_actions=[],
        allowed_to_proceed=True,
        certification_gate={
            "artifact_reference": "not_applicable",
            "certification_decision": "not_applicable",
            "certification_status": "not_applicable",
            "block_reason": None,
        },
    )
    errors = validate_enforcement_action(action)
    assert errors == [], f"Unexpected errors: {errors}"


def test_validate_enforcement_action_invalid():
    errors = validate_enforcement_action({"status": "not-a-valid-status"})
    assert len(errors) > 0


# ---------------------------------------------------------------------------
# 8–10. determine_enforcement_scope
# ---------------------------------------------------------------------------


def test_determine_enforcement_scope_default():
    decision = _make_decision()
    scope = determine_enforcement_scope(decision)
    assert scope == "release"


def test_determine_enforcement_scope_from_context():
    decision = _make_decision()
    scope = determine_enforcement_scope(decision, context={"enforcement_scope": "promotion"})
    assert scope == "promotion"


def test_determine_enforcement_scope_unknown_fails_closed():
    decision = _make_decision()
    with pytest.raises(EnforcementBridgeError, match="Invalid enforcement_scope 'unknown_scope'"):
        determine_enforcement_scope(decision, context={"enforcement_scope": "unknown_scope"})


# ---------------------------------------------------------------------------
# 11–17. enforce_budget_decision
# ---------------------------------------------------------------------------


def test_enforce_canonical_allow():
    decision = _make_decision(system_response="allow", status="healthy")
    action = enforce_budget_decision(decision)
    assert action["action_type"] == "allow"
    assert action["status"] == "advisory"
    assert action["allowed_to_proceed"] is True


def test_enforce_canonical_warn():
    decision = _make_decision(system_response="warn", status="warning")
    action = enforce_budget_decision(decision)
    assert action["action_type"] == "warn"
    assert action["status"] == "advisory"
    assert action["allowed_to_proceed"] is True


def test_enforce_canonical_block():
    decision = _make_decision(system_response="block", status="warning")
    action = enforce_budget_decision(decision)
    assert action["action_type"] == "block"
    assert action["status"] == "enforced"
    assert action["allowed_to_proceed"] is False


def test_enforce_canonical_freeze():
    decision = _make_decision(system_response="freeze", status="exhausted")
    action = enforce_budget_decision(decision)
    assert action["action_type"] == "freeze"
    assert action["status"] == "enforced"
    assert action["allowed_to_proceed"] is False


def test_enforce_budget_decision_invalid_decision_raises():
    with pytest.raises(InvalidDecisionError):
        enforce_budget_decision({"bad": "data"})


def test_legacy_values_rejected():
    decision = _make_decision(decision_dialect="legacy", system_response="warn", status="warning")
    with pytest.raises(InvalidDecisionError):
        enforce_budget_decision(decision)


def test_enforcement_bridge_accepts_explicit_control_loop_budget_decision():
    decision = {
        "decision_dialect": "control_loop",
        "decision_id": "decision-control-001",
        "summary_id": "summary-control-001",
        "trace_id": "trace-control-001",
        "timestamp": "2026-03-21T00:00:00Z",
        "status": "exhausted",
        "system_response": "freeze",
        "triggered_thresholds": ["summary_reported_exhausted"],
        "reasons": ["Monitor summary reported exhausted status."],
    }
    action = enforce_budget_decision(decision)
    assert action["action_type"] == "freeze"
    assert action["status"] == "enforced"
    assert action["allowed_to_proceed"] is False


def test_unknown_response_fails_closed():
    decision = _make_decision(system_response="unknown-response")
    with pytest.raises(InvalidDecisionError):
        enforce_budget_decision(decision)


def test_no_default_allow_path():
    decision = _make_decision(system_response="freeze", status="exhausted")
    action = enforce_budget_decision(decision)
    assert action["allowed_to_proceed"] is False


def test_mixed_dialect_rejected():
    decision = _make_decision(decision_dialect="control_loop", system_response="allow_with_warning")
    with pytest.raises(InvalidDecisionError):
        enforce_budget_decision(decision)


# ---------------------------------------------------------------------------
# 18–20. build_enforcement_action
# ---------------------------------------------------------------------------


def test_build_enforcement_action_schema_valid():
    action = build_enforcement_action(
        decision_id="dec-001",
        summary_id="sum-001",
        system_response="block",
        enforcement_scope="release",
        reasons=["Critical failure rate."],
        required_human_actions=["Block all release activity."],
        allowed_to_proceed=False,
        certification_gate={
            "artifact_reference": "not_applicable",
            "certification_decision": "not_applicable",
            "certification_status": "not_applicable",
            "block_reason": None,
        },
    )
    errors = validate_enforcement_action(action)
    assert errors == [], f"Schema errors: {errors}"


def test_build_enforcement_action_required_fields():
    action = build_enforcement_action(
        decision_id="dec-002",
        summary_id="sum-002",
        system_response="warn",
        enforcement_scope="promotion",
        reasons=["Elevated drift."],
        required_human_actions=["Review before promoting."],
        allowed_to_proceed=True,
        certification_gate={
            "artifact_reference": "not_applicable",
            "certification_decision": "not_applicable",
            "certification_status": "not_applicable",
            "block_reason": None,
        },
    )
    for field in (
        "action_id", "decision_id", "summary_id", "status", "action_type",
        "enforcement_scope", "allowed_to_proceed", "reasons",
        "required_human_actions", "certification_gate", "created_at",
    ):
        assert field in action, f"Missing field: {field}"
    assert action["decision_id"] == "dec-002"
    assert action["summary_id"] == "sum-002"


def test_build_enforcement_action_raises_on_unknown_response():
    with pytest.raises(EnforcementBridgeError, match="Unknown system_response"):
        build_enforcement_action(
            decision_id="dec-003",
            summary_id="sum-003",
            system_response="not_a_valid_response",
            enforcement_scope="release",
            reasons=["test"],
            required_human_actions=[],
            allowed_to_proceed=False,
            certification_gate={
                "artifact_reference": "not_applicable",
                "certification_decision": "not_applicable",
                "certification_status": "not_applicable",
                "block_reason": None,
            },
        )


def test_build_enforcement_action_rejects_blocking_allowed_to_proceed_true():
    with pytest.raises(EnforcementBridgeError, match="requires allowed_to_proceed=False"):
        build_enforcement_action(
            decision_id="dec-004",
            summary_id="sum-004",
            system_response="block",
            enforcement_scope="release",
            reasons=["Critical failures"],
            required_human_actions=["Stop release"],
            allowed_to_proceed=True,
            certification_gate={
                "artifact_reference": "not_applicable",
                "certification_decision": "not_applicable",
                "certification_status": "not_applicable",
                "block_reason": None,
            },
        )


# ---------------------------------------------------------------------------
# 21–29. run_enforcement_bridge
# ---------------------------------------------------------------------------


def test_run_enforcement_bridge_allow():
    action = run_enforcement_bridge(_ALLOW)
    assert action["action_type"] == "allow"
    assert action["allowed_to_proceed"] is True
    assert action["decision_id"] == "decision-allow-001"


def test_run_enforcement_bridge_warn():
    action = run_enforcement_bridge(_WARN)
    assert action["action_type"] == "warn"
    assert action["allowed_to_proceed"] is True


def test_run_enforcement_bridge_block():
    action = run_enforcement_bridge(_REVIEW)
    assert action["action_type"] == "block"
    assert action["allowed_to_proceed"] is False


def test_run_enforcement_bridge_rejects_override():
    override = _load_json(_OVERRIDE_AUTHORIZATION)
    with pytest.raises(EnforcementBridgeError, match="not supported"):
        run_enforcement_bridge(_REVIEW, context={"override_authorization": override})


def test_run_enforcement_bridge_freeze_changes():
    action = run_enforcement_bridge(_FREEZE)
    assert action["action_type"] == "freeze"
    assert action["allowed_to_proceed"] is False


def test_run_enforcement_bridge_block_release():
    action = run_enforcement_bridge(_BLOCK)
    assert action["action_type"] == "block"
    assert action["allowed_to_proceed"] is False


def test_run_enforcement_bridge_raises_on_missing_file():
    with pytest.raises(EnforcementBridgeError, match="not found"):
        run_enforcement_bridge("/nonexistent/path/decision.json")


def test_run_enforcement_bridge_raises_on_invalid_decision():
    with pytest.raises(InvalidDecisionError):
        run_enforcement_bridge(_INVALID)


def test_run_enforcement_bridge_respects_scope():
    action = run_enforcement_bridge(_ALLOW, context={"enforcement_scope": "schema_change"})
    assert action["enforcement_scope"] == "schema_change"


def test_run_enforcement_bridge_invalid_scope_fails_closed():
    with pytest.raises(EnforcementBridgeError, match="Invalid enforcement_scope 'unknown_scope'"):
        run_enforcement_bridge(_ALLOW, context={"enforcement_scope": "unknown_scope"})


def test_promotion_certified_pass_allows(tmp_path: Path):
    certification_path = _write_certification_pack(tmp_path, decision="pass", certification_status="certified")
    action = run_enforcement_bridge(
        _ALLOW,
        context={"enforcement_scope": "promotion", "done_certification_path": str(certification_path)},
    )
    assert action["allowed_to_proceed"] is True
    assert action["action_type"] == "allow"
    assert action["certification_gate"]["certification_status"] == "certified"
    assert action["certification_gate"]["certification_decision"] == "pass"
    assert action["certification_gate"]["block_reason"] is None
    assert action["certification_gate"]["artifact_reference"].startswith(str(certification_path))


def test_promotion_warn_with_certified_pass_preserves_warn(tmp_path: Path):
    certification_path = _write_certification_pack(tmp_path, decision="pass", certification_status="certified")
    action = run_enforcement_bridge(
        _WARN,
        context={"enforcement_scope": "promotion", "done_certification_path": str(certification_path)},
    )
    assert action["allowed_to_proceed"] is True
    assert action["action_type"] == "warn"
    assert action["status"] == "advisory"
    assert action["certification_gate"]["certification_status"] == "certified"
    assert action["certification_gate"]["certification_decision"] == "pass"
    assert action["certification_gate"]["block_reason"] is None


def test_promotion_uncertified_fail_blocks(tmp_path: Path):
    certification_path = _write_certification_pack(tmp_path, decision="fail", certification_status="uncertified")
    action = run_enforcement_bridge(
        _ALLOW,
        context={"enforcement_scope": "promotion", "done_certification_path": str(certification_path)},
    )
    assert action["allowed_to_proceed"] is False
    assert action["action_type"] == "block"
    assert action["certification_gate"]["certification_status"] == "uncertified"
    assert action["certification_gate"]["certification_decision"] == "fail"
    assert action["certification_gate"]["block_reason"]


def test_promotion_blocked_certification_blocks(tmp_path: Path):
    certification_path = _write_certification_pack(tmp_path, decision="blocked", certification_status="blocked")
    action = run_enforcement_bridge(
        _ALLOW,
        context={"enforcement_scope": "promotion", "done_certification_path": str(certification_path)},
    )
    assert action["allowed_to_proceed"] is False
    assert action["action_type"] == "block"
    assert action["certification_gate"]["certification_status"] == "uncertified"
    assert action["certification_gate"]["certification_decision"] == "fail"


def test_promotion_missing_certification_blocks():
    action = run_enforcement_bridge(_ALLOW, context={"enforcement_scope": "promotion"})
    assert action["allowed_to_proceed"] is False
    assert action["action_type"] == "block"
    assert action["certification_gate"]["artifact_reference"] == "missing"
    assert action["certification_gate"]["certification_status"] == "missing"
    assert action["certification_gate"]["certification_decision"] == "missing"
    assert action["certification_gate"]["block_reason"]



def test_promotion_missing_certification_path_blocks_fail_closed(tmp_path: Path):
    missing = tmp_path / "missing-certification-pack.json"
    action = run_enforcement_bridge(
        _ALLOW,
        context={"enforcement_scope": "promotion", "done_certification_path": str(missing)},
    )
    assert action["allowed_to_proceed"] is False
    assert action["action_type"] == "block"
    assert action["certification_gate"]["artifact_reference"] == str(missing)
    assert action["certification_gate"]["certification_status"] == "missing"
    assert action["certification_gate"]["certification_decision"] == "missing"
    assert action["certification_gate"]["block_reason"] == (
        f"done_certification_record file not found: {missing}"
    )
    assert action["status"] == "enforced"
    assert action["required_human_actions"][-1] == action["certification_gate"]["block_reason"]


def test_promotion_schema_invalid_certification_blocks_as_malformed(tmp_path: Path):
    schema_invalid = tmp_path / "schema-invalid-certification-pack.json"
    schema_invalid.write_text(json.dumps({"artifact_type": "done_certification_record"}), encoding="utf-8")
    action = run_enforcement_bridge(
        _ALLOW,
        context={"enforcement_scope": "promotion", "done_certification_path": str(schema_invalid)},
    )
    assert action["allowed_to_proceed"] is False
    assert action["action_type"] == "block"
    assert action["certification_gate"]["artifact_reference"] == str(schema_invalid)
    assert action["certification_gate"]["certification_status"] == "malformed"
    assert action["certification_gate"]["certification_decision"] == "malformed"
    assert "failed schema validation" in str(action["certification_gate"]["block_reason"])
    assert "is a required property" in str(action["certification_gate"]["block_reason"])
    assert "not valid JSON" not in str(action["certification_gate"]["block_reason"])
    assert action["status"] == "enforced"


def test_promotion_malformed_certification_blocks(tmp_path: Path):
    malformed = tmp_path / "bad-cert.json"
    malformed.write_text("{not-json", encoding="utf-8")
    action = run_enforcement_bridge(
        _ALLOW,
        context={"enforcement_scope": "promotion", "done_certification_path": str(malformed)},
    )
    assert action["allowed_to_proceed"] is False
    assert action["action_type"] == "block"
    assert action["certification_gate"]["artifact_reference"] == str(malformed)
    assert action["certification_gate"]["certification_status"] == "malformed"
    assert action["certification_gate"]["certification_decision"] == "malformed"
    assert "not valid JSON" in str(action["certification_gate"]["block_reason"])


def test_promotion_missing_certification_is_deterministically_fail_closed():
    first = run_enforcement_bridge(_ALLOW, context={"enforcement_scope": "promotion"})
    second = run_enforcement_bridge(_ALLOW, context={"enforcement_scope": "promotion"})
    assert first["action_type"] == second["action_type"] == "block"
    assert first["allowed_to_proceed"] is False and second["allowed_to_proceed"] is False
    assert first["certification_gate"] == second["certification_gate"]
    assert first["reasons"] == second["reasons"]


@pytest.mark.parametrize(
    ("final_status", "system_response", "expected_fragment"),
    [
        ("PASSED", "block", "'allow' was expected"),
        ("FAILED", "allow", "'block' was expected"),
    ],
    ids=["passed-with-block-response", "failed-with-allow-response"],
)
def test_promotion_contradictory_certification_state_blocks_fail_closed(
    tmp_path: Path,
    final_status: str,
    system_response: str,
    expected_fragment: str,
):
    payload = _load_json(_DONE_CERTIFICATION_RECORD)
    payload["final_status"] = final_status
    payload["system_response"] = system_response
    payload["blocking_reasons"] = [] if final_status == "PASSED" else ["unexpected"]
    certification_path = _write_certification_payload(tmp_path, "contradictory-done-cert.json", payload)
    action = run_enforcement_bridge(
        _ALLOW,
        context={"enforcement_scope": "promotion", "done_certification_path": str(certification_path)},
    )
    assert action["allowed_to_proceed"] is False
    assert action["action_type"] == "block"
    assert action["status"] == "enforced"
    assert expected_fragment in str(action["certification_gate"]["block_reason"])


def test_promotion_enum_violation_blocks_as_malformed(tmp_path: Path):
    payload = _load_json(_DONE_CERTIFICATION_RECORD)
    payload["final_status"] = "p4ss"
    payload["blocking_reasons"] = ["schema violation"]
    payload["system_response"] = "block"
    certification_path = _write_certification_payload(tmp_path, "enum-violation-certification-pack.json", payload)
    action = run_enforcement_bridge(
        _ALLOW,
        context={"enforcement_scope": "promotion", "done_certification_path": str(certification_path)},
    )
    assert action["allowed_to_proceed"] is False
    assert action["action_type"] == "block"
    assert action["status"] == "enforced"
    assert action["certification_gate"]["artifact_reference"] == str(certification_path)
    assert action["certification_gate"]["certification_status"] == "malformed"
    assert action["certification_gate"]["certification_decision"] == "malformed"
    assert "failed schema validation" in str(action["certification_gate"]["block_reason"])
    assert "'p4ss' is not one of ['PASSED', 'FAILED']" in str(action["certification_gate"]["block_reason"])


def test_promotion_additional_properties_violation_blocks(tmp_path: Path):
    payload = _load_json(_DONE_CERTIFICATION_RECORD)
    payload["unexpected_flag"] = "adversarial"
    certification_path = _write_certification_payload(
        tmp_path,
        "additional-properties-certification-pack.json",
        payload,
    )
    action = run_enforcement_bridge(
        _ALLOW,
        context={"enforcement_scope": "promotion", "done_certification_path": str(certification_path)},
    )
    assert action["allowed_to_proceed"] is False
    assert action["action_type"] == "block"
    assert action["status"] == "enforced"
    assert action["certification_gate"]["artifact_reference"] == str(certification_path)
    assert action["certification_gate"]["certification_status"] == "malformed"
    assert action["certification_gate"]["certification_decision"] == "malformed"
    assert "failed schema validation" in str(action["certification_gate"]["block_reason"])
    assert "Additional properties are not allowed ('unexpected_flag' was unexpected)" in str(
        action["certification_gate"]["block_reason"]
    )


def test_promotion_missing_required_field_blocks(tmp_path: Path):
    payload = _load_json(_DONE_CERTIFICATION_RECORD)
    payload.pop("final_status")
    certification_path = _write_certification_payload(tmp_path, "missing-required-certification-pack.json", payload)
    action = run_enforcement_bridge(
        _ALLOW,
        context={"enforcement_scope": "promotion", "done_certification_path": str(certification_path)},
    )
    assert action["allowed_to_proceed"] is False
    assert action["action_type"] == "block"
    assert action["status"] == "enforced"
    assert action["certification_gate"]["artifact_reference"] == str(certification_path)
    assert action["certification_gate"]["certification_status"] == "malformed"
    assert action["certification_gate"]["certification_decision"] == "malformed"
    assert "failed schema validation" in str(action["certification_gate"]["block_reason"])
    assert "'final_status' is a required property" in str(action["certification_gate"]["block_reason"])


def test_promotion_trace_provenance_inconsistency_blocks(tmp_path: Path):
    payload = _load_json(_DONE_CERTIFICATION_RECORD)
    payload["trace_id"] = ""
    certification_path = _write_certification_payload(
        tmp_path,
        "invalid-trace-provenance-certification-pack.json",
        payload,
    )
    action = run_enforcement_bridge(
        _ALLOW,
        context={"enforcement_scope": "promotion", "done_certification_path": str(certification_path)},
    )
    assert action["allowed_to_proceed"] is False
    assert action["action_type"] == "block"
    assert action["status"] == "enforced"
    assert action["certification_gate"]["artifact_reference"] == str(certification_path)
    assert action["certification_gate"]["certification_status"] == "malformed"
    assert action["certification_gate"]["certification_decision"] == "malformed"
    assert "failed schema validation" in str(action["certification_gate"]["block_reason"])
    assert "should be non-empty" in str(action["certification_gate"]["block_reason"])


def test_promotion_semantically_impossible_certified_blocked_combination_blocks(tmp_path: Path):
    payload = _load_json(_DONE_CERTIFICATION_RECORD)
    payload["final_status"] = "PASSED"
    payload["system_response"] = "allow"
    payload["blocking_reasons"] = ["cannot exist for passed state"]
    certification_path = _write_certification_payload(tmp_path, "impossible-combination-certification-pack.json", payload)
    action = run_enforcement_bridge(
        _ALLOW,
        context={"enforcement_scope": "promotion", "done_certification_path": str(certification_path)},
    )
    assert action["allowed_to_proceed"] is False
    assert action["action_type"] == "block"
    assert action["status"] == "enforced"
    assert action["certification_gate"] == {
        "artifact_reference": str(certification_path),
        "certification_decision": "malformed",
        "certification_status": "malformed",
        "block_reason": action["certification_gate"]["block_reason"],
    }
    assert "done_certification_record failed schema validation" in str(action["certification_gate"]["block_reason"])


# ---------------------------------------------------------------------------
# 30–37. CLI
# ---------------------------------------------------------------------------


def test_cli_exit_0_allow(tmp_path):
    from scripts.run_evaluation_enforcement_bridge import main  # noqa: PLC0415

    exit_code = main(["--input", str(_ALLOW), "--output-dir", str(tmp_path)])
    assert exit_code == 0


def test_cli_exit_0_warn(tmp_path):
    from scripts.run_evaluation_enforcement_bridge import main  # noqa: PLC0415

    exit_code = main(["--input", str(_WARN), "--output-dir", str(tmp_path)])
    assert exit_code == 0


def test_cli_promotion_requires_certification_and_blocks_when_missing(tmp_path):
    from scripts.run_evaluation_enforcement_bridge import main  # noqa: PLC0415

    exit_code = main([
        "--input", str(_ALLOW),
        "--scope", "promotion",
        "--output-dir", str(tmp_path),
    ])
    assert exit_code == 2


def test_cli_promotion_certified_pass_allows(tmp_path: Path):
    from scripts.run_evaluation_enforcement_bridge import main  # noqa: PLC0415

    certification_path = _write_certification_pack(tmp_path, decision="pass", certification_status="certified")
    exit_code = main([
        "--input", str(_ALLOW),
        "--scope", "promotion",
        "--done-certification", str(certification_path),
        "--output-dir", str(tmp_path),
    ])
    assert exit_code == 0


def test_cli_exit_2_block(tmp_path):
    from scripts.run_evaluation_enforcement_bridge import main  # noqa: PLC0415

    exit_code = main(["--input", str(_BLOCK), "--output-dir", str(tmp_path)])
    assert exit_code == 2


def test_cli_exit_2_override_not_supported(tmp_path):
    from scripts.run_evaluation_enforcement_bridge import main  # noqa: PLC0415

    exit_code = main([
        "--input", str(_BLOCK),
        "--output-dir", str(tmp_path),
        "--override-authorization", str(_OVERRIDE_AUTHORIZATION),
    ])
    assert exit_code == 2


def test_cli_exit_2_freeze_changes(tmp_path):
    from scripts.run_evaluation_enforcement_bridge import main  # noqa: PLC0415

    exit_code = main(["--input", str(_FREEZE), "--output-dir", str(tmp_path)])
    assert exit_code == 2


def test_cli_exit_2_block_release(tmp_path):
    from scripts.run_evaluation_enforcement_bridge import main  # noqa: PLC0415

    exit_code = main(["--input", str(_BLOCK), "--output-dir", str(tmp_path)])
    assert exit_code == 2


def test_cli_exit_2_invalid_input(tmp_path):
    from scripts.run_evaluation_enforcement_bridge import main  # noqa: PLC0415

    exit_code = main(["--input", str(_INVALID), "--output-dir", str(tmp_path)])
    assert exit_code == 2


def test_cli_exit_2_catch_all_when_not_allowed_even_with_unexpected_action_type(tmp_path, monkeypatch):
    from scripts import run_evaluation_enforcement_bridge as cli  # noqa: PLC0415

    def _fake_run_enforcement_bridge(*args, **kwargs):  # noqa: ANN002, ANN003
        return {
            "action_id": "action-weird-001",
            "decision_id": "decision-weird-001",
            "summary_id": "summary-weird-001",
            "status": "enforced",
            "action_type": "unexpected_type",
            "enforcement_scope": "release",
            "allowed_to_proceed": False,
            "reasons": ["fixture"],
            "required_human_actions": [],
            "certification_gate": {
                "artifact_reference": "not_applicable",
                "certification_decision": "not_applicable",
                "certification_status": "not_applicable",
                "block_reason": None,
            },
            "created_at": "2026-03-22T00:00:00Z",
        }

    monkeypatch.setattr(cli, "run_enforcement_bridge", _fake_run_enforcement_bridge)
    exit_code = cli.main(["--input", str(_ALLOW), "--output-dir", str(tmp_path)])
    assert exit_code == 2


def test_cli_writes_enforcement_action_artifact(tmp_path):
    from scripts.run_evaluation_enforcement_bridge import main  # noqa: PLC0415

    main(["--input", str(_ALLOW), "--output-dir", str(tmp_path)])
    action_path = tmp_path / "evaluation_enforcement_action.json"
    assert action_path.is_file()
    with action_path.open() as fh:
        action = json.load(fh)
    errors = validate_enforcement_action(action)
    assert errors == [], f"Written action is not schema-valid: {errors}"


# ---------------------------------------------------------------------------
# 38. All produced enforcement actions are schema-valid
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "fixture",
    [_ALLOW, _WARN, _REVIEW, _FREEZE, _BLOCK],
    ids=["allow", "warn", "block", "freeze", "block"],
)
def test_all_enforcement_actions_schema_valid(fixture: Path):
    action = run_enforcement_bridge(fixture)
    errors = validate_enforcement_action(action)
    assert errors == [], f"Schema errors for {fixture.name}: {errors}"


def test_enforcement_action_schema_canonical_only():
    invalid_action = {
        "action_id": "action-legacy-001",
        "decision_id": "decision-001",
        "summary_id": "summary-001",
        "status": "enforced",
        "action_type": "require_review",
        "enforcement_scope": "release",
        "allowed_to_proceed": False,
        "reasons": ["legacy response should fail"],
        "required_human_actions": [],
        "certification_gate": {
            "artifact_reference": "not_applicable",
            "certification_decision": "not_applicable",
            "certification_status": "not_applicable",
            "block_reason": None,
        },
        "created_at": "2026-03-23T00:00:00Z",
    }
    errors = validate_enforcement_action(invalid_action)
    assert errors


# ---------------------------------------------------------------------------
# 39–41. load_override_authorization
# ---------------------------------------------------------------------------


def test_load_override_authorization_valid():
    override = load_override_authorization(_OVERRIDE_AUTHORIZATION)
    assert override["override_id"] == "override-auth-001"
    assert override["decision_id"] == "decision-review-001"


def test_load_override_authorization_missing_file():
    with pytest.raises(EnforcementBridgeError, match="not found"):
        load_override_authorization("/nonexistent/path/override_authorization.json")


def test_load_override_authorization_invalid_raises():
    import tempfile  # noqa: PLC0415

    bad = {"not": "a valid override"}
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as fh:
        json.dump(bad, fh)
        bad_path = fh.name
    with pytest.raises(EnforcementBridgeError):
        load_override_authorization(bad_path)


# ---------------------------------------------------------------------------
# 42–43. validate_override_authorization
# ---------------------------------------------------------------------------


def test_validate_override_authorization_valid():
    override = _make_override_auth()
    errors = validate_override_authorization(override)
    assert errors == [], f"Unexpected errors: {errors}"


def test_validate_override_authorization_invalid():
    errors = validate_override_authorization({"bad": "data"})
    assert len(errors) > 0


# ---------------------------------------------------------------------------
# 44–50. verify_override_applicability
# ---------------------------------------------------------------------------


def _make_proto_action(
    *,
    action_id: str = "test-action-override-001",
    action_type: str = "block",
    enforcement_scope: str = "release",
) -> Dict[str, Any]:
    return {
        "action_id": action_id,
        "action_type": action_type,
        "enforcement_scope": enforcement_scope,
    }


def test_verify_override_applicability_passes():
    override = _make_override_auth()
    decision = _make_decision(system_response="block", status="warning")
    action = _make_proto_action()
    verify_override_applicability(override, decision, action)  # should not raise


def test_verify_override_applicability_fails_decision_id_mismatch():
    override = _make_override_auth(decision_id="wrong-decision-id")
    decision = _make_decision(system_response="block")
    action = _make_proto_action()
    with pytest.raises(EnforcementBridgeError, match="decision_id"):
        verify_override_applicability(override, decision, action)


def test_verify_override_applicability_fails_summary_id_mismatch():
    override = _make_override_auth(summary_id="wrong-summary-id")
    decision = _make_decision(system_response="block")
    action = _make_proto_action()
    with pytest.raises(EnforcementBridgeError, match="summary_id"):
        verify_override_applicability(override, decision, action)


def test_verify_override_applicability_fails_action_id_mismatch():
    override = _make_override_auth(action_id="wrong-action-id")
    decision = _make_decision(system_response="block")
    action = _make_proto_action(action_id="different-action-id")
    with pytest.raises(EnforcementBridgeError, match="action_id"):
        verify_override_applicability(override, decision, action)


def test_verify_override_applicability_fails_scope_mismatch():
    override = _make_override_auth(scope="promotion")
    decision = _make_decision(system_response="block")
    action = _make_proto_action(enforcement_scope="release")
    with pytest.raises(EnforcementBridgeError, match="scope"):
        verify_override_applicability(override, decision, action)


def test_verify_override_applicability_fails_expired():
    override = _make_override_auth(expires_at="2000-01-01T00:00:00Z")
    decision = _make_decision(system_response="block")
    action = _make_proto_action()
    with pytest.raises(EnforcementBridgeError, match="expired"):
        verify_override_applicability(override, decision, action)


def test_verify_override_applicability_fails_action_type_not_allowed():
    override = _make_override_auth(allowed_actions=["allow"])
    decision = _make_decision(system_response="block")
    action = _make_proto_action(action_type="block")
    with pytest.raises(EnforcementBridgeError, match="allowed_actions"):
        verify_override_applicability(override, decision, action)


# ---------------------------------------------------------------------------
# 51–52. enforce_budget_decision fail-closed on bad override_authorization
# ---------------------------------------------------------------------------


def test_enforce_budget_decision_fails_closed_on_invalid_override_schema():
    decision = _make_decision(system_response="block", status="warning")
    bad_override = {"not": "a valid override"}
    with pytest.raises(EnforcementBridgeError, match="not supported"):
        enforce_budget_decision(decision, context={"override_authorization": bad_override})


def test_enforce_budget_decision_fails_closed_on_expired_override():
    decision = _make_decision(system_response="block", status="warning")
    expired_override = _make_override_auth(expires_at="2000-01-01T00:00:00Z")
    with pytest.raises(EnforcementBridgeError, match="not supported"):
        enforce_budget_decision(decision, context={"override_authorization": expired_override})
