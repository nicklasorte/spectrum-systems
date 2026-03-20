"""Tests for the Control-Signal Emission Layer (BN.5).

Covers all requirements from the problem statement:
 1.  clean continue emits continuation_mode=continue
 2.  proceed_with_warning emits continuation_mode=continue_with_monitoring
 3.  blocked traceability issue emits stop_and_repair
 4.  malformed/inconsistent input emits stop_and_escalate
 5.  decision-bearing clean stage can set publication_allowed=true
 6.  decision-bearing warning state cannot set publication_allowed=true
 7.  decision_grade_allowed false when gating halts
 8.  human_review_required true for relevant warning states
 9.  escalation_required true for malformed/inconsistent states
10.  rerun_recommended true when rerun is appropriate
11.  required_validators populated deterministically
12.  repair_actions populated deterministically
13.  control_signal_reason_codes deterministic
14.  schema validation of updated control-chain artifact
15.  CLI summary includes control signal fields
16.  no uncaught exceptions on malformed inputs
17.  backward compatibility with existing control-chain flows
18.  continue path does not emit contradictory stop signals
19.  stop path does not emit publication_allowed=true
20.  decision-bearing blocked states fail closed
21.  additive schema change does not break existing generation path
22.  required_inputs emitted when inputs are missing or inferred missing
23.  stage override behavior remains auditable
24.  signal derivation remains deterministic across repeated runs
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

from spectrum_systems.modules.runtime.control_signals import (  # noqa: E402
    CONTINUATION_MODE_CONTINUE,
    CONTINUATION_MODE_CONTINUE_WITH_MONITORING,
    CONTINUATION_MODE_STOP,
    CONTINUATION_MODE_STOP_AND_ESCALATE,
    CONTINUATION_MODE_STOP_AND_REPAIR,
    CONTINUATION_MODE_STOP_AND_RERUN,
    KNOWN_CONTINUATION_MODES,
    KNOWN_CS_REASON_CODES,
    KNOWN_VALIDATORS,
    KNOWN_REPAIR_ACTIONS,
    CS_REASON_GATING_HALT,
    CS_REASON_MISSING_TRACEABILITY,
    CS_REASON_INVALID_LINEAGE,
    CS_REASON_MALFORMED_CONTROL_INPUT,
    CS_REASON_ESCALATION_REQUIRED_FOR_DECISION_STAGE,
    CS_REASON_HUMAN_REVIEW_REQUIRED_FOR_WARNING_STATE,
    CS_REASON_RERUN_POSSIBLE_AFTER_REPAIR,
    CS_REASON_DECISION_STAGE_REQUIRES_STRICT_VALIDATION,
    CS_REASON_DEGRADED_LINEAGE_NOT_ALLOWED,
    REPAIR_RESTORE_MISSING_LINEAGE,
    REPAIR_RERUN_WITH_STRICT_VALIDATION,
    REPAIR_REBUILD_WITH_REGISTRY,
    REPAIR_ESCALATE_FOR_MANUAL_REVIEW,
    REPAIR_MISSING_INPUTS,
    VALIDATOR_TRACEABILITY_INTEGRITY,
    VALIDATOR_SCHEMA_CONFORMANCE,
    VALIDATOR_RUNTIME_COMPATIBILITY,
    VALIDATOR_BUNDLE_CONTRACT,
    VALIDATOR_ARTIFACT_COMPLETENESS,
    VALIDATOR_CROSS_ARTIFACT_CONSISTENCY,
    build_control_signals,
    derive_control_signals,
    derive_continuation_mode,
    derive_required_validators,
    derive_repair_actions,
    derive_publication_permissions,
    derive_control_signal_reason_codes,
    explain_blocking_requirements,
    list_required_followups,
    summarize_control_signals,
    validate_control_signals,
)
from spectrum_systems.modules.runtime.control_chain import (  # noqa: E402
    REASON_CONTINUE,
    REASON_CONTINUE_WITH_WARNING,
    REASON_BLOCKED_BY_GATING,
    REASON_BLOCKED_BY_MISSING_GATING,
    REASON_BLOCKED_BY_MALFORMED_INPUT,
    REASON_BLOCKED_BY_INCONSISTENT_STATE,
    run_control_chain,
    validate_control_chain_decision,
    build_control_chain_decision,
)
from spectrum_systems.modules.runtime.decision_gating import (  # noqa: E402
    STAGE_OBSERVE,
    STAGE_INTERPRET,
    STAGE_RECOMMEND,
    STAGE_SYNTHESIS,
    STAGE_EXPORT,
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


def _clean_cs(stage: Optional[str] = None) -> Dict[str, Any]:
    """Derive control signals for a clean continue case."""
    return derive_control_signals(
        continuation_allowed=True,
        primary_reason_code=REASON_CONTINUE,
        gating_outcome="proceed",
        enforcement_status="allow",
        lineage_defaulted=False,
        lineage_valid=True,
        stage=stage,
    )


def _warning_cs(stage: Optional[str] = None) -> Dict[str, Any]:
    """Derive control signals for a warning (continue_with_monitoring) case."""
    return derive_control_signals(
        continuation_allowed=True,
        primary_reason_code=REASON_CONTINUE_WITH_WARNING,
        gating_outcome="proceed_with_warning",
        enforcement_status="allow_with_warning",
        lineage_defaulted=True,
        lineage_valid=None,
        stage=stage,
    )


def _blocked_lineage_cs(stage: Optional[str] = None) -> Dict[str, Any]:
    """Derive control signals for a blocked lineage case."""
    return derive_control_signals(
        continuation_allowed=False,
        primary_reason_code=REASON_BLOCKED_BY_GATING,
        gating_outcome="halt",
        enforcement_status="allow_with_warning",
        lineage_defaulted=True,
        lineage_valid=None,
        stage=stage,
    )


def _blocked_invalid_lineage_cs(stage: Optional[str] = None) -> Dict[str, Any]:
    """Derive control signals for a blocked invalid lineage case."""
    return derive_control_signals(
        continuation_allowed=False,
        primary_reason_code=REASON_BLOCKED_BY_GATING,
        gating_outcome="halt",
        enforcement_status="fail",
        lineage_defaulted=False,
        lineage_valid=False,
        stage=stage,
    )


def _malformed_cs(stage: Optional[str] = None) -> Dict[str, Any]:
    """Derive control signals for a malformed/inconsistent input case."""
    return derive_control_signals(
        continuation_allowed=False,
        primary_reason_code=REASON_BLOCKED_BY_MALFORMED_INPUT,
        gating_outcome=None,
        enforcement_status=None,
        lineage_defaulted=None,
        lineage_valid=None,
        stage=stage,
    )


def _missing_gating_cs(stage: Optional[str] = STAGE_SYNTHESIS) -> Dict[str, Any]:
    """Derive control signals for a missing gating (decision stage) case."""
    return derive_control_signals(
        continuation_allowed=False,
        primary_reason_code=REASON_BLOCKED_BY_MISSING_GATING,
        gating_outcome=None,
        enforcement_status=None,
        lineage_defaulted=None,
        lineage_valid=None,
        stage=stage,
    )


# ---------------------------------------------------------------------------
# 1. Clean continue emits continuation_mode=continue
# ---------------------------------------------------------------------------


class TestCleanContinue:
    def test_continuation_mode_continue(self):
        cs = _clean_cs()
        assert cs["continuation_mode"] == CONTINUATION_MODE_CONTINUE

    def test_no_repair_actions(self):
        cs = _clean_cs()
        assert cs["repair_actions"] == []

    def test_no_required_validators(self):
        cs = _clean_cs()
        assert cs["required_validators"] == []

    def test_no_reason_codes(self):
        cs = _clean_cs()
        assert cs["control_signal_reason_codes"] == []

    def test_publication_allowed_non_decision_stage(self):
        cs = _clean_cs(stage=STAGE_OBSERVE)
        assert cs["publication_allowed"] is True

    def test_decision_grade_allowed_non_decision_stage(self):
        cs = _clean_cs(stage=STAGE_OBSERVE)
        assert cs["decision_grade_allowed"] is True

    def test_rerun_not_recommended(self):
        cs = _clean_cs()
        assert cs["rerun_recommended"] is False

    def test_human_review_not_required(self):
        cs = _clean_cs()
        assert cs["human_review_required"] is False

    def test_escalation_not_required(self):
        cs = _clean_cs()
        assert cs["escalation_required"] is False


# ---------------------------------------------------------------------------
# 2. proceed_with_warning emits continuation_mode=continue_with_monitoring
# ---------------------------------------------------------------------------


class TestWarningContinue:
    def test_continuation_mode(self):
        cs = _warning_cs()
        assert cs["continuation_mode"] == CONTINUATION_MODE_CONTINUE_WITH_MONITORING

    def test_publication_not_allowed_without_stage(self):
        # No stage means non-decision bearing — allowed for warning at non-decision stage
        cs = _warning_cs(stage=STAGE_OBSERVE)
        # Warning at non-decision stage: publication disallowed (not a clean continue)
        assert cs["publication_allowed"] is False

    def test_decision_grade_not_allowed_for_warning(self):
        cs = _warning_cs(stage=STAGE_OBSERVE)
        assert cs["decision_grade_allowed"] is False

    def test_human_review_required_at_decision_stage(self):
        cs = _warning_cs(stage=STAGE_SYNTHESIS)
        assert cs["human_review_required"] is True

    def test_human_review_not_required_at_non_decision_stage(self):
        cs = _warning_cs(stage=STAGE_OBSERVE)
        assert cs["human_review_required"] is False

    def test_reason_code_human_review_for_warning(self):
        cs = _warning_cs(stage=STAGE_SYNTHESIS)
        assert CS_REASON_HUMAN_REVIEW_REQUIRED_FOR_WARNING_STATE in cs["control_signal_reason_codes"]

    def test_traceability_validator_added(self):
        cs = _warning_cs()
        assert VALIDATOR_TRACEABILITY_INTEGRITY in cs["required_validators"]


# ---------------------------------------------------------------------------
# 3. Blocked traceability issue emits stop_and_repair / stop_and_rerun
# ---------------------------------------------------------------------------


class TestBlockedTraceability:
    def test_degraded_lineage_emits_stop_and_rerun(self):
        # degraded lineage + allow_with_warning enforcement -> stop_and_rerun
        cs = _blocked_lineage_cs()
        assert cs["continuation_mode"] == CONTINUATION_MODE_STOP_AND_RERUN

    def test_invalid_lineage_emits_stop_and_repair(self):
        cs = _blocked_invalid_lineage_cs()
        assert cs["continuation_mode"] == CONTINUATION_MODE_STOP_AND_REPAIR

    def test_publication_not_allowed(self):
        cs = _blocked_lineage_cs()
        assert cs["publication_allowed"] is False

    def test_traceability_required(self):
        cs = _blocked_lineage_cs()
        assert cs["traceability_required"] is True

    def test_restore_lineage_in_repair_actions(self):
        cs = _blocked_lineage_cs()
        assert REPAIR_RESTORE_MISSING_LINEAGE in cs["repair_actions"]

    def test_gating_halt_reason_code(self):
        cs = _blocked_lineage_cs()
        assert CS_REASON_GATING_HALT in cs["control_signal_reason_codes"]

    def test_missing_traceability_reason_code(self):
        cs = _blocked_lineage_cs()
        assert CS_REASON_MISSING_TRACEABILITY in cs["control_signal_reason_codes"]

    def test_rebuild_with_registry_in_repair(self):
        cs = _blocked_lineage_cs()
        assert REPAIR_REBUILD_WITH_REGISTRY in cs["repair_actions"]

    def test_rerun_recommended_for_degraded(self):
        cs = _blocked_lineage_cs()
        assert cs["rerun_recommended"] is True


# ---------------------------------------------------------------------------
# 4. Malformed/inconsistent input emits stop_and_escalate
# ---------------------------------------------------------------------------


class TestMalformedInput:
    def test_continuation_mode_stop_and_escalate(self):
        cs = _malformed_cs()
        assert cs["continuation_mode"] == CONTINUATION_MODE_STOP_AND_ESCALATE

    def test_escalation_required(self):
        cs = _malformed_cs()
        assert cs["escalation_required"] is True

    def test_publication_not_allowed(self):
        cs = _malformed_cs()
        assert cs["publication_allowed"] is False

    def test_decision_grade_not_allowed(self):
        cs = _malformed_cs()
        assert cs["decision_grade_allowed"] is False

    def test_malformed_reason_code(self):
        cs = _malformed_cs()
        assert CS_REASON_MALFORMED_CONTROL_INPUT in cs["control_signal_reason_codes"]

    def test_escalate_action_in_repair(self):
        cs = _malformed_cs()
        assert REPAIR_ESCALATE_FOR_MANUAL_REVIEW in cs["repair_actions"]

    def test_inconsistent_state_also_escalates(self):
        cs = derive_control_signals(
            continuation_allowed=False,
            primary_reason_code=REASON_BLOCKED_BY_INCONSISTENT_STATE,
            gating_outcome=None,
            enforcement_status=None,
            lineage_defaulted=None,
            lineage_valid=None,
            stage=None,
        )
        assert cs["continuation_mode"] == CONTINUATION_MODE_STOP_AND_ESCALATE
        assert cs["escalation_required"] is True


# ---------------------------------------------------------------------------
# 5. Decision-bearing clean stage can set publication_allowed=true
# ---------------------------------------------------------------------------


class TestDecisionBearingClean:
    @pytest.mark.parametrize("stage", [STAGE_RECOMMEND, STAGE_SYNTHESIS, STAGE_EXPORT])
    def test_publication_allowed_clean_proceed(self, stage):
        cs = derive_control_signals(
            continuation_allowed=True,
            primary_reason_code=REASON_CONTINUE,
            gating_outcome="proceed",
            enforcement_status="allow",
            lineage_defaulted=False,
            lineage_valid=True,
            stage=stage,
        )
        assert cs["publication_allowed"] is True

    @pytest.mark.parametrize("stage", [STAGE_RECOMMEND, STAGE_SYNTHESIS, STAGE_EXPORT])
    def test_decision_grade_allowed_clean_proceed(self, stage):
        cs = derive_control_signals(
            continuation_allowed=True,
            primary_reason_code=REASON_CONTINUE,
            gating_outcome="proceed",
            enforcement_status="allow",
            lineage_defaulted=False,
            lineage_valid=True,
            stage=stage,
        )
        assert cs["decision_grade_allowed"] is True


# ---------------------------------------------------------------------------
# 6. Decision-bearing warning state cannot set publication_allowed=true
# ---------------------------------------------------------------------------


class TestDecisionBearingWarning:
    @pytest.mark.parametrize("stage", [STAGE_RECOMMEND, STAGE_SYNTHESIS, STAGE_EXPORT])
    def test_publication_not_allowed_for_warning(self, stage):
        cs = _warning_cs(stage=stage)
        assert cs["publication_allowed"] is False

    @pytest.mark.parametrize("stage", [STAGE_RECOMMEND, STAGE_SYNTHESIS, STAGE_EXPORT])
    def test_decision_grade_not_allowed_for_warning(self, stage):
        cs = _warning_cs(stage=stage)
        assert cs["decision_grade_allowed"] is False

    @pytest.mark.parametrize("stage", [STAGE_RECOMMEND, STAGE_SYNTHESIS, STAGE_EXPORT])
    def test_human_review_required_at_decision_stage_warning(self, stage):
        cs = _warning_cs(stage=stage)
        assert cs["human_review_required"] is True


# ---------------------------------------------------------------------------
# 7. decision_grade_allowed false when gating halts
# ---------------------------------------------------------------------------


class TestDecisionGradeBlockedOnHalt:
    @pytest.mark.parametrize("stage", [STAGE_RECOMMEND, STAGE_SYNTHESIS, STAGE_EXPORT, STAGE_OBSERVE])
    def test_decision_grade_false_on_halt(self, stage):
        cs = _blocked_lineage_cs(stage=stage)
        assert cs["decision_grade_allowed"] is False

    def test_decision_grade_false_on_missing_gating(self):
        cs = _missing_gating_cs()
        assert cs["decision_grade_allowed"] is False


# ---------------------------------------------------------------------------
# 8. human_review_required true for relevant warning states
# ---------------------------------------------------------------------------


class TestHumanReviewRequired:
    def test_human_review_at_synthesis_warning(self):
        cs = _warning_cs(stage=STAGE_SYNTHESIS)
        assert cs["human_review_required"] is True

    def test_human_review_at_recommend_warning(self):
        cs = _warning_cs(stage=STAGE_RECOMMEND)
        assert cs["human_review_required"] is True

    def test_human_review_at_export_warning(self):
        cs = _warning_cs(stage=STAGE_EXPORT)
        assert cs["human_review_required"] is True

    def test_human_review_not_required_for_clean_continue(self):
        cs = _clean_cs(stage=STAGE_SYNTHESIS)
        assert cs["human_review_required"] is False

    def test_human_review_required_on_escalate(self):
        cs = _malformed_cs()
        assert cs["human_review_required"] is True


# ---------------------------------------------------------------------------
# 9. escalation_required true for malformed/inconsistent states
# ---------------------------------------------------------------------------


class TestEscalationRequired:
    def test_malformed_escalates(self):
        cs = _malformed_cs()
        assert cs["escalation_required"] is True

    def test_missing_gating_escalates(self):
        cs = _missing_gating_cs()
        assert cs["escalation_required"] is True

    def test_inconsistent_state_escalates(self):
        cs = derive_control_signals(
            continuation_allowed=False,
            primary_reason_code=REASON_BLOCKED_BY_INCONSISTENT_STATE,
            gating_outcome=None,
            enforcement_status=None,
            lineage_defaulted=None,
            lineage_valid=None,
            stage=None,
        )
        assert cs["escalation_required"] is True

    def test_clean_continue_does_not_escalate(self):
        cs = _clean_cs()
        assert cs["escalation_required"] is False

    def test_blocked_lineage_does_not_escalate(self):
        cs = _blocked_lineage_cs()
        assert cs["escalation_required"] is False


# ---------------------------------------------------------------------------
# 10. rerun_recommended true when rerun is appropriate
# ---------------------------------------------------------------------------


class TestRerunRecommended:
    def test_degraded_lineage_rerun(self):
        cs = _blocked_lineage_cs()
        assert cs["rerun_recommended"] is True

    def test_clean_continue_no_rerun(self):
        cs = _clean_cs()
        assert cs["rerun_recommended"] is False

    def test_malformed_no_rerun(self):
        cs = _malformed_cs()
        assert cs["rerun_recommended"] is False

    def test_invalid_lineage_no_rerun(self):
        cs = _blocked_invalid_lineage_cs()
        assert cs["rerun_recommended"] is False

    def test_reason_code_rerun_possible(self):
        cs = _blocked_lineage_cs()
        assert CS_REASON_RERUN_POSSIBLE_AFTER_REPAIR in cs["control_signal_reason_codes"]


# ---------------------------------------------------------------------------
# 11. required_validators populated deterministically
# ---------------------------------------------------------------------------


class TestRequiredValidators:
    def test_traceability_validator_on_blocked_lineage(self):
        cs = _blocked_lineage_cs()
        assert VALIDATOR_TRACEABILITY_INTEGRITY in cs["required_validators"]

    def test_schema_conformance_on_malformed(self):
        cs = _malformed_cs()
        assert VALIDATOR_SCHEMA_CONFORMANCE in cs["required_validators"]

    def test_runtime_compat_on_rerun(self):
        cs = _blocked_lineage_cs()
        assert VALIDATOR_RUNTIME_COMPATIBILITY in cs["required_validators"]

    def test_bundle_contract_on_escalate(self):
        cs = _malformed_cs()
        assert VALIDATOR_BUNDLE_CONTRACT in cs["required_validators"]

    def test_artifact_completeness_on_decision_blocked(self):
        cs = _blocked_lineage_cs(stage=STAGE_SYNTHESIS)
        assert VALIDATOR_ARTIFACT_COMPLETENESS in cs["required_validators"]

    def test_cross_artifact_on_decision_blocked(self):
        cs = _blocked_lineage_cs(stage=STAGE_SYNTHESIS)
        assert VALIDATOR_CROSS_ARTIFACT_CONSISTENCY in cs["required_validators"]

    def test_clean_continue_no_validators(self):
        cs = _clean_cs()
        assert cs["required_validators"] == []

    def test_deterministic_across_runs(self):
        cs1 = _blocked_lineage_cs(stage=STAGE_SYNTHESIS)
        cs2 = _blocked_lineage_cs(stage=STAGE_SYNTHESIS)
        assert cs1["required_validators"] == cs2["required_validators"]


# ---------------------------------------------------------------------------
# 12. repair_actions populated deterministically
# ---------------------------------------------------------------------------


class TestRepairActions:
    def test_restore_lineage_for_degraded(self):
        cs = _blocked_lineage_cs()
        assert REPAIR_RESTORE_MISSING_LINEAGE in cs["repair_actions"]

    def test_rebuild_with_registry_for_rerun(self):
        cs = _blocked_lineage_cs()
        assert REPAIR_REBUILD_WITH_REGISTRY in cs["repair_actions"]

    def test_rerun_with_strict_for_rerun(self):
        cs = _blocked_lineage_cs()
        assert REPAIR_RERUN_WITH_STRICT_VALIDATION in cs["repair_actions"]

    def test_escalate_action_for_malformed(self):
        cs = _malformed_cs()
        assert REPAIR_ESCALATE_FOR_MANUAL_REVIEW in cs["repair_actions"]

    def test_no_repair_actions_for_clean(self):
        cs = _clean_cs()
        assert cs["repair_actions"] == []

    def test_missing_inputs_action_for_missing_gating(self):
        cs = _missing_gating_cs()
        assert REPAIR_MISSING_INPUTS in cs["repair_actions"]

    def test_deterministic_across_runs(self):
        cs1 = _blocked_lineage_cs()
        cs2 = _blocked_lineage_cs()
        assert cs1["repair_actions"] == cs2["repair_actions"]


# ---------------------------------------------------------------------------
# 13. control_signal_reason_codes deterministic
# ---------------------------------------------------------------------------


class TestReasonCodes:
    def test_gating_halt_code(self):
        cs = _blocked_lineage_cs()
        assert CS_REASON_GATING_HALT in cs["control_signal_reason_codes"]

    def test_missing_traceability_code(self):
        cs = _blocked_lineage_cs()
        assert CS_REASON_MISSING_TRACEABILITY in cs["control_signal_reason_codes"]

    def test_invalid_lineage_code(self):
        cs = _blocked_invalid_lineage_cs()
        assert CS_REASON_INVALID_LINEAGE in cs["control_signal_reason_codes"]

    def test_malformed_code(self):
        cs = _malformed_cs()
        assert CS_REASON_MALFORMED_CONTROL_INPUT in cs["control_signal_reason_codes"]

    def test_escalation_code_for_decision_stage_malformed(self):
        cs = _missing_gating_cs(stage=STAGE_SYNTHESIS)
        assert CS_REASON_ESCALATION_REQUIRED_FOR_DECISION_STAGE in cs["control_signal_reason_codes"]

    def test_human_review_code_for_warning(self):
        cs = _warning_cs(stage=STAGE_SYNTHESIS)
        assert CS_REASON_HUMAN_REVIEW_REQUIRED_FOR_WARNING_STATE in cs["control_signal_reason_codes"]

    def test_decision_stage_strict_validation_code(self):
        cs = _blocked_lineage_cs(stage=STAGE_SYNTHESIS)
        assert CS_REASON_DECISION_STAGE_REQUIRES_STRICT_VALIDATION in cs["control_signal_reason_codes"]

    def test_degraded_lineage_not_allowed_code(self):
        cs = _blocked_lineage_cs(stage=STAGE_SYNTHESIS)
        assert CS_REASON_DEGRADED_LINEAGE_NOT_ALLOWED in cs["control_signal_reason_codes"]

    def test_rerun_possible_code(self):
        cs = _blocked_lineage_cs()
        assert CS_REASON_RERUN_POSSIBLE_AFTER_REPAIR in cs["control_signal_reason_codes"]

    def test_clean_continue_no_codes(self):
        cs = _clean_cs()
        assert cs["control_signal_reason_codes"] == []

    def test_deterministic_across_runs(self):
        cs1 = _blocked_lineage_cs(stage=STAGE_SYNTHESIS)
        cs2 = _blocked_lineage_cs(stage=STAGE_SYNTHESIS)
        assert cs1["control_signal_reason_codes"] == cs2["control_signal_reason_codes"]


# ---------------------------------------------------------------------------
# 14. Schema validation of updated control-chain artifact
# ---------------------------------------------------------------------------


class TestSchemaValidation:
    def test_clean_run_no_schema_errors(self):
        result = run_control_chain(_slo_evaluation(), stage=STAGE_OBSERVE)
        assert result["schema_errors"] == []

    def test_control_signals_field_in_artifact(self):
        result = run_control_chain(_slo_evaluation(), stage=STAGE_SYNTHESIS)
        cd = result["control_chain_decision"]
        assert "control_signals" in cd

    def test_control_signals_has_continuation_mode(self):
        result = run_control_chain(_slo_evaluation(), stage=STAGE_SYNTHESIS)
        cs = result["control_chain_decision"]["control_signals"]
        assert "continuation_mode" in cs

    def test_blocked_run_no_schema_errors(self):
        result = run_control_chain(
            _invalid_evaluation(), stage=STAGE_SYNTHESIS
        )
        assert result["schema_errors"] == []

    def test_schema_validates_with_jsonschema(self):
        from jsonschema import Draft202012Validator, FormatChecker
        schema = json.loads(_CC_SCHEMA_PATH.read_text())
        result = run_control_chain(_slo_evaluation(), stage=STAGE_SYNTHESIS)
        cd = result["control_chain_decision"]
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        errors = list(validator.iter_errors(cd))
        assert errors == [], [e.message for e in errors]

    def test_schema_validates_blocked_artifact(self):
        from jsonschema import Draft202012Validator, FormatChecker
        schema = json.loads(_CC_SCHEMA_PATH.read_text())
        result = run_control_chain(_invalid_evaluation(), stage=STAGE_SYNTHESIS)
        cd = result["control_chain_decision"]
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        errors = list(validator.iter_errors(cd))
        assert errors == [], [e.message for e in errors]

    def test_control_signals_validate_helper(self):
        cs = _clean_cs()
        errs = validate_control_signals(cs)
        assert errs == []

    def test_invalid_continuation_mode_fails_validation(self):
        cs = dict(_clean_cs())
        cs["continuation_mode"] = "fly_away"
        errs = validate_control_signals(cs)
        assert errs

    def test_stop_with_publication_allowed_fails_validation(self):
        cs = dict(_blocked_lineage_cs())
        cs["publication_allowed"] = True
        errs = validate_control_signals(cs)
        assert errs


# ---------------------------------------------------------------------------
# 15. CLI summary includes control signal fields
# ---------------------------------------------------------------------------


class TestCLISummary:
    def _run_cli(self, artifact: Dict[str, Any], stage: Optional[str] = None) -> int:
        with tempfile.NamedTemporaryFile(
            suffix=".json", mode="w", delete=False
        ) as f:
            json.dump(artifact, f)
            input_path = f.name
        with tempfile.TemporaryDirectory() as outdir:
            argv = [input_path, "--output", f"{outdir}/out.json"]
            if stage:
                argv += ["--stage", stage]
            import io
            from contextlib import redirect_stdout
            buf = io.StringIO()
            with redirect_stdout(buf):
                code = cc_main(argv)
            return code, buf.getvalue()

    def test_cli_summary_contains_continuation_mode(self):
        code, output = self._run_cli(_slo_evaluation(), stage=STAGE_OBSERVE)
        assert "continuation_mode" in output

    def test_cli_summary_contains_publication_allowed(self):
        code, output = self._run_cli(_slo_evaluation(), stage=STAGE_SYNTHESIS)
        assert "publication_allowed" in output

    def test_cli_summary_contains_decision_grade_allowed(self):
        code, output = self._run_cli(_slo_evaluation(), stage=STAGE_SYNTHESIS)
        assert "decision_grade_allowed" in output

    def test_cli_summary_contains_human_review_required(self):
        code, output = self._run_cli(_slo_evaluation(), stage=STAGE_SYNTHESIS)
        assert "human_review_required" in output

    def test_cli_summary_has_validators_for_blocked(self):
        code, output = self._run_cli(_invalid_evaluation(), stage=STAGE_SYNTHESIS)
        # Should show blocking requirements
        assert "required_validators" in output or "Blocking requirements" in output

    def test_cli_summary_has_repair_actions_for_blocked(self):
        code, output = self._run_cli(_invalid_evaluation(), stage=STAGE_SYNTHESIS)
        assert "repair_actions" in output or "Blocking requirements" in output

    def test_cli_exit_code_0_for_continue(self):
        code, _ = self._run_cli(_slo_evaluation(), stage=STAGE_OBSERVE)
        assert code == 0

    def test_cli_exit_code_2_for_blocked(self):
        code, _ = self._run_cli(_invalid_evaluation(), stage=STAGE_SYNTHESIS)
        assert code == 2


# ---------------------------------------------------------------------------
# 16. No uncaught exceptions on malformed inputs
# ---------------------------------------------------------------------------


class TestNoCrashes:
    def test_none_input(self):
        cs = derive_control_signals(
            continuation_allowed=False,
            primary_reason_code=REASON_BLOCKED_BY_MALFORMED_INPUT,
            gating_outcome=None,
            enforcement_status=None,
            lineage_defaulted=None,
            lineage_valid=None,
            stage=None,
        )
        assert isinstance(cs, dict)

    def test_unknown_strings(self):
        cs = derive_control_signals(
            continuation_allowed=False,
            primary_reason_code="some_unknown_reason",
            gating_outcome="some_unknown_outcome",
            enforcement_status="some_unknown_status",
            lineage_defaulted=None,
            lineage_valid=None,
            stage="some_unknown_stage",
        )
        assert isinstance(cs, dict)

    def test_summarize_invalid_signals(self):
        result = summarize_control_signals(None)  # type: ignore[arg-type]
        assert isinstance(result, str)

    def test_explain_blocking_invalid(self):
        result = explain_blocking_requirements(None)  # type: ignore[arg-type]
        assert isinstance(result, str)

    def test_list_followups_invalid(self):
        result = list_required_followups(None)  # type: ignore[arg-type]
        assert isinstance(result, list)

    def test_validate_signals_non_dict(self):
        errs = validate_control_signals("not a dict")  # type: ignore[arg-type]
        assert isinstance(errs, list)
        assert len(errs) > 0

    def test_run_control_chain_malformed_input_no_crash(self):
        result = run_control_chain({"totally": "wrong"})
        assert isinstance(result, dict)
        assert "control_signals" in result["control_chain_decision"]


# ---------------------------------------------------------------------------
# 17. Backward compatibility with existing control-chain flows
# ---------------------------------------------------------------------------


class TestBackwardCompatibility:
    def test_existing_fields_still_present(self):
        result = run_control_chain(_slo_evaluation(), stage=STAGE_OBSERVE)
        cd = result["control_chain_decision"]
        for field in [
            "continuation_allowed",
            "primary_reason_code",
            "recommended_action",
            "blocking_layer",
            "enforcement_decision_id",
            "gating_decision_id",
            "stage",
            "evaluated_at",
            "schema_version",
        ]:
            assert field in cd, f"Missing backward-compatible field: {field}"

    def test_top_level_keys_unchanged(self):
        result = run_control_chain(_slo_evaluation(), stage=STAGE_OBSERVE)
        for key in [
            "control_chain_decision",
            "continuation_allowed",
            "primary_reason_code",
            "schema_errors",
            "enforcement_result",
            "gating_result",
        ]:
            assert key in result

    def test_control_signals_is_additive(self):
        # control_signals is a new field; its presence is additive
        result = run_control_chain(_slo_evaluation(), stage=STAGE_OBSERVE)
        cd = result["control_chain_decision"]
        assert "control_signals" in cd
        # existing fields unchanged
        assert cd["continuation_allowed"] is True

    def test_schema_version_unchanged(self):
        result = run_control_chain(_slo_evaluation(), stage=STAGE_OBSERVE)
        assert result["control_chain_decision"]["schema_version"] == "1.0.0"


# ---------------------------------------------------------------------------
# 18. continue path does not emit contradictory stop signals
# ---------------------------------------------------------------------------


class TestNonContradictorySignals:
    def test_continue_no_stop_signals(self):
        cs = _clean_cs()
        assert cs["continuation_mode"] == CONTINUATION_MODE_CONTINUE
        assert cs["rerun_recommended"] is False
        assert cs["escalation_required"] is False
        assert cs["human_review_required"] is False

    def test_continue_no_repair_actions(self):
        cs = _clean_cs()
        assert cs["repair_actions"] == []

    def test_continue_no_reason_codes(self):
        cs = _clean_cs()
        assert cs["control_signal_reason_codes"] == []

    def test_continue_monitoring_no_escalation(self):
        cs = _warning_cs(stage=STAGE_OBSERVE)
        assert cs["escalation_required"] is False
        assert cs["continuation_mode"] == CONTINUATION_MODE_CONTINUE_WITH_MONITORING


# ---------------------------------------------------------------------------
# 19. stop path does not emit publication_allowed=true
# ---------------------------------------------------------------------------


class TestStopNeverAllowsPublication:
    @pytest.mark.parametrize("stop_mode", [
        CONTINUATION_MODE_STOP,
        CONTINUATION_MODE_STOP_AND_REPAIR,
        CONTINUATION_MODE_STOP_AND_RERUN,
        CONTINUATION_MODE_STOP_AND_ESCALATE,
    ])
    def test_stop_mode_publication_false(self, stop_mode):
        # Build minimal signals dict with a stop mode
        cs = build_control_signals(
            continuation_mode=stop_mode,
            required_inputs=[],
            required_validators=[],
            repair_actions=[],
            rerun_recommended=False,
            human_review_required=False,
            escalation_required=False,
            publication_allowed=False,
            decision_grade_allowed=False,
            traceability_required=False,
            control_signal_reason_codes=[],
        )
        errs = validate_control_signals(cs)
        assert errs == []

    def test_blocked_lineage_publication_false(self):
        cs = _blocked_lineage_cs()
        assert cs["publication_allowed"] is False

    def test_malformed_publication_false(self):
        cs = _malformed_cs()
        assert cs["publication_allowed"] is False

    def test_missing_gating_publication_false(self):
        cs = _missing_gating_cs()
        assert cs["publication_allowed"] is False


# ---------------------------------------------------------------------------
# 20. Decision-bearing blocked states fail closed
# ---------------------------------------------------------------------------


class TestDecisionBearingFailClosed:
    @pytest.mark.parametrize("stage", [STAGE_RECOMMEND, STAGE_SYNTHESIS, STAGE_EXPORT])
    def test_blocked_at_decision_stage_publication_false(self, stage):
        result = run_control_chain(_invalid_evaluation(), stage=stage)
        cs = result["control_chain_decision"]["control_signals"]
        assert cs["publication_allowed"] is False

    @pytest.mark.parametrize("stage", [STAGE_RECOMMEND, STAGE_SYNTHESIS, STAGE_EXPORT])
    def test_blocked_at_decision_stage_decision_grade_false(self, stage):
        result = run_control_chain(_invalid_evaluation(), stage=stage)
        cs = result["control_chain_decision"]["control_signals"]
        assert cs["decision_grade_allowed"] is False

    @pytest.mark.parametrize("stage", [STAGE_RECOMMEND, STAGE_SYNTHESIS, STAGE_EXPORT])
    def test_continuation_allowed_false(self, stage):
        result = run_control_chain(_invalid_evaluation(), stage=stage)
        assert result["continuation_allowed"] is False


# ---------------------------------------------------------------------------
# 21. Additive schema change does not break existing generation path
# ---------------------------------------------------------------------------


class TestAdditiveSchema:
    def test_build_decision_with_no_signals_still_works(self):
        # build_control_chain_decision accepts control_signals=None (defaults to {})
        from spectrum_systems.modules.runtime.control_chain import (
            build_control_chain_decision,
            INPUT_KIND_EVALUATION,
            BLOCKING_NONE,
            REASON_CONTINUE,
            ACTION_CONTINUE,
            CONTRACT_VERSION,
        )
        decision = build_control_chain_decision(
            artifact_id="ART-001",
            stage="observe",
            input_kind=INPUT_KIND_EVALUATION,
            enforcement_decision_id="ENF-001",
            gating_decision_id="GATE-001",
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
            control_signals=None,
            evaluated_at=_TS,
        )
        assert "control_signals" in decision
        assert isinstance(decision["control_signals"], dict)


# ---------------------------------------------------------------------------
# 22. required_inputs emitted when inputs are missing
# ---------------------------------------------------------------------------


class TestRequiredInputs:
    def test_required_inputs_passed_through(self):
        cs = derive_control_signals(
            continuation_allowed=False,
            primary_reason_code=REASON_BLOCKED_BY_MISSING_GATING,
            gating_outcome=None,
            enforcement_status=None,
            lineage_defaulted=None,
            lineage_valid=None,
            stage=STAGE_SYNTHESIS,
            required_inputs=["gating_decision_artifact", "enforcement_policy"],
        )
        assert "gating_decision_artifact" in cs["required_inputs"]
        assert "enforcement_policy" in cs["required_inputs"]

    def test_empty_required_inputs_by_default(self):
        cs = _clean_cs()
        assert cs["required_inputs"] == []

    def test_missing_required_input_reason_code(self):
        cs = derive_control_signals(
            continuation_allowed=False,
            primary_reason_code=REASON_BLOCKED_BY_MISSING_GATING,
            gating_outcome=None,
            enforcement_status=None,
            lineage_defaulted=None,
            lineage_valid=None,
            stage=STAGE_SYNTHESIS,
            required_inputs=["gating_decision_artifact"],
        )
        from spectrum_systems.modules.runtime.control_signals import CS_REASON_MISSING_REQUIRED_INPUT
        assert CS_REASON_MISSING_REQUIRED_INPUT in cs["control_signal_reason_codes"]


# ---------------------------------------------------------------------------
# 23. Stage override behavior remains auditable
# ---------------------------------------------------------------------------


class TestStageOverrideAuditability:
    def test_stage_override_reflected_in_artifact(self):
        result = run_control_chain(_slo_evaluation(), stage=STAGE_SYNTHESIS)
        cd = result["control_chain_decision"]
        assert cd["stage"] == STAGE_SYNTHESIS

    def test_stage_override_source_recorded(self):
        result = run_control_chain(_slo_evaluation(), stage=STAGE_SYNTHESIS)
        cd = result["control_chain_decision"]
        assert cd.get("stage_source") == "override"

    def test_no_stage_uses_original_source(self):
        from spectrum_systems.modules.runtime.slo_enforcement import run_slo_enforcement
        from spectrum_systems.modules.runtime.decision_gating import run_slo_gating
        enf = run_slo_enforcement(_slo_evaluation(), policy="permissive", stage=STAGE_OBSERVE)
        gating = run_slo_gating(enf, stage=STAGE_OBSERVE)
        gating_artifact = gating.get("gating_decision") or {}
        result = run_control_chain(gating_artifact, input_kind="gating")
        cd = result["control_chain_decision"]
        assert cd.get("stage_source") == "original"


# ---------------------------------------------------------------------------
# 24. Signal derivation remains deterministic across repeated runs
# ---------------------------------------------------------------------------


class TestDeterminism:
    @pytest.mark.parametrize("scenario", [
        "clean",
        "warning_observe",
        "warning_synthesis",
        "blocked_lineage",
        "blocked_invalid_lineage",
        "malformed",
        "missing_gating",
    ])
    def test_deterministic_output(self, scenario):
        scenarios = {
            "clean": lambda: _clean_cs(stage=STAGE_OBSERVE),
            "warning_observe": lambda: _warning_cs(stage=STAGE_OBSERVE),
            "warning_synthesis": lambda: _warning_cs(stage=STAGE_SYNTHESIS),
            "blocked_lineage": lambda: _blocked_lineage_cs(stage=STAGE_SYNTHESIS),
            "blocked_invalid_lineage": lambda: _blocked_invalid_lineage_cs(),
            "malformed": lambda: _malformed_cs(),
            "missing_gating": lambda: _missing_gating_cs(),
        }
        fn = scenarios[scenario]
        cs1 = fn()
        cs2 = fn()
        # Remove any non-deterministic fields (none expected, but be safe)
        assert cs1 == cs2, f"Non-deterministic output for scenario {scenario}"


# ---------------------------------------------------------------------------
# Diagnostics helper tests
# ---------------------------------------------------------------------------


class TestDiagnosticHelpers:
    def test_summarize_clean(self):
        cs = _clean_cs()
        summary = summarize_control_signals(cs)
        assert "continue" in summary
        assert "continuation_mode" in summary

    def test_summarize_blocked(self):
        cs = _blocked_lineage_cs()
        summary = summarize_control_signals(cs)
        assert "stop" in summary

    def test_explain_blocking_empty_for_continue(self):
        cs = _clean_cs()
        explanation = explain_blocking_requirements(cs)
        assert explanation == ""

    def test_explain_blocking_non_empty_for_stop(self):
        cs = _blocked_lineage_cs()
        explanation = explain_blocking_requirements(cs)
        assert explanation != ""
        assert "stop" in explanation.lower() or "repair" in explanation.lower()

    def test_list_followups_empty_for_clean(self):
        cs = _clean_cs()
        followups = list_required_followups(cs)
        assert followups == []

    def test_list_followups_non_empty_for_blocked(self):
        cs = _blocked_lineage_cs()
        followups = list_required_followups(cs)
        assert len(followups) > 0

    def test_list_followups_includes_repair_actions(self):
        cs = _blocked_lineage_cs()
        followups = list_required_followups(cs)
        # Repair actions should be in follow-ups
        for action in cs["repair_actions"]:
            assert action in followups

    def test_list_followups_includes_validator_runs(self):
        cs = _blocked_lineage_cs()
        followups = list_required_followups(cs)
        for v in cs["required_validators"]:
            assert f"run:{v}" in followups

    def test_list_followups_escalate_flag(self):
        cs = _malformed_cs()
        followups = list_required_followups(cs)
        assert "escalate_to_governance" in followups

    def test_list_followups_rerun_flag(self):
        cs = _blocked_lineage_cs()
        followups = list_required_followups(cs)
        assert "rerun_after_repair" in followups
