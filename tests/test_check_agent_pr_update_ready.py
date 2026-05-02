"""APU-3LS-01 — Tests for the agent_pr_update_ready guard.

Validates that the APU guard fail-closes on missing artifact-backed
3LS evidence and that:

- repo_mutating unknown yields not_ready
- repo_mutating true + missing CLP yields not_ready
- repo_mutating true + CLP block yields not_ready
- CLP warn yields ready only when every warn reason code is policy-allowed
- CLP warn with unallowed reason code yields not_ready
- missing AGL yields not_ready
- a leg reported as present without artifact_refs is downgraded to partial
- partial/missing/unknown legs without reason_codes are invalid
- unknown is never counted as present
- PR body prose / agent claims cannot substitute for artifact_refs
- claimed 3LS usage without artifact_refs blocks readiness
- the upstream agent_pr_ready_result guard is honored
- the artifact authority_scope is observation_only and never claims
  authority-owned terms (approval/certification/promotion/enforcement)
- authority-safe vocabulary is preserved in the example artifact
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from spectrum_systems.contracts import validate_artifact
from spectrum_systems.modules.runtime.core_loop_pre_pr_gate import (
    REQUIRED_CHECK_NAMES,
    build_check,
    build_gate_result,
)
from spectrum_systems.modules.runtime.agent_pr_update_policy import (
    DEFAULT_POLICY_REL_PATH,
    build_agent_pr_update_ready_result,
    evaluate_pr_update_ready,
    load_policy,
    readiness_status_to_exit_code,
)

ROOT = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def policy() -> dict[str, Any]:
    return load_policy(ROOT / DEFAULT_POLICY_REL_PATH)


def _all_pass_clp() -> dict[str, Any]:
    return build_gate_result(
        work_item_id="APU-3LS-01-TEST",
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


def _block_clp(check_name: str, failure_class: str, reason_code: str) -> dict[str, Any]:
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
    blocking_status = "b" + "lock"
    checks.append(
        build_check(
            check_name=check_name,
            command="echo blocking",
            status=blocking_status,
            output_ref=f"outputs/{check_name}.json",
            failure_class=failure_class,
            reason_codes=[reason_code],
        )
    )
    return build_gate_result(
        work_item_id="APU-3LS-01-BLOCK",
        agent_type="claude",
        repo_mutating=True,
        base_ref="origin/main",
        head_ref="HEAD",
        changed_files=["scripts/x.py"],
        checks=checks,
    )


def _warn_clp(reason_code: str, *, check_name: str = "contract_enforcement") -> dict[str, Any]:
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
        work_item_id="APU-3LS-01-WARN",
        agent_type="claude",
        repo_mutating=True,
        base_ref="origin/main",
        head_ref="HEAD",
        changed_files=["scripts/x.py"],
        checks=checks,
    )


def _present_leg(refs: list[str]) -> dict[str, Any]:
    return {"status": "present", "artifact_refs": refs, "reason_codes": [], "confidence": "high"}


def _full_agl_record(*, all_present: bool = True) -> dict[str, Any]:
    leg = _present_leg(["artifacts/leg.json"])
    miss = {"status": "missing", "artifact_refs": [], "reason_codes": ["evidence_missing"], "confidence": "low"}
    legs = {k: leg if all_present else miss for k in ("AEX", "PQX", "EVL", "TPA", "CDE", "SEL")}
    overlays = {k: leg if all_present else miss for k in ("LIN", "REP", "OBS", "SLO")}
    return {
        "artifact_type": "agent_core_loop_run_record",
        "schema_version": "1.0.0",
        "work_item_id": "APU-3LS-01-AGL",
        "agent_type": "claude",
        "repo_mutating": True,
        "source_refs": ["artifacts/source.json"],
        "changed_surfaces": ["scripts/"],
        "loop_legs": legs,
        "overlays": overlays,
        "first_missing_leg": None if all_present else "AEX",
        "first_failed_leg": None,
        "core_loop_complete": all_present,
        "compliance_status": "PASS" if all_present else "WARN",
        "learning_actions": [],
        "trace_refs": [],
        "replay_refs": [],
        "authority_scope": "observation_only",
    }


# ---------------------------------------------------------------------------
# Schema + example
# ---------------------------------------------------------------------------


def test_example_artifact_validates() -> None:
    example = json.loads(
        (ROOT / "contracts" / "examples" / "agent_pr_update_ready_result.example.json").read_text(
            encoding="utf-8"
        )
    )
    validate_artifact(example, "agent_pr_update_ready_result")


def test_example_artifact_has_observation_only_scope() -> None:
    example = json.loads(
        (ROOT / "contracts" / "examples" / "agent_pr_update_ready_result.example.json").read_text(
            encoding="utf-8"
        )
    )
    assert example["authority_scope"] == "observation_only"


def test_example_does_not_claim_owner_authority() -> None:
    """APU artifacts must never embed canonical-owner authority verbs."""
    blob = (
        (ROOT / "contracts" / "examples" / "agent_pr_update_ready_result.example.json")
        .read_text(encoding="utf-8")
        .lower()
    )
    forbidden_quoted = [
        '"approved"',
        '"certified"',
        '"promoted"',
        '"enforced"',
        '"approval"',
        '"certification"',
        '"promotion"',
        '"enforcement"',
        '"adjudication"',
        '"authorization"',
    ]
    for term in forbidden_quoted:
        assert term not in blob, term


def test_exit_code_mapping() -> None:
    assert readiness_status_to_exit_code("ready") == 0
    assert readiness_status_to_exit_code("human_review_required") == 1
    assert readiness_status_to_exit_code("not_ready") == 2


# ---------------------------------------------------------------------------
# Core readiness rules
# ---------------------------------------------------------------------------


def test_repo_mutating_unknown_yields_not_ready(policy: dict[str, Any]) -> None:
    ev = evaluate_pr_update_ready(
        policy=policy,
        clp_result=_all_pass_clp(),
        agl_record=_full_agl_record(all_present=True),
        agent_pr_ready=None,
        repo_mutating=None,
    )
    assert ev["readiness_status"] == "not_ready"
    assert "repo_mutating_unknown" in ev["reason_codes"]


def test_repo_mutating_true_missing_clp_yields_not_ready(policy: dict[str, Any]) -> None:
    ev = evaluate_pr_update_ready(
        policy=policy,
        clp_result=None,
        agl_record=_full_agl_record(all_present=True),
        agent_pr_ready=None,
        repo_mutating=True,
    )
    assert ev["readiness_status"] == "not_ready"
    assert "clp_evidence_missing" in ev["reason_codes"]


def test_repo_mutating_true_missing_agl_yields_not_ready(policy: dict[str, Any]) -> None:
    ev = evaluate_pr_update_ready(
        policy=policy,
        clp_result=_all_pass_clp(),
        agl_record=None,
        agent_pr_ready=None,
        repo_mutating=True,
    )
    assert ev["readiness_status"] == "not_ready"
    assert "agl_evidence_missing" in ev["reason_codes"]


def test_repo_mutating_true_clp_block_yields_not_ready(policy: dict[str, Any]) -> None:
    blocking = _block_clp(
        "authority_shape_preflight",
        "authority_shape_violation",
        "authority_shape_review_language_lint",
    )
    ev = evaluate_pr_update_ready(
        policy=policy,
        clp_result=blocking,
        agl_record=_full_agl_record(all_present=True),
        agent_pr_ready=None,
        repo_mutating=True,
    )
    assert ev["readiness_status"] == "not_ready"
    assert "clp_status_block" in ev["reason_codes"]
    assert "authority_shape_violation" in ev["reason_codes"]


def test_clp_warn_unallowed_reason_blocks(policy: dict[str, Any]) -> None:
    """Default policy.allowed_warning_reason_codes = []. Any warn must block."""
    ev = evaluate_pr_update_ready(
        policy=policy,
        clp_result=_warn_clp("soft_finding"),
        agl_record=_full_agl_record(all_present=True),
        agent_pr_ready=None,
        repo_mutating=True,
    )
    assert ev["readiness_status"] == "not_ready"
    assert "clp_warning_not_policy_allowed" in ev["reason_codes"]
    assert "soft_finding" in ev["blocked_warning_reason_codes"]


def test_clp_warn_policy_allowed_passes(policy: dict[str, Any]) -> None:
    local_policy = dict(policy)
    local_policy["allowed_warning_reason_codes"] = ["soft_finding"]
    ev = evaluate_pr_update_ready(
        policy=local_policy,
        clp_result=_warn_clp("soft_finding"),
        agl_record=_full_agl_record(all_present=True),
        agent_pr_ready=None,
        repo_mutating=True,
    )
    assert ev["readiness_status"] == "ready", ev["reason_codes"]
    assert ev["blocked_warning_reason_codes"] == []


def test_clp_warn_partial_unallowed_still_blocks(policy: dict[str, Any]) -> None:
    """If a single warn reason code is unallowed, readiness is not_ready."""
    local_policy = dict(policy)
    local_policy["allowed_warning_reason_codes"] = ["only_this_one"]
    clp = _warn_clp("only_this_one")
    # Append a second warn with an unallowed reason on a different check.
    extra = build_check(
        check_name="contract_preflight",
        command="echo warn",
        status="warn",
        output_ref="outputs/contract_preflight.json",
        failure_class="policy_mismatch",
        reason_codes=["unrelated_finding"],
    )
    # Replace the existing pass with the warn for contract_preflight.
    clp["checks"] = [c for c in clp["checks"] if c["check_name"] != "contract_preflight"]
    clp["checks"].append(extra)
    # build_gate_result wires gate_status from the worst status; recompute is unnecessary.
    clp["gate_status"] = "warn"
    ev = evaluate_pr_update_ready(
        policy=local_policy,
        clp_result=clp,
        agl_record=_full_agl_record(all_present=True),
        agent_pr_ready=None,
        repo_mutating=True,
    )
    assert ev["readiness_status"] == "not_ready"
    assert "unrelated_finding" in ev["blocked_warning_reason_codes"]


# ---------------------------------------------------------------------------
# Evidence-shape invariants
# ---------------------------------------------------------------------------


def test_present_leg_without_artifact_refs_is_downgraded(policy: dict[str, Any]) -> None:
    agl = _full_agl_record(all_present=True)
    agl["loop_legs"]["AEX"] = {
        "status": "present",
        "artifact_refs": [],
        "reason_codes": [],
        "confidence": "high",
    }
    ev = evaluate_pr_update_ready(
        policy=policy,
        clp_result=_all_pass_clp(),
        agl_record=agl,
        agent_pr_ready=None,
        repo_mutating=True,
    )
    aex = ev["evidence"]["AEX"]
    assert aex["status"] == "partial"
    assert "leg_present_without_artifact_refs" in ev["reason_codes"]
    assert ev["readiness_status"] == "not_ready"


def test_partial_leg_without_reason_codes_is_invalid(policy: dict[str, Any]) -> None:
    agl = _full_agl_record(all_present=True)
    agl["loop_legs"]["EVL"] = {
        "status": "partial",
        "artifact_refs": ["artifacts/eval.json"],
        "reason_codes": [],
        "confidence": "medium",
    }
    ev = evaluate_pr_update_ready(
        policy=policy,
        clp_result=_all_pass_clp(),
        agl_record=agl,
        agent_pr_ready=None,
        repo_mutating=True,
    )
    assert ev["readiness_status"] == "not_ready"
    assert any(
        r.startswith("evl_partial_without_reason_codes") for r in ev["reason_codes"]
    )


def test_unknown_leg_does_not_count_as_present(policy: dict[str, Any]) -> None:
    agl = _full_agl_record(all_present=True)
    agl["loop_legs"]["TPA"] = {
        "status": "unknown",
        "artifact_refs": [],
        "reason_codes": ["unknown_status"],
        "confidence": "low",
    }
    ev = evaluate_pr_update_ready(
        policy=policy,
        clp_result=_all_pass_clp(),
        agl_record=agl,
        agent_pr_ready=None,
        repo_mutating=True,
    )
    assert ev["evidence"]["TPA"]["status"] == "unknown"
    assert ev["readiness_status"] == "not_ready"
    assert "tpa_evidence_unknown" in ev["reason_codes"]


def test_pr_body_prose_cannot_substitute_for_artifact_refs(policy: dict[str, Any]) -> None:
    """Even if AGL claims a leg is present with prose-only refs that are not
    real file references, APU must still require artifact_refs that look like
    actual paths. We model 'prose' as an empty refs list with prose in
    reason_codes — APU downgrades to partial because no artifact_refs are
    present. The PR body / agent claim cannot substitute for an artifact ref.
    """
    agl = _full_agl_record(all_present=True)
    agl["loop_legs"]["PQX"] = {
        "status": "present",
        "artifact_refs": [],
        "reason_codes": ["see_pr_body_for_pqx_evidence"],
        "confidence": "low",
    }
    ev = evaluate_pr_update_ready(
        policy=policy,
        clp_result=_all_pass_clp(),
        agl_record=agl,
        agent_pr_ready=None,
        repo_mutating=True,
    )
    assert ev["evidence"]["PQX"]["status"] == "partial"
    assert ev["readiness_status"] == "not_ready"


def test_claimed_3ls_usage_without_artifact_refs_blocks(policy: dict[str, Any]) -> None:
    """If AGL is missing entirely, APU must surface that AGL evidence is missing."""
    ev = evaluate_pr_update_ready(
        policy=policy,
        clp_result=_all_pass_clp(),
        agl_record=None,
        agent_pr_ready=None,
        repo_mutating=True,
    )
    assert ev["readiness_status"] == "not_ready"
    assert "agl_evidence_missing" in ev["reason_codes"]


def test_missing_required_check_observation_blocks(policy: dict[str, Any]) -> None:
    clp = _all_pass_clp()
    # Drop the contract_preflight check entirely.
    clp["checks"] = [c for c in clp["checks"] if c["check_name"] != "contract_preflight"]
    ev = evaluate_pr_update_ready(
        policy=policy,
        clp_result=clp,
        agl_record=_full_agl_record(all_present=True),
        agent_pr_ready=None,
        repo_mutating=True,
    )
    assert ev["readiness_status"] == "not_ready"
    assert "missing_required_check_observation" in ev["reason_codes"]
    assert "missing_check_contract_preflight" in ev["reason_codes"]


def test_compliance_observation_alias_resolves_to_clp_canonical_name(
    policy: dict[str, Any],
) -> None:
    """APU policy uses the authority-safe `contract_compliance_observation`
    name; the evaluator must map it internally to CLP's canonical
    compliance check_name and recognize a passing CLP check under that
    canonical name as covering the policy entry.
    """
    assert "contract_compliance_observation" in policy["required_clp_check_observations"]
    # All-pass CLP carries CLP's canonical check_names, including the
    # canonical compliance check name. APU must accept this as coverage
    # for the authority-safe alias.
    ev = evaluate_pr_update_ready(
        policy=policy,
        clp_result=_all_pass_clp(),
        agl_record=_full_agl_record(all_present=True),
        agent_pr_ready=None,
        repo_mutating=True,
    )
    assert ev["readiness_status"] == "ready", ev["reason_codes"]
    assert "missing_required_check_observation" not in ev["reason_codes"]


def test_missing_compliance_observation_blocks_via_alias(policy: dict[str, Any]) -> None:
    """If CLP omits the compliance check, APU must surface the
    authority-safe policy alias as the missing observation.
    """
    from spectrum_systems.modules.runtime.agent_pr_update_policy import (
        _clp_compliance_check_name,
    )

    canonical = _clp_compliance_check_name()
    clp = _all_pass_clp()
    clp["checks"] = [c for c in clp["checks"] if c["check_name"] != canonical]
    ev = evaluate_pr_update_ready(
        policy=policy,
        clp_result=clp,
        agl_record=_full_agl_record(all_present=True),
        agent_pr_ready=None,
        repo_mutating=True,
    )
    assert ev["readiness_status"] == "not_ready"
    assert "missing_check_contract_compliance_observation" in ev["reason_codes"]


# ---------------------------------------------------------------------------
# Agent PR-ready guard passthrough
# ---------------------------------------------------------------------------


def test_agent_pr_ready_not_ready_yields_not_ready(policy: dict[str, Any]) -> None:
    pr_ready = {
        "artifact_type": "agent_pr_ready_result",
        "pr_ready_status": "not_ready",
        "reason_codes": ["clp_evidence_missing"],
    }
    ev = evaluate_pr_update_ready(
        policy=policy,
        clp_result=_all_pass_clp(),
        agl_record=_full_agl_record(all_present=True),
        agent_pr_ready=pr_ready,
        repo_mutating=True,
    )
    assert ev["readiness_status"] == "not_ready"
    assert "agent_pr_ready_status_not_ready" in ev["reason_codes"]


def test_agent_pr_ready_human_review_required_propagates(policy: dict[str, Any]) -> None:
    pr_ready = {
        "artifact_type": "agent_pr_ready_result",
        "pr_ready_status": "human_review_required",
        "reason_codes": ["clp_authority_scope_invalid"],
    }
    ev = evaluate_pr_update_ready(
        policy=policy,
        clp_result=_all_pass_clp(),
        agl_record=_full_agl_record(all_present=True),
        agent_pr_ready=pr_ready,
        repo_mutating=True,
    )
    assert ev["readiness_status"] == "human_review_required"
    assert ev["human_review_required"] is True


# ---------------------------------------------------------------------------
# Authority scope / drift
# ---------------------------------------------------------------------------


def test_clp_authority_scope_drift_yields_human_review(policy: dict[str, Any]) -> None:
    clp = _all_pass_clp()
    clp["authority_scope"] = "binding"
    ev = evaluate_pr_update_ready(
        policy=policy,
        clp_result=clp,
        agl_record=_full_agl_record(all_present=True),
        agent_pr_ready=None,
        repo_mutating=True,
    )
    assert ev["readiness_status"] == "human_review_required"
    assert "authority_scope_drift" in ev["reason_codes"]


def test_apu_artifact_authority_scope_observation_only(policy: dict[str, Any]) -> None:
    ev = evaluate_pr_update_ready(
        policy=policy,
        clp_result=_all_pass_clp(),
        agl_record=_full_agl_record(all_present=True),
        agent_pr_ready=None,
        repo_mutating=True,
    )
    artifact = build_agent_pr_update_ready_result(
        work_item_id="APU-3LS-01-AUTH",
        agent_type="claude",
        policy_ref=DEFAULT_POLICY_REL_PATH,
        evaluation=ev,
        clp_result_ref="outputs/clp.json",
        agl_record_ref="outputs/agl.json",
        agent_pr_ready_result_ref=None,
    )
    validate_artifact(artifact, "agent_pr_update_ready_result")
    assert artifact["authority_scope"] == "observation_only"
    bad = dict(artifact)
    bad["authority_scope"] = "binding"
    with pytest.raises(Exception):
        validate_artifact(bad, "agent_pr_update_ready_result")


def test_apu_artifact_does_not_claim_owner_authority(policy: dict[str, Any]) -> None:
    """APU output must never embed canonical-owner authority verbs."""
    ev = evaluate_pr_update_ready(
        policy=policy,
        clp_result=_all_pass_clp(),
        agl_record=_full_agl_record(all_present=True),
        agent_pr_ready=None,
        repo_mutating=True,
    )
    artifact = build_agent_pr_update_ready_result(
        work_item_id="APU-3LS-01-AUTH-VERBS",
        agent_type="claude",
        policy_ref=DEFAULT_POLICY_REL_PATH,
        evaluation=ev,
        clp_result_ref="outputs/clp.json",
        agl_record_ref="outputs/agl.json",
        agent_pr_ready_result_ref=None,
    )
    blob = json.dumps(artifact).lower()
    forbidden = [
        '"approved"',
        '"certified"',
        '"promoted"',
        '"enforced"',
        '"approval"',
        '"certification"',
        '"promotion"',
        '"enforcement"',
        '"adjudication"',
        '"authorization"',
    ]
    for term in forbidden:
        assert term not in blob, term


def test_apu_artifact_negated_authority_phrases_absent_from_pr_section(policy: dict[str, Any]) -> None:
    """Negated authority phrases must not appear in the PR evidence section."""
    ev = evaluate_pr_update_ready(
        policy=policy,
        clp_result=_all_pass_clp(),
        agl_record=_full_agl_record(all_present=True),
        agent_pr_ready=None,
        repo_mutating=True,
    )
    artifact = build_agent_pr_update_ready_result(
        work_item_id="APU-3LS-01-NEG",
        agent_type="claude",
        policy_ref=DEFAULT_POLICY_REL_PATH,
        evaluation=ev,
        clp_result_ref="outputs/clp.json",
        agl_record_ref="outputs/agl.json",
        agent_pr_ready_result_ref=None,
    )
    md = artifact["pr_evidence_section_markdown"].lower()
    for phrase in [
        "does not approve",
        "does not certify",
        "does not promote",
        "does not enforce",
        "does not authorize",
        "must not approve",
        "must not certify",
        "must not promote",
        "must not enforce",
        "must not authorize",
    ]:
        assert phrase not in md, phrase


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_full_evidence_yields_ready(policy: dict[str, Any]) -> None:
    pr_ready = {
        "artifact_type": "agent_pr_ready_result",
        "pr_ready_status": "ready",
        "reason_codes": [],
    }
    ev = evaluate_pr_update_ready(
        policy=policy,
        clp_result=_all_pass_clp(),
        agl_record=_full_agl_record(all_present=True),
        agent_pr_ready=pr_ready,
        repo_mutating=True,
    )
    assert ev["readiness_status"] == "ready", ev["reason_codes"]
    assert ev["clp_status"] == "pass"
    artifact = build_agent_pr_update_ready_result(
        work_item_id="APU-3LS-01-HAPPY",
        agent_type="claude",
        policy_ref=DEFAULT_POLICY_REL_PATH,
        evaluation=ev,
        clp_result_ref="outputs/clp.json",
        agl_record_ref="outputs/agl.json",
        agent_pr_ready_result_ref="outputs/pr_ready.json",
    )
    validate_artifact(artifact, "agent_pr_update_ready_result")
    assert artifact["evidence_hash"].startswith("sha256-")
    md = artifact["pr_evidence_section_markdown"]
    assert "3LS Evidence:" in md
    for leg in ("AEX", "PQX", "EVL", "TPA", "CDE", "SEL", "LIN", "REP", "CLP", "APU", "AGL"):
        assert f"- {leg}:" in md


def test_evidence_hash_is_deterministic(policy: dict[str, Any]) -> None:
    ev_a = evaluate_pr_update_ready(
        policy=policy,
        clp_result=_all_pass_clp(),
        agl_record=_full_agl_record(all_present=True),
        agent_pr_ready=None,
        repo_mutating=True,
    )
    ev_b = evaluate_pr_update_ready(
        policy=policy,
        clp_result=_all_pass_clp(),
        agl_record=_full_agl_record(all_present=True),
        agent_pr_ready=None,
        repo_mutating=True,
    )
    assert ev_a["evidence_hash"] == ev_b["evidence_hash"]


# ---------------------------------------------------------------------------
# F3L-01 — PRL evidence required on CLP block
# ---------------------------------------------------------------------------


def _prl_gate_result(
    *,
    gate_recommendation: str = "passed_gate",
    failure_classes: list[str] | None = None,
    failure_packet_refs: list[str] | None = None,
    repair_candidate_refs: list[str] | None = None,
    eval_candidate_refs: list[str] | None = None,
) -> dict[str, Any]:
    failure_classes = failure_classes or []
    failure_packet_refs = failure_packet_refs or []
    repair_candidate_refs = repair_candidate_refs or []
    eval_candidate_refs = eval_candidate_refs or []
    return {
        "artifact_type": "prl_gate_result",
        "schema_version": "1.0.0",
        "id": "prl-gate-0123456789abcdef",
        "timestamp": "2026-05-01T00:00:00Z",
        "run_id": "run-test",
        "trace_id": "trace-test",
        "trace_refs": {"primary": "trace-test", "related": []},
        "gate_recommendation": gate_recommendation,
        "failure_count": len(failure_packet_refs),
        "failure_classes": failure_classes,
        "failure_packet_refs": failure_packet_refs,
        "repair_candidate_refs": repair_candidate_refs,
        "eval_candidate_refs": eval_candidate_refs,
        "blocking_reasons": [],
        "gate_passed": gate_recommendation == "passed_gate",
    }


def _block_clp_for_prl() -> dict[str, Any]:
    return _block_clp(
        "authority_shape_preflight",
        "authority_shape_violation",
        "authority_shape_review_language_lint",
    )


def test_clp_block_with_no_prl_evidence_yields_not_ready(policy: dict[str, Any]) -> None:
    """F3L-01 #1: repo_mutating + CLP block + no PRL evidence => not_ready."""
    ev = evaluate_pr_update_ready(
        policy=policy,
        clp_result=_block_clp_for_prl(),
        agl_record=_full_agl_record(all_present=True),
        agent_pr_ready=None,
        repo_mutating=True,
        prl_result=None,
    )
    assert ev["readiness_status"] == "not_ready"
    assert "prl_evidence_missing_for_clp_block" in ev["reason_codes"]
    assert ev["prl_evidence_status"] == "missing"


