#!/usr/bin/env python3
"""Thin roadmap realization runner for RF-02 and RF-03."""

from __future__ import annotations

import argparse
import importlib
import json
import re
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
    authoritative_start_status,
    enforce_realization_dependencies,
    next_realization_status,
)

SUPPORTED_STEPS = ["RF-02", "RF-03"]
BASELINE_REALIZATION_STATUS = {"RF-01": "runtime_realized"}
DEFAULT_CONTRACT_DIR = REPO_ROOT / "artifacts" / "roadmap_contracts"
DEFAULT_RESULT_PATH = DEFAULT_CONTRACT_DIR / "roadmap_realization_result.json"
DEFAULT_POLICY_PATH = REPO_ROOT / "config" / "roadmap_expansion_policy.json"
BASE_FORBIDDEN_PATTERNS = [
    r"\b_write_json\b",
    r"\bjson\.dump\w*\(",
    r"def\s+\w*(write|emit|persist|artifact)\w*\s*\(",
    r"\"status\"\s*:\s*\"pass\"",
    r"artifact[-_ ]only",
    r"direct static payload",
]

APPROVED_TEST_PREFIXES = ("pytest tests/", "python -m pytest tests/")
REJECTED_TEST_PATTERNS = [
    re.compile(r"\bpython\s+-c\b"),
    re.compile(r"\bpython\s+<<"),
    re.compile(r"\btest\s+-f\b"),
    re.compile(r"\bPath\([^)]*\)\.is_file\("),
]

CRITICAL_FAILURE_CATEGORIES = [
    "contract_validation",
    "dependency_validation",
    "ownership_validation",
    "forbidden_pattern_validation",
    "runtime_entrypoint_validation",
    "behavioral_test_validation",
]


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _contract_path(contract_dir: Path, step_id: str) -> Path:
    return contract_dir / f"{step_id}.json"


def _load_expansion_policy(policy_path: Path = DEFAULT_POLICY_PATH) -> dict[str, Any]:
    if not policy_path.is_file():
        raise FileNotFoundError(f"missing expansion policy: {policy_path}")
    return _load_json(policy_path)


def _validate_contract_semantics(contract: dict[str, Any]) -> None:
    def _require_non_empty_list(key: str) -> None:
        value = contract.get(key)
        if not isinstance(value, list) or len(value) == 0:
            raise ValueError(f"contract field must be non-empty list: {key}")

    _require_non_empty_list("target_modules")
    _require_non_empty_list("acceptance_checks")

    if contract.get("realization_mode") == "runtime_realization":
        _require_non_empty_list("target_tests")
        _require_non_empty_list("runtime_entrypoints")


def _load_contract(contract_dir: Path, step_id: str) -> dict[str, Any]:
    path = _contract_path(contract_dir, step_id)
    if not path.is_file():
        raise FileNotFoundError(f"missing step contract: {path}")
    contract = _load_json(path)
    validate_artifact(contract, "roadmap_step_contract")
    _validate_contract_semantics(contract)
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
            except Exception as exc:  # pragma: no cover
                ok = False
                error = str(exc)
        checks.append({"entrypoint": entry, "exists": ok, "error": error})
    return checks


def _scan_forbidden_patterns(contract: dict[str, Any], repo_root: Path) -> list[dict[str, Any]]:
    caller_patterns = [re.escape(pattern) for pattern in contract["forbidden_patterns"]]
    patterns = [re.compile(pattern, flags=re.IGNORECASE | re.MULTILINE) for pattern in sorted(set(BASE_FORBIDDEN_PATTERNS + caller_patterns))]

    scoped_files = sorted(set(contract["target_modules"]))

    hits: list[dict[str, Any]] = []
    for rel_path in scoped_files:
        path = repo_root / rel_path
        if not path.is_file():
            raise FileNotFoundError(f"missing target module path: {path}")
        text = path.read_text(encoding="utf-8")
        for pattern in patterns:
            if pattern.search(text):
                hits.append({"step_id": contract["step_id"], "path": rel_path, "pattern": pattern.pattern})

    return hits


