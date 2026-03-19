"""SLO Policy Registry (BN.2) tests + governance policy registry tests.

Original tests (kept for backward compatibility):
- test_policy_registry_matches_schema
- test_policy_ids_are_unique

BN.2 tests cover:
1.  registry schema validation
2.  canonical registry file validation
3.  known policy lookup
4.  unknown policy rejection
5.  known stage lookup
6.  unknown stage rejection
7.  default stage binding correctness
8.  explicit policy override beats stage binding
9.  stage binding beats system default
10. no-stage resolution uses system default
11. slo_enforcement integration still preserves existing semantics
12. CLI --list-policies output
13. CLI --list-stages output
14. CLI --show-effective-policy output
15. malformed registry produces governed failure, not uncaught exception
16. deterministic resolution behavior
17. recommended action mappings remain stable after refactor
18. backward compatibility with current enforcement tests
"""
import io
import json
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict

import jsonschema
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = REPO_ROOT / "governance" / "policies" / "policy-registry.json"
SCHEMA_PATH = REPO_ROOT / "governance" / "policies" / "policy-registry.schema.json"

sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.modules.runtime.policy_registry import (  # noqa: E402
    CONTRACT_VERSION,
    DEFAULT_POLICY,
    KNOWN_POLICIES,
    KNOWN_STAGES,
    POLICY_DECISION_GRADE,
    POLICY_EXPLORATORY,
    POLICY_PERMISSIVE,
    REGISTRY_VERSION,
    STAGE_DEFAULT_POLICIES,
    STAGE_EXPORT,
    STAGE_INTERPRET,
    STAGE_OBSERVE,
    STAGE_RECOMMEND,
    STAGE_SYNTHESIS,
    MalformedRegistryError,
    UnknownPolicyError,
    UnknownStageError,
    describe_effective_policy,
    get_policy_profile,
    get_stage_bound_policy,
    list_slo_policies,
    list_slo_stages,
    list_stage_bindings,
    load_slo_policy_registry,
    resolve_effective_slo_policy,
    validate_policy_name,
    validate_slo_policy_registry,
    validate_stage_name,
)
from spectrum_systems.modules.runtime.slo_enforcement import (  # noqa: E402
    DECISION_ALLOW,
    DECISION_ALLOW_WITH_WARNING,
    DECISION_FAIL,
    evaluate_traceability_policy,
    resolve_enforcement_policy,
    run_slo_enforcement,
)

_REGISTRY_PATH = REPO_ROOT / "data" / "policy" / "slo_policy_registry.json"
_REGISTRY_SCHEMA_PATH = REPO_ROOT / "contracts" / "schemas" / "slo_policy_registry.schema.json"

# ---------------------------------------------------------------------------
# Original governance policy registry tests (backward compatibility)
# ---------------------------------------------------------------------------


def test_policy_registry_matches_schema() -> None:
    registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    jsonschema.validate(instance=registry, schema=schema)


def test_policy_ids_are_unique() -> None:
    registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    policy_ids = [policy["policy_id"] for policy in registry.get("policies", [])]
    assert len(policy_ids) == len(set(policy_ids))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def canonical_registry() -> Dict[str, Any]:
    """Load the canonical SLO policy registry from disk once per module."""
    return load_slo_policy_registry()


@pytest.fixture
def valid_artifact_ti_1_0() -> Dict[str, Any]:
    return {
        "artifact_id": "test-artifact-001",
        "traceability_integrity_sli": 1.0,
        "lineage_validation_mode": "strict",
        "lineage_defaulted": False,
        "lineage_valid": True,
    }


@pytest.fixture
def valid_artifact_ti_0_5() -> Dict[str, Any]:
    return {
        "artifact_id": "test-artifact-002",
        "traceability_integrity_sli": 0.5,
        "lineage_validation_mode": "degraded",
        "lineage_defaulted": True,
        "lineage_valid": None,
    }


@pytest.fixture
def valid_artifact_ti_0_0() -> Dict[str, Any]:
    return {
        "artifact_id": "test-artifact-003",
        "traceability_integrity_sli": 0.0,
        "lineage_validation_mode": "strict",
        "lineage_defaulted": False,
        "lineage_valid": False,
    }


# ---------------------------------------------------------------------------
# 1. Registry schema validation
# ---------------------------------------------------------------------------