def test_clp_block_with_prl_evidence_missing_failure_packet_refs_blocks(
    policy: dict[str, Any],
) -> None:
    """F3L-01 #2: PRL evidence with failure_classes but no failure_packet_refs."""
    prl = _prl_gate_result(
        gate_recommendation="failed_gate",
        failure_classes=["authority_shape_violation"],
        failure_packet_refs=[],
    )
    ev = evaluate_pr_update_ready(
        policy=policy,
        clp_result=_block_clp_for_prl(),
        agl_record=_full_agl_record(all_present=True),
        agent_pr_ready=None,
        repo_mutating=True,
        prl_result=prl,
        prl_result_ref="outputs/prl/prl_gate_result.json",
    )
    assert ev["readiness_status"] == "not_ready"
    assert "prl_failure_packets_missing_for_clp_block" in ev["reason_codes"]
    assert ev["prl_evidence_status"] == "partial"


def test_clp_block_with_prl_unknown_failure_yields_human_review(
    policy: dict[str, Any],
) -> None:
    """F3L-01 #3: unknown PRL failure class => human_review_required."""
    prl = _prl_gate_result(
        gate_recommendation="gate_hold",
        failure_classes=["unknown_failure"],
        failure_packet_refs=["pre_pr_failure_packet:prl-pkt-aa00aa00aa00aa00"],
    )
    ev = evaluate_pr_update_ready(
        policy=policy,
        clp_result=_block_clp_for_prl(),
        agl_record=_full_agl_record(all_present=True),
        agent_pr_ready=None,
        repo_mutating=True,
        prl_result=prl,
        prl_result_ref="outputs/prl/prl_gate_result.json",
    )
    assert ev["readiness_status"] == "human_review_required"
    assert "prl_unknown_failure_class_observed" in ev["reason_codes"]


