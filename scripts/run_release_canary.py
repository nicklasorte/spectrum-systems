#!/usr/bin/env python3
"""Run deterministic baseline-vs-candidate release canary evaluation (SF-14)."""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.run_eval_coverage_report import build_eval_coverage  # noqa: E402
from spectrum_systems.modules.evaluation.eval_engine import run_eval_run  # noqa: E402
from spectrum_systems.modules.runtime.release_canary import (  # noqa: E402
    ReleaseInputVersions,
    build_release_record,
    decision_exit_code,
)

_DEFAULT_OUTPUT_DIR = _REPO_ROOT / "outputs" / "release_canary"
_DEFAULT_RELEASE_POLICY = _REPO_ROOT / "data" / "policy" / "eval_release_policy.json"
_DEFAULT_COVERAGE_POLICY = _REPO_ROOT / "data" / "policy" / "eval_coverage_policy.json"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_json_many(path: Path) -> list[dict[str, Any]]:
    payload = _load_json(path)
    if isinstance(payload, dict):
        return [payload]
    if isinstance(payload, list):
        if all(isinstance(item, dict) for item in payload):
            return payload
    raise ValueError(f"{path}: expected JSON object or array of objects")


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _ref_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(_REPO_ROOT))
    except ValueError:
        return str(path)


def _run_eval_bundle(eval_run_path: Path, eval_cases_path: Path) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    eval_run = _load_json(eval_run_path)
    eval_cases = _load_json_many(eval_cases_path)
    execution = run_eval_run(eval_run, eval_cases)
    eval_results = execution["eval_results"]
    eval_summary = execution["eval_summary"]
    return eval_run, eval_cases, eval_results, eval_summary