class TestRegistrySchemaValidation:
    def test_schema_file_exists(self) -> None:
        assert _REGISTRY_SCHEMA_PATH.exists()

    def test_schema_is_valid_json(self) -> None:
        data = json.loads(_REGISTRY_SCHEMA_PATH.read_text(encoding="utf-8"))
        assert isinstance(data, dict)
        assert data.get("$schema") == "https://json-schema.org/draft/2020-12/schema"

    def test_schema_has_required_fields(self) -> None:
        schema = json.loads(_REGISTRY_SCHEMA_PATH.read_text(encoding="utf-8"))
        required = schema.get("required", [])
        assert "registry_version" in required
        assert "contract_version" in required
        assert "default_policy" in required
        assert "policies" in required
        assert "stage_bindings" in required

    def test_schema_additional_properties_false_at_root(self) -> None:
        schema = json.loads(_REGISTRY_SCHEMA_PATH.read_text(encoding="utf-8"))
        assert schema.get("additionalProperties") is False

    def test_valid_registry_passes_schema(self, canonical_registry: Dict[str, Any]) -> None:
        errors = validate_slo_policy_registry(canonical_registry)
        assert errors == []

    def test_empty_registry_fails_schema(self) -> None:
        assert len(validate_slo_policy_registry({})) > 0

    def test_unknown_default_policy_fails_schema(self) -> None:
        registry = load_slo_policy_registry()
        bad = dict(registry)
        bad["default_policy"] = "nonexistent_policy"
        assert len(validate_slo_policy_registry(bad)) > 0


# ---------------------------------------------------------------------------
# 2. Canonical registry file validation
# ---------------------------------------------------------------------------


class TestCanonicalRegistryFile:
    def test_registry_file_exists(self) -> None:
        assert _REGISTRY_PATH.exists()

    def test_registry_file_validates_against_schema(self, canonical_registry: Dict[str, Any]) -> None:
        assert validate_slo_policy_registry(canonical_registry) == []

    def test_registry_version_matches_constant(self, canonical_registry: Dict[str, Any]) -> None:
        assert canonical_registry["registry_version"] == REGISTRY_VERSION

    def test_contract_version_present(self, canonical_registry: Dict[str, Any]) -> None:
        assert canonical_registry["contract_version"] == CONTRACT_VERSION

    def test_all_three_profiles_present(self, canonical_registry: Dict[str, Any]) -> None:
        policies = canonical_registry["policies"]
        assert POLICY_PERMISSIVE in policies
        assert POLICY_DECISION_GRADE in policies
        assert POLICY_EXPLORATORY in policies

    def test_all_five_stages_bound(self, canonical_registry: Dict[str, Any]) -> None:
        bindings = canonical_registry["stage_bindings"]
        for stage in KNOWN_STAGES:
            assert stage in bindings


# ---------------------------------------------------------------------------
# 3. Known policy lookup
# ---------------------------------------------------------------------------


class TestKnownPolicyLookup:
    def test_permissive_ti_decisions(self) -> None:
        p = get_policy_profile(POLICY_PERMISSIVE)
        assert p["ti_1_0_decision"] == DECISION_ALLOW
        assert p["ti_0_5_decision"] == DECISION_ALLOW_WITH_WARNING
        assert p["ti_0_0_decision"] == DECISION_FAIL

    def test_decision_grade_ti_decisions(self) -> None:
        p = get_policy_profile(POLICY_DECISION_GRADE)
        assert p["ti_1_0_decision"] == DECISION_ALLOW
        assert p["ti_0_5_decision"] == DECISION_FAIL
        assert p["ti_0_0_decision"] == DECISION_FAIL

    def test_exploratory_ti_decisions(self) -> None:
        p = get_policy_profile(POLICY_EXPLORATORY)
        assert p["ti_1_0_decision"] == DECISION_ALLOW
        assert p["ti_0_5_decision"] == DECISION_ALLOW_WITH_WARNING
        assert p["ti_0_0_decision"] == DECISION_FAIL

    def test_permissive_warnings_permitted(self) -> None:
        assert get_policy_profile(POLICY_PERMISSIVE)["warnings_permitted"] is True

    def test_decision_grade_warnings_not_permitted(self) -> None:
        assert get_policy_profile(POLICY_DECISION_GRADE)["warnings_permitted"] is False

    def test_decision_grade_degraded_lineage_not_allowed(self) -> None:
        assert get_policy_profile(POLICY_DECISION_GRADE)["degraded_lineage_allowed"] is False

    def test_list_slo_policies_returns_all_known(self) -> None:
        assert set(list_slo_policies()) == KNOWN_POLICIES

    def test_list_slo_policies_is_sorted(self) -> None:
        policies = list_slo_policies()
        assert policies == sorted(policies)


