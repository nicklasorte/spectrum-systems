from __future__ import annotations

from pathlib import Path

from scripts import validate_system_registry_boundaries as validator


REPO_ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = REPO_ROOT / "docs" / "architecture" / "system_registry.md"


def test_registry_parser_extracts_targeted_system_fields() -> None:
    systems, _ = validator.parse_registry(REGISTRY_PATH)

    assert systems["TLC"].owns == [
        "orchestration",
        "subsystem_routing",
        "bounded_cycle_coordination",
        "unresolved_handoff_disposition_classification",
    ]
    assert "promotion_readiness_decisioning" in systems["CDE"].owns
    assert "review_interpretation" in systems["RIL"].owns
    assert "failure_diagnosis" in systems["FRE"].owns


def test_validator_passes_for_current_registry() -> None:
    errors = validator.run_all_checks(REGISTRY_PATH)
    assert errors == []


def test_validator_fails_when_tlc_owns_closure_decisions(tmp_path: Path) -> None:
    content = REGISTRY_PATH.read_text(encoding="utf-8")
    mutated = content.replace(
        "  - unresolved_handoff_disposition_classification\n",
        "  - unresolved_handoff_disposition_classification\n  - closure_decisions\n",
        1,
    )
    mutated_path = tmp_path / "registry.md"
    mutated_path.write_text(mutated, encoding="utf-8")

    errors = validator.run_all_checks(mutated_path)

    assert any("closure/promotion authority" in error for error in errors)
    assert any("closure decisioning" in error for error in errors)


def test_validator_fails_when_review_interpretation_is_duplicated_in_rqx(tmp_path: Path) -> None:
    content = REGISTRY_PATH.read_text(encoding="utf-8")
    mutated = content.replace(
        "  - unresolved_post_cycle_operator_handoff_emission\n",
        "  - unresolved_post_cycle_operator_handoff_emission\n  - review_interpretation\n",
        1,
    )
    mutated_path = tmp_path / "registry.md"
    mutated_path.write_text(mutated, encoding="utf-8")

    errors = validator.run_all_checks(mutated_path)

    assert any("interpretation semantics" in error for error in errors)
    assert any("Review semantics duplicated" in error for error in errors)


def test_validator_fails_when_entry_invariant_is_weakened(tmp_path: Path) -> None:
    content = REGISTRY_PATH.read_text(encoding="utf-8")
    weakened = content.replace(
        "- **PQX** MUST reject repo-writing execution that lacks AEX admission artifacts plus TLC-mediated lineage.\n",
        "",
        1,
    )
    weakened_path = tmp_path / "registry.md"
    weakened_path.write_text(weakened, encoding="utf-8")

    errors = validator.run_all_checks(weakened_path)

    assert any("Entry invariant missing required fail-closed statement" in error for error in errors)
