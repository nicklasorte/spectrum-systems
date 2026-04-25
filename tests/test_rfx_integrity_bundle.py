"""Tests for the RFX LIN+REP integrity-bundle guard (LOOP-05)."""

from __future__ import annotations

import pytest

from spectrum_systems.modules.runtime.rfx_integrity_bundle import (
    RFXIntegrityBundleError,
    assert_rfx_integrity_bundle,
)


_VALID_LIN = {
    "lineage_id": "lin-rfx-001",
    "authenticity": "pass",
}

_VALID_REP = {
    "replay_id": "rep-rfx-001",
    "match": True,
}


# ---------------------------------------------------------------------------
# Lineage failures
# ---------------------------------------------------------------------------

def test_missing_lineage_blocks_certification_candidate() -> None:
    with pytest.raises(RFXIntegrityBundleError, match="rfx_missing_lineage"):
        assert_rfx_integrity_bundle(lineage_record=None, replay_record=_VALID_REP)


def test_empty_lineage_blocks_certification_candidate() -> None:
    with pytest.raises(RFXIntegrityBundleError, match="rfx_missing_lineage"):
        assert_rfx_integrity_bundle(lineage_record={}, replay_record=_VALID_REP)


def test_broken_lineage_authenticity_blocks_certification_candidate() -> None:
    broken = {**_VALID_LIN, "authenticity": "fail"}
    with pytest.raises(RFXIntegrityBundleError, match="rfx_lineage_not_authentic"):
        assert_rfx_integrity_bundle(lineage_record=broken, replay_record=_VALID_REP)


def test_lineage_missing_authenticity_blocks_certification_candidate() -> None:
    no_auth = {"lineage_id": "lin-rfx-001"}
    with pytest.raises(RFXIntegrityBundleError, match="rfx_lineage_not_authentic"):
        assert_rfx_integrity_bundle(lineage_record=no_auth, replay_record=_VALID_REP)


# ---------------------------------------------------------------------------
# Replay failures
# ---------------------------------------------------------------------------

def test_missing_replay_blocks_certification_candidate() -> None:
    with pytest.raises(RFXIntegrityBundleError, match="rfx_missing_replay"):
        assert_rfx_integrity_bundle(lineage_record=_VALID_LIN, replay_record=None)


def test_empty_replay_blocks_certification_candidate() -> None:
    with pytest.raises(RFXIntegrityBundleError, match="rfx_missing_replay"):
        assert_rfx_integrity_bundle(lineage_record=_VALID_LIN, replay_record={})


def test_replay_mismatch_freezes_certification_path() -> None:
    mismatch = {**_VALID_REP, "match": False}
    with pytest.raises(RFXIntegrityBundleError, match="rfx_replay_mismatch"):
        assert_rfx_integrity_bundle(lineage_record=_VALID_LIN, replay_record=mismatch)


def test_replay_match_non_boolean_blocks_certification_path() -> None:
    fishy = {**_VALID_REP, "match": "true"}
    with pytest.raises(RFXIntegrityBundleError, match="rfx_replay_mismatch"):
        assert_rfx_integrity_bundle(lineage_record=_VALID_LIN, replay_record=fishy)


def test_replay_record_missing_match_field_blocks_certification_path() -> None:
    no_match = {"replay_id": "rep-rfx-001"}
    with pytest.raises(RFXIntegrityBundleError, match="rfx_replay_mismatch"):
        assert_rfx_integrity_bundle(lineage_record=_VALID_LIN, replay_record=no_match)


# ---------------------------------------------------------------------------
# Valid bundle
# ---------------------------------------------------------------------------

def test_valid_integrity_bundle_passes() -> None:
    # Must not raise
    assert_rfx_integrity_bundle(lineage_record=_VALID_LIN, replay_record=_VALID_REP)
