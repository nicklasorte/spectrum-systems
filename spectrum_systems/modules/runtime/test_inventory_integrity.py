from __future__ import annotations

import configparser
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


FAILURE_CLASSES = {
    "pytest_config_missing",
    "pytest_config_mismatch",
    "testpaths_missing",
    "no_tests_discovered",
    "unexpected_test_inventory_regression",
    "import_resolution_failure",
    "collection_failure",
    "working_directory_mismatch",
    "accidental_filtering_detected",
    "success",
}


@dataclass(frozen=True)
class IntegrityEvaluation:
    status: str
    failure_class: str
    blocking: bool
    payload: dict[str, Any]


def _read_pytest_ini(repo_root: Path) -> tuple[dict[str, Any], str | None]:
    pytest_ini = repo_root / "pytest.ini"
    if not pytest_ini.is_file():
        return {}, "pytest_config_missing"

    parser = configparser.ConfigParser()
    parser.read(pytest_ini, encoding="utf-8")
    if "pytest" not in parser:
        return {}, "pytest_config_mismatch"

    section = parser["pytest"]
    raw_testpaths = str(section.get("testpaths", "")).strip()
    if not raw_testpaths:
        return {
            "pytest_ini_path": str(pytest_ini.relative_to(repo_root)),
            "raw_testpaths": raw_testpaths,
        }, "testpaths_missing"

    testpaths = [entry for entry in raw_testpaths.split() if entry]
    addopts = str(section.get("addopts", "")).strip()
    pythonpath = str(section.get("pythonpath", "")).strip()
    return {
        "pytest_ini_path": str(pytest_ini.relative_to(repo_root)),
        "raw_testpaths": raw_testpaths,
        "testpaths": testpaths,
        "addopts": addopts,
        "pythonpath": pythonpath,
    }, None


def _discover_test_files(repo_root: Path, testpaths: list[str]) -> tuple[list[str], list[str]]:
    missing_roots: list[str] = []
    discovered: list[str] = []
    for rel in testpaths:
        root = repo_root / rel
        if not root.exists():
            missing_roots.append(rel)
            continue
        if root.is_file() and root.name.startswith("test_") and root.suffix == ".py":
            discovered.append(root.relative_to(repo_root).as_posix())
            continue
        if root.is_dir():
            for candidate in sorted(root.rglob("test_*.py")):
                if candidate.is_file():
                    discovered.append(candidate.relative_to(repo_root).as_posix())
    return sorted(set(discovered)), sorted(set(missing_roots))


def _run_collect(repo_root: Path, targets: list[str] | None = None, cwd: Path | None = None) -> tuple[int, list[str], str]:
    pytest_bin = shutil.which("pytest")
    if pytest_bin:
        command = [pytest_bin, "--collect-only", "-q"]
    else:
        command = [sys.executable, "-m", "pytest", "--collect-only", "-q"]
    if targets:
        command.extend(targets)
    completed = subprocess.run(command, cwd=str(cwd or repo_root), capture_output=True, text=True, check=False)
    output = f"{completed.stdout}\n{completed.stderr}".strip()
    nodeids: list[str] = []
    for line in (completed.stdout or "").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("=") or stripped.endswith("collected") or "collected" in stripped:
            continue
        if stripped.startswith("no tests ran"):
            continue
        if "::" in stripped and not stripped.startswith("ERROR"):
            nodeids.append(stripped)
    return completed.returncode, sorted(set(nodeids)), output[-8000:]


