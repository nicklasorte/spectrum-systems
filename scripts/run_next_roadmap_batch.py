#!/usr/bin/env python3
"""Load governed roadmap, select next batch, execute one bounded cycle, and emit progress outputs."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.contracts import validate_artifact
from spectrum_systems.modules.runtime.roadmap_selector import (  # noqa: E402
    RoadmapSelectionError,
    load_active_roadmap,
    select_next_batch,
)
from spectrum_systems.modules.runtime.system_cycle_operator import (  # noqa: E402
    SystemCycleOperatorError,
    run_system_cycle,
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _canonical_hash(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object in {path}")
    return payload


def _parse_csv_set(raw: str | None) -> set[str] | None:
    if raw is None:
        return None
    parsed = {item.strip() for item in raw.split(",") if item.strip()}
    return parsed or None


def _build_cycle_runner_result(*, timestamp: str, trace_id: str, run_id: str, next_decision_id: str, next_bundle_id: str) -> dict[str, Any]:
    seed = {
        "trace_id": trace_id,
        "run_id": run_id,
        "next_decision_id": next_decision_id,
        "next_bundle_id": next_bundle_id,
        "created_at": timestamp,
    }
    runner_id = f"CRR-{_canonical_hash(seed)[:12].upper()}"
    result = {
        "cycle_runner_result_id": runner_id,
        "schema_version": "1.0.0",
        "source_cycle_decision_id": next_decision_id,
        "source_cycle_input_bundle_id": next_bundle_id,
        "attempted_execution": True,
        "execution_status": "executed",
        "refusal_reason_codes": [],
        "refusal_severity": "expected",
        "executed_cycle_id": run_id,
        "emitted_artifact_refs": sorted(
            {
                f"roadmap_multi_batch_run_result:{run_id}",
                f"next_cycle_decision:{next_decision_id}",
                f"next_cycle_input_bundle:{next_bundle_id}",
            }
        ),
        "next_cycle_decision_ref": f"next_cycle_decision:{next_decision_id}",
        "next_cycle_input_bundle_ref": f"next_cycle_input_bundle:{next_bundle_id}",
        "error_detail": None,
        "replay_entry_point": {
            "input_artifact_refs": [f"next_cycle_decision:{next_decision_id}", f"next_cycle_input_bundle:{next_bundle_id}"],
            "decision_refs": [f"next_cycle_decision:{next_decision_id}"],
            "bundle_refs": [f"next_cycle_input_bundle:{next_bundle_id}"],
            "execution_refs": [f"roadmap_multi_batch_run_result:{run_id}"],
        },
        "created_at": timestamp,
        "trace_id": trace_id,
    }
    validate_artifact(result, "cycle_runner_result")
    return result


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Execute one governed batch from contracts/examples/system_roadmap.json")
    parser.add_argument("--system-roadmap", type=Path, default=REPO_ROOT / "contracts/examples/system_roadmap.json")
    parser.add_argument("--roadmap-artifact", type=Path, required=True)
    parser.add_argument("--selection-signals", type=Path, required=True)
    parser.add_argument("--authorization-signals", type=Path, required=True)
    parser.add_argument("--integration-inputs", type=Path, required=True)
    parser.add_argument("--pqx-state-path", type=Path, required=True)
    parser.add_argument("--pqx-runs-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--execution-policy", type=Path)
    parser.add_argument("--program-aligned-batches", help="Comma-separated allowlist of program-aligned batch ids")
    parser.add_argument("--disallow-continuation", action="store_true", help="Fail closed before selection.")
    parser.add_argument("--created-at")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    timestamp = args.created_at or _utc_now()

    try:
        system_roadmap = load_active_roadmap(args.system_roadmap)
        selected_batch_id = select_next_batch(
            system_roadmap,
            program_aligned_batch_ids=_parse_csv_set(args.program_aligned_batches),
            continuation_allowed=not args.disallow_continuation,
        )
    except RoadmapSelectionError as exc:
        print(json.dumps({"status": "refused", "reason": str(exc)}))
        return 1

    try:
        execution_roadmap = _load_json(args.roadmap_artifact)
        cycle = run_system_cycle(
            roadmap_artifact=execution_roadmap,
            selection_signals=_load_json(args.selection_signals),
            authorization_signals=_load_json(args.authorization_signals),
            integration_inputs=_load_json(args.integration_inputs),
            pqx_state_path=args.pqx_state_path,
            pqx_runs_root=args.pqx_runs_root,
            execution_policy=_load_json(args.execution_policy) if args.execution_policy else {"max_batches_per_run": 1},
            created_at=timestamp,
        )
    except (OSError, ValueError, json.JSONDecodeError, SystemCycleOperatorError) as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}))
        return 2

    updated = cycle["updated_roadmap"]
    run_result = cycle["roadmap_multi_batch_run_result"]
    trace_id = str(run_result.get("trace_id") or "trace-run-next-roadmap-batch")

    new_status = "blocked"
    for batch in updated.get("batches", []):
        if isinstance(batch, dict) and batch.get("batch_id") == selected_batch_id:
            new_status = str(batch.get("status") or "blocked")
            break

    progress_update = {
        "roadmap_id": system_roadmap["roadmap_id"],
        "batch_id": selected_batch_id,
        "new_status": "completed" if new_status == "completed" else "blocked",
        "reason_codes": [str(run_result.get("stop_reason") or "executed")],
        "trace_id": trace_id,
    }

    next_cycle_decision = cycle["next_cycle_decision"]
    next_cycle_input_bundle = cycle["next_cycle_input_bundle"]
    cycle_runner_result = _build_cycle_runner_result(
        timestamp=timestamp,
        trace_id=trace_id,
        run_id=str(run_result["run_id"]),
        next_decision_id=str(next_cycle_decision["cycle_decision_id"]),
        next_bundle_id=str(next_cycle_input_bundle["bundle_id"]),
    )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "cycle_runner_result.json").write_text(json.dumps(cycle_runner_result, indent=2) + "\n", encoding="utf-8")
    (args.output_dir / "roadmap_progress_update.json").write_text(json.dumps(progress_update, indent=2) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "status": "executed",
                "selected_batch_id": selected_batch_id,
                "cycle_runner_result": str(args.output_dir / "cycle_runner_result.json"),
                "roadmap_progress_update": str(args.output_dir / "roadmap_progress_update.json"),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