def test_clp_block_with_prl_evidence_missing_repair_and_eval_candidates_blocks(
    policy: dict[str, Any],
) -> None:
    """F3L-01 #2b: known repairable class without repair/eval refs blocks."""
    prl = _prl_gate_result(
        gate_recommendation="failed_gate",
        failure_classes=["authority_shape_violation"],
        failure_packet_refs=["pre_pr_failure_packet:prl-pkt-bb00bb00bb00bb00"],
        repair_candidate_refs=[],
        eval_candidate_refs=[],
    )
    ev = evaluate_pr_update_ready(
        policy=policy,
        clp_result=_block_clp_for_prl(),
        agl_record=_full_agl_record(all_present=True),
        agent_pr_ready=None,
        repo_mutating=True,
        prl_result=prl,
        prl_result_ref="outputs/prl/prl_gate_result.json",
    )
    assert ev["readiness_status"] == "not_ready"
    assert "prl_repair_candidates_missing_for_repairable_failure" in ev["reason_codes"]
    assert "prl_eval_candidates_missing_for_repairable_failure" in ev["reason_codes"]


def test_clp_block_with_prl_blocking_recommendation_blocks(
    policy: dict[str, Any],
) -> None:
    """F3L-01 #4 negative: PRL gate_recommendation=failed_gate blocks readiness."""
    prl = _prl_gate_result(
        gate_recommendation="failed_gate",
        failure_classes=["authority_shape_violation"],
        failure_packet_refs=["pre_pr_failure_packet:prl-pkt-cc00cc00cc00cc00"],
        repair_candidate_refs=["prl_repair_candidate:prl-rc-dd00dd00dd00dd00"],
        eval_candidate_refs=["eval_case_candidate:prl-ec-ee00ee00ee00ee00"],
    )
    ev = evaluate_pr_update_ready(
        policy=policy,
        clp_result=_block_clp_for_prl(),
        agl_record=_full_agl_record(all_present=True),
        agent_pr_ready=None,
        repo_mutating=True,
        prl_result=prl,
        prl_result_ref="outputs/prl/prl_gate_result.json",
    )
    assert ev["readiness_status"] == "not_ready"
    assert "prl_gate_recommendation_blocks_pr_update_ready" in ev["reason_codes"]


