from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

from spectrum_systems.modules.runtime.control_executor import execute_with_enforcement  # noqa: E402
from spectrum_systems.modules.runtime.enforcement_engine import (  # noqa: E402
    enforce_budget_decision,
    validate_enforcement_result,
)


def _decision(system_response: str) -> Dict[str, Any]:
    return {
        "decision_id": "dec-001",
        "summary_id": "sum-001",
        "trace_id": "trace-001",
        "timestamp": "2026-03-21T00:00:00Z",
        "status": "healthy" if system_response in {"allow", "warn"} else "blocked",
        "system_response": system_response,
        "triggered_thresholds": [],
        "reasons": ["fixture decision"],
    }


def _base_manifest() -> dict:
    return {
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


def _build_bundle(tmp_path: Path, *, valid: bool = True) -> Path:
    bundle = tmp_path / "bundle"
    (bundle / "inputs").mkdir(parents=True)
    (bundle / "outputs").mkdir(parents=True)
    (bundle / "logs").mkdir(parents=True)
    (bundle / "inputs" / "cases.json").write_text("{}", encoding="utf-8")
    manifest = _base_manifest()
    if not valid:
        manifest.pop("platform")
    (bundle / "run_bundle_manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )
    return bundle


def test_allow_decision_execution_permitted() -> None:
    result = enforce_budget_decision(_decision("allow"))
    assert result["enforcement_action"] == "allow"
    assert result["execution_permitted"] is True
    assert result["enforcement_status"] == "executed"
    assert validate_enforcement_result(result) == []


def test_warn_decision_execution_permitted() -> None:
    result = enforce_budget_decision(_decision("warn"))
    assert result["enforcement_action"] == "warn"
    assert result["execution_permitted"] is True
    assert result["enforcement_status"] == "executed"
    assert validate_enforcement_result(result) == []


def test_freeze_decision_execution_frozen() -> None:
    result = enforce_budget_decision(_decision("freeze"))
    assert result["enforcement_action"] == "freeze"
    assert result["execution_permitted"] is False
    assert result["enforcement_status"] == "frozen"


def test_block_decision_execution_blocked() -> None:
    result = enforce_budget_decision(_decision("block"))
    assert result["enforcement_action"] == "block"
    assert result["execution_permitted"] is False
    assert result["enforcement_status"] == "blocked"


def test_malformed_decision_fails_closed_block() -> None:
    result = enforce_budget_decision({"bad": "input"})
    assert result["enforcement_action"] == "block"
    assert result["execution_permitted"] is False
    assert result["enforcement_status"] == "blocked"


def test_unknown_system_response_fails_closed_block() -> None:
    result = enforce_budget_decision(_decision("unknown"))
    assert result["enforcement_action"] == "block"
    assert result["execution_permitted"] is False
    assert result["enforcement_status"] == "blocked"


def test_end_to_end_valid_bundle_allows_execution(tmp_path: Path) -> None:
    bundle = _build_bundle(tmp_path, valid=True)
    result = execute_with_enforcement(str(bundle))
    assert result["enforcement_action"] == "allow"
    assert result["execution_permitted"] is True


def test_end_to_end_invalid_bundle_blocks_execution(tmp_path: Path) -> None:
    bundle = _build_bundle(tmp_path, valid=False)
    result = execute_with_enforcement(str(bundle))
    assert result["enforcement_action"] == "block"
    assert result["execution_permitted"] is False


def test_cli_exit_codes(tmp_path: Path) -> None:
    script = _REPO_ROOT / "scripts" / "run_enforced_execution.py"

    valid_bundle = _build_bundle(tmp_path / "valid", valid=True)
    valid_proc = subprocess.run(
        [sys.executable, str(script), "--bundle", str(valid_bundle)], check=False
    )
    assert valid_proc.returncode == 0

    invalid_bundle = _build_bundle(tmp_path / "invalid", valid=False)
    invalid_proc = subprocess.run(
        [sys.executable, str(script), "--bundle", str(invalid_bundle)], check=False
    )
    assert invalid_proc.returncode == 2
