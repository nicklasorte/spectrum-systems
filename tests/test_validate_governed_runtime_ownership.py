from __future__ import annotations

from scripts import validate_governed_runtime_ownership as validator


def test_validate_paths_fails_for_unclassified_governed_runtime_path() -> None:
    failures = validator.validate_paths(["spectrum_systems/modules/runtime/new_governed_surface.py"])
    assert failures
    assert failures[0].startswith("ownership_classification_missing:")


def test_validate_paths_allows_classified_paths() -> None:
    failures = validator.validate_paths(
        [
            "spectrum_systems/modules/runtime/system_registry_enforcer.py",
            "scripts/run_contract_preflight.py",
            "docs/architecture/system_registry.md",
        ]
    )
    assert failures == []
