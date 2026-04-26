#!/usr/bin/env python3
"""BLF-01 baseline gate: verify the BLF-01 artifact surface is well-formed.

Fail-closed verification that every target failure tracked by BLF-01 has
inventory, classification, root-cause, fix-decision, and validation evidence
present in the governed artifact set, and that the delivery report cannot
declare H01 readiness while blocking gaps remain.

Usage:
    python scripts/run_blf_01_baseline_gate.py [--artifact-dir DIR]

Exit codes:
    0 — all BLF-01 gate checks pass
    1 — one or more checks failed (printed as machine-readable reason codes)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Iterable

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ARTIFACT_DIR = REPO_ROOT / "artifacts" / "blf_01_baseline_failure_fix"

REQUIRED_RECORDS = (
    "failure_inventory.json",
    "failure_classification.json",
    "root_cause_analysis.json",
    "fix_decisions.json",
    "control_validation.json",
    "replay_validation.json",
    "delivery_report.json",
)

TARGET_FAILURES = (
    "test_authority_leak_guard_local::test_authority_leak_guard_passes_on_local_changes",
    "test_contract_impact_analysis",
    "test_github_pr_autofix_review_artifact_validation",
    "test_roadmap_realization_runner::test_verified_requires_stricter_behavioral_coverage_than_runtime_realized",
)

ALLOWED_FIX_DECISIONS = {
    "code_fix",
    "test_fixture_fix",
    "contract_schema_fix",
    "roadmap_sync_fix",
    "guard_policy_fix",
    "governed_exception_with_block",
    "no_change_failure_not_reproduced",
}

VALID_DELIVERY_STATUSES = {"pass", "blocked"}
VALID_H01_VERDICTS = {"ready", "blocked"}


class BlfGateError(ValueError):
    """Raised when a BLF gate invariant is violated."""


def _load(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise BlfGateError(f"missing_required_record:{path.name}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise BlfGateError(f"unparseable_record:{path.name}:{exc}") from exc


def _failures_in(payload: dict[str, Any], key: str, name_field: str) -> set[str]:
    items = payload.get(key, [])
    if not isinstance(items, list):
        raise BlfGateError(f"non_list_collection:{key}")
    names: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            raise BlfGateError(f"non_object_entry:{key}")
        name = item.get(name_field)
        if not isinstance(name, str) or not name.strip():
            raise BlfGateError(f"missing_name_field:{key}:{name_field}")
        names.add(name.strip())
    return names


def _coverage_check(actual: set[str], required: Iterable[str], reason_code: str) -> list[str]:
    missing = [name for name in required if not any(name in present for present in actual)]
    return [f"{reason_code}:{name}" for name in missing]


def run_gate(artifact_dir: Path) -> dict[str, Any]:
    reasons: list[str] = []
    records: dict[str, dict[str, Any]] = {}
    for name in REQUIRED_RECORDS:
        try:
            records[name] = _load(artifact_dir / name)
        except BlfGateError as exc:
            reasons.append(str(exc))

    if reasons:
        return {
            "artifact_type": "blf_01_baseline_gate_result",
            "status": "fail",
            "reason_codes": sorted(set(reasons)),
            "artifact_dir": str(artifact_dir),
        }

    inventory = records["failure_inventory.json"]
    classification = records["failure_classification.json"]
    rca = records["root_cause_analysis.json"]
    fixes = records["fix_decisions.json"]
    control = records["control_validation.json"]
    delivery = records["delivery_report.json"]

    inventory_names = _failures_in(inventory, "target_failures", "name")
    reasons.extend(_coverage_check(inventory_names, TARGET_FAILURES, "inventory_missing"))

    classification_names = _failures_in(classification, "classifications", "failure_name")
    reasons.extend(_coverage_check(classification_names, TARGET_FAILURES, "classification_missing"))

    rca_names = _failures_in(rca, "analyses", "failure_name")
    reasons.extend(_coverage_check(rca_names, TARGET_FAILURES, "root_cause_missing"))

    fixes_names = _failures_in(fixes, "decisions", "failure_name")
    reasons.extend(_coverage_check(fixes_names, TARGET_FAILURES, "fix_decision_missing"))

    for decision in fixes.get("decisions", []):
        if decision.get("fix_decision") not in ALLOWED_FIX_DECISIONS:
            reasons.append(f"unknown_fix_decision:{decision.get('failure_name')}")

    commands = control.get("commands", [])
    if not isinstance(commands, list) or not commands:
        reasons.append("control_validation_missing_commands")
    for entry in commands:
        if not isinstance(entry, dict):
            reasons.append("control_validation_malformed_command")
            continue
        if not entry.get("command") or not entry.get("status"):
            reasons.append("control_validation_missing_command_or_status")

    target_failures_in_delivery = _failures_in(delivery, "target_failures", "name")
    reasons.extend(_coverage_check(target_failures_in_delivery, TARGET_FAILURES, "delivery_target_missing"))

    delivery_status = delivery.get("status")
    if delivery_status not in VALID_DELIVERY_STATUSES:
        reasons.append(f"invalid_delivery_status:{delivery_status}")

    h01_verdict = delivery.get("h01_readiness")
    if h01_verdict not in VALID_H01_VERDICTS:
        reasons.append(f"invalid_h01_readiness:{h01_verdict}")

    remaining = delivery.get("remaining_blockers", [])
    if not isinstance(remaining, list):
        reasons.append("delivery_remaining_blockers_not_list")
        remaining = []

    if delivery_status == "pass" and remaining:
        reasons.append("delivery_status_pass_with_remaining_blockers")

    if h01_verdict == "ready" and (delivery_status != "pass" or remaining):
        reasons.append("h01_ready_but_blockers_remain")

    status = "pass" if not reasons else "fail"
    return {
        "artifact_type": "blf_01_baseline_gate_result",
        "status": status,
        "reason_codes": sorted(set(reasons)),
        "artifact_dir": str(artifact_dir),
        "covered_target_failures": sorted(TARGET_FAILURES),
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-dir", default=str(DEFAULT_ARTIFACT_DIR))
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    result = run_gate(Path(args.artifact_dir))
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
