#!/usr/bin/env python3
"""Thin roadmap realization runner for RF-02 and RF-03."""

from __future__ import annotations

import argparse
import importlib
import json
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.contracts import validate_artifact
from spectrum_systems.modules.runtime.roadmap_realization_runtime import (
    RoadmapRealizationRuntimeError,
    enforce_realization_dependencies,
    next_realization_status,
)

SUPPORTED_STEPS = ["RF-02", "RF-03"]
BASELINE_REALIZATION_STATUS = {"RF-01": "runtime_realized"}
DEFAULT_CONTRACT_DIR = REPO_ROOT / "artifacts" / "roadmap_contracts"
DEFAULT_RESULT_PATH = DEFAULT_CONTRACT_DIR / "roadmap_realization_result.json"
BASE_FORBIDDEN_PATTERNS = [
    "_write_json",
    '"status": "pass"',
    "artifact-only",
    "artifact_only",
]


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _contract_path(contract_dir: Path, step_id: str) -> Path:
    return contract_dir / f"{step_id}.json"


def _load_contract(contract_dir: Path, step_id: str) -> dict[str, Any]:
    path = _contract_path(contract_dir, step_id)
    if not path.is_file():
        raise FileNotFoundError(f"missing step contract: {path}")
    contract = _load_json(path)
    validate_artifact(contract, "roadmap_step_contract")
    if contract["step_id"] != step_id:
        raise ValueError(f"contract step mismatch: expected {step_id}, found {contract['step_id']}")
    return contract


def _validate_expansion_trace(contract: dict[str, Any], repo_root: Path) -> dict[str, Any]:
    trace_ref = contract["expansion_trace_ref"]
    if "#" not in trace_ref:
        raise ValueError(f"expansion_trace_ref missing fragment: {trace_ref}")
    trace_path_raw, _fragment = trace_ref.split("#", 1)
    trace_path = repo_root / trace_path_raw
    if not trace_path.is_file():
        raise FileNotFoundError(f"missing expansion trace: {trace_path}")
    trace = _load_json(trace_path)
    validate_artifact(trace, "roadmap_expansion_trace")
    if trace["expansion_version"] != contract["expansion_version"]:
        raise ValueError(f"expansion_version mismatch for {contract['step_id']}")
    if trace["expansion_policy_hash"] != contract["expansion_policy_hash"]:
        raise ValueError(f"expansion_policy_hash mismatch for {contract['step_id']}")
    return trace


