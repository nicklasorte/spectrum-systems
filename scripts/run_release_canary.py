#!/usr/bin/env python3
"""Run deterministic baseline-vs-candidate release canary evaluation (SF-14)."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.run_eval_coverage_report import build_eval_coverage  # noqa: E402
from spectrum_systems.modules.evaluation.eval_engine import run_eval_run  # noqa: E402
from spectrum_systems.modules.runtime.release_canary import (  # noqa: E402
    ReleaseCanaryError,
    ReleaseInputVersions,
    build_release_record,
    decision_exit_code,
)

_DEFAULT_OUTPUT_DIR = _REPO_ROOT / "outputs" / "release_canary"
_DEFAULT_RELEASE_POLICY = _REPO_ROOT / "data" / "policy" / "eval_release_policy.json"
_DEFAULT_COVERAGE_POLICY = _REPO_ROOT / "data" / "policy" / "eval_coverage_policy.json"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_json_many(path: Path) -> list[dict[str, Any]]:
    payload = _load_json(path)
    if isinstance(payload, dict):
        return [payload]
    if isinstance(payload, list) and all(isinstance(item, dict) for item in payload):
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


def _stable_release_id(args: argparse.Namespace, release_policy: dict[str, Any], coverage_policy: dict[str, Any]) -> str:
    payload = {
        "baseline_eval_run": str(Path(args.baseline_eval_run).resolve()),
        "baseline_eval_cases": str(Path(args.baseline_eval_cases).resolve()),
        "candidate_eval_run": str(Path(args.candidate_eval_run).resolve()),
        "candidate_eval_cases": str(Path(args.candidate_eval_cases).resolve()),
        "baseline_version": args.baseline_version,
        "candidate_version": args.candidate_version,
        "baseline_prompt_version_id": args.baseline_prompt_version_id,
        "candidate_prompt_version_id": args.candidate_prompt_version_id,
        "baseline_schema_version": args.baseline_schema_version,
        "candidate_schema_version": args.candidate_schema_version,
        "baseline_policy_version_id": args.baseline_policy_version_id,
        "candidate_policy_version_id": args.candidate_policy_version_id,
        "baseline_route_policy_version_id": args.baseline_route_policy_version_id,
        "candidate_route_policy_version_id": args.candidate_route_policy_version_id,
        "artifact_types": sorted(set(args.artifact_type)),
        "release_policy": release_policy,
        "coverage_policy": coverage_policy,
    }
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()[:16]
    return f"release-canary-{digest}"


def _run_eval_bundle(eval_run_path: Path, eval_cases_path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    eval_run = _load_json(eval_run_path)
    eval_cases = _load_json_many(eval_cases_path)
    execution = run_eval_run(eval_run, eval_cases)
    eval_results = execution["eval_results"]
    eval_summary = execution["eval_summary"]
    return eval_cases, eval_results, eval_summary


def _build_coverage(
    *,
    eval_cases: list[dict[str, Any]],
    eval_results: list[dict[str, Any]],
    policy: dict[str, Any],
    coverage_run_id: str,
    timestamp: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    coverage, slices, _ = build_eval_coverage(
        eval_cases=eval_cases,
        eval_results=eval_results,
        datasets=[],
        policy=policy,
        coverage_run_id=coverage_run_id,
        timestamp=timestamp,
    )
    return coverage, slices


def _error_record(
    *,
    release_id: str,
    timestamp: str,
    baseline_version: str,
    candidate_version: str,
    artifact_types: list[str],
    reason: str,
    decision: str,
    policy_version_id: str,
) -> dict[str, Any]:
    return {
        "artifact_type": "evaluation_release_record",
        "schema_version": "1.1.0",
        "release_id": release_id,
        "timestamp": timestamp,
        "candidate_version": candidate_version,
        "baseline_version": baseline_version,
        "artifact_types": sorted(set(artifact_types)),
        "version_set": {
            "baseline": {
                "prompt_version_id": "unknown",
                "schema_version": "unknown",
                "policy_version_id": "unknown",
                "route_policy_version_id": None,
            },
            "candidate": {
                "prompt_version_id": "unknown",
                "schema_version": "unknown",
                "policy_version_id": "unknown",
                "route_policy_version_id": None,
            },
        },
        "eval_summary_refs": {"baseline": "unavailable://baseline", "candidate": "unavailable://candidate"},
        "coverage_summary_refs": {"baseline": "unavailable://baseline", "candidate": "unavailable://candidate"},
        "canary_comparison_results": {
            "baseline_eval_run_id": "error",
            "candidate_eval_run_id": "error",
            "sample_size": 0,
            "pass_rate_delta": 0.0,
            "coverage_score_delta": 0.0,
            "required_slice_regressions": [],
            "coverage_mismatch_fields": [],
            "new_failures": [],
            "indeterminate_failures": [],
            "control_responses": {"baseline": "block", "candidate": "block"},
            "threshold_results": [
                {
                    "threshold": "operational_exception",
                    "passed": False,
                    "actual": reason,
                    "expected": "none",
                }
            ],
        },
        "decision": decision,
        "reasons": [reason],
        "rollback_target_version": baseline_version if decision == "rollback" else None,
        "policy_version_id": policy_version_id,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run governed release canary policy and emit evaluation_release_record")
    parser.add_argument("--baseline-eval-run", default="contracts/examples/eval_run.json")
    parser.add_argument("--baseline-eval-cases", default="contracts/examples/eval_case.json")
    parser.add_argument("--candidate-eval-run", default="contracts/examples/eval_run.json")
    parser.add_argument("--candidate-eval-cases", default="contracts/examples/eval_case.json")
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

    record_path = output_dir / "evaluation_release_record.json"
    release_policy: dict[str, Any] = {}
    coverage_policy: dict[str, Any] = {}
    release_id = args.release_id.strip() or "release-canary-unset"
    policy_version_id = "unknown"

    try:
        release_policy = _load_json(Path(args.release_policy))
        coverage_policy = _load_json(Path(args.coverage_policy))
        policy_version_id = str(release_policy.get("policy_version_id", "unknown"))
        release_id = args.release_id.strip() or _stable_release_id(args, release_policy, coverage_policy)

        baseline_cases, baseline_results, baseline_summary = _run_eval_bundle(
            Path(args.baseline_eval_run),
            Path(args.baseline_eval_cases),
        )
        candidate_cases, candidate_results, candidate_summary = _run_eval_bundle(
            Path(args.candidate_eval_run),
            Path(args.candidate_eval_cases),
        )

        timestamp = args.timestamp.strip() or str(candidate_summary.get("timestamp") or baseline_summary.get("timestamp") or _utc_now())

        baseline_coverage, baseline_slices = _build_coverage(
            eval_cases=baseline_cases,
            eval_results=baseline_results,
            policy=coverage_policy,
            coverage_run_id=f"{release_id}-baseline",
            timestamp=timestamp,
        )
        candidate_coverage, candidate_slices = _build_coverage(
            eval_cases=candidate_cases,
            eval_results=candidate_results,
            policy=coverage_policy,
            coverage_run_id=f"{release_id}-candidate",
            timestamp=timestamp,
        )

        baseline_eval_summary_path = baseline_dir / "eval_summary.json"
        candidate_eval_summary_path = candidate_dir / "eval_summary.json"
        baseline_eval_results_path = baseline_dir / "eval_results.json"
        candidate_eval_results_path = candidate_dir / "eval_results.json"
        baseline_coverage_path = baseline_dir / "eval_coverage_summary.json"
        candidate_coverage_path = candidate_dir / "eval_coverage_summary.json"

        _write_json(baseline_eval_summary_path, baseline_summary)
        _write_json(candidate_eval_summary_path, candidate_summary)
        _write_json(baseline_eval_results_path, baseline_results)
        _write_json(candidate_eval_results_path, candidate_results)
        _write_json(baseline_coverage_path, baseline_coverage)
        _write_json(candidate_coverage_path, candidate_coverage)

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
            eval_summary_refs={
                "baseline": _ref_path(baseline_eval_summary_path),
                "candidate": _ref_path(candidate_eval_summary_path),
            },
            coverage_summary_refs={
                "baseline": _ref_path(baseline_coverage_path),
                "candidate": _ref_path(candidate_coverage_path),
            },
            policy=release_policy,
        )
        _write_json(record_path, record)

        decision = str(record["decision"])
        print(
            f"release_id={record['release_id']} decision={decision} baseline={record['baseline_version']} candidate={record['candidate_version']} reasons={','.join(record['reasons'])}"
        )
        return decision_exit_code(decision)
    except Exception as exc:  # noqa: BLE001
        timestamp = args.timestamp.strip() or _utc_now()
        reason = f"operational_error:{type(exc).__name__}"
        decision = "hold"
        if isinstance(exc, ReleaseCanaryError):
            decision = "rollback"
        error_record = _error_record(
            release_id=release_id,
            timestamp=timestamp,
            baseline_version=args.baseline_version,
            candidate_version=args.candidate_version,
            artifact_types=args.artifact_type,
            reason=reason,
            decision=decision,
            policy_version_id=policy_version_id,
        )

        try:
            _write_json(record_path, error_record)
        except Exception as write_exc:  # noqa: BLE001
            print(f"release-canary fatal: artifact emission failed ({write_exc})")
            return decision_exit_code("rollback")

        print(f"release-canary non-promote: {reason}: {exc}")
        return decision_exit_code(decision)


if __name__ == "__main__":
    raise SystemExit(main())
