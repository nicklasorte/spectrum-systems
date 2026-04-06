from __future__ import annotations

import copy
from pathlib import Path

from spectrum_systems.contracts import load_example, validate_artifact
from spectrum_systems.modules.runtime.system_end_to_end_validator import run_system_end_to_end_governed_validation

_REVIEW_TEXT = """---
module: pqx
review_date: 2026-04-06
---
# Review

## Overall Assessment
**Overall Verdict: CONDITIONAL PASS**

## Critical Risks
1. Maintain governed PQX→TPA→FRE→RIL→SEL continuity.
"""

_ACTION_TRACKER_TEXT = """# Action Tracker

## Critical Items
| ID | Risk | Severity | Recommended Action | Status | Notes |
| --- | --- | --- | --- | --- | --- |
| CR-1 | Potential bypass path in sel boundary | Critical | Keep projection-only intake boundary (R1) | Open | blocking |

## High-Priority Items
| ID | Risk | Severity | Recommended Action | Status | Notes |
| --- | --- | --- | --- | --- | --- |
| HI-1 | Recoverability evidence could drift | High | Verify diagnosis->repair->recovery chain (R2) | Open | |

## Medium-Priority Items
| ID | Risk | Severity | Recommended Action | Status | Notes |
| --- | --- | --- | --- | --- | --- |
| MI-1 | Observability notes should remain explicit | Medium | Keep deterministic summary annotations (R3) | Open | |

## Blocking Items
- CR-1 blocks promotion.
"""


def _write_review_inputs(tmp_path: Path) -> tuple[Path, Path]:
    review_path = tmp_path / "review.md"
    action_tracker_path = tmp_path / "action_tracker.md"
    review_path.write_text(_REVIEW_TEXT, encoding="utf-8")
    action_tracker_path.write_text(_ACTION_TRACKER_TEXT, encoding="utf-8")
    return review_path, action_tracker_path


def test_system_end_to_end_result_example_contract_valid() -> None:
    validate_artifact(load_example("system_end_to_end_validation_result_artifact"), "system_end_to_end_validation_result_artifact")


def test_canonical_governed_scenario_passes_and_reports_successful_phases(tmp_path: Path) -> None:
    review_path, action_tracker_path = _write_review_inputs(tmp_path)

    output = run_system_end_to_end_governed_validation(
        review_path=review_path,
        action_tracker_path=action_tracker_path,
        runtime_dir=tmp_path / "runtime",
        emitted_at="2026-04-06T00:00:00Z",
    )
    result = output["validation_result"]

    validate_artifact(result, "system_end_to_end_validation_result_artifact")

    assert result["validation_status"] == "pass"
    assert result["pqx_phase_status"] == "pass"
    assert result["tpa_phase_status"] == "pass"
    assert result["fre_phase_status"] == "pass"
    assert result["ril_phase_status"] == "pass"
    assert result["sel_phase_status"] == "pass"


def test_required_artifacts_trace_lineage_and_sel_assertions_are_explicit(tmp_path: Path) -> None:
    review_path, action_tracker_path = _write_review_inputs(tmp_path)

    output = run_system_end_to_end_governed_validation(
        review_path=review_path,
        action_tracker_path=action_tracker_path,
        runtime_dir=tmp_path / "runtime",
        emitted_at="2026-04-06T00:00:00Z",
    )
    result = output["validation_result"]

    assert result["produced_artifact_refs"]
    assert "review_projection_bundle_artifact" in "\n".join(result["produced_artifact_refs"])
    assert "recovery_result_artifact" in "\n".join(result["produced_artifact_refs"])
    assert result["trace_continuity_verified"] is True
    assert result["lineage_continuity_verified"] is True
    assert result["sel_valid_path_allowed"] is True
    assert result["sel_invalid_path_blocked"] is True


def test_ril_artifact_flow_and_recovery_artifacts_present(tmp_path: Path) -> None:
    review_path, action_tracker_path = _write_review_inputs(tmp_path)

    output = run_system_end_to_end_governed_validation(
        review_path=review_path,
        action_tracker_path=action_tracker_path,
        runtime_dir=tmp_path / "runtime",
        emitted_at="2026-04-06T00:00:00Z",
    )
    phase_artifacts = output["phase_artifacts"]

    assert phase_artifacts["fre"]["failure_diagnosis_artifact"]["artifact_type"] == "failure_diagnosis_artifact"
    assert phase_artifacts["fre"]["repair_prompt_artifact"]["artifact_type"] == "repair_prompt_artifact"
    assert phase_artifacts["fre"]["recovery_result_artifact"]["artifact_type"] == "recovery_result_artifact"

    assert phase_artifacts["ril"]["review_signal_artifact"]["artifact_type"] == "review_signal_artifact"
    assert phase_artifacts["ril"]["review_control_signal_artifact"]["artifact_type"] == "review_control_signal_artifact"
    assert phase_artifacts["ril"]["review_integration_packet_artifact"]["artifact_type"] == "review_integration_packet_artifact"
    assert phase_artifacts["ril"]["review_projection_bundle_artifact"]["artifact_type"] == "review_projection_bundle_artifact"
    assert phase_artifacts["ril"]["review_consumer_output_bundle_artifact"]["artifact_type"] == "review_consumer_output_bundle_artifact"


def test_determinism_same_input_same_output(tmp_path: Path) -> None:
    review_path, action_tracker_path = _write_review_inputs(tmp_path)

    kwargs = {
        "review_path": review_path,
        "action_tracker_path": action_tracker_path,
        "runtime_dir": tmp_path / "runtime",
        "emitted_at": "2026-04-06T00:00:00Z",
    }

    first = run_system_end_to_end_governed_validation(**kwargs)
    second = run_system_end_to_end_governed_validation(**copy.deepcopy(kwargs))

    assert first == second
