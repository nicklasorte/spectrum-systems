#!/usr/bin/env python3
"""M3L-02 — Agent 3LS Path Measurement CLI.

Aggregates existing APR / CLP / APU / AGL artifacts into a single
``agent_3ls_path_measurement_record`` so that callers can answer:

- did the agent traverse AEX -> PQX -> EVL -> TPA -> CDE -> SEL?
- where did it fall out?
- what was the first missing leg?
- what was the first failed check?

This script is observation-only. It MUST NOT recompute upstream gates,
run any check, or mutate any input artifact. Canonical authority remains
with AEX (admission), PQX (bounded execution closure), EVL (eval
evidence), TPA (policy/scope), CDE (continuation/closure), SEL (final
gate signal), LIN (lineage), REP (replay), and GOV per
``docs/architecture/system_registry.md``.

Exit codes
----------
0 — measurement record emitted (regardless of loop completeness)
2 — input artifact path was supplied but is missing or invalid
4 — internal runner error
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.contracts import validate_artifact  # noqa: E402
from spectrum_systems.modules.runtime.agent_3ls_path_measurement import (  # noqa: E402
    DEFAULT_OUTPUT_REL_PATH,
    build_agent_3ls_path_measurement_record,
    load_agl_record,
    load_apr_result,
    load_apu_result,
    load_clp_result,
    write_measurement_record,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="M3L-02 Agent 3LS Path Measurement")
    parser.add_argument("--work-item-id", required=True)
    parser.add_argument(
        "--agent-type",
        default="unknown",
        choices=["codex", "claude", "other", "unknown", "unknown_ai_agent"],
    )
    parser.add_argument(
        "--repo-mutating",
        default="auto",
        choices=["auto", "true", "false", "unknown"],
        help=(
            "auto = inherit from APR/APU/AGL artifact_type fields; "
            "unknown = force null (forces pr_update_ready_status=not_ready)."
        ),
    )
    parser.add_argument("--apr-result", default=None)
    parser.add_argument("--clp-result", default=None)
    parser.add_argument("--apu-result", default=None)
    parser.add_argument("--agl-record", default=None)
    parser.add_argument("--output", default=DEFAULT_OUTPUT_REL_PATH)
    return parser.parse_args()


def _resolve_repo_mutating(directive: str) -> bool | None:
    if directive == "true":
        return True
    if directive == "false":
        return False
    if directive == "unknown":
        return None
    return None  # "auto" — defer to artifact-derived value inside the builder


def _resolve_path(value: str | None) -> Path | None:
    if not value:
        return None
    return (REPO_ROOT / value).resolve()


def _ref_relative(value: str | None) -> str | None:
    if not value:
        return None
    return value


def main() -> int:
    args = _parse_args()
    output_path = (REPO_ROOT / args.output).resolve()

    apr_path = _resolve_path(args.apr_result)
    clp_path = _resolve_path(args.clp_result)
    apu_path = _resolve_path(args.apu_result)
    agl_path = _resolve_path(args.agl_record)

    apr_result = load_apr_result(apr_path)
    clp_result = load_clp_result(clp_path)
    apu_result = load_apu_result(apu_path)
    agl_record = load_agl_record(agl_path) if agl_path is not None else None

    # If a path was provided but the artifact is missing/invalid we fall through
    # and reflect that in the measurement record (the leg observations encode
    # the absence). Exit code 2 is reserved for the case where every input was
    # supplied and at least one was unloadable — the operator can still see
    # the measurement record.
    invalid_inputs: list[str] = []
    if apr_path is not None and apr_result is None:
        invalid_inputs.append("apr")
    if clp_path is not None and clp_result is None:
        invalid_inputs.append("clp")
    if apu_path is not None and apu_result is None:
        invalid_inputs.append("apu")
    if agl_path is not None and agl_record is None:
        invalid_inputs.append("agl")

    record: dict[str, Any] = build_agent_3ls_path_measurement_record(
        work_item_id=args.work_item_id,
        agent_type=args.agent_type,
        repo_mutating=_resolve_repo_mutating(args.repo_mutating),
        apr_result=apr_result,
        clp_result=clp_result,
        apu_result=apu_result,
        agl_record=agl_record,
        apr_result_ref=_ref_relative(args.apr_result),
        clp_result_ref=_ref_relative(args.clp_result),
        apu_result_ref=_ref_relative(args.apu_result),
        agl_record_ref=_ref_relative(args.agl_record),
    )

    validate_artifact(record, "agent_3ls_path_measurement_record")
    write_measurement_record(record, output_path)

    summary = {
        "loop_complete": record["loop_complete"],
        "first_missing_leg": record["first_missing_leg"],
        "first_failed_check": record["first_failed_check"],
        "fell_out_at": record["fell_out_at"],
        "pr_ready_status": record["pr_ready_status"],
        "pr_update_ready_status": record["pr_update_ready_status"],
        "output": str(output_path.relative_to(REPO_ROOT)),
    }
    if invalid_inputs:
        summary["invalid_inputs"] = invalid_inputs
    print(json.dumps(summary, indent=2))
    return 2 if invalid_inputs else 0


if __name__ == "__main__":
    raise SystemExit(main())