# ---------------------------------------------------------------------------
# 4. Unknown policy rejection
# ---------------------------------------------------------------------------


class TestUnknownPolicyRejection:
    def test_get_profile_unknown_raises(self) -> None:
        with pytest.raises(UnknownPolicyError):
            get_policy_profile("not_a_policy")

    def test_validate_policy_name_unknown_raises(self) -> None:
        with pytest.raises(UnknownPolicyError):
            validate_policy_name("not_a_policy")

    def test_resolve_with_unknown_policy_raises(self) -> None:
        with pytest.raises(UnknownPolicyError):
            resolve_effective_slo_policy("ghost_policy", None)

    def test_unknown_policy_error_is_value_error(self) -> None:
        with pytest.raises(ValueError):
            get_policy_profile("bad_policy")


# ---------------------------------------------------------------------------
# 5. Known stage lookup
# ---------------------------------------------------------------------------


class TestKnownStageLookup:
    def test_list_slo_stages_returns_all_known(self) -> None:
        assert set(list_slo_stages()) == KNOWN_STAGES

    def test_list_slo_stages_is_sorted(self) -> None:
        stages = list_slo_stages()
        assert stages == sorted(stages)

    def test_get_stage_bound_policy_observe(self) -> None:
        assert get_stage_bound_policy(STAGE_OBSERVE) == POLICY_PERMISSIVE

    def test_get_stage_bound_policy_synthesis(self) -> None:
        assert get_stage_bound_policy(STAGE_SYNTHESIS) == POLICY_DECISION_GRADE

    def test_get_stage_bound_policy_export(self) -> None:
        assert get_stage_bound_policy(STAGE_EXPORT) == POLICY_DECISION_GRADE


# ---------------------------------------------------------------------------
# 6. Unknown stage rejection
# ---------------------------------------------------------------------------


class TestUnknownStageRejection:
    def test_get_stage_bound_unknown_raises(self) -> None:
        with pytest.raises(UnknownStageError):
            get_stage_bound_policy("not_a_stage")

    def test_validate_stage_name_unknown_raises(self) -> None:
        with pytest.raises(UnknownStageError):
            validate_stage_name("not_a_stage")

    def test_resolve_with_unknown_stage_raises(self) -> None:
        with pytest.raises(UnknownStageError):
            resolve_effective_slo_policy(None, "ghost_stage")

    def test_unknown_stage_error_is_value_error(self) -> None:
        with pytest.raises(ValueError):
            get_stage_bound_policy("bad_stage")


# ---------------------------------------------------------------------------
# 7. Default stage binding correctness
# ---------------------------------------------------------------------------


class TestDefaultStageBindings:
    def test_observe_bound_to_permissive(self) -> None:
        assert STAGE_DEFAULT_POLICIES[STAGE_OBSERVE] == POLICY_PERMISSIVE

    def test_interpret_bound_to_permissive(self) -> None:
        assert STAGE_DEFAULT_POLICIES[STAGE_INTERPRET] == POLICY_PERMISSIVE

    def test_recommend_bound_to_decision_grade(self) -> None:
        assert STAGE_DEFAULT_POLICIES[STAGE_RECOMMEND] == POLICY_DECISION_GRADE

    def test_synthesis_bound_to_decision_grade(self) -> None:
        assert STAGE_DEFAULT_POLICIES[STAGE_SYNTHESIS] == POLICY_DECISION_GRADE

    def test_export_bound_to_decision_grade(self) -> None:
        assert STAGE_DEFAULT_POLICIES[STAGE_EXPORT] == POLICY_DECISION_GRADE

    def test_stage_default_policies_consistent_with_registry(self) -> None:
        registry_bindings = list_stage_bindings()
        for stage, policy in STAGE_DEFAULT_POLICIES.items():
            assert registry_bindings[stage] == policy


# ---------------------------------------------------------------------------
# 8. Explicit policy override beats stage binding
# ---------------------------------------------------------------------------


