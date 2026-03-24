#!/usr/bin/env python3
"""Run AG-01 canonical agent runtime golden path."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPTS_DIR.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from spectrum_systems.modules.runtime.agent_golden_path import GoldenPathConfig, run_agent_golden_path  # noqa: E402


def _parse_json_arg(raw: str) -> dict:
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("JSON argument must decode to an object")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run AG-01 canonical agent runtime golden path")
    parser.add_argument("--task-type", default="meeting_minutes", help="Context assembly task type")
    parser.add_argument(
        "--input-json",
        default='{"transcript":"Golden path runtime input"}',
        help="JSON object for context primary input",
    )
    parser.add_argument(
        "--context-config-json",
        default="{}",
        help="JSON object for context assembly config",
    )
    parser.add_argument(
        "--source-artifacts-json",
        default='[{"artifact_id":"artifact-001","kind":"seed"}]',
        help="JSON array of source artifact objects",
    )
    parser.add_argument("--output-dir", default="outputs/agent_golden_path", help="Artifact output directory")
    parser.add_argument("--fail-agent-execution", action="store_true", help="Force agent execution tool failure")
    parser.add_argument("--emit-invalid-structured-output", action="store_true", help="Force invalid structured output schema")
    parser.add_argument("--fail-eval-execution", action="store_true", help="Force eval stage failure")
    parser.add_argument(
        "--force-eval-status",
        choices=["pass", "fail"],
        help="Force deterministic eval status for control-path testing",
    )
    parser.add_argument("--force-control-block", action="store_true", help="Force control decision into block/freeze path")
    args = parser.parse_args(argv)

    input_payload = _parse_json_arg(args.input_json)
    context_config = _parse_json_arg(args.context_config_json)
    source_artifacts = json.loads(args.source_artifacts_json)
    if not isinstance(source_artifacts, list):
        raise ValueError("--source-artifacts-json must be a JSON array")

    artifacts = run_agent_golden_path(
        GoldenPathConfig(
            task_type=args.task_type,
            input_payload=input_payload,
            source_artifacts=source_artifacts,
            context_config=context_config,
            output_dir=Path(args.output_dir),
            fail_agent_execution=args.fail_agent_execution,
            emit_invalid_structured_output=args.emit_invalid_structured_output,
            fail_eval_execution=args.fail_eval_execution,
            force_eval_status=args.force_eval_status,
            force_control_block=args.force_control_block,
        )
    )

    print(json.dumps({"artifacts_emitted": sorted(artifacts.keys())}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
