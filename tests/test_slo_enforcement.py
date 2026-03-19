"""Tests for the TI Enforcement Layer (Prompt 11B).

Covers all requirements from the problem statement:
1.  permissive policy: 1.0 allow, 0.5 warn, 0.0 fail
2.  decision_grade policy: 1.0 allow, 0.5 fail, 0.0 fail
3.  exploratory policy: 1.0 allow, 0.5 allow_with_warning, 0.0 fail
4.  missing TI
5.  malformed TI
6.  missing lineage mode
7.  malformed lineage mode
8.  contradictory state detection
9.  deterministic reason code assignment
10. schema validation of emitted decision artifact
11. CLI exit codes
12. summary output includes policy, decision, TI, and reason code
13. backward-compatible use alongside existing slo_control flows
14. stage override behavior
15. no uncaught exceptions on malformed artifact input
"""
from __future__ import annotations

import io
import json
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional
from unittest.mock import patch

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

from spectrum_systems.modules.runtime.slo_enforcement import (  # noqa: E402
    ACTION_FIX_INPUT,
    ACTION_HALT_AND_REVIEW,
    ACTION_HALT_DEGRADED_LINEAGE,
    ACTION_HALT_INVALID_LINEAGE,
    ACTION_INVESTIGATE_INCONSISTENCY,
    ACTION_PROCEED,
    ACTION_PROCEED_WITH_CAUTION,
    CONTRACT_VERSION,
    DECISION_ALLOW,
    DECISION_ALLOW_WITH_WARNING,
    DECISION_FAIL,
    DEFAULT_POLICY,
    KNOWN_POLICIES,
    KNOWN_REASON_CODES,
    POLICY_DECISION_GRADE,
    POLICY_EXPLORATORY,
    POLICY_PERMISSIVE,
    REASON_DEGRADED_NO_REGISTRY,
    REASON_INCONSISTENT_LINEAGE_STATE,
    REASON_MALFORMED_LINEAGE_MODE,
    REASON_MALFORMED_TI,
    REASON_MISSING_LINEAGE_MODE,
    REASON_MISSING_TI,
    REASON_STRICT_INVALID_LINEAGE,
    REASON_STRICT_VALID_LINEAGE,
    STAGE_DEFAULT_POLICIES,
    STAGE_EXPORT,
    STAGE_INTERPRET,
    STAGE_OBSERVE,
    STAGE_RECOMMEND,
    STAGE_SYNTHESIS,
    build_slo_enforcement_decision,
    derive_decision_reason_code,
    derive_recommended_action,
    detect_lineage_state_inconsistencies,
    evaluate_traceability_policy,
    normalize_enforcement_inputs,
    resolve_enforcement_policy,
    run_slo_enforcement,
    validate_enforcement_inputs,
    validate_slo_enforcement_decision,
)

# Import run_slo_control for backward-compat tests
from spectrum_systems.modules.runtime.slo_control import run_slo_control  # noqa: E402

_ENFORCEMENT_SCHEMA_PATH = _REPO_ROOT / "contracts" / "schemas" / "slo_enforcement_decision.schema.json"


def _load_enforcement_schema() -> Dict[str, Any]:
    """Cached schema loader for tests."""
    return json.loads(_ENFORCEMENT_SCHEMA_PATH.read_text())


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _artifact(
    artifact_id: str = "TEST-ARTIFACT-001",
    artifact_type: str = "slo_evaluation",
    ti: float = 1.0,
    mode: str = "strict",
    defaulted: bool = False,
    lineage_valid: Optional[bool] = True,
) -> Dict[str, Any]:
    """Return a minimal artifact dict with the enforcement-relevant fields."""
    return {
        "artifact_id": artifact_id,
        "artifact_type": artifact_type,
        "traceability_integrity_sli": ti,
        "lineage_validation_mode": mode,
        "lineage_defaulted": defaulted,
        "lineage_valid": lineage_valid,
        "parent_artifact_ids": ["parent-001"],
    }


def _degraded_artifact(**kwargs) -> Dict[str, Any]:
    return _artifact(ti=0.5, mode="degraded", defaulted=True, lineage_valid=None, **kwargs)


def _invalid_artifact(**kwargs) -> Dict[str, Any]:
    return _artifact(ti=0.0, mode="strict", defaulted=False, lineage_valid=False, **kwargs)


# ---------------------------------------------------------------------------
# 1. Permissive policy
# ---------------------------------------------------------------------------


class TestPermissivePolicy:
    def test_ti_1_0_allow(self):
        result = run_slo_enforcement(_artifact(ti=1.0), policy=POLICY_PERMISSIVE)
        assert result["decision_status"] == DECISION_ALLOW
        assert result["decision_reason_code"] == REASON_STRICT_VALID_LINEAGE

    def test_ti_0_5_allow_with_warning(self):
        result = run_slo_enforcement(_degraded_artifact(), policy=POLICY_PERMISSIVE)
        assert result["decision_status"] == DECISION_ALLOW_WITH_WARNING
        assert result["decision_reason_code"] == REASON_DEGRADED_NO_REGISTRY

    def test_ti_0_0_fail(self):
        result = run_slo_enforcement(_invalid_artifact(), policy=POLICY_PERMISSIVE)
        assert result["decision_status"] == DECISION_FAIL
        assert result["decision_reason_code"] == REASON_STRICT_INVALID_LINEAGE


