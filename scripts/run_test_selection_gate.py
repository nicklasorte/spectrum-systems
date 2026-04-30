"""
Test Selection Gate runner — Gate 2 of 4.

Validates that the set of tests selected for this PR is non-empty, properly derived,
and passes integrity checks. Invokes the fallback smoke baseline when selection is
weak or absent for a governed surface.

Fail-closed: empty selection against a governed surface always blocks.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


_GATE_NAME = "test_selection_gate"
_SCHEMA_VERSION = "1.0.0"
_CANONICAL_EXECUTION_RECORD = "outputs/contract_preflight/pytest_execution_record.json"
_CANONICAL_SELECTION_RECORD = "outputs/contract_preflight/pytest_selection_integrity_result.json"
_CANONICAL_PREFLIGHT_ARTIFACT = "outputs/contract_preflight/contract_preflight_result_artifact.json"
_SELECTION_POLICY_PATH = "docs/governance/pytest_pr_selection_integrity_policy.json"
_SMOKE_BASELINE_PATH = "docs/governance/pytest_pr_inventory_baseline.json"


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _build_result(status: str, details: dict, failure_summary: dict | None) -> dict:
    payload: dict = {
        "artifact_type": "test_selection_gate_result",
        "schema_version": _SCHEMA_VERSION,
        "gate_name": _GATE_NAME,
        "status": status,
        "produced_at": datetime.now(timezone.utc).isoformat(),
        "producer_script": "scripts/run_test_selection_gate.py",
        **details,
    }
    if failure_summary:
        payload["failure_summary"] = failure_summary
    text = json.dumps(payload, sort_keys=True, indent=2)
    payload["artifact_hash"] = _sha256(text)
    return payload


def _write_result(result: dict, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / "test_selection_gate_result.json"
    out_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"[test_selection_gate] result written to {out_path}")


def _fail_closed(reason: str, root_cause: str, next_action: str,
                 affected_files: list[str], artifact_refs: list[str],
                 output_dir: Path) -> None:
    failure_summary = {
        "gate_name": _GATE_NAME,
        "failure_class": "selection_gate_failure",
        "root_cause": root_cause,
        "blocking_reason": reason,
        "next_action": next_action,
        "affected_files": affected_files,
        "failed_command": "scripts/run_test_selection_gate.py",
        "artifact_refs": artifact_refs,
    }
    result = _build_result("block", {}, failure_summary)
    _write_result(result, output_dir)
    print(f"[test_selection_gate] BLOCK: {reason}", file=sys.stderr)
    sys.exit(1)


def _load_json_file(path: Path, label: str, output_dir: Path) -> dict:
    if not path.is_file():
        _fail_closed(
            f"missing required artifact: {path}",
            f"{label} not found at {path}",
            f"Ensure the Contract Gate ran successfully before the Test Selection Gate",
            [],
            [str(path)],
            output_dir,
        )
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        _fail_closed(
            f"invalid JSON in {path}",
            f"{label} contains invalid JSON: {e}",
            f"Fix or regenerate {path}",
            [],
            [str(path)],
            output_dir,
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Test Selection Gate runner")
    parser.add_argument("--output-dir", default="outputs/gates")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--event-name", default="pull_request")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    repo_root = Path(args.repo_root)
    details: dict = {"event_name": args.event_name}

    # Load upstream artifacts
    preflight_artifact = _load_json_file(
        repo_root / _CANONICAL_PREFLIGHT_ARTIFACT, "contract_preflight_result_artifact", output_dir
    )
    execution_record = _load_json_file(
        repo_root / _CANONICAL_EXECUTION_RECORD, "pytest_execution_record", output_dir
    )
    selection_record = _load_json_file(
        repo_root / _CANONICAL_SELECTION_RECORD, "pytest_selection_integrity_result", output_dir
    )

    # Load selection policy
    policy_path = repo_root / _SELECTION_POLICY_PATH
    policy = _load_json_file(policy_path, "pytest_pr_selection_integrity_policy", output_dir)
    minimum_threshold = int(policy.get("minimum_selection_threshold") or 1)

    # Extract selected targets
    selected_targets: list[str] = execution_record.get("selected_targets") or []
    selection_integrity_decision = str(
        selection_record.get("selection_integrity_decision") or "BLOCK"
    )
    executed = bool(execution_record.get("executed", False))

    # Provenance validation
    required_provenance = [
        "source_commit_sha", "source_head_ref", "workflow_run_id",
        "producer_script", "produced_at", "artifact_hash",
    ]
    missing_prov = [f for f in required_provenance if not str(execution_record.get(f) or "").strip()]
    if missing_prov:
        _fail_closed(
            f"missing provenance fields in execution record: {missing_prov}",
            f"pytest_execution_record missing: {missing_prov}",
            "Ensure run_contract_preflight.py writes all provenance fields",
            [],
            [_CANONICAL_EXECUTION_RECORD],
            output_dir,
        )

    selection_provenance = required_provenance + [
        "source_pytest_execution_record_ref",
        "source_pytest_execution_record_hash",
    ]
    missing_sel_prov = [f for f in selection_provenance if not str(selection_record.get(f) or "").strip()]
    if missing_sel_prov:
        _fail_closed(
            f"missing provenance in selection integrity result: {missing_sel_prov}",
            f"pytest_selection_integrity_result missing: {missing_sel_prov}",
            "Ensure run_contract_preflight.py writes all selection provenance fields",
            [],
            [_CANONICAL_SELECTION_RECORD],
            output_dir,
        )

    # Cross-record consistency checks
    exec_sha = str(execution_record.get("source_commit_sha") or "")
    sel_sha = str(selection_record.get("source_commit_sha") or "")
    if exec_sha and sel_sha and exec_sha != sel_sha:
        _fail_closed(
            "selection provenance commit mismatch",
            f"execution_record.source_commit_sha={exec_sha} != selection_record.source_commit_sha={sel_sha}",
            "Ensure selection and execution records are from the same commit",
            [],
            [_CANONICAL_EXECUTION_RECORD, _CANONICAL_SELECTION_RECORD],
            output_dir,
        )

    exec_hash = str(execution_record.get("artifact_hash") or "")
    sel_exec_hash = str(selection_record.get("source_pytest_execution_record_hash") or "")
    if exec_hash and sel_exec_hash and exec_hash != sel_exec_hash:
        _fail_closed(
            "selection provenance hash mismatch",
            f"execution_record.artifact_hash != selection_record.source_pytest_execution_record_hash",
            "Ensure selection record references the same execution record produced this run",
            [],
            [_CANONICAL_EXECUTION_RECORD, _CANONICAL_SELECTION_RECORD],
            output_dir,
        )

    # Integrity decision check
    if selection_integrity_decision != "ALLOW":
        _fail_closed(
            f"selection integrity decision={selection_integrity_decision}",
            f"pytest_selection_integrity_result.selection_integrity_decision={selection_integrity_decision}",
            "Review selection integrity result for blocking reason",
            [],
            [_CANONICAL_SELECTION_RECORD],
            output_dir,
        )

    # Empty selection check — never pass-equivalent for governed surfaces
    fallback_invoked = False
    if len(selected_targets) < minimum_threshold:
        # Try fallback smoke baseline
        baseline_path = repo_root / _SMOKE_BASELINE_PATH
        if baseline_path.is_file():
            try:
                baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError) as exc:
                _fail_closed(
                    "smoke baseline JSON is malformed or unreadable",
                    str(exc),
                    f"Fix or regenerate {_SMOKE_BASELINE_PATH}",
                    [str(baseline_path)],
                    [str(baseline_path)],
                    output_dir,
                )
            fallback_targets = baseline.get("suite_targets") or []
            if fallback_targets:
                print(f"[test_selection_gate] Selection below threshold ({len(selected_targets)} < {minimum_threshold}); invoking smoke fallback baseline")
                selected_targets = fallback_targets
                fallback_invoked = True
            else:
                _fail_closed(
                    "empty selection and fallback baseline is also empty",
                    "No tests selected and smoke baseline has no targets",
                    "Add tests to pytest_pr_inventory_baseline.json suite_targets",
                    [],
                    [_SMOKE_BASELINE_PATH],
                    output_dir,
                )
        else:
            _fail_closed(
                f"empty selection and no fallback baseline at {_SMOKE_BASELINE_PATH}",
                "No tests selected for PR and smoke baseline is missing",
                f"Create {_SMOKE_BASELINE_PATH} with fallback suite targets",
                [],
                [_SMOKE_BASELINE_PATH],
                output_dir,
            )

    details.update({
        "selected_targets": selected_targets,
        "target_count": len(selected_targets),
        "selection_integrity_decision": selection_integrity_decision,
        "fallback_invoked": fallback_invoked,
        "executed": executed,
        "minimum_selection_threshold": minimum_threshold,
        "execution_record_ref": _CANONICAL_EXECUTION_RECORD,
        "selection_record_ref": _CANONICAL_SELECTION_RECORD,
    })

    result = _build_result("allow", details, None)
    _write_result(result, output_dir)
    print(f"[test_selection_gate] ALLOW — {len(selected_targets)} targets selected, fallback={fallback_invoked}")


if __name__ == "__main__":
    main()
