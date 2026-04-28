"""Tests for RFX-12 policy compilation."""

from __future__ import annotations

import pytest

from spectrum_systems.modules.runtime.rfx_policy_compilation import (
    RFXPolicyCompilationError,
    build_rfx_policy_candidate_handoff,
)


def _kwargs(**override: object) -> dict[str, object]:
    base: dict[str, object] = dict(
        source_judgment_refs=["rfx-judgment-candidate-1"],
        candidate_text="Require replay-burst recovery before promotion.",
        candidate_structure=None,
        eval_requirements=["eval:replay_burst"],
        rollout_requirements=["rollout:canary_first"],
        canary_requirements=["canary:5_percent"],
        pol_handoff_target="pol:registry/v1",
        activation_state="candidate",
    )
    base.update(override)
    return base


def test_judgment_candidate_becomes_policy_candidate() -> None:
    h = build_rfx_policy_candidate_handoff(**_kwargs())  # type: ignore[arg-type]
    assert h["artifact_type"] == "rfx_policy_candidate_handoff"
    assert h["activation_state"] == "candidate"
    assert "POL retains its canonical" in h["ownership_note"]


def test_missing_eval_requirement_blocks() -> None:
    with pytest.raises(RFXPolicyCompilationError, match="rfx_policy_eval_requirement_missing"):
        build_rfx_policy_candidate_handoff(**_kwargs(eval_requirements=[]))  # type: ignore[arg-type]


def test_missing_rollout_and_canary_blocks() -> None:
    with pytest.raises(RFXPolicyCompilationError, match="rfx_policy_rollout_requirement_missing"):
        build_rfx_policy_candidate_handoff(**_kwargs(rollout_requirements=[], canary_requirements=[]))  # type: ignore[arg-type]


def test_policy_not_activated_directly() -> None:
    with pytest.raises(RFXPolicyCompilationError, match="rfx_policy_candidate_invalid"):
        build_rfx_policy_candidate_handoff(**_kwargs(activation_state="active"))  # type: ignore[arg-type]


def test_missing_judgment_refs_blocks() -> None:
    with pytest.raises(RFXPolicyCompilationError, match="rfx_policy_source_missing"):
        build_rfx_policy_candidate_handoff(**_kwargs(source_judgment_refs=None))  # type: ignore[arg-type]


def test_missing_pol_handoff_blocks() -> None:
    with pytest.raises(RFXPolicyCompilationError, match="rfx_pol_handoff_missing"):
        build_rfx_policy_candidate_handoff(**_kwargs(pol_handoff_target=None))  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# RT-20 red-team: compile directly into active policy
# ---------------------------------------------------------------------------


def test_rt20_red_team_active_policy_blocks_then_revalidates() -> None:
    with pytest.raises(RFXPolicyCompilationError, match="rfx_policy_candidate_invalid"):
        build_rfx_policy_candidate_handoff(**_kwargs(activation_state="active"))  # type: ignore[arg-type]
    h = build_rfx_policy_candidate_handoff(**_kwargs())  # type: ignore[arg-type]
    assert h["activation_state"] == "candidate"