# ---------------------------------------------------------------------------
# 2. Decision-grade policy
# ---------------------------------------------------------------------------


class TestDecisionGradePolicy:
    def test_ti_1_0_allow(self):
        result = run_slo_enforcement(_artifact(ti=1.0), policy=POLICY_DECISION_GRADE)
        assert result["decision_status"] == DECISION_ALLOW

    def test_ti_0_5_fail(self):
        result = run_slo_enforcement(_degraded_artifact(), policy=POLICY_DECISION_GRADE)
        assert result["decision_status"] == DECISION_FAIL

    def test_ti_0_0_fail(self):
        result = run_slo_enforcement(_invalid_artifact(), policy=POLICY_DECISION_GRADE)
        assert result["decision_status"] == DECISION_FAIL


# ---------------------------------------------------------------------------
# 3. Exploratory policy
# ---------------------------------------------------------------------------


class TestExploratoryPolicy:
    def test_ti_1_0_allow(self):
        result = run_slo_enforcement(_artifact(ti=1.0), policy=POLICY_EXPLORATORY)
        assert result["decision_status"] == DECISION_ALLOW

    def test_ti_0_5_allow_with_warning(self):
        result = run_slo_enforcement(_degraded_artifact(), policy=POLICY_EXPLORATORY)
        assert result["decision_status"] == DECISION_ALLOW_WITH_WARNING

    def test_ti_0_0_fail(self):
        result = run_slo_enforcement(_invalid_artifact(), policy=POLICY_EXPLORATORY)
        assert result["decision_status"] == DECISION_FAIL


# ---------------------------------------------------------------------------
# 4. Missing TI
# ---------------------------------------------------------------------------


class TestMissingTI:
    def test_missing_ti_field(self):
        artifact = _artifact()
        del artifact["traceability_integrity_sli"]
        result = run_slo_enforcement(artifact)
        assert result["decision_status"] == DECISION_FAIL
        assert result["decision_reason_code"] == REASON_MISSING_TI

    def test_missing_ti_has_error_message(self):
        artifact = _artifact()
        del artifact["traceability_integrity_sli"]
        result = run_slo_enforcement(artifact)
        assert any("traceability_integrity_sli" in e for e in result["errors"])

    def test_missing_ti_returns_governed_decision(self):
        artifact = _artifact()
        del artifact["traceability_integrity_sli"]
        result = run_slo_enforcement(artifact)
        assert "enforcement_decision" in result
        d = result["enforcement_decision"]
        assert d["decision_status"] == DECISION_FAIL
        assert d["traceability_integrity_sli"] is None


# ---------------------------------------------------------------------------
# 5. Malformed TI
# ---------------------------------------------------------------------------


class TestMalformedTI:
    def test_ti_is_string(self):
        artifact = _artifact()
        artifact["traceability_integrity_sli"] = "high"
        result = run_slo_enforcement(artifact)
        assert result["decision_status"] == DECISION_FAIL
        assert result["decision_reason_code"] == REASON_MALFORMED_TI

    def test_ti_is_none(self):
        artifact = _artifact()
        artifact["traceability_integrity_sli"] = None
        result = run_slo_enforcement(artifact)
        assert result["decision_status"] == DECISION_FAIL
        assert result["decision_reason_code"] == REASON_MISSING_TI

    def test_ti_is_invalid_float(self):
        """A float that is not a governed band (e.g. 0.75) → malformed."""
        artifact = _artifact()
        artifact["traceability_integrity_sli"] = 0.75
        result = run_slo_enforcement(artifact)
        assert result["decision_status"] == DECISION_FAIL
        assert result["decision_reason_code"] == REASON_MALFORMED_TI

    def test_ti_negative_value(self):
        artifact = _artifact()
        artifact["traceability_integrity_sli"] = -0.1
        result = run_slo_enforcement(artifact)
        assert result["decision_status"] == DECISION_FAIL
        assert result["decision_reason_code"] == REASON_MALFORMED_TI


# ---------------------------------------------------------------------------
# 6. Missing lineage mode
# ---------------------------------------------------------------------------


class TestMissingLineageMode:
    def test_missing_lineage_mode(self):
        artifact = _artifact()
        del artifact["lineage_validation_mode"]
        result = run_slo_enforcement(artifact)
        assert result["decision_status"] == DECISION_FAIL
        assert result["decision_reason_code"] == REASON_MISSING_LINEAGE_MODE

    def test_missing_lineage_mode_has_error(self):
        artifact = _artifact()
        del artifact["lineage_validation_mode"]
        result = run_slo_enforcement(artifact)
        assert any("lineage_validation_mode" in e for e in result["errors"])


# ---------------------------------------------------------------------------
# 7. Malformed lineage mode
# ---------------------------------------------------------------------------


