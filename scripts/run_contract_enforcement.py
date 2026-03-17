#!/usr/bin/env python3
"""
Cross-repo contract enforcement for the spectrum-systems governance architecture.

Reads governance manifests, the ecosystem registry, and the canonical standards
manifest to validate contract usage across all governed repositories.

Validation rules applied
------------------------
contract-exists   : Every contract pin declared in a governance manifest must
                    reference an artifact_type that exists in the standards manifest.
version-pin       : Every pinned contract version must match the canonical version
                    from the standards manifest (exact match required unless the
                    repo explicitly opts out, which is not yet supported).
consumer-consistency : Repos listed as intended_consumers of a contract in the
                    standards manifest should declare that contract in their
                    governance manifest.  Gaps are reported as warnings.

Repos that require a governance manifest (manifest_required=true in the ecosystem
registry) but do not yet have one are reported as "not_yet_enforceable" and do NOT
cause CI failure — they are surfaced clearly so they can be remediated.

Outputs
-------
- governance/reports/contract-dependency-graph.json  (machine-readable)
- docs/governance-reports/contract-enforcement-report.md  (human-readable)

Exit codes
----------
0 — no enforcement failures  (warnings and not-yet-enforceable do not count)
1 — one or more real enforcement failures

CI output format
----------------
[contract-enforcement] repo=<name> system_id=<id> contract=<type>[@<ver>] rule=<rule> error=<msg>
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
ECOSYSTEM_REGISTRY_PATH = REPO_ROOT / "ecosystem" / "ecosystem-registry.json"
STANDARDS_MANIFEST_PATH = REPO_ROOT / "contracts" / "standards-manifest.json"
MANIFESTS_DIR = REPO_ROOT / "governance" / "examples" / "manifests"
CONTRACT_GRAPH_PATH = REPO_ROOT / "governance" / "reports" / "contract-dependency-graph.json"
ENFORCEMENT_REPORT_PATH = REPO_ROOT / "docs" / "governance-reports" / "contract-enforcement-report.md"


# ─────────────────────────────────────────────────────────────────────────────
# Data loaders
# ─────────────────────────────────────────────────────────────────────────────

def load_json(path: Path) -> Optional[dict]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None


def load_ecosystem_registry() -> Dict[str, dict]:
    """Return {repo_name: registry_entry} for all repos in the ecosystem registry."""
    data = load_json(ECOSYSTEM_REGISTRY_PATH) or {}
    return {
        entry["repo_name"]: entry
        for entry in data.get("repositories", [])
        if entry.get("repo_name")
    }


def load_standards_contracts() -> Dict[str, dict]:
    """Return {artifact_type: contract_entry} from the canonical standards manifest."""
    data = load_json(STANDARDS_MANIFEST_PATH) or {}
    return {
        c["artifact_type"]: c
        for c in data.get("contracts", [])
        if c.get("artifact_type")
    }


def load_governance_manifests() -> Dict[str, dict]:
    """Return {repo_name: manifest} for all .spectrum-governance.json files."""
    manifests: Dict[str, dict] = {}
    for path in sorted(MANIFESTS_DIR.glob("*.spectrum-governance.json")):
        data = load_json(path)
        if data:
            repo_name = data.get("repo_name") or path.stem.split(".")[0]
            manifests[repo_name] = data
    return manifests


# ─────────────────────────────────────────────────────────────────────────────
# Enforcement logic helpers
# ─────────────────────────────────────────────────────────────────────────────

def _failure(repo: str, system_id: Optional[str], contract: str, rule: str, error: str) -> dict:
    return {"repo": repo, "system_id": system_id or "", "contract": contract,
            "rule": rule, "error": error}


def _warning(repo: str, system_id: Optional[str], contract: str, rule: str, message: str) -> dict:
    return {"repo": repo, "system_id": system_id or "", "contract": contract,
            "rule": rule, "message": message}


def check_repo_contracts(
    repo_name: str,
    system_id: Optional[str],
    manifest: dict,
    standards: Dict[str, dict],
) -> Tuple[List[dict], List[dict]]:
    """
    Validate a single repo's governance manifest against the standards manifest.

    Returns (failures, warnings).  Failures cause CI to exit non-zero;
    warnings are surfaced but do not block.
    """
    failures: List[dict] = []
    warnings: List[dict] = []
    contracts = manifest.get("contracts") or {}

    for artifact_type, pinned_version in sorted(contracts.items()):
        # Rule: contract-exists
        if artifact_type not in standards:
            failures.append(_failure(
                repo_name, system_id, artifact_type, "contract-exists",
                f"'{artifact_type}' is not defined in the standards manifest",
            ))
            continue

        # Rule: version-pin (exact match required)
        canonical = standards[artifact_type]["schema_version"]
        if pinned_version != canonical:
            failures.append(_failure(
                repo_name, system_id, f"{artifact_type}@{pinned_version}", "version-pin",
                f"expected {canonical}, found {pinned_version}",
            ))

    return failures, warnings


def check_consumer_consistency(
    standards: Dict[str, dict],
    manifests: Dict[str, dict],
    registry: Dict[str, dict],
) -> Tuple[List[dict], List[dict]]:
    """
    For each contract in the standards manifest, check that repos declared
    as intended_consumers actually pin the contract in their governance manifest.

    Repos without manifest_required=true or without a manifest yet are skipped
    (not-yet-enforceable state is handled separately).

    Returns (failures, warnings).  Consumer consistency gaps are warnings,
    not hard failures, because the intended_consumers list may be aspirational.
    """
    failures: List[dict] = []
    warnings: List[dict] = []

    for artifact_type, contract_entry in sorted(standards.items()):
        intended_consumers = contract_entry.get("intended_consumers") or []
        canonical_version = contract_entry["schema_version"]

        for consumer_repo in intended_consumers:
            reg_entry = registry.get(consumer_repo)
            if reg_entry is None:
                # Not in registry — flagged by GOV-006 in the policy engine
                continue
            if not reg_entry.get("manifest_required", False):
                continue
            manifest = manifests.get(consumer_repo)
            if manifest is None:
                # No manifest yet — not_yet_enforceable
                continue

            system_id = manifest.get("system_id")
            consumer_contracts = manifest.get("contracts") or {}
            if artifact_type not in consumer_contracts:
                warnings.append(_warning(
                    consumer_repo, system_id, artifact_type, "consumer-consistency",
                    f"repo is listed as intended_consumer of '{artifact_type}' "
                    f"(canonical v{canonical_version}) but does not declare it "
                    f"in its governance manifest",
                ))

    return failures, warnings


# ─────────────────────────────────────────────────────────────────────────────
# Contract dependency graph builder
# ─────────────────────────────────────────────────────────────────────────────

def build_contract_dependency_graph(
    registry: Dict[str, dict],
    manifests: Dict[str, dict],
    standards: Dict[str, dict],
    per_repo_results: Dict[str, dict],
    generated_at: str,
) -> dict:
    """
    Build the machine-readable cross-repo contract dependency graph.

    For each repo:
    - repo_name, repo_type, system_id
    - contracts_consumed (with pinned and canonical versions, drift flag)
    - contracts_produced (not yet tracked in the data model — empty list)
    - validation_status: pass | fail | warning | not_yet_enforceable | governance-repo

    Also includes a reverse index: contract → consumers.
    """
    repos: List[dict] = []
    contract_index: Dict[str, dict] = {}

    for repo_name in sorted(registry):
        reg_entry = registry[repo_name]
        manifest = manifests.get(repo_name)
        result = per_repo_results.get(repo_name, {})
        system_id = (manifest or {}).get("system_id") or reg_entry.get("system_id") or ""

        if not reg_entry.get("manifest_required", False):
            status = "governance-repo"
        elif manifest is None:
            status = "not_yet_enforceable"
        else:
            repo_failures = result.get("failures", [])
            repo_warnings = result.get("warnings", [])
            if repo_failures:
                status = "fail"
            elif repo_warnings:
                status = "warning"
            else:
                status = "pass"

        contracts_consumed: List[dict] = []
        if manifest:
            for artifact_type, pinned_version in sorted((manifest.get("contracts") or {}).items()):
                canonical = standards.get(artifact_type, {}).get("schema_version", "unknown")
                contracts_consumed.append({
                    "contract": artifact_type,
                    "pinned_version": pinned_version,
                    "canonical_version": canonical,
                    "drift": pinned_version != canonical,
                })
                if artifact_type not in contract_index:
                    contract_index[artifact_type] = {
                        "canonical_version": canonical,
                        "status": standards.get(artifact_type, {}).get("status", "unknown"),
                        "consumers": [],
                    }
                contract_index[artifact_type]["consumers"].append(repo_name)

        repos.append({
            "repo_name": repo_name,
            "repo_type": reg_entry.get("repo_type", ""),
            "system_id": system_id,
            "contracts_consumed": contracts_consumed,
            "contracts_produced": [],
            "validation_status": status,
            "failures": result.get("failures", []),
            "warnings": result.get("warnings", []),
        })

    for entry in contract_index.values():
        entry["consumers"].sort()

    return {
        "schema_version": "1.0.0",
        "generated_at": generated_at,
        "source_manifest": "contracts/standards-manifest.json",
        "repos": repos,
        "contract_index": dict(sorted(contract_index.items())),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Output formatters
# ─────────────────────────────────────────────────────────────────────────────

def format_enforcement_line(item: dict) -> str:
    """Return a structured enforcement log line for CI output."""
    repo = item.get("repo", "")
    system_id = item.get("system_id", "")
    contract = item.get("contract", "")
    rule = item.get("rule", "")
    error = item.get("error", item.get("message", ""))
    return (
        f"[contract-enforcement] repo={repo} system_id={system_id} "
        f"contract={contract} rule={rule} error={error}"
    )


def write_dependency_graph(graph: dict) -> None:
    CONTRACT_GRAPH_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONTRACT_GRAPH_PATH.write_text(json.dumps(graph, indent=2), encoding="utf-8")


def write_enforcement_report(
    graph: dict,
    all_failures: List[dict],
    all_warnings: List[dict],
    not_yet_enforceable: List[str],
    generated_at: str,
) -> None:
    repos = graph["repos"]
    passes = [r for r in repos if r["validation_status"] == "pass"]
    fails = [r for r in repos if r["validation_status"] == "fail"]
    warns = [r for r in repos if r["validation_status"] == "warning"]
    nyes = [r for r in repos if r["validation_status"] == "not_yet_enforceable"]

    lines = [
        "# Cross-Repo Contract Enforcement Report",
        "",
        f"Generated: {generated_at}",
        f"Source: `contracts/standards-manifest.json`",
        "",
        "## Summary",
        "",
        "| Status | Count |",
        "|--------|-------|",
        f"| Pass | {len(passes)} |",
        f"| Fail | {len(fails)} |",
        f"| Warning | {len(warns)} |",
        f"| Not Yet Enforceable | {len(nyes)} |",
        f"| Total Inspected | {len(repos)} |",
        "",
        "## Repos Inspected",
        "",
    ]

    badge_map = {
        "pass": "✅ PASS",
        "fail": "❌ FAIL",
        "warning": "⚠️ WARNING",
        "not_yet_enforceable": "🔲 NOT YET ENFORCEABLE",
        "governance-repo": "🏛 GOVERNANCE REPO",
    }
    for repo in repos:
        badge = badge_map.get(repo["validation_status"], repo["validation_status"].upper())
        sid = f" `{repo['system_id']}`" if repo["system_id"] else ""
        lines.append(f"- **{repo['repo_name']}**{sid} — {badge}")

    lines += ["", "## Enforcement Failures", ""]
    if all_failures:
        for f in all_failures:
            lines.append(f"`{format_enforcement_line(f)}`")
            lines.append("")
    else:
        lines.append("None.")

    lines += ["", "## Warnings", ""]
    if all_warnings:
        for w in all_warnings:
            lines.append(f"- `{format_enforcement_line(w)}`")
    else:
        lines.append("None.")

    lines += ["", "## Not Yet Enforceable", ""]
    if not_yet_enforceable:
        for repo in sorted(not_yet_enforceable):
            lines.append(f"- **{repo}**: `manifest_required=true` but no governance manifest found.")
        lines += [
            "",
            "> These repos are not failed by CI. Add a governance manifest under "
            "`governance/examples/manifests/` to enable enforcement.",
        ]
    else:
        lines.append("All governed repos have governance manifests.")

    lines += ["", "## Remediation Actions", ""]
    if all_failures:
        lines.append("### Enforcement Failures (must fix)")
        for f in all_failures:
            rule = f.get("rule", "")
            repo = f.get("repo", "")
            contract = f.get("contract", "")
            error = f.get("error", "")
            if rule == "contract-exists":
                lines.append(
                    f"- **{repo}**: Remove or replace `{contract}` — "
                    "it is not defined in the canonical standards manifest."
                )
            elif rule == "version-pin":
                lines.append(
                    f"- **{repo}**: Update version pin for `{contract}` in governance manifest ({error})."
                )
            else:
                lines.append(
                    f"- **{repo}**: Fix `{rule}` violation for contract `{contract}`: {error}."
                )
        lines.append("")

    if all_warnings:
        lines.append("### Warnings (recommended)")
        for w in all_warnings:
            rule = w.get("rule", "")
            repo = w.get("repo", "")
            contract = w.get("contract", "")
            message = w.get("message", "")
            lines.append(f"- **{repo}**: `{rule}` on `{contract}` — {message}.")
        lines.append("")

    if not all_failures and not all_warnings:
        lines.append("No actions required.")

    ENFORCEMENT_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    ENFORCEMENT_REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ─────────────────────────────────────────────────────────────────────────────
# Orchestration
# ─────────────────────────────────────────────────────────────────────────────

def run_enforcement(
    registry: Dict[str, dict],
    standards: Dict[str, dict],
    manifests: Dict[str, dict],
) -> Tuple[List[dict], List[dict], List[str], Dict[str, dict]]:
    """
    Run all enforcement checks and return (failures, warnings, not_yet_enforceable,
    per_repo_results).

    This function is separated from main() so it can be unit-tested without
    running the full script.
    """
    all_failures: List[dict] = []
    all_warnings: List[dict] = []
    not_yet_enforceable: List[str] = []
    per_repo_results: Dict[str, dict] = {}

    for repo_name in sorted(registry):
        reg_entry = registry[repo_name]
        if not reg_entry.get("manifest_required", False):
            continue

        manifest = manifests.get(repo_name)
        if manifest is None:
            not_yet_enforceable.append(repo_name)
            per_repo_results[repo_name] = {"failures": [], "warnings": []}
            continue

        system_id = manifest.get("system_id")
        failures, warnings = check_repo_contracts(repo_name, system_id, manifest, standards)
        per_repo_results[repo_name] = {"failures": failures, "warnings": warnings}
        all_failures.extend(failures)
        all_warnings.extend(warnings)

    cc_failures, cc_warnings = check_consumer_consistency(standards, manifests, registry)
    for f in cc_failures:
        per_repo_results.setdefault(f["repo"], {"failures": [], "warnings": []})
        per_repo_results[f["repo"]]["failures"].append(f)
    for w in cc_warnings:
        per_repo_results.setdefault(w["repo"], {"failures": [], "warnings": []})
        per_repo_results[w["repo"]]["warnings"].append(w)
    all_failures.extend(cc_failures)
    all_warnings.extend(cc_warnings)

    return all_failures, all_warnings, not_yet_enforceable, per_repo_results


def main() -> int:
    registry = load_ecosystem_registry()
    standards = load_standards_contracts()
    manifests = load_governance_manifests()

    all_failures, all_warnings, not_yet_enforceable, per_repo_results = run_enforcement(
        registry, standards, manifests
    )

    for f in all_failures:
        print(format_enforcement_line(f))
    for w in all_warnings:
        print(format_enforcement_line(w))
    for repo in not_yet_enforceable:
        print(
            f"[contract-enforcement] repo={repo} status=not_yet_enforceable "
            f"reason=no governance manifest found"
        )

    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    graph = build_contract_dependency_graph(
        registry, manifests, standards, per_repo_results, generated_at
    )
    write_dependency_graph(graph)
    write_enforcement_report(graph, all_failures, all_warnings, not_yet_enforceable, generated_at)

    print(
        f"\n[contract-enforcement] graph written to "
        f"{CONTRACT_GRAPH_PATH.relative_to(REPO_ROOT)}"
    )
    print(
        f"[contract-enforcement] report written to "
        f"{ENFORCEMENT_REPORT_PATH.relative_to(REPO_ROOT)}"
    )
    print(
        f"\n[contract-enforcement] summary: failures={len(all_failures)} "
        f"warnings={len(all_warnings)} not_yet_enforceable={len(not_yet_enforceable)}"
    )

    return 1 if all_failures else 0


if __name__ == "__main__":
    sys.exit(main())
