"""Tests for the RFX LOOP-08 telemetry-enforced SLO gate (Part 4)."""

from __future__ import annotations

import pytest

from spectrum_systems.modules.runtime.rfx_telemetry_slo_gate import (
    RFXTelemetrySLOError,
    assert_rfx_telemetry_slo_eligible,
)


_OBS_FULL = {
    "obs_id": "obs-1",
    "trace_id": "trace-1",
    "execution_path_coverage": ["AEX", "PQX", "EVL", "TPA", "CDE", "SEL"],
    "artifact_linkage": ["lin:001", "rep:001"],
    "failure_logs": [],
    "completeness": "pass",
}

_SLO_OK_DERIVED = {
    "slo_id": "slo-1",
    "status": "within_budget",
    "obs_ref": "obs-1",
}


def test_full_obs_and_derived_slo_passes() -> None:
    # Must not raise
    assert_rfx_telemetry_slo_eligible(obs=_OBS_FULL, slo=_SLO_OK_DERIVED)


def test_missing_obs_blocks() -> None:
    with pytest.raises(RFXTelemetrySLOError, match="rfx_missing_obs_telemetry"):
        assert_rfx_telemetry_slo_eligible(obs=None, slo=_SLO_OK_DERIVED)


def test_missing_slo_blocks() -> None:
    with pytest.raises(RFXTelemetrySLOError, match="rfx_missing_slo"):
        assert_rfx_telemetry_slo_eligible(obs=_OBS_FULL, slo=None)


@pytest.mark.parametrize("missing_key", [
    "trace_id", "execution_path_coverage", "artifact_linkage", "failure_logs",
])
def test_obs_missing_required_field_blocks(missing_key: str) -> None:
    obs = {k: v for k, v in _OBS_FULL.items() if k != missing_key}
    with pytest.raises(RFXTelemetrySLOError, match="rfx_obs_incomplete"):
        assert_rfx_telemetry_slo_eligible(obs=obs, slo=_SLO_OK_DERIVED)


def test_obs_completeness_must_be_pass() -> None:
    obs = {**_OBS_FULL, "completeness": "incomplete"}
    with pytest.raises(RFXTelemetrySLOError, match="rfx_obs_incomplete"):
        assert_rfx_telemetry_slo_eligible(obs=obs, slo=_SLO_OK_DERIVED)


def test_fake_slo_ok_with_missing_obs_segments_fires_inconsistency() -> None:
    """SLO posture ok + OBS missing trace segments → cross-check fires."""
    obs = {**_OBS_FULL}
    obs.pop("trace_id")
    with pytest.raises(RFXTelemetrySLOError) as exc:
        assert_rfx_telemetry_slo_eligible(obs=obs, slo=_SLO_OK_DERIVED)
    msg = str(exc.value)
    assert "rfx_obs_incomplete" in msg
    assert "rfx_slo_inconsistent_with_obs" in msg


def test_slo_without_obs_ref_fires_inconsistency() -> None:
    independent_slo = {"slo_id": "slo-1", "status": "within_budget"}
    with pytest.raises(RFXTelemetrySLOError, match="rfx_slo_inconsistent_with_obs"):
        assert_rfx_telemetry_slo_eligible(obs=_OBS_FULL, slo=independent_slo)


def test_slo_burn_status_blocks_directly() -> None:
    burning_slo = {"slo_id": "slo-1", "status": "over_budget", "obs_ref": "obs-1"}
    with pytest.raises(RFXTelemetrySLOError, match="rfx_slo_block"):
        assert_rfx_telemetry_slo_eligible(obs=_OBS_FULL, slo=burning_slo)


def test_obs_with_completeness_true_passes() -> None:
    obs = {**_OBS_FULL, "completeness": True}
    # Must not raise
    assert_rfx_telemetry_slo_eligible(obs=obs, slo=_SLO_OK_DERIVED)


# ---------------------------------------------------------------------------
# Documented OBS-source aliases must all be honored by _slo_derived_from_obs.
# ---------------------------------------------------------------------------


def test_slo_with_derived_from_obs_string_alias_passes() -> None:
    """The documented bare ``derived_from_obs: "<obs_id>"`` alias must be
    accepted as an OBS source reference (regression for Codex P2 finding)."""
    slo = {"slo_id": "slo-1", "status": "within_budget", "derived_from_obs": "obs-1"}
    # Must not raise.
    assert_rfx_telemetry_slo_eligible(obs=_OBS_FULL, slo=slo)


def test_slo_with_source_obs_id_alias_passes() -> None:
    slo = {"slo_id": "slo-1", "status": "within_budget", "source_obs_id": "obs-1"}
    assert_rfx_telemetry_slo_eligible(obs=_OBS_FULL, slo=slo)


def test_slo_with_derived_from_obs_id_alias_passes() -> None:
    slo = {"slo_id": "slo-1", "status": "within_budget", "derived_from_obs_id": "obs-1"}
    assert_rfx_telemetry_slo_eligible(obs=_OBS_FULL, slo=slo)


