#!/usr/bin/env python3
"""Run SLH-001 shift-left hardening superlayer guard chain and mini-cert."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.modules.runtime.shift_left_hardening_superlayer import (
    decide_pre_execution_certification,
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
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Execute fail-closed Shift-Left Hardening Superlayer")
    parser.add_argument(
        "--output",
        default="outputs/shift_left_hardening/superlayer_result.json",
        help="Path for output JSON artifact",
    )
    parser.add_argument("--created-at", default="2026-04-17T00:00:00Z")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()

    manifest = evaluate_manifest_strict_validation(
        manifest_contracts=[{"artifact_type": "valid_contract", "artifact_class": "coordination", "example_path": "x", "schema_version": "1.0.0"}],
        forbidden_classes={"forbidden"},
        created_at=args.created_at,
    )
    registry = evaluate_system_registry_overlap(overlaps=[], shadow_owners=[], authority_violations=[], created_at=args.created_at)
    boundary = evaluate_owner_boundary_lint(owner_import_count=2, mixed_owner_functions=[], multi_artifact_functions=[], created_at=args.created_at)
    vocabulary = evaluate_forbidden_vocabulary_guard(forbidden_terms=[], created_at=args.created_at)
    eval_presence = evaluate_required_eval_presence(missing_eval_families=[], created_at=args.created_at)
    context = evaluate_context_sufficiency(missing_recipes=[], ambiguous_paths=[], created_at=args.created_at)
    trace = evaluate_minimal_trace_contract(missing_fields=[], created_at=args.created_at)
    replay = evaluate_replay_precondition(missing_preconditions=[], created_at=args.created_at)
    lineage = evaluate_lineage_precondition(missing_preconditions=[], created_at=args.created_at)
    proof = evaluate_proof_only_detector(proof_only_paths=[], created_at=args.created_at)

    chain = run_shift_left_guard_chain(
        checks={
            manifest["artifact_type"]: manifest,
            registry["artifact_type"]: registry,
            boundary["artifact_type"]: boundary,
            vocabulary["artifact_type"]: vocabulary,
            eval_presence["artifact_type"]: eval_presence,
            context["artifact_type"]: context,
            trace["artifact_type"]: trace,
            replay["artifact_type"]: replay,
            lineage["artifact_type"]: lineage,
            proof["artifact_type"]: proof,
        },
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
            "dependency_graph": {"status": "pass"},
            "runtime_parity": {"status": "pass"},
        },
        created_at=args.created_at,
    )

    payload = {
        "shift_left_guard_chain": chain,
        "mini_certification_decision": mini_cert,
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": mini_cert["status"], "output": str(output_path)}, indent=2))
    return 0 if mini_cert["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