def _load_baseline(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {
            "schema_version": "1.0.0",
            "suite_name": "pr_default",
            "expected_count": 0,
            "expected_nodeids": [],
            "baseline_status": "missing",
        }
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("baseline payload must be an object")
    payload["baseline_status"] = "present"
    return payload


def refresh_baseline(*, repo_root: Path, baseline_path: Path, suite_targets: list[str] | None = None) -> dict[str, Any]:
    _code, nodeids, _output = _run_collect(repo_root=repo_root, targets=suite_targets)
    payload = {
        "schema_version": "1.0.0",
        "suite_name": "pr_default",
        "expected_count": len(nodeids),
        "expected_nodeids": nodeids,
        "suite_targets": suite_targets or [],
    }
    baseline_path.parent.mkdir(parents=True, exist_ok=True)
    baseline_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def evaluate_test_inventory_integrity(
    *,
    repo_root: Path,
    baseline_path: Path,
    suite_targets: list[str] | None = None,
    execution_cwd: Path | None = None,
) -> IntegrityEvaluation:
    execution_cwd = execution_cwd or repo_root
    payload: dict[str, Any] = {
        "artifact_type": "test_inventory_integrity_result",
        "schema_version": "1.0.0",
        "owner_system": "PRG",
        "policy_observation": "SEL",
        "execution_system": "PQX",
        "orchestration_system": "TLC",
        "diagnosis_system": "FRE",
        "registry_system": "SRG",
        "configured_test_roots": [],
        "discovered_test_files": [],
        "collected_nodeids": [],
        "selected_nodeids": [],
        "collected_count": 0,
        "selected_count": 0,
        "baseline_expected_count": 0,
        "baseline_expected_nodeids": [],
        "baseline_missing_nodeids": [],
        "baseline_unexpected_nodeids": [],
        "failure_class": "success",
        "status": "passed",
        "blocking": False,
        "recommended_repair_route": "none",
        "classification_detail": "",
        "execution_cwd": str(execution_cwd),
        "repo_root": str(repo_root),
    }

    if execution_cwd.resolve() != repo_root.resolve():
        payload.update(
            failure_class="working_directory_mismatch",
            status="failed",
            blocking=True,
            recommended_repair_route="run pytest collection from repository root",
            classification_detail="pytest collection was invoked from a non-root working directory",
        )
        return IntegrityEvaluation("failed", "working_directory_mismatch", True, payload)

    config, config_failure = _read_pytest_ini(repo_root)
    payload["pytest_config"] = config
    if config_failure:
        payload.update(
            failure_class=config_failure,
            status="failed",
            blocking=True,
            recommended_repair_route="repair pytest.ini test configuration",
            classification_detail="pytest configuration is missing or malformed",
        )
        return IntegrityEvaluation("failed", config_failure, True, payload)

    testpaths = list(config.get("testpaths", []))
    payload["configured_test_roots"] = testpaths
    discovered, missing_roots = _discover_test_files(repo_root, testpaths)
    payload["discovered_test_files"] = discovered
    if missing_roots:
        payload.update(
            failure_class="testpaths_missing",
            status="failed",
            blocking=True,
            recommended_repair_route="align pytest testpaths with on-disk test directories",
            classification_detail=f"missing configured test roots: {', '.join(missing_roots)}",
        )
        return IntegrityEvaluation("failed", "testpaths_missing", True, payload)
    if not discovered:
        payload.update(
            failure_class="no_tests_discovered",
            status="failed",
            blocking=True,
            recommended_repair_route="restore tests/ inventory or pytest naming conventions",
            classification_detail="configured test roots contain no discoverable test files",
        )
        return IntegrityEvaluation("failed", "no_tests_discovered", True, payload)

    collect_code, collected_nodeids, collect_output = _run_collect(repo_root=repo_root)
    payload["collected_nodeids"] = collected_nodeids
    payload["collected_count"] = len(collected_nodeids)
    payload["collect_output_excerpt"] = collect_output

    if collect_code != 0:
        lowered = collect_output.lower()
        failure_class = "import_resolution_failure" if ("modulenotfounderror" in lowered or "importerror" in lowered) else "collection_failure"
        payload.update(
            failure_class=failure_class,
            status="failed",
            blocking=True,
            recommended_repair_route="repair import/module boundaries for deterministic pytest collection",
            classification_detail="pytest collection failed before deterministic node inventory could be established",
        )
        return IntegrityEvaluation("failed", failure_class, True, payload)

    selected_targets = suite_targets or []
    sel_code, selected_nodeids, selected_output = _run_collect(repo_root=repo_root, targets=selected_targets)
    payload["selected_targets"] = selected_targets
    payload["selected_nodeids"] = selected_nodeids
    payload["selected_count"] = len(selected_nodeids)
    payload["selected_output_excerpt"] = selected_output

    if sel_code != 0:
        lowered = selected_output.lower()
        failure_class = "import_resolution_failure" if ("modulenotfounderror" in lowered or "importerror" in lowered) else "collection_failure"
        payload.update(
            failure_class=failure_class,
            status="failed",
            blocking=True,
            recommended_repair_route="repair selected-suite import/module boundaries",
            classification_detail="pytest selected-suite collection failed",
        )
        return IntegrityEvaluation("failed", failure_class, True, payload)

    baseline = _load_baseline(baseline_path)
    expected_nodeids = sorted({str(item) for item in baseline.get("expected_nodeids", []) if isinstance(item, str)})
    payload["baseline_expected_count"] = int(baseline.get("expected_count", len(expected_nodeids)))
    payload["baseline_expected_nodeids"] = expected_nodeids
    payload["baseline_status"] = baseline.get("baseline_status", "present")

    if payload["baseline_status"] == "missing":
        payload.update(
            failure_class="pytest_config_mismatch",
            status="failed",
            blocking=True,
            recommended_repair_route="create governed baseline manifest via refresh flow",
            classification_detail="baseline manifest missing for PR/default suite",
        )
        return IntegrityEvaluation("failed", "pytest_config_mismatch", True, payload)

    selected_set = set(selected_nodeids)
    expected_set = set(expected_nodeids)
    payload["baseline_missing_nodeids"] = sorted(expected_set - selected_set)
    payload["baseline_unexpected_nodeids"] = sorted(selected_set - expected_set)

    if payload["selected_count"] == 0:
        payload.update(
            failure_class="no_tests_discovered",
            status="failed",
            blocking=True,
            recommended_repair_route="repair selected test targets and pytest collection filters",
            classification_detail="selected PR/default suite produced zero tests",
        )
        return IntegrityEvaluation("failed", "no_tests_discovered", True, payload)

    addopts = str(config.get("addopts", ""))
    env_filter = os.environ.get("PYTEST_ADDOPTS", "")
    if ("-k " in addopts or "-m " in addopts or "-k " in env_filter or "-m " in env_filter) and payload["selected_count"] < payload["baseline_expected_count"]:
        payload.update(
            failure_class="accidental_filtering_detected",
            status="failed",
            blocking=True,
            recommended_repair_route="remove accidental pytest filter flags for governed PR suite",
            classification_detail="pytest marker/expression filtering reduced selected inventory below baseline",
        )
        return IntegrityEvaluation("failed", "accidental_filtering_detected", True, payload)

    if payload["selected_count"] < payload["baseline_expected_count"] or payload["baseline_missing_nodeids"] or payload["baseline_unexpected_nodeids"]:
        payload.update(
            failure_class="unexpected_test_inventory_regression",
            status="failed",
            blocking=True,
            recommended_repair_route="restore baseline node inventory or perform explicit governed baseline refresh",
            classification_detail="selected suite inventory drifted from governed baseline",
        )
        return IntegrityEvaluation("failed", "unexpected_test_inventory_regression", True, payload)

    return IntegrityEvaluation("passed", "success", False, payload)
