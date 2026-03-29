from __future__ import annotations

from copy import deepcopy

import pytest

from spectrum_systems.modules.runtime.provenance_verification import (
    ProvenanceVerificationError,
    assert_linked_identity_consistency,
    assert_persisted_reload_identity,
    validate_required_identity,
)


def test_persisted_reload_identity_preserves_ids() -> None:
    persisted = {"run_id": "run-001", "trace_id": "trace-001", "artifact_type": "x"}
    reloaded = {"run_id": "run-001", "trace_id": "trace-001", "artifact_type": "x"}
    assert_persisted_reload_identity(
        persisted,
        reloaded,
        persisted_label="persisted",
        reloaded_label="reloaded",
    )


def test_downstream_mismatched_trace_rejected() -> None:
    with pytest.raises(ProvenanceVerificationError, match="PROVENANCE_TRACE_MISMATCH"):
        assert_linked_identity_consistency(
            {"run_id": "run-001", "trace_id": "trace-001"},
            {"run_id": "run-001", "trace_id": "trace-002"},
            upstream_label="replay",
            linked_label="eval",
            require_same_run=True,
        )


def test_downstream_mismatched_run_rejected_when_same_run_required() -> None:
    with pytest.raises(ProvenanceVerificationError, match="PROVENANCE_RUN_MISMATCH"):
        assert_linked_identity_consistency(
            {"run_id": "run-001", "trace_id": "trace-001"},
            {"run_id": "run-002", "trace_id": "trace-001"},
            upstream_label="replay",
            linked_label="eval",
            require_same_run=True,
        )


def test_explicit_cross_run_reference_is_allowed() -> None:
    assert_linked_identity_consistency(
        {"run_id": "run-001", "trace_id": "trace-001"},
        {"run_id": "run-002", "trace_id": "trace-001"},
        upstream_label="replay",
        linked_label="eval",
        require_same_run=True,
        allow_cross_run_reference=True,
    )


def test_verification_does_not_mutate_inputs() -> None:
    upstream = {"run_id": "run-001", "trace_id": "trace-001", "nested": {"a": 1}}
    downstream = {"run_id": "run-001", "trace_id": "trace-001", "nested": {"b": 2}}
    upstream_before = deepcopy(upstream)
    downstream_before = deepcopy(downstream)

    validate_required_identity(upstream, label="upstream")
    assert_linked_identity_consistency(
        upstream,
        downstream,
        upstream_label="upstream",
        linked_label="downstream",
    )

    assert upstream == upstream_before
    assert downstream == downstream_before