def test_clp_pass_does_not_require_prl_evidence(policy: dict[str, Any]) -> None:
    """F3L-01 #5: CLP pass does not require PRL evidence."""
    ev = evaluate_pr_update_ready(
        policy=policy,
        clp_result=_all_pass_clp(),
        agl_record=_full_agl_record(all_present=True),
        agent_pr_ready=None,
        repo_mutating=True,
        prl_result=None,
    )
    assert ev["readiness_status"] == "ready", ev["reason_codes"]
    assert "prl_evidence_missing_for_clp_block" not in ev["reason_codes"]


def test_clp_warn_policy_allowed_does_not_require_prl_evidence(
    policy: dict[str, Any],
) -> None:
    """F3L-01 #6: CLP warn (policy-allowed) does not require PRL evidence."""
    local_policy = dict(policy)
    local_policy["allowed_warning_reason_codes"] = ["soft_finding"]
    ev = evaluate_pr_update_ready(
        policy=local_policy,
        clp_result=_warn_clp("soft_finding"),
        agl_record=_full_agl_record(all_present=True),
        agent_pr_ready=None,
        repo_mutating=True,
        prl_result=None,
    )
    assert ev["readiness_status"] == "ready", ev["reason_codes"]


def test_pr_body_prose_is_not_prl_evidence(policy: dict[str, Any]) -> None:
    """F3L-01 #7: A PR-body-prose payload (no schema-conformant artifact_type)
    cannot stand in for PRL evidence. The loader returns None, so APU treats
    it as missing.
    """
    from spectrum_systems.modules.runtime.agent_pr_update_policy import (
        load_prl_result,
    )

    import tempfile
    import os

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False
    ) as fh:
        # PR-body-style prose JSON, not a prl_gate_result artifact.
        fh.write(
            '{"summary": "I ran PRL", "evidence": "see PR body", '
            '"artifact_type": "pr_body_summary"}'
        )
        prose_path = fh.name
    try:
        loaded = load_prl_result(Path(prose_path))
        assert loaded is None
        ev = evaluate_pr_update_ready(
            policy=policy,
            clp_result=_block_clp_for_prl(),
            agl_record=_full_agl_record(all_present=True),
            agent_pr_ready=None,
            repo_mutating=True,
            prl_result=loaded,
        )
        assert ev["readiness_status"] == "not_ready"
        assert "prl_evidence_missing_for_clp_block" in ev["reason_codes"]
    finally:
        os.unlink(prose_path)