class TestExplicitPolicyOverride:
    def test_explicit_beats_stage_binding(self) -> None:
        effective, source = resolve_effective_slo_policy(POLICY_PERMISSIVE, STAGE_SYNTHESIS)
        assert effective == POLICY_PERMISSIVE
        assert source == "explicit"

    def test_explicit_exploratory_beats_recommend_default(self) -> None:
        effective, source = resolve_effective_slo_policy(POLICY_EXPLORATORY, STAGE_RECOMMEND)
        assert effective == POLICY_EXPLORATORY
        assert source == "explicit"

    def test_explicit_no_stage_uses_explicit(self) -> None:
        effective, source = resolve_effective_slo_policy(POLICY_DECISION_GRADE, None)
        assert effective == POLICY_DECISION_GRADE
        assert source == "explicit"

    def test_slo_enforcement_explicit_beats_stage(
        self, valid_artifact_ti_1_0: Dict[str, Any]
    ) -> None:
        result = run_slo_enforcement(
            valid_artifact_ti_1_0, policy=POLICY_PERMISSIVE, stage=STAGE_SYNTHESIS
        )
        assert result["enforcement_decision"]["enforcement_policy"] == POLICY_PERMISSIVE


# ---------------------------------------------------------------------------
# 9. Stage binding beats system default
# ---------------------------------------------------------------------------


class TestStageBindingBeatsSystemDefault:
    def test_synthesis_returns_decision_grade(self) -> None:
        effective, source = resolve_effective_slo_policy(None, STAGE_SYNTHESIS)
        assert effective == POLICY_DECISION_GRADE
        assert source == "stage_binding"

    def test_recommend_returns_decision_grade(self) -> None:
        effective, source = resolve_effective_slo_policy(None, STAGE_RECOMMEND)
        assert effective == POLICY_DECISION_GRADE
        assert source == "stage_binding"

    def test_observe_returns_permissive_via_binding(self) -> None:
        effective, source = resolve_effective_slo_policy(None, STAGE_OBSERVE)
        assert effective == POLICY_PERMISSIVE
        assert source == "stage_binding"


# ---------------------------------------------------------------------------
# 10. No-stage resolution uses system default
# ---------------------------------------------------------------------------


class TestNoStageResolution:
    def test_no_policy_no_stage_returns_default(self) -> None:
        effective, source = resolve_effective_slo_policy(None, None)
        assert effective == DEFAULT_POLICY
        assert source == "system_default"

    def test_default_policy_is_permissive(self) -> None:
        assert DEFAULT_POLICY == POLICY_PERMISSIVE

    def test_registry_default_matches_constant(self, canonical_registry: Dict[str, Any]) -> None:
        assert canonical_registry["default_policy"] == DEFAULT_POLICY

    def test_slo_enforcement_no_policy_no_stage_is_permissive(
        self, valid_artifact_ti_0_5: Dict[str, Any]
    ) -> None:
        result = run_slo_enforcement(valid_artifact_ti_0_5)
        assert result["enforcement_decision"]["enforcement_policy"] == POLICY_PERMISSIVE
        assert result["decision_status"] == DECISION_ALLOW_WITH_WARNING


# ---------------------------------------------------------------------------
# 11. slo_enforcement integration preserves existing semantics
# ---------------------------------------------------------------------------


