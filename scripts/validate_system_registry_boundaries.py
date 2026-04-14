#!/usr/bin/env python3
"""Fail-closed boundary checks for docs/architecture/system_registry.md."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = REPO_ROOT / "docs" / "architecture" / "system_registry.md"
REGISTRY_ARTIFACT_PATH = REPO_ROOT / "contracts" / "examples" / "system_registry_artifact.json"

SYSTEM_HEADER_RE = re.compile(r"^\s*###\s+([A-Z0-9]+)\s*$")
FIELD_RE = re.compile(r"^\s*-\s+\*\*(role|owns|consumes|produces|must_not_do):\*\*\s*(.*)$")
LIST_ITEM_RE = re.compile(r"^\s*-\s+(.*)$")
ANY_FIELD_RE = re.compile(r"^\s*-\s+\*\*[a-z_]+:\*\*")


@dataclass
class SystemDefinition:
    name: str
    role: str
    owns: list[str]
    consumes: list[str]
    produces: list[str]
    must_not_do: list[str]


def parse_registry(path: Path) -> tuple[dict[str, SystemDefinition], str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    systems: dict[str, SystemDefinition] = {}
    current: str | None = None
    role = ""
    owns: list[str] = []
    consumes: list[str] = []
    produces: list[str] = []
    must_not_do: list[str] = []
    active_list: str | None = None

    def flush() -> None:
        nonlocal current, role, owns, consumes, produces, must_not_do, active_list
        if current is None:
            return
        systems[current] = SystemDefinition(
            name=current,
            role=role.strip(),
            owns=[item.strip() for item in owns if item.strip()],
            consumes=[item.strip() for item in consumes if item.strip()],
            produces=[item.strip() for item in produces if item.strip()],
            must_not_do=[item.strip() for item in must_not_do if item.strip()],
        )
        current = None
        role = ""
        owns = []
        consumes = []
        produces = []
        must_not_do = []
        active_list = None

    for line in lines:
        header_match = SYSTEM_HEADER_RE.match(line)
        if header_match:
            flush()
            current = header_match.group(1)
            continue

        if current is None:
            continue

        field_match = FIELD_RE.match(line)
        if field_match:
            field, remainder = field_match.groups()
            if field == "role":
                role = remainder.strip()
                active_list = None
            elif field == "owns":
                active_list = "owns"
            elif field == "consumes":
                active_list = "consumes"
            elif field == "produces":
                active_list = "produces"
            elif field == "must_not_do":
                active_list = "must_not_do"
            continue

        if active_list:
            if ANY_FIELD_RE.match(line):
                active_list = None
                continue
            item_match = LIST_ITEM_RE.match(line)
            if item_match:
                item = item_match.group(1).strip()
                if active_list == "owns":
                    owns.append(item)
                elif active_list == "consumes":
                    consumes.append(item)
                elif active_list == "produces":
                    produces.append(item)
                elif active_list == "must_not_do":
                    must_not_do.append(item)
            elif line.strip() and not line.lstrip().startswith("- "):
                active_list = None

    flush()
    return systems, "\n".join(lines)


def _combined_text(system: SystemDefinition) -> str:
    return " ".join([system.role, *system.owns, *system.must_not_do]).lower()


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    return any(term in text for term in terms)


def check_critical_family_uniqueness(systems: dict[str, SystemDefinition]) -> list[str]:
    errors: list[str] = []
    family_owner = {
        "execution": "PQX",
        "admission": "AEX",
        "trust/policy admissibility": "TPA",
        "review interpretation": "RIL",
        "repair diagnosis/planning": "FRE",
        "closure decisioning": "CDE",
        "enforcement": "SEL",
        "orchestration": "TLC",
        "program governance": "PRG",
    }
    family_markers = {
        "execution": {"execution", "execution_state_transitions", "execution_trace_emission"},
        "admission": {"execution_admission", "request_validation", "entrypoint_enforcement"},
        "trust/policy admissibility": {"trust_policy_application", "scope_gating"},
        "review interpretation": {"review_interpretation"},
        "repair diagnosis/planning": {"failure_diagnosis", "repair_plan_generation"},
        "closure decisioning": {"closure_decisions", "promotion_readiness_decisioning", "closure_lock_state"},
        "enforcement": {"enforcement", "fail_closed_blocking", "promotion_guarding"},
        "orchestration": {"orchestration", "subsystem_routing", "bounded_cycle_coordination"},
        "program governance": {"program_governance", "roadmap_alignment", "program_drift_management"},
    }

    for family, owner in family_owner.items():
        markers = family_markers[family]
        owning_systems = sorted(
            name
            for name, system in systems.items()
            if any(item in markers for item in system.owns)
        )
        if owner not in owning_systems:
            errors.append(
                f"{family}: expected owner {owner} missing ownership markers {sorted(markers)}"
            )
        if len(owning_systems) != 1:
            errors.append(
                f"{family}: expected exactly one owner ({owner}), found {owning_systems or 'none'}"
            )
    return errors


def check_forbidden_authority_patterns(systems: dict[str, SystemDefinition]) -> list[str]:
    errors: list[str] = []

    def owns_or_role_contains(system_name: str, *terms: str) -> bool:
        system = systems[system_name]
        combined = " ".join([system.role, *system.owns]).lower()
        return _contains_any(combined, tuple(term.lower() for term in terms))

    forbidden = [
        ("TLC", ("closure", "promotion_readiness", "promotion authority"), "TLC must not own closure/promotion authority"),
        ("RQX", ("interpretation semantics", "review_interpretation"), "RQX must not own interpretation semantics"),
        ("RQX", ("repair diagnosis", "repair_plan_generation", "failure_diagnosis"), "RQX must not own repair diagnosis"),
        ("SEL", ("review_interpretation", "policy interpretation", "trust_policy_application"), "SEL must not own review/policy interpretation"),
        ("PQX", ("closure_decisions", "closure decision"), "PQX must not own closure decisions"),
        ("AEX", ("trust_policy_application", "policy admissibility"), "AEX must not own trust/policy admissibility"),
        ("PRG", ("runtime execution authority", "execution_state_transitions", "execute bounded work"), "PRG must not own runtime execution authority"),
    ]

    for system_name, terms, message in forbidden:
        if owns_or_role_contains(system_name, *terms):
            errors.append(message)

    return errors


def check_drift_risks(systems: dict[str, SystemDefinition]) -> list[str]:
    errors: list[str] = []

    tlc = " ".join([systems["TLC"].role, *systems["TLC"].owns]).lower()
    pqx = " ".join([systems["PQX"].role, *systems["PQX"].owns]).lower()
    rqx = " ".join([systems["RQX"].role, *systems["RQX"].owns]).lower()
    ril = " ".join([systems["RIL"].role, *systems["RIL"].owns]).lower()
    sel = " ".join([systems["SEL"].role, *systems["SEL"].owns]).lower()
    prg = " ".join([systems["PRG"].role, *systems["PRG"].owns]).lower()

    if _contains_any(tlc, ("decision engine", "policy evaluation", "review interpretation", "admission validation")):
        errors.append("TLC drift: convenience decision/policy/interpretation logic detected")

    if _contains_any(pqx, ("temporary decision", "closure decision", "promotion readiness")):
        errors.append("PQX drift: temporary decision logic leaked into execution")

    if _contains_any(rqx, ("temporary decision", "closure decision", "promotion readiness")):
        errors.append("RQX drift: temporary decision logic leaked into review queue")

    if "review_interpretation" in ril and _contains_any(rqx, ("review_interpretation", "interpret review semantics")):
        errors.append("Review semantics duplicated across RIL and RQX")

    cde_owns_promotion = any("promotion_readiness" in item for item in systems["CDE"].owns)
    tlc_owns_promotion = any("promotion" in item for item in systems["TLC"].owns)
    sel_owns_promotion_ready = any("promotion_readiness" in item for item in systems["SEL"].owns)
    if not cde_owns_promotion or tlc_owns_promotion or sel_owns_promotion_ready:
        errors.append("Promotion readiness drift: must be owned only by CDE")

    if any("policy" in item for item in systems["SEL"].owns) or "policy" in systems["SEL"].role.lower():
        errors.append("Policy-check drift: SEL must not duplicate TPA policy admissibility")

    if _contains_any(prg, ("execution authority", "runtime control", "admission")):
        errors.append("Roadmap/execution bleed: PRG must stay out of runtime execution control")

    return errors


def check_repo_mutation_fail_closed(systems: dict[str, SystemDefinition], full_text: str) -> list[str]:
    errors: list[str] = []

    if "execution_admission" not in systems["AEX"].owns:
        errors.append("AEX must own execution_admission as repo-mutation entry point")

    required_doc_phrases = [
        "All Codex execution requests that create or modify repository state MUST enter through **AEX**.",
        "**PQX** MUST reject repo-writing execution that lacks AEX admission artifacts plus TLC-mediated lineage.",
        "Any attempt to invoke **TLC** or **PQX** directly for repo-mutating work without valid AEX/TLC lineage MUST fail closed.",
    ]
    for phrase in required_doc_phrases:
        if phrase not in full_text:
            errors.append(f"Entry invariant missing required fail-closed statement: {phrase}")

    if any("admission" in item for item in systems["TLC"].owns):
        errors.append("TLC must not own admission validation")

    return errors





def check_adv_owner_constraints(systems: dict[str, SystemDefinition]) -> list[str]:
    errors: list[str] = []
    if "execution" in systems["CHX"].owns or "execution_state_transitions" in systems["CHX"].owns:
        errors.append("CHX must not own runtime execution authority")
    if "decision_authority" in systems["DEX"].owns or "closure_decisions" in systems["DEX"].owns:
        errors.append("DEX must not own decision authority")
    if any("live" in item for item in systems["SIM"].owns):
        errors.append("SIM must not own live state mutation")
    if any("closure" in item for item in systems["PRX"].owns):
        errors.append("PRX must not own closure authority")
    if any("execution" in item for item in systems["CVX"].owns):
        errors.append("CVX must not own execution mutation")
    if any("bypass" in item for item in systems["HIX"].owns):
        errors.append("HIX must not own bypass behaviors")
    return errors



def check_extended_hardening_ownership(systems: dict[str, SystemDefinition]) -> list[str]:
    errors: list[str] = []
    required_owners = {
        "context_bundle_contracts": "CTX",
        "required_eval_registry": "EVL",
        "observability_contracts": "OBS",
        "lineage_completeness_rules": "LIN",
        "drift_signal_emission": "DRT",
        "slo_error_budget_artifacts": "SLO",
        "canary_rollout_artifacts": "REL",
        "eval_dataset_registry": "DAT",
        "judgment_artifact_requirements": "JDX",
        "judgment_record": "JDX",
        "reuse_record_artifacts": "RUX",
        "artifact_card_records": "XPL",
        "release_records": "REL",
        "dependency_graph_artifacts": "DAG",
        "external_runtime_provenance_contracts": "EXT",
        "policy_rollout_lifecycle": "POL",
        "prompt_registry_authority": "PRM",
        "route_candidate_records": "ROU",
        "human_override_artifacts": "HIT",
        "cost_budget_artifacts": "CAP",
        "security_guardrail_event_contracts": "SEC",
        "replay_integrity_validation": "REP",
        "entropy_accumulation_detection": "ENT",
        "interface_contract_registry": "CON",
        "source_translation_contracts": "TRN",
        "deterministic_normalization_rules": "NRM",
        "comparison_run_governance": "CMP",
        "retirement_lifecycle_rules": "RET",
        "abstention_taxonomy": "ABS",
        "cross_artifact_consistency_checks": "CRS",
        "migration_plan_contracts": "MIG",
        "query_index_manifest_authority": "QRY",
        "test_asset_registry": "TST",
        "risk_classification_taxonomy": "RSK",
        "evidence_sufficiency_scoring": "EVD",
        "supersession_rules": "SUP",
        "handoff_package_contracts": "HND",
        "trust_signal_synthesis_rules": "SYN",
    }
    for responsibility, owner in required_owners.items():
        owning = sorted(name for name, s in systems.items() if responsibility in s.owns)
        if owning != [owner]:
            errors.append(f"{responsibility}: expected unique owner {owner}, found {owning or 'none'}")
    return errors



def check_next_wave_boundaries(systems: dict[str, SystemDefinition]) -> list[str]:
    errors: list[str] = []
    for required in ("JDX", "RUX", "XPL", "REL", "DAG", "EXT"):
        if required not in systems:
            errors.append(f"missing required system definition: {required}")
    if "JDX" in systems and any("closure" in x for x in systems["JDX"].owns):
        errors.append("JDX must not own closure authority")
    if "DAG" in systems and any("execution" in x for x in systems["DAG"].owns):
        errors.append("DAG must not own execution")
    return errors


def check_next_phase_presence_and_io(systems: dict[str, SystemDefinition]) -> list[str]:
    errors: list[str] = []
    required = ("TRN", "NRM", "CMP", "RET", "ABS", "CRS", "MIG", "QRY", "TST", "RSK", "EVD", "SUP", "HND", "SYN")
    for name in required:
        if name not in systems:
            errors.append(f"missing required system definition: {name}")
            continue
        if not systems[name].consumes:
            errors.append(f"{name} must declare consumes list")
        if not systems[name].produces:
            errors.append(f"{name} must declare produces list")
    return errors


def check_doc_artifact_drift(systems: dict[str, SystemDefinition], artifact_path: Path) -> list[str]:
    errors: list[str] = []
    if not artifact_path.is_file():
        return [f"missing canonical registry artifact: {artifact_path}"]
    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    artifact_systems_raw = payload.get("systems")
    if not isinstance(artifact_systems_raw, list):
        return ["canonical registry artifact malformed: systems must be a list"]
    artifact_systems = {
        str(item.get("acronym") or "").strip().upper(): item
        for item in artifact_systems_raw
        if isinstance(item, dict)
    }

    protected_actions = {
        "execution": "PQX",
        "execution_admission": "AEX",
        "failure_diagnosis": "FRE",
        "review_interpretation": "RIL",
        "closure_decisions": "CDE",
        "enforcement": "SEL",
        "orchestration": "TLC",
    }
    for action, expected_owner in protected_actions.items():
        doc_owners = sorted(name for name, definition in systems.items() if action in definition.owns)
        artifact_owners = sorted(
            acronym
            for acronym, entry in artifact_systems.items()
            if isinstance(entry, dict) and action in [str(item).strip() for item in entry.get("owns", [])]
        )
        if doc_owners != [expected_owner] or artifact_owners != [expected_owner]:
            errors.append(
                f"doc/artifact drift: protected owner mismatch for {action} (doc={doc_owners}, artifact={artifact_owners})"
            )
    return errors

def run_all_checks(registry_path: Path = REGISTRY_PATH) -> list[str]:
    systems, full_text = parse_registry(registry_path)

    required_systems = {"TLC", "CDE", "RQX", "RIL", "FRE", "TPA", "SEL", "PRG", "AEX", "MAP", "PQX", "CHX", "DEX", "SIM", "PRX", "CVX", "HIX", "CAL", "POL", "AIL", "SCH", "DEP", "RCA", "QOS", "SIMX", "JDX", "RUX", "XPL", "REL", "DAG", "EXT", "CTX", "EVL", "OBS", "LIN", "DRT", "SLO", "REL", "DAT", "JDX", "PRM", "ROU", "HIT", "CAP", "SEC", "REP", "ENT", "CON", "TRN", "NRM", "CMP", "RET", "ABS", "CRS", "MIG", "QRY", "TST", "RSK", "EVD", "SUP", "HND", "SYN"}
    missing = sorted(required_systems - set(systems))
    errors: list[str] = []
    if missing:
        errors.append(f"Missing required systems in registry: {missing}")
        return errors

    errors.extend(check_critical_family_uniqueness(systems))
    errors.extend(check_forbidden_authority_patterns(systems))
    errors.extend(check_drift_risks(systems))
    errors.extend(check_repo_mutation_fail_closed(systems, full_text))
    errors.extend(check_adv_owner_constraints(systems))
    errors.extend(check_extended_hardening_ownership(systems))
    errors.extend(check_next_wave_boundaries(systems))
    errors.extend(check_next_phase_presence_and_io(systems))
    errors.extend(check_doc_artifact_drift(systems, REGISTRY_ARTIFACT_PATH))
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate system registry boundary hardening rules.")
    parser.add_argument(
        "--registry",
        default=str(REGISTRY_PATH),
        help="Path to docs/architecture/system_registry.md (default: %(default)s)",
    )
    args = parser.parse_args(argv)

    errors = run_all_checks(registry_path=Path(args.registry))
    if errors:
        print("System registry boundary validation FAILED:")
        for error in errors:
            print(f"  ERROR: {error}")
        return 1

    print("System registry boundary validation PASSED — no drift detected.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