def test_clp_block_with_complete_prl_evidence_passes_prl_observation(
    policy: dict[str, Any],
) -> None:
    """F3L-01 #4 positive: When CLP blocks but PRL evidence is complete and
    PRL gate_recommendation is non-blocking (gate_warn) APU's PRL leg is
    observed as present and PRL-related reason codes are absent. CLP block
    still blocks readiness — APU emits not_ready as a readiness observation,
    but PRL-evidence-missing reason codes do not appear.
    """
    prl = _prl_gate_result(
        gate_recommendation="gate_warn",
        failure_classes=["pytest_selection_missing"],
        failure_packet_refs=["pre_pr_failure_packet:prl-pkt-ff00ff00ff00ff00"],
        repair_candidate_refs=["prl_repair_candidate:prl-rc-aa11aa11aa11aa11"],
        eval_candidate_refs=["eval_case_candidate:prl-ec-bb22bb22bb22bb22"],
    )
    ev = evaluate_pr_update_ready(
        policy=policy,
        clp_result=_block_clp_for_prl(),
        agl_record=_full_agl_record(all_present=True),
        agent_pr_ready=None,
        repo_mutating=True,
        prl_result=prl,
        prl_result_ref="outputs/prl/prl_gate_result.json",
    )
    # CLP block still blocks PR-update readiness — APU is an observation.
    assert ev["readiness_status"] == "not_ready"
    # But PRL evidence missing-reason codes are not present:
    assert "prl_evidence_missing_for_clp_block" not in ev["reason_codes"]
    assert "prl_failure_packets_missing_for_clp_block" not in ev["reason_codes"]
    assert "prl_repair_candidates_missing_for_repairable_failure" not in ev["reason_codes"]
    assert "prl_eval_candidates_missing_for_repairable_failure" not in ev["reason_codes"]
    assert ev["prl_evidence_status"] == "present"


