"""Tests for the Stage-Aware Decision Gating Engine (BN.3).

Covers all requirements from the problem statement:
 1.  allow -> proceed
 2.  fail -> halt
 3.  warning at observe -> proceed_with_warning
 4.  warning at interpret -> proceed_with_warning
 5.  warning at recommend -> halt
 6.  warning at synthesis -> halt
 7.  warning at export -> halt by default
 8.  malformed enforcement payload
 9.  missing enforcement status
10.  unknown enforcement status
11.  contradictory enforcement payload detection
12.  schema validation of emitted gating artifact
13.  CLI exit code 0
14.  CLI exit code 1
15.  CLI exit code 2
16.  CLI exit code 3
17.  deterministic gating reason code assignment
18.  recommended action mapping correctness
19.  stage override behavior
20.  integration with run_slo_enforcement output
21.  no uncaught exceptions on malformed input
22.  governed config/schema validation
23.  outputs include stage, enforcement status, gating outcome, and reason code
24.  decision-bearing stages fail closed on warnings by default
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

from spectrum_systems.modules.runtime.decision_gating import (  # noqa: E402
    ACTION_HALT_AND_ESCALATE,
    ACTION_HALT_AND_REPAIR_LINEAGE,
    ACTION_HALT_AND_RERUN_WITH_REGISTRY,
    ACTION_HALT_AND_REVIEW,
    ACTION_PROCEED,
    ACTION_PROCEED_WITH_MONITORING,
    CONTRACT_VERSION,
    KNOWN_GATING_OUTCOMES,
    KNOWN_GATING_REASON_CODES,
    KNOWN_RECOMMENDED_ACTIONS,
    KNOWN_STAGES,
    OUTCOME_HALT,
    OUTCOME_PROCEED,
    OUTCOME_PROCEED_WITH_WARNING,
    REASON_ENFORCEMENT_ALLOW,
    REASON_ENFORCEMENT_FAIL,
    REASON_ENFORCEMENT_WARNING_ALLOWED,
    REASON_ENFORCEMENT_WARNING_BLOCKED_BY_STAGE,
    REASON_INCONSISTENT_ENFORCEMENT_PAYLOAD,
    REASON_MALFORMED_ENFORCEMENT_DECISION,
    REASON_MISSING_ENFORCEMENT_STATUS,
    REASON_UNKNOWN_ENFORCEMENT_STATUS,
    STAGE_EXPORT,
    STAGE_INTERPRET,
    STAGE_OBSERVE,
    STAGE_RECOMMEND,
    STAGE_SYNTHESIS,
    build_slo_gating_decision,
    derive_gating_reason_code,
    derive_gating_recommended_action,
    describe_stage_gating_posture,
    evaluate_gating_outcome,
    normalize_gating_inputs,
    resolve_stage_gating_posture,
    run_slo_gating,
    summarize_gating_decision,
    validate_enforcement_decision_for_gating,
    validate_slo_gating_decision,
)
from spectrum_systems.modules.runtime.slo_enforcement import (  # noqa: E402
    run_slo_enforcement,
)

from scripts.run_slo_gating import main as gating_main  # noqa: E402

_GATING_SCHEMA_PATH = _REPO_ROOT / "contracts" / "schemas" / "slo_gating_decision.schema.json"
_GATING_RULES_SCHEMA_PATH = _REPO_ROOT / "contracts" / "schemas" / "slo_gating_rules.schema.json"
_GATING_RULES_PATH = _REPO_ROOT / "data" / "policy" / "slo_gating_rules.json"


def _load_schema(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

_TS = "2024-01-01T00:00:00+00:00"


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


def _allow_decision(**kwargs) -> Dict[str, Any]:
    return _enforcement_decision(decision_status="allow", **kwargs)


def _warn_decision(stage: Optional[str] = None, **kwargs) -> Dict[str, Any]:
    return _enforcement_decision(
        decision_status="allow_with_warning",
        reason_code="degraded_no_registry",
        ti=0.5,
        lineage_mode="degraded",
        lineage_defaulted=True,
        lineage_valid=None,
        stage=stage,
        warnings=["Degraded lineage: no registry."],
        **kwargs,
    )


def _fail_decision(**kwargs) -> Dict[str, Any]:
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


# ---------------------------------------------------------------------------
# 1. allow -> proceed
# ---------------------------------------------------------------------------


class TestAllowToProceed:
    def test_allow_produces_proceed(self):
        result = run_slo_gating(_allow_decision(), stage="observe")
        assert result["gating_outcome"] == OUTCOME_PROCEED

    def test_allow_reason_code(self):
        result = run_slo_gating(_allow_decision(), stage="synthesis")
        gd = result["gating_decision"]
        assert gd["gating_reason_code"] == REASON_ENFORCEMENT_ALLOW

    def test_allow_recommended_action(self):
        result = run_slo_gating(_allow_decision(), stage="export")
        assert result["gating_decision"]["recommended_action"] == ACTION_PROCEED

    def test_allow_proceed_at_decision_bearing_stage(self):
        """allow always proceeds, even at decision-bearing stages."""
        for s in (STAGE_RECOMMEND, STAGE_SYNTHESIS, STAGE_EXPORT):
            result = run_slo_gating(_allow_decision(stage=s), stage=s)
            assert result["gating_outcome"] == OUTCOME_PROCEED


# ---------------------------------------------------------------------------
# 2. fail -> halt
# ---------------------------------------------------------------------------


class TestFailToHalt:
    def test_fail_produces_halt(self):
        result = run_slo_gating(_fail_decision(), stage="observe")
        assert result["gating_outcome"] == OUTCOME_HALT

    def test_fail_reason_code(self):
        result = run_slo_gating(_fail_decision())
        assert result["gating_decision"]["gating_reason_code"] == REASON_ENFORCEMENT_FAIL

    def test_fail_recommended_action_review(self):
        # _fail_decision sets lineage_valid=False by default
        result = run_slo_gating(_fail_decision(), stage="synthesis")
        assert result["gating_decision"]["recommended_action"] == ACTION_HALT_AND_REPAIR_LINEAGE

    def test_fail_recommended_action_rerun(self):
        result = run_slo_gating(
            _enforcement_decision(
                decision_status="fail",
                reason_code="strict_invalid_lineage",
                ti=0.0,
                lineage_mode="degraded",
                lineage_defaulted=True,
                lineage_valid=None,
                errors=["degraded fail"],
            )
        )
        assert result["gating_decision"]["recommended_action"] == ACTION_HALT_AND_RERUN_WITH_REGISTRY

    def test_fail_halt_at_all_stages(self):
        for s in KNOWN_STAGES:
            result = run_slo_gating(_fail_decision(), stage=s)
            assert result["gating_outcome"] == OUTCOME_HALT


# ---------------------------------------------------------------------------
# 3 & 4. warning at observe / interpret -> proceed_with_warning
# ---------------------------------------------------------------------------


class TestWarningAtPermissiveStages:
    def test_warning_at_observe(self):
        result = run_slo_gating(_warn_decision(stage=STAGE_OBSERVE), stage=STAGE_OBSERVE)
        assert result["gating_outcome"] == OUTCOME_PROCEED_WITH_WARNING

    def test_warning_at_interpret(self):
        result = run_slo_gating(_warn_decision(stage=STAGE_INTERPRET), stage=STAGE_INTERPRET)
        assert result["gating_outcome"] == OUTCOME_PROCEED_WITH_WARNING

    def test_warning_reason_code_allowed(self):
        result = run_slo_gating(_warn_decision(), stage=STAGE_OBSERVE)
        assert result["gating_decision"]["gating_reason_code"] == REASON_ENFORCEMENT_WARNING_ALLOWED

    def test_warning_recommended_action_monitoring(self):
        result = run_slo_gating(_warn_decision(), stage=STAGE_INTERPRET)
        assert result["gating_decision"]["recommended_action"] == ACTION_PROCEED_WITH_MONITORING


# ---------------------------------------------------------------------------
# 5 & 6 & 7. warning at recommend / synthesis / export -> halt
# ---------------------------------------------------------------------------


class TestWarningAtDecisionBearingStages:
    def test_warning_at_recommend_halts(self):
        result = run_slo_gating(_warn_decision(stage=STAGE_RECOMMEND), stage=STAGE_RECOMMEND)
        assert result["gating_outcome"] == OUTCOME_HALT

    def test_warning_at_synthesis_halts(self):
        result = run_slo_gating(_warn_decision(stage=STAGE_SYNTHESIS), stage=STAGE_SYNTHESIS)
        assert result["gating_outcome"] == OUTCOME_HALT

    def test_warning_at_export_halts(self):
        result = run_slo_gating(_warn_decision(stage=STAGE_EXPORT), stage=STAGE_EXPORT)
        assert result["gating_outcome"] == OUTCOME_HALT

    def test_warning_blocked_reason_code(self):
        for s in (STAGE_RECOMMEND, STAGE_SYNTHESIS, STAGE_EXPORT):
            result = run_slo_gating(_warn_decision(), stage=s)
            gd = result["gating_decision"]
            assert gd["gating_reason_code"] == REASON_ENFORCEMENT_WARNING_BLOCKED_BY_STAGE

    def test_warning_blocked_recommended_action_rerun(self):
        """Degraded lineage warning at decision-bearing stage → rerun with registry."""
        result = run_slo_gating(_warn_decision(), stage=STAGE_SYNTHESIS)
        gd = result["gating_decision"]
        assert gd["recommended_action"] == ACTION_HALT_AND_RERUN_WITH_REGISTRY


# ---------------------------------------------------------------------------
# 8. Malformed enforcement payload
# ---------------------------------------------------------------------------


class TestMalformedEnforcementPayload:
    def test_non_dict_input_produces_halt(self):
        result = run_slo_gating("not a dict")
        assert result["gating_outcome"] == OUTCOME_HALT
        assert result["gating_decision"]["gating_reason_code"] == REASON_MALFORMED_ENFORCEMENT_DECISION

    def test_list_input_produces_halt(self):
        result = run_slo_gating([1, 2, 3])
        assert result["gating_outcome"] == OUTCOME_HALT

    def test_empty_dict_produces_halt(self):
        result = run_slo_gating({})
        assert result["gating_outcome"] == OUTCOME_HALT

    def test_malformed_input_has_errors(self):
        result = run_slo_gating({"garbage": True})
        gd = result["gating_decision"]
        assert gd["errors"]

    def test_malformed_recommended_action(self):
        result = run_slo_gating("bad input")
        gd = result["gating_decision"]
        assert gd["recommended_action"] == ACTION_HALT_AND_ESCALATE


# ---------------------------------------------------------------------------
# 9. Missing enforcement status
# ---------------------------------------------------------------------------


class TestMissingEnforcementStatus:
    def test_missing_decision_status(self):
        decision = _allow_decision()
        del decision["decision_status"]
        result = run_slo_gating(decision)
        assert result["gating_outcome"] == OUTCOME_HALT
        assert result["gating_decision"]["gating_reason_code"] == REASON_MISSING_ENFORCEMENT_STATUS

    def test_none_decision_status(self):
        decision = _allow_decision()
        decision["decision_status"] = None
        result = run_slo_gating(decision)
        assert result["gating_outcome"] == OUTCOME_HALT


# ---------------------------------------------------------------------------
# 10. Unknown enforcement status
# ---------------------------------------------------------------------------


class TestUnknownEnforcementStatus:
    def test_unknown_status(self):
        decision = _allow_decision()
        decision["decision_status"] = "supersede"
        result = run_slo_gating(decision)
        assert result["gating_outcome"] == OUTCOME_HALT
        assert result["gating_decision"]["gating_reason_code"] == REASON_UNKNOWN_ENFORCEMENT_STATUS

    def test_empty_string_status(self):
        decision = _allow_decision()
        decision["decision_status"] = ""
        result = run_slo_gating(decision)
        assert result["gating_outcome"] == OUTCOME_HALT


# ---------------------------------------------------------------------------
# 11. Contradictory enforcement payload detection
# ---------------------------------------------------------------------------


class TestContradictoryEnforcementPayload:
    def test_allow_with_errors_is_inconsistent(self):
        """decision_status == allow but errors array is non-empty."""
        decision = _allow_decision(errors=["some error"])
        result = run_slo_gating(decision)
        assert result["gating_outcome"] == OUTCOME_HALT
        gd = result["gating_decision"]
        assert gd["gating_reason_code"] == REASON_INCONSISTENT_ENFORCEMENT_PAYLOAD

    def test_inconsistent_recommended_action(self):
        decision = _allow_decision(errors=["error"])
        result = run_slo_gating(decision)
        gd = result["gating_decision"]
        assert gd["recommended_action"] == ACTION_HALT_AND_ESCALATE


# ---------------------------------------------------------------------------
# 12. Schema validation of emitted gating artifact
# ---------------------------------------------------------------------------


class TestSchemaValidation:
    def test_allow_decision_passes_schema(self):
        result = run_slo_gating(_allow_decision(stage="observe"), stage="observe")
        assert result["schema_errors"] == []

    def test_warn_observe_passes_schema(self):
        result = run_slo_gating(_warn_decision(stage="observe"), stage="observe")
        assert result["schema_errors"] == []

    def test_fail_decision_passes_schema(self):
        result = run_slo_gating(_fail_decision(), stage="synthesis")
        assert result["schema_errors"] == []

    def test_malformed_input_passes_schema(self):
        """Even failure artifacts must conform to the schema."""
        result = run_slo_gating("bad input", stage="observe")
        assert result["schema_errors"] == []

    def test_gating_decision_id_pattern(self):
        result = run_slo_gating(_allow_decision(), stage="observe")
        gd = result["gating_decision"]
        import re
        assert re.match(r"^GATE-[A-Z0-9]+$", gd["gating_decision_id"])

    def test_contract_version_present(self):
        result = run_slo_gating(_allow_decision(), stage="observe")
        assert result["gating_decision"]["contract_version"] == CONTRACT_VERSION


# ---------------------------------------------------------------------------
# 13. CLI exit code 0 (proceed)
# ---------------------------------------------------------------------------


class TestCLIExitCode0:
    def test_cli_exit_0_for_proceed(self, tmp_path):
        decision = _allow_decision(stage="observe")
        decision_file = tmp_path / "enforcement.json"
        decision_file.write_text(json.dumps(decision), encoding="utf-8")
        output_file = tmp_path / "gating.json"
        code = gating_main([str(decision_file), "--stage", "observe", "--output", str(output_file)])
        assert code == 0


# ---------------------------------------------------------------------------
# 14. CLI exit code 1 (proceed_with_warning)
# ---------------------------------------------------------------------------


class TestCLIExitCode1:
    def test_cli_exit_1_for_proceed_with_warning(self, tmp_path):
        decision = _warn_decision(stage="observe")
        decision_file = tmp_path / "enforcement.json"
        decision_file.write_text(json.dumps(decision), encoding="utf-8")
        output_file = tmp_path / "gating.json"
        code = gating_main([str(decision_file), "--stage", "observe", "--output", str(output_file)])
        assert code == 1


# ---------------------------------------------------------------------------
# 15. CLI exit code 2 (halt)
# ---------------------------------------------------------------------------


class TestCLIExitCode2:
    def test_cli_exit_2_for_halt_on_fail(self, tmp_path):
        decision = _fail_decision()
        decision_file = tmp_path / "enforcement.json"
        decision_file.write_text(json.dumps(decision), encoding="utf-8")
        output_file = tmp_path / "gating.json"
        code = gating_main([str(decision_file), "--stage", "observe", "--output", str(output_file)])
        assert code == 2

    def test_cli_exit_2_for_warning_at_decision_bearing(self, tmp_path):
        decision = _warn_decision(stage="synthesis")
        decision_file = tmp_path / "enforcement.json"
        decision_file.write_text(json.dumps(decision), encoding="utf-8")
        output_file = tmp_path / "gating.json"
        code = gating_main(
            [str(decision_file), "--stage", "synthesis", "--output", str(output_file)]
        )
        assert code == 2


# ---------------------------------------------------------------------------
# 16. CLI exit code 3 (error)
# ---------------------------------------------------------------------------


class TestCLIExitCode3:
    def test_cli_exit_3_missing_path(self):
        code = gating_main(["/nonexistent/path/decision.json"])
        assert code == 3

    def test_cli_exit_3_no_arguments(self):
        code = gating_main([])
        assert code == 3

    def test_cli_exit_3_invalid_json(self, tmp_path):
        bad_file = tmp_path / "bad.json"
        bad_file.write_text("not valid json{{", encoding="utf-8")
        code = gating_main([str(bad_file)])
        assert code == 3


# ---------------------------------------------------------------------------
# 17. Deterministic gating reason code assignment
# ---------------------------------------------------------------------------


class TestDeterministicReasonCode:
    def test_allow_always_enforcement_allow(self):
        codes = set()
        for _ in range(5):
            result = run_slo_gating(_allow_decision(), stage="observe", evaluated_at=_TS)
            codes.add(result["gating_decision"]["gating_reason_code"])
        assert codes == {REASON_ENFORCEMENT_ALLOW}

    def test_warn_observe_always_warning_allowed(self):
        codes = set()
        for _ in range(5):
            result = run_slo_gating(_warn_decision(), stage="observe", evaluated_at=_TS)
            codes.add(result["gating_decision"]["gating_reason_code"])
        assert codes == {REASON_ENFORCEMENT_WARNING_ALLOWED}

    def test_warn_synthesis_always_blocked(self):
        codes = set()
        for _ in range(5):
            result = run_slo_gating(_warn_decision(), stage="synthesis", evaluated_at=_TS)
            codes.add(result["gating_decision"]["gating_reason_code"])
        assert codes == {REASON_ENFORCEMENT_WARNING_BLOCKED_BY_STAGE}

    def test_all_known_reason_codes_valid(self):
        for code in KNOWN_GATING_REASON_CODES:
            assert isinstance(code, str)
            assert code  # not empty


# ---------------------------------------------------------------------------
# 18. Recommended action mapping correctness
# ---------------------------------------------------------------------------


class TestRecommendedActionMapping:
    def test_proceed_action_for_allow(self):
        result = run_slo_gating(_allow_decision())
        assert result["gating_decision"]["recommended_action"] == ACTION_PROCEED

    def test_monitoring_for_proceed_with_warning(self):
        result = run_slo_gating(_warn_decision(), stage="observe")
        assert result["gating_decision"]["recommended_action"] == ACTION_PROCEED_WITH_MONITORING

    def test_repair_lineage_when_lineage_invalid(self):
        # _fail_decision already defaults lineage_valid=False (strict mode)
        result = run_slo_gating(_fail_decision(), stage="synthesis")
        assert result["gating_decision"]["recommended_action"] == ACTION_HALT_AND_REPAIR_LINEAGE

    def test_rerun_registry_when_degraded(self):
        result = run_slo_gating(
            _enforcement_decision(
                decision_status="fail",
                reason_code="strict_invalid_lineage",
                ti=0.0,
                lineage_mode="degraded",
                lineage_defaulted=True,
                lineage_valid=None,
                errors=["degraded fail"],
            ),
            stage="synthesis",
        )
        assert result["gating_decision"]["recommended_action"] == ACTION_HALT_AND_RERUN_WITH_REGISTRY

    def test_escalate_for_malformed(self):
        result = run_slo_gating(None)
        assert result["gating_decision"]["recommended_action"] == ACTION_HALT_AND_ESCALATE

    def test_escalate_for_inconsistent(self):
        result = run_slo_gating(_allow_decision(errors=["err"]))
        assert result["gating_decision"]["recommended_action"] == ACTION_HALT_AND_ESCALATE

    def test_all_recommended_actions_valid(self):
        for action in KNOWN_RECOMMENDED_ACTIONS:
            assert isinstance(action, str)
            assert action


# ---------------------------------------------------------------------------
# 19. Stage override behavior
# ---------------------------------------------------------------------------


class TestStageOverride:
    def test_override_from_observe_to_synthesis(self):
        """Warn decision embedded in observe scope, but override to synthesis → halt."""
        decision = _warn_decision(stage="observe")
        result = run_slo_gating(decision, stage="synthesis")
        assert result["gating_outcome"] == OUTCOME_HALT

    def test_override_from_synthesis_to_observe(self):
        """Warn decision embedded in synthesis scope, but override to observe → proceed_with_warning."""
        decision = _warn_decision(stage="synthesis")
        result = run_slo_gating(decision, stage="observe")
        assert result["gating_outcome"] == OUTCOME_PROCEED_WITH_WARNING

    def test_override_stage_is_recorded_in_artifact(self):
        decision = _warn_decision(stage="observe")
        result = run_slo_gating(decision, stage="synthesis")
        assert result["gating_decision"]["stage"] == "synthesis"

    def test_no_override_uses_enforcement_scope(self):
        decision = _warn_decision(stage="observe")
        result = run_slo_gating(decision)
        assert result["gating_decision"]["stage"] == "observe"
        assert result["gating_outcome"] == OUTCOME_PROCEED_WITH_WARNING

    def test_no_scope_no_override_unknown_stage_fails_closed(self):
        decision = _warn_decision(stage=None)
        result = run_slo_gating(decision)
        # No stage embedded and no override → fail closed
        assert result["gating_outcome"] == OUTCOME_HALT


# ---------------------------------------------------------------------------
# 20. Integration with run_slo_enforcement output
# ---------------------------------------------------------------------------


class TestIntegrationWithEnforcement:
    def _slo_artifact(self, ti: float, mode: str = "strict",
                      defaulted: bool = False, lineage_valid: Optional[bool] = True) -> Dict[str, Any]:
        return {
            "artifact_id": "INT-TEST-001",
            "artifact_type": "slo_evaluation",
            "traceability_integrity_sli": ti,
            "lineage_validation_mode": mode,
            "lineage_defaulted": defaulted,
            "lineage_valid": lineage_valid,
        }

    def test_enforcement_then_gating_allow(self):
        raw = self._slo_artifact(ti=1.0)
        enforcement_result = run_slo_enforcement(raw, policy="permissive", stage="observe")
        gating_result = run_slo_gating(enforcement_result, stage="observe")
        assert gating_result["gating_outcome"] == OUTCOME_PROCEED

    def test_enforcement_then_gating_warn_observe(self):
        raw = self._slo_artifact(ti=0.5, mode="degraded", defaulted=True, lineage_valid=None)
        enforcement_result = run_slo_enforcement(raw, policy="permissive", stage="observe")
        gating_result = run_slo_gating(enforcement_result, stage="observe")
        assert gating_result["gating_outcome"] == OUTCOME_PROCEED_WITH_WARNING

    def test_enforcement_then_gating_warn_synthesis(self):
        raw = self._slo_artifact(ti=0.5, mode="degraded", defaulted=True, lineage_valid=None)
        enforcement_result = run_slo_enforcement(raw, policy="permissive", stage="synthesis")
        gating_result = run_slo_gating(enforcement_result, stage="synthesis")
        assert gating_result["gating_outcome"] == OUTCOME_HALT

    def test_enforcement_then_gating_fail(self):
        raw = self._slo_artifact(ti=0.0, lineage_valid=False)
        enforcement_result = run_slo_enforcement(raw, policy="permissive")
        gating_result = run_slo_gating(enforcement_result, stage="synthesis")
        assert gating_result["gating_outcome"] == OUTCOME_HALT

    def test_wrapped_enforcement_result_unwrapped(self):
        """run_slo_gating handles the {enforcement_decision: ...} wrapper from run_slo_enforcement."""
        raw = self._slo_artifact(ti=1.0)
        enforcement_result = run_slo_enforcement(raw, policy="permissive")
        # enforcement_result has key 'enforcement_decision'
        assert "enforcement_decision" in enforcement_result
        gating_result = run_slo_gating(enforcement_result, stage="observe")
        assert gating_result["gating_outcome"] == OUTCOME_PROCEED


# ---------------------------------------------------------------------------
# 21. No uncaught exceptions on malformed input
# ---------------------------------------------------------------------------


class TestNoCrashesMalformedInput:
    @pytest.mark.parametrize("bad_input", [
        None,
        "",
        "just a string",
        42,
        3.14,
        [],
        [{"a": 1}],
        {"decision_status": "allow"},  # missing required fields
        {"decision_id": None, "artifact_id": None, "enforcement_policy": None,
         "decision_status": None, "decision_reason_code": None},
        {"decision_status": "allow", "errors": ["err"]},  # contradictory
    ])
    def test_no_exception(self, bad_input):
        try:
            result = run_slo_gating(bad_input)
            assert "gating_outcome" in result
        except Exception as exc:  # noqa: BLE001
            pytest.fail(f"run_slo_gating raised an exception on input {bad_input!r}: {exc}")


# ---------------------------------------------------------------------------
# 22. Governed config/schema validation
# ---------------------------------------------------------------------------


class TestGovernedConfigSchema:
    def test_gating_rules_file_exists(self):
        assert _GATING_RULES_PATH.exists(), f"Gating rules file not found: {_GATING_RULES_PATH}"

    def test_gating_rules_schema_exists(self):
        assert _GATING_RULES_SCHEMA_PATH.exists()

    def test_gating_decision_schema_exists(self):
        assert _GATING_SCHEMA_PATH.exists()

    def test_gating_rules_validates_against_schema(self):
        from jsonschema import Draft202012Validator, FormatChecker
        schema = _load_schema(_GATING_RULES_SCHEMA_PATH)
        data = _load_schema(_GATING_RULES_PATH)
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        errors = list(validator.iter_errors(data))
        assert errors == [], f"Gating rules failed schema validation: {errors}"

    def test_gating_rules_has_all_known_stages(self):
        data = _load_schema(_GATING_RULES_PATH)
        stage_keys = set(data["stages"].keys())
        assert KNOWN_STAGES == stage_keys, f"Missing stages in gating rules: {KNOWN_STAGES - stage_keys}"

    def test_gating_decision_schema_draft_2020_12(self):
        schema = _load_schema(_GATING_SCHEMA_PATH)
        assert "2020-12" in schema.get("$schema", "")

    def test_gating_rules_schema_draft_2020_12(self):
        schema = _load_schema(_GATING_RULES_SCHEMA_PATH)
        assert "2020-12" in schema.get("$schema", "")


# ---------------------------------------------------------------------------
# 23. Outputs include stage, enforcement status, gating outcome, reason code
# ---------------------------------------------------------------------------


class TestOutputCompleteness:
    def test_artifact_has_stage(self):
        result = run_slo_gating(_allow_decision(), stage="synthesis")
        assert result["gating_decision"]["stage"] == "synthesis"

    def test_artifact_has_enforcement_status(self):
        result = run_slo_gating(_allow_decision(), stage="observe")
        assert result["gating_decision"]["enforcement_decision_status"] == "allow"

    def test_artifact_has_gating_outcome(self):
        result = run_slo_gating(_allow_decision(), stage="observe")
        assert result["gating_decision"]["gating_outcome"] in KNOWN_GATING_OUTCOMES

    def test_artifact_has_reason_code(self):
        result = run_slo_gating(_allow_decision(), stage="observe")
        assert result["gating_decision"]["gating_reason_code"] in KNOWN_GATING_REASON_CODES

    def test_artifact_has_source_decision_id(self):
        d = _allow_decision(decision_id="ENF-XYZ999")
        result = run_slo_gating(d, stage="observe")
        assert result["gating_decision"]["source_decision_id"] == "ENF-XYZ999"

    def test_artifact_has_artifact_id(self):
        d = _allow_decision(artifact_id="MYART-001")
        result = run_slo_gating(d, stage="observe")
        assert result["gating_decision"]["artifact_id"] == "MYART-001"

    def test_artifact_has_enforcement_policy(self):
        d = _allow_decision(policy="decision_grade")
        result = run_slo_gating(d, stage="observe")
        assert result["gating_decision"]["enforcement_policy"] == "decision_grade"

    def test_artifact_has_ti_sli(self):
        result = run_slo_gating(_allow_decision(), stage="observe")
        assert result["gating_decision"]["traceability_integrity_sli"] == 1.0

    def test_artifact_has_evaluated_at(self):
        result = run_slo_gating(_allow_decision(), stage="observe", evaluated_at=_TS)
        assert result["gating_decision"]["evaluated_at"] == _TS


# ---------------------------------------------------------------------------
# 24. Decision-bearing stages fail closed on warnings by default
# ---------------------------------------------------------------------------


class TestDecisionBearingFailClosed:
    @pytest.mark.parametrize("stage", [STAGE_RECOMMEND, STAGE_SYNTHESIS, STAGE_EXPORT])
    def test_warning_halts_at_decision_bearing_stage(self, stage):
        result = run_slo_gating(_warn_decision(), stage=stage)
        assert result["gating_outcome"] == OUTCOME_HALT

    @pytest.mark.parametrize("stage", [STAGE_RECOMMEND, STAGE_SYNTHESIS, STAGE_EXPORT])
    def test_allow_proceeds_at_decision_bearing_stage(self, stage):
        result = run_slo_gating(_allow_decision(), stage=stage)
        assert result["gating_outcome"] == OUTCOME_PROCEED

    def test_stage_posture_decision_bearing_flags(self):
        for s in (STAGE_RECOMMEND, STAGE_SYNTHESIS, STAGE_EXPORT):
            posture = resolve_stage_gating_posture(s)
            assert posture["decision_bearing"] is True
            assert posture["warnings_allowed"] is False

    def test_stage_posture_permissive_flags(self):
        for s in (STAGE_OBSERVE, STAGE_INTERPRET):
            posture = resolve_stage_gating_posture(s)
            assert posture["decision_bearing"] is False
            assert posture["warnings_allowed"] is True


# ---------------------------------------------------------------------------
# Extra: unit-level function tests
# ---------------------------------------------------------------------------


class TestNormalizeGatingInputs:
    def test_bare_decision_dict(self):
        d = _allow_decision()
        result = normalize_gating_inputs(d)
        assert result["decision_status"] == "allow"

    def test_wrapped_enforcement_result(self):
        """Handles {enforcement_decision: {...}} wrapper."""
        d = {"enforcement_decision": _allow_decision(), "decision_status": "ignored"}
        result = normalize_gating_inputs(d)
        assert result["decision_status"] == "allow"

    def test_non_dict_returns_malformed_marker(self):
        result = normalize_gating_inputs("not a dict")
        assert result.get("_malformed") is True

    def test_none_returns_malformed_marker(self):
        result = normalize_gating_inputs(None)
        assert result.get("_malformed") is True


class TestValidateEnforcementDecision:
    def test_valid_decision_passes(self):
        valid, reason, errors = validate_enforcement_decision_for_gating(_allow_decision())
        assert valid is True
        assert errors == []

    def test_missing_decision_status(self):
        d = _allow_decision()
        del d["decision_status"]
        valid, reason, errors = validate_enforcement_decision_for_gating(d)
        assert valid is False
        assert reason == REASON_MISSING_ENFORCEMENT_STATUS

    def test_unknown_status(self):
        d = _allow_decision()
        d["decision_status"] = "nope"
        valid, reason, errors = validate_enforcement_decision_for_gating(d)
        assert valid is False
        assert reason == REASON_UNKNOWN_ENFORCEMENT_STATUS

    def test_allow_with_errors_inconsistency(self):
        d = _allow_decision(errors=["bad"])
        valid, reason, errors = validate_enforcement_decision_for_gating(d)
        assert valid is False
        assert reason == REASON_INCONSISTENT_ENFORCEMENT_PAYLOAD


class TestEvaluateGatingOutcome:
    def test_allow_proceeds(self):
        assert evaluate_gating_outcome("allow", True, True) == OUTCOME_PROCEED
        assert evaluate_gating_outcome("allow", False, True) == OUTCOME_PROCEED

    def test_warning_with_allowed(self):
        assert evaluate_gating_outcome("allow_with_warning", True, True) == OUTCOME_PROCEED_WITH_WARNING

    def test_warning_without_allowed(self):
        assert evaluate_gating_outcome("allow_with_warning", False, True) == OUTCOME_HALT

    def test_fail_halts(self):
        assert evaluate_gating_outcome("fail", True, True) == OUTCOME_HALT
        assert evaluate_gating_outcome("fail", False, True) == OUTCOME_HALT

    def test_invalid_inputs_halt(self):
        assert evaluate_gating_outcome("allow", True, False) == OUTCOME_HALT


class TestDescribeStageGatingPosture:
    def test_known_stage(self):
        info = describe_stage_gating_posture("synthesis")
        assert info["stage"] == "synthesis"
        assert info["stage_known"] is True
        assert info["decision_bearing"] is True
        assert info["warnings_allowed"] is False

    def test_unknown_stage(self):
        info = describe_stage_gating_posture("nonexistent_stage")
        assert info["stage_known"] is False
        assert info["warnings_allowed"] is False  # fail-closed

    def test_none_stage(self):
        info = describe_stage_gating_posture(None)
        assert info["stage_known"] is False


class TestSummarizeGatingDecision:
    def test_summary_contains_outcome(self):
        result = run_slo_gating(_allow_decision(), stage="observe")
        summary = summarize_gating_decision(result)
        assert "proceed" in summary

    def test_summary_contains_stage(self):
        result = run_slo_gating(_allow_decision(), stage="synthesis")
        summary = summarize_gating_decision(result)
        assert "synthesis" in summary

    def test_summary_contains_reason_code(self):
        result = run_slo_gating(_allow_decision(), stage="observe")
        summary = summarize_gating_decision(result)
        assert "enforcement_allow" in summary


class TestCLIShowStagePosture:
    def test_show_all_stages(self, capsys):
        code = gating_main(["--show-stage-posture"])
        assert code == 0

    def test_show_specific_stage(self, capsys):
        code = gating_main(["--show-stage-posture", "--stage", "synthesis"])
        assert code == 0

    def test_cli_writes_output_file(self, tmp_path):
        decision = _allow_decision(stage="observe")
        decision_file = tmp_path / "enforcement.json"
        decision_file.write_text(json.dumps(decision), encoding="utf-8")
        output_file = tmp_path / "gating.json"
        code = gating_main([str(decision_file), "--stage", "observe", "--output", str(output_file)])
        assert code == 0
        assert output_file.exists()
        artifact = json.loads(output_file.read_text(encoding="utf-8"))
        assert "gating_decision_id" in artifact
        assert artifact["gating_outcome"] == OUTCOME_PROCEED