class TestSloEnforcementIntegration:
    def test_permissive_ti_1_0_allows(self, valid_artifact_ti_1_0: Dict[str, Any]) -> None:
        result = run_slo_enforcement(valid_artifact_ti_1_0, policy=POLICY_PERMISSIVE)
        assert result["decision_status"] == DECISION_ALLOW

    def test_permissive_ti_0_5_warns(self, valid_artifact_ti_0_5: Dict[str, Any]) -> None:
        result = run_slo_enforcement(valid_artifact_ti_0_5, policy=POLICY_PERMISSIVE)
        assert result["decision_status"] == DECISION_ALLOW_WITH_WARNING

    def test_permissive_ti_0_0_fails(self, valid_artifact_ti_0_0: Dict[str, Any]) -> None:
        result = run_slo_enforcement(valid_artifact_ti_0_0, policy=POLICY_PERMISSIVE)
        assert result["decision_status"] == DECISION_FAIL

    def test_decision_grade_ti_1_0_allows(self, valid_artifact_ti_1_0: Dict[str, Any]) -> None:
        result = run_slo_enforcement(valid_artifact_ti_1_0, policy=POLICY_DECISION_GRADE)
        assert result["decision_status"] == DECISION_ALLOW

    def test_decision_grade_ti_0_5_fails(self, valid_artifact_ti_0_5: Dict[str, Any]) -> None:
        result = run_slo_enforcement(valid_artifact_ti_0_5, policy=POLICY_DECISION_GRADE)
        assert result["decision_status"] == DECISION_FAIL

    def test_decision_grade_ti_0_0_fails(self, valid_artifact_ti_0_0: Dict[str, Any]) -> None:
        result = run_slo_enforcement(valid_artifact_ti_0_0, policy=POLICY_DECISION_GRADE)
        assert result["decision_status"] == DECISION_FAIL

    def test_exploratory_ti_0_5_warns(self, valid_artifact_ti_0_5: Dict[str, Any]) -> None:
        result = run_slo_enforcement(valid_artifact_ti_0_5, policy=POLICY_EXPLORATORY)
        assert result["decision_status"] == DECISION_ALLOW_WITH_WARNING

    def test_synthesis_stage_decision_grade_default(
        self, valid_artifact_ti_0_5: Dict[str, Any]
    ) -> None:
        result = run_slo_enforcement(valid_artifact_ti_0_5, stage=STAGE_SYNTHESIS)
        assert result["decision_status"] == DECISION_FAIL
        assert result["enforcement_decision"]["enforcement_policy"] == POLICY_DECISION_GRADE

    def test_observe_stage_permissive_default(
        self, valid_artifact_ti_0_5: Dict[str, Any]
    ) -> None:
        result = run_slo_enforcement(valid_artifact_ti_0_5, stage=STAGE_OBSERVE)
        assert result["decision_status"] == DECISION_ALLOW_WITH_WARNING
        assert result["enforcement_decision"]["enforcement_policy"] == POLICY_PERMISSIVE

    def test_evaluate_traceability_policy_permissive(self) -> None:
        assert evaluate_traceability_policy(1.0, POLICY_PERMISSIVE) == DECISION_ALLOW
        assert evaluate_traceability_policy(0.5, POLICY_PERMISSIVE) == DECISION_ALLOW_WITH_WARNING
        assert evaluate_traceability_policy(0.0, POLICY_PERMISSIVE) == DECISION_FAIL

    def test_evaluate_traceability_policy_decision_grade(self) -> None:
        assert evaluate_traceability_policy(1.0, POLICY_DECISION_GRADE) == DECISION_ALLOW
        assert evaluate_traceability_policy(0.5, POLICY_DECISION_GRADE) == DECISION_FAIL
        assert evaluate_traceability_policy(0.0, POLICY_DECISION_GRADE) == DECISION_FAIL

    def test_evaluate_traceability_policy_exploratory(self) -> None:
        assert evaluate_traceability_policy(1.0, POLICY_EXPLORATORY) == DECISION_ALLOW
        assert evaluate_traceability_policy(0.5, POLICY_EXPLORATORY) == DECISION_ALLOW_WITH_WARNING
        assert evaluate_traceability_policy(0.0, POLICY_EXPLORATORY) == DECISION_FAIL

    def test_resolve_enforcement_policy_delegates(self) -> None:
        assert resolve_enforcement_policy(None, None) == DEFAULT_POLICY
        assert resolve_enforcement_policy(None, STAGE_SYNTHESIS) == POLICY_DECISION_GRADE
        assert resolve_enforcement_policy(POLICY_EXPLORATORY, STAGE_SYNTHESIS) == POLICY_EXPLORATORY


# ---------------------------------------------------------------------------
# 12. CLI --list-policies output
# ---------------------------------------------------------------------------


def _run_cli(argv: list) -> tuple:
    """Run the CLI entry point, capture stdout/stderr, return (exit_code, stdout, stderr)."""
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    from scripts.run_slo_enforcement import main  # noqa: PLC0415
    buf_out = io.StringIO()
    buf_err = io.StringIO()
    old_out, old_err = sys.stdout, sys.stderr
    try:
        sys.stdout = buf_out
        sys.stderr = buf_err
        exit_code = main(argv)
    finally:
        sys.stdout = old_out
        sys.stderr = old_err
    return exit_code, buf_out.getvalue(), buf_err.getvalue()


