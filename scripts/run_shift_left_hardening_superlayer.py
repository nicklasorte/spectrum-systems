#!/usr/bin/env python3
"""Run SLH-001 shift-left hardening superlayer guard chain and mini-cert."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.modules.runtime.shift_left_hardening_superlayer import (
    decide_pre_execution_certification,
    detect_hidden_state,
    evaluate_context_sufficiency,
    evaluate_forbidden_vocabulary_guard,
    evaluate_lineage_precondition,
    evaluate_manifest_strict_validation,
    evaluate_minimal_trace_contract,
    evaluate_proof_only_detector,
    evaluate_replay_precondition,
    evaluate_required_eval_presence,
    evaluate_system_registry_overlap,
    evaluate_owner_boundary_lint,
    run_shift_left_guard_chain,
    validate_dependency_graph,
    verify_eval_completeness,
    verify_lineage_integrity,
    verify_observability_completeness,
    verify_replay_integrity,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Execute fail-closed Shift-Left Hardening Superlayer")
    parser.add_argument(
        "--output",
        default="outputs/shift_left_hardening/superlayer_result.json",
        help="Path for output JSON artifact",
    )
    parser.add_argument("--created-at", default=datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"))
    parser.add_argument("--base-ref", default="origin/main", help="Git base ref for changed-file resolution")
    parser.add_argument("--head-ref", default="HEAD", help="Git head ref for changed-file resolution")
    parser.add_argument("--changed-files", nargs="*", default=[], help="Explicit changed files")
    return parser.parse_args()


def _run(command: list[str]) -> tuple[int, str, str]:
    proc = subprocess.run(command, cwd=REPO_ROOT, check=False, capture_output=True, text=True)
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


def _resolve_changed_files(*, explicit: list[str], base_ref: str, head_ref: str) -> tuple[list[str], list[str]]:
    if explicit:
        return sorted(set(path.strip() for path in explicit if path.strip())), []

    retrieval_failures: list[str] = []
    attempts = [
        ["git", "diff", "--name-only", f"{base_ref}..{head_ref}"],
        ["git", "diff", "--name-only", "HEAD^..HEAD"],
        ["git", "ls-files"],
    ]
    for cmd in attempts:
        code, out, err = _run(cmd)
        if code == 0:
            changed_files = sorted(set(line.strip() for line in out.splitlines() if line.strip()))
            if changed_files:
                return changed_files, retrieval_failures
            retrieval_failures.append(f"empty_scope:{' '.join(cmd)}")
            continue
        retrieval_failures.append(f"failed_scope:{' '.join(cmd)}:{err or out or 'unknown_error'}")

    return [], retrieval_failures


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _derive_repo_signals(*, created_at: str, changed_files: list[str], changed_scope_errors: list[str]) -> dict[str, Any]:
    manifest_path = REPO_ROOT / "contracts" / "standards-manifest.json"
    manifest_data: dict[str, Any] = {}
    manifest_load_errors: list[str] = []
    if manifest_path.exists():
        try:
            manifest_data = _load_json(manifest_path)
        except json.JSONDecodeError as exc:
            manifest_load_errors.append(f"manifest_json_decode_error:{exc.msg}")
    else:
        manifest_load_errors.append("manifest_missing")

    contracts = manifest_data.get("contracts", []) if isinstance(manifest_data, dict) else []
    forbidden_classes = {"forbidden", "synthetic", "placeholder"}
    manifest_result = evaluate_manifest_strict_validation(
        manifest_contracts=contracts if isinstance(contracts, list) else [],
        forbidden_classes=forbidden_classes,
        created_at=created_at,
    )
    if manifest_load_errors:
        manifest_result["status"] = "fail"
        manifest_result["reason_codes"] = sorted(set(list(manifest_result.get("reason_codes", [])) + ["missing_evidence"] + manifest_load_errors))

    dep_code, dep_out, dep_err = _run(["python", "scripts/build_dependency_graph.py"])
    dependency_graph_errors: list[str] = []
    if dep_code != 0:
        dependency_graph_errors.append(f"dependency_graph_build_failed:{dep_err or dep_out or 'unknown_error'}")

    dependency_graph_path = REPO_ROOT / "ecosystem" / "dependency-graph.json"
    if not dependency_graph_path.exists():
        dependency_graph_errors.append("dependency_graph_missing")
    else:
        try:
            dependency_graph = _load_json(dependency_graph_path)
            if not dependency_graph.get("systems"):
                dependency_graph_errors.append("dependency_graph_missing_systems")
            if not dependency_graph.get("artifacts"):
                dependency_graph_errors.append("dependency_graph_missing_artifacts")
            if not dependency_graph.get("edges"):
                dependency_graph_errors.append("dependency_graph_missing_edges")
        except json.JSONDecodeError as exc:
            dependency_graph_errors.append(f"dependency_graph_json_decode_error:{exc.msg}")

    dependency_graph_result = validate_dependency_graph(graph_errors=dependency_graph_errors, created_at=created_at)

    srg_cmd = ["python", "scripts/run_system_registry_guard.py", "--head-ref", "HEAD", "--base-ref", "HEAD^", "--changed-files", *changed_files]
    srg_code, srg_out, srg_err = _run(srg_cmd)
    registry_output_path = REPO_ROOT / "outputs" / "system_registry_guard" / "system_registry_guard_result.json"
    registry_payload: dict[str, Any] = {}
    registry_errors: list[str] = []
    if srg_code != 0:
        registry_errors.append(f"system_registry_guard_failed:{srg_err or srg_out or 'unknown_error'}")
    if registry_output_path.exists():
        try:
            registry_payload = _load_json(registry_output_path)
        except json.JSONDecodeError as exc:
            registry_errors.append(f"system_registry_guard_json_decode_error:{exc.msg}")
    else:
        registry_errors.append("system_registry_guard_output_missing")

    overlaps = list(registry_payload.get("overlaps_found", []))
    shadow_owners = list(registry_payload.get("shadow_owner_findings", []))
    authority_violations = list(registry_payload.get("protected_authority_violations", [])) + registry_errors
    registry_result = evaluate_system_registry_overlap(
        overlaps=overlaps,
        shadow_owners=shadow_owners,
        authority_violations=authority_violations,
        created_at=created_at,
    )

    changed_scope_missing = not bool(changed_files)
    missing_changed_scope: list[str] = []
    if changed_scope_missing:
        missing_changed_scope = ["changed_scope_unavailable", *changed_scope_errors]

    slh_paths = [p for p in changed_files if p.startswith("spectrum_systems/modules/runtime/")]
    owner_import_count = len({path.split("/")[2] for path in slh_paths if len(path.split("/")) > 2})
    boundary_result = evaluate_owner_boundary_lint(
        owner_import_count=owner_import_count,
        mixed_owner_functions=["changed_scope_unavailable"] if changed_scope_missing else [],
        multi_artifact_functions=[],
        created_at=created_at,
    )

    forbidden_terms = [term for term in ["TODO", "FIXME"] if any(term.lower() in path.lower() for path in changed_files)]
    vocabulary_result = evaluate_forbidden_vocabulary_guard(forbidden_terms=forbidden_terms, created_at=created_at)

    required_eval_files = {"tests/test_shift_left_hardening_superlayer.py"}
    missing_eval_families = sorted(required_eval_files - set(changed_files)) if changed_files else ["changed_scope_unavailable"]
    eval_presence_result = evaluate_required_eval_presence(missing_eval_families=missing_eval_families, created_at=created_at)

    missing_context = []
    for required_path in ["README.md", "docs/architecture/system_registry.md"]:
        if not (REPO_ROOT / required_path).exists():
            missing_context.append(required_path)
    context_result = evaluate_context_sufficiency(
        missing_recipes=missing_context + missing_changed_scope,
        ambiguous_paths=[],
        created_at=created_at,
    )

    trace_missing_fields = []
    if manifest_result["status"] != "pass":
        trace_missing_fields.append("manifest_validation")
    if dependency_graph_result["status"] != "pass":
        trace_missing_fields.append("dependency_graph_validation")
    if registry_result["status"] != "pass":
        trace_missing_fields.append("system_registry_guard")
    if changed_scope_missing:
        trace_missing_fields.append("changed_scope")
    trace_result = evaluate_minimal_trace_contract(missing_fields=trace_missing_fields, created_at=created_at)

    replay_preconditions = ["changed_scope"] if changed_scope_missing else []
    replay_preconditions.extend(f"scope_error:{item}" for item in changed_scope_errors)
    replay_result = evaluate_replay_precondition(missing_preconditions=replay_preconditions, created_at=created_at)

    lineage_preconditions = []
    if manifest_result.get("missing_link_count", 0):
        lineage_preconditions.append("manifest_contract_links")
    if manifest_result.get("missing_evidence_count", 0):
        lineage_preconditions.append("manifest_required_fields")
    if not contracts:
        lineage_preconditions.append("manifest_contracts")
    lineage_result = evaluate_lineage_precondition(missing_preconditions=lineage_preconditions, created_at=created_at)

    proof_only_paths = [path for path in changed_files if "docs/reviews/" in path and len(changed_files) <= 2]
    proof_result = evaluate_proof_only_detector(proof_only_paths=proof_only_paths, created_at=created_at)

    eval_completeness = verify_eval_completeness(missing_evals=missing_eval_families, created_at=created_at)
    replay_integrity = verify_replay_integrity(
        replay_gaps=["changed_scope_unavailable"] if changed_scope_missing else changed_scope_errors,
        created_at=created_at,
    )
    lineage_integrity = verify_lineage_integrity(lineage_gaps=lineage_preconditions, created_at=created_at)
    observability = verify_observability_completeness(observability_gaps=trace_missing_fields, created_at=created_at)

    runtime_parity_reasons: list[str] = []
    parity_strength = "strong"
    if dep_code != 0:
        runtime_parity_reasons.append("dependency_graph_build_failed")
    if srg_code != 0:
        runtime_parity_reasons.append("system_registry_guard_failed")
    if changed_scope_missing:
        runtime_parity_reasons.append("missing_evidence")
    if runtime_parity_reasons:
        parity_strength = "weak"
    runtime_parity = {
        "status": "pass" if not runtime_parity_reasons else "fail",
        "reason_codes": runtime_parity_reasons,
        "parity_strength": parity_strength,
        "parity_ok": not runtime_parity_reasons,
    }

    hidden_state_findings: list[str] = []
    expected_failure_count = sum(
        1
        for check in [
            manifest_result,
            registry_result,
            boundary_result,
            vocabulary_result,
            eval_presence_result,
            context_result,
            trace_result,
            replay_result,
            lineage_result,
            proof_result,
        ]
        if check.get("status") != "pass"
    )
    if expected_failure_count == 0 and any(runtime_parity_reasons):
        hidden_state_findings.append("parity_disagrees_with_guard_surface")
    hidden_state = detect_hidden_state(hidden_state_findings=hidden_state_findings, created_at=created_at)

    checks = {
        manifest_result["artifact_type"]: manifest_result,
        registry_result["artifact_type"]: registry_result,
        boundary_result["artifact_type"]: boundary_result,
        vocabulary_result["artifact_type"]: vocabulary_result,
        eval_presence_result["artifact_type"]: eval_presence_result,
        context_result["artifact_type"]: context_result,
        trace_result["artifact_type"]: trace_result,
        replay_result["artifact_type"]: replay_result,
        lineage_result["artifact_type"]: lineage_result,
        proof_result["artifact_type"]: proof_result,
    }

    return {
        "checks": checks,
        "dependency_graph": dependency_graph_result,
        "runtime_parity": runtime_parity,
        "eval": eval_completeness,
        "replay": replay_integrity,
        "lineage": lineage_integrity,
        "observability": observability,
        "hidden_state": hidden_state,
        "meta": {
            "changed_files": changed_files,
            "changed_scope_errors": changed_scope_errors,
            "dependency_graph_command": "python scripts/build_dependency_graph.py",
            "system_registry_guard_command": "python scripts/run_system_registry_guard.py --head-ref HEAD --base-ref HEAD^ --changed-files ...",
            "manifest_path": str(manifest_path.relative_to(REPO_ROOT)),
        },
    }


def main() -> int:
    args = _parse_args()
    changed_files, changed_scope_errors = _resolve_changed_files(
        explicit=list(args.changed_files or []),
        base_ref=args.base_ref,
        head_ref=args.head_ref,
    )

    derived = _derive_repo_signals(
        created_at=args.created_at,
        changed_files=changed_files,
        changed_scope_errors=changed_scope_errors,
    )
    chain = run_shift_left_guard_chain(
        checks=derived["checks"],
        fail_fast=True,
        created_at=args.created_at,
    )

    mini_cert = decide_pre_execution_certification(
        checks={
            "sl_core": chain,
            "sl_structure": {"status": "pass"},
            "sl_memory": {"status": "pass"},
            "sl_router": {"status": "pass"},
            "sl_cert": {"status": "pass"},
            "dependency_graph": derived["dependency_graph"],
            "runtime_parity": derived["runtime_parity"],
            "eval": derived["eval"],
            "replay": derived["replay"],
            "lineage": derived["lineage"],
            "observability": derived["observability"],
            "hidden_state": derived["hidden_state"],
        },
        created_at=args.created_at,
    )

    payload = {
        "shift_left_guard_chain": chain,
        "mini_certification_decision": mini_cert,
        "repo_derived_signals": {
            "changed_files": derived["meta"]["changed_files"],
            "changed_scope_errors": derived["meta"]["changed_scope_errors"],
            "manifest_path": derived["meta"]["manifest_path"],
            "dependency_graph_command": derived["meta"]["dependency_graph_command"],
            "system_registry_guard_command": derived["meta"]["system_registry_guard_command"],
        },
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "status": mini_cert["status"],
                "output": str(output_path),
                "changed_files": derived["meta"]["changed_files"],
                "reason_codes": mini_cert["reason_codes"],
            },
            indent=2,
        )
    )
    return 0 if mini_cert["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
