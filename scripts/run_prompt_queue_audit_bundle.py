#!/usr/bin/env python3
"""Thin CLI wrapper for deterministic fail-closed prompt queue audit bundles."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.modules.prompt_queue import (  # noqa: E402
    QueueAuditBundleError,
    build_queue_audit_bundle,
    validate_queue_audit_bundle,
    write_artifact,
)


def _parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build prompt queue audit bundle artifact")
    parser.add_argument("--manifest-ref", required=True)
    parser.add_argument("--final-queue-state-ref", required=True)
    parser.add_argument("--execution-result-ref", action="append", required=True)
    parser.add_argument("--step-decision-ref", action="append", required=True)
    parser.add_argument("--transition-decision-ref", action="append", required=True)
    parser.add_argument("--replay-ref", action="append", default=[])
    parser.add_argument("--observability-ref", required=True)
    parser.add_argument("--certification-ref", required=True)
    parser.add_argument("--output-path", required=True)
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    args = _parse_args(argv)
    refs = {
        "manifest_ref": args.manifest_ref,
        "final_queue_state_ref": args.final_queue_state_ref,
        "execution_result_refs": args.execution_result_ref,
        "step_decision_refs": args.step_decision_ref,
        "transition_decision_refs": args.transition_decision_ref,
        "replay_refs": args.replay_ref,
        "observability_ref": args.observability_ref,
        "certification_ref": args.certification_ref,
    }

    try:
        bundle = build_queue_audit_bundle(refs)
        validate_queue_audit_bundle(bundle)
        write_artifact(bundle, Path(args.output_path))
    except (QueueAuditBundleError, ValueError, FileNotFoundError, json.JSONDecodeError) as exc:
        print(json.dumps({"error": str(exc)}, indent=2), file=sys.stderr)
        return 2

    print(
        json.dumps(
            {
                "output_path": args.output_path,
                "lineage_status": bundle["lineage_status"],
                "completeness_status": bundle["completeness_status"],
            },
            indent=2,
        )
    )
    return 0 if bundle["completeness_status"] == "complete" else 3


if __name__ == "__main__":
    raise SystemExit(main())
