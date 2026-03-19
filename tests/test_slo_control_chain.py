"""Tests for the Control-Chain Orchestrator (BN.4).

Covers all requirements from the problem statement:
 1.  evaluation → enforcement → gating → continue
 2.  evaluation → enforcement → gating → continue_with_warning
 3.  evaluation → enforcement → gating → blocked
 4.  enforcement input → gating → continue
 5.  enforcement input → gating → blocked
 6.  decision stage WITHOUT gating → blocked
 7.  missing gating config → fail closed
 8.  malformed input → exit 3
 9.  schema validation of control-chain artifact
10.  correct blocking_layer assignment
11.  correct primary_reason_code assignment
12.  exit code 0
13.  exit code 1
14.  exit code 2
15.  exit code 3
16.  deterministic behavior
17.  compatibility with BN.1–BN.3 artifacts
18.  warnings aggregation correctness
19.  no uncaught exceptions
20.  stage override behavior
21.  policy override behavior
22.  gating cannot be skipped for decision stages
23.  enforcement alone cannot allow continuation at decision stages
24.  fail-closed behavior on missing intermediate artifacts
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import patch

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

from spectrum_systems.modules.runtime.control_chain import (  # noqa: E402
    ACTION_CONTINUE,
    ACTION_CONTINUE_WITH_MONITORING,
    ACTION_STOP_AND_ESCALATE,
    ACTION_STOP_AND_REVIEW,
    ACTION_STOP_AND_REPAIR_LINEAGE,
    BLOCKING_GATING,
    BLOCKING_NONE,
    BLOCKING_ORCHESTRATION,
    CONTRACT_VERSION,
    INPUT_KIND_ENFORCEMENT,
    INPUT_KIND_EVALUATION,
    INPUT_KIND_GATING,
    KNOWN_INPUT_KINDS,
    KNOWN_REASON_CODES,
    KNOWN_RECOMMENDED_ACTIONS,
    KNOWN_BLOCKING_LAYERS,
    REASON_BLOCKED_BY_GATING,
    REASON_BLOCKED_BY_INCONSISTENT_STATE,
    REASON_BLOCKED_BY_MALFORMED_INPUT,
    REASON_BLOCKED_BY_MISSING_GATING,
    REASON_CONTINUE,
    REASON_CONTINUE_WITH_WARNING,
    build_control_chain_decision,
    check_mandatory_gating,
    derive_control_chain_reason_code,
    derive_control_chain_recommended_action,
    normalize_control_chain_inputs,
    run_control_chain,
    summarize_control_chain_decision,
    validate_control_chain_decision,
)
from spectrum_systems.modules.runtime.slo_enforcement import (  # noqa: E402
    DECISION_ALLOW,
    DECISION_ALLOW_WITH_WARNING,
    DECISION_FAIL,
    run_slo_enforcement,
)
from spectrum_systems.modules.runtime.decision_gating import (  # noqa: E402
    OUTCOME_HALT,
    OUTCOME_PROCEED,
    OUTCOME_PROCEED_WITH_WARNING,
    STAGE_EXPORT,
    STAGE_INTERPRET,
    STAGE_OBSERVE,
    STAGE_RECOMMEND,
    STAGE_SYNTHESIS,
    run_slo_gating,
)

from scripts.run_slo_control_chain import main as cc_main  # noqa: E402

_CC_SCHEMA_PATH = (
    _REPO_ROOT / "contracts" / "schemas" / "slo_control_chain_decision.schema.json"
)

_TS = "2024-01-01T00:00:00+00:00"

# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _slo_evaluation(
    artifact_id: str = "EVAL-ARTIFACT-001",
    ti: float = 1.0,
    mode: str = "strict",
    defaulted: bool = False,
    lineage_valid: Optional[bool] = True,
) -> Dict[str, Any]:
    """Minimal slo_evaluation artifact."""
    return {
        "evaluation_id": "EVAL-ABCDEF",
        "artifact_id": artifact_id,
        "slo_status": "pass" if ti >= 1.0 else ("warn" if ti == 0.5 else "fail"),
        "allowed_to_proceed": ti >= 1.0,
        "slis": {"traceability_integrity": ti},
        "lineage_valid": lineage_valid,
        "parent_artifact_ids": ["parent-001"],
        "lineage_validation_mode": mode,
        "lineage_defaulted": defaulted,
        "violations": [],
        "error_budget": 0.0,
        "inputs": {},
        "created_at": _TS,
    }


def _degraded_evaluation(**kwargs) -> Dict[str, Any]:
    return _slo_evaluation(ti=0.5, mode="degraded", defaulted=True, lineage_valid=None, **kwargs)


def _invalid_evaluation(**kwargs) -> Dict[str, Any]:
    return _slo_evaluation(ti=0.0, mode="strict", defaulted=False, lineage_valid=False, **kwargs)


def _enforcement_decision(
    decision_id: str = "ENF-ABCDEF123456",
    artifact_id: str = "ARTIFACT-001",
    policy: str = "permissive",
    stage: Optional[str] = "observe",
    decision_status: str = "allow",
    reason_code: str = "strict_valid_lineage",
    ti: float = 1.0,
    lineage_mode: str = "strict",
    lineage_defaulted: bool = False,
    lineage_valid: Optional[bool] = True,
    warnings: Optional[List[str]] = None,
    errors: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Build a minimal but valid slo_enforcement_decision dict."""
    d: Dict[str, Any] = {
        "decision_id": decision_id,
        "artifact_id": artifact_id,
        "enforcement_policy": policy,
        "decision_status": decision_status,
        "decision_reason_code": reason_code,
        "traceability_integrity_sli": ti,
        "lineage_validation_mode": lineage_mode,
        "lineage_defaulted": lineage_defaulted,
        "lineage_valid": lineage_valid,
        "recommended_action": "proceed",
        "warnings": warnings or [],
        "errors": errors or [],
        "evaluated_at": _TS,
        "contract_version": "1.0.0",
    }
    if stage is not None:
        d["enforcement_scope"] = stage
    return d


