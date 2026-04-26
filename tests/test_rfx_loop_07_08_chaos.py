"""LOOP-07 / LOOP-08 chaos / red-team tests (Part 8).

Each scenario injects a specific reliability failure mode into the RFX
flow integration entry point and asserts the guard short-circuits with a
deterministic reason code:

  * remove telemetry            → must block
  * inject replay drift         → must freeze
  * fake SLO ``ok`` w/ partial OBS → must block
  * inject repeated failures    → must freeze
  * inject inconsistent metrics → must block
  * remove trace linkage        → must block
"""

from __future__ import annotations

import pytest

from spectrum_systems.modules.runtime.rfx_adversarial_reliability_guard import (
    RFXAdversarialReliabilityError,
)
from spectrum_systems.modules.runtime.rfx_certification_gate import (
    RFXCertificationGateError,
)
from spectrum_systems.modules.runtime.rfx_flow_integration import (
    assert_rfx_promotion_ready,
)
from spectrum_systems.modules.runtime.rfx_observability_replay_consistency import (
    RFXObservabilityReplayConsistencyError,
)
from spectrum_systems.modules.runtime.rfx_reliability_freeze import (
    RFXReliabilityFreezeError,
)
from spectrum_systems.modules.runtime.rfx_route_guard import (
    build_rfx_tlc_route_artifact,
)
from spectrum_systems.modules.runtime.rfx_telemetry_slo_gate import (
    RFXTelemetrySLOError,
)


# ---------------------------------------------------------------------------
# Healthy-baseline fixtures (LOOP-07/08 enabled via telemetry inputs)
# ---------------------------------------------------------------------------

_FULL_RFX_PATH = ["AEX", "RIL", "FRE", "PQX", "EVL", "TPA", "CDE", "SEL", "GOV"]

_ADMISSION = {
    "admission_id": "aex-rfx-chaos-001",
    "admission_status": "accepted",
    "execution_type": "repo_write",
}
_HANDOFF = {
    "handoff_id": "tlc-handoff-chaos-001",
    "handoff_status": "accepted",
    "target_subsystems": ["TPA", "PQX"],
}
_EVL = {"eval_id": "evl-chaos-001", "evaluation_status": "pass"}
_TPA = {"tpa_decision_id": "tpa-chaos-001", "discipline_status": "accepted"}
_CDE = {"decision_id": "cde-chaos-001", "status": "ready"}
_SEL = {"sel_record_id": "sel-chaos-001", "cde_decision_ref": "cde-chaos-001"}
_LIN = {"lineage_id": "lin-chaos-001", "authenticity": "pass"}
_REP = {"replay_id": "rep-chaos-001", "match": True}

# OBS rich enough to satisfy LOOP-08 strict invariants.
_OBS_FULL = {
    "obs_id": "obs-chaos-001",
    "trace_id": "trace-chaos-001",
    "execution_path_coverage": ["AEX", "PQX", "EVL", "TPA", "CDE", "SEL"],
    "artifact_linkage": ["lin:001", "rep:001"],
    "failure_logs": [],
    "completeness": "pass",
}
_SLO_OK = {
    "slo_id": "slo-chaos-001",
    "status": "within_budget",
    "obs_ref": "obs-chaos-001",
}
_PRA = {"pra_id": "pra-chaos-001", "status": "ready"}
_POL = {"pol_id": "pol-chaos-001", "status": "active", "in_scope": True}

# Replay corpus matched to OBS trace coverage.
_REPLAY_RESULTS_OK = [{"trace_id": "trace-chaos-001", "match": True}]


@pytest.fixture
def route_artifact() -> dict:
    return build_rfx_tlc_route_artifact(
        run_id="rfx-chaos-001",
        trace_id="trace-chaos-001",
        aex_admission_id=_ADMISSION["admission_id"],
        intended_path=_FULL_RFX_PATH,
        created_at="2026-04-25T00:00:00Z",
    )


