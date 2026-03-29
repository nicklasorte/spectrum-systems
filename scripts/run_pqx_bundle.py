#!/usr/bin/env python3
"""Run a governed PQX executable bundle from docs/roadmaps/execution_bundles.md."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from spectrum_systems.modules.runtime.pqx_bundle_orchestrator import (
    PQXBundleOrchestratorError,
    execute_bundle_run,
    load_bundle_plan,
    resolve_bundle_definition,
)
from spectrum_systems.modules.runtime.pqx_bundle_state import (
    PQXBundleStateError,
    ingest_review_result,
    load_bundle_state,
    save_bundle_state,
)
from spectrum_systems.modules.runtime.pqx_triage_planner import (
    PQXTriagePlannerError,
    build_triage_plan_record,
)


def _run(args: argparse.Namespace) -> int:
    try:
        result = execute_bundle_run(
            bundle_id=args.bundle_id,
            bundle_state_path=Path(args.bundle_state_path),
            output_dir=Path(args.output_dir),
            run_id=args.run_id,
            sequence_run_id=args.sequence_run_id,
            trace_id=args.trace_id,
            bundle_plan_path=Path(args.bundle_plan_path),
            execute_fixes=args.execute_fixes,
            emit_triage_plan=args.emit_triage_plan,
        )
    except PQXBundleOrchestratorError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    print(json.dumps(result, indent=2))
    if result.get("status") != "completed":
        failure = result.get("failure_classification")
        if failure == "FIX_GATE_BLOCKED":
            print(
                f"fix gate adjudication blocked bundle resume (failure_classification={failure}, bundle_state={result.get('bundle_state')})",
                file=sys.stderr,
            )
    return 0 if result["status"] == "completed" else 1


def _emit_triage(args: argparse.Namespace) -> int:
    try:
        definition = resolve_bundle_definition(load_bundle_plan(args.bundle_plan_path), args.bundle_id)
        review_refs = list(args.review_artifact_ref or [])
        fix_refs = list(args.fix_gate_artifact_ref or [])

        reviews = [json.loads(Path(ref).read_text(encoding="utf-8")) for ref in review_refs]
        fixes = [json.loads(Path(ref).read_text(encoding="utf-8")) for ref in fix_refs]
        record = build_triage_plan_record(
            run_id=args.run_id,
            trace_id=args.trace_id,
            bundle_run_id=args.sequence_run_id,
            bundle_id=args.bundle_id,
            roadmap_authority_ref="docs/roadmaps/system_roadmap.md",
            review_artifacts=reviews,
            review_artifact_refs=review_refs,
            fix_gate_records=fixes,
            fix_gate_record_refs=fix_refs,
            step_ids=list(definition.ordered_step_ids),
            created_at=args.created_at,
        )
        out_path = Path(args.output_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    except (PQXTriagePlannerError, PQXBundleOrchestratorError, OSError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 2

    print(json.dumps({"status": "triage_plan_emitted", "triage_plan_record": args.output_path}, indent=2))
    if record["summary_counts"]["blocking_total"] > 0:
        return 1
    return 0


def _ingest(args: argparse.Namespace) -> int:
    try:
        definition = resolve_bundle_definition(load_bundle_plan(args.bundle_plan_path), args.bundle_id)
        bundle_plan = [{"bundle_id": definition.bundle_id, "step_ids": list(definition.ordered_step_ids), "depends_on": list(definition.depends_on)}]
        state = load_bundle_state(args.bundle_state_path, bundle_plan=bundle_plan)
        review = json.loads(Path(args.review_artifact_path).read_text(encoding="utf-8"))
        updated = ingest_review_result(
            state,
            bundle_plan,
            review_artifact=review,
            artifact_ref=args.review_artifact_path,
            now=args.now,
        )
        save_bundle_state(updated, args.bundle_state_path, bundle_plan=bundle_plan)
    except (PQXBundleStateError, PQXBundleOrchestratorError, OSError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps({"status": "ingested", "bundle_state": args.bundle_state_path}, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Execute and govern a PQX bundle deterministically.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="run/resume bundle execution")
    run_parser.add_argument("--bundle-id", required=True)
    run_parser.add_argument("--bundle-state-path", required=True)
    run_parser.add_argument("--output-dir", required=True)
    run_parser.add_argument("--run-id", required=True)
    run_parser.add_argument("--sequence-run-id", required=True)
    run_parser.add_argument("--trace-id", required=True)
    run_parser.add_argument("--bundle-plan-path", default="docs/roadmaps/execution_bundles.md")
    run_parser.add_argument(
        "--execute-fixes",
        action="store_true",
        help="execute all pending fixes before advancing bundle steps; exits non-zero if a fix blocks/fails",
    )
    run_parser.add_argument(
        "--emit-triage-plan",
        action="store_true",
        help="emit planning-only pqx_triage_plan_record when blocked/findings conditions are met",
    )

    ingest_parser = subparsers.add_parser("ingest-findings", help="attach + ingest a review artifact into bundle state")
    ingest_parser.add_argument("--bundle-id", required=True)
    ingest_parser.add_argument("--bundle-state-path", required=True)
    ingest_parser.add_argument("--bundle-plan-path", default="docs/roadmaps/execution_bundles.md")
    ingest_parser.add_argument("--review-artifact-path", required=True)
    ingest_parser.add_argument("--now", required=True)

    triage_parser = subparsers.add_parser("emit-triage-plan", help="emit a planning-only triage artifact from existing inputs")
    triage_parser.add_argument("--bundle-id", required=True)
    triage_parser.add_argument("--bundle-plan-path", default="docs/roadmaps/execution_bundles.md")
    triage_parser.add_argument("--run-id", required=True)
    triage_parser.add_argument("--sequence-run-id", required=True)
    triage_parser.add_argument("--trace-id", required=True)
    triage_parser.add_argument("--created-at", required=True)
    triage_parser.add_argument("--output-path", required=True)
    triage_parser.add_argument("--review-artifact-ref", action="append", default=[])
    triage_parser.add_argument("--fix-gate-artifact-ref", action="append", default=[])

    args = parser.parse_args()
    if args.command == "run":
        return _run(args)
    if args.command == "ingest-findings":
        return _ingest(args)
    return _emit_triage(args)


if __name__ == "__main__":
    raise SystemExit(main())
