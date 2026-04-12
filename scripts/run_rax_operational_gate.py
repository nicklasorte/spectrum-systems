#!/usr/bin/env python3
"""Run RAX operational hard gate with fail-closed exit semantics."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.contracts import load_example
from spectrum_systems.modules.runtime.rax_eval_runner import (
    apply_admission_quality_filters,
    build_policy_regression_evidence_bundle,
    build_replay_evidence_binding,
    compile_judgment_patterns_to_policy_candidates,
    enforce_rax_operational_hard_gate,
    evaluate_drift_threshold_semantics,
    sign_rax_evidence_bundle,
    verify_rax_evidence_bundle_signature,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run RAX operational gate and emit artifact")
    parser.add_argument("--output", type=Path, default=Path("outputs/rax_operational_gate_record.json"))
    parser.add_argument("--fail-freeze", action="store_true", help="Inject freeze-worthy drift signal")
    args = parser.parse_args()

    readiness = load_example("rax_control_readiness_record")
    readiness["ready_for_control"] = True
    readiness["decision"] = "hold"
    readiness["blocking_reasons"] = []
    conflict = load_example("rax_conflict_arbitration_record")
    conflict["material_conflicts"] = []

    if args.fail_freeze:
        conflict["material_conflicts"] = ["contradictory_eval_signals"]

    policy_bundle = build_policy_regression_evidence_bundle(
        bundle_id="policy-bundle-001",
        policy_version="1.0.0",
        rule_version="1.0.0",
        eval_version="1.2.0",
        regression_passed=True,
        evidence_refs=["eval_summary://rax-001"],
    )

    replay_binding = build_replay_evidence_binding(
        bundle_id="run-bundle-001",
        replay_identity={
            "fingerprint": "fp-001",
            "policy_version": "1.0.0",
            "semantic_rule_version": "1.0.0",
        },
        expected_policy_version="1.0.0",
        expected_semantic_rule_version="1.0.0",
    )

    drift_decision = evaluate_drift_threshold_semantics(
        health_snapshot={"snapshot_id": "s1", "candidate_posture": "healthy", "threshold_violations": []},
        drift_signal_record={
            "signal_id": "d1",
            "candidate_posture": "freeze_candidate" if args.fail_freeze else "warn",
            "violations": ["eval_signal_drift"] if args.fail_freeze else [],
        },
    )

    candidate = load_example("rax_failure_eval_candidate")
    registry: dict[str, object] = {"admitted_candidates": []}
    admission = apply_admission_quality_filters(
        candidate=candidate,
        admission_policy={
            "min_reason_codes": 1,
            "allowed_eval_types": ["rax_output_semantic_alignment", "rax_control_readiness"],
            "max_candidates_per_target_per_window": 3,
            "max_same_dedupe_key_per_window": 2,
        },
        canonical_registry=registry,
    )

    _ = compile_judgment_patterns_to_policy_candidates(
        compilation_id="compile-001",
        judgment_records=[{"rationale": ["missing_required_eval_types", "trace_incomplete"]}] * 3,
    )

    signature = sign_rax_evidence_bundle(bundle=policy_bundle, signing_key="rax-dev-key")
    signature_verified = verify_rax_evidence_bundle_signature(
        bundle=policy_bundle,
        signature_record=signature,
        signing_key="rax-dev-key",
    )

    gate = enforce_rax_operational_hard_gate(
        gate_id="rax-operational-gate-001",
        readiness_record=readiness,
        conflict_record=conflict,
        policy_regression_bundle=policy_bundle,
        replay_binding=replay_binding,
        drift_threshold_decision=drift_decision,
        admission_record=admission,
        signature_verified=signature_verified,
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(gate, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "passed": gate["passed"], "decision": gate["decision"]}))

    raise SystemExit(0 if gate["passed"] else 2)


if __name__ == "__main__":
    main()
