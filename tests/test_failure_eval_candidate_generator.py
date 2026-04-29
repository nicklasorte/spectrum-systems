"""Tests for failure_eval_candidate_generator (CLX-ALL-01 Phase 3).

Covers:
- Known failure classes produce correct eval_type
- Unknown failure class raises error (fail-closed)
- Missing trace_id raises error
- Missing source_failure_ref raises error
- Deterministic: same inputs produce same entry_id
- Deduplication works
- Skipped items do not silently produce entries
- Full registry output has required fields
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.modules.runtime.failure_eval_candidate_generator import (
    FailureEvalCandidateGeneratorError,
    generate_eval_candidate_entry,
    generate_eval_candidate_registry,
)


def test_authority_shape_violation_produces_authority_shape_eval() -> None:
    entry = generate_eval_candidate_entry(
        trace_id="t",
        failure_class="authority_shape_violation",
        source_failure_ref="pkt-001",
    )
    assert entry["eval_type"] == "authority_shape"
    assert entry["adoption_status"] == "pending_review"
    assert entry["deterministic"] is True


def test_registry_guard_failure_produces_registry_guard_eval() -> None:
    entry = generate_eval_candidate_entry(
        trace_id="t",
        failure_class="registry_guard_failure",
        source_failure_ref="rg-001",
    )
    assert entry["eval_type"] == "registry_guard"


def test_manifest_drift_produces_manifest_drift_eval() -> None:
    entry = generate_eval_candidate_entry(
        trace_id="t",
        failure_class="manifest_drift",
        source_failure_ref="md-001",
    )
    assert entry["eval_type"] == "manifest_drift"


def test_unknown_failure_class_raises() -> None:
    import pytest
    with pytest.raises(FailureEvalCandidateGeneratorError, match="Unknown failure_class"):
        generate_eval_candidate_entry(
            trace_id="t",
            failure_class="totally_made_up_class",
            source_failure_ref="ref-001",
        )


def test_missing_trace_id_raises() -> None:
    import pytest
    with pytest.raises(FailureEvalCandidateGeneratorError, match="trace_id"):
        generate_eval_candidate_entry(
            trace_id="",
            failure_class="authority_shape_violation",
            source_failure_ref="ref-001",
        )


def test_missing_source_ref_raises() -> None:
    import pytest
    with pytest.raises(FailureEvalCandidateGeneratorError, match="source_failure_ref"):
        generate_eval_candidate_entry(
            trace_id="t",
            failure_class="authority_shape_violation",
            source_failure_ref="",
        )


def test_deterministic_same_inputs_same_entry_id() -> None:
    entry1 = generate_eval_candidate_entry(
        trace_id="stable-trace",
        failure_class="authority_shape_violation",
        source_failure_ref="ref-stable",
    )
    entry2 = generate_eval_candidate_entry(
        trace_id="stable-trace",
        failure_class="authority_shape_violation",
        source_failure_ref="ref-stable",
    )
    assert entry1["entry_id"] == entry2["entry_id"]


def test_different_inputs_different_entry_id() -> None:
    entry1 = generate_eval_candidate_entry(
        trace_id="t",
        failure_class="authority_shape_violation",
        source_failure_ref="ref-A",
    )
    entry2 = generate_eval_candidate_entry(
        trace_id="t",
        failure_class="registry_guard_failure",
        source_failure_ref="ref-B",
    )
    assert entry1["entry_id"] != entry2["entry_id"]


def test_registry_deduplicates_entries() -> None:
    failures = [
        {"failure_class": "authority_shape_violation", "source_failure_ref": "ref-dup"},
        {"failure_class": "authority_shape_violation", "source_failure_ref": "ref-dup"},
    ]
    registry = generate_eval_candidate_registry(trace_id="t", failures=failures)
    assert registry["total_entries"] == 1
    assert len(registry["entries"]) == 1


def test_registry_skips_unknown_failure_class_without_raising() -> None:
    failures = [
        {"failure_class": "unknown_bad_class", "source_failure_ref": "ref-X"},
        {"failure_class": "authority_shape_violation", "source_failure_ref": "ref-Y"},
    ]
    registry = generate_eval_candidate_registry(trace_id="t", failures=failures)
    assert registry["total_entries"] == 1
    assert registry["entries"][0]["failure_class"] == "authority_shape_violation"


def test_registry_required_fields() -> None:
    registry = generate_eval_candidate_registry(
        trace_id="t",
        failures=[{"failure_class": "manifest_drift", "source_failure_ref": "ref-001"}],
    )
    required = ["artifact_type", "schema_version", "registry_id", "trace_id", "entries", "total_entries", "emitted_at"]
    for key in required:
        assert key in registry, f"Missing key: {key}"
    assert registry["artifact_type"] == "eval_candidate_registry"


def test_empty_failures_produces_empty_registry() -> None:
    registry = generate_eval_candidate_registry(trace_id="t", failures=[])
    assert registry["total_entries"] == 0
    assert registry["entries"] == []


def test_all_accepted_failure_classes_work() -> None:
    from spectrum_systems.modules.runtime.failure_eval_candidate_generator import _ACCEPTED_FAILURE_CLASSES
    for fc in sorted(_ACCEPTED_FAILURE_CLASSES):
        entry = generate_eval_candidate_entry(
            trace_id="t",
            failure_class=fc,
            source_failure_ref=f"ref-{fc}",
        )
        assert entry["entry_id"].startswith("fecg-")