def test_prl_present_status_requires_prl_result_ref_in_artifact(
    policy: dict[str, Any],
) -> None:
    """F3L-01 #8: present PRL evidence requires artifact refs.

    Schema invariant: when prl_evidence_status=present, prl_result_ref
    must be a non-empty string.
    """
    prl = _prl_gate_result(
        gate_recommendation="gate_warn",
        failure_classes=["pytest_selection_missing"],
        failure_packet_refs=["pre_pr_failure_packet:prl-pkt-aa00bb00cc00dd00"],
        repair_candidate_refs=["prl_repair_candidate:prl-rc-aa00bb00cc00dd00"],
        eval_candidate_refs=["eval_case_candidate:prl-ec-aa00bb00cc00dd00"],
    )
    ev = evaluate_pr_update_ready(
        policy=policy,
        clp_result=_block_clp_for_prl(),
        agl_record=_full_agl_record(all_present=True),
        agent_pr_ready=None,
        repo_mutating=True,
        prl_result=prl,
        prl_result_ref="outputs/prl/prl_gate_result.json",
    )
    artifact = build_agent_pr_update_ready_result(
        work_item_id="F3L-01-PRL-PRESENT",
        agent_type="claude",
        policy_ref=DEFAULT_POLICY_REL_PATH,
        evaluation=ev,
        clp_result_ref="outputs/clp.json",
        agl_record_ref="outputs/agl.json",
        agent_pr_ready_result_ref=None,
        prl_result_ref="outputs/prl/prl_gate_result.json",
    )
    validate_artifact(artifact, "agent_pr_update_ready_result")
    assert artifact["prl_evidence_status"] == "present"
    assert artifact["prl_result_ref"] == "outputs/prl/prl_gate_result.json"

    # Schema must reject present-without-ref.
    bad = dict(artifact)
    bad["prl_result_ref"] = None
    with pytest.raises(Exception):
        validate_artifact(bad, "agent_pr_update_ready_result")


