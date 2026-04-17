#!/usr/bin/env python3
"""Run the minimal governed PQX backbone control loop."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

from spectrum_systems.modules.runtime.pqx_execution_policy import evaluate_pqx_execution_policy
from spectrum_systems.modules.runtime.pqx_required_context_enforcement import (
    PQXRequiredContextEnforcementError,
    enforce_pqx_required_context,
)
from spectrum_systems.modules.runtime.pqx_slice_runner import run_pqx_slice


REPO_ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Deterministic PQX roadmap runner")
    parser.add_argument("--step-id", help="Explicit roadmap step id to execute.")
    parser.add_argument(
        "--pqx-output-file",
        type=Path,
        help="Path to deterministic PQX output text input. Required for execution; if missing, run blocks fail-closed.",
    )
    parser.add_argument(
        "--roadmap-path",
        type=Path,
        default=REPO_ROOT / "docs" / "roadmap" / "system_roadmap.md",
    )
    parser.add_argument(
        "--state-path",
        type=Path,
        default=REPO_ROOT / "data" / "pqx_state.json",
    )
    parser.add_argument(
        "--runs-root",
        type=Path,
        default=REPO_ROOT / "data" / "pqx_runs",
    )
    parser.add_argument(
        "--contract-impact-artifact-path",
        type=Path,
        help="Optional path to precomputed contract_impact_artifact JSON; blocks PQX when unresolved.",
    )
    parser.add_argument(
        "--changed-contract-path",
        action="append",
        default=[],
        help="Changed contract schema path(s). If provided without --contract-impact-artifact-path, analyzer runs pre-execution.",
    )
    parser.add_argument(
        "--changed-example-path",
        action="append",
        default=[],
        help="Optional changed contract example path(s) forwarded to analyzer.",
    )
    parser.add_argument(
        "--execution-change-impact-artifact-path",
        type=Path,
        help="Optional path to precomputed execution_change_impact_artifact JSON; blocks PQX when unresolved.",
    )
    parser.add_argument(
        "--changed-path",
        action="append",
        default=[],
        help="Changed file path(s) for deterministic execution change impact analysis.",
    )
    parser.add_argument(
        "--execution-change-baseline-ref",
        default="HEAD",
        help="Git baseline reference for execution change impact analysis.",
    )
    parser.add_argument(
        "--provided-review",
        action="append",
        default=[],
        help="Review evidence ids supplied to execution change impact gate.",
    )
    parser.add_argument(
        "--provided-eval-artifact",
        action="append",
        default=[],
        help="Evaluation artifact ids supplied to execution change impact gate.",
    )
    parser.add_argument(
        "--control-surface-gap-packet",
        type=Path,
        help="Optional path to control_surface_gap_packet JSON consumed by PQX fail-closed gating.",
    )
    parser.add_argument(
        "--execution-context",
        default="unspecified",
        help="Execution context posture for governed PQX required-context enforcement.",
    )
    parser.add_argument(
        "--pqx-wrapper-path",
        type=Path,
        help="Optional canonical codex_pqx_task_wrapper path required for governed execution contexts.",
    )
    parser.add_argument(
        "--authority-evidence-ref",
        help="Optional authority evidence ref for governed required-context enforcement.",
    )
    parser.add_argument(
        "--execution-intent",
        choices=("repo_write", "non_repo_write"),
        help="Required PQX execution intent declaration at the execution boundary.",
    )
    parser.add_argument(
        "--build-admission-record-path",
        type=Path,
        help="Optional build_admission_record JSON path required for repo_write execution_intent.",
    )
    parser.add_argument(
        "--normalized-execution-request-path",
        type=Path,
        help="Optional normalized_execution_request JSON path required for repo_write execution_intent.",
    )
    parser.add_argument(
        "--tlc-handoff-record-path",
        type=Path,
        help="Optional tlc_handoff_record JSON path required for repo_write execution_intent.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    preflight_cmd = [sys.executable, "scripts/run_shift_left_preflight.py"]
    for changed in list(args.changed_path) + list(args.changed_contract_path) + list(args.changed_example_path):
        preflight_cmd.extend(["--changed-file", changed])
    preflight = subprocess.run(preflight_cmd, cwd=REPO_ROOT, check=False, capture_output=True, text=True)
    if preflight.stdout:
        print(preflight.stdout, end="")
    if preflight.stderr:
        print(preflight.stderr, end="")
    if preflight.returncode != 0:
        print({"status": "blocked", "block_type": "SLH_PREFLIGHT_BLOCKED"})
        return 2

    pqx_output_text = None
    if args.pqx_output_file:
        pqx_output_text = args.pqx_output_file.read_text(encoding="utf-8")
    wrapper_payload = None
    if args.pqx_wrapper_path:
        try:
            wrapper_payload = json.loads(args.pqx_wrapper_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print({"status": "blocked", "block_type": "PQX_REQUIRED_CONTEXT_BLOCKED", "reason": f"invalid pqx wrapper path: {exc}"})
            return 2

    required_context_changed_paths = list(args.changed_path) + list(args.changed_contract_path) + list(args.changed_example_path)
    policy = evaluate_pqx_execution_policy(
        changed_paths=required_context_changed_paths,
        execution_context=args.execution_context,
    ).to_dict()
    try:
        required_context = enforce_pqx_required_context(
            classification=str(policy.get("classification", "exploration_only_or_non_governed")),
            execution_context=args.execution_context,
            changed_paths=required_context_changed_paths,
            pqx_task_wrapper=wrapper_payload,
            authority_evidence_ref=args.authority_evidence_ref,
        ).to_dict()
    except PQXRequiredContextEnforcementError as exc:
        print({"status": "blocked", "block_type": "PQX_REQUIRED_CONTEXT_BLOCKED", "reason": str(exc)})
        return 2
    if str(required_context.get("status", "")).lower() == "block":
        print(
            {
                "status": "blocked",
                "block_type": "PQX_REQUIRED_CONTEXT_BLOCKED",
                "reason": "pqx required context enforcement blocked execution",
                "pqx_execution_policy": policy,
                "pqx_required_context_enforcement": required_context,
            }
        )
        return 2

    lineage_payload = None
    if any(
        path is not None
        for path in (
            args.build_admission_record_path,
            args.normalized_execution_request_path,
            args.tlc_handoff_record_path,
        )
    ):
        try:
            lineage_payload = {
                "build_admission_record": (
                    json.loads(args.build_admission_record_path.read_text(encoding="utf-8"))
                    if args.build_admission_record_path
                    else None
                ),
                "normalized_execution_request": (
                    json.loads(args.normalized_execution_request_path.read_text(encoding="utf-8"))
                    if args.normalized_execution_request_path
                    else None
                ),
                "tlc_handoff_record": (
                    json.loads(args.tlc_handoff_record_path.read_text(encoding="utf-8"))
                    if args.tlc_handoff_record_path
                    else None
                ),
            }
        except (OSError, json.JSONDecodeError) as exc:
            print({"status": "blocked", "block_type": "REPO_WRITE_LINEAGE_REQUIRED", "reason": f"invalid lineage artifact path: {exc}"})
            return 2

    result = run_pqx_slice(
        step_id=args.step_id or "",
        pqx_output_text=pqx_output_text,
        roadmap_path=args.roadmap_path,
        state_path=args.state_path,
        runs_root=args.runs_root,
        contract_impact_artifact_path=args.contract_impact_artifact_path,
        changed_contract_paths=args.changed_contract_path,
        changed_example_paths=args.changed_example_path,
        execution_change_impact_artifact_path=args.execution_change_impact_artifact_path,
        changed_paths=args.changed_path,
        execution_change_baseline_ref=args.execution_change_baseline_ref,
        provided_reviews=args.provided_review,
        provided_eval_artifacts=args.provided_eval_artifact,
        control_surface_gap_packet_ref=str(args.control_surface_gap_packet) if args.control_surface_gap_packet else None,
        execution_intent=args.execution_intent,
        repo_write_lineage=lineage_payload,
    )

    print(result)
    return 0 if result["status"] == "complete" else 2


if __name__ == "__main__":
    raise SystemExit(main())
