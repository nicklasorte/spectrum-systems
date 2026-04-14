import json
from pathlib import Path

from spectrum_systems.contracts import validate_artifact
from spectrum_systems.modules.runtime.retroactive_pytest_integrity_audit import (
    classify_historical_preflight_artifact,
    run_retroactive_pytest_integrity_audit,
    scan_historical_preflight_artifacts,
)


def test_trusted_post_pyx01_artifact_is_trusted() -> None:
    artifact = {
        "artifact_type": "contract_preflight_result_artifact",
        "preflight_status": "passed",
        "control_signal": {"strategy_gate_decision": "ALLOW"},
        "generated_at": "2026-04-10T00:00:00Z",
        "pytest_execution": {
            "event_name": "pull_request",
            "pytest_execution_count": 1,
            "pytest_commands": ["python -m pytest tests/test_contract_preflight.py"],
            "selected_targets": ["tests/test_contract_preflight.py"],
            "fallback_targets": [],
            "fallback_used": False,
            "targeted_selection_empty": False,
            "fallback_selection_empty": True,
            "selection_reason_codes": [],
        },
    }

    classified = classify_historical_preflight_artifact(artifact, artifact_path="x.json")
    assert classified["classification"] == "trusted"


def test_historical_allow_without_execution_is_suspect() -> None:
    artifact = {
        "artifact_type": "contract_preflight_result_artifact",
        "preflight_status": "passed",
        "control_signal": {"strategy_gate_decision": "ALLOW"},
        "generated_at": "2026-03-01T00:00:00Z",
        "pytest_execution": {
            "event_name": "pull_request",
            "pytest_execution_count": 0,
            "pytest_commands": [],
            "selected_targets": [],
            "fallback_targets": [],
            "fallback_used": True,
            "targeted_selection_empty": True,
            "fallback_selection_empty": True,
            "selection_reason_codes": ["PR_PYTEST_SELECTED_TARGETS_EMPTY"],
        },
    }

    classified = classify_historical_preflight_artifact(artifact, artifact_path="x.json")
    assert classified["classification"] == "suspect_incomplete_execution_accounting"
    assert "HISTORICAL_PR_ALLOW_WITHOUT_PYTEST_EXECUTION" in classified["reason_codes"]


def test_pre_pyx01_shape_is_flagged_deterministically() -> None:
    artifact = {
        "artifact_type": "contract_preflight_result_artifact",
        "preflight_status": "passed",
        "control_signal": {"strategy_gate_decision": "WARN"},
        "changed_path_detection": {"ref_context": {"event_name": "pull_request"}},
    }

    classified = classify_historical_preflight_artifact(artifact, artifact_path="x.json")
    assert classified["classification"] == "suspect_missing_pytest_execution"
    assert "HISTORICAL_ARTIFACT_SHAPE_PRE_PYX01" in classified["reason_codes"]
    assert "HISTORICAL_WARN_WITHOUT_PYTEST_EXECUTION" in classified["reason_codes"]


def test_unable_to_evaluate_when_context_missing() -> None:
    artifact = {
        "artifact_type": "contract_preflight_result_artifact",
        "preflight_status": "failed",
    }

    classified = classify_historical_preflight_artifact(artifact, artifact_path="x.json")
    assert classified["classification"] == "unable_to_evaluate"
    assert "HISTORICAL_CONTEXT_NOT_EVALUABLE" in classified["reason_codes"]


def test_non_pr_context_not_misclassified_as_pr_failure() -> None:
    artifact = {
        "artifact_type": "contract_preflight_result_artifact",
        "preflight_status": "passed",
        "control_signal": {"strategy_gate_decision": "ALLOW"},
        "pytest_execution": {
            "event_name": "push",
            "pytest_execution_count": 0,
            "pytest_commands": [],
            "selected_targets": [],
            "fallback_targets": [],
            "fallback_used": False,
            "targeted_selection_empty": True,
            "fallback_selection_empty": True,
            "selection_reason_codes": [],
        },
    }

    classified = classify_historical_preflight_artifact(artifact, artifact_path="x.json")
    assert classified["classification"] == "trusted"


def test_deterministic_remediation_queue_and_schema_validation(tmp_path: Path) -> None:
    root = tmp_path / "outputs"
    first = root / "a" / "contract_preflight_result_artifact.json"
    first.parent.mkdir(parents=True, exist_ok=True)
    first.write_text(
        json.dumps(
            {
                "artifact_type": "contract_preflight_result_artifact",
                "preflight_status": "passed",
                "control_signal": {"strategy_gate_decision": "ALLOW"},
                "changed_path_detection": {"ref_context": {"event_name": "pull_request"}},
                "generated_at": "2026-02-01T00:00:00Z",
            }
        ),
        encoding="utf-8",
    )

    second = root / "b" / "contract_preflight_result_artifact.json"
    second.parent.mkdir(parents=True, exist_ok=True)
    second.write_text(
        json.dumps(
            {
                "artifact_type": "contract_preflight_result_artifact",
                "preflight_status": "passed",
                "control_signal": {"strategy_gate_decision": "ALLOW"},
                "generated_at": "2026-04-01T00:00:00Z",
                "pytest_execution": {
                    "event_name": "pull_request",
                    "pytest_execution_count": 1,
                    "pytest_commands": ["pytest tests/test_contract_preflight.py"],
                    "selected_targets": ["tests/test_contract_preflight.py"],
                    "fallback_targets": [],
                    "fallback_used": False,
                    "targeted_selection_empty": False,
                    "fallback_selection_empty": True,
                    "selection_reason_codes": [],
                },
            }
        ),
        encoding="utf-8",
    )

    scanned = scan_historical_preflight_artifacts([root])
    result, queue = run_retroactive_pytest_integrity_audit(
        scanned_artifacts=scanned,
        audit_scope={"roots": [str(root)], "artifact_globs": ["**/contract_preflight_result_artifact.json"], "repo_root": str(tmp_path)},
        remediation_queue_limit=5,
    )

    assert result["scanned_run_count"] == 2
    assert result["suspect_count"] == 1
    assert result["trusted_count"] == 1
    assert queue["queue_size"] == 1
    assert queue["items"][0]["artifact_path"].endswith("a/contract_preflight_result_artifact.json")

    validate_artifact(result, "retroactive_pytest_integrity_audit_result")
    validate_artifact(queue, "retroactive_pytest_remediation_queue")


def test_examples_validate() -> None:
    audit_example = json.loads(Path("contracts/examples/retroactive_pytest_integrity_audit_result.json").read_text(encoding="utf-8"))
    queue_example = json.loads(Path("contracts/examples/retroactive_pytest_remediation_queue.json").read_text(encoding="utf-8"))
    validate_artifact(audit_example, "retroactive_pytest_integrity_audit_result")
    validate_artifact(queue_example, "retroactive_pytest_remediation_queue")
