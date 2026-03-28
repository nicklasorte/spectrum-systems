import json
from pathlib import Path

import pytest

from scripts import build_source_indexes

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def test_build_source_indexes_generates_deterministic_outputs() -> None:
    build_source_indexes.build_indexes()

    source_inventory = _load(REPO_ROOT / "docs" / "source_indexes" / "source_inventory.json")
    obligation_index = _load(REPO_ROOT / "docs" / "source_indexes" / "obligation_index.json")
    component_source_map = _load(REPO_ROOT / "docs" / "source_indexes" / "component_source_map.json")

    source_ids = [entry["source_id"] for entry in source_inventory["sources"]]
    assert source_ids == sorted(source_ids)

    obligation_ids = [entry["obligation_id"] for entry in obligation_index["obligations"]]
    assert obligation_ids == sorted(obligation_ids)

    component_ids = [entry["component_id"] for entry in component_source_map["components"]]
    assert component_ids == sorted(component_ids)


def test_build_source_indexes_fails_on_undocumented_duplicate_obligation_id(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    structured_dir = tmp_path / "source_structured"
    indexes_dir = tmp_path / "source_indexes"
    structured_dir.mkdir(parents=True)
    indexes_dir.mkdir(parents=True)

    base_payload = _load(
        REPO_ROOT / "docs" / "source_structured" / "mapping_google_sre_reliability_principles_to_spectrum_systems.json"
    )
    second_payload = _load(
        REPO_ROOT / "docs" / "source_structured" / "production_ready_best_practices_for_integrating_ai_models_into_automated_engineering_workflows.json"
    )

    duplicate_obligation_id = "OBL-DUPLICATE-001"
    base_payload["source_traceability_rows"][0]["obligation_id"] = duplicate_obligation_id
    second_payload["source_traceability_rows"][0]["obligation_id"] = duplicate_obligation_id

    (structured_dir / "one.json").write_text(json.dumps(base_payload), encoding="utf-8")
    (structured_dir / "two.json").write_text(json.dumps(second_payload), encoding="utf-8")

    monkeypatch.setattr(build_source_indexes, "SOURCE_STRUCTURED_DIR", structured_dir)
    monkeypatch.setattr(build_source_indexes, "SOURCE_INDEXES_DIR", indexes_dir)

    with pytest.raises(ValueError, match="Duplicate obligation_id"):
        build_source_indexes.build_indexes()


def test_build_source_indexes_allows_documented_duplicate_obligation_id(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    structured_dir = tmp_path / "source_structured"
    indexes_dir = tmp_path / "source_indexes"
    structured_dir.mkdir(parents=True)
    indexes_dir.mkdir(parents=True)

    payload_a = _load(
        REPO_ROOT / "docs" / "source_structured" / "mapping_google_sre_reliability_principles_to_spectrum_systems.json"
    )
    payload_b = _load(
        REPO_ROOT / "docs" / "source_structured" / "production_ready_best_practices_for_integrating_ai_models_into_automated_engineering_workflows.json"
    )

    duplicate_obligation_id = "OBL-DUPLICATE-DOCUMENTED-001"
    for payload in (payload_a, payload_b):
        payload["source_traceability_rows"][0]["obligation_id"] = duplicate_obligation_id
        payload["source_traceability_rows"][0]["duplicate_allowed"] = True
        payload["source_traceability_rows"][0]["duplicate_reason"] = "Shared control requirement across sources."

    (structured_dir / "a.json").write_text(json.dumps(payload_a), encoding="utf-8")
    (structured_dir / "b.json").write_text(json.dumps(payload_b), encoding="utf-8")

    monkeypatch.setattr(build_source_indexes, "SOURCE_STRUCTURED_DIR", structured_dir)
    monkeypatch.setattr(build_source_indexes, "SOURCE_INDEXES_DIR", indexes_dir)

    build_source_indexes.build_indexes()

    obligation_index = _load(indexes_dir / "obligation_index.json")
    obligations = [row for row in obligation_index["obligations"] if row["obligation_id"] == duplicate_obligation_id]
    assert len(obligations) == 2
