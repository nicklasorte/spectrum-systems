#!/usr/bin/env python3
"""D3L-MASTER-01 Phase 0 — registry contract artifact builder.

Reads the parsed registry artifact (artifacts/tls/system_registry_dependency_graph.json)
and emits artifacts/tls/d3l_registry_contract.json with the explicit
ranking_universe and maturity_universe fields the dashboard consumes.

The dashboard MUST NEVER invent systems, never include future / demoted /
deprecated / merged ids in the ranking universe, and never render forbidden
labels (H01, TLS-BND-*, D3L-FIX-*) as nodes.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEPENDENCY_GRAPH = REPO_ROOT / "artifacts" / "tls" / "system_registry_dependency_graph.json"
OUTPUT_PATH = REPO_ROOT / "artifacts" / "tls" / "d3l_registry_contract.json"

FORBIDDEN_NODE_EXAMPLES = [
    "H01",
    "TLS-BND-01",
    "TLS-BND-02",
    "D3L-FIX-01",
    "D3L-FIX-02",
    "RFX",
    "MET",
    "METS",
    "BUNDLE-01",
    "BUNDLE-02",
    "roadmap_label",
    "prompt_label",
    "red_team_report_id",
]


def build_contract(graph: dict) -> dict:
    active_ids = [row["system_id"] for row in graph.get("active_systems", [])]
    future_ids = [row["system_id"] for row in graph.get("future_systems", [])]
    demoted_ids = [row["system_id"] for row in graph.get("merged_or_demoted", [])]
    return {
        "artifact_type": "d3l_registry_contract",
        "phase": "D3L-MASTER-01",
        "schema_version": "d3l-master-01.v1",
        "generated_at": datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source_artifact": str(DEPENDENCY_GRAPH.relative_to(REPO_ROOT)),
        "active_system_ids": sorted(active_ids),
        "future_system_ids": sorted(future_ids),
        "deprecated_or_merged_system_ids": sorted(demoted_ids),
        "excluded_ids": sorted(future_ids + demoted_ids),
        "ranking_universe": sorted(active_ids),
        "maturity_universe": sorted(active_ids),
        "forbidden_node_examples": FORBIDDEN_NODE_EXAMPLES,
        "rules": [
            "ranking_universe = active_system_ids only",
            "maturity_universe = active_system_ids only",
            "future / deprecated / merged ids must not appear in ranking or maturity",
            "forbidden_node_examples must never become graph nodes",
            "dashboard never invents nodes — registry is canonical",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    parser.add_argument("--source", type=Path, default=DEPENDENCY_GRAPH)
    args = parser.parse_args(argv)

    if not args.source.exists():
        print(f"missing source artifact: {args.source}", file=sys.stderr)
        return 2
    graph = json.loads(args.source.read_text(encoding="utf-8"))
    contract = build_contract(graph)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(contract, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    try:
        rel = args.output.relative_to(REPO_ROOT)
    except ValueError:
        rel = args.output
    print(f"wrote {rel}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