def _build_coverage(
    *,
    eval_cases: list[dict[str, Any]],
    eval_results: list[dict[str, Any]],
    datasets: list[dict[str, Any]],
    policy: dict[str, Any],
    coverage_run_id: str,
    timestamp: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    coverage, slices, _ = build_eval_coverage(
        eval_cases=eval_cases,
        eval_results=eval_results,
        datasets=datasets,
        policy=policy,
        coverage_run_id=coverage_run_id,
        timestamp=timestamp,
    )
    return coverage, slices


def _build_fail_closed_record(
    *,
    release_id: str,
    timestamp: str,
    baseline_version: str,
    candidate_version: str,
    artifact_types: list[str],
    baseline_versions: ReleaseInputVersions,
    candidate_versions: ReleaseInputVersions,
    baseline_eval_run_id: str,
    candidate_eval_run_id: str,
    eval_summary_refs: dict[str, str],
    coverage_summary_refs: dict[str, str],
    reason: str,
) -> dict[str, Any]:
    record = {
        "artifact_type": "evaluation_release_record",
        "schema_version": "1.0.0",
        "release_id": release_id,
        "timestamp": timestamp,
        "candidate_version": candidate_version,
        "baseline_version": baseline_version,
        "artifact_types": artifact_types,
        "version_set": {
            "baseline": {
                "prompt_version_id": baseline_versions.prompt_version_id,
                "schema_version": baseline_versions.schema_version,
                "policy_version_id": baseline_versions.policy_version_id,
                "route_policy_version_id": baseline_versions.route_policy_version_id,
            },
            "candidate": {
                "prompt_version_id": candidate_versions.prompt_version_id,
                "schema_version": candidate_versions.schema_version,
                "policy_version_id": candidate_versions.policy_version_id,
                "route_policy_version_id": candidate_versions.route_policy_version_id,
            },
        },
        "eval_summary_refs": eval_summary_refs,
        "coverage_summary_refs": coverage_summary_refs,
        "canary_comparison_results": {
            "baseline_eval_run_id": baseline_eval_run_id,
            "candidate_eval_run_id": candidate_eval_run_id,
            "sample_size": 0,
            "pass_rate_delta": 0.0,
            "coverage_score_delta": 0.0,
            "required_slice_regressions": [],
            "new_failures": [],
            "indeterminate_failures": [],
            "control_responses": {
                "baseline": "allow",
                "candidate": "block",
            },
            "threshold_results": [
                {
                    "threshold": "release_canary_execution",
                    "passed": False,
                    "actual": reason,
                    "expected": "successful_eval_and_coverage_execution",
                }
            ],
        },
        "decision": "hold",
        "reasons": [reason],
        "rollback_target_version": None,
    }
    return record


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run governed release canary policy and emit evaluation_release_record")
    parser.add_argument("--baseline-eval-run", default="contracts/examples/eval_run.json")
    parser.add_argument("--baseline-eval-cases", default="contracts/examples/release_canary_eval_cases.json")
    parser.add_argument("--candidate-eval-run", default="contracts/examples/eval_run.json")
    parser.add_argument("--candidate-eval-cases", default="contracts/examples/release_canary_eval_cases.json")
    parser.add_argument("--baseline-dataset", action="append", default=[])
    parser.add_argument("--candidate-dataset", action="append", default=[])
    parser.add_argument("--release-policy", default=str(_DEFAULT_RELEASE_POLICY))
    parser.add_argument("--coverage-policy", default=str(_DEFAULT_COVERAGE_POLICY))
    parser.add_argument("--output-dir", default=str(_DEFAULT_OUTPUT_DIR))
    parser.add_argument("--release-id", default="")
    parser.add_argument("--timestamp", default="")
    parser.add_argument("--baseline-version", required=True)
    parser.add_argument("--candidate-version", required=True)
    parser.add_argument("--artifact-type", action="append", default=["prompt", "schema", "policy", "routing"])

    parser.add_argument("--baseline-prompt-version-id", required=True)
    parser.add_argument("--candidate-prompt-version-id", required=True)
    parser.add_argument("--baseline-schema-version", required=True)
    parser.add_argument("--candidate-schema-version", required=True)
    parser.add_argument("--baseline-policy-version-id", required=True)
    parser.add_argument("--candidate-policy-version-id", required=True)
    parser.add_argument("--baseline-route-policy-version-id", default="")
    parser.add_argument("--candidate-route-policy-version-id", default="")

    args = parser.parse_args(argv)

    output_dir = Path(args.output_dir)
    baseline_dir = output_dir / "baseline"
    candidate_dir = output_dir / "candidate"
    output_dir.mkdir(parents=True, exist_ok=True)
    baseline_dir.mkdir(parents=True, exist_ok=True)
    candidate_dir.mkdir(parents=True, exist_ok=True)

    release_policy = _load_json(Path(args.release_policy))
    coverage_policy = _load_json(Path(args.coverage_policy))

    timestamp = args.timestamp.strip() or _utc_now()
    release_id = args.release_id.strip() or f"release-canary-{uuid.uuid4()}"
    baseline_eval_run = _load_json(Path(args.baseline_eval_run))
    candidate_eval_run = _load_json(Path(args.candidate_eval_run))
    baseline_dataset_paths = args.baseline_dataset or ["contracts/examples/eval_dataset.json"]
    candidate_dataset_paths = args.candidate_dataset or ["contracts/examples/eval_dataset.json"]
    baseline_datasets = [_load_json(Path(path)) for path in baseline_dataset_paths]
    candidate_datasets = [_load_json(Path(path)) for path in candidate_dataset_paths]

    baseline_eval_summary_path = baseline_dir / "eval_summary.json"
    candidate_eval_summary_path = candidate_dir / "eval_summary.json"
    baseline_eval_results_path = baseline_dir / "eval_results.json"
    candidate_eval_results_path = candidate_dir / "eval_results.json"
    baseline_coverage_path = baseline_dir / "eval_coverage_summary.json"
    candidate_coverage_path = candidate_dir / "eval_coverage_summary.json"

    baseline_versions = ReleaseInputVersions(
        prompt_version_id=args.baseline_prompt_version_id,
        schema_version=args.baseline_schema_version,
        policy_version_id=args.baseline_policy_version_id,
        route_policy_version_id=args.baseline_route_policy_version_id or None,
    )
    candidate_versions = ReleaseInputVersions(
        prompt_version_id=args.candidate_prompt_version_id,
        schema_version=args.candidate_schema_version,
        policy_version_id=args.candidate_policy_version_id,
        route_policy_version_id=args.candidate_route_policy_version_id or None,
    )
    eval_summary_refs = {
        "baseline": _ref_path(baseline_eval_summary_path),
        "candidate": _ref_path(candidate_eval_summary_path),
    }
    coverage_summary_refs = {
        "baseline": _ref_path(baseline_coverage_path),
        "candidate": _ref_path(candidate_coverage_path),
    }

    try:
        _, baseline_cases, baseline_results, baseline_summary = _run_eval_bundle(
            Path(args.baseline_eval_run),
            Path(args.baseline_eval_cases),
        )
        _, candidate_cases, candidate_results, candidate_summary = _run_eval_bundle(
            Path(args.candidate_eval_run),
            Path(args.candidate_eval_cases),
        )

        baseline_coverage, baseline_slices = _build_coverage(
            eval_cases=baseline_cases,
            eval_results=baseline_results,
            datasets=baseline_datasets,
            policy=coverage_policy,
            coverage_run_id=f"{release_id}-baseline",
            timestamp=timestamp,
        )
        candidate_coverage, candidate_slices = _build_coverage(
            eval_cases=candidate_cases,
            eval_results=candidate_results,
            datasets=candidate_datasets,
            policy=coverage_policy,
            coverage_run_id=f"{release_id}-candidate",
            timestamp=timestamp,
        )

        _write_json(baseline_eval_summary_path, baseline_summary)
        _write_json(candidate_eval_summary_path, candidate_summary)
        _write_json(baseline_eval_results_path, baseline_results)
        _write_json(candidate_eval_results_path, candidate_results)
        _write_json(baseline_coverage_path, baseline_coverage)
        _write_json(candidate_coverage_path, candidate_coverage)

        record = build_release_record(
            release_id=release_id,
            timestamp=timestamp,
            baseline_version=args.baseline_version,
            candidate_version=args.candidate_version,
            artifact_types=args.artifact_type,
            baseline_versions=baseline_versions,
            candidate_versions=candidate_versions,
            baseline_eval_summary=baseline_summary,
            candidate_eval_summary=candidate_summary,
            baseline_eval_results=baseline_results,
            candidate_eval_results=candidate_results,
            baseline_coverage_summary=baseline_coverage,
            candidate_coverage_summary=candidate_coverage,
            baseline_slice_summaries=baseline_slices,
            candidate_slice_summaries=candidate_slices,
            eval_summary_refs=eval_summary_refs,
            coverage_summary_refs=coverage_summary_refs,
            policy=release_policy,
        )
    except Exception as exc:  # noqa: BLE001
        reason = f"execution_error:{exc}"
        record = _build_fail_closed_record(
            release_id=release_id,
            timestamp=timestamp,
            baseline_version=args.baseline_version,
            candidate_version=args.candidate_version,
            artifact_types=args.artifact_type,
            baseline_versions=baseline_versions,
            candidate_versions=candidate_versions,
            baseline_eval_run_id=str(baseline_eval_run.get("eval_run_id", "unknown-baseline-eval-run")),
            candidate_eval_run_id=str(candidate_eval_run.get("eval_run_id", "unknown-candidate-eval-run")),
            eval_summary_refs=eval_summary_refs,
            coverage_summary_refs=coverage_summary_refs,
            reason=reason,
        )

    record_path = output_dir / "evaluation_release_record.json"
    _write_json(record_path, record)

    decision = record["decision"]
    print(
        f"release_id={record['release_id']} decision={decision} baseline={record['baseline_version']} candidate={record['candidate_version']} reasons={','.join(record['reasons'])}"
    )
    return decision_exit_code(decision)


if __name__ == "__main__":
    raise SystemExit(main())
