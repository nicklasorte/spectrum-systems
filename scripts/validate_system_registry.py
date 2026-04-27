#!/usr/bin/env python3
"""Validate canonical system registry structure and registry-to-code conformance."""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = REPO_ROOT / "docs" / "architecture" / "system_registry.md"
RUNTIME_DIR = REPO_ROOT / "spectrum_systems" / "modules" / "runtime"

REQUIRED_FIELDS = {
    "Purpose",
    "Failure Prevented",
    "Signal Improved",
    "Canonical Artifacts Owned",
    "Primary Code Paths",
    "Status",
}
IGNORED_RUNTIME_PREFIXES = {
    "RUN", "TOP", "PRE", "TAX", "PMH", "MVP", "BNE", "BAX", "CAX",
    "RFX",  # cross-system phase label declared in docs/roadmaps/rfx_cross_system_roadmap.md
}

# Active-system → protected authority cluster. Used to detect cross-claims
# where an active system declares ownership of an authority belonging to
# a different active system (e.g. GOV claiming TPA, TLC claiming CDE closure).
PROTECTED_AUTHORITY_BY_SYSTEM: dict[str, set[str]] = {
    "PQX": {"execution"},
    "CDE": {"closure", "promotion_readiness_decisioning", "closure_lock_state"},
    "TLC": {"orchestration", "subsystem_routing", "bounded_cycle_coordination"},
    "TPA": {"trust_policy_application", "scope_gating"},
    "SEL": {"enforcement", "fail_closed_blocking", "promotion_guarding"},
    "RIL": {"review_interpretation"},
    "GOV": {"certification_evidence_packaging"},
    "PRA": {"promotion_readiness_artifacts"},
    "EVL": {"required_eval_registry"},
    "REP": {"replay_integrity_validation"},
    "LIN": {"lineage_completeness_rules"},
    "CTX": {"context_bundle_contracts"},
    "OBS": {"observability_contracts"},
    "SLO": {"slo_error_budget_artifacts"},
    "JDX": {"judgment_artifact_requirements", "judgment_record"},
    "JSX": {"judgment_lifecycle_rules"},
}

# Demoted/non-authoritative systems must NOT declare these substrings in
# their `owns` field. The forbidden tokens encode authority-claim attempts.
DEMOTED_FORBIDDEN_OWNS: dict[str, tuple[str, ...]] = {
    "RDX": ("execute_runtime_work", "decide_policy_authority"),
    "PRG": ("own_runtime_execution", "decide_policy_authority"),
    "HNX": ("execute_work", "issue_closure_state_decisions"),
    "RQX": ("own_review_interpretation",),
    "CHX": ("own_runtime_execution",),
    "DEX": ("own_closure_decisions",),
    "SIM": ("own_live_state_mutation",),
    "PRX": ("own_closure_authority",),
    "CVX": ("own_execution_mutation",),
    "HIX": ("own_bypass_behaviors",),
    "CAL": ("own_policy_authority",),
    "AIL": ("own_control_decisions",),
    "SCH": ("own_execution_authority",),
    "DEP": ("own_control_decisions",),
    "RCA": ("own_enforcement_authority",),
    "QOS": ("own_policy_authority",),
    "SIMX": ("own_runtime_mutation",),
    "RUX": ("own_control_decisions",),
    "XPL": ("own_closure_authority",),
    "REL": ("own_policy_authority",),
    "DAG": ("own_execution_authority",),
    "EXT": ("own_policy_authority",),
    "DRT": ("own_closure_decisions",),
    "DAT": ("own_control_decisions",),
    "ROU": ("own_execution_authority",),
    "HIT": ("own_policy_authority",),
    "ENT": ("own_enforcement_authority",),
    "CON": ("own_policy_authority",),
    "TRN": ("own_context_admission",),
    "NRM": ("own_context_admission",),
    "CMP": ("own_eval_gate_authority",),
    "RET": ("own_promotion_authority",),
    "ABS": ("own_control_authority",),
    "CRS": ("own_control_decisions",),
    "MIG": ("own_policy_authority",),
    "QRY": ("own_context_admission",),
    "TST": ("own_eval_gate_authority",),
    "RSK": ("own_closure_authority",),
    "EVD": ("own_policy_authority",),
    "SUP": ("own_judgment_semantics",),
    "HND": ("own_execution_authority",),
    "SYN": ("own_policy_authority",),
    "XRL": ("own_policy_authority",),
}


@dataclass
class SystemEntry:
    acronym: str
    fields: dict[str, str]