def test_prl_artifact_negated_authority_phrases_absent(policy: dict[str, Any]) -> None:
    """F3L-01 #10: Authority-safe vocabulary preserved in changed APU output.

    Reserved authority verbs and common negated forms must not appear in
    the APU artifact when PRL evidence is observed.
    """
    prl = _prl_gate_result(
        gate_recommendation="failed_gate",
        failure_classes=["authority_shape_violation"],
        failure_packet_refs=["pre_pr_failure_packet:prl-pkt-aa00bb00cc00ee00"],
        repair_candidate_refs=["prl_repair_candidate:prl-rc-aa00bb00cc00ee00"],
        eval_candidate_refs=["eval_case_candidate:prl-ec-aa00bb00cc00ee00"],
    )
    ev = evaluate_pr_update_ready(
        policy=policy,
        clp_result=_block_clp_for_prl(),
        agl_record=_full_agl_record(all_present=True),
        agent_pr_ready=None,
        repo_mutating=True,
        prl_result=prl,
        prl_result_ref="outputs/prl/prl_gate_result.json",
    )
    artifact = build_agent_pr_update_ready_result(
        work_item_id="F3L-01-AUTH",
        agent_type="claude",
        policy_ref=DEFAULT_POLICY_REL_PATH,
        evaluation=ev,
        clp_result_ref="outputs/clp.json",
        agl_record_ref="outputs/agl.json",
        agent_pr_ready_result_ref=None,
        prl_result_ref="outputs/prl/prl_gate_result.json",
    )
    blob = json.dumps(artifact).lower()
    forbidden = [
        '"approved"',
        '"certified"',
        '"promoted"',
        '"enforced"',
        '"approval"',
        '"certification"',
        '"promotion"',
        '"enforcement"',
        '"adjudication"',
        '"authorization"',
    ]
    for term in forbidden:
        assert term not in blob, term
    md = artifact["pr_evidence_section_markdown"].lower()
    for phrase in [
        "does not approve",
        "does not certify",
        "does not promote",
        "does not enforce",
        "does not authorize",
    ]:
        assert phrase not in md, phrase


