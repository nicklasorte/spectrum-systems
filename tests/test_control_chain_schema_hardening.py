"""Tests for BZ — Control Chain Schema Hardening for Replay Governance.

Covers:
 1.  Schema tests
     a. Artifact with no replay_governance remains valid (Option A backward compat)
     b. Artifact with valid replay_governance object passes
     c. replay_governance with extra/misspelled field fails
     d. replay_governance with invalid enum fails
     e. replay_governance with replay_consistency_sli > 1 fails
     f. replay_governance with replay_consistency_sli < 0 fails
     g. replay_governance present=true + replay_governed=true but missing required fields fails
     h. replay_governance present=false is valid

 2.  Producer tests
     a. Control chain with replay governance emits schema-valid nested replay_governance
     b. Control chain without replay governance emits no replay_governance key
     c. BY-integrated drifted replay path emits correct system_response and rationale_code
     d. Missing required replay fields fail schema when governed=true

 3.  Consumer / regression tests
     a. Old flat replay governance keys are absent from the artifact
     b. Strict-precedence merging still works after schema hardening
     c. Backward compatibility: old artifact without replay_governance validates
     d. replay_governance with replay_governed=false does not require replay_status etc.

 4.  blocking_layer enum
     a. replay_governance is a valid blocking_layer value in the schema
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional
from unittest.mock import patch

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

_CC_SCHEMA_PATH = (
    _REPO_ROOT / "contracts" / "schemas" / "slo_control_chain_decision.schema.json"
)

from jsonschema import Draft202012Validator, FormatChecker  # noqa: E402

from spectrum_systems.modules.runtime.control_chain import (  # noqa: E402
    ACTION_CONTINUE,
    BLOCKING_NONE,
    CONTRACT_VERSION,
    INPUT_KIND_EVALUATION,
    REASON_CONTINUE,
    build_control_chain_decision,
    run_control_chain,
    validate_control_chain_decision,
)
from spectrum_systems.modules.runtime.decision_gating import STAGE_OBSERVE  # noqa: E402
from spectrum_systems.modules.runtime.replay_governance import (  # noqa: E402
    REPLAY_STATUS_CONSISTENT,
    REPLAY_STATUS_DRIFTED,
    REPLAY_STATUS_INDETERMINATE,
    SYSTEM_RESPONSE_ALLOW,
    SYSTEM_RESPONSE_BLOCK,
    SYSTEM_RESPONSE_QUARANTINE,
    SYSTEM_RESPONSE_REQUIRE_REVIEW,
    build_replay_governance_decision,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TS = "2026-01-01T00:00:00+00:00"
_SCHEMA = json.loads(_CC_SCHEMA_PATH.read_text())
_VALIDATOR = Draft202012Validator(_SCHEMA, format_checker=FormatChecker())


def _validate(artifact: Dict[str, Any]) -> list:
    return [e.message for e in _VALIDATOR.iter_errors(artifact)]


def _explicit_governance_policy(
    *,
    drift_action: str = SYSTEM_RESPONSE_QUARANTINE,
    indeterminate_action: str = SYSTEM_RESPONSE_REQUIRE_REVIEW,
    missing_replay_action: str = SYSTEM_RESPONSE_ALLOW,
    require_replay: bool = False,
) -> Dict[str, Any]:
    return {
        "policy_name": "bas_replay_governance",
        "policy_version": "1.0.0",
        "drift_action": drift_action,
        "indeterminate_action": indeterminate_action,
        "missing_replay_action": missing_replay_action,
        "require_replay": require_replay,
    }


def _build_replay_governance_decision(*args: Any, **kwargs: Any) -> Dict[str, Any]:
    kwargs.setdefault("governance_policy", _explicit_governance_policy())
    return build_replay_governance_decision(*args, **kwargs)


def _base_artifact() -> Dict[str, Any]:
    """Minimal valid control-chain decision without replay_governance."""
    cs = {
        "continuation_mode": "continue",
        "required_inputs": [],
        "required_validators": [],
        "repair_actions": [],
        "rerun_recommended": False,
        "human_review_required": False,
        "escalation_required": False,
        "publication_allowed": True,
        "decision_grade_allowed": False,
        "traceability_required": False,
        "control_signal_reason_codes": [],
    }
    return {
        "control_chain_decision_id": "CC-AAAA",
        "artifact_id": "art-001",
        "stage": "observe",
        "input_kind": "evaluation",
        "enforcement_decision_id": "ENF-001",
        "gating_decision_id": "GATE-001",
        "enforcement_policy": "permissive",
        "enforcement_decision_status": "allow",
        "gating_outcome": "proceed",
        "continuation_allowed": True,
        "blocking_layer": "none",
        "primary_reason_code": "control_chain_continue",
        "traceability_integrity_sli": 1.0,
        "lineage_validation_mode": "strict",
        "lineage_defaulted": False,
        "lineage_valid": True,
        "warnings": [],
        "errors": [],
        "recommended_action": "continue",
        "control_signals": cs,
        "evaluated_at": _TS,
        "schema_version": "1.0.0",
    }


def _valid_rg_governed() -> Dict[str, Any]:
    """Minimal valid replay_governance object with replay_governed=True."""
    return {
        "present": True,
        "replay_governed": True,
        "replay_status": "consistent",
        "replay_consistency_sli": 1.0,
        "system_response": "allow",
        "severity": "info",
        "rationale_code": "replay_consistent",
        "status": "ok",
        "escalated_final_decision": False,
    }


def _make_replay_analysis(
    *,
    status: str = REPLAY_STATUS_CONSISTENT,
    score: float = 1.0,
) -> Dict[str, Any]:
    return {
        "analysis_id": "analysis-001",
        "trace_id": "trace-001",
        "replay_result_id": "replay-001",
        "original_decision": {
            "decision_status": "allow",
            "decision_reason_code": "slo_pass",
        },
        "replay_decision": {
            "decision_status": "allow",
            "decision_reason_code": "slo_pass",
        },
        "decision_consistency": {
            "status": status,
            "differences": [],
        },
        "reproducibility_score": score,
        "explanation": "Test.",
        "created_at": _TS,
    }


def _slo_evaluation(**overrides: Any) -> Dict[str, Any]:
    base = {
        "artifact_type": "slo_enforcement_decision",
        "artifact_id": "art-bz-001",
        "stage": "observe",
        "decision_id": "dec-bz-001",
        "decision_status": "allow",
        "enforcement_policy": "default",
        "traceability_integrity_sli": 1.0,
        "lineage_validation_mode": "strict",
        "lineage_defaulted": False,
        "lineage_valid": True,
        "warnings": [],
        "errors": [],
        "recommended_action": "continue",
        "evaluated_at": _TS,
        "schema_version": "1.0.0",
        "source_decision_id": "dec-bz-001",
        "enforcement_decision_status": "allow",
        "gating_outcome": "proceed",
        "gating_decision_id": "gate-bz-001",
    }
    base.update(overrides)
    return base


def _mock_gating_proceed():
    return {
        "gating_decision": {
            "gating_decision_id": "gate-bz-001",
            "gating_outcome": "proceed",
            "stage": "observe",
            "warnings": [],
            "errors": [],
        },
        "gating_outcome": "proceed",
        "schema_errors": [],
    }


# ===========================================================================
# 1. Schema tests
# ===========================================================================

class TestReplayGovernanceSchema:
    """Schema-level tests for the replay_governance nested object."""

    def test_artifact_without_replay_governance_is_valid(self):
        """Backward compat: old artifacts without replay_governance key must still pass."""
        art = _base_artifact()
        errors = _validate(art)
        assert errors == [], errors

    def test_artifact_with_valid_replay_governance_passes(self):
        """New artifact with valid replay_governance nested object must pass."""
        art = _base_artifact()
        art["replay_governance"] = _valid_rg_governed()
        errors = _validate(art)
        assert errors == [], errors

    def test_replay_governance_extra_field_fails(self):
        """additionalProperties: false — unknown fields must be rejected."""
        art = _base_artifact()
        rg = _valid_rg_governed()
        rg["extra_unknown_field"] = "surprise"
        art["replay_governance"] = rg
        errors = _validate(art)
        assert errors, "Expected schema error for unknown extra field"

    def test_replay_governance_misspelled_field_fails(self):
        """Misspelled field names must fail, not silently pass."""
        art = _base_artifact()
        rg = _valid_rg_governed()
        rg["raplay_status"] = "consistent"  # typo
        art["replay_governance"] = rg
        errors = _validate(art)
        assert errors, "Expected schema error for misspelled field"

    def test_replay_governance_invalid_enum_fails(self):
        """Invalid enum value in system_response must fail."""
        art = _base_artifact()
        rg = _valid_rg_governed()
        rg["system_response"] = "proceed"  # not a valid enum
        art["replay_governance"] = rg
        errors = _validate(art)
        assert errors, "Expected schema error for invalid system_response enum"

    def test_replay_governance_invalid_replay_status_fails(self):
        """Invalid enum value in replay_status must fail."""
        art = _base_artifact()
        rg = _valid_rg_governed()
        rg["replay_status"] = "unknown_status"
        art["replay_governance"] = rg
        errors = _validate(art)
        assert errors, "Expected schema error for invalid replay_status"

    def test_replay_consistency_sli_above_1_fails(self):
        """replay_consistency_sli > 1 must fail schema validation."""
        art = _base_artifact()
        rg = _valid_rg_governed()
        rg["replay_consistency_sli"] = 1.5
        art["replay_governance"] = rg
        errors = _validate(art)
        assert errors, "Expected schema error for sli > 1"

    def test_replay_consistency_sli_below_0_fails(self):
        """replay_consistency_sli < 0 must fail schema validation."""
        art = _base_artifact()
        rg = _valid_rg_governed()
        rg["replay_consistency_sli"] = -0.1
        art["replay_governance"] = rg
        errors = _validate(art)
        assert errors, "Expected schema error for sli < 0"

    def test_governed_true_missing_required_fields_fails(self):
        """present=True + replay_governed=True but missing replay_status etc. must fail."""
        art = _base_artifact()
        art["replay_governance"] = {
            "present": True,
            "replay_governed": True,
            # missing: replay_status, replay_consistency_sli, system_response, severity, rationale_code, status
        }
        errors = _validate(art)
        assert errors, "Expected schema error for missing governed fields"

    def test_replay_governance_present_false_is_valid(self):
        """present=False (no replay governance provided) must be valid."""
        art = _base_artifact()
        art["replay_governance"] = {
            "present": False,
            "replay_governed": False,
        }
        errors = _validate(art)
        assert errors == [], errors

    def test_replay_governed_false_no_required_sli_fields(self):
        """present=True, replay_governed=False does not require the SLI/status fields."""
        art = _base_artifact()
        art["replay_governance"] = {
            "present": True,
            "replay_governed": False,
            "rationale_code": "replay_not_required",
            "status": "ok",
        }
        errors = _validate(art)
        assert errors == [], errors

    def test_replay_governance_blocking_layer_value_valid(self):
        """replay_governance is a valid value for the blocking_layer field."""
        art = _base_artifact()
        art["blocking_layer"] = "replay_governance"
        art["continuation_allowed"] = False
        errors = _validate(art)
        assert errors == [], errors

    def test_old_flat_replay_fields_at_top_level_fail(self):
        """Old ad-hoc flat replay fields at the top level must fail (additionalProperties: false)."""
        art = _base_artifact()
        art["replay_governance_response"] = "quarantine"
        errors = _validate(art)
        assert errors, "Expected schema error for undeclared flat replay field"

    def test_replay_status_at_top_level_fails(self):
        """Flat replay_status at top level must fail."""
        art = _base_artifact()
        art["replay_status"] = "consistent"
        errors = _validate(art)
        assert errors, "Expected schema error for flat replay_status"

    def test_replay_consistency_sli_at_top_level_fails(self):
        """Flat replay_consistency_sli at top level must fail."""
        art = _base_artifact()
        art["replay_consistency_sli"] = 0.9
        errors = _validate(art)
        assert errors, "Expected schema error for flat replay_consistency_sli"


# ===========================================================================
# 2. Producer tests
# ===========================================================================

class TestProducer:
    """Tests proving the producer emits schema-valid replay governance."""

    def test_without_replay_governance_no_replay_key(self):
        """When no replay governance is supplied, artifact must not have replay_governance key."""
        result = run_control_chain(_slo_evaluation(), stage=STAGE_OBSERVE)
        cd = result["control_chain_decision"]
        assert "replay_governance" not in cd

    def test_without_replay_governance_passes_schema(self):
        """When no replay governance is supplied, artifact must validate cleanly."""
        result = run_control_chain(_slo_evaluation(), stage=STAGE_OBSERVE)
        cd = result["control_chain_decision"]
        errors = _validate(cd)
        assert errors == [], errors

    def test_with_consistent_replay_emits_valid_nested_object(self):
        """Consistent replay governance path emits valid nested replay_governance."""
        analysis = _make_replay_analysis(status=REPLAY_STATUS_CONSISTENT, score=1.0)
        gov = _build_replay_governance_decision(analysis, run_id="run-bz-1")

        with patch(
            "spectrum_systems.modules.runtime.control_chain.run_slo_gating",
            return_value=_mock_gating_proceed(),
        ):
            result = run_control_chain(
                _slo_evaluation(),
                stage=STAGE_OBSERVE,
                replay_governance_decision=gov,
            )

        cd = result["control_chain_decision"]
        assert "replay_governance" in cd
        rg = cd["replay_governance"]
        assert rg["present"] is True
        assert rg["replay_governed"] is True
        assert rg["system_response"] == SYSTEM_RESPONSE_ALLOW
        assert rg["replay_status"] == REPLAY_STATUS_CONSISTENT
        assert rg["replay_consistency_sli"] == pytest.approx(1.0)

        errors = _validate(cd)
        assert errors == [], errors

    def test_with_drifted_replay_emits_valid_nested_object(self):
        """Drifted replay governance path emits valid nested replay_governance."""
        analysis = _make_replay_analysis(status=REPLAY_STATUS_DRIFTED, score=0.0)
        gov = _build_replay_governance_decision(analysis, run_id="run-bz-2")

        with patch(
            "spectrum_systems.modules.runtime.control_chain.run_slo_gating",
            return_value=_mock_gating_proceed(),
        ):
            result = run_control_chain(
                _slo_evaluation(),
                stage=STAGE_OBSERVE,
                replay_governance_decision=gov,
            )

        cd = result["control_chain_decision"]
        rg = cd["replay_governance"]
        assert rg["present"] is True
        assert rg["replay_governed"] is True
        assert rg["system_response"] in {
            SYSTEM_RESPONSE_QUARANTINE, SYSTEM_RESPONSE_BLOCK
        }
        assert rg["replay_status"] == REPLAY_STATUS_DRIFTED
        assert rg["rationale_code"] == "replay_drifted"

        errors = _validate(cd)
        assert errors == [], errors

    def test_with_indeterminate_replay_emits_valid_nested_object(self):
        """Indeterminate replay governance path emits valid nested replay_governance."""
        analysis = _make_replay_analysis(status=REPLAY_STATUS_INDETERMINATE, score=0.5)
        gov = _build_replay_governance_decision(analysis, run_id="run-bz-3")

        with patch(
            "spectrum_systems.modules.runtime.control_chain.run_slo_gating",
            return_value=_mock_gating_proceed(),
        ):
            result = run_control_chain(
                _slo_evaluation(),
                stage=STAGE_OBSERVE,
                replay_governance_decision=gov,
            )

        cd = result["control_chain_decision"]
        rg = cd["replay_governance"]
        assert rg["present"] is True
        assert rg["system_response"] in {
            SYSTEM_RESPONSE_REQUIRE_REVIEW, SYSTEM_RESPONSE_BLOCK
        }
        assert rg["replay_status"] == REPLAY_STATUS_INDETERMINATE

        errors = _validate(cd)
        assert errors == [], errors

    def test_no_old_flat_replay_fields_in_artifact(self):
        """Old ad-hoc flat replay fields must not appear in the produced artifact."""
        analysis = _make_replay_analysis(status=REPLAY_STATUS_CONSISTENT, score=1.0)
        gov = _build_replay_governance_decision(analysis, run_id="run-bz-4")

        with patch(
            "spectrum_systems.modules.runtime.control_chain.run_slo_gating",
            return_value=_mock_gating_proceed(),
        ):
            result = run_control_chain(
                _slo_evaluation(),
                stage=STAGE_OBSERVE,
                replay_governance_decision=gov,
            )

        cd = result["control_chain_decision"]
        # These old flat field names must NOT appear in the artifact
        assert "replay_governance_response" not in cd
        assert "replay_governance_rationale_code" not in cd
        assert "replay_governance_escalated_final_decision" not in cd
        assert "replay_status" not in cd
        assert "replay_consistency_sli" not in cd

    def test_build_control_chain_decision_no_replay_is_valid(self):
        """build_control_chain_decision without replay_governance omits the key."""
        decision = build_control_chain_decision(
            artifact_id="ART-BZ-001",
            stage="observe",
            input_kind=INPUT_KIND_EVALUATION,
            enforcement_decision_id="ENF-BZ-001",
            gating_decision_id="GATE-BZ-001",
            enforcement_policy="permissive",
            enforcement_decision_status="allow",
            gating_outcome="proceed",
            continuation_allowed=True,
            blocking_layer=BLOCKING_NONE,
            primary_reason_code=REASON_CONTINUE,
            ti_value=1.0,
            lineage_mode="strict",
            lineage_defaulted=False,
            lineage_valid=True,
            warnings=[],
            errors=[],
            recommended_action=ACTION_CONTINUE,
            evaluated_at=_TS,
        )
        # replay_governance must not appear when not supplied
        assert "replay_governance" not in decision
        # None of the old flat ad-hoc fields should appear either
        assert "replay_governance_response" not in decision
        assert "replay_governance_rationale_code" not in decision


# ===========================================================================
# 3. Consumer / regression tests
# ===========================================================================

class TestConsumerRegression:
    """Tests proving consumers rely on the declared schema path only."""

    def test_validate_control_chain_decision_clean(self):
        """validate_control_chain_decision returns no errors for valid artifact."""
        art = _base_artifact()
        errors = validate_control_chain_decision(art)
        assert errors == []

    def test_validate_control_chain_decision_with_valid_replay_governance(self):
        """validate_control_chain_decision returns no errors for valid rg-bearing artifact."""
        art = _base_artifact()
        art["replay_governance"] = _valid_rg_governed()
        errors = validate_control_chain_decision(art)
        assert errors == []

    def test_validate_control_chain_decision_rejects_extra_rg_field(self):
        """validate_control_chain_decision must reject extra field in replay_governance."""
        art = _base_artifact()
        rg = _valid_rg_governed()
        rg["undeclared_field"] = True
        art["replay_governance"] = rg
        errors = validate_control_chain_decision(art)
        assert errors, "Expected validation error for undeclared rg field"

    def test_validate_control_chain_decision_rejects_flat_replay_fields(self):
        """Old ad-hoc flat fields on the artifact must fail validation."""
        art = _base_artifact()
        art["replay_governance_response"] = "allow"
        errors = validate_control_chain_decision(art)
        assert errors, "Expected validation error for flat replay field"

    def test_strict_precedence_still_blocks_with_schema_hardening(self):
        """block > quarantine > require_review > allow precedence still works."""
        analysis = _make_replay_analysis(status=REPLAY_STATUS_DRIFTED, score=0.0)
        gov = _build_replay_governance_decision(analysis, run_id="run-bz-5")

        with patch(
            "spectrum_systems.modules.runtime.control_chain.run_slo_gating",
            return_value=_mock_gating_proceed(),
        ):
            result = run_control_chain(
                _slo_evaluation(),
                stage=STAGE_OBSERVE,
                replay_governance_decision=gov,
            )

        # Drifted → quarantine (default policy) → continuation_allowed=False
        assert result["continuation_allowed"] is False
        cd = result["control_chain_decision"]
        assert cd["continuation_allowed"] is False
        rg = cd["replay_governance"]
        assert rg["system_response"] in {SYSTEM_RESPONSE_QUARANTINE, SYSTEM_RESPONSE_BLOCK}
        # Schema must still be valid
        errors = _validate(cd)
        assert errors == [], errors

    def test_backward_compat_old_artifact_without_replay_governance_validates(self):
        """Artifacts produced before BZ (no replay_governance key) still validate."""
        # Simulate a pre-BZ artifact: all mandatory fields, no replay_governance
        art = _base_artifact()
        assert "replay_governance" not in art
        errors = _validate(art)
        assert errors == [], errors

    def test_replay_summary_still_available_in_result(self):
        """replay_governance_summary in the run result is still accessible after hardening."""
        analysis = _make_replay_analysis(status=REPLAY_STATUS_CONSISTENT, score=1.0)
        gov = _build_replay_governance_decision(analysis, run_id="run-bz-6")

        with patch(
            "spectrum_systems.modules.runtime.control_chain.run_slo_gating",
            return_value=_mock_gating_proceed(),
        ):
            result = run_control_chain(
                _slo_evaluation(),
                stage=STAGE_OBSERVE,
                replay_governance_decision=gov,
            )

        assert result["replay_governance_summary"] is not None
        assert result["replay_governance_result"] is not None

    def test_escalated_final_decision_flag_in_nested_object(self):
        """escalated_final_decision is correctly captured in the nested object."""
        analysis = _make_replay_analysis(status=REPLAY_STATUS_DRIFTED, score=0.2)
        gov = _build_replay_governance_decision(analysis, run_id="run-bz-7")

        with patch(
            "spectrum_systems.modules.runtime.control_chain.run_slo_gating",
            return_value=_mock_gating_proceed(),
        ):
            result = run_control_chain(
                _slo_evaluation(),
                stage=STAGE_OBSERVE,
                replay_governance_decision=gov,
            )

        cd = result["control_chain_decision"]
        rg = cd["replay_governance"]
        # Drifted → non-allow response → escalated
        assert rg["escalated_final_decision"] is True