class TestMalformedLineageMode:
    def test_invalid_lineage_mode_value(self):
        artifact = _artifact()
        artifact["lineage_validation_mode"] = "ultra-strict"
        result = run_slo_enforcement(artifact)
        assert result["decision_status"] == DECISION_FAIL
        assert result["decision_reason_code"] == REASON_MALFORMED_LINEAGE_MODE

    def test_numeric_lineage_mode(self):
        artifact = _artifact()
        artifact["lineage_validation_mode"] = 1
        result = run_slo_enforcement(artifact)
        assert result["decision_status"] == DECISION_FAIL
        assert result["decision_reason_code"] == REASON_MALFORMED_LINEAGE_MODE


# ---------------------------------------------------------------------------
# 8. Contradictory / inconsistent state detection
# ---------------------------------------------------------------------------


class TestInconsistentStateDetection:
    def test_ti_1_with_degraded_mode(self):
        """TI 1.0 but mode is degraded — contradiction."""
        artifact = _artifact(ti=1.0, mode="degraded", defaulted=True, lineage_valid=None)
        result = run_slo_enforcement(artifact)
        assert result["decision_status"] == DECISION_FAIL
        assert result["decision_reason_code"] == REASON_INCONSISTENT_LINEAGE_STATE
        assert any("1.0" in w or "degraded" in w for w in result["warnings"])

    def test_ti_0_5_with_defaulted_false(self):
        """TI 0.5 but lineage_defaulted is False — contradiction."""
        artifact = _artifact(ti=0.5, mode="degraded", defaulted=False, lineage_valid=None)
        result = run_slo_enforcement(artifact)
        assert result["decision_status"] == DECISION_FAIL
        assert result["decision_reason_code"] == REASON_INCONSISTENT_LINEAGE_STATE

    def test_ti_0_0_with_lineage_valid_true(self):
        """TI 0.0 but lineage_valid is True — contradiction."""
        artifact = _artifact(ti=0.0, mode="strict", defaulted=False, lineage_valid=True)
        result = run_slo_enforcement(artifact)
        assert result["decision_status"] == DECISION_FAIL
        assert result["decision_reason_code"] == REASON_INCONSISTENT_LINEAGE_STATE

    def test_strict_mode_without_lineage_valid(self):
        """Strict mode with TI=1.0 but lineage_valid absent."""
        artifact = _artifact(ti=1.0, mode="strict", defaulted=False)
        del artifact["lineage_valid"]
        result = run_slo_enforcement(artifact)
        # lineage_valid is None → inconsistency detected
        assert result["decision_reason_code"] == REASON_INCONSISTENT_LINEAGE_STATE

    def test_inconsistency_appears_in_warnings(self):
        artifact = _artifact(ti=1.0, mode="degraded", defaulted=True, lineage_valid=None)
        result = run_slo_enforcement(artifact)
        assert len(result["warnings"]) >= 1


# ---------------------------------------------------------------------------
# 9. Deterministic reason code assignment
# ---------------------------------------------------------------------------


class TestDeterministicReasonCodes:
    def test_strict_valid_gives_strict_valid_reason(self):
        result = run_slo_enforcement(_artifact(ti=1.0, mode="strict", lineage_valid=True))
        assert result["decision_reason_code"] == REASON_STRICT_VALID_LINEAGE

    def test_strict_invalid_gives_strict_invalid_reason(self):
        result = run_slo_enforcement(_invalid_artifact())
        assert result["decision_reason_code"] == REASON_STRICT_INVALID_LINEAGE

    def test_degraded_gives_degraded_reason(self):
        result = run_slo_enforcement(_degraded_artifact())
        assert result["decision_reason_code"] == REASON_DEGRADED_NO_REGISTRY

    def test_reason_codes_are_governed_values(self):
        for ti, mode, defaulted, valid in [
            (1.0, "strict", False, True),
            (0.5, "degraded", True, None),
            (0.0, "strict", False, False),
        ]:
            art = _artifact(ti=ti, mode=mode, defaulted=defaulted, lineage_valid=valid)
            result = run_slo_enforcement(art)
            assert result["decision_reason_code"] in KNOWN_REASON_CODES

    def test_same_input_same_reason_code(self):
        """Repeated calls produce the same reason code (deterministic)."""
        art = _artifact(ti=1.0)
        r1 = run_slo_enforcement(art, evaluated_at="2026-01-01T00:00:00+00:00")
        r2 = run_slo_enforcement(art, evaluated_at="2026-01-01T00:00:00+00:00")
        assert r1["decision_reason_code"] == r2["decision_reason_code"]
        assert r1["decision_status"] == r2["decision_status"]


# ---------------------------------------------------------------------------
# 10. Schema validation of emitted decision artifact
# ---------------------------------------------------------------------------


