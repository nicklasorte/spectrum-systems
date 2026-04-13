#!/usr/bin/env python3
"""Deterministic builder/validator for system_registry_artifact.

This tool normalizes set-like list fields, validates schema conformance,
and enforces protected ownership invariants fail-closed.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.contracts import validate_artifact

DEFAULT_INPUT = REPO_ROOT / "contracts" / "examples" / "system_registry_artifact.json"

_SET_LIKE_SYSTEM_FIELDS = (
    "owns",
    "consumes",
    "produces",
    "prohibited_behaviors",
    "upstream_dependencies",
    "downstream_consumers",
)

_PROTECTED_OWNERS = {
    "execution": "PQX",
    "execution_admission": "AEX",
    "failure_diagnosis": "FRE",
    "review_interpretation": "RIL",
    "closure_decisions": "CDE",
    "enforcement": "SEL",
    "orchestration": "TLC",
}


class SystemRegistryBuildError(RuntimeError):
    """Raised when registry build/validation fails."""


@dataclass(frozen=True)
class BuildResult:
    output_path: Path
    normalized_system_count: int


def _dedupe_ordered_strings(values: Any, *, field: str, acronym: str) -> list[str]:
    if not isinstance(values, list):
        raise SystemRegistryBuildError(f"registry_build_invalid:{acronym}.{field}:expected_list")
    out: list[str] = []
    seen: set[str] = set()
    for idx, raw in enumerate(values):
        if not isinstance(raw, str):
            raise SystemRegistryBuildError(f"registry_build_invalid:{acronym}.{field}[{idx}]:expected_string")
        value = raw.strip()
        if not value:
            raise SystemRegistryBuildError(f"registry_build_invalid:{acronym}.{field}[{idx}]:empty_string")
        if value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def _normalize_registry(payload: dict[str, Any]) -> dict[str, Any]:
    systems = payload.get("systems")
    if not isinstance(systems, list):
        raise SystemRegistryBuildError("registry_build_invalid:systems:expected_list")

    normalized = dict(payload)
    normalized_systems: list[dict[str, Any]] = []
    seen_acronyms: set[str] = set()
    for idx, entry in enumerate(systems):
        if not isinstance(entry, dict):
            raise SystemRegistryBuildError(f"registry_build_invalid:systems[{idx}]:expected_object")
        acronym = str(entry.get("acronym") or "").strip().upper()
        if not acronym:
            raise SystemRegistryBuildError(f"registry_build_invalid:systems[{idx}].acronym:required")
        if acronym in seen_acronyms:
            raise SystemRegistryBuildError(f"registry_build_invalid:duplicate_acronym:{acronym}")
        seen_acronyms.add(acronym)

        record = dict(entry)
        record["acronym"] = acronym
        for field in _SET_LIKE_SYSTEM_FIELDS:
            record[field] = _dedupe_ordered_strings(record.get(field, []), field=field, acronym=acronym)
        normalized_systems.append(record)

    normalized["systems"] = normalized_systems
    return normalized


def _validate_semantic_invariants(payload: dict[str, Any]) -> None:
    systems = payload["systems"]
    owners_by_action: dict[str, list[str]] = {}
    for system in systems:
        acronym = system["acronym"]
        for action in system.get("owns", []):
            owners_by_action.setdefault(action, []).append(acronym)

    for action, canonical_owner in _PROTECTED_OWNERS.items():
        owners = owners_by_action.get(action, [])
        if owners != [canonical_owner]:
            raise SystemRegistryBuildError(
                f"registry_build_invariant_failed:{action}:expected_owner={canonical_owner}:actual={owners}"
            )

    for action, owners in owners_by_action.items():
        if len(owners) > 1:
            raise SystemRegistryBuildError(f"registry_build_invariant_failed:duplicate_owner:{action}:{owners}")

    for system in systems:
        acronym = system["acronym"]
        downstream = system.get("downstream_consumers", [])
        if len(downstream) != len(set(downstream)):
            raise SystemRegistryBuildError(
                f"registry_build_invariant_failed:duplicate_downstream_consumers:{acronym}:{downstream}"
            )


def build_system_registry_artifact(*, input_path: Path, output_path: Path) -> BuildResult:
    if not input_path.is_file():
        raise SystemRegistryBuildError(f"registry_build_invalid:missing_input:{input_path}")
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemRegistryBuildError("registry_build_invalid:root:expected_object")

    normalized = _normalize_registry(payload)
    validate_artifact(normalized, "system_registry_artifact")
    _validate_semantic_invariants(normalized)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(normalized, indent=2) + "\n", encoding="utf-8")
    return BuildResult(output_path=output_path, normalized_system_count=len(normalized["systems"]))


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Normalize + validate system_registry_artifact fail-closed")
    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    parser.add_argument("--output", default=str(DEFAULT_INPUT))
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    try:
        result = build_system_registry_artifact(input_path=Path(args.input), output_path=Path(args.output))
    except (SystemRegistryBuildError, ValueError, TypeError, FileNotFoundError) as exc:
        print(f"ERROR: {exc}")
        return 2
    print(
        json.dumps(
            {
                "status": "ok",
                "output_path": str(result.output_path),
                "normalized_system_count": result.normalized_system_count,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