def _validate_behavioral_test_commands(test_commands: list[str]) -> tuple[bool, list[dict[str, Any]]]:
    checks: list[dict[str, Any]] = []
    approved_count = 0
    for command in test_commands:
        approved_prefix = any(command.startswith(prefix) for prefix in APPROVED_TEST_PREFIXES)
        rejected_reason = ""
        for pattern in REJECTED_TEST_PATTERNS:
            if pattern.search(command):
                rejected_reason = f"rejected by policy pattern: {pattern.pattern}"
                break
        pytest_target_ok = "tests/" in command and ("-k" in command or "::" in command or "-q" in command)
        is_approved = approved_prefix and pytest_target_ok and rejected_reason == ""
        if is_approved:
            approved_count += 1
        checks.append(
            {
                "command": command,
                "approved": is_approved,
                "rejected_reason": rejected_reason,
                "approved_prefix": approved_prefix,
                "pytest_target_ok": pytest_target_ok,
            }
        )
    return approved_count > 0 and all(item["approved"] for item in checks), checks


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


def _validate_ownership_boundaries(contract: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    owner_defaults = policy.get("owner_defaults", {})
    owner = contract["owner"]
    owner_policy = owner_defaults.get(owner)
    if not owner_policy:
        return {"passed": False, "reason": f"owner missing from expansion policy: {owner}"}

    allowed_module_prefixes = tuple(owner_policy.get("allowed_module_prefixes", []))
    invalid_modules = [p for p in contract["target_modules"] if not p.startswith(allowed_module_prefixes)]

    allowed_test_prefixes = tuple(owner_policy.get("allowed_test_prefixes", []))
    invalid_tests: list[str] = []
    for cmd in contract["target_tests"]:
        if "tests/" not in cmd:
            invalid_tests.append(cmd)
            continue
        tokens = shlex.split(cmd)
        test_tokens = [tok for tok in tokens if tok.startswith("tests/")]
        if not test_tokens:
            invalid_tests.append(cmd)
            continue
        if not all(tok.startswith(allowed_test_prefixes) for tok in test_tokens):
            invalid_tests.append(cmd)

    passed = len(invalid_modules) == 0 and len(invalid_tests) == 0
    return {
        "passed": passed,
        "invalid_modules": invalid_modules,
        "invalid_tests": invalid_tests,
        "allowed_module_prefixes": list(allowed_module_prefixes),
        "allowed_test_prefixes": list(allowed_test_prefixes),
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

    policy = _load_expansion_policy()
    contracts: dict[str, dict[str, Any]] = {}
    contract_validation_failures: dict[str, str] = {}
    for step_id in step_ids:
        try:
            contract = _load_contract(contract_dir, step_id)
            _validate_expansion_trace(contract, repo_root)
            contract["_authoritative_status"] = authoritative_start_status(contract["realization_status"])
            contracts[step_id] = contract
        except Exception as exc:
            contract_validation_failures[step_id] = str(exc)

    status_by_step = dict(BASELINE_REALIZATION_STATUS)
    for step_id, contract in contracts.items():
        status_by_step[step_id] = contract["_authoritative_status"]

    attempted_steps: list[str] = []
    passed_steps: list[str] = []
    failed_steps: list[str] = sorted(set(contract_validation_failures.keys()))

    forbidden_pattern_hits: dict[str, list[dict[str, Any]]] = {}
    runtime_entrypoint_checks: dict[str, list[dict[str, Any]]] = {}
    behavioral_test_results: dict[str, list[dict[str, Any]]] = {}
    behavioral_test_policy_checks: dict[str, list[dict[str, Any]]] = {}
    ownership_checks: dict[str, dict[str, Any]] = {}
    dependency_failures: dict[str, str] = {}
    status_updates: list[dict[str, str]] = []

    critical_failures: dict[str, dict[str, bool]] = {
        step_id: {category: False for category in CRITICAL_FAILURE_CATEGORIES} for step_id in step_ids
    }
    for step_id in contract_validation_failures:
        critical_failures[step_id]["contract_validation"] = True

    for step_id in step_ids:
        if step_id in contract_validation_failures:
            continue
        contract = contracts[step_id]
        attempted_steps.append(step_id)

        dependency_passed = True
        try:
            enforce_realization_dependencies(
                step_id=step_id,
                depends_on=contract["depends_on"],
                attempted_steps=attempted_steps,
                status_by_step=status_by_step,
            )
        except RoadmapRealizationRuntimeError as exc:
            dependency_passed = False
            dependency_failures[step_id] = str(exc)
            critical_failures[step_id]["dependency_validation"] = True

        ownership = _validate_ownership_boundaries(contract, policy)
        ownership_checks[step_id] = ownership
        ownership_passed = ownership["passed"]
        if not ownership_passed:
            critical_failures[step_id]["ownership_validation"] = True
        if not dependency_passed or not ownership_passed:
            failed_steps.append(step_id)
            continue

        step_forbidden_hits = _scan_forbidden_patterns(contract, repo_root)
        forbidden_pattern_hits[step_id] = step_forbidden_hits
        forbidden_passed = len(step_forbidden_hits) == 0
        if not forbidden_passed:
            critical_failures[step_id]["forbidden_pattern_validation"] = True

        step_entrypoint_checks = _check_runtime_entrypoints(contract["runtime_entrypoints"])
        runtime_entrypoint_checks[step_id] = step_entrypoint_checks
        entrypoints_passed = all(item["exists"] for item in step_entrypoint_checks)
        if not entrypoints_passed:
            critical_failures[step_id]["runtime_entrypoint_validation"] = True

        test_policy_passed, test_policy_checks = _validate_behavioral_test_commands(contract["target_tests"])
        behavioral_test_policy_checks[step_id] = test_policy_checks
        behavioral_results: list[dict[str, Any]] = []
        if test_policy_passed:
            behavioral_results = _run_behavioral_tests(contract["target_tests"], repo_root)
        behavioral_test_results[step_id] = behavioral_results
        behavioral_passed = test_policy_passed and all(result["passed"] for result in behavioral_results)
        if not behavioral_passed:
            critical_failures[step_id]["behavioral_test_validation"] = True

        verification = _verification_checks(contract, repo_root)
        prior_status = status_by_step[step_id]
        next_status = next_realization_status(
            current_status=prior_status,
            dependency_checks_passed=dependency_passed,
            ownership_checks_passed=ownership_passed,
            forbidden_patterns_absent=forbidden_passed,
            runtime_entrypoints_exist=entrypoints_passed,
            behavioral_tests_passed=behavioral_passed,
            verification_checks_passed=verification["passed"],
        )

        step_failed = any(critical_failures[step_id].values()) or next_status not in {"runtime_realized", "verified"}
        if step_failed:
            failed_steps.append(step_id)
            continue

        if next_status != prior_status:
            contract["realization_status"] = next_status
            _write_json(_contract_path(contract_dir, step_id), contract)
            status_updates.append({"step_id": step_id, "from": prior_status, "to": next_status})
            status_by_step[step_id] = next_status

        # Verified transition requires a separate invocation after runtime realization.
        if next_status == "runtime_realized" and verification["passed"]:
            verified_status = next_realization_status(
                current_status=next_status,
                dependency_checks_passed=dependency_passed,
                ownership_checks_passed=ownership_passed,
                forbidden_patterns_absent=forbidden_passed,
                runtime_entrypoints_exist=entrypoints_passed,
                behavioral_tests_passed=behavioral_passed,
                verification_checks_passed=verification["passed"],
            )
            if verified_status != next_status:
                contract["realization_status"] = verified_status
                _write_json(_contract_path(contract_dir, step_id), contract)
                status_updates.append({"step_id": step_id, "from": next_status, "to": verified_status})
                status_by_step[step_id] = verified_status
                next_status = verified_status

        if next_status in {"runtime_realized", "verified"}:
            passed_steps.append(step_id)
        else:
            failed_steps.append(step_id)

    any_critical_failure = any(any(categories.values()) for categories in critical_failures.values())
    if any_critical_failure:
        passed_steps = [step for step in passed_steps if not any(critical_failures[step].values())]
        status_updates = []

    overall_status = "pass" if len(step_ids) > 0 and not any_critical_failure and len(failed_steps) == 0 else "fail"

    result = {
        "artifact_type": "roadmap_realization_result",
        "step_ids": step_ids,
        "attempted_steps": attempted_steps,
        "passed_steps": sorted(set(passed_steps)),
        "failed_steps": sorted(set(failed_steps)),
        "contract_validation_failures": contract_validation_failures,
        "dependency_failures": dependency_failures,
        "ownership_checks": ownership_checks,
        "forbidden_pattern_hits": forbidden_pattern_hits,
        "runtime_entrypoint_checks": runtime_entrypoint_checks,
        "behavioral_test_policy_checks": behavioral_test_policy_checks,
        "behavioral_test_results": behavioral_test_results,
        "critical_failures": critical_failures,
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