def _check_runtime_entrypoints(runtime_entrypoints: list[str]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    for entry in runtime_entrypoints:
        module_name, sep, symbol = entry.partition(":")
        ok = True
        error = ""
        if not sep:
            ok = False
            error = "invalid entrypoint format"
        else:
            try:
                module = importlib.import_module(module_name)
                obj = getattr(module, symbol)
                if not callable(obj):
                    ok = False
                    error = "entrypoint is not callable"
            except Exception as exc:  # pragma: no cover - exercised in tests via contract values
                ok = False
                error = str(exc)
        checks.append({"entrypoint": entry, "exists": ok, "error": error})
    return checks


def _scan_forbidden_patterns(contract: dict[str, Any], repo_root: Path) -> list[dict[str, Any]]:
    patterns = sorted(set(contract["forbidden_patterns"] + BASE_FORBIDDEN_PATTERNS))
    hits: list[dict[str, Any]] = []
    scoped_files = sorted(set(contract["target_modules"]))
    for rel_path in scoped_files:
        path = repo_root / rel_path
        if not path.is_file():
            raise FileNotFoundError(f"missing target module path: {path}")
        text = path.read_text(encoding="utf-8")
        for pattern in patterns:
            if pattern in text:
                hits.append({"step_id": contract["step_id"], "path": rel_path, "pattern": pattern})
        if contract["step_id"] in text and '"status": "pass"' in text:
            hits.append(
                {
                    "step_id": contract["step_id"],
                    "path": rel_path,
                    "pattern": "direct static payload emission for target step",
                }
            )
    return hits


def _run_behavioral_tests(test_commands: list[str], repo_root: Path) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for command in test_commands:
        proc = subprocess.run(
            shlex.split(command),
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=False,
        )
        results.append(
            {
                "command": command,
                "returncode": proc.returncode,
                "passed": proc.returncode == 0,
                "stdout": proc.stdout,
                "stderr": proc.stderr,
            }
        )
    return results


def _verification_checks(contract: dict[str, Any], repo_root: Path) -> dict[str, Any]:
    contract_paths_exist = all((repo_root / path).is_file() for path in contract["target_contracts"])
    required_checks_declared = all(check.get("required") is True for check in contract["acceptance_checks"])
    return {
        "contract_paths_exist": contract_paths_exist,
        "required_checks_declared": required_checks_declared,
        "passed": contract_paths_exist and required_checks_declared,
    }


def realize_steps(
    *,
    step_ids: list[str],
    contract_dir: Path = DEFAULT_CONTRACT_DIR,
    result_path: Path = DEFAULT_RESULT_PATH,
    repo_root: Path = REPO_ROOT,
) -> dict[str, Any]:
    for step_id in step_ids:
        if step_id not in SUPPORTED_STEPS:
            raise ValueError(f"unsupported step: {step_id}")

    contracts = {step_id: _load_contract(contract_dir, step_id) for step_id in step_ids}
    for contract in contracts.values():
        _validate_expansion_trace(contract, repo_root)

    status_by_step = dict(BASELINE_REALIZATION_STATUS)
    status_by_step.update({step_id: contracts[step_id]["realization_status"] for step_id in step_ids})
    attempted_steps: list[str] = []
    passed_steps: list[str] = []
    failed_steps: list[str] = []
    forbidden_pattern_hits: dict[str, list[dict[str, Any]]] = {}
    runtime_entrypoint_checks: dict[str, list[dict[str, Any]]] = {}
    behavioral_test_results: dict[str, list[dict[str, Any]]] = {}
    status_updates: list[dict[str, str]] = []

    for step_id in step_ids:
        contract = contracts[step_id]
        attempted_steps.append(step_id)

        try:
            enforce_realization_dependencies(
                step_id=step_id,
                depends_on=contract["depends_on"],
                attempted_steps=attempted_steps,
                status_by_step=status_by_step,
            )
        except RoadmapRealizationRuntimeError:
            failed_steps.append(step_id)
            continue

        step_forbidden_hits = _scan_forbidden_patterns(contract, repo_root)
        forbidden_pattern_hits[step_id] = step_forbidden_hits

        step_entrypoint_checks = _check_runtime_entrypoints(contract["runtime_entrypoints"])
        runtime_entrypoint_checks[step_id] = step_entrypoint_checks

        step_behavioral_results = _run_behavioral_tests(contract["target_tests"], repo_root)
        behavioral_test_results[step_id] = step_behavioral_results

        verification = _verification_checks(contract, repo_root)
        prior_status = contract["realization_status"]
        next_status = next_realization_status(
            current_status=prior_status,
            forbidden_patterns_absent=len(step_forbidden_hits) == 0,
            runtime_entrypoints_exist=all(item["exists"] for item in step_entrypoint_checks),
            behavioral_tests_passed=all(result["passed"] for result in step_behavioral_results),
            verification_checks_passed=verification["passed"],
        )

        if next_status != prior_status:
            contract["realization_status"] = next_status
            _write_json(_contract_path(contract_dir, step_id), contract)
            status_updates.append({"step_id": step_id, "from": prior_status, "to": next_status})
            status_by_step[step_id] = next_status

        if next_status in {"runtime_realized", "verified"}:
            passed_steps.append(step_id)
        else:
            failed_steps.append(step_id)

    overall_status = "pass" if len(failed_steps) == 0 and len(step_ids) > 0 else "fail"
    result = {
        "artifact_type": "roadmap_realization_result",
        "step_ids": step_ids,
        "attempted_steps": attempted_steps,
        "passed_steps": passed_steps,
        "failed_steps": failed_steps,
        "forbidden_pattern_hits": forbidden_pattern_hits,
        "runtime_entrypoint_checks": runtime_entrypoint_checks,
        "behavioral_test_results": behavioral_test_results,
        "status_updates": status_updates,
        "overall_status": overall_status,
    }
    _write_json(result_path, result)
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("steps", nargs="*", default=SUPPORTED_STEPS)
    parser.add_argument("--contract-dir", default=str(DEFAULT_CONTRACT_DIR))
    parser.add_argument("--result-path", default=str(DEFAULT_RESULT_PATH))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = realize_steps(
        step_ids=list(args.steps),
        contract_dir=Path(args.contract_dir),
        result_path=Path(args.result_path),
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["overall_status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
