#!/usr/bin/env python3

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS_DIR = REPO_ROOT / "artifacts"
POLICY_REGISTRY_PATH = REPO_ROOT / "governance" / "policies" / "policy-registry.json"
ECOSYSTEM_REGISTRY_PATH = REPO_ROOT / "ecosystem" / "ecosystem-registry.json"
STANDARDS_MANIFEST_PATH = REPO_ROOT / "contracts" / "standards-manifest.json"
MANIFESTS_DIR = REPO_ROOT / "governance" / "examples" / "manifests"
DEPENDENCY_GRAPH_PATH = REPO_ROOT / "artifacts" / "ecosystem-dependency-graph.json"


def load_json(path: Path) -> Optional[dict]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError:
        return None


def load_policy_registry() -> List[dict]:
    registry = load_json(POLICY_REGISTRY_PATH)
    if not registry or "policies" not in registry:
        raise RuntimeError("Policy registry is missing or invalid.")
    return [policy for policy in registry["policies"] if policy.get("enabled", False)]


def load_manifests() -> Dict[str, dict]:
    manifests = {}
    for manifest_path in sorted(MANIFESTS_DIR.glob("*.json")):
        data = load_json(manifest_path)
        if not data:
            continue
        repo_name = data.get("repo_name") or manifest_path.stem.split(".")[0]
        manifests[repo_name] = data
    return manifests


def build_registry_maps(registry: dict) -> Tuple[Dict[str, dict], Dict[str, dict]]:
    repos = registry.get("repositories", []) if registry else []
    repo_map = {}
    system_map = {}
    for entry in repos:
        name = entry.get("repo_name")
        if name:
            repo_map[name] = entry
        system_id = entry.get("system_id")
        if system_id:
            system_map[system_id] = entry
    return repo_map, system_map


def build_standards_contracts(standards: dict) -> Dict[str, dict]:
    contracts = standards.get("contracts", []) if standards else []
    return {contract.get("artifact_type"): contract for contract in contracts if contract.get("artifact_type")}


def make_result(policy: dict, subject: str, status: str, message: str, evidence: Optional[List[str]] = None) -> dict:
    return {
        "policy_id": policy["policy_id"],
        "severity": policy["severity"],
        "status": status,
        "subject": subject,
        "message": message,
        "evidence": evidence or [],
    }


def evaluate_gov_001(policy: dict, manifests: Dict[str, dict], registry_map: Dict[str, dict]) -> List[dict]:
    results = []
    for repo_name in sorted(manifests):
        if repo_name in registry_map:
            results.append(
                make_result(
                    policy,
                    repo_name,
                    "pass",
                    "Repository is present in the ecosystem registry.",
                )
            )
        else:
            results.append(
                make_result(
                    policy,
                    repo_name,
                    "fail",
                    "Repository not found in ecosystem registry.",
                    [repo_name],
                )
            )
    return results


def evaluate_gov_002(policy: dict, manifests: Dict[str, dict], registry_map: Dict[str, dict]) -> List[dict]:
    results = []
    registered_repos = sorted(name for name, entry in registry_map.items() if entry.get("repo_type") != "governance")
    for repo_name in registered_repos:
        if repo_name in manifests:
            results.append(
                make_result(
                    policy,
                    repo_name,
                    "pass",
                    "Governance manifest discovered for registered system.",
                )
            )
        else:
            results.append(
                make_result(
                    policy,
                    repo_name,
                    "fail",
                    "Registered system is missing a governance manifest in examples.",
                    [repo_name],
                )
            )
    return results


def evaluate_gov_003(policy: dict, manifests: Dict[str, dict], registry_map: Dict[str, dict]) -> List[dict]:
    results = []
    for repo_name in sorted(manifests):
        manifest = manifests[repo_name]
        registry_entry = registry_map.get(repo_name)
        manifest_system = manifest.get("system_id")
        registry_system = registry_entry.get("system_id") if registry_entry else None
        if registry_entry and manifest_system == registry_system:
            results.append(
                make_result(
                    policy,
                    repo_name,
                    "pass",
                    "Manifest system_id matches registry entry.",
                )
            )
        else:
            evidence = [f"manifest:{manifest_system}", f"registry:{registry_system}"]
            message = "Manifest system_id does not align with registry entry."
            if not registry_entry:
                message = "Registry entry missing; cannot validate system_id."
            results.append(make_result(policy, repo_name, "fail", message, evidence))
    return results


