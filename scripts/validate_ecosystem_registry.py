#!/usr/bin/env python3
"""
Validate the ecosystem registry for structural correctness and internal consistency.

Checks performed:
1. Repository name validity and URL structure consistency.
2. Naming convention: repo_name matches the URL slug and system_id (when present).
3. System IDs: every system_id must have a corresponding design package.
4. Contract consumer references: every intended_consumer in the standards manifest
   must appear as a repo_name in the registry.
5. Layer classification: repo_type must map to the expected layer.

No external API calls are made. All checks are deterministic.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = REPO_ROOT / "ecosystem" / "ecosystem-registry.json"
STANDARDS_MANIFEST_PATH = REPO_ROOT / "contracts" / "standards-manifest.json"
DESIGN_PACKAGES_DIR = REPO_ROOT / "design-packages"

REPO_SLUG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
REPO_URL_PATTERN = re.compile(
    r"^https://github\.com/(?P<org>[A-Za-z0-9_.-]+)/(?P<slug>[A-Za-z0-9_.-]+)/?$"
)

# Expected layer for each repo_type.
EXPECTED_LAYER: dict[str, str] = {
    "governance": "Layer 2",
    "factory": "Layer 1",
    "operational_engine": "Layer 3",
    "pipeline": "Layer 4",
    "advisory": "Layer 5",
}


def _load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_registry(path: Path) -> list[dict]:
    data = _load_json(path)
    assert isinstance(data, dict), "Registry must be a JSON object"
    repos = data.get("repositories", [])
    assert isinstance(repos, list), "'repositories' must be a list"
    return repos


def _load_manifest_consumers(path: Path) -> set[str]:
    data = _load_json(path)
    assert isinstance(data, dict), "Standards manifest must be a JSON object"
    consumers: set[str] = set()
    for contract in data.get("contracts", []):
        for consumer in contract.get("intended_consumers", []):
            if isinstance(consumer, str) and REPO_SLUG_PATTERN.match(consumer):
                consumers.add(consumer)
    return consumers


def validate_repo_name_and_url(repos: list[dict]) -> list[str]:
    """Check that repo_name is valid and matches the URL slug."""
    errors: list[str] = []
    for entry in repos:
        name = entry.get("repo_name", "")
        url = entry.get("repo_url", "")

        if not REPO_SLUG_PATTERN.match(name):
            errors.append(
                f"[{name}] repo_name '{name}' does not match required slug pattern "
                f"(lowercase alphanumeric, hyphens, dots, underscores)."
            )

        m = REPO_URL_PATTERN.match(url)
        if not m:
            errors.append(
                f"[{name}] repo_url '{url}' does not match the required GitHub URL pattern "
                f"'https://github.com/<org>/<repo>'."
            )
        else:
            url_slug = m.group("slug").rstrip("/")
            if url_slug != name:
                errors.append(
                    f"[{name}] repo_url slug '{url_slug}' does not match repo_name '{name}'."
                )

    return errors


def validate_system_id_naming(repos: list[dict]) -> list[str]:
    """Check that system_id matches repo_name when present."""
    errors: list[str] = []
    for entry in repos:
        name = entry.get("repo_name", "")
        system_id = entry.get("system_id")
        if system_id is not None and system_id != name:
            errors.append(
                f"[{name}] system_id '{system_id}' does not match repo_name '{name}'."
            )
    return errors


def validate_system_id_design_packages(repos: list[dict], design_packages_dir: Path) -> list[str]:
    """Check that every system_id has a corresponding design package file."""
    errors: list[str] = []
    for entry in repos:
        name = entry.get("repo_name", "")
        system_id = entry.get("system_id")
        if system_id is None:
            continue
        expected_path = design_packages_dir / f"{system_id}.design-package.json"
        if not expected_path.is_file():
            errors.append(
                f"[{name}] system_id '{system_id}' has no design package at "
                f"'{expected_path.relative_to(REPO_ROOT)}'."
            )
    return errors


def validate_contract_consumers(repos: list[dict], manifest_consumers: set[str]) -> list[str]:
    """Check that every contract consumer in the standards manifest is in the registry."""
    registry_names = {entry.get("repo_name") for entry in repos}
    missing = sorted(manifest_consumers - registry_names)
    if missing:
        return [
            f"Standards manifest references consumers not present in the registry: {missing}"
        ]
    return []


def validate_layer_classification(repos: list[dict]) -> list[str]:
    """Check that each repo's layer matches the expected layer for its repo_type."""
    errors: list[str] = []
    for entry in repos:
        name = entry.get("repo_name", "")
        repo_type = entry.get("repo_type", "")
        layer = entry.get("layer", "")
        expected = EXPECTED_LAYER.get(repo_type)
        if expected is not None and layer != expected:
            errors.append(
                f"[{name}] repo_type '{repo_type}' expects layer '{expected}' "
                f"but registry declares layer '{layer}'."
            )
    return errors


def run_all_checks(
    registry_path: Path = REGISTRY_PATH,
    manifest_path: Path = STANDARDS_MANIFEST_PATH,
    design_packages_dir: Path = DESIGN_PACKAGES_DIR,
) -> list[str]:
    """Run all registry validation checks and return a list of error messages."""
    repos = _load_registry(registry_path)
    manifest_consumers = _load_manifest_consumers(manifest_path)

    all_errors: list[str] = []
    all_errors.extend(validate_repo_name_and_url(repos))
    all_errors.extend(validate_system_id_naming(repos))
    all_errors.extend(validate_system_id_design_packages(repos, design_packages_dir))
    all_errors.extend(validate_contract_consumers(repos, manifest_consumers))
    all_errors.extend(validate_layer_classification(repos))
    return all_errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate the ecosystem registry for structural correctness."
    )
    parser.add_argument(
        "--registry",
        default=str(REGISTRY_PATH),
        help="Path to ecosystem-registry.json (default: %(default)s)",
    )
    parser.add_argument(
        "--manifest",
        default=str(STANDARDS_MANIFEST_PATH),
        help="Path to standards-manifest.json (default: %(default)s)",
    )
    parser.add_argument(
        "--design-packages",
        default=str(DESIGN_PACKAGES_DIR),
        help="Path to design-packages directory (default: %(default)s)",
    )
    args = parser.parse_args(argv)

    errors = run_all_checks(
        registry_path=Path(args.registry),
        manifest_path=Path(args.manifest),
        design_packages_dir=Path(args.design_packages),
    )

    if errors:
        print("Ecosystem registry validation FAILED:")
        for error in errors:
            print(f"  ERROR: {error}")
        return 1

    print("Ecosystem registry validation PASSED — no issues detected.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