class TestSchemaValidation:
    def test_valid_allow_artifact_passes_schema(self):
        result = run_slo_enforcement(_artifact(ti=1.0))
        assert result["schema_errors"] == []

    def test_valid_warn_artifact_passes_schema(self):
        result = run_slo_enforcement(_degraded_artifact())
        assert result["schema_errors"] == []

    def test_valid_fail_artifact_passes_schema(self):
        result = run_slo_enforcement(_invalid_artifact())
        assert result["schema_errors"] == []

    def test_missing_ti_artifact_passes_schema(self):
        """Even error-path artifacts should be schema-valid."""
        artifact = _artifact()
        del artifact["traceability_integrity_sli"]
        result = run_slo_enforcement(artifact)
        assert result["schema_errors"] == []

    def test_decision_id_matches_pattern(self):
        result = run_slo_enforcement(_artifact())
        d = result["enforcement_decision"]
        assert d["decision_id"].startswith("ENF-")

    def test_contract_version_present(self):
        result = run_slo_enforcement(_artifact())
        d = result["enforcement_decision"]
        assert d["contract_version"] == CONTRACT_VERSION

    def test_all_required_fields_present(self):
        schema = _load_enforcement_schema()
        required_fields = set(schema["required"])
        result = run_slo_enforcement(_artifact())
        d = result["enforcement_decision"]
        for field in required_fields:
            assert field in d, f"Required field '{field}' missing from decision artifact"

    def test_schema_file_exists(self):
        assert _ENFORCEMENT_SCHEMA_PATH.exists()

    def test_validate_function_detects_missing_field(self):
        result = run_slo_enforcement(_artifact())
        bad = dict(result["enforcement_decision"])
        del bad["decision_id"]
        errors = validate_slo_enforcement_decision(bad)
        assert len(errors) > 0


# ---------------------------------------------------------------------------
# 11. CLI exit codes
# ---------------------------------------------------------------------------


class TestCLIExitCodes:
    def _write_artifact(self, artifact: Dict[str, Any], path: Path) -> None:
        path.write_text(json.dumps(artifact), encoding="utf-8")

    def test_allow_exits_0(self, tmp_path):
        art_path = tmp_path / "artifact.json"
        self._write_artifact(_artifact(ti=1.0), art_path)
        output_path = tmp_path / "decision.json"
        from scripts.run_slo_enforcement import main
        code = main([str(art_path), "--policy", "permissive", "--output", str(output_path)])
        assert code == 0

    def test_allow_with_warning_exits_1(self, tmp_path):
        art_path = tmp_path / "artifact.json"
        self._write_artifact(_degraded_artifact(), art_path)
        output_path = tmp_path / "decision.json"
        from scripts.run_slo_enforcement import main
        code = main([str(art_path), "--policy", "permissive", "--output", str(output_path)])
        assert code == 1

    def test_fail_exits_2(self, tmp_path):
        art_path = tmp_path / "artifact.json"
        self._write_artifact(_invalid_artifact(), art_path)
        output_path = tmp_path / "decision.json"
        from scripts.run_slo_enforcement import main
        code = main([str(art_path), "--policy", "permissive", "--output", str(output_path)])
        assert code == 2

    def test_missing_file_exits_3(self, tmp_path):
        from scripts.run_slo_enforcement import main
        code = main([str(tmp_path / "nonexistent.json")])
        assert code == 3

    def test_malformed_json_exits_3(self, tmp_path):
        bad_path = tmp_path / "bad.json"
        bad_path.write_text("{not valid json}", encoding="utf-8")
        from scripts.run_slo_enforcement import main
        code = main([str(bad_path)])
        assert code == 3

    def test_decision_grade_degraded_exits_2(self, tmp_path):
        art_path = tmp_path / "artifact.json"
        self._write_artifact(_degraded_artifact(), art_path)
        output_path = tmp_path / "decision.json"
        from scripts.run_slo_enforcement import main
        code = main([str(art_path), "--policy", "decision_grade", "--output", str(output_path)])
        assert code == 2

    def test_output_file_written(self, tmp_path):
        art_path = tmp_path / "artifact.json"
        self._write_artifact(_artifact(ti=1.0), art_path)
        output_path = tmp_path / "decision.json"
        from scripts.run_slo_enforcement import main
        main([str(art_path), "--output", str(output_path)])
        assert output_path.exists()
        decision = json.loads(output_path.read_text())
        assert "decision_id" in decision


# ---------------------------------------------------------------------------
# 12. Summary output includes policy, decision, TI, and reason code
# ---------------------------------------------------------------------------


