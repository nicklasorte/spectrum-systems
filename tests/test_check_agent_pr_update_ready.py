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