def parse_active_systems(text: str) -> list[SystemEntry]:
    section_match = re.search(
        r"## Active executable systems\n(.*?)(?:\n## Merged or demoted systems)",
        text,
        flags=re.S,
    )
    if not section_match:
        return []
    section = section_match.group(1)

    systems: list[SystemEntry] = []
    for block in re.split(r"\n(?=###\s+[A-Z]{3}\s*$)", section.strip(), flags=re.M):
        head = re.match(r"###\s+([A-Z]{3})\n", block)
        if not head:
            continue
        acronym = head.group(1)
        fields: dict[str, str] = {}
        current_key: str | None = None
        for line in block.splitlines():
            match = re.match(r"- \*\*([^*]+):\*\*\s*(.*)", line)
            if match:
                current_key = match.group(1).strip()
                fields[current_key] = match.group(2).strip()
                continue
            if current_key and line.strip().startswith("- `"):
                fields[current_key] = (fields[current_key] + " " + line.strip()).strip()
        systems.append(SystemEntry(acronym=acronym, fields=fields))
    return systems


def parse_future_systems(text: str) -> set[str]:
    section_match = re.search(
        r"## Future / placeholder systems\n(.*?)(?:\n## Artifact families and supporting capabilities)",
        text,
        flags=re.S,
    )
    if not section_match:
        return set()
    section = section_match.group(1)
    return set(re.findall(r"\|\s*([A-Z]{3})\s*\|", section))


def parse_future_systems_with_rationale(text: str) -> dict[str, str]:
    """Return mapping of placeholder acronym → rationale text (may be empty)."""
    section_match = re.search(
        r"## Future / placeholder systems\n(.*?)(?:\n## Artifact families and supporting capabilities)",
        text,
        flags=re.S,
    )
    if not section_match:
        return {}
    out: dict[str, str] = {}
    for line in section_match.group(1).splitlines():
        m = re.match(r"\|\s*([A-Z]{3})\s*\|\s*([^|]*)\|\s*([^|]*)\|", line)
        if m:
            out[m.group(1).strip()] = m.group(3).strip()
    return out


def parse_system_definitions(text: str) -> dict[str, dict[str, Any]]:
    """Parse the `## System Definitions` blocks and return acronym → fields.

    Each definition block contributes keys: status, owns, role, must_not_do, etc.
    """
    section_match = re.search(r"## System Definitions\n(.*)", text, flags=re.S)
    if not section_match:
        return {}
    body = section_match.group(1)
    blocks = re.split(r"\n(?=###\s+[A-Z]{2,8}\s*$)", body.strip(), flags=re.M)
    out: dict[str, dict[str, Any]] = {}
    for block in blocks:
        head = re.match(r"###\s+([A-Z]{2,8})\s*\n", block)
        if not head:
            continue
        acronym = head.group(1)
        fields: dict[str, Any] = {
            "status": "",
            "role": "",
            "owns": [],
            "consumes": [],
            "produces": [],
            "must_not_do": [],
        }
        current_key: str | None = None
        for line in block.splitlines():
            field_match = re.match(
                r"-\s+\*\*(status|role|owns|consumes|produces|must_not_do):\*\*\s*(.*)",
                line,
            )
            if field_match:
                key = field_match.group(1)
                remainder = field_match.group(2).strip()
                if key in {"status", "role"}:
                    fields[key] = remainder
                    current_key = None
                else:
                    current_key = key
                continue
            if current_key:
                bullet = re.match(r"\s*-\s+(.+)$", line)
                if bullet:
                    val = bullet.group(1).strip()
                    if val and not val.startswith("**"):
                        fields[current_key].append(val)
        out[acronym] = fields
    return out


def parse_declared_systems(text: str) -> set[str]:
    return set(re.findall(r"(?m)^###\s+([A-Z]{3})\s*$", text)) | set(
        re.findall(r"\|\s*([A-Z]{3})\s*\|", text)
    )


def parse_primary_paths(field_value: str) -> list[Path]:
    paths = re.findall(r"`([^`]+)`", field_value)
    return [REPO_ROOT / p for p in paths]


def runtime_prefix_usage() -> dict[str, int]:
    usage: dict[str, int] = {}
    if not RUNTIME_DIR.exists():
        return usage
    for path in RUNTIME_DIR.glob("*.py"):
        match = re.match(r"^([a-z]{3})(?:_|$)", path.stem)
        if match:
            key = match.group(1).upper()
            usage[key] = usage.get(key, 0) + 1
    return usage