class TestSummaryOutput:
    def test_summary_includes_policy(self, tmp_path, capsys):
        art_path = tmp_path / "artifact.json"
        art_path.write_text(json.dumps(_artifact(ti=1.0)), encoding="utf-8")
        output_path = tmp_path / "decision.json"
        from scripts.run_slo_enforcement import main
        main([str(art_path), "--policy", "permissive", "--output", str(output_path)])
        captured = capsys.readouterr()
        assert "permissive" in captured.out

    def test_summary_includes_decision_status(self, tmp_path, capsys):
        art_path = tmp_path / "artifact.json"
        art_path.write_text(json.dumps(_artifact(ti=1.0)), encoding="utf-8")
        output_path = tmp_path / "decision.json"
        from scripts.run_slo_enforcement import main
        main([str(art_path), "--output", str(output_path)])
        captured = capsys.readouterr()
        assert "allow" in captured.out

    def test_summary_includes_ti_value(self, tmp_path, capsys):
        art_path = tmp_path / "artifact.json"
        art_path.write_text(json.dumps(_artifact(ti=1.0)), encoding="utf-8")
        output_path = tmp_path / "decision.json"
        from scripts.run_slo_enforcement import main
        main([str(art_path), "--output", str(output_path)])
        captured = capsys.readouterr()
        assert "1.0" in captured.out

    def test_summary_includes_reason_code(self, tmp_path, capsys):
        art_path = tmp_path / "artifact.json"
        art_path.write_text(json.dumps(_artifact(ti=1.0)), encoding="utf-8")
        output_path = tmp_path / "decision.json"
        from scripts.run_slo_enforcement import main
        main([str(art_path), "--output", str(output_path)])
        captured = capsys.readouterr()
        assert "strict_valid_lineage" in captured.out


# ---------------------------------------------------------------------------
# 13. Backward-compatible use alongside existing slo_control flows
# ---------------------------------------------------------------------------


class TestBackwardCompatibility:
    """Verify slo_enforcement can accept output from run_slo_control."""

    def _slo_evaluation_artifact(self) -> Dict[str, Any]:
        """Produce an slo_evaluation artifact via run_slo_control."""
        result = run_slo_control([], None, None)
        return result["slo_evaluation"]

    def test_slo_control_output_accepted_by_enforcement(self):
        slo_artifact = self._slo_evaluation_artifact()
        result = run_slo_enforcement(slo_artifact)
        assert result["decision_status"] in {
            DECISION_ALLOW, DECISION_ALLOW_WITH_WARNING, DECISION_FAIL
        }

    def test_slo_control_output_produces_valid_schema(self):
        slo_artifact = self._slo_evaluation_artifact()
        result = run_slo_enforcement(slo_artifact)
        assert result["schema_errors"] == []

    def test_slo_control_degraded_enforcement_decision(self):
        """run_slo_control with no registry → TI 0.5 → permissive gives allow_with_warning."""
        result_ctrl = run_slo_control([], None, None)
        slo_artifact = result_ctrl["slo_evaluation"]
        # No lineage registry → TI should be 0.5 (degraded)
        assert slo_artifact["slis"]["traceability_integrity"] == 0.5
        result_enf = run_slo_enforcement(slo_artifact, policy=POLICY_PERMISSIVE)
        assert result_enf["decision_status"] == DECISION_ALLOW_WITH_WARNING
        assert result_enf["decision_reason_code"] == REASON_DEGRADED_NO_REGISTRY

    def test_slo_control_degraded_decision_grade_fails(self):
        """run_slo_control with no registry → TI 0.5 → decision_grade gives fail."""
        result_ctrl = run_slo_control([], None, None)
        slo_artifact = result_ctrl["slo_evaluation"]
        result_enf = run_slo_enforcement(slo_artifact, policy=POLICY_DECISION_GRADE)
        assert result_enf["decision_status"] == DECISION_FAIL

    def test_existing_slo_control_tests_not_broken(self):
        """Importing slo_enforcement must not break slo_control imports."""
        from spectrum_systems.modules.runtime.slo_control import (
            run_slo_control as _rc,
        )
        from spectrum_systems.modules.runtime.slo_enforcement import (
            run_slo_enforcement as _re,
        )
        assert callable(_rc)
        assert callable(_re)


# ---------------------------------------------------------------------------
# 14. Stage override behavior
# ---------------------------------------------------------------------------


class TestStageOverride:
    def test_synthesis_stage_defaults_to_decision_grade(self):
        """synthesis stage uses decision_grade by default."""
        result = run_slo_enforcement(_degraded_artifact(), stage=STAGE_SYNTHESIS)
        assert result["decision_status"] == DECISION_FAIL
        d = result["enforcement_decision"]
        assert d["enforcement_policy"] == POLICY_DECISION_GRADE

    def test_export_stage_defaults_to_decision_grade(self):
        result = run_slo_enforcement(_degraded_artifact(), stage=STAGE_EXPORT)
        assert result["decision_status"] == DECISION_FAIL

    def test_observe_stage_defaults_to_permissive(self):
        result = run_slo_enforcement(_degraded_artifact(), stage=STAGE_OBSERVE)
        assert result["decision_status"] == DECISION_ALLOW_WITH_WARNING

    def test_interpret_stage_defaults_to_permissive(self):
        result = run_slo_enforcement(_degraded_artifact(), stage=STAGE_INTERPRET)
        assert result["decision_status"] == DECISION_ALLOW_WITH_WARNING

    def test_recommend_stage_defaults_to_decision_grade(self):
        result = run_slo_enforcement(_degraded_artifact(), stage=STAGE_RECOMMEND)
        assert result["decision_status"] == DECISION_FAIL

    def test_explicit_policy_overrides_stage_default(self):
        """Explicit policy takes precedence over stage default."""
        result = run_slo_enforcement(
            _degraded_artifact(),
            policy=POLICY_PERMISSIVE,
            stage=STAGE_SYNTHESIS,
        )
        # With permissive policy, degraded TI should allow_with_warning
        assert result["decision_status"] == DECISION_ALLOW_WITH_WARNING

    def test_stage_appears_in_decision_artifact(self):
        result = run_slo_enforcement(_artifact(), stage=STAGE_SYNTHESIS)
        d = result["enforcement_decision"]
        assert d.get("enforcement_scope") == STAGE_SYNTHESIS

    def test_no_stage_enforcement_scope_absent(self):
        result = run_slo_enforcement(_artifact())
        d = result["enforcement_decision"]
        assert "enforcement_scope" not in d


