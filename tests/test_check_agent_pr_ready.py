"""CLP-02 — Tests for the agent_pr_ready guard and PRL CLP consumer.

Validates that:
- evaluate_pr_ready fail-closes on missing CLP evidence
- CLP block always produces pr_ready_status=not_ready
- CLP warn with unapproved reason codes blocks
- CLP warn with approved reason codes is allowed
- CLP block normalizes into PRL KNOWN_FAILURE_CLASSES via clp_consumer
- the agent_pr_ready_result example artifact validates against its schema
- the artifact never claims approval/certification/promotion/enforcement
  authority
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from spectrum_systems.contracts import validate_artifact
from spectrum_systems.modules.prl.clp_consumer import (
    CLP_TO_PRL_FAILURE_CLASS,
    parsed_failures_from_clp_result,
)
from spectrum_systems.modules.prl.failure_classifier import (
    KNOWN_FAILURE_CLASSES as PRL_KNOWN,
)
from spectrum_systems.modules.runtime.core_loop_pre_pr_gate import (
    REQUIRED_CHECK_NAMES,
    build_check,
    build_gate_result,
)
from spectrum_systems.modules.runtime.core_loop_pre_pr_gate_policy import (
    DEFAULT_POLICY_REL_PATH,
    build_agent_pr_ready_result,
    evaluate_pr_ready,
    load_policy,
    pr_ready_status_to_exit_code,
)

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def policy() -> dict:
    return load_policy(ROOT / DEFAULT_POLICY_REL_PATH)


def _all_pass_clp() -> dict:
    return build_gate_result(
        work_item_id="CLP-02-TEST",
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


def _block_clp(check_name: str, failure_class: str, reason_code: str) -> dict:
    checks = [
        build_check(
            check_name=name,
            command="echo ok",
            status="pass",
            output_ref=f"outputs/{name}.json",
        )
        for name in REQUIRED_CHECK_NAMES
        if name != check_name
    ]
    checks.append(
        build_check(
            check_name=check_name,
            command="echo blocking",
            status="block",
            output_ref=f"outputs/{check_name}.json",
            failure_class=failure_class,
            reason_codes=[reason_code],
        )
    )
    return build_gate_result(
        work_item_id="CLP-02-BLOCK",
        agent_type="claude",
        repo_mutating=True,
        base_ref="origin/main",
        head_ref="HEAD",
        changed_files=["scripts/x.py"],
        checks=checks,
    )


def _warn_clp(reason_code: str, *, check_name: str = "contract_enforcement") -> dict:
    checks = [
        build_check(
            check_name=name,
            command="echo ok",
            status="pass",
            output_ref=f"outputs/{name}.json",
        )
        for name in REQUIRED_CHECK_NAMES
        if name != check_name
    ]
    checks.append(
        build_check(
            check_name=check_name,
            command="echo warn",
            status="warn",
            output_ref=f"outputs/{check_name}.json",
            failure_class="policy_mismatch",
            reason_codes=[reason_code],
        )
    )
    return build_gate_result(
        work_item_id="CLP-02-WARN",
        agent_type="claude",
        repo_mutating=True,
        base_ref="origin/main",
        head_ref="HEAD",
        changed_files=["scripts/x.py"],
        checks=checks,
    )


# ---------------------------------------------------------------------------
# Schema + example
# ---------------------------------------------------------------------------


def test_example_artifact_validates():
    example = json.loads(
        (ROOT / "contracts" / "examples" / "agent_pr_ready_result.example.json").read_text(
            encoding="utf-8"
        )
    )
    validate_artifact(example, "agent_pr_ready_result")


def test_artifact_authority_scope_is_observation_only(policy):
    eval_ = evaluate_pr_ready(policy=policy, clp_result=_all_pass_clp())
    artifact = build_agent_pr_ready_result(
        work_item_id="W",
        agent_type="claude",
        policy_ref=DEFAULT_POLICY_REL_PATH,
        clp_result_ref="outputs/clp.json",
        evaluation=eval_,
    )
    validate_artifact(artifact, "agent_pr_ready_result")
    assert artifact["authority_scope"] == "observation_only"
    bad = dict(artifact)
    bad["authority_scope"] = "binding"
    with pytest.raises(Exception):
        validate_artifact(bad, "agent_pr_ready_result")


def test_artifact_does_not_claim_authority(policy):
    eval_ = evaluate_pr_ready(policy=policy, clp_result=_all_pass_clp())
    artifact = build_agent_pr_ready_result(
        work_item_id="W",
        agent_type="claude",
        policy_ref=DEFAULT_POLICY_REL_PATH,
        clp_result_ref="outputs/clp.json",
        evaluation=eval_,
    )
    forbidden = {"approval", "certified", "promoted", "enforced"}
    blob = json.dumps(artifact).lower()
    for term in forbidden:
        assert f'"{term}"' not in blob, term


def test_exit_code_mapping():
    assert pr_ready_status_to_exit_code("ready") == 0
    assert pr_ready_status_to_exit_code("human_review_required") == 1
    assert pr_ready_status_to_exit_code("not_ready") == 2


# ---------------------------------------------------------------------------
# evaluate_pr_ready core rules
# ---------------------------------------------------------------------------


def test_missing_clp_blocks_pr_ready_for_repo_mutating(policy):
    eval_ = evaluate_pr_ready(policy=policy, clp_result=None, repo_mutating=True)
    assert eval_["pr_ready_status"] == "not_ready"
    assert "clp_evidence_missing" in eval_["reason_codes"]


def test_clp_pass_allows_pr_ready(policy):
    eval_ = evaluate_pr_ready(policy=policy, clp_result=_all_pass_clp())
    assert eval_["pr_ready_status"] == "ready"
    assert eval_["clp_gate_status"] == "pass"
    assert eval_["reason_codes"] == []


def test_clp_block_blocks_pr_ready(policy):
    eval_ = evaluate_pr_ready(
        policy=policy,
        clp_result=_block_clp(
            "authority_shape_preflight",
            "authority_shape_violation",
            "authority_shape_review_language_lint",
        ),
    )
    assert eval_["pr_ready_status"] == "not_ready"
    assert "authority_shape_violation" in eval_["reason_codes"]


def test_warn_with_unallowed_reason_blocks(policy):
    """Default policy.allowed_warn_reason_codes = []. Any warn must block."""
    eval_ = evaluate_pr_ready(policy=policy, clp_result=_warn_clp("soft_finding"))
    assert eval_["pr_ready_status"] == "not_ready"
    assert "clp_warn_not_policy_allowed" in eval_["reason_codes"]


def test_warn_with_policy_allowed_reason_passes(policy):
    """Local policy override: allow a specific reason code."""
    local_policy = dict(policy)
    local_policy["allowed_warn_reason_codes"] = ["soft_finding"]
    eval_ = evaluate_pr_ready(
        policy=local_policy, clp_result=_warn_clp("soft_finding")
    )
    assert eval_["pr_ready_status"] == "ready"


def test_clp_authority_drift_blocks(policy):
    drifted = _all_pass_clp()
    drifted["authority_scope"] = "binding"
    eval_ = evaluate_pr_ready(policy=policy, clp_result=drifted)
    assert eval_["pr_ready_status"] == "not_ready"
    assert "clp_authority_scope_invalid" in eval_["reason_codes"]


def test_clp_human_review_required_propagates(policy):
    drifted = _all_pass_clp()
    drifted["gate_status"] = "block"
    drifted["first_failed_check"] = "contract_enforcement"
    drifted["failure_classes"] = ["completely_unknown_failure"]
    drifted["human_review_required"] = True
    eval_ = evaluate_pr_ready(policy=policy, clp_result=drifted)
    assert eval_["pr_ready_status"] == "human_review_required"
    assert eval_["human_review_required"] is True


# ---------------------------------------------------------------------------
# PRL CLP consumer
# ---------------------------------------------------------------------------


def test_clp_block_normalizes_to_prl_classes():
    """Every CLP failure class in the policy block list maps to a known PRL class."""
    blocking = _block_clp(
        "tls_generated_artifact_freshness",
        "tls_generated_artifact_stale",
        "tls_generated_artifact_drift",
    )
    failures = parsed_failures_from_clp_result(blocking, clp_path="outputs/clp.json")
    assert failures, "expected at least one ParsedFailure for a CLP block"
    for parsed in failures:
        assert parsed.failure_class in PRL_KNOWN, parsed.failure_class


def test_clp_consumer_returns_empty_on_pass():
    failures = parsed_failures_from_clp_result(_all_pass_clp())
    assert failures == []


def test_clp_consumer_handles_top_level_failures_only():
    """Fallback path: failure_classes present but no per-check block."""
    payload = _all_pass_clp()
    payload["gate_status"] = "block"
    payload["failure_classes"] = ["contract_mismatch"]
    payload["first_failed_check"] = "contract_preflight"
    failures = parsed_failures_from_clp_result(payload, clp_path="outputs/clp.json")
    assert any(p.failure_class == "contract_schema_violation" for p in failures)


def test_clp_to_prl_mapping_covers_known_failure_classes():
    """Every mapped value must be a canonical PRL class."""
    for clp_code, prl_class in CLP_TO_PRL_FAILURE_CLASS.items():
        assert prl_class in PRL_KNOWN, (clp_code, prl_class)


# ---------------------------------------------------------------------------
# Required checks coverage
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "check_name,failure_class,reason_code",
    [
        ("authority_shape_preflight", "authority_shape_violation", "authority_shape_review_language_lint"),
        ("authority_leak_guard", "authority_leak_violation", "forbidden_authority_value"),
        ("contract_enforcement", "contract_enforcement_violation", "contract_compliance_findings"),
        ("tls_generated_artifact_freshness", "tls_generated_artifact_stale", "tls_generated_artifact_drift"),
        ("contract_preflight", "contract_preflight_block", "block"),
        ("selected_tests", "pytest_selection_missing", "no_tests_selected_for_governed_changes"),
    ],
)
def test_each_required_check_block_blocks_pr_ready(
    policy, check_name, failure_class, reason_code
):
    clp = _block_clp(check_name, failure_class, reason_code)
    eval_ = evaluate_pr_ready(policy=policy, clp_result=clp)
    assert eval_["pr_ready_status"] != "ready"


def test_missing_required_check_output_blocks_pr_ready(policy):
    """Drop authority_shape from the checks list — CLP gate_status must be block."""
    checks = [
        build_check(
            check_name=name,
            command="echo ok",
            status="pass",
            output_ref=f"outputs/{name}.json",
        )
        for name in REQUIRED_CHECK_NAMES
        if name != "authority_shape_preflight"
    ]
    clp = build_gate_result(
        work_item_id="CLP-02-MISSING-CHECK",
        agent_type="claude",
        repo_mutating=True,
        base_ref="origin/main",
        head_ref="HEAD",
        changed_files=["scripts/x.py"],
        checks=checks,
    )
    assert clp["gate_status"] == "block"
    eval_ = evaluate_pr_ready(policy=policy, clp_result=clp)
    assert eval_["pr_ready_status"] == "not_ready"
    assert "missing_required_check_output" in eval_["reason_codes"]
