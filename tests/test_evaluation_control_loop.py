from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

from spectrum_systems.modules.runtime.evaluation_budget_governor import (  # noqa: E402
    build_validation_budget_decision,
)
from spectrum_systems.modules.runtime.evaluation_monitor import (  # noqa: E402
    EvaluationMonitorError,
    build_validation_monitor_record,
    summarize_validation_monitor_records,
)
from spectrum_systems.modules.runtime.run_bundle_validator import validate_and_emit_decision  # noqa: E402


def _artifact_decision(*, status: str = "valid", system_response: str = "allow") -> Dict[str, Any]:
    return {
        "decision_id": "dec-001",
        "run_id": "run-001",
        "trace_id": "trace-001",
        "status": status,
        "system_response": system_response,
        "validation_results": {
            "manifest_valid": status == "valid",
            "inputs_present": status == "valid",
            "expected_outputs_declared": status == "valid",
            "output_paths_valid": status == "valid",
            "provenance_required": status == "valid",
        },
        "missing_artifacts": [],
        "invalid_fields": [],
        "reasons": ["fixture decision"],
        "timestamp": "2026-03-21T00:00:00Z",
    }


def _bundle_manifest(valid: bool = True) -> Dict[str, Any]:
    manifest = {
        "run_id": "run-001",
        "matlab_release": "R2024b",
        "runtime_version_required": "R2024b",
        "platform": "linux-x86_64",
        "worker_entrypoint": "bin/run.sh",
        "inputs": [{"path": "inputs/cases.json", "required": True}],
        "expected_outputs": [
            {"path": "outputs/results_summary.json", "required": True},
            {"path": "outputs/provenance.json", "required": True},
        ],
    }
    if not valid:
        manifest.pop("platform")
    return manifest


def _build_bundle(tmp_path: Path, *, valid: bool = True, remove_outputs_dir: bool = False) -> Path:
    bundle = tmp_path / "bundle"
    (bundle / "inputs").mkdir(parents=True)
    (bundle / "outputs").mkdir(parents=True)
    (bundle / "logs").mkdir(parents=True)
    (bundle / "inputs" / "cases.json").write_text("{}", encoding="utf-8")
    (bundle / "run_bundle_manifest.json").write_text(
        json.dumps(_bundle_manifest(valid=valid)),
        encoding="utf-8",
    )
    if remove_outputs_dir:
        (bundle / "outputs").rmdir()
    return bundle


def test_monitor_record_valid_decision_healthy() -> None:
    record = build_validation_monitor_record(_artifact_decision(status="valid", system_response="allow"))
    assert record["status"] == "healthy"
    assert record["validation_status"] == "valid"
    assert record["system_response"] == "allow"
    assert record["slis"]["bundle_validation_success_rate"] == 1.0


def test_monitor_record_invalid_block_failed() -> None:
    record = build_validation_monitor_record(_artifact_decision(status="invalid", system_response="block"))
    assert record["status"] == "failed"
    assert record["validation_status"] == "invalid"
    assert record["system_response"] == "block"
    assert record["slis"]["bundle_validation_success_rate"] == 0.0


def test_monitor_record_malformed_indeterminate() -> None:
    record = build_validation_monitor_record(
        {
            "decision_id": "dec-malformed-001",
            "run_id": "run-malformed-001",
            "trace_id": "trace-malformed-001",
            "bad": "input",
        }
    )
    assert record["status"] == "indeterminate"
    assert record["system_response"] == "block"


@pytest.mark.parametrize("missing_field", ["run_id", "trace_id", "decision_id"])
def test_monitor_record_missing_required_traceability_ids_fail_closed(missing_field: str) -> None:
    decision = _artifact_decision(status="valid", system_response="allow")
    decision.pop(missing_field)
    with pytest.raises(EvaluationMonitorError, match=missing_field):
        build_validation_monitor_record(decision)


def test_summary_one_healthy_record_healthy() -> None:
    summary = summarize_validation_monitor_records([
        build_validation_monitor_record(_artifact_decision(status="valid", system_response="allow"))
    ])
    assert summary["overall_status"] == "healthy"


def test_summary_mixed_records_warning_at_or_above_point_8() -> None:
    records = [build_validation_monitor_record(_artifact_decision(status="valid", system_response="allow")) for _ in range(4)]
    records.append(build_validation_monitor_record(_artifact_decision(status="invalid", system_response="block")))
    summary = summarize_validation_monitor_records(records)
    assert summary["aggregated_slis"]["bundle_validation_success_rate"] == pytest.approx(0.8)
    assert summary["overall_status"] == "warning"