# ---------------------------------------------------------------------------
# 15. No uncaught exceptions on malformed artifact input
# ---------------------------------------------------------------------------


class TestCrashProofing:
    def test_none_input(self):
        result = run_slo_enforcement(None)
        assert result["decision_status"] == DECISION_FAIL
        assert "enforcement_decision" in result

    def test_empty_dict_input(self):
        result = run_slo_enforcement({})
        assert result["decision_status"] == DECISION_FAIL
        assert "enforcement_decision" in result

    def test_list_input(self):
        result = run_slo_enforcement([1, 2, 3])
        assert result["decision_status"] == DECISION_FAIL

    def test_string_input(self):
        result = run_slo_enforcement("not an artifact")
        assert result["decision_status"] == DECISION_FAIL

    def test_integer_input(self):
        result = run_slo_enforcement(42)
        assert result["decision_status"] == DECISION_FAIL

    def test_deeply_nested_dict_no_ti(self):
        result = run_slo_enforcement({"nested": {"a": 1}})
        assert result["decision_status"] == DECISION_FAIL

    def test_artifact_with_all_none_values(self):
        result = run_slo_enforcement({
            "artifact_id": None,
            "traceability_integrity_sli": None,
            "lineage_validation_mode": None,
            "lineage_defaulted": None,
            "lineage_valid": None,
        })
        assert result["decision_status"] == DECISION_FAIL

    def test_no_exception_on_garbage_input(self):
        """Absolutely no uncaught exception regardless of input."""
        for bad_input in [None, "", 0, [], {}, {"ti": "abc"}, object()]:
            try:
                result = run_slo_enforcement(bad_input)
                assert isinstance(result, dict)
                assert "decision_status" in result
            except Exception as exc:
                pytest.fail(f"run_slo_enforcement raised {type(exc).__name__}: {exc}")


# ---------------------------------------------------------------------------
# Unit tests for individual functions
# ---------------------------------------------------------------------------


class TestNormalizeEnforcementInputs:
    def test_extracts_ti_from_top_level(self):
        norm = normalize_enforcement_inputs({"traceability_integrity_sli": 1.0})
        assert norm["traceability_integrity_sli"] == 1.0

    def test_extracts_ti_from_traceability_integrity_key(self):
        norm = normalize_enforcement_inputs({"traceability_integrity": 0.5})
        assert norm["traceability_integrity_sli"] == 0.5

    def test_extracts_ti_from_nested_slis(self):
        norm = normalize_enforcement_inputs({"slis": {"traceability_integrity": 0.0}})
        assert norm["traceability_integrity_sli"] == 0.0

    def test_extracts_ti_from_outer_slo_evaluation(self):
        norm = normalize_enforcement_inputs({
            "slo_evaluation": {"slis": {"traceability_integrity": 0.0}}
        })
        assert norm["traceability_integrity_sli"] == 0.0

    def test_non_dict_returns_raw_ok_false(self):
        norm = normalize_enforcement_inputs("invalid")
        assert norm["_raw_ok"] is False

    def test_missing_fields_are_none(self):
        norm = normalize_enforcement_inputs({})
        assert norm["traceability_integrity_sli"] is None
        assert norm["lineage_validation_mode"] is None


class TestDetectInconsistencies:
    def test_no_issues_on_clean_strict_valid(self):
        norm = {
            "traceability_integrity_sli": 1.0,
            "lineage_validation_mode": "strict",
            "lineage_defaulted": False,
            "lineage_valid": True,
        }
        issues = detect_lineage_state_inconsistencies(norm)
        assert issues == []

    def test_no_issues_on_clean_degraded(self):
        norm = {
            "traceability_integrity_sli": 0.5,
            "lineage_validation_mode": "degraded",
            "lineage_defaulted": True,
            "lineage_valid": None,
        }
        issues = detect_lineage_state_inconsistencies(norm)
        assert issues == []

    def test_detects_ti_1_with_degraded_mode(self):
        norm = {
            "traceability_integrity_sli": 1.0,
            "lineage_validation_mode": "degraded",
            "lineage_defaulted": True,
            "lineage_valid": None,
        }
        issues = detect_lineage_state_inconsistencies(norm)
        assert len(issues) >= 1

    def test_detects_ti_0_5_with_defaulted_false(self):
        norm = {
            "traceability_integrity_sli": 0.5,
            "lineage_validation_mode": "degraded",
            "lineage_defaulted": False,
            "lineage_valid": None,
        }
        issues = detect_lineage_state_inconsistencies(norm)
        assert len(issues) >= 1

    def test_detects_ti_0_0_with_valid_true(self):
        norm = {
            "traceability_integrity_sli": 0.0,
            "lineage_validation_mode": "strict",
            "lineage_defaulted": False,
            "lineage_valid": True,
        }
        issues = detect_lineage_state_inconsistencies(norm)
        assert len(issues) >= 1

    def test_non_numeric_ti_returns_empty(self):
        norm = {
            "traceability_integrity_sli": "bad",
            "lineage_validation_mode": "strict",
            "lineage_defaulted": False,
            "lineage_valid": True,
        }
        issues = detect_lineage_state_inconsistencies(norm)
        assert issues == []