def evaluate_gov_004(policy: dict, manifests: Dict[str, dict], standards_contracts: Dict[str, dict]) -> List[dict]:
    results = []
    for repo_name in sorted(manifests):
        manifest = manifests[repo_name]
        contracts = manifest.get("contracts", {}) or {}
        missing = [name for name in sorted(contracts) if name not in standards_contracts]
        if missing:
            results.append(
                make_result(
                    policy,
                    repo_name,
                    "fail",
                    "Manifest pins contracts that are not in the standards manifest.",
                    missing,
                )
            )
        else:
            results.append(
                make_result(
                    policy,
                    repo_name,
                    "pass",
                    "All manifest contract pins exist in the standards manifest.",
                )
            )
    return results


def evaluate_gov_005(policy: dict, manifests: Dict[str, dict], registry_map: Dict[str, dict]) -> List[dict]:
    results = []
    for repo_name in sorted(manifests):
        manifest = manifests[repo_name]
        registry_entry = registry_map.get(repo_name)
        if not registry_entry:
            results.append(
                make_result(
                    policy,
                    repo_name,
                    "warning",
                    "Registry entry missing; cannot confirm declared contracts.",
                    [],
                )
            )
            continue

        manifest_contracts = set((manifest.get("contracts") or {}).keys())
        registry_contracts = set(registry_entry.get("contracts", []))
        undeclared = sorted(manifest_contracts - registry_contracts)

        if undeclared:
            results.append(
                make_result(
                    policy,
                    repo_name,
                    "warning",
                    "Manifest pins contracts that are not declared for this repo in the registry.",
                    undeclared,
                )
            )
        else:
            results.append(
                make_result(
                    policy,
                    repo_name,
                    "pass",
                    "Manifest contracts are consistent with registry declarations.",
                )
            )
    return results


def evaluate_gov_006(policy: dict, standards_contracts: Dict[str, dict], registry_map: Dict[str, dict]) -> List[dict]:
    results = []
    for contract_name in sorted(standards_contracts):
        contract = standards_contracts[contract_name]
        intended_consumers = contract.get("intended_consumers", []) or []
        missing = [consumer for consumer in sorted(intended_consumers) if consumer not in registry_map]
        if missing:
            results.append(
                make_result(
                    policy,
                    contract_name,
                    "warning",
                    "Intended consumers are not registered in the ecosystem registry.",
                    missing,
                )
            )
        else:
            results.append(
                make_result(
                    policy,
                    contract_name,
                    "pass",
                    "All intended consumers exist in the ecosystem registry.",
                )
            )
    return results


def evaluate_gov_007(policy: dict, dependency_graph: Optional[dict], system_map: Dict[str, dict]) -> List[dict]:
    if not dependency_graph:
        return [
            make_result(
                policy,
                "ecosystem-dependency-graph",
                "fail",
                "Dependency graph artifact is missing; cannot validate system resolution.",
                [],
            )
        ]

    results = []
    systems = dependency_graph.get("systems", {}) or {}
    for system_id in sorted(systems):
        graph_entry = systems[system_id]
        registry_entry = system_map.get(system_id)
        repo_name = graph_entry.get("repo_name")
        registry_repo = registry_entry.get("repo_name") if registry_entry else None
        if registry_entry and registry_repo == repo_name:
            results.append(
                make_result(
                    policy,
                    system_id,
                    "pass",
                    "Dependency graph system resolves to registry repository.",
                )
            )
        else:
            evidence = [f"graph:{repo_name}", f"registry:{registry_repo}"]
            message = "System in dependency graph is missing from registry or repo name does not match."
            results.append(make_result(policy, system_id, "fail", message, evidence))
    return results


def evaluate_gov_008(policy: dict, repo_root: Path) -> List[dict]:
    suspicious = ["src", "package", "spectrum_systems", "app", "service"]
    found = [name for name in suspicious if (repo_root / name).is_dir()]
    if found:
        return [
            make_result(
                policy,
                "spectrum-systems",
                "warning",
                "Governance repository contains implementation-like directories.",
                sorted(found),
            )
        ]
    return [
        make_result(
            policy,
            "spectrum-systems",
            "pass",
            "No implementation directories detected in governance repository.",
        )
    ]


