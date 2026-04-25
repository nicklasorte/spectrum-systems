#!/usr/bin/env python3
"""Fail-closed checker for top engineer practice mapping coverage and invariants."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
SYSTEM_REGISTRY_PATH = REPO_ROOT / "docs/architecture/system_registry.md"
MAPPING_PATH = REPO_ROOT / "contracts/examples/top_engineer_practice_mapping_record.example.json"


def _extract_active_system_ids(system_registry_text: str) -> list[str]:
    active_match = re.search(
        r"## Active executable systems\n(?P<body>.*?)(\n## Merged or demoted systems)",
        system_registry_text,
        re.S,
    )
    if not active_match:
        raise ValueError("Unable to locate active executable systems section.")
    body = active_match.group("body")
    return re.findall(r"^### ([A-Z0-9]{3})$", body, re.M)


def _is_blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def check_mapping(mapping: dict[str, Any], required_system_ids: list[str]) -> list[str]:
    errors: list[str] = []
    systems = mapping.get("systems")
    if not isinstance(systems, list):
        return ["Mapping artifact must include a systems array."]

    by_id = {}
    for item in systems:
        sid = item.get("system_id")
        if sid in by_id:
            errors.append(f"Duplicate mapping entry for system_id={sid}.")
        by_id[sid] = item

    for sid in required_system_ids:
        if sid not in by_id:
            errors.append(f"Missing mapping entry for active registry system {sid}.")

    for sid, item in by_id.items():
        if _is_blank(item.get("failure_prevented")):
            errors.append(f"{sid}: missing failure_prevented.")
        if _is_blank(item.get("signal_improved")):
            errors.append(f"{sid}: missing signal_improved.")

        loop = item.get("loop_strengthened", {})
        strengthened = loop.get("core_loop_strengthened")
        justification = loop.get("justification", "")
        if strengthened is not True and _is_blank(justification):
            errors.append(f"{sid}: loop_strengthened missing core-loop strengthening or justification.")

        unknown = item.get("unknown_state_policy", {})
        if unknown.get("silent_allowed") is not False:
            errors.append(f"{sid}: unknown_state_policy allows silent unknown states.")
        if unknown.get("mode") not in {"block", "escalate"}:
            errors.append(f"{sid}: unknown_state_policy.mode must be block or escalate.")

        promotion = item.get("promotion_requirements", {})
        if promotion.get("eval_required") is not True:
            errors.append(f"{sid}: promotion requirements missing eval validation.")
        if promotion.get("policy_required") is not True:
            errors.append(f"{sid}: promotion requirements missing policy validation.")
        if promotion.get("replay_required") is not True:
            errors.append(f"{sid}: promotion requirements missing replay validation.")

        rollback = item.get("rollback_path")
        if not isinstance(rollback, dict) or _is_blank(rollback.get("trigger")):
            errors.append(f"{sid}: missing rollback_path.")

        humans = item.get("human_intervention_points", [])
        if not isinstance(humans, list):
            errors.append(f"{sid}: human_intervention_points must be a list.")
            humans = []
        for point in humans:
            if point.get("required") is True and _is_blank(point.get("artifact_record")):
                errors.append(f"{sid}: required human intervention missing artifact capture.")

        scale = item.get("scale_failure_mode")
        if not isinstance(scale, dict) or any(_is_blank(scale.get(k)) for k in ("mode", "detection", "control_response")):
            errors.append(f"{sid}: no scale-failure mode declared.")

    return errors


def main() -> int:
    registry_text = SYSTEM_REGISTRY_PATH.read_text(encoding="utf-8")
    mapping = json.loads(MAPPING_PATH.read_text(encoding="utf-8"))
    required_ids = _extract_active_system_ids(registry_text)
    errors = check_mapping(mapping, required_ids)
    if errors:
        print("Top Engineer Practices check failed:")
        for err in errors:
            print(f"- {err}")
        return 1
    print(f"Top Engineer Practices check passed for {len(required_ids)} active systems.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
