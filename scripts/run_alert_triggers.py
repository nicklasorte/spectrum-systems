#!/usr/bin/env python3
"""Build a governed alert_trigger artifact from a governed replay_result artifact."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from spectrum_systems.contracts import validate_artifact  # noqa: E402
from spectrum_systems.modules.runtime.alert_triggers import (  # noqa: E402
    AlertTriggerError,
    build_alert_trigger,
    load_alert_trigger_policy,
)


def _load_json(path: Path) -> Dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise AlertTriggerError(f"input file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise AlertTriggerError(f"input file is not valid JSON: {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise AlertTriggerError(f"input file must contain an object: {path}")
    return payload


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Build deterministic alert_trigger artifact.")
    parser.add_argument("--replay", required=True, help="Path to replay_result artifact JSON.")
    parser.add_argument("--policy", help="Optional path to alert_trigger_policy artifact JSON.")
    parser.add_argument("--trace-id", help="Optional explicit trace ID override.")
    parser.add_argument("--output", required=True, help="Output path for alert_trigger artifact JSON.")
    args = parser.parse_args(argv)

    replay_result = _load_json(Path(args.replay))
    policy_input = _load_json(Path(args.policy)) if args.policy else None
    policy = load_alert_trigger_policy(policy_input)

    trigger = build_alert_trigger(replay_result, policy=policy, trace_id=args.trace_id)
    validate_artifact(trigger, "alert_trigger")

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(trigger, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(trigger, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AlertTriggerError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)