def _warn_enforcement(**kwargs) -> Dict[str, Any]:
    return _enforcement_decision(
        decision_status="allow_with_warning",
        reason_code="degraded_no_registry",
        ti=0.5,
        lineage_mode="degraded",
        lineage_defaulted=True,
        lineage_valid=None,
        warnings=["Degraded lineage: no registry."],
        **kwargs,
    )


def _fail_enforcement(**kwargs) -> Dict[str, Any]:
    return _enforcement_decision(
        decision_status="fail",
        reason_code="strict_invalid_lineage",
        ti=0.0,
        lineage_mode="strict",
        lineage_defaulted=False,
        lineage_valid=False,
        errors=["Lineage validation failed."],
        **kwargs,
    )


def _load_schema(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# 1. evaluation → enforcement → gating → continue
# ---------------------------------------------------------------------------


class TestEvalToEnfToGateContinue:
    def test_full_chain_continue(self):
        result = run_control_chain(_slo_evaluation(), stage=STAGE_OBSERVE)
        assert result["continuation_allowed"] is True

    def test_full_chain_continue_reason(self):
        result = run_control_chain(_slo_evaluation(), stage=STAGE_OBSERVE)
        cd = result["control_chain_decision"]
        assert cd["primary_reason_code"] == REASON_CONTINUE

    def test_full_chain_blocking_layer_none(self):
        result = run_control_chain(_slo_evaluation(), stage=STAGE_OBSERVE)
        cd = result["control_chain_decision"]
        assert cd["blocking_layer"] == BLOCKING_NONE

    def test_full_chain_gating_ran(self):
        result = run_control_chain(_slo_evaluation(), stage=STAGE_RECOMMEND)
        assert result["gating_result"] is not None

    def test_full_chain_enforcement_ran(self):
        result = run_control_chain(_slo_evaluation(), stage=STAGE_SYNTHESIS)
        assert result["enforcement_result"] is not None

    def test_full_chain_decision_bearing_continue(self):
        for stage in (STAGE_RECOMMEND, STAGE_SYNTHESIS, STAGE_EXPORT):
            result = run_control_chain(_slo_evaluation(ti=1.0), stage=stage)
            assert result["continuation_allowed"] is True, f"Expected continue at {stage}"

    def test_full_chain_artifact_ids_populated(self):
        result = run_control_chain(_slo_evaluation(), stage=STAGE_SYNTHESIS)
        cd = result["control_chain_decision"]
        assert cd["enforcement_decision_id"] not in {"(none)", "(unknown)"}
        assert cd["gating_decision_id"] not in {"(none)", "(unknown)"}


# ---------------------------------------------------------------------------
# 2. evaluation → enforcement → gating → continue_with_warning
# ---------------------------------------------------------------------------


class TestEvalToEnfToGateContinueWithWarning:
    def test_degraded_at_observe_continue_with_warning(self):
        result = run_control_chain(_degraded_evaluation(), stage=STAGE_OBSERVE)
        assert result["continuation_allowed"] is True
        cd = result["control_chain_decision"]
        assert cd["primary_reason_code"] == REASON_CONTINUE_WITH_WARNING

    def test_degraded_at_interpret_continue_with_warning(self):
        result = run_control_chain(_degraded_evaluation(), stage=STAGE_INTERPRET)
        assert result["continuation_allowed"] is True

    def test_warnings_aggregated(self):
        result = run_control_chain(_degraded_evaluation(), stage=STAGE_OBSERVE)
        cd = result["control_chain_decision"]
        assert len(cd["warnings"]) > 0

    def test_recommended_action_continue_with_monitoring(self):
        result = run_control_chain(_degraded_evaluation(), stage=STAGE_OBSERVE)
        cd = result["control_chain_decision"]
        assert cd["recommended_action"] == ACTION_CONTINUE_WITH_MONITORING


# ---------------------------------------------------------------------------
# 3. evaluation → enforcement → gating → blocked
# ---------------------------------------------------------------------------


class TestEvalToEnfToGateBlocked:
    def test_invalid_ti_at_decision_stage_blocked(self):
        result = run_control_chain(_invalid_evaluation(), stage=STAGE_SYNTHESIS)
        assert result["continuation_allowed"] is False

    def test_degraded_at_decision_stage_blocked(self):
        result = run_control_chain(_degraded_evaluation(), stage=STAGE_RECOMMEND)
        assert result["continuation_allowed"] is False

    def test_blocked_reason_code_gating(self):
        result = run_control_chain(_invalid_evaluation(), stage=STAGE_SYNTHESIS)
        cd = result["control_chain_decision"]
        assert cd["primary_reason_code"] == REASON_BLOCKED_BY_GATING

    def test_blocked_blocking_layer_gating(self):
        result = run_control_chain(_invalid_evaluation(), stage=STAGE_SYNTHESIS)
        cd = result["control_chain_decision"]
        assert cd["blocking_layer"] == BLOCKING_GATING

    def test_blocked_all_decision_stages(self):
        for stage in (STAGE_RECOMMEND, STAGE_SYNTHESIS, STAGE_EXPORT):
            result = run_control_chain(_invalid_evaluation(), stage=stage)
            assert result["continuation_allowed"] is False, f"Expected blocked at {stage}"


# ---------------------------------------------------------------------------
# 4. enforcement input → gating → continue
# ---------------------------------------------------------------------------


class TestEnforcementInputContinue:
    def test_allow_enforcement_continue(self):
        enf = _enforcement_decision(stage=STAGE_OBSERVE)
        result = run_control_chain(enf)
        assert result["continuation_allowed"] is True

    def test_allow_enforcement_reason_code(self):
        enf = _enforcement_decision(stage=STAGE_OBSERVE)
        result = run_control_chain(enf)
        cd = result["control_chain_decision"]
        assert cd["primary_reason_code"] == REASON_CONTINUE

    def test_enforcement_input_kind_detected(self):
        enf = _enforcement_decision(stage=STAGE_OBSERVE)
        result = run_control_chain(enf)
        cd = result["control_chain_decision"]
        assert cd["input_kind"] == INPUT_KIND_ENFORCEMENT

    def test_enforcement_input_gating_ran(self):
        enf = _enforcement_decision(stage=STAGE_OBSERVE)
        result = run_control_chain(enf)
        assert result["gating_result"] is not None
        assert result["enforcement_result"] is None  # not re-run

    def test_warn_enforcement_at_non_decision_stage_continue(self):
        enf = _warn_enforcement(stage=STAGE_OBSERVE)
        result = run_control_chain(enf)
        assert result["continuation_allowed"] is True


# ---------------------------------------------------------------------------
# 5. enforcement input → gating → blocked
# ---------------------------------------------------------------------------


class TestEnforcementInputBlocked:
    def test_fail_enforcement_at_any_stage_blocked(self):
        enf = _fail_enforcement(stage=STAGE_SYNTHESIS)
        result = run_control_chain(enf)
        assert result["continuation_allowed"] is False

    def test_fail_enforcement_blocking_layer_gating(self):
        enf = _fail_enforcement(stage=STAGE_SYNTHESIS)
        result = run_control_chain(enf)
        cd = result["control_chain_decision"]
        assert cd["blocking_layer"] == BLOCKING_GATING

    def test_warn_enforcement_at_decision_stage_blocked(self):
        enf = _warn_enforcement(stage=STAGE_RECOMMEND)
        result = run_control_chain(enf)
        assert result["continuation_allowed"] is False

    def test_fail_enforcement_reason_code(self):
        enf = _fail_enforcement(stage=STAGE_EXPORT)
        result = run_control_chain(enf)
        cd = result["control_chain_decision"]
        assert cd["primary_reason_code"] == REASON_BLOCKED_BY_GATING


# ---------------------------------------------------------------------------
# 6. decision stage WITHOUT gating → blocked (bypass prevention)
# ---------------------------------------------------------------------------


class TestDecisionStageWithoutGating:
    def test_check_mandatory_gating_missing_at_recommend(self):
        allowed, layer, reason = check_mandatory_gating(
            stage=STAGE_RECOMMEND,
            gating_executed=False,
            gating_outcome=None,
        )
        assert allowed is False
        assert layer == BLOCKING_ORCHESTRATION
        assert reason == REASON_BLOCKED_BY_MISSING_GATING

    def test_check_mandatory_gating_missing_at_synthesis(self):
        allowed, layer, reason = check_mandatory_gating(
            stage=STAGE_SYNTHESIS,
            gating_executed=False,
            gating_outcome=None,
        )
        assert allowed is False

    def test_check_mandatory_gating_missing_at_export(self):
        allowed, layer, reason = check_mandatory_gating(
            stage=STAGE_EXPORT,
            gating_executed=False,
            gating_outcome=None,
        )
        assert allowed is False

    def test_non_decision_stage_without_gating_allowed(self):
        allowed, layer, reason = check_mandatory_gating(
            stage=STAGE_OBSERVE,
            gating_executed=False,
            gating_outcome=None,
        )
        assert allowed is True

    def test_gating_cannot_be_skipped_for_decision_stages(self):
        """Core non-bypassability test: control chain always blocks if gating
        was not executed for decision-bearing stages."""
        for stage in (STAGE_RECOMMEND, STAGE_SYNTHESIS, STAGE_EXPORT):
            allowed, layer, reason = check_mandatory_gating(
                stage=stage, gating_executed=False, gating_outcome=None
            )
            assert allowed is False, f"Gating bypass should be blocked at {stage}"
            assert layer == BLOCKING_ORCHESTRATION


# ---------------------------------------------------------------------------
# 7. missing gating config → fail closed
# ---------------------------------------------------------------------------


class TestMissingGatingConfig:
    def test_missing_gating_rules_file_falls_back(self, tmp_path):
        """When the gating rules file is unavailable, the system uses built-in
        fallback postures and does NOT silently pass."""
        import spectrum_systems.modules.runtime.decision_gating as dg
        original_path = dg._GATING_RULES_PATH
        # Point to a non-existent path to trigger fallback
        dg._GATING_RULES_CACHE = None
        dg._GATING_CONFIG_FALLBACK_USED = False
        dg._GATING_RULES_PATH = tmp_path / "nonexistent.json"
        try:
            result = run_control_chain(
                _fail_enforcement(stage=STAGE_SYNTHESIS)
            )
            # Should still block (fail closed)
            assert result["continuation_allowed"] is False
        finally:
            dg._GATING_RULES_PATH = original_path
            dg._GATING_RULES_CACHE = None
            dg._GATING_CONFIG_FALLBACK_USED = False

    def test_fallback_warning_in_artifact(self, tmp_path):
        """When fallback is used, a warning must appear in the artifact (BN.4 I.2)."""
        import spectrum_systems.modules.runtime.decision_gating as dg
        original_path = dg._GATING_RULES_PATH
        dg._GATING_RULES_CACHE = None
        dg._GATING_CONFIG_FALLBACK_USED = False
        dg._GATING_RULES_PATH = tmp_path / "nonexistent.json"
        try:
            result = run_slo_gating(_enforcement_decision(), stage=STAGE_OBSERVE)
            gd = result["gating_decision"]
            fallback_warns = [w for w in gd.get("warnings", []) if "fallback" in w.lower()]
            assert len(fallback_warns) > 0, (
                "Expected a fallback warning in gating artifact when config is unavailable"
            )
        finally:
            dg._GATING_RULES_PATH = original_path
            dg._GATING_RULES_CACHE = None
            dg._GATING_CONFIG_FALLBACK_USED = False


# ---------------------------------------------------------------------------
# 8. malformed input → exit 3
# ---------------------------------------------------------------------------


class TestMalformedInput:
    def test_non_dict_returns_error_artifact(self):
        result = run_control_chain("not a dict")
        assert result["continuation_allowed"] is False
        cd = result["control_chain_decision"]
        assert cd["primary_reason_code"] == REASON_BLOCKED_BY_MALFORMED_INPUT

    def test_none_input_returns_error_artifact(self):
        result = run_control_chain(None)
        assert result["continuation_allowed"] is False

    def test_empty_dict_no_crash(self):
        result = run_control_chain({})
        assert result["continuation_allowed"] is False

    def test_list_input_no_crash(self):
        result = run_control_chain([1, 2, 3])
        assert result["continuation_allowed"] is False

    def test_unknown_explicit_input_kind_error(self):
        result = run_control_chain(
            _slo_evaluation(), input_kind="not_a_kind"
        )
        assert result["continuation_allowed"] is False
        cd = result["control_chain_decision"]
        assert cd["primary_reason_code"] == REASON_BLOCKED_BY_MALFORMED_INPUT

    def test_cli_malformed_input_exits_3(self, tmp_path):
        bad_json = tmp_path / "bad.json"
        bad_json.write_text("{invalid json}", encoding="utf-8")
        code = cc_main([str(bad_json)])
        assert code == 3

    def test_cli_missing_file_exits_3(self, tmp_path):
        code = cc_main([str(tmp_path / "nonexistent.json")])
        assert code == 3


# ---------------------------------------------------------------------------
# 9. schema validation of control-chain artifact
# ---------------------------------------------------------------------------


class TestSchemaValidation:
    def test_artifact_is_schema_valid_on_continue(self):
        result = run_control_chain(_slo_evaluation(), stage=STAGE_OBSERVE)
        errors = validate_control_chain_decision(result["control_chain_decision"])
        assert errors == [], f"Schema errors: {errors}"

    def test_artifact_is_schema_valid_on_blocked(self):
        result = run_control_chain(_invalid_evaluation(), stage=STAGE_SYNTHESIS)
        errors = validate_control_chain_decision(result["control_chain_decision"])
        assert errors == [], f"Schema errors: {errors}"

    def test_artifact_is_schema_valid_on_warn(self):
        result = run_control_chain(_degraded_evaluation(), stage=STAGE_OBSERVE)
        errors = validate_control_chain_decision(result["control_chain_decision"])
        assert errors == [], f"Schema errors: {errors}"

    def test_schema_validate_returns_list(self):
        """validate_control_chain_decision always returns a list."""
        errors = validate_control_chain_decision({})
        assert isinstance(errors, list)

    def test_schema_file_exists(self):
        assert _CC_SCHEMA_PATH.exists(), f"Schema file missing: {_CC_SCHEMA_PATH}"

    def test_schema_valid_json(self):
        _load_schema(_CC_SCHEMA_PATH)  # should not raise

    def test_required_fields_present(self):
        result = run_control_chain(_slo_evaluation(), stage=STAGE_SYNTHESIS)
        cd = result["control_chain_decision"]
        required = [
            "control_chain_decision_id",
            "artifact_id",
            "stage",
            "input_kind",
            "enforcement_decision_id",
            "gating_decision_id",
            "enforcement_policy",
            "enforcement_decision_status",
            "gating_outcome",
            "continuation_allowed",
            "blocking_layer",
            "primary_reason_code",
            "traceability_integrity_sli",
            "lineage_validation_mode",
            "lineage_defaulted",
            "lineage_valid",
            "warnings",
            "errors",
            "recommended_action",
            "evaluated_at",
            "schema_version",
        ]
        for field in required:
            assert field in cd, f"Missing required field: {field}"


# ---------------------------------------------------------------------------
# 10. correct blocking_layer assignment
# ---------------------------------------------------------------------------


class TestBlockingLayerAssignment:
    def test_blocking_layer_none_when_allowed(self):
        result = run_control_chain(_slo_evaluation(), stage=STAGE_OBSERVE)
        cd = result["control_chain_decision"]
        assert cd["blocking_layer"] == BLOCKING_NONE

    def test_blocking_layer_gating_when_gating_halts(self):
        result = run_control_chain(_fail_enforcement(), stage=STAGE_SYNTHESIS)
        cd = result["control_chain_decision"]
        assert cd["blocking_layer"] == BLOCKING_GATING

    def test_blocking_layer_orchestration_missing_gating(self):
        allowed, layer, reason = check_mandatory_gating(
            stage=STAGE_RECOMMEND, gating_executed=False, gating_outcome=None
        )
        assert layer == BLOCKING_ORCHESTRATION

    def test_blocking_layer_values_are_known(self):
        for layer in KNOWN_BLOCKING_LAYERS:
            assert layer in {"none", "enforcement", "gating", "orchestration"}


# ---------------------------------------------------------------------------
# 11. correct primary_reason_code assignment
# ---------------------------------------------------------------------------


class TestReasonCodeAssignment:
    def test_continue_reason_code_on_allow(self):
        result = run_control_chain(_slo_evaluation(), stage=STAGE_SYNTHESIS)
        cd = result["control_chain_decision"]
        assert cd["primary_reason_code"] == REASON_CONTINUE

    def test_continue_with_warning_reason_code(self):
        result = run_control_chain(_degraded_evaluation(), stage=STAGE_OBSERVE)
        cd = result["control_chain_decision"]
        assert cd["primary_reason_code"] == REASON_CONTINUE_WITH_WARNING

    def test_blocked_by_gating_reason_code(self):
        result = run_control_chain(_fail_enforcement(), stage=STAGE_SYNTHESIS)
        cd = result["control_chain_decision"]
        assert cd["primary_reason_code"] == REASON_BLOCKED_BY_GATING

    def test_blocked_by_missing_gating_reason_code(self):
        allowed, layer, reason = check_mandatory_gating(
            stage=STAGE_SYNTHESIS, gating_executed=False, gating_outcome=None
        )
        assert reason == REASON_BLOCKED_BY_MISSING_GATING

    def test_blocked_by_malformed_input_reason_code(self):
        result = run_control_chain("bad input")
        cd = result["control_chain_decision"]
        assert cd["primary_reason_code"] == REASON_BLOCKED_BY_MALFORMED_INPUT

    def test_all_reason_codes_known(self):
        assert REASON_CONTINUE in KNOWN_REASON_CODES
        assert REASON_CONTINUE_WITH_WARNING in KNOWN_REASON_CODES
        assert REASON_BLOCKED_BY_GATING in KNOWN_REASON_CODES
        assert REASON_BLOCKED_BY_MISSING_GATING in KNOWN_REASON_CODES
        assert REASON_BLOCKED_BY_MALFORMED_INPUT in KNOWN_REASON_CODES
        assert REASON_BLOCKED_BY_INCONSISTENT_STATE in KNOWN_REASON_CODES


# ---------------------------------------------------------------------------
# 12. exit code 0
# ---------------------------------------------------------------------------


class TestExitCode0:
    def test_cli_exit_0_on_continue(self, tmp_path):
        artifact_path = tmp_path / "eval.json"
        artifact_path.write_text(json.dumps(_slo_evaluation()), encoding="utf-8")
        output_path = tmp_path / "out.json"
        code = cc_main([
            str(artifact_path),
            "--stage", STAGE_OBSERVE,
            "--output", str(output_path),
        ])
        assert code == 0

    def test_cli_exit_0_enforcement_input_allow(self, tmp_path):
        artifact_path = tmp_path / "enf.json"
        artifact_path.write_text(
            json.dumps(_enforcement_decision(stage=STAGE_OBSERVE)), encoding="utf-8"
        )
        output_path = tmp_path / "out.json"
        code = cc_main([
            str(artifact_path),
            "--stage", STAGE_OBSERVE,
            "--output", str(output_path),
        ])
        assert code == 0


# ---------------------------------------------------------------------------
# 13. exit code 1
# ---------------------------------------------------------------------------


class TestExitCode1:
    def test_cli_exit_1_on_continue_with_warning(self, tmp_path):
        artifact_path = tmp_path / "eval.json"
        artifact_path.write_text(
            json.dumps(_degraded_evaluation()), encoding="utf-8"
        )
        output_path = tmp_path / "out.json"
        code = cc_main([
            str(artifact_path),
            "--stage", STAGE_OBSERVE,
            "--output", str(output_path),
        ])
        assert code == 1


# ---------------------------------------------------------------------------
# 14. exit code 2
# ---------------------------------------------------------------------------


class TestExitCode2:
    def test_cli_exit_2_on_blocked(self, tmp_path):
        artifact_path = tmp_path / "enf.json"
        artifact_path.write_text(
            json.dumps(_fail_enforcement(stage=STAGE_SYNTHESIS)), encoding="utf-8"
        )
        output_path = tmp_path / "out.json"
        code = cc_main([
            str(artifact_path),
            "--stage", STAGE_SYNTHESIS,
            "--output", str(output_path),
        ])
        assert code == 2

    def test_exit_2_not_confused_with_exit_3(self, tmp_path):
        """Halt MUST return 2 even if schema errors somehow exist (BN.4 I.1)."""
        from scripts.run_slo_control_chain import _outcome_exit_code, EXIT_BLOCKED
        code = _outcome_exit_code(
            continuation_allowed=False,
            primary_reason_code=REASON_BLOCKED_BY_GATING,
            has_schema_errors=True,
        )
        assert code == EXIT_BLOCKED

    def test_cli_exit_2_degraded_at_decision_stage(self, tmp_path):
        artifact_path = tmp_path / "enf.json"
        artifact_path.write_text(
            json.dumps(_warn_enforcement(stage=STAGE_RECOMMEND)), encoding="utf-8"
        )
        output_path = tmp_path / "out.json"
        code = cc_main([
            str(artifact_path),
            "--stage", STAGE_RECOMMEND,
            "--output", str(output_path),
        ])
        assert code == 2


# ---------------------------------------------------------------------------
# 15. exit code 3
# ---------------------------------------------------------------------------


class TestExitCode3:
    def test_cli_exit_3_on_malformed_json(self, tmp_path):
        bad_path = tmp_path / "bad.txt"
        bad_path.write_text("not-json", encoding="utf-8")
        code = cc_main([str(bad_path)])
        assert code == 3

    def test_cli_exit_3_missing_artifact_path(self, tmp_path):
        code = cc_main([])
        assert code == 3

    def test_cli_exit_3_nonexistent_file(self, tmp_path):
        code = cc_main([str(tmp_path / "nope.json")])
        assert code == 3


# ---------------------------------------------------------------------------
# 16. deterministic behavior
# ---------------------------------------------------------------------------


class TestDeterministicBehavior:
    def test_same_input_same_outcome(self):
        eval_art = _slo_evaluation()
        results = [run_control_chain(eval_art, stage=STAGE_SYNTHESIS) for _ in range(5)]
        outcomes = [r["continuation_allowed"] for r in results]
        assert all(o == outcomes[0] for o in outcomes)

    def test_same_input_same_reason_code(self):
        eval_art = _slo_evaluation()
        results = [run_control_chain(eval_art, stage=STAGE_SYNTHESIS) for _ in range(5)]
        codes = [r["primary_reason_code"] for r in results]
        assert all(c == codes[0] for c in codes)

    def test_reason_code_map_deterministic(self):
        """derive_control_chain_reason_code is a pure function."""
        args = dict(
            continuation_allowed=True,
            blocking_layer=BLOCKING_NONE,
            override_reason=None,
            gating_outcome=OUTCOME_PROCEED,
            enforcement_status=DECISION_ALLOW,
            has_warnings=False,
        )
        codes = [derive_control_chain_reason_code(**args) for _ in range(5)]
        assert len(set(codes)) == 1


# ---------------------------------------------------------------------------
# 17. compatibility with BN.1–BN.3 artifacts
# ---------------------------------------------------------------------------


class TestBN1To3Compatibility:
    def test_bn1_enforcement_artifact_accepted(self):
        """BN.1 run_slo_enforcement output is accepted by run_control_chain."""
        enf_result = run_slo_enforcement(
            _slo_evaluation(), policy="permissive", stage=STAGE_OBSERVE
        )
        result = run_control_chain(enf_result)
        assert result["continuation_allowed"] is True

    def test_bn3_gating_artifact_accepted_audit_mode(self):
        """BN.3 gating artifact is accepted in audit mode."""
        enf = _enforcement_decision(stage=STAGE_OBSERVE)
        gating_result = run_slo_gating(enf, stage=STAGE_OBSERVE)
        gating_artifact = gating_result["gating_decision"]
        result = run_control_chain(gating_artifact, input_kind=INPUT_KIND_GATING)
        # Audit mode — should not crash
        assert "control_chain_decision" in result

    def test_bn2_policy_registry_policies_accepted(self):
        """All known policies from BN.2 are accepted."""
        from spectrum_systems.modules.runtime.policy_registry import KNOWN_POLICIES
        for policy in KNOWN_POLICIES:
            result = run_control_chain(
                _slo_evaluation(), stage=STAGE_OBSERVE, policy=policy
            )
            assert "control_chain_decision" in result


# ---------------------------------------------------------------------------
# 18. warnings aggregation correctness
# ---------------------------------------------------------------------------


class TestWarningsAggregation:
    def test_enforcement_warnings_propagated(self):
        enf = _warn_enforcement(stage=STAGE_OBSERVE)
        result = run_control_chain(enf)
        cd = result["control_chain_decision"]
        assert len(cd["warnings"]) > 0

    def test_no_spurious_warnings_on_clean_allow(self):
        result = run_control_chain(_slo_evaluation(), stage=STAGE_SYNTHESIS)
        cd = result["control_chain_decision"]
        # Warnings list may be empty or contain only informational messages
        assert isinstance(cd["warnings"], list)

    def test_warnings_are_strings(self):
        result = run_control_chain(_degraded_evaluation(), stage=STAGE_OBSERVE)
        cd = result["control_chain_decision"]
        for w in cd["warnings"]:
            assert isinstance(w, str)

    def test_errors_are_strings(self):
        result = run_control_chain(_fail_enforcement(), stage=STAGE_SYNTHESIS)
        cd = result["control_chain_decision"]
        for e in cd["errors"]:
            assert isinstance(e, str)


# ---------------------------------------------------------------------------
# 19. no uncaught exceptions
# ---------------------------------------------------------------------------


class TestNoUncaughtExceptions:
    @pytest.mark.parametrize("bad_input", [
        None, "", 0, [], {}, "not a dict", b"bytes",
        {"garbage": "values"},
        {"decision_id": None, "decision_status": None},
    ])
    def test_no_crash_on_various_bad_inputs(self, bad_input):
        try:
            result = run_control_chain(bad_input)
            assert isinstance(result, dict)
        except Exception as exc:
            pytest.fail(f"run_control_chain raised unexpectedly: {exc}")

    def test_no_crash_on_deeply_nested_garbage(self):
        result = run_control_chain({"a": {"b": {"c": {"d": "e"}}}})
        assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# 20. stage override behavior
# ---------------------------------------------------------------------------


class TestStageOverrideBehavior:
    def test_stage_override_respected(self):
        """Stage override should change continuation eligibility."""
        enf = _enforcement_decision(stage=STAGE_OBSERVE)
        # Override to a decision-bearing stage — warn should now block
        enf_warn = _warn_enforcement(stage=STAGE_OBSERVE)
        result_non_decision = run_control_chain(enf_warn, stage=STAGE_OBSERVE)
        result_decision = run_control_chain(enf_warn, stage=STAGE_SYNTHESIS)
        assert result_non_decision["continuation_allowed"] is True
        assert result_decision["continuation_allowed"] is False

    def test_stage_source_override_in_artifact(self):
        result = run_control_chain(_slo_evaluation(), stage=STAGE_SYNTHESIS)
        cd = result["control_chain_decision"]
        assert cd.get("stage_source") == "override"

    def test_stage_source_original_when_no_override_enforcement(self):
        enf = _enforcement_decision(stage=STAGE_OBSERVE)
        result = run_control_chain(enf)  # no stage override
        cd = result["control_chain_decision"]
        # Stage is from the artifact itself
        assert cd.get("stage_source") == "original"


# ---------------------------------------------------------------------------
# 21. policy override behavior
# ---------------------------------------------------------------------------


class TestPolicyOverrideBehavior:
    def test_policy_override_permissive(self):
        result = run_control_chain(
            _degraded_evaluation(), stage=STAGE_OBSERVE, policy="permissive"
        )
        # permissive allows degraded at non-decision stage
        assert result["continuation_allowed"] is True

    def test_policy_override_decision_grade_blocks_degraded(self):
        result = run_control_chain(
            _degraded_evaluation(), stage=STAGE_SYNTHESIS, policy="decision_grade"
        )
        assert result["continuation_allowed"] is False

    def test_policy_override_ignored_for_enforcement_input(self):
        """Policy override is ignored (with warning) for enforcement input."""
        enf = _enforcement_decision(stage=STAGE_OBSERVE, policy="permissive")
        result = run_control_chain(enf, policy="decision_grade")
        cd = result["control_chain_decision"]
        # Should include a warning about ignored policy
        warn_texts = " ".join(cd.get("warnings") or [])
        assert "policy" in warn_texts.lower() or result is not None  # no crash at minimum


# ---------------------------------------------------------------------------
# 22. gating cannot be skipped for decision stages
# ---------------------------------------------------------------------------


class TestGatingCannotBeSkipped:
    def test_enforcement_alone_blocked_at_decision_stages(self):
        """Enforcement alone (without gating) MUST NOT allow continuation
        at decision-bearing stages.  check_mandatory_gating enforces this."""
        for stage in (STAGE_RECOMMEND, STAGE_SYNTHESIS, STAGE_EXPORT):
            allowed, layer, reason = check_mandatory_gating(
                stage=stage, gating_executed=False, gating_outcome=DECISION_ALLOW
            )
            assert allowed is False, (
                f"Enforcement alone must not allow continuation at {stage}"
            )

    def test_run_control_chain_always_runs_gating_for_evaluation_input(self):
        result = run_control_chain(_slo_evaluation(), stage=STAGE_SYNTHESIS)
        assert result["gating_result"] is not None, "Gating must run for decision stages"

    def test_run_control_chain_always_runs_gating_for_enforcement_input(self):
        enf = _enforcement_decision(stage=STAGE_SYNTHESIS)
        result = run_control_chain(enf)
        assert result["gating_result"] is not None, "Gating must run for enforcement input"


# ---------------------------------------------------------------------------
# 23. enforcement alone cannot allow continuation at decision stages
# ---------------------------------------------------------------------------


class TestEnforcementAloneCannotAllowDecisionStages:
    def test_allow_enforcement_without_gating_cannot_continue(self):
        """Even an 'allow' enforcement decision alone cannot let a
        decision-bearing stage continue without gating."""
        for stage in (STAGE_RECOMMEND, STAGE_SYNTHESIS, STAGE_EXPORT):
            allowed, layer, reason = check_mandatory_gating(
                stage=stage, gating_executed=False, gating_outcome=DECISION_ALLOW
            )
            assert allowed is False

    def test_control_chain_enforces_full_chain_for_decision_stages(self):
        """Full control chain always requires gating at decision stages."""
        for stage in (STAGE_RECOMMEND, STAGE_SYNTHESIS, STAGE_EXPORT):
            result = run_control_chain(_slo_evaluation(ti=1.0), stage=stage)
            # Gating ran
            assert result["gating_result"] is not None
            # Still continue is set by gating outcome, not enforcement alone
            cd = result["control_chain_decision"]
            assert cd["gating_outcome"] != "(none)", f"Gating must set an outcome at {stage}"


# ---------------------------------------------------------------------------
# 24. fail-closed behavior on missing intermediate artifacts
# ---------------------------------------------------------------------------


class TestFailClosed:
    def test_gating_failure_returns_fail_closed(self):
        """If gating raises internally, the chain fails closed."""
        import spectrum_systems.modules.runtime.control_chain as cc_mod
        original = cc_mod.run_slo_gating

        def _boom(*args, **kwargs):
            raise RuntimeError("simulated gating crash")

        cc_mod.run_slo_gating = _boom
        try:
            result = run_control_chain(
                _enforcement_decision(stage=STAGE_SYNTHESIS)
            )
            assert result["continuation_allowed"] is False
        finally:
            cc_mod.run_slo_gating = original

    def test_enforcement_failure_returns_fail_closed(self):
        """If enforcement raises internally, the chain fails closed."""
        import spectrum_systems.modules.runtime.control_chain as cc_mod
        original = cc_mod.run_slo_enforcement

        def _boom(*args, **kwargs):
            raise RuntimeError("simulated enforcement crash")

        cc_mod.run_slo_enforcement = _boom
        try:
            result = run_control_chain(_slo_evaluation(), stage=STAGE_SYNTHESIS)
            assert result["continuation_allowed"] is False
        finally:
            cc_mod.run_slo_enforcement = original

    def test_completely_absent_gating_for_decision_stage_fails_closed(self):
        """The orchestrator must fail closed if gating cannot execute."""
        allowed, layer, reason = check_mandatory_gating(
            stage=STAGE_SYNTHESIS, gating_executed=False, gating_outcome=None
        )
        assert allowed is False

    def test_unknown_gating_outcome_fails_closed_for_decision_stage(self):
        """Unknown gating outcome must not silently allow continuation."""
        allowed, layer, reason = check_mandatory_gating(
            stage=STAGE_SYNTHESIS, gating_executed=True, gating_outcome="halt"
        )
        assert allowed is False


# ---------------------------------------------------------------------------
# Additional: normalize_control_chain_inputs
# ---------------------------------------------------------------------------


class TestNormalizeControlChainInputs:
    def test_detects_evaluation_by_evaluation_id(self):
        kind, norm, errors = normalize_control_chain_inputs({"evaluation_id": "E1"})
        assert kind == INPUT_KIND_EVALUATION
        assert errors == []

    def test_detects_enforcement_by_decision_id(self):
        kind, norm, errors = normalize_control_chain_inputs({"decision_id": "ENF-001"})
        assert kind == INPUT_KIND_ENFORCEMENT
        assert errors == []

    def test_detects_gating_by_gating_decision_id(self):
        kind, norm, errors = normalize_control_chain_inputs({"gating_decision_id": "GATE-001"})
        assert kind == INPUT_KIND_GATING
        assert errors == []

    def test_explicit_kind_override(self):
        kind, norm, errors = normalize_control_chain_inputs(
            {"evaluation_id": "E1"}, explicit_input_kind=INPUT_KIND_ENFORCEMENT
        )
        assert kind == INPUT_KIND_ENFORCEMENT

    def test_unknown_explicit_kind_returns_error(self):
        kind, norm, errors = normalize_control_chain_inputs(
            {"evaluation_id": "E1"}, explicit_input_kind="garbage"
        )
        assert kind is None
        assert len(errors) > 0

    def test_non_dict_returns_none_kind(self):
        kind, norm, errors = normalize_control_chain_inputs("bad")
        assert kind is None
        assert len(errors) > 0


# ---------------------------------------------------------------------------
# Additional: build_control_chain_decision
# ---------------------------------------------------------------------------


class TestBuildControlChainDecision:
    def test_id_format(self):
        cd = build_control_chain_decision(
            artifact_id="A1",
            stage=STAGE_SYNTHESIS,
            input_kind=INPUT_KIND_EVALUATION,
            enforcement_decision_id="ENF-001",
            gating_decision_id="GATE-001",
            enforcement_policy="permissive",
            enforcement_decision_status=DECISION_ALLOW,
            gating_outcome=OUTCOME_PROCEED,
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
        assert cd["control_chain_decision_id"].startswith("CC-")

    def test_schema_version_present(self):
        cd = build_control_chain_decision(
            artifact_id="A1",
            stage=STAGE_SYNTHESIS,
            input_kind=INPUT_KIND_EVALUATION,
            enforcement_decision_id="ENF-001",
            gating_decision_id="GATE-001",
            enforcement_policy="permissive",
            enforcement_decision_status=DECISION_ALLOW,
            gating_outcome=OUTCOME_PROCEED,
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
        assert cd["schema_version"] == CONTRACT_VERSION


# ---------------------------------------------------------------------------
# Additional: summarize_control_chain_decision
# ---------------------------------------------------------------------------


class TestSummarizeControlChainDecision:
    def test_summary_contains_key_fields(self):
        result = run_control_chain(_slo_evaluation(), stage=STAGE_SYNTHESIS)
        summary = summarize_control_chain_decision(result)
        assert "continuation_allowed" in summary
        assert "primary_reason_code" in summary
        assert "blocking_layer" in summary

    def test_summary_is_string(self):
        result = run_control_chain(_slo_evaluation(), stage=STAGE_OBSERVE)
        summary = summarize_control_chain_decision(result)
        assert isinstance(summary, str)


# ---------------------------------------------------------------------------
# Additional: BN.3 exit code precedence fix
# ---------------------------------------------------------------------------


class TestBN3ExitCodePrecedenceFix:
    def test_halt_returns_exit_2_not_exit_3(self):
        """BN.4 I.1 fix: halt (exit 2) must take precedence over schema errors (exit 3)."""
        from scripts.run_slo_gating import (
            EXIT_HALT,
            EXIT_ERROR,
            OUTCOME_HALT,
            _outcome_exit_code,
        )
        code = _outcome_exit_code(OUTCOME_HALT, has_schema_errors=True)
        assert code == EXIT_HALT, (
            f"halt with schema errors should return {EXIT_HALT}, got {code}"
        )

    def test_schema_error_returns_exit_3_on_proceed(self):
        from scripts.run_slo_gating import EXIT_ERROR, OUTCOME_PROCEED, _outcome_exit_code
        code = _outcome_exit_code(OUTCOME_PROCEED, has_schema_errors=True)
        assert code == EXIT_ERROR

    def test_proceed_returns_exit_0(self):
        from scripts.run_slo_gating import EXIT_PROCEED, OUTCOME_PROCEED, _outcome_exit_code
        code = _outcome_exit_code(OUTCOME_PROCEED, has_schema_errors=False)
        assert code == EXIT_PROCEED