def test_summary_success_rate_between_zero_and_point_8_exhausted() -> None:
    records = [
        build_validation_monitor_record(_artifact_decision(status="valid", system_response="allow")),
        build_validation_monitor_record(_artifact_decision(status="invalid", system_response="block")),
    ]
    summary = summarize_validation_monitor_records(records)
    assert 0 < summary["aggregated_slis"]["bundle_validation_success_rate"] < 0.8
    assert summary["overall_status"] == "exhausted"


def test_summary_zero_success_rate_blocked() -> None:
    summary = summarize_validation_monitor_records([
        build_validation_monitor_record(_artifact_decision(status="invalid", system_response="block"))
    ])
    assert summary["aggregated_slis"]["bundle_validation_success_rate"] == 0.0
    assert summary["overall_status"] == "blocked"


def test_summary_indeterminate_record_indeterminate() -> None:
    summary = summarize_validation_monitor_records(
        [
            build_validation_monitor_record(
                {
                    "decision_id": "dec-malformed-002",
                    "run_id": "run-malformed-002",
                    "trace_id": "trace-malformed-002",
                    "bad": "input",
                }
            )
        ]
    )
    assert summary["overall_status"] == "indeterminate"


def test_summary_empty_input_fails_closed() -> None:
    with pytest.raises(EvaluationMonitorError):
        summarize_validation_monitor_records([])


@pytest.mark.parametrize(
    ("overall_status", "expected_response", "expected_status"),
    [
        ("healthy", "allow", "healthy"),
        ("warning", "warn", "warning"),
        ("exhausted", "freeze", "exhausted"),
        ("blocked", "block", "blocked"),
        ("indeterminate", "block", "blocked"),
    ],
)
def test_budget_decision_status_mapping(
    overall_status: str,
    expected_response: str,
    expected_status: str,
) -> None:
    summary = {
        "summary_id": "sum-001",
        "trace_id": "trace-001",
        "generated_at": "2026-03-21T00:00:00Z",
        "window": {"record_count": 1},
        "aggregated_slis": {
            "manifest_valid_rate": 1.0,
            "inputs_present_rate": 1.0,
            "expected_outputs_declared_rate": 1.0,
            "output_paths_valid_rate": 1.0,
            "provenance_required_rate": 1.0,
            "bundle_validation_success_rate": 1.0,
        },
        "overall_status": overall_status,
        "reasons": ["fixture summary"],
    }
    if overall_status in {"warning", "exhausted", "blocked", "indeterminate"}:
        summary["aggregated_slis"]["bundle_validation_success_rate"] = 0.5
    if overall_status == "blocked":
        summary["aggregated_slis"]["bundle_validation_success_rate"] = 0.0

    decision = build_validation_budget_decision(summary)
    assert decision["system_response"] == expected_response
    assert decision["status"] == expected_status


def test_end_to_end_valid_bundle_allows(tmp_path: Path) -> None:
    bundle = _build_bundle(tmp_path, valid=True)
    validator_decision = validate_and_emit_decision(bundle)
    record = build_validation_monitor_record(validator_decision)
    summary = summarize_validation_monitor_records([record])
    budget = build_validation_budget_decision(summary)
    assert budget["system_response"] == "allow"


def test_end_to_end_broken_bundle_blocks_or_freezes(tmp_path: Path) -> None:
    bundle = _build_bundle(tmp_path, valid=False)
    validator_decision = validate_and_emit_decision(bundle)
    record = build_validation_monitor_record(validator_decision)
    summary = summarize_validation_monitor_records([record])
    budget = build_validation_budget_decision(summary)
    assert budget["system_response"] in {"freeze", "block"}


def test_cli_exit_code_behavior(tmp_path: Path) -> None:
    script = _REPO_ROOT / "scripts" / "run_evaluation_control_loop.py"

    valid_bundle = _build_bundle(tmp_path / "valid", valid=True)
    valid_proc = subprocess.run([sys.executable, str(script), str(valid_bundle)], check=False)
    assert valid_proc.returncode == 0

    broken_bundle = _build_bundle(tmp_path / "broken", valid=False)
    broken_proc = subprocess.run([sys.executable, str(script), str(broken_bundle)], check=False)
    assert broken_proc.returncode in {1, 2}

    rebuild_bundle = _build_bundle(tmp_path / "rebuild", valid=True, remove_outputs_dir=True)
    rebuild_proc = subprocess.run([sys.executable, str(script), str(rebuild_bundle)], check=False)
    assert rebuild_proc.returncode in {1, 2}
