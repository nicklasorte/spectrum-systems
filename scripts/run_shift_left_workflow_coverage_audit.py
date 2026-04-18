#!/usr/bin/env python3
"""Workflow-level SLH front-door coverage audit and fail-closed enforcement artifact emitter."""
from __future__ import annotations

import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.modules.runtime.pra_nsx_prg_loop import (  # noqa: E402
    con_workflow_coverage_audit,
    con_workflow_front_door_enforcement,
)


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    coverage = con_workflow_coverage_audit(repo_root=REPO_ROOT)
    enforcement = con_workflow_front_door_enforcement(coverage=coverage)

    out_dir = REPO_ROOT / "outputs" / "shift_left_hardening"
    _write(out_dir / "workflow_coverage_audit.json", coverage)
    _write(out_dir / "workflow_front_door_enforcement.json", enforcement)

    print(json.dumps({"coverage": coverage["status"], "enforcement": enforcement["status"]}, indent=2))
    return 0 if enforcement["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