def test_slo_with_derived_from_obs_bool_alone_is_not_enough() -> None:
    """Boolean ``derived_from_obs=True`` without a matching id alias must
    NOT count as derived — fail-closed against an unverifiable claim."""
    slo = {"slo_id": "slo-1", "status": "within_budget", "derived_from_obs": True}
    with pytest.raises(RFXTelemetrySLOError, match="rfx_slo_inconsistent_with_obs"):
        assert_rfx_telemetry_slo_eligible(obs=_OBS_FULL, slo=slo)


def test_slo_with_derived_from_obs_string_mismatch_blocks() -> None:
    slo = {"slo_id": "slo-1", "status": "within_budget", "derived_from_obs": "obs-other"}
    with pytest.raises(RFXTelemetrySLOError, match="rfx_slo_inconsistent_with_obs"):
        assert_rfx_telemetry_slo_eligible(obs=_OBS_FULL, slo=slo)


# ---------------------------------------------------------------------------
# OBS field-shape validation (Codex P2 regression — line 157).
# Required fields must have telemetry-usable types, not just be present.
# ---------------------------------------------------------------------------


def test_failure_logs_dict_instead_of_list_blocks() -> None:
    """failure_logs={...} (dict) is not a usable telemetry shape — the
    anti-gaming guard's isinstance(logs, list) check would silently
    ignore it. Reject deterministically at LOOP-08."""
    obs = {**_OBS_FULL, "failure_logs": {"reason": "drift"}}
    with pytest.raises(RFXTelemetrySLOError, match="rfx_obs_invalid_field_shape"):
        assert_rfx_telemetry_slo_eligible(obs=obs, slo=_SLO_OK_DERIVED)


def test_artifact_linkage_string_instead_of_list_blocks() -> None:
    obs = {**_OBS_FULL, "artifact_linkage": "x"}
    with pytest.raises(RFXTelemetrySLOError, match="rfx_obs_invalid_field_shape"):
        assert_rfx_telemetry_slo_eligible(obs=obs, slo=_SLO_OK_DERIVED)


def test_execution_path_coverage_int_instead_of_list_blocks() -> None:
    obs = {**_OBS_FULL, "execution_path_coverage": 42}
    with pytest.raises(RFXTelemetrySLOError, match="rfx_obs_invalid_field_shape"):
        assert_rfx_telemetry_slo_eligible(obs=obs, slo=_SLO_OK_DERIVED)


def test_trace_id_int_instead_of_string_blocks() -> None:
    obs = {**_OBS_FULL, "trace_id": 123}
    with pytest.raises(RFXTelemetrySLOError, match="rfx_obs_invalid_field_shape"):
        assert_rfx_telemetry_slo_eligible(obs=obs, slo=_SLO_OK_DERIVED)


def test_failure_logs_bool_blocks() -> None:
    """bool is subclass of int but neither is a valid list shape."""
    obs = {**_OBS_FULL, "failure_logs": True}
    with pytest.raises(RFXTelemetrySLOError, match="rfx_obs_invalid_field_shape"):
        assert_rfx_telemetry_slo_eligible(obs=obs, slo=_SLO_OK_DERIVED)


def test_slo_with_stale_obs_ref_and_matching_source_obs_id_passes() -> None:
    """Codex P2 regression (line 117): every alias must be evaluated. A
    migration-era payload with a stale ``obs_ref`` AND a matching
    ``source_obs_id`` must pass — the prior or-chain shortcircuited on
    the first non-empty alias and incorrectly rejected this case."""
    slo = {
        "slo_id": "slo-1",
        "status": "within_budget",
        "obs_ref": "obs-stale",
        "source_obs_id": "obs-1",
    }
    # Must not raise — at least one alias matches the OBS id.
    assert_rfx_telemetry_slo_eligible(obs=_OBS_FULL, slo=slo)


def test_slo_with_two_stale_aliases_blocks() -> None:
    """Sanity counterpart: if no alias matches, the cross-check still
    fires. Locks in that the loop hasn't accidentally become permissive."""
    slo = {
        "slo_id": "slo-1",
        "status": "within_budget",
        "obs_ref": "obs-stale",
        "source_obs_id": "obs-also-stale",
    }
    with pytest.raises(RFXTelemetrySLOError, match="rfx_slo_inconsistent_with_obs"):
        assert_rfx_telemetry_slo_eligible(obs=_OBS_FULL, slo=slo)


# ---------------------------------------------------------------------------
# Empty execution_path_coverage / artifact_linkage must fail closed.
# ---------------------------------------------------------------------------


def test_empty_execution_path_coverage_blocks() -> None:
    """Codex P1 regression (line 167): empty list/dict for
    ``execution_path_coverage`` means no telemetry was recorded — fail
    closed instead of treating it as complete."""
    obs = {**_OBS_FULL, "execution_path_coverage": []}
    with pytest.raises(RFXTelemetrySLOError, match="rfx_obs_empty_field"):
        assert_rfx_telemetry_slo_eligible(obs=obs, slo=_SLO_OK_DERIVED)


