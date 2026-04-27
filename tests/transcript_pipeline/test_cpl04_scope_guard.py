"""CPL-04 scope guard for changed-file boundaries."""
from __future__ import annotations

from typing import Iterable, List

_ALLOWED_PATHS = (
    "contracts/schemas/transcript_pipeline/meeting_minutes_artifact.schema.json",
    "contracts/examples/meeting_minutes_artifact.json",
)

_ALLOWED_PREFIXES = (
    "spectrum_systems/modules/transcript_pipeline/",
    "tests/transcript_pipeline/",
    "docs/review-actions/CPL-04",
    "docs/review-actions/PLAN-CPL-04",
    "docs/review-actions/PLAN-BATCH-CPL-04",
    "docs/reviews/CPL-04",
    "contracts/review_actions/CPL-04",
    "contracts/review_artifact/CPL-04",
)

_BLOCKED_PATHS = (
    "contracts/standards-manifest.json",
    "contracts/schemas/certification_evidence_index.schema.json",
    "contracts/schemas/loop_proof_bundle.schema.json",
    "spectrum_systems/modules/runtime/context_admission_gate.py",
    "spectrum_systems/modules/runtime/slo_budget_gate.py",
    "docs/reviews/NS_ALL_01_delivery_report.md",
)

_BLOCKED_PREFIXES = (
    "contracts/governance/",
    "spectrum_systems/modules/governance/",
    "spectrum_systems/modules/observability/",
    "spectrum_systems/modules/lineage/",
    "tests/test_ns_",
)


def find_scope_violations(changed_files: Iterable[str]) -> List[str]:
    violations: List[str] = []
    for path in changed_files:
        if path in _BLOCKED_PATHS or any(path.startswith(prefix) for prefix in _BLOCKED_PREFIXES):
            violations.append(path)
            continue
        if path in _ALLOWED_PATHS or any(path.startswith(prefix) for prefix in _ALLOWED_PREFIXES):
            continue
        violations.append(path)
    return sorted(set(violations))


def test_cpl04_scope_guard_accepts_expected_paths() -> None:
    changed_files = [
        "contracts/schemas/transcript_pipeline/meeting_minutes_artifact.schema.json",
        "contracts/examples/meeting_minutes_artifact.json",
        "spectrum_systems/modules/transcript_pipeline/meeting_minutes_extractor.py",
        "tests/transcript_pipeline/test_meeting_minutes_extractor_cpl04.py",
        "docs/review-actions/CPL-04_review.json",
        "docs/review-actions/PLAN-CPL-04-FIX-STANDARDS-MANIFEST-SCOPE-2026-04-27.md",
    ]

    assert find_scope_violations(changed_files) == []


def test_cpl04_scope_guard_rejects_out_of_scope_paths() -> None:
    changed_files = [
        "contracts/standards-manifest.json",
        "contracts/governance/control_plane.schema.json",
        "spectrum_systems/modules/governance/authority.py",
        "spectrum_systems/modules/observability/telemetry.py",
        "spectrum_systems/modules/lineage/trace_mapper.py",
        "tests/test_ns_runtime.py",
    ]

    assert find_scope_violations(changed_files) == sorted(changed_files)
