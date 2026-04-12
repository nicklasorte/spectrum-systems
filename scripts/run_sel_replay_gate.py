#!/usr/bin/env python3
"""Fail-closed SEL replay gate for CI runner outputs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.modules.runtime.sel_orchestration_runner import SELOrchestrationRunnerError, run_sel_replay_gate


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate SEL replay determinism for orchestration outputs.")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--decision-record", required=True)
    parser.add_argument("--action-record", required=True)
    args = parser.parse_args()

    try:
        replay = run_sel_replay_gate(
            output_dir=Path(args.output_dir),
            decision_record=_load(Path(args.decision_record)),
            action_record=_load(Path(args.action_record)),
        )
    except (SELOrchestrationRunnerError, OSError, json.JSONDecodeError, KeyError) as exc:
        print(str(exc), file=sys.stderr)
        return 2

    print(json.dumps(replay, indent=2))
    return 0 if replay.get("result") == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
