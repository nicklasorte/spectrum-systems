#!/usr/bin/env python3
"""
Lifecycle and data backbone validation check.

Scans the repository for:
1. Artifacts stored under data/ that are missing required records
   (metadata, lineage, evaluation).
2. Artifacts where action_required=True but no linked work item exists.
3. JSON files in shared/*/  and control_plane/lifecycle/ that are not
   valid JSON.

This script is designed to be run in CI and exits with a non-zero status
code when any violation is found.

Usage:
    python scripts/validate_lifecycle_data.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import List

_BASE_DIR = Path(__file__).resolve().parents[1]
_DATA_DIR = _BASE_DIR / "data"
_SHARED_DIR = _BASE_DIR / "shared"
_LIFECYCLE_DIR = _BASE_DIR / "control_plane" / "lifecycle"


def _collect_artifact_ids() -> List[str]:
    """Return all artifact IDs recorded in data/artifacts/."""
    store = _DATA_DIR / "artifacts"
    if not store.is_dir():
        return []
    return [p.stem for p in store.glob("*.json")]


def _record_exists(store: str, record_id: str) -> bool:
    path = _DATA_DIR / store / f"{record_id}.json"
    return path.is_file()


def _load_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def check_json_files_are_valid() -> List[str]:
    """Return error messages for any JSON files in shared/ or lifecycle/ that are invalid."""
    errors: List[str] = []
    dirs_to_check = [
        _SHARED_DIR,
        _LIFECYCLE_DIR,
    ]
    for directory in dirs_to_check:
        if not directory.is_dir():
            continue
        for json_file in directory.rglob("*.json"):
            try:
                json.loads(json_file.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                errors.append(f"Invalid JSON: {json_file.relative_to(_BASE_DIR)}: {exc}")
    return errors


def check_lifecycle_state_definitions() -> List[str]:
    """Return errors if lifecycle definition files are missing or malformed."""
    errors: List[str] = []

    states_path = _LIFECYCLE_DIR / "lifecycle_states.json"
    transitions_path = _LIFECYCLE_DIR / "lifecycle_transitions.json"

    for path in (states_path, transitions_path):
        if not path.is_file():
            errors.append(f"Missing lifecycle definition file: {path.relative_to(_BASE_DIR)}")

    if states_path.is_file():
        doc = _load_json(states_path)
        if not doc or "states" not in doc:
            errors.append("lifecycle_states.json is missing 'states' key")
        else:
            required = {"input", "transformed", "evaluated", "action_required",
                        "in_progress", "resolved", "re_evaluated"}
            found = {s["state"] for s in doc["states"]}
            missing = required - found
            if missing:
                errors.append(f"lifecycle_states.json missing required states: {sorted(missing)}")

    if transitions_path.is_file():
        doc = _load_json(transitions_path)
        if not doc or "transitions" not in doc:
            errors.append("lifecycle_transitions.json is missing 'transitions' key")

    return errors


def check_data_artifact_integrity() -> List[str]:
    """Return errors for artifacts in data/artifacts/ missing lineage or evaluation records."""
    errors: List[str] = []
    artifact_ids = _collect_artifact_ids()

    for artifact_id in artifact_ids:
        if not _record_exists("lineage", artifact_id):
            errors.append(
                f"Artifact '{artifact_id}' has metadata in data/artifacts/ "
                "but no lineage record in data/lineage/."
            )

        eval_path = _DATA_DIR / "evaluations" / f"{artifact_id}.json"
        if eval_path.is_file():
            eval_record = _load_json(eval_path)
            if eval_record is None:
                errors.append(f"data/evaluations/{artifact_id}.json is not valid JSON.")
                continue
            if "action_required" not in eval_record:
                errors.append(
                    f"Evaluation for '{artifact_id}' is missing required field 'action_required'."
                )
            elif eval_record["action_required"]:
                linked_id = eval_record.get("linked_work_item_id")
                if not linked_id:
                    errors.append(
                        f"Evaluation for '{artifact_id}' has action_required=True "
                        "but linked_work_item_id is missing or null."
                    )
                elif not _record_exists("work_items", linked_id):
                    errors.append(
                        f"Evaluation for '{artifact_id}' links to work item '{linked_id}' "
                        "but no record exists in data/work_items/."
                    )
            else:
                if not eval_record.get("rationale", "").strip():
                    errors.append(
                        f"Evaluation for '{artifact_id}' has action_required=False "
                        "but rationale is missing or empty."
                    )

    return errors


def main() -> int:
    violations: List[str] = []

    violations.extend(check_json_files_are_valid())
    violations.extend(check_lifecycle_state_definitions())
    violations.extend(check_data_artifact_integrity())

    if violations:
        print(f"[lifecycle-validation] {len(violations)} violation(s) found:\n")
        for v in violations:
            print(f"  - {v}")
        return 1

    print("[lifecycle-validation] All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
