#!/usr/bin/env python3
"""D3L-MASTER-01 Phase 6 — MVP graph artifact builder.

Emits artifacts/tls/d3l_mvp_graph.json. MVP boxes are product-level
capabilities, NEVER registry systems. Each mapping is validated against
the registry contract; rejected mappings surface as warnings but never
become graph nodes in the 3LS graph.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = REPO_ROOT / "artifacts" / "tls" / "d3l_registry_contract.json"
OUTPUT_PATH = REPO_ROOT / "artifacts" / "tls" / "d3l_mvp_graph.json"

MVP_BOXES = [
    {"id": "transcript_ingestion", "label": "Transcript Ingestion", "description": "inbound transcript admission and validation", "maps_to_systems": ["AEX", "CTX"]},
    {"id": "multi_pass_extraction", "label": "Multi-pass Extraction", "description": "bounded extraction passes over context bundles", "maps_to_systems": ["PQX", "CTX"]},
    {"id": "context_builder", "label": "Context Builder", "description": "context bundle assembly + admission", "maps_to_systems": ["CTX", "PRM"]},
    {"id": "paper_generator", "label": "Paper Generator", "description": "governed paper synthesis with HOP-evaluated harness", "maps_to_systems": ["PQX", "HOP"]},
    {"id": "eval_system", "label": "Eval System", "description": "required eval coverage and gate decisions", "maps_to_systems": ["EVL"]},
    {"id": "judgment_engine", "label": "Judgment Engine", "description": "judgment artifact semantics and lifecycle", "maps_to_systems": ["JDX", "JSX"]},
    {"id": "control_loop", "label": "Control Loop", "description": "closure decisions and trust/policy adjudication", "maps_to_systems": ["CDE", "TPA", "SEL"]},
    {"id": "learning_loop", "label": "Learning Loop", "description": "failure diagnosis + repair planning, feeds eval candidates", "maps_to_systems": ["FRE", "RIL", "RAX"]},
    {"id": "slo_system", "label": "SLO System", "description": "observability + reliability error-budget governance", "maps_to_systems": ["OBS", "SLO"]},
]

MVP_EDGES = [
    {"from": "transcript_ingestion", "to": "multi_pass_extraction"},
    {"from": "multi_pass_extraction", "to": "context_builder"},
    {"from": "context_builder", "to": "paper_generator"},
    {"from": "paper_generator", "to": "eval_system"},
    {"from": "eval_system", "to": "judgment_engine"},
    {"from": "judgment_engine", "to": "control_loop"},
    {"from": "control_loop", "to": "learning_loop"},
    {"from": "learning_loop", "to": "slo_system"},
]


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def build_mvp_graph_report() -> dict:
    contract = _load(CONTRACT_PATH)
    active = set(contract.get("active_system_ids", [])) if contract else set()
    warnings: list[str] = []
    if not contract:
        warnings.append("mvp_graph_contract_missing")
    validated: list[dict] = []
    for box in MVP_BOXES:
        admitted = []
        rejected = []
        for sid in box["maps_to_systems"]:
            if not active:
                rejected.append(sid)
                continue
            if sid in active:
                admitted.append(sid)
            else:
                rejected.append(sid)
        validated.append({
            "box_id": box["id"],
            "admitted_systems": admitted,
            "rejected_systems": rejected,
        })
        if rejected:
            warnings.append(f"mvp_box_rejected_mapping:{box['id']}:{','.join(rejected)}")
    return {
        "artifact_type": "d3l_mvp_graph",
        "phase": "D3L-MASTER-01",
        "schema_version": "d3l-master-01.v1",
        "generated_at": _now_iso(),
        "boxes": MVP_BOXES,
        "edges": MVP_EDGES,
        "validated_mappings": validated,
        "warnings": warnings,
        "rules": [
            "MVP boxes are product-level capabilities, NOT registry systems",
            "MVP boxes MUST never become 3LS graph nodes",
            "every maps_to_systems entry MUST be in active_system_ids",
        ],
        "sources": {"contract": str(CONTRACT_PATH.relative_to(REPO_ROOT)) if contract else None},
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    args = parser.parse_args(argv)
    report = build_mvp_graph_report()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    try:
        rel = args.output.relative_to(REPO_ROOT)
    except ValueError:
        rel = args.output
    print(f"wrote {rel} boxes={len(report['boxes'])} warnings={len(report['warnings'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