class TestCLIListPolicies:
    def test_list_policies_exit_code_0(self) -> None:
        exit_code, _, _ = _run_cli(["--list-policies"])
        assert exit_code == 0

    def test_list_policies_stdout_contains_all_policies(self) -> None:
        _, stdout, _ = _run_cli(["--list-policies"])
        for policy in KNOWN_POLICIES:
            assert policy in stdout

    def test_list_policies_output_is_deterministic(self) -> None:
        _, stdout1, _ = _run_cli(["--list-policies"])
        _, stdout2, _ = _run_cli(["--list-policies"])
        assert stdout1 == stdout2


# ---------------------------------------------------------------------------
# 13. CLI --list-stages output
# ---------------------------------------------------------------------------


class TestCLIListStages:
    def test_list_stages_exit_code_0(self) -> None:
        exit_code, _, _ = _run_cli(["--list-stages"])
        assert exit_code == 0

    def test_list_stages_stdout_contains_all_stages(self) -> None:
        _, stdout, _ = _run_cli(["--list-stages"])
        for stage in KNOWN_STAGES:
            assert stage in stdout

    def test_list_stages_stdout_contains_binding(self) -> None:
        _, stdout, _ = _run_cli(["--list-stages"])
        assert "decision_grade" in stdout
        assert "permissive" in stdout

    def test_list_stages_output_is_deterministic(self) -> None:
        _, stdout1, _ = _run_cli(["--list-stages"])
        _, stdout2, _ = _run_cli(["--list-stages"])
        assert stdout1 == stdout2


# ---------------------------------------------------------------------------
# 14. CLI --show-effective-policy output
# ---------------------------------------------------------------------------


class TestCLIShowEffectivePolicy:
    def test_show_effective_policy_exit_code_0(self) -> None:
        exit_code, _, _ = _run_cli(["--show-effective-policy"])
        assert exit_code == 0

    def test_show_effective_policy_default_is_permissive(self) -> None:
        _, stdout, _ = _run_cli(["--show-effective-policy"])
        assert "permissive" in stdout

    def test_show_effective_policy_resolution_source_system_default(self) -> None:
        _, stdout, _ = _run_cli(["--show-effective-policy"])
        assert "system_default" in stdout

    def test_show_effective_policy_explicit_override(self) -> None:
        _, stdout, _ = _run_cli(["--show-effective-policy", "--policy", "decision_grade"])
        assert "decision_grade" in stdout
        assert "explicit" in stdout

    def test_show_effective_policy_stage_binding(self) -> None:
        _, stdout, _ = _run_cli(["--show-effective-policy", "--stage", "synthesis"])
        assert "decision_grade" in stdout
        assert "stage_binding" in stdout

    def test_show_effective_policy_output_is_deterministic(self) -> None:
        _, stdout1, _ = _run_cli(["--show-effective-policy", "--stage", "synthesis"])
        _, stdout2, _ = _run_cli(["--show-effective-policy", "--stage", "synthesis"])
        assert stdout1 == stdout2


# ---------------------------------------------------------------------------
# 15. Malformed registry produces governed failure, not uncaught exception
# ---------------------------------------------------------------------------