def test_empty_artifact_linkage_blocks() -> None:
    obs = {**_OBS_FULL, "artifact_linkage": []}
    with pytest.raises(RFXTelemetrySLOError, match="rfx_obs_empty_field"):
        assert_rfx_telemetry_slo_eligible(obs=obs, slo=_SLO_OK_DERIVED)


def test_empty_artifact_linkage_dict_form_blocks() -> None:
    obs = {**_OBS_FULL, "artifact_linkage": {}}
    with pytest.raises(RFXTelemetrySLOError, match="rfx_obs_empty_field"):
        assert_rfx_telemetry_slo_eligible(obs=obs, slo=_SLO_OK_DERIVED)


def test_empty_failure_logs_still_passes() -> None:
    """``failure_logs=[]`` is a legitimate signal (no failures observed),
    so the empty-field invariant must NOT apply to it."""
    obs = {**_OBS_FULL, "failure_logs": []}
    # Must not raise.
    assert_rfx_telemetry_slo_eligible(obs=obs, slo=_SLO_OK_DERIVED)


def test_empty_obs_field_feeds_slo_inconsistent_cross_check() -> None:
    """When SLO posture is ok, an empty OBS coverage/linkage field must
    surface BOTH ``rfx_obs_empty_field`` AND
    ``rfx_slo_inconsistent_with_obs`` — the SLO claim is unsupported."""
    obs = {**_OBS_FULL, "execution_path_coverage": []}
    with pytest.raises(RFXTelemetrySLOError) as exc:
        assert_rfx_telemetry_slo_eligible(obs=obs, slo=_SLO_OK_DERIVED)
    msg = str(exc.value)
    assert "rfx_obs_empty_field" in msg
    assert "rfx_slo_inconsistent_with_obs" in msg


def test_artifact_linkage_dict_with_empty_per_trace_buckets_blocks() -> None:
    """Codex P1 regression (line 193): a dict-form linkage where every
    per-trace bucket is empty (e.g. ``{"trace-1": []}``) must fail at
    LOOP-08 — the outer non-empty check passes but no actual evidence
    is present, and OBS+REP consistency is inactive on the
    ``replay_results``-omitted path."""
    obs = {**_OBS_FULL, "artifact_linkage": {"trace-1": []}}
    with pytest.raises(RFXTelemetrySLOError, match="rfx_obs_empty_field"):
        assert_rfx_telemetry_slo_eligible(obs=obs, slo=_SLO_OK_DERIVED)


def test_artifact_linkage_dict_with_non_list_bucket_blocks() -> None:
    obs = {**_OBS_FULL, "artifact_linkage": {"trace-1": "not-a-list"}}
    with pytest.raises(RFXTelemetrySLOError, match="rfx_obs_empty_field"):
        assert_rfx_telemetry_slo_eligible(obs=obs, slo=_SLO_OK_DERIVED)


def test_execution_path_coverage_dict_with_empty_bucket_blocks() -> None:
    obs = {**_OBS_FULL, "execution_path_coverage": {"trace-1": []}}
    with pytest.raises(RFXTelemetrySLOError, match="rfx_obs_empty_field"):
        assert_rfx_telemetry_slo_eligible(obs=obs, slo=_SLO_OK_DERIVED)


def test_artifact_linkage_list_with_only_blank_entries_blocks() -> None:
    """Codex P1 regression (line 208): list-form linkage carrying only
    blank/None entries (e.g. ``["", null]``) carries no usable artifact
    reference and must fail closed at LOOP-08."""
    obs = {**_OBS_FULL, "artifact_linkage": ["", None]}
    with pytest.raises(RFXTelemetrySLOError, match="rfx_obs_empty_field"):
        assert_rfx_telemetry_slo_eligible(obs=obs, slo=_SLO_OK_DERIVED)


def test_artifact_linkage_dict_with_blank_only_list_bucket_blocks() -> None:
    obs = {**_OBS_FULL, "artifact_linkage": {"trace-1": ["", None]}}
    with pytest.raises(RFXTelemetrySLOError, match="rfx_obs_empty_field"):
        assert_rfx_telemetry_slo_eligible(obs=obs, slo=_SLO_OK_DERIVED)


def test_artifact_linkage_dict_with_blank_only_dict_bucket_blocks() -> None:
    obs = {**_OBS_FULL, "artifact_linkage": {"trace-1": {"lin": "", "rep": None}}}
    with pytest.raises(RFXTelemetrySLOError, match="rfx_obs_empty_field"):
        assert_rfx_telemetry_slo_eligible(obs=obs, slo=_SLO_OK_DERIVED)


def test_artifact_linkage_dict_form_passes() -> None:
    """The dict-keyed-by-trace_id form for artifact_linkage is supported
    by the OBS+REP consistency check, so LOOP-08 must accept it too."""
    obs = {**_OBS_FULL, "artifact_linkage": {"trace-1": ["lin:1"]}}
    # Must not raise — dict form is structurally valid.
    assert_rfx_telemetry_slo_eligible(obs=obs, slo=_SLO_OK_DERIVED)
