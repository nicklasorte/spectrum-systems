#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from scripts.run_contract_preflight import REPO_ROOT, ChangedPathDetectionResult, detect_changed_paths


class WrapperBuildError(RuntimeError):
    """Raised when wrapper evidence is insufficient for governed execution."""


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build canonical preflight PQX wrapper with bounded diff-resolution")
    parser.add_argument("--base-ref", default="origin/main", help="Git base ref used for diff detection")
    parser.add_argument("--head-ref", default="HEAD", help="Git head ref used for diff detection")
    parser.add_argument("--changed-path", action="append", default=[], help="Optional explicit changed path")
    parser.add_argument(
        "--output-path",
        default="outputs/contract_preflight/preflight_pqx_task_wrapper.json",
        help="Wrapper artifact output path",
    )
    parser.add_argument(
        "--template-path",
        default="contracts/examples/codex_pqx_task_wrapper.json",
        help="Template wrapper payload path",
    )
    parser.add_argument(
        "--trace-output-path",
        default="outputs/contract_preflight/preflight_wrapper_changed_path_trace.json",
        help="Optional changed-path detection trace output path",
    )
    return parser.parse_args()


def _load_template(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("artifact_type") != "codex_pqx_task_wrapper":
        raise WrapperBuildError(f"template at {path} is not codex_pqx_task_wrapper")
    return payload


def _changed_path_trace(detection: ChangedPathDetectionResult) -> dict[str, Any]:
    return {
        "changed_path_detection_mode": detection.changed_path_detection_mode,
        "fallback_used": detection.fallback_used,
        "trust_level": detection.trust_level,
        "bounded_runtime": detection.bounded_runtime,
        "reason_codes": list(detection.reason_codes),
        "warnings": list(detection.warnings),
        "refs_attempted": list(detection.refs_attempted),
        "ref_resolution_records": list(detection.ref_resolution_records),
        "changed_paths": list(detection.changed_paths),
    }


def build_wrapper_payload(
    *,
    template_payload: dict[str, Any],
    detection: ChangedPathDetectionResult,
) -> dict[str, Any]:
    changed_paths = sorted(set(str(path).strip() for path in detection.changed_paths if str(path).strip()))

    if detection.trust_level == "insufficient":
        raise WrapperBuildError("insufficient changed-path evidence; bounded diff-resolution exhausted")
    if not changed_paths:
        raise WrapperBuildError("changed_paths resolved to empty; refusing silent wrapper construction")

    payload = dict(template_payload)
    payload["changed_paths"] = changed_paths

    execution_intent = dict(payload.get("execution_intent") or {})
    execution_intent.setdefault("execution_context", "pqx_governed")
    execution_intent.setdefault("mode", "governed")
    payload["execution_intent"] = execution_intent

    return payload


def main() -> int:
    try:
        args = _parse_args()
        template_path = Path(args.template_path)
        output_path = Path(args.output_path)
        trace_output_path = Path(args.trace_output_path)

        detection = detect_changed_paths(
            repo_root=REPO_ROOT,
            base_ref=args.base_ref,
            head_ref=args.head_ref,
            explicit=list(args.changed_path or []),
        )
        template_payload = _load_template(template_path)
        wrapper_payload = build_wrapper_payload(template_payload=template_payload, detection=detection)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(wrapper_payload, indent=2) + "\n", encoding="utf-8")

        trace_output_path.parent.mkdir(parents=True, exist_ok=True)
        trace_output_path.write_text(json.dumps(_changed_path_trace(detection), indent=2) + "\n", encoding="utf-8")

        print(
            json.dumps(
                {
                    "status": "ok",
                    "output_path": str(output_path),
                    "trace_output_path": str(trace_output_path),
                    "changed_path_detection_mode": detection.changed_path_detection_mode,
                    "trust_level": detection.trust_level,
                    "fallback_used": detection.fallback_used,
                    "changed_paths_count": len(wrapper_payload.get("changed_paths") or []),
                },
                sort_keys=True,
            )
        )
        return 0
    except WrapperBuildError as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