class TestMalformedRegistryHandling:
    def test_nonexistent_file_raises_malformed_error(self) -> None:
        with pytest.raises(MalformedRegistryError):
            load_slo_policy_registry(Path("/nonexistent/path/registry.json"))

    def test_invalid_json_raises_malformed_error(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("{not valid json")
            tmp_path = Path(f.name)
        try:
            with pytest.raises(MalformedRegistryError):
                load_slo_policy_registry(tmp_path)
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_validate_empty_dict_returns_errors(self) -> None:
        errors = validate_slo_policy_registry({})
        assert len(errors) > 0

    def test_describe_effective_policy_with_unknown_policy_returns_error_field(self) -> None:
        info = describe_effective_policy("ghost_policy", None)
        assert info["error"] is not None
        assert info["effective_policy"] is None


# ---------------------------------------------------------------------------
# 16. Deterministic resolution behavior
# ---------------------------------------------------------------------------


class TestDeterministicResolution:
    def test_resolution_is_deterministic_explicit(self) -> None:
        results = [resolve_effective_slo_policy(POLICY_DECISION_GRADE, None) for _ in range(5)]
        assert all(r == results[0] for r in results)

    def test_resolution_is_deterministic_stage(self) -> None:
        results = [resolve_effective_slo_policy(None, STAGE_SYNTHESIS) for _ in range(5)]
        assert all(r == results[0] for r in results)

    def test_resolution_is_deterministic_default(self) -> None:
        results = [resolve_effective_slo_policy(None, None) for _ in range(5)]
        assert all(r == results[0] for r in results)

    def test_profile_lookup_is_deterministic(self) -> None:
        profiles = [get_policy_profile(POLICY_PERMISSIVE) for _ in range(5)]
        assert all(p == profiles[0] for p in profiles)


# ---------------------------------------------------------------------------
# 17. Recommended action mappings remain stable after refactor
# ---------------------------------------------------------------------------


class TestRecommendedActionMappings:
    def test_permissive_allow_recommends_proceed(self) -> None:
        assert get_policy_profile(POLICY_PERMISSIVE)["recommended_actions"]["allow"] == "proceed"

    def test_permissive_allow_with_warning_recommends_proceed_with_caution(self) -> None:
        profile = get_policy_profile(POLICY_PERMISSIVE)
        assert profile["recommended_actions"]["allow_with_warning"] == "proceed_with_caution"

    def test_decision_grade_allow_recommends_proceed(self) -> None:
        assert get_policy_profile(POLICY_DECISION_GRADE)["recommended_actions"]["allow"] == "proceed"

    def test_decision_grade_fail_recommends_halt(self) -> None:
        assert get_policy_profile(POLICY_DECISION_GRADE)["recommended_actions"]["fail"] == "halt_and_review"

    def test_all_profiles_have_required_recommended_actions(self) -> None:
        for policy in KNOWN_POLICIES:
            actions = get_policy_profile(policy).get("recommended_actions", {})
            assert DECISION_ALLOW in actions
            assert DECISION_ALLOW_WITH_WARNING in actions
            assert DECISION_FAIL in actions


# ---------------------------------------------------------------------------
# 18. Backward compatibility with current enforcement constants
# ---------------------------------------------------------------------------


class TestBackwardCompatibility:
    def test_known_policies_unchanged(self) -> None:
        from spectrum_systems.modules.runtime.slo_enforcement import KNOWN_POLICIES as EP
        assert EP == frozenset({POLICY_PERMISSIVE, POLICY_DECISION_GRADE, POLICY_EXPLORATORY})

    def test_stage_default_policies_unchanged(self) -> None:
        from spectrum_systems.modules.runtime.slo_enforcement import STAGE_DEFAULT_POLICIES as SDP
        assert SDP[STAGE_OBSERVE] == POLICY_PERMISSIVE
        assert SDP[STAGE_SYNTHESIS] == POLICY_DECISION_GRADE
        assert SDP[STAGE_EXPORT] == POLICY_DECISION_GRADE

    def test_policy_constants_accessible_from_slo_enforcement(self) -> None:
        from spectrum_systems.modules.runtime.slo_enforcement import (
            POLICY_PERMISSIVE as PP,
            POLICY_DECISION_GRADE as PDG,
            POLICY_EXPLORATORY as PE,
        )
        assert PP == POLICY_PERMISSIVE
        assert PDG == POLICY_DECISION_GRADE
        assert PE == POLICY_EXPLORATORY

    def test_stage_constants_accessible_from_slo_enforcement(self) -> None:
        from spectrum_systems.modules.runtime.slo_enforcement import (
            STAGE_OBSERVE as SO,
            STAGE_SYNTHESIS as SS,
            STAGE_EXPORT as SE,
        )
        assert SO == STAGE_OBSERVE
        assert SS == STAGE_SYNTHESIS
        assert SE == STAGE_EXPORT

    def test_resolve_enforcement_policy_still_works(self) -> None:
        from spectrum_systems.modules.runtime.slo_enforcement import resolve_enforcement_policy
        assert resolve_enforcement_policy(None, None) == POLICY_PERMISSIVE
        assert resolve_enforcement_policy(None, STAGE_SYNTHESIS) == POLICY_DECISION_GRADE

    def test_describe_effective_policy_diagnostics(self) -> None:
        info = describe_effective_policy(None, STAGE_SYNTHESIS)
        assert info["effective_policy"] == POLICY_DECISION_GRADE
        assert info["resolution_source"] == "stage_binding"
        assert info["error"] is None