def _kwargs(route_artifact: dict, **overrides):
    base = dict(
        route_artifact=route_artifact,
        build_admission_record=_ADMISSION,
        tlc_handoff_record=_HANDOFF,
        evl=_EVL, tpa=_TPA,
        cde=_CDE, sel=_SEL,
        lin=_LIN, rep=_REP,
        obs=_OBS_FULL, slo=_SLO_OK,
        pra=_PRA, pol=_POL,
        recent_failures=[],
        replay_results=_REPLAY_RESULTS_OK,
        window_seconds=60,
    )
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Healthy baseline must pass
# ---------------------------------------------------------------------------


def test_full_healthy_flow_with_loop07_08_passes(route_artifact: dict) -> None:
    # Must not raise — clean telemetry, no failures, derived SLO.
    assert_rfx_promotion_ready(**_kwargs(route_artifact))


# ---------------------------------------------------------------------------
# Chaos: remove telemetry → must block
# ---------------------------------------------------------------------------


def test_chaos_removes_obs_blocks_loop06_or_loop08(route_artifact: dict) -> None:
    """OBS removed entirely. LOOP-06 fires first with rfx_missing_obs."""
    with pytest.raises(RFXCertificationGateError, match="rfx_missing_obs"):
        assert_rfx_promotion_ready(**_kwargs(route_artifact, obs=None))


def test_chaos_partial_obs_blocks_loop08(route_artifact: dict) -> None:
    """OBS lacks LOOP-08 invariants but passes LOOP-06. LOOP-08 must catch."""
    obs_partial = {
        "obs_id": "obs-chaos-001",
        "completeness": "pass",
        # missing trace_id / execution_path_coverage / artifact_linkage / failure_logs
    }
    with pytest.raises(RFXTelemetrySLOError, match="rfx_obs_incomplete"):
        assert_rfx_promotion_ready(**_kwargs(route_artifact, obs=obs_partial))


# ---------------------------------------------------------------------------
# Chaos: inject replay drift → must freeze
# ---------------------------------------------------------------------------


def test_chaos_replay_drift_freezes(route_artifact: dict) -> None:
    drift_replays = [
        {"trace_id": "trace-chaos-001", "match": False},
        {"trace_id": "trace-chaos-001", "match": False},
        {"trace_id": "trace-chaos-001", "match": True},
    ]
    # LOOP-07 catches drift before adversarial / consistency guards.
    with pytest.raises(RFXReliabilityFreezeError, match="rfx_replay_drift_detected"):
        assert_rfx_promotion_ready(**_kwargs(route_artifact, replay_results=drift_replays))


# ---------------------------------------------------------------------------
# Chaos: fake SLO "ok" while OBS is missing fields → must block
# ---------------------------------------------------------------------------


def test_chaos_fake_slo_ok_with_missing_obs_segments_blocks(route_artifact: dict) -> None:
    obs_missing_trace = {**_OBS_FULL}
    obs_missing_trace.pop("execution_path_coverage")
    with pytest.raises(RFXTelemetrySLOError) as exc:
        assert_rfx_promotion_ready(**_kwargs(route_artifact, obs=obs_missing_trace))
    assert "rfx_slo_inconsistent_with_obs" in str(exc.value) or "rfx_obs_incomplete" in str(exc.value)


def test_chaos_independent_slo_without_obs_ref_blocks(route_artifact: dict) -> None:
    independent = {"slo_id": "slo-x", "status": "within_budget"}
    with pytest.raises(RFXTelemetrySLOError, match="rfx_slo_inconsistent_with_obs"):
        assert_rfx_promotion_ready(**_kwargs(route_artifact, slo=independent))


# ---------------------------------------------------------------------------
# Chaos: inject repeated failures → must freeze
# ---------------------------------------------------------------------------


def test_chaos_recurring_failures_freeze(route_artifact: dict) -> None:
    failures = [
        {"timestamp_seconds": 5.0, "reason_code": "schema_drift"},
        {"timestamp_seconds": 25.0, "reason_code": "schema_drift"},
        {"timestamp_seconds": 45.0, "reason_code": "schema_drift"},
    ]
    # OBS reflects same failures so anti-gaming guard cannot fire first.
    obs = {**_OBS_FULL, "failure_logs": failures}
    with pytest.raises(RFXReliabilityFreezeError, match="rfx_recurring_failure_pattern_detected"):
        assert_rfx_promotion_ready(
            **_kwargs(route_artifact, recent_failures=failures, obs=obs, window_seconds=120)
        )


