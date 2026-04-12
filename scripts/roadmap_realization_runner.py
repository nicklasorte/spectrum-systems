#!/usr/bin/env python3
"""Thin roadmap realization runner for RF-02 and RF-03."""

from __future__ import annotations

import argparse
import ast
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
FORGED_REALIZATION_STATUSES = {"runtime_realized", "verified"}
NORMALIZED_FORBIDDEN_SIGNATURES = (
    "writejson",
    "jsondump",
    "statuspass",
    "artifactonly",
    "directstaticpayload",
)

APPROVED_TEST_PREFIXES = ("pytest tests/", "python -m pytest tests/")
APPROVED_PYTEST_TARGET_PATTERNS = (
    re.compile(r"^tests/test_[\w/.-]+\.py$"),
    re.compile(r"^tests/[\w./-]+::[\w.\[\]-]+$"),
)
REJECTED_TEST_PATTERNS = [
    re.compile(r"\bpython\s+-c\b"),
    re.compile(r"\bpython\s+<<"),
    re.compile(r"\btest\s+-f\b"),
    re.compile(r"\bPath\([^)]*\)\.is_file\("),
]
WEAK_TEST_PATTERNS = [
    re.compile(r"(?:string[_-]?match|regex|contains?)", flags=re.IGNORECASE),
    re.compile(r"\bsmoke\b", flags=re.IGNORECASE),
    re.compile(r"\b(?:exists?|is_file|is_dir|file[_-]?exists?)\b", flags=re.IGNORECASE),
    re.compile(r"\b(?:true|echo|printf)\b", flags=re.IGNORECASE),
    re.compile(r"\b(?:raise\s+SystemExit\(0\)|exit\s+0)\b", flags=re.IGNORECASE),
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
    regex_patterns = [
        re.compile(pattern, flags=re.IGNORECASE | re.MULTILINE) for pattern in sorted(set(BASE_FORBIDDEN_PATTERNS + caller_patterns))
    ]
    normalized_signatures = set(NORMALIZED_FORBIDDEN_SIGNATURES)
    normalized_signatures.update(_normalize_forbidden_text(pattern) for pattern in contract["forbidden_patterns"])
    normalized_signatures.discard("")

    scoped_files = _resolve_forbidden_scan_scope(contract=contract, repo_root=repo_root)

    hits: list[dict[str, Any]] = []
    for rel_path in scoped_files:
        path = repo_root / rel_path
        if not path.is_file():
            raise FileNotFoundError(f"missing target/helper module path: {path}")
        text = path.read_text(encoding="utf-8")
        normalized_text = _normalize_forbidden_text(text)
        for pattern in regex_patterns:
            if pattern.search(text):
                hits.append({"step_id": contract["step_id"], "path": rel_path, "pattern": pattern.pattern, "match_mode": "regex"})
        for signature in sorted(normalized_signatures):
            if signature and signature in normalized_text:
                hits.append(
                    {
                        "step_id": contract["step_id"],
                        "path": rel_path,
                        "pattern": signature,
                        "match_mode": "normalized_signature",
                    }
                )

    deduped_hits = {
        (item["step_id"], item["path"], item["pattern"], item["match_mode"]): item for item in hits
    }
    return list(deduped_hits.values())


def _normalize_forbidden_text(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", text.lower())


def _entrypoint_to_repo_path(entrypoint: str) -> str | None:
    module_name, sep, _symbol = entrypoint.partition(":")
    if not sep or not module_name.startswith("spectrum_systems."):
        return None
    return f"{module_name.replace('.', '/')}.py"


def _extract_local_import_paths(path: Path, repo_root: Path) -> set[str]:
    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text)
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                module_name = alias.name
                if module_name.startswith("spectrum_systems."):
                    imports.add(f"{module_name.replace('.', '/')}.py")
        elif isinstance(node, ast.ImportFrom):
            module_name = node.module or ""
            if module_name.startswith("spectrum_systems."):
                imports.add(f"{module_name.replace('.', '/')}.py")
    return {candidate for candidate in imports if (repo_root / candidate).is_file()}


def _resolve_forbidden_scan_scope(*, contract: dict[str, Any], repo_root: Path) -> list[str]:
    scoped_files: set[str] = set(contract["target_modules"])
    for entrypoint in contract["runtime_entrypoints"]:
        entrypoint_path = _entrypoint_to_repo_path(entrypoint)
        if entrypoint_path:
            scoped_files.add(entrypoint_path)

    helper_files: set[str] = set()
    for rel_path in sorted(scoped_files):
        path = repo_root / rel_path
        if not path.is_file():
            raise FileNotFoundError(f"missing target/helper module path: {path}")
        helper_files.update(_extract_local_import_paths(path, repo_root))

    scoped_files.update(helper_files)
    return sorted(scoped_files)


def _extract_pytest_targets(command: str) -> list[str]:
    tokens = shlex.split(command)
    return [token for token in tokens if token.startswith("tests/")]


def _command_has_weak_k_expression(command: str) -> bool:
    tokens = shlex.split(command)
    if "-k" not in tokens:
        return False
    k_index = tokens.index("-k")
    if k_index + 1 >= len(tokens):
        return True
    k_expr = tokens[k_index + 1]
    return bool(WEAK_TEST_PATTERNS[0].search(k_expr) or WEAK_TEST_PATTERNS[1].search(k_expr))


def _classify_behavioral_test_command(command: str) -> dict[str, Any]:
    approved_prefix = any(command.startswith(prefix) for prefix in APPROVED_TEST_PREFIXES)
    rejected_reason = ""
    for pattern in REJECTED_TEST_PATTERNS:
        if pattern.search(command):
            rejected_reason = f"rejected by policy pattern: {pattern.pattern}"
            break

    pytest_targets = _extract_pytest_targets(command)
    target_pattern_ok = bool(pytest_targets) and all(
        any(pattern.match(target) for pattern in APPROVED_PYTEST_TARGET_PATTERNS) for target in pytest_targets
    )
    has_selector = "-k" in shlex.split(command) or any("::" in target for target in pytest_targets)
    weak_reasons: list[str] = []
    for pattern in WEAK_TEST_PATTERNS:
        if pattern.search(command):
            weak_reasons.append(f"matched weak pattern: {pattern.pattern}")
    if _command_has_weak_k_expression(command):
        weak_reasons.append("weak pytest -k expression indicates non-behavioral string/smoke filtering")

    classification = "behavioral"
    approved = False
    if not approved_prefix or rejected_reason or not target_pattern_ok or not has_selector:
        classification = "invalid"
    elif weak_reasons:
        classification = "weak"
    else:
        approved = True

    return {
        "command": command,
        "classification": classification,
        "approved": approved,
        "approved_prefix": approved_prefix,
        "pytest_target_patterns_ok": target_pattern_ok,
        "has_selector": has_selector,
        "pytest_targets": pytest_targets,
        "rejected_reason": rejected_reason,
        "weak_reasons": weak_reasons,
    }


def _relevance_tokens_for_contract(contract: dict[str, Any]) -> dict[str, set[str]]:
    module_tokens: set[str] = set()
    entrypoint_tokens: set[str] = set()
    acceptance_tokens: set[str] = set()
    for module_path in contract["target_modules"]:
        stem = Path(module_path).stem
        normalized = stem.lower()
        module_tokens.add(normalized)
        if normalized.endswith("_runtime"):
            module_tokens.add(normalized[: -len("_runtime")])
    for entrypoint in contract["runtime_entrypoints"]:
        module_name, _, symbol = entrypoint.partition(":")
        module_leaf = module_name.split(".")[-1].lower()
        entrypoint_tokens.add(module_leaf)
        if module_leaf.endswith("_runtime"):
            entrypoint_tokens.add(module_leaf[: -len("_runtime")])
        entrypoint_tokens.add(symbol.lower())
    for check in contract["acceptance_checks"]:
        check_id = str(check.get("check_id", "")).lower()
        acceptance_tokens.add(check_id)
        acceptance_tokens.update(piece for piece in check_id.split("_") if len(piece) > 3)
    return {
        "module_tokens": module_tokens,
        "entrypoint_tokens": entrypoint_tokens,
        "acceptance_tokens": acceptance_tokens,
    }


def _validate_behavioral_test_integrity(contract: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    classifications = [_classify_behavioral_test_command(command) for command in contract["target_tests"]]
    behavioral_commands = [item for item in classifications if item["classification"] == "behavioral"]
    weak_commands = [item for item in classifications if item["classification"] == "weak"]
    invalid_commands = [item for item in classifications if item["classification"] == "invalid"]

    tokens = _relevance_tokens_for_contract(contract)
    relevant_behavioral: list[dict[str, Any]] = []
    entrypoint_covered = False
    acceptance_covered = False
    for command in behavioral_commands:
        target_surface = " ".join(command.get("pytest_targets", [])).lower()
        module_match = any(token and token in target_surface for token in tokens["module_tokens"])
        entrypoint_match = any(token and token in target_surface for token in tokens["entrypoint_tokens"])
        acceptance_match = any(token and token in target_surface for token in tokens["acceptance_tokens"])
        command["coverage"] = {
            "module_match": module_match,
            "entrypoint_match": entrypoint_match,
            "acceptance_match": acceptance_match,
        }
        if module_match or entrypoint_match or acceptance_match:
            relevant_behavioral.append(command)
        entrypoint_covered = entrypoint_covered or entrypoint_match
        acceptance_covered = acceptance_covered or acceptance_match

    failure_reasons: list[str] = []
    if not behavioral_commands:
        failure_reasons.append("zero behavioral tests declared")
    if weak_commands:
        failure_reasons.append("weak test command(s) declared; ambiguous behavioral proof rejected")
    if invalid_commands:
        failure_reasons.append("invalid test command(s) declared")
    if weak_commands and not behavioral_commands:
        failure_reasons.append("weak-only proof set rejected")
    if behavioral_commands and not relevant_behavioral:
        failure_reasons.append("behavioral tests do not cover target modules/runtime entrypoints/acceptance checks")

    runtime_realization_passed = not failure_reasons
    verified_strict_passed = runtime_realization_passed and entrypoint_covered and acceptance_covered
    if runtime_realization_passed and not verified_strict_passed:
        failure_reasons.append("verified proof requires behavioral coverage for both runtime entrypoints and acceptance checks")

    return runtime_realization_passed, {
        "commands": classifications,
        "behavioral_count": len(behavioral_commands),
        "weak_count": len(weak_commands),
        "invalid_count": len(invalid_commands),
        "relevant_behavioral_count": len(relevant_behavioral),
        "entrypoint_coverage_met": entrypoint_covered,
        "acceptance_coverage_met": acceptance_covered,
        "runtime_realization_passed": runtime_realization_passed,
        "verified_strict_passed": verified_strict_passed,
        "failure_reasons": failure_reasons,
    }


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
    forged_status_failures: dict[str, str] = {}
    for step_id in step_ids:
        try:
            contract = _load_contract(contract_dir, step_id)
            _validate_expansion_trace(contract, repo_root)
            incoming_status = contract["realization_status"]
            if incoming_status in FORGED_REALIZATION_STATUSES:
                raise RoadmapRealizationRuntimeError(
                    "incoming realization_status is forged for standard realization execution "
                    f"({incoming_status}); authoritative prior-run verification artifact required"
                )
            contract["_authoritative_status"] = authoritative_start_status(contract["realization_status"])
            contracts[step_id] = contract
        except Exception as exc:
            contract_validation_failures[step_id] = str(exc)
            if "incoming realization_status is forged" in str(exc):
                forged_status_failures[step_id] = str(exc)

    status_by_step = dict(BASELINE_REALIZATION_STATUS)
    for step_id, contract in contracts.items():
        status_by_step[step_id] = contract["_authoritative_status"]

    attempted_steps: list[str] = []
    passed_steps: list[str] = []
    failed_steps: list[str] = sorted(set(contract_validation_failures.keys()))

    forbidden_pattern_hits: dict[str, list[dict[str, Any]]] = {}
    runtime_entrypoint_checks: dict[str, list[dict[str, Any]]] = {}
    behavioral_test_results: dict[str, list[dict[str, Any]]] = {}
    behavioral_test_policy_checks: dict[str, dict[str, Any]] = {}
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

        test_policy_passed, test_policy_checks = _validate_behavioral_test_integrity(contract)
        behavioral_test_policy_checks[step_id] = test_policy_checks
        behavioral_results: list[dict[str, Any]] = []
        if test_policy_passed:
            approved_commands = [item["command"] for item in test_policy_checks["commands"] if item["classification"] == "behavioral"]
            behavioral_results = _run_behavioral_tests(approved_commands, repo_root)
        behavioral_test_results[step_id] = behavioral_results
        behavioral_passed = test_policy_passed and all(result["passed"] for result in behavioral_results)
        if not behavioral_passed:
            critical_failures[step_id]["behavioral_test_validation"] = True

        verification = _verification_checks(contract, repo_root)
        verification["passed"] = verification["passed"] and test_policy_checks["verified_strict_passed"]
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
    invocation_dependency_blocked = len(dependency_failures) > 0 and len(step_ids) > 1
    if any_critical_failure or invocation_dependency_blocked:
        if invocation_dependency_blocked:
            for step_id in attempted_steps:
                critical_failures[step_id]["dependency_validation"] = True
        passed_steps = []
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
        "forged_status_failures": forged_status_failures,
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