class TestResolveEnforcementPolicy:
    def test_explicit_policy_takes_priority(self):
        resolved = resolve_enforcement_policy(POLICY_EXPLORATORY, STAGE_SYNTHESIS)
        assert resolved == POLICY_EXPLORATORY

    def test_stage_fallback(self):
        resolved = resolve_enforcement_policy(None, STAGE_SYNTHESIS)
        assert resolved == STAGE_DEFAULT_POLICIES[STAGE_SYNTHESIS]

    def test_default_fallback(self):
        resolved = resolve_enforcement_policy(None, None)
        assert resolved == DEFAULT_POLICY

    def test_unknown_policy_falls_through_to_stage(self):
        resolved = resolve_enforcement_policy("unknown_policy", STAGE_SYNTHESIS)
        assert resolved == STAGE_DEFAULT_POLICIES[STAGE_SYNTHESIS]

    def test_unknown_stage_falls_through_to_default(self):
        resolved = resolve_enforcement_policy(None, "nonexistent_stage")
        assert resolved == DEFAULT_POLICY


class TestEvaluateTraceabilityPolicy:
    def test_permissive_1_0_allow(self):
        assert evaluate_traceability_policy(1.0, POLICY_PERMISSIVE) == DECISION_ALLOW

    def test_permissive_0_5_warn(self):
        assert evaluate_traceability_policy(0.5, POLICY_PERMISSIVE) == DECISION_ALLOW_WITH_WARNING

    def test_permissive_0_0_fail(self):
        assert evaluate_traceability_policy(0.0, POLICY_PERMISSIVE) == DECISION_FAIL

    def test_decision_grade_1_0_allow(self):
        assert evaluate_traceability_policy(1.0, POLICY_DECISION_GRADE) == DECISION_ALLOW

    def test_decision_grade_0_5_fail(self):
        assert evaluate_traceability_policy(0.5, POLICY_DECISION_GRADE) == DECISION_FAIL

    def test_decision_grade_0_0_fail(self):
        assert evaluate_traceability_policy(0.0, POLICY_DECISION_GRADE) == DECISION_FAIL

    def test_exploratory_1_0_allow(self):
        assert evaluate_traceability_policy(1.0, POLICY_EXPLORATORY) == DECISION_ALLOW

    def test_exploratory_0_5_warn(self):
        assert evaluate_traceability_policy(0.5, POLICY_EXPLORATORY) == DECISION_ALLOW_WITH_WARNING

    def test_exploratory_0_0_fail(self):
        assert evaluate_traceability_policy(0.0, POLICY_EXPLORATORY) == DECISION_FAIL

    def test_unknown_policy_fails_conservatively(self):
        assert evaluate_traceability_policy(1.0, "unknown") == DECISION_FAIL


class TestDeriveRecommendedAction:
    def test_allow_returns_proceed(self):
        assert derive_recommended_action(DECISION_ALLOW, REASON_STRICT_VALID_LINEAGE, True) == ACTION_PROCEED

    def test_fail_invalid_lineage_returns_halt_invalid(self):
        assert (
            derive_recommended_action(DECISION_FAIL, REASON_STRICT_INVALID_LINEAGE, True)
            == ACTION_HALT_INVALID_LINEAGE
        )

    def test_fail_degraded_returns_halt_degraded(self):
        assert (
            derive_recommended_action(DECISION_FAIL, REASON_DEGRADED_NO_REGISTRY, True)
            == ACTION_HALT_DEGRADED_LINEAGE
        )

    def test_inconsistency_returns_investigate(self):
        assert (
            derive_recommended_action(DECISION_FAIL, REASON_INCONSISTENT_LINEAGE_STATE, True)
            == ACTION_INVESTIGATE_INCONSISTENCY
        )

    def test_invalid_inputs_returns_fix_input(self):
        assert derive_recommended_action(DECISION_FAIL, REASON_MISSING_TI, False) == ACTION_FIX_INPUT

    def test_warn_degraded_returns_proceed_with_caution(self):
        assert (
            derive_recommended_action(DECISION_ALLOW_WITH_WARNING, REASON_DEGRADED_NO_REGISTRY, True)
            == ACTION_PROCEED_WITH_CAUTION
        )


