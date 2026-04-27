#!/usr/bin/env python3
"""Run TLS-EXEC-01 (TLS-05..TLS-09) in deterministic fail-closed mode."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.modules.tls_dependency_graph.tls_exec_01 import TlsExecutionFailure
from spectrum_systems.modules.tls_dependency_graph.tls_exec_01 import run_tls_exec_01


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--priority-report",
        default=str(REPO_ROOT / "artifacts" / "system_dependency_priority_report.json"),
        help="Input priority report artifact path.",
    )
    parser.add_argument(
        "--out-dir",
        default=str(REPO_ROOT / "artifacts" / "tls"),
        help="Output directory for TLS-05..TLS-09 artifacts.",
    )
    parser.add_argument(
        "--top-level-priority-out",
        default=str(REPO_ROOT / "artifacts" / "system_dependency_priority_report.json"),
        help="Published top-level adjusted priority report.",
    )
    args = parser.parse_args(argv)

    try:
        outputs = run_tls_exec_01(
            priority_report_path=Path(args.priority_report),
            out_dir=Path(args.out_dir),
            top_level_priority_path=Path(args.top_level_priority_out),
        )
    except TlsExecutionFailure as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1

    summary = {
        "status": "ok",
        "phase_outputs": {
            "TLS-05": "tls_ranking_review_report.json",
            "TLS-06": ["system_dependency_priority_report.json", "ranking_adjustment_log.json"],
            "TLS-07": "tls_action_plan.json",
            "TLS-08": ["tls_control_input_artifact.json", "tls_owner_input_packet.json"],
            "TLS-09": ["tls_learning_record.json", "tls_weight_update_record.json"],
        },
        "top_5": [
            {"rank": row["rank"], "system_id": row["system_id"], "score": row["score"]}
            for row in outputs["updated_priority"].get("top_5", [])
        ],
    }
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