def evaluate_policies(policies: List[dict]) -> dict:
    ecosystem_registry = load_json(ECOSYSTEM_REGISTRY_PATH) or {}
    standards_manifest = load_json(STANDARDS_MANIFEST_PATH) or {}
    dependency_graph = load_json(DEPENDENCY_GRAPH_PATH)
    manifests = load_manifests()

    registry_map, system_map = build_registry_maps(ecosystem_registry)
    standards_contracts = build_standards_contracts(standards_manifest)

    results: List[dict] = []
    for policy in sorted(policies, key=lambda p: p["policy_id"]):
        pid = policy["policy_id"]
        if pid == "GOV-001":
            results.extend(evaluate_gov_001(policy, manifests, registry_map))
        elif pid == "GOV-002":
            results.extend(evaluate_gov_002(policy, manifests, registry_map))
        elif pid == "GOV-003":
            results.extend(evaluate_gov_003(policy, manifests, registry_map))
        elif pid == "GOV-004":
            results.extend(evaluate_gov_004(policy, manifests, standards_contracts))
        elif pid == "GOV-005":
            results.extend(evaluate_gov_005(policy, manifests, registry_map))
        elif pid == "GOV-006":
            results.extend(evaluate_gov_006(policy, standards_contracts, registry_map))
        elif pid == "GOV-007":
            results.extend(evaluate_gov_007(policy, dependency_graph, system_map))
        elif pid == "GOV-008":
            results.extend(evaluate_gov_008(policy, REPO_ROOT))

    results.sort(key=lambda r: (r["policy_id"], r["subject"]))

    summary = {
        "policies_evaluated": len(results),
        "repos_checked": len(manifests),
        "errors": sum(1 for r in results if r["severity"] == "error" and r["status"] == "fail"),
        "warnings": sum(
            1
            for r in results
            if (r["severity"] == "warning" and r["status"] in {"warning", "fail"})
        ),
    }

    return {
        "run_date": datetime.now(timezone.utc).isoformat(),
        "summary": summary,
        "results": results,
    }


def write_json_report(report: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)


def write_summary_markdown(report: dict, path: Path) -> None:
    results = report["results"]
    errors = [r for r in results if r["status"] == "fail"]
    warnings = [r for r in results if r["status"] == "warning"]

    lines = []
    lines.append("# Policy Engine Summary")
    lines.append(f"Run date: {report['run_date']}")
    lines.append(f"Policies evaluated: {report['summary']['policies_evaluated']}")
    lines.append(f"Repos checked: {report['summary']['repos_checked']}")
    lines.append(f"Errors: {report['summary']['errors']}")
    lines.append(f"Warnings: {report['summary']['warnings']}")
    lines.append("")

    lines.append("## Error Findings")
    if errors:
        for item in errors:
            lines.append(f"- {item['policy_id']} ({item['subject']}): {item['message']}")
    else:
        lines.append("- None")
    lines.append("")

    lines.append("## Warning Findings")
    if warnings:
        for item in warnings:
            lines.append(f"- {item['policy_id']} ({item['subject']}): {item['message']}")
    else:
        lines.append("- None")
    lines.append("")

    lines.append("## Findings by Repo")
    grouped: Dict[str, List[dict]] = {}
    for item in results:
        grouped.setdefault(item["subject"], []).append(item)

    for subject in sorted(grouped):
        lines.append(f"### {subject}")
        for item in sorted(grouped[subject], key=lambda r: r["policy_id"]):
            tag = "ERROR" if item["status"] == "fail" else "WARN" if item["status"] == "warning" else "PASS"
            lines.append(f"- [{tag}] {item['policy_id']}: {item['message']}")
        lines.append("")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def main() -> int:
    try:
        policies = load_policy_registry()
        report = evaluate_policies(policies)
        report_path = ARTIFACTS_DIR / "policy-engine-report.json"
        summary_path = ARTIFACTS_DIR / "policy-engine-summary.md"
        write_json_report(report, report_path)
        write_summary_markdown(report, summary_path)
    except Exception as exc:  # pragma: no cover
        sys.stderr.write(f"Policy engine failed: {exc}\n")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