def validate_registry(text: str) -> list[str]:
    errors: list[str] = []

    active_systems = parse_active_systems(text)
    if not active_systems:
        return ["No active systems parsed from canonical registry."]

    seen: set[str] = set()
    for sys_entry in active_systems:
        if sys_entry.acronym in seen:
            errors.append(f"Duplicate active acronym: {sys_entry.acronym}")
        seen.add(sys_entry.acronym)

        missing = [f for f in REQUIRED_FIELDS if f not in sys_entry.fields]
        if missing:
            errors.append(
                f"{sys_entry.acronym} missing required fields: {', '.join(sorted(missing))}"
            )

        raw_paths = sys_entry.fields.get("Primary Code Paths", "")
        paths = parse_primary_paths(raw_paths)
        if not paths:
            errors.append(f"{sys_entry.acronym} has no primary code paths listed.")
        for path in paths:
            if not path.exists():
                errors.append(f"{sys_entry.acronym} path does not exist: {path.relative_to(REPO_ROOT)}")

    future = parse_future_systems(text)
    runtime_usage = runtime_prefix_usage()
    for acronym, count in sorted(runtime_usage.items()):
        if count < 1:
            continue
        if acronym in future:
            errors.append(
                f"{acronym} is marked future but has runtime implementation evidence ({count} files)."
            )

    active_set = {s.acronym for s in active_systems}
    declared_set = parse_declared_systems(text)
    for acronym, count in sorted(runtime_usage.items()):
        if count >= 2 and acronym not in active_set and acronym not in declared_set:
            if acronym in IGNORED_RUNTIME_PREFIXES:
                continue
            errors.append(
                f"Runtime drift: {acronym} has substantial runtime prefix usage ({count} files) "
                "but is not active or future in registry."
            )

    # NX-01: future placeholders with live runtime evidence must declare a
    # non-empty rationale that references "no" or "placeholder" or the system
    # is downgraded — otherwise the placeholder is shadow-active.
    future_with_rationale = parse_future_systems_with_rationale(text)
    for acronym, count in sorted(runtime_usage.items()):
        if acronym in future_with_rationale and count >= 1:
            rationale = future_with_rationale.get(acronym, "").strip()
            if not rationale:
                errors.append(
                    f"NX-01: future placeholder {acronym} has runtime evidence "
                    f"({count} files) but no rationale entry."
                )
            elif not re.search(r"placeholder|no\s+(?:bounded|canonical|runtime|dedicated|discrete)|reserved|conceptual", rationale, flags=re.I):
                errors.append(
                    f"NX-01: future placeholder {acronym} runtime evidence requires "
                    f"explicit non-active rationale; got: {rationale!r}"
                )

    # NX-02/NX-03: parse the System Definitions section and enforce that:
    #   - protected authorities are not claimed by a non-owner active system
    #   - demoted/non-authoritative systems do not declare forbidden owns tokens
    definitions = parse_system_definitions(text)
    for acronym, fields in definitions.items():
        owns = [str(item).strip().lower() for item in fields.get("owns", [])]
        status = str(fields.get("status", "")).strip().lower()

        if status == "active" and acronym in PROTECTED_AUTHORITY_BY_SYSTEM:
            mine = {a.lower() for a in PROTECTED_AUTHORITY_BY_SYSTEM[acronym]}
            for other_owner, other_authorities in PROTECTED_AUTHORITY_BY_SYSTEM.items():
                if other_owner == acronym:
                    continue
                for token in other_authorities:
                    if token.lower() in mine:
                        # legitimate overlap declared in PROTECTED_AUTHORITY_BY_SYSTEM
                        continue
                    if any(token.lower() == own_token for own_token in owns):
                        errors.append(
                            f"NX-02: {acronym} (active) claims protected authority "
                            f"'{token}' canonically owned by {other_owner}."
                        )

        if status in {"demoted", "deprecated"} and acronym in DEMOTED_FORBIDDEN_OWNS:
            forbidden = DEMOTED_FORBIDDEN_OWNS[acronym]
            for token in owns:
                for forbidden_token in forbidden:
                    if forbidden_token.lower() in token:
                        errors.append(
                            f"NX-02: demoted system {acronym} declares forbidden "
                            f"authoritative ownership token '{token}'."
                        )

        # NX-02: a system that is the canonical owner of a protected authority
        # cannot itself be demoted/deprecated/removed without halting promotion.
        if status in {"demoted", "deprecated", "removed"} and acronym in PROTECTED_AUTHORITY_BY_SYSTEM:
            errors.append(
                f"NX-02: protected authority owner {acronym} cannot have non-active "
                f"status '{status}' (canonical authorities: "
                f"{sorted(PROTECTED_AUTHORITY_BY_SYSTEM[acronym])})."
            )

        # NX-02 generalized: any demoted/deprecated system that declares
        # responsibilities matching a protected authority of an active owner
        # is treated as a shadow ownership claim.
        if status in {"demoted", "deprecated", "removed"}:
            for token in owns:
                normalized = token.replace(" ", "_")
                for active_owner, authorities in PROTECTED_AUTHORITY_BY_SYSTEM.items():
                    if active_owner == acronym:
                        continue
                    for authority in authorities:
                        if authority.lower() == normalized:
                            errors.append(
                                f"NX-02: demoted/deprecated system {acronym} claims "
                                f"protected authority '{authority}' (canonical owner: {active_owner})."
                            )

    return errors


def main() -> int:
    if not REGISTRY_PATH.exists():
        print(f"ERROR: missing registry file: {REGISTRY_PATH}")
        return 1

    text = REGISTRY_PATH.read_text(encoding="utf-8")
    errors = validate_registry(text)
    if errors:
        print("System registry validation failed:")
        for e in errors:
            print(f"- {e}")
        return 1

    print("System registry validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
