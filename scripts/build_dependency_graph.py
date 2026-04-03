#!/usr/bin/env python3
"""
Build the canonical ecosystem dependency graph from the control-plane sources.

Inputs:
- ecosystem/system-registry.json
- contracts/standards-manifest.json
- contracts/artifact-class-registry.json

Outputs (deterministic and sorted):
- ecosystem/dependency-graph.json
- artifacts/dependency-graph-summary.md
- artifacts/dependency-graph.mmd
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, Iterable, List, Set, Tuple


REPO_ROOT = Path(__file__).resolve().parents[1]
SYSTEM_REGISTRY_PATH = REPO_ROOT / "ecosystem" / "system-registry.json"
STANDARDS_MANIFEST_PATH = REPO_ROOT / "contracts" / "standards-manifest.json"
ARTIFACT_CLASS_REGISTRY_PATH = REPO_ROOT / "contracts" / "artifact-class-registry.json"
OUTPUT_JSON = REPO_ROOT / "ecosystem" / "dependency-graph.json"
OUTPUT_SUMMARY = REPO_ROOT / "artifacts" / "dependency-graph-summary.md"
OUTPUT_MERMAID = REPO_ROOT / "artifacts" / "dependency-graph.mmd"

EXPLICIT_ARTIFACT_TYPES: Set[str] = {
    "transcript",
    "meeting_minutes_record",
    "meeting_minutes_docx",
    "working_paper_input",
    "reviewer_comment_set",
    "comment_resolution_matrix",
    "comment_resolution_matrix_spreadsheet",
    "adjudicated_matrix",
    "updated_working_paper",
    "program_brief",
    "study_readiness_assessment",
    "next_best_action_memo",
}

LOOP_ARTIFACTS = {
    "coordination": "coordination_loop",
    "document_production": "document_production_loop",
    "cross_loop": "cross_loop",
    "governance": "governance_loop",
}

MANUAL_ARTIFACT_METADATA: Dict[str, Dict[str, str]] = {
    "transcript": {
        "artifact_class": "coordination",
        "description": "Raw meeting transcript captured before governance processing.",
    },
    "meeting_minutes_docx": {
        "artifact_class": "coordination",
        "description": "Rendered DOCX minutes distributed to participants.",
    },
    "comment_resolution_matrix_spreadsheet": {
        "artifact_class": "review",
        "description": "Spreadsheet representation of the governed comment resolution matrix.",
    },
    "adjudicated_matrix": {
        "artifact_class": "review",
        "description": "Approved adjudication state for reviewer comments.",
    },
    "updated_working_paper": {
        "artifact_class": "work",
        "description": "Working paper revision after adjudication or injection.",
    },
    "updated_working_paper_docx": {
        "artifact_class": "work",
        "description": "DOCX export of the updated working paper.",
    },
    "governance_guidance": {
        "artifact_class": "coordination",
        "description": "Narrative governance instructions emitted by spectrum-systems.",
    },
    "review_guidance": {
        "artifact_class": "review",
        "description": "Guidance documents steering reviewer expectations and rubric.",
    },
    "pipeline_run_manifest": {
        "artifact_class": "coordination",
        "description": "Structured manifest describing a pipeline run configuration and outputs.",
    },
    "governance_templates": {
        "artifact_class": "coordination",
        "description": "Template files used by system-factory when scaffolding governed repos.",
    },
    "scaffolded_repository_manifest": {
        "artifact_class": "coordination",
        "description": "Manifest describing the generated repository from system-factory.",
    },
    "coordination_loop": {
        "artifact_class": "coordination",
        "description": "Marker node for systems participating in the coordination loop.",
    },
    "document_production_loop": {
        "artifact_class": "work",
        "description": "Marker node for systems participating in the document production loop.",
    },
    "cross_loop": {
        "artifact_class": "coordination",
        "description": "Marker node for systems that orchestrate or advise across loops.",
    },
    "governance_loop": {
        "artifact_class": "coordination",
        "description": "Marker node for control-plane and governance functions.",
    },
}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sanitize_id(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]", "_", value)


def infer_artifact_class(artifact_type: str) -> str:
    lowered = artifact_type.lower()
    if any(keyword in lowered for keyword in ["policy", "governance", "control", "compliance"]):
        return "governance"
    if any(keyword in lowered for keyword in ["comment", "review"]):
        return "review"
    if any(keyword in lowered for keyword in ["working_paper", "study", "work"]):
        return "work"
    return "coordination"


def extract_systems(registry: List[dict]) -> List[dict]:
    systems: List[dict] = []
    for system in registry:
        systems.append(
            {
                "system_id": system["system_id"],
                "repo_name": system["repo_name"],
                "repo_type": system["repo_type"],
                "primary_loop_alignment": system.get("primary_loop_alignment", ""),
                "maturity_level": system.get("maturity_level"),
                "consumes_artifact_types": sorted(set(system.get("consumes_artifact_types", []))),
                "emits_artifact_types": sorted(set(system.get("emits_artifact_types", []))),
                "contract_dependencies": sorted(set(system.get("contract_dependencies", []))),
            }
        )
    systems.sort(key=lambda item: item["system_id"])
    return systems


def extract_contracts(standards_manifest: dict) -> Tuple[List[dict], Dict[str, dict]]:
    contracts: List[dict] = []
    contract_lookup: Dict[str, dict] = {}
    for contract in standards_manifest.get("contracts", []):
        record = {
            "contract_name": contract["artifact_type"],
            "artifact_class": contract["artifact_class"],
            "intended_consumers": sorted(set(contract.get("intended_consumers", []))),
            "related_artifact_types": [contract["artifact_type"]],
        }
        contracts.append(record)
        contract_lookup[record["contract_name"]] = contract

    contracts.sort(key=lambda item: item["contract_name"])
    return contracts, contract_lookup


def collect_artifact_types(
    systems: Iterable[dict], contracts: Iterable[dict], explicit_types: Set[str]
) -> Set[str]:
    artifact_types: Set[str] = set(explicit_types)
    for system in systems:
        artifact_types.update(system.get("consumes_artifact_types", []))
        artifact_types.update(system.get("emits_artifact_types", []))
    for contract in contracts:
        artifact_types.add(contract["contract_name"])

    artifact_types.update(LOOP_ARTIFACTS.values())
    return artifact_types


def build_artifacts(
    artifact_types: Set[str],
    contract_lookup: Dict[str, dict],
    producers: Dict[str, Set[str]],
    consumers: Dict[str, Set[str]],
) -> List[dict]:
    artifacts: List[dict] = []
    for artifact_type in sorted(artifact_types):
        manual = MANUAL_ARTIFACT_METADATA.get(artifact_type, {})
        contract = contract_lookup.get(artifact_type)

        artifact_class = manual.get("artifact_class") or (contract["artifact_class"] if contract else None)
        if not artifact_class:
            artifact_class = infer_artifact_class(artifact_type)

        description = manual.get("description") or ""
        if not description and contract:
            description = f"Governed artifact for contract `{artifact_type}`."
        if not description:
            description = f"{artifact_type.replace('_', ' ')} artifact."

        artifacts.append(
            {
                "artifact_type": artifact_type,
                "artifact_class": artifact_class,
                "description": description,
                "producing_systems": sorted(producers.get(artifact_type, [])),
                "consuming_systems": sorted(consumers.get(artifact_type, [])),
            }
        )
    return artifacts


def build_edges(systems: List[dict], contracts: List[dict]) -> List[dict]:
    edges: List[dict] = []
    seen: Set[Tuple[str, str, str, str, str]] = set()

    def add_edge(from_type: str, from_id: str, relation: str, to_type: str, to_id: str) -> None:
        key = (from_type, from_id, relation, to_type, to_id)
        if key in seen:
            return
        seen.add(key)
        edges.append(
            {
                "from_type": from_type,
                "from_id": from_id,
                "relation": relation,
                "to_type": to_type,
                "to_id": to_id,
            }
        )

    for system in systems:
        for artifact in system["emits_artifact_types"]:
            add_edge("system", system["system_id"], "emits", "artifact", artifact)
        for artifact in system["consumes_artifact_types"]:
            add_edge("system", system["system_id"], "consumes", "artifact", artifact)
        for contract in system["contract_dependencies"]:
            add_edge("system", system["system_id"], "depends_on", "contract", contract)

        loop_target = LOOP_ARTIFACTS.get(system.get("primary_loop_alignment", ""))
        if loop_target:
            add_edge("system", system["system_id"], "participates_in", "artifact", loop_target)

    for contract in contracts:
        for artifact_type in contract["related_artifact_types"]:
            add_edge("contract", contract["contract_name"], "validates_against", "artifact", artifact_type)
            add_edge("artifact", artifact_type, "governed_by", "contract", contract["contract_name"])

    edges.sort(key=lambda item: (item["from_type"], item["from_id"], item["relation"], item["to_type"], item["to_id"]))
    return edges


def render_summary(graph: dict) -> str:
    lines: List[str] = ["# Ecosystem Dependency Graph Summary", ""]

    lines.append("## Systems")
    for system in graph["systems"]:
        lines.append(
            f"- {system['system_id']} ({system['repo_type']}, loop={system['primary_loop_alignment']}, "
            f"maturity={system['maturity_level']}) consumes: {', '.join(system['consumes_artifact_types']) or '—'}; "
            f"emits: {', '.join(system['emits_artifact_types']) or '—'}; contracts: {', '.join(system['contract_dependencies']) or '—'}"
        )
    lines.append("")

    lines.append("## Artifacts")
    for artifact in graph["artifacts"]:
        lines.append(
            f"- {artifact['artifact_type']} [{artifact['artifact_class']}] "
            f"producers: {', '.join(artifact['producing_systems']) or '—'}; "
            f"consumers: {', '.join(artifact['consuming_systems']) or '—'}; "
            f"{artifact['description']}"
        )
    lines.append("")

    lines.append("## Contracts")
    for contract in graph["contracts"]:
        lines.append(
            f"- {contract['contract_name']} [{contract['artifact_class']}] "
            f"intended consumers: {', '.join(contract['intended_consumers']) or '—'}; "
            f"artifacts: {', '.join(contract['related_artifact_types'])}"
        )
    lines.append("")

    lines.append("## Loop Participation")
    loop_map: Dict[str, List[str]] = {loop: [] for loop in LOOP_ARTIFACTS.values()}
    for edge in graph["edges"]:
        if edge["relation"] == "participates_in":
            loop_map.setdefault(edge["to_id"], []).append(edge["from_id"])

    for loop_node, participants in sorted(loop_map.items()):
        lines.append(f"- {loop_node}: {', '.join(sorted(participants)) or '—'}")

    lines.append("")
    lines.append("Generated via scripts/build_dependency_graph.py from registry and standards sources.")
    return "\n".join(lines)


def render_mermaid(graph: dict) -> str:
    lines: List[str] = ["flowchart TD"]

    def system_node_id(system_id: str) -> str:
        return f"sys_{sanitize_id(system_id)}"

    def artifact_node_id(artifact_type: str) -> str:
        return f"art_{sanitize_id(artifact_type)}"

    def contract_node_id(contract_name: str) -> str:
        return f"con_{sanitize_id(contract_name)}"

    for system in graph["systems"]:
        node_id = system_node_id(system["system_id"])
        label = f'{node_id}["{system["system_id"]}\\n{system["repo_type"]}"]'
        lines.append(f"  {label}")

    for artifact in graph["artifacts"]:
        node_id = artifact_node_id(artifact["artifact_type"])
        label = f'{node_id}["{artifact["artifact_type"]}\\n{artifact["artifact_class"]}"]'
        lines.append(f"  {label}")

    for contract in graph["contracts"]:
        node_id = contract_node_id(contract["contract_name"])
        label = f'{node_id}["{contract["contract_name"]}\\ncontract"]'
        lines.append(f"  {label}")

    for edge in graph["edges"]:
        if edge["from_type"] == "system":
            from_id = system_node_id(edge["from_id"])
        elif edge["from_type"] == "artifact":
            from_id = artifact_node_id(edge["from_id"])
        else:
            from_id = contract_node_id(edge["from_id"])

        if edge["to_type"] == "system":
            to_id = system_node_id(edge["to_id"])
        elif edge["to_type"] == "artifact":
            to_id = artifact_node_id(edge["to_id"])
        else:
            to_id = contract_node_id(edge["to_id"])

        if edge["relation"] == "emits":
            lines.append(f"  {from_id} -->|emits| {to_id}")
        elif edge["relation"] == "consumes":
            lines.append(f"  {to_id} -->|consumes| {from_id}")
        elif edge["relation"] == "depends_on":
            lines.append(f"  {from_id} -. depends_on .-> {to_id}")
        elif edge["relation"] == "participates_in":
            lines.append(f"  {from_id} -. participates_in .-> {to_id}")
        elif edge["relation"] == "validates_against":
            lines.append(f"  {from_id} -->|validates| {to_id}")
        elif edge["relation"] == "governed_by":
            lines.append(f"  {from_id} -. governed_by .-> {to_id}")

    return "\n".join(lines) + "\n"


def main() -> int:
    system_registry = load_json(SYSTEM_REGISTRY_PATH)
    standards_manifest = load_json(STANDARDS_MANIFEST_PATH)
    artifact_class_registry = load_json(ARTIFACT_CLASS_REGISTRY_PATH)

    available_artifact_classes = {entry["name"] for entry in artifact_class_registry.get("artifact_classes", [])}

    systems = extract_systems(system_registry)
    contracts, contract_lookup = extract_contracts(standards_manifest)

    producers: Dict[str, Set[str]] = {}
    consumers: Dict[str, Set[str]] = {}
    for system in systems:
        for artifact in system["emits_artifact_types"]:
            producers.setdefault(artifact, set()).add(system["system_id"])
        for artifact in system["consumes_artifact_types"]:
            consumers.setdefault(artifact, set()).add(system["system_id"])

    artifact_types = collect_artifact_types(systems, contracts, EXPLICIT_ARTIFACT_TYPES)
    artifacts = build_artifacts(artifact_types, contract_lookup, producers, consumers)

    for artifact in artifacts:
        if artifact["artifact_class"] not in available_artifact_classes:
            artifact["artifact_class"] = infer_artifact_class(artifact["artifact_type"])

    artifacts.sort(key=lambda item: item["artifact_type"])
    edges = build_edges(systems, contracts)

    graph = {
        "systems": systems,
        "artifacts": artifacts,
        "contracts": contracts,
        "edges": edges,
    }

    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps(graph, indent=2, sort_keys=False), encoding="utf-8")

    OUTPUT_SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_SUMMARY.write_text(render_summary(graph), encoding="utf-8")

    OUTPUT_MERMAID.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_MERMAID.write_text(render_mermaid(graph), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
