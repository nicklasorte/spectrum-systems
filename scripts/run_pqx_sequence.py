#!/usr/bin/env python3
"""Thin CLI wrapper for deterministic roadmap→wrapper→sequential PQX execution (CON-048)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Mapping

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.contracts import validate_artifact
from spectrum_systems.modules.runtime.codex_to_pqx_task_wrapper import (
    CodexToPQXWrapperError,
    build_codex_pqx_task_wrapper,
)
from spectrum_systems.modules.runtime.pqx_sequential_loop import (
    PQXSequentialLoopError,
    run_pqx_sequential,
)


class PQXSequenceCLIError(ValueError):
    """Raised when CLI inputs violate deterministic/fail-closed run requirements."""


def _load_json(path: Path) -> dict[str, Any] | list[Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise PQXSequenceCLIError(f"failed to read JSON file {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise PQXSequenceCLIError(f"invalid JSON in {path}: {exc}") from exc

    if not isinstance(payload, (dict, list)):
        raise PQXSequenceCLIError(f"JSON payload must be object or list: {path}")
    return payload


def _require_non_empty_string(payload: Mapping[str, Any], field: str, *, label: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise PQXSequenceCLIError(f"{label}.{field} must be a non-empty string")
    return value.strip()


def _normalize_roadmap_slices(payload: dict[str, Any] | list[Any]) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        slices = payload
    else:
        slices = payload.get("slices")

    if not isinstance(slices, list) or not slices:
        raise PQXSequenceCLIError("roadmap must be a non-empty list or object with non-empty 'slices' list")

    normalized: list[dict[str, Any]] = []
    for idx, row in enumerate(slices):
        if not isinstance(row, Mapping):
            raise PQXSequenceCLIError(f"roadmap slice at index {idx} must be an object")
        normalized.append(dict(row))
    return normalized


def _build_wrapped_slices(
    roadmap_slices: list[dict[str, Any]],
    *,
    run_id: str,
    execution_context: str,
    authority_evidence_ref: str | None,
    contract_preflight_result_artifact_path: str | None,
    roadmap_path: str,
    state_path: str,
    runs_root: str,
) -> list[dict[str, Any]]:
    def _render_with_run_id(value: Any, *, label: str) -> str:
        rendered = _require_non_empty_string({"value": value}, "value", label=label)
        try:
            return rendered.format(run_id=run_id)
        except KeyError as exc:
            raise PQXSequenceCLIError(f"{label} contains unsupported format key: {exc}") from exc

    wrapped: list[dict[str, Any]] = []
    for idx, row in enumerate(roadmap_slices):
        step_id = _require_non_empty_string(row, "step_id", label=f"roadmap.slices[{idx}]")
        step_name = _require_non_empty_string(row, "step_name", label=f"roadmap.slices[{idx}]")
        prompt = _require_non_empty_string(row, "prompt", label=f"roadmap.slices[{idx}]")
        pqx_output_text = _require_non_empty_string(row, "pqx_output_text", label=f"roadmap.slices[{idx}]")
        requested_at = _require_non_empty_string(row, "requested_at", label=f"roadmap.slices[{idx}]")

        changed_paths = row.get("changed_paths")
        if changed_paths is None:
            changed_paths = []
        if not isinstance(changed_paths, list):
            raise PQXSequenceCLIError(f"roadmap.slices[{idx}].changed_paths must be a list")

        wrapper_authority = authority_evidence_ref
        if isinstance(row.get("authority_evidence_ref"), str) and row["authority_evidence_ref"].strip():
            wrapper_authority = row["authority_evidence_ref"].strip()

        try:
            build_result = build_codex_pqx_task_wrapper(
                {
                    "task_id": str(row.get("task_id") or f"{run_id}:{step_id}:{idx}"),
                    "run_id": run_id,
                    "step_id": step_id,
                    "step_name": step_name,
                    "prompt": prompt,
                    "execution_context": execution_context,
                    "requested_at": requested_at,
                    "dependencies": row.get("dependencies", []),
                    "changed_paths": changed_paths,
                    "authority_context": {
                        "authority_evidence_ref": wrapper_authority,
                        "contract_preflight_result_artifact_path": contract_preflight_result_artifact_path,
                        "notes": row.get("authority_notes"),
                    },
                    "roadmap_version": str(row.get("roadmap_version") or roadmap_path),
                    "row_index": idx,
                    "row_status": str(row.get("row_status") or "ready"),
                }
            )
        except CodexToPQXWrapperError as exc:
            raise PQXSequenceCLIError(f"wrapper build failed for slice {step_id}: {exc}") from exc

        wrapper = build_result.wrapper
        governance = wrapper.get("governance") if isinstance(wrapper, Mapping) else {}
        classification = governance.get("classification") if isinstance(governance, Mapping) else None
        if not isinstance(classification, str) or not classification.strip():
            raise PQXSequenceCLIError(f"wrapper build failed for slice {step_id}: governance.classification missing")

        authority_state = governance.get("authority_state") if isinstance(governance, Mapping) else None
        if authority_state in {"non_authoritative_direct_run", "unknown_pending_execution"}:
            raise PQXSequenceCLIError(
                f"wrapper build failed for slice {step_id}: authority state {authority_state} is not allowed for CLI execution"
            )

        effective_authority = governance.get("authority_evidence_ref") if isinstance(governance, Mapping) else None
        if bool(governance.get("pqx_required")) and (not isinstance(effective_authority, str) or not effective_authority.strip()):
            raise PQXSequenceCLIError(
                f"wrapper build failed for slice {step_id}: governed slice missing authority evidence"
            )

        wrapped.append(
            {
                "slice_id": step_id,
                "wrapper": wrapper,
                "required_context": {
                    "classification": classification,
                    "execution_context": execution_context,
                    "authority_evidence_ref": effective_authority,
                },
                "roadmap_path": _render_with_run_id(
                    row.get("slice_roadmap_path") or roadmap_path,
                    label=f"roadmap.slices[{idx}].slice_roadmap_path",
                ),
                "state_path": _render_with_run_id(
                    row.get("state_path") or state_path,
                    label=f"roadmap.slices[{idx}].state_path",
                ),
                "runs_root": _render_with_run_id(
                    row.get("runs_root") or runs_root,
                    label=f"roadmap.slices[{idx}].runs_root",
                ),
                "pqx_output_text": pqx_output_text,
                "input_ref": str(row.get("input_ref") or f"roadmap:{step_id}"),
                "changed_paths": changed_paths,
            }
        )

    return wrapped


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a deterministic roadmap-driven sequential PQX execution")
    parser.add_argument("--roadmap", type=Path, required=True, help="Path to ordered roadmap slices JSON")
    parser.add_argument("--output", type=Path, required=True, help="Path to write authoritative sequential trace JSON")
    parser.add_argument("--run-id", required=True, help="Stable run identifier")
    parser.add_argument(
        "--execution-context",
        default=None,
        help="Execution context forwarded to wrapper builder (defaults to pqx_governed for CLI)",
    )
    parser.add_argument("--authority-evidence-ref", help="Authority evidence ref required for governed wrapper inputs")
    parser.add_argument("--contract-preflight-result-artifact-path", help="Optional contract preflight artifact path")
    parser.add_argument("--initial-context", type=Path, help="Optional initial context JSON override")
    parser.add_argument("--stage", default="sequence_execution", help="Default initial context stage if no context file")
    parser.add_argument("--runtime-environment", default="cli", help="Default runtime environment if no context file")
    parser.add_argument("--roadmap-path", default="docs/roadmaps/system_roadmap.md", help="Roadmap reference for slice runner")
    parser.add_argument("--state-path", default="data/pqx_state.json", help="PQX state path forwarded to slice runner")
    parser.add_argument("--runs-root", default="data/pqx_runs", help="PQX runs root forwarded to slice runner")
    return parser.parse_args()


def _resolve_execution_context(args: argparse.Namespace) -> str:
    raw = args.execution_context
    if raw is None:
        return "pqx_governed"
    normalized = str(raw).strip()
    if not normalized:
        return "pqx_governed"
    return normalized


def _load_initial_context(args: argparse.Namespace, first_slice: dict[str, Any]) -> dict[str, Any]:
    if args.initial_context:
        payload = _load_json(args.initial_context)
        if not isinstance(payload, dict):
            raise PQXSequenceCLIError("initial context must be a JSON object")
        return dict(payload)

    required_context = first_slice.get("required_context")
    if not isinstance(required_context, Mapping):
        raise PQXSequenceCLIError("wrapped slice missing required_context")

    return {
        "stage": args.stage,
        "runtime_environment": args.runtime_environment,
        "classification": required_context.get("classification"),
        "execution_context": required_context.get("execution_context"),
        "authority_evidence_ref": required_context.get("authority_evidence_ref"),
        "run_id": args.run_id,
    }


def main() -> int:
    try:
        args = parse_args()
        roadmap_payload = _load_json(args.roadmap)
        roadmap_slices = _normalize_roadmap_slices(roadmap_payload)

        execution_context = _resolve_execution_context(args)

        wrapped_slices = _build_wrapped_slices(
            roadmap_slices,
            run_id=args.run_id,
            execution_context=execution_context,
            authority_evidence_ref=args.authority_evidence_ref,
            contract_preflight_result_artifact_path=args.contract_preflight_result_artifact_path,
            roadmap_path=args.roadmap_path,
            state_path=args.state_path,
            runs_root=args.runs_root,
        )
        initial_context = _load_initial_context(args, wrapped_slices[0])

        trace = run_pqx_sequential(slices=wrapped_slices, initial_context=initial_context)
        if not isinstance(trace, dict):
            raise PQXSequenceCLIError("sequential loop returned malformed trace payload")

        validate_artifact(trace, "pqx_sequential_execution_trace")

        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(trace, indent=2) + "\n", encoding="utf-8")

        summary = {
            "status": "ok",
            "trace_artifact_path": str(args.output),
            "final_run_status": trace.get("final_status"),
            "blocking_reason": trace.get("blocking_reason"),
            "stopping_slice_id": trace.get("stopping_slice_id"),
        }
        print(json.dumps(summary, indent=2))

        final_status = trace.get("final_status")
        if final_status == "ALLOW":
            return 0
        if final_status in {"BLOCK", "REQUIRE_REVIEW"}:
            return 2
        raise PQXSequenceCLIError(f"unsupported final_status: {final_status}")
    except (PQXSequenceCLIError, PQXSequentialLoopError) as exc:
        print(json.dumps({"status": "blocked", "error": str(exc)}, indent=2), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
