#!/usr/bin/env python3
"""Validate canonical system registry structure and registry-to-code conformance."""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

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
IGNORED_RUNTIME_PREFIXES = {"RUN", "TOP", "PRE", "TAX", "PMH", "MVP", "BNE", "BAX", "CAX", "RFX"}


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