class TestBuildSloEnforcementDecision:
    def test_all_required_fields_present(self):
        schema = _load_enforcement_schema()
        required = set(schema["required"])
        decision = build_slo_enforcement_decision(
            artifact_id="TEST-001",
            policy=POLICY_PERMISSIVE,
            stage=None,
            decision_status=DECISION_ALLOW,
            reason_code=REASON_STRICT_VALID_LINEAGE,
            ti_value=1.0,
            lineage_mode="strict",
            lineage_defaulted=False,
            lineage_valid=True,
            recommended_action=ACTION_PROCEED,
            warnings=[],
            errors=[],
            evaluated_at="2026-01-01T00:00:00+00:00",
        )
        for field in required:
            assert field in decision, f"'{field}' missing"

    def test_stage_included_when_provided(self):
        decision = build_slo_enforcement_decision(
            artifact_id="TEST-001",
            policy=POLICY_PERMISSIVE,
            stage=STAGE_SYNTHESIS,
            decision_status=DECISION_ALLOW,
            reason_code=REASON_STRICT_VALID_LINEAGE,
            ti_value=1.0,
            lineage_mode="strict",
            lineage_defaulted=False,
            lineage_valid=True,
            recommended_action=ACTION_PROCEED,
            warnings=[],
            errors=[],
        )
        assert decision.get("enforcement_scope") == STAGE_SYNTHESIS

    def test_stage_absent_when_not_provided(self):
        decision = build_slo_enforcement_decision(
            artifact_id="TEST-001",
            policy=POLICY_PERMISSIVE,
            stage=None,
            decision_status=DECISION_ALLOW,
            reason_code=REASON_STRICT_VALID_LINEAGE,
            ti_value=1.0,
            lineage_mode="strict",
            lineage_defaulted=False,
            lineage_valid=True,
            recommended_action=ACTION_PROCEED,
            warnings=[],
            errors=[],
        )
        assert "enforcement_scope" not in decision


# ---------------------------------------------------------------------------
# Additional integration / edge-case tests
# ---------------------------------------------------------------------------


class TestIntegration:
    def test_full_pipeline_allow(self):
        art = _artifact(ti=1.0, mode="strict", defaulted=False, lineage_valid=True)
        result = run_slo_enforcement(art, policy=POLICY_PERMISSIVE)
        assert result["decision_status"] == DECISION_ALLOW
        assert result["schema_errors"] == []
        d = result["enforcement_decision"]
        assert d["traceability_integrity_sli"] == 1.0
        assert d["enforcement_policy"] == POLICY_PERMISSIVE

    def test_full_pipeline_fail(self):
        art = _invalid_artifact()
        result = run_slo_enforcement(art, policy=POLICY_DECISION_GRADE, stage=STAGE_EXPORT)
        assert result["decision_status"] == DECISION_FAIL
        assert result["schema_errors"] == []
        d = result["enforcement_decision"]
        assert d["enforcement_scope"] == STAGE_EXPORT
        assert d["enforcement_policy"] == POLICY_DECISION_GRADE

    def test_ti_from_nested_slo_evaluation_slis(self):
        """run_slo_control output with nested slis is accepted (direct slis key)."""
        raw = {
            "artifact_id": "SLO-EVAL-001",
            "slis": {
                "traceability_integrity": 1.0
            },
            "lineage_validation_mode": "strict",
            "lineage_defaulted": False,
            "lineage_valid": True,
        }
        result = run_slo_enforcement(raw)
        assert result["decision_status"] == DECISION_ALLOW

    def test_ti_from_outer_wrapper_slo_evaluation(self):
        """Outer dict wrapping slo_evaluation with nested slis is accepted."""
        raw = {
            "artifact_id": "SLO-EVAL-001",
            "slo_evaluation": {
                "slis": {
                    "traceability_integrity": 1.0
                }
            },
            "lineage_validation_mode": "strict",
            "lineage_defaulted": False,
            "lineage_valid": True,
        }
        result = run_slo_enforcement(raw)
        assert result["decision_status"] == DECISION_ALLOW

    def test_decision_id_is_unique_across_calls(self):
        art = _artifact()
        r1 = run_slo_enforcement(art)
        r2 = run_slo_enforcement(art)
        assert r1["enforcement_decision"]["decision_id"] != r2["enforcement_decision"]["decision_id"]

    def test_evaluated_at_override_is_deterministic(self):
        art = _artifact()
        ts = "2026-06-01T12:00:00+00:00"
        r1 = run_slo_enforcement(art, evaluated_at=ts)
        r2 = run_slo_enforcement(art, evaluated_at=ts)
        assert r1["enforcement_decision"]["evaluated_at"] == ts
        assert r2["enforcement_decision"]["evaluated_at"] == ts

    def test_all_known_policies_produce_valid_schema(self):
        for pol in KNOWN_POLICIES:
            for art_fn in [_artifact, _degraded_artifact, _invalid_artifact]:
                result = run_slo_enforcement(art_fn(), policy=pol)
                assert result["schema_errors"] == [], (
                    f"Policy {pol!r} with {art_fn.__name__} produced schema errors"
                )