def test_chaos_burst_failures_freeze(route_artifact: dict) -> None:
    failures = [
        {"timestamp_seconds": 80.0 + i, "reason_code": f"fail_{i}"}
        for i in range(5)
    ]
    obs = {**_OBS_FULL, "failure_logs": failures}
    with pytest.raises(RFXReliabilityFreezeError, match="rfx_burst_failure_detected"):
        assert_rfx_promotion_ready(
            **_kwargs(route_artifact, recent_failures=failures, obs=obs, window_seconds=100)
        )


# ---------------------------------------------------------------------------
# Chaos: inject inconsistent metrics → must block (anti-gaming)
# ---------------------------------------------------------------------------


def test_chaos_zero_failures_with_obs_failure_logs_blocks(route_artifact: dict) -> None:
    """Adversarial: caller suppressed failures while OBS still has logs."""
    obs_with_logs = {**_OBS_FULL, "failure_logs": [{"reason": "drift"}]}
    with pytest.raises(RFXAdversarialReliabilityError, match="rfx_suspicious_signal_suppression"):
        assert_rfx_promotion_ready(**_kwargs(route_artifact, obs=obs_with_logs))


def test_chaos_zero_failures_with_replay_mismatches_caught_upstream(route_artifact: dict) -> None:
    """LOOP-07 catches this as drift first, ahead of the anti-gaming guard."""
    drift = [{"trace_id": "trace-chaos-001", "match": False}]
    with pytest.raises(RFXReliabilityFreezeError, match="rfx_replay_drift_detected"):
        assert_rfx_promotion_ready(**_kwargs(route_artifact, replay_results=drift))


# ---------------------------------------------------------------------------
# Chaos: remove trace linkage → must block
# ---------------------------------------------------------------------------


def test_chaos_obs_without_artifact_linkage_blocks_loop08(route_artifact: dict) -> None:
    """LOOP-08 fires on missing artifact_linkage before OBS+REP consistency."""
    obs = {**_OBS_FULL}
    obs.pop("artifact_linkage")
    with pytest.raises(RFXTelemetrySLOError, match="rfx_obs_incomplete"):
        assert_rfx_promotion_ready(**_kwargs(route_artifact, obs=obs))


def test_chaos_obs_with_empty_artifact_linkage_blocks_at_loop08(route_artifact: dict) -> None:
    """Empty ``artifact_linkage`` list now fails closed at LOOP-08 with
    ``rfx_obs_empty_field`` — the field is present but carries no
    telemetry content. The OBS+REP consistency layer would also catch
    this if reached, but LOOP-08 is the earlier (stricter) gate."""
    obs = {**_OBS_FULL, "artifact_linkage": []}
    with pytest.raises(RFXTelemetrySLOError, match="rfx_obs_empty_field"):
        assert_rfx_promotion_ready(**_kwargs(route_artifact, obs=obs))


def test_chaos_replay_referencing_unknown_trace_blocks(route_artifact: dict) -> None:
    bad = [{"trace_id": "trace-other", "match": True}]
    with pytest.raises(RFXObservabilityReplayConsistencyError, match="rfx_trace_replay_inconsistency"):
        assert_rfx_promotion_ready(**_kwargs(route_artifact, replay_results=bad))


# ---------------------------------------------------------------------------
# Order discipline: LOOP-07 fires before LOOP-08 / consistency / anti-gaming
# ---------------------------------------------------------------------------


def test_loop07_fires_before_loop08_when_both_would_block(route_artifact: dict) -> None:
    failures = [
        {"timestamp_seconds": 80.0 + i, "reason_code": "x"} for i in range(5)
    ]
    obs = {**_OBS_FULL, "failure_logs": failures}
    obs.pop("trace_id")  # would also break LOOP-08
    with pytest.raises(RFXReliabilityFreezeError, match="rfx_burst_failure_detected"):
        assert_rfx_promotion_ready(
            **_kwargs(route_artifact, recent_failures=failures, obs=obs, window_seconds=100)
        )
