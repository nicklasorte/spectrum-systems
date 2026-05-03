"""CLP-02 — Tests for the core_loop_pre_pr_gate policy artifact and loader.

Validates that:
- the policy file is well-formed JSON with the expected fields
- the policy is observation_only (CLP must not claim authority)
- the policy lists the canonical required checks
- the loader fail-closes on missing / malformed / authority-shifted policies
- block reason codes cover the AGL-01 failure surface
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from spectrum_systems.modules.runtime.core_loop_pre_pr_gate import (
    REQUIRED_CHECK_NAMES,
)
from spectrum_systems.modules.runtime.core_loop_pre_pr_gate_policy import (
    DEFAULT_POLICY_REL_PATH,
    PolicyLoadError,
    load_policy,
)

ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / DEFAULT_POLICY_REL_PATH


def test_policy_file_exists_and_loads():
    assert POLICY_PATH.is_file(), POLICY_PATH
    policy = load_policy(POLICY_PATH)
    assert policy["policy_id"] == "CLP-02"
    assert policy["schema_version"] == "1.0.0"


def test_policy_authority_scope_is_observation_only():
    policy = load_policy(POLICY_PATH)
    # CLP must not claim binding authority. The policy declares authority_scope
    # as "observation_only" and lists forbidden actions in must_not_do (using
    # the verbs there is correct; that field forbids the action, not claims it).
    assert policy["authority_scope"] == "observation_only"
    # Spot-check authority-claiming surfaces never assert binding authority.
    for key in ("authority_scope",):
        value = policy.get(key)
        assert value == "observation_only", (key, value)
    # Owners' policy_owner is TPA (authority owner), not CLP.
    assert policy["owners"]["policy_owner"] == "TPA"
    assert policy["owners"]["evidence_runner"] == "CLP"


def test_policy_required_check_observations_cover_canonical_checks():
    policy = load_policy(POLICY_PATH)
    aliases = set(policy["required_check_observations"])
    expected = {f"{name}_observation" for name in REQUIRED_CHECK_NAMES}
    # The policy lists CLP-02 observation aliases for the canonical CLP-01
    # check set. The CLP-02 alias "contract_compliance_observation"
    # corresponds to CLP-01's "contract_enforcement" canonical name; both
    # must remain in lock-step.
    contract_alias = "contract_compliance_observation"
    expected_contract_alias = "contract_enforcement_observation"
    assert expected_contract_alias in expected
    expected.remove(expected_contract_alias)
    expected.add(contract_alias)
    assert aliases == expected


def test_policy_must_not_do_blocks_authority_overreach():
    policy = load_policy(POLICY_PATH)
    must_not = set(policy["must_not_do"])
    # CLP must explicitly forbid claiming GOV review_observation, GOV
    # readiness_evidence, REL readiness_handoff, SEL final_gate_signal,
    # AEX admission_input, PQX execution_input, and CDE continuation_input
    # ownership. Each constraint is named with a safety-suffixed identifier.
    for term in {
        "claim_review_observation_authority",
        "claim_readiness_evidence_authority",
        "claim_readiness_handoff_recommendation_authority",
        "claim_compliance_observation_authority",
        "claim_admission_input_authority",
        "claim_execution_input_authority",
        "claim_continuation_input_authority",
        "auto_apply_repairs",
        "suppress_existing_gates",
    }:
        assert term in must_not, term


def test_policy_block_reason_codes_cover_agl01_surface():
    policy = load_policy(POLICY_PATH)
    blocks = set(policy["block_reason_codes"])
    for code in {
        "authority_shape_violation",
        "authority_leak_guard_failure",
        "tls_generated_artifact_stale",
        "contract_mismatch",
        "schema_violation",
        "missing_required_artifact",
        "missing_required_check_output",
        "selected_test_failure",
        "no_tests_selected_for_governed_changes",
    }:
        assert code in blocks, code


def test_policy_rules_include_fail_closed_invariants():
    policy = load_policy(POLICY_PATH)
    rules = policy["rules"]
    assert rules["repo_mutating_requires_clp_evidence"] is True
    assert rules["missing_clp_evidence_blocks_pr_ready"] is True
    assert rules["clp_block_blocks_pr_ready"] is True
    assert rules["clp_warn_requires_explicit_allow"] is True
    assert rules["selected_tests_missing_for_governed_surfaces_blocks"] is True
    assert rules["generated_artifact_freshness_failure_blocks"] is True
    assert rules["contract_mismatch_blocks"] is True
    assert rules["schema_violation_blocks"] is True
    assert rules["authority_shape_violation_blocks"] is True
    assert rules["authority_leak_guard_failure_blocks"] is True
    assert rules["authority_scope_must_be_observation_only"] is True


def test_loader_fails_closed_on_missing_file(tmp_path):
    with pytest.raises(PolicyLoadError):
        load_policy(tmp_path / "nope.json")


def test_loader_fails_closed_on_malformed_json(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("not json", encoding="utf-8")
    with pytest.raises(PolicyLoadError):
        load_policy(bad)


def test_loader_fails_closed_on_wrong_policy_id(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(
        json.dumps(
            {
                "policy_id": "OTHER",
                "authority_scope": "observation_only",
                "required_check_observations": ["selected_tests_observation"],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(PolicyLoadError):
        load_policy(bad)


def test_loader_fails_closed_on_authority_drift(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(
        json.dumps(
            {
                "policy_id": "CLP-02",
                "authority_scope": "binding",
                "required_check_observations": ["selected_tests_observation"],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(PolicyLoadError):
        load_policy(bad)


def test_loader_fails_closed_on_empty_required_check_observations(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(
        json.dumps(
            {
                "policy_id": "CLP-02",
                "authority_scope": "observation_only",
                "required_check_observations": [],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(PolicyLoadError):
        load_policy(bad)


def test_policy_max_repair_attempts_is_zero():
    """CLP-02 must not auto-fix. PRL/FRE/CDE/PQX own repair authority."""
    policy = load_policy(POLICY_PATH)
    assert policy["max_repair_attempts"] == 0


# ---------------------------------------------------------------------------
# EVL-RT-04: shard-first readiness in CLP policy
# ---------------------------------------------------------------------------


def test_policy_lists_shard_first_readiness_observation_alias():
    policy = load_policy(POLICY_PATH)
    aliases = set(policy["required_check_observations"])
    assert "evl_shard_first_readiness_observation" in aliases


def test_policy_block_codes_cover_shard_first_failures():
    policy = load_policy(POLICY_PATH)
    blocks = set(policy["block_reason_codes"])
    for code in {
        "evl_shard_first_readiness_missing",
        "evl_shard_first_readiness_invalid",
        "evl_shard_first_readiness_partial",
        "evl_shard_first_readiness_unknown",
        "evl_shard_first_readiness_fallback_unjustified",
        "evl_shard_first_readiness_shard_refs_empty",
        "pr_test_shard_first_readiness_observation_missing",
        "pr_test_shard_first_readiness_observation_invalid",
        "fallback_signal_without_fallback_justification_ref",
        "fallback_signal_without_fallback_reason_codes",
    }:
        assert code in blocks, code


def test_policy_rules_include_shard_first_invariants():
    policy = load_policy(POLICY_PATH)
    rules = policy["rules"]
    assert rules["evl_shard_first_readiness_required"] is True
    assert rules["evl_shard_first_missing_blocks"] is True
    assert rules["evl_shard_first_partial_blocks"] is True
    assert rules["evl_shard_first_unknown_blocks"] is True
    assert rules["evl_shard_first_fallback_without_justification_blocks"] is True


def test_policy_shard_first_evidence_section():
    policy = load_policy(POLICY_PATH)
    section = policy.get("evl_shard_first_readiness_evidence")
    assert isinstance(section, dict)
    assert (
        section["observation_path"]
        == "outputs/pr_test_shard_first_readiness/"
        "pr_test_shard_first_readiness_observation.json"
    )
    assert isinstance(section.get("allowed_fallback_reason_codes"), list)
    assert section.get("invoke_builder_if_missing") is False
    notes = section.get("notes") or ""
    # Authority-safe vocabulary in the policy notes.
    forbidden = {
        "approve",
        "approval",
        "certify",
        "certification",
        "promote",
        "promotion",
        "enforce",
        "enforcement",
        "verdict",
    }
    lowered = notes.lower()
    for term in forbidden:
        assert term not in lowered, term


def test_policy_authority_safe_vocabulary_overall():
    """Overall scan: no authority-binding verbs leak into the policy file."""
    text = POLICY_PATH.read_text(encoding="utf-8").lower()
    forbidden_phrases = {
        '"approve"',
        '"certify"',
        '"promote"',
        '"enforce"',
        '"verdict"',
        '"decide"',
        '"authorize"',
        "binding authority",
    }
    for phrase in forbidden_phrases:
        assert phrase not in text, phrase
