#!/usr/bin/env python3
"""Build canonical preflight PQX wrapper using changed-path resolution."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from spectrum_systems.modules.runtime.changed_path_resolution import resolve_changed_paths  # noqa: E402
from spectrum_systems.modules.runtime.preflight_ref_normalization import (  # noqa: E402
    normalize_preflight_ref_context,
)


def _stable_hash(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load_example(name: str) -> dict:
    path = _REPO_ROOT / "contracts" / "examples" / f"{name}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _write_preflight_hardening_artifacts(*, output_dir: Path, run_id: str, trace_id: str, step_id: str) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    refs: dict[str, str] = {}
    now = _now_iso()

    eval_payload = deepcopy(_load_example("pqx_execution_eval_result"))
    eval_payload["eval_id"] = f"pqx-eval-{_stable_hash([run_id, step_id, 'eval'])[:12]}"
    eval_payload["run_id"] = run_id
    eval_payload["trace_id"] = trace_id
    eval_payload["slice_id"] = step_id
    eval_payload["generated_at"] = now
    eval_path = output_dir / "preflight.pqx_execution_eval_result.json"
    eval_path.write_text(json.dumps(eval_payload, indent=2) + "\n", encoding="utf-8")
    refs["eval"] = str(eval_path.relative_to(_REPO_ROOT))

    readiness_payload = deepcopy(_load_example("pqx_execution_readiness_record"))
    readiness_payload["readiness_id"] = f"pqx-readiness-{_stable_hash([run_id, step_id, 'readiness'])[:12]}"
    readiness_payload["eval_result_ref"] = refs["eval"]
    readiness_payload["generated_at"] = now
    readiness_path = output_dir / "preflight.pqx_execution_readiness_record.json"
    readiness_path.write_text(json.dumps(readiness_payload, indent=2) + "\n", encoding="utf-8")
    refs["readiness"] = str(readiness_path.relative_to(_REPO_ROOT))

    effectiveness_payload = deepcopy(_load_example("pqx_execution_effectiveness_record"))
    effectiveness_payload["record_id"] = f"pqx-effectiveness-{_stable_hash([run_id, step_id, 'effectiveness'])[:12]}"
    effectiveness_payload["slice_id"] = step_id
    effectiveness_payload["generated_at"] = now
    effectiveness_path = output_dir / "preflight.pqx_execution_effectiveness_record.json"
    effectiveness_path.write_text(json.dumps(effectiveness_payload, indent=2) + "\n", encoding="utf-8")
    refs["effectiveness"] = str(effectiveness_path.relative_to(_REPO_ROOT))

    recurrence_payload = deepcopy(_load_example("pqx_execution_recurrence_record"))
    recurrence_payload["record_id"] = f"pqx-recurrence-{_stable_hash([run_id, step_id, 'recurrence'])[:12]}"
    recurrence_payload["run_id"] = run_id
    recurrence_payload["generated_at"] = now
    recurrence_path = output_dir / "preflight.pqx_execution_recurrence_record.json"
    recurrence_path.write_text(json.dumps(recurrence_payload, indent=2) + "\n", encoding="utf-8")
    refs["recurrence"] = str(recurrence_path.relative_to(_REPO_ROOT))

    bundle_payload = deepcopy(_load_example("pqx_execution_bundle"))
    bundle_payload["bundle_id"] = f"pqx-exec-bundle-{_stable_hash([run_id, step_id, 'bundle'])[:12]}"
    bundle_payload["run_id"] = run_id
    bundle_payload["trace_id"] = trace_id
    bundle_payload["eval_result_ref"] = refs["eval"]
    bundle_payload["readiness_ref"] = refs["readiness"]
    bundle_payload["effectiveness_ref"] = refs["effectiveness"]
    bundle_payload["recurrence_ref"] = refs["recurrence"]
    bundle_payload["generated_at"] = now
    bundle_path = output_dir / "preflight.pqx_execution_bundle.json"
    bundle_path.write_text(json.dumps(bundle_payload, indent=2) + "\n", encoding="utf-8")
    refs["bundle"] = str(bundle_path.relative_to(_REPO_ROOT))
    return refs


def _parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build preflight PQX wrapper")
    parser.add_argument("--base-ref", default="")
    parser.add_argument("--head-ref", default="")
    parser.add_argument("--event-name", default=None)
    parser.add_argument("--template", default="contracts/examples/codex_pqx_task_wrapper.json")
    parser.add_argument("--output", default="outputs/contract_preflight/preflight_pqx_task_wrapper.json")
    parser.add_argument("--changed-path", action="append", default=[])
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    args = _parse_args(argv)
    template_path = _REPO_ROOT / args.template
    if not template_path.exists():
        print(f"ERROR: wrapper template missing: {template_path}", file=sys.stderr)
        return 2

    ref_context = normalize_preflight_ref_context(
        event_name=args.event_name,
        cli_base_ref=args.base_ref,
        cli_head_ref=args.head_ref,
        env=os.environ,
    )
    if not ref_context.valid:
        print(
            f"ERROR: preflight ref normalization failed ({ref_context.reason_code}): {ref_context.invalid_reason}",
            file=sys.stderr,
        )
        return 2

    resolution = resolve_changed_paths(
        repo_root=_REPO_ROOT,
        base_ref=ref_context.base_ref,
        head_ref=ref_context.head_ref,
        explicit=args.changed_path,
    )

    if resolution.insufficient_context:
        print(
            "ERROR: changed-path resolution insufficient; cannot build authoritative preflight wrapper.",
            file=sys.stderr,
        )
        return 2

    payload = json.loads(template_path.read_text(encoding="utf-8"))
    payload["changed_paths"] = resolution.changed_paths
    run_id = str(payload.get("task_identity", {}).get("run_id") or "preflight-run")
    step_id = str(payload.get("task_identity", {}).get("step_id") or "AI-01")
    trace_id = f"trace:preflight:{run_id}:{step_id}"
    hardening_refs = _write_preflight_hardening_artifacts(
        output_dir=_REPO_ROOT / "outputs" / "contract_preflight",
        run_id=run_id,
        trace_id=trace_id,
        step_id=step_id,
    )
    governance = payload.get("governance")
    if isinstance(governance, dict):
        governance["authority_evidence_ref"] = "artifacts/pqx_runs/preflight.pqx_slice_execution_record.json"
    metadata = payload.get("metadata")
    if isinstance(metadata, dict):
        metadata["authority_notes"] = (
            "preflight_hardening_refs:"
            f"eval={hardening_refs['eval']};readiness={hardening_refs['readiness']};"
            f"effectiveness={hardening_refs['effectiveness']};recurrence={hardening_refs['recurrence']};"
            f"bundle={hardening_refs['bundle']}"
        )
    resolution_payload = {
        "changed_path_detection_mode": resolution.changed_path_detection_mode,
        "resolution_mode": resolution.resolution_mode,
        "trust_level": resolution.trust_level,
        "bounded_runtime": resolution.bounded_runtime,
        "refs_attempted": resolution.refs_attempted,
        "warnings": resolution.warnings,
        "hardening_artifact_refs": hardening_refs,
        "ref_context": ref_context.as_dict(),
    }

    output_path = _REPO_ROOT / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    resolution_path = output_path.with_name("preflight_changed_path_resolution.json")
    resolution_path.write_text(json.dumps(resolution_payload, indent=2) + "\n", encoding="utf-8")
    print(str(output_path.relative_to(_REPO_ROOT)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