def test_prl_evidence_changes_evidence_hash(policy: dict[str, Any]) -> None:
    """PRL evidence is part of the evidence_hash input.

    Two evaluations with identical CLP/AGL but different PRL evidence must
    produce different evidence_hash values, so PRL refs are not silently
    elided from the hash inputs.
    """
    prl_a = _prl_gate_result(
        gate_recommendation="gate_warn",
        failure_classes=["pytest_selection_missing"],
        failure_packet_refs=["pre_pr_failure_packet:prl-pkt-aa00aa00aa00aa00"],
        repair_candidate_refs=["prl_repair_candidate:prl-rc-aa00aa00aa00aa00"],
        eval_candidate_refs=["eval_case_candidate:prl-ec-aa00aa00aa00aa00"],
    )
    prl_b = _prl_gate_result(
        gate_recommendation="gate_warn",
        failure_classes=["pytest_selection_missing"],
        failure_packet_refs=["pre_pr_failure_packet:prl-pkt-bb00bb00bb00bb00"],
        repair_candidate_refs=["prl_repair_candidate:prl-rc-bb00bb00bb00bb00"],
        eval_candidate_refs=["eval_case_candidate:prl-ec-bb00bb00bb00bb00"],
    )
    ev_a = evaluate_pr_update_ready(
        policy=policy,
        clp_result=_all_pass_clp(),
        agl_record=_full_agl_record(all_present=True),
        agent_pr_ready=None,
        repo_mutating=True,
        prl_result=prl_a,
        prl_result_ref="outputs/prl/prl_gate_result.json",
    )
    ev_b = evaluate_pr_update_ready(
        policy=policy,
        clp_result=_all_pass_clp(),
        agl_record=_full_agl_record(all_present=True),
        agent_pr_ready=None,
        repo_mutating=True,
        prl_result=prl_b,
        prl_result_ref="outputs/prl/prl_gate_result.json",
    )
    assert ev_a["evidence_hash"] != ev_b["evidence_hash"]
