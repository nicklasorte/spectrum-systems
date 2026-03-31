import json
from pathlib import Path

import pytest

from scripts import build_source_indexes

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_markdown_source(path: Path, source_id: str, obligation_id: str, duplicate_allowed: bool = False, duplicate_reason: str = "") -> None:
    payload = f"""# Test Source

## machine_source_document
```json
{{
  \"source_id\": \"{source_id}\",
  \"title\": \"{source_id} title\",
  \"path\": \"{path.as_posix()}\",
  \"status\": \"active\"
}}
```

## machine_obligations
```json
[
  {{
    \"obligation_id\": \"{obligation_id}\",
    \"trace_id\": \"TRACE-{obligation_id.replace('OBL-', '')}\",
    \"component_id\": \"COMP-TEST\",
    \"category\": \"test\",
    \"description\": \"test obligation\",
    \"layer\": \"test\",
    \"required_artifacts\": [\"artifact\"],
    \"required_gates\": [\"gate\"],
    \"status\": \"planned\",
    \"source_section\": \"test\",
    \"duplicate_allowed\": {str(duplicate_allowed).lower()},
    \"duplicate_reason\": \"{duplicate_reason}\"
  }}
]
```
"""
    path.write_text(payload, encoding="utf-8")


def test_build_source_indexes_generates_deterministic_outputs() -> None:
    build_source_indexes.build_indexes()

    source_inventory = _load(REPO_ROOT / "docs" / "source_indexes" / "source_inventory.json")
    obligation_index = _load(REPO_ROOT / "docs" / "source_indexes" / "obligation_index.json")
    component_source_map = _load(REPO_ROOT / "docs" / "source_indexes" / "component_source_map.json")

    source_ids = [entry["source_id"] for entry in source_inventory["sources"]]
    assert source_ids == sorted(source_ids)
    assert source_ids == [
        "SRC-AGENT-EVAL-INTEGRATION-DESIGN",
        "SRC-AI-DURABILITY-STRATEGY",
        "SRC-DONE-CERTIFICATION-GATE-GOV10",
        "SRC-GOOGLE-SRE-MAPPING",
        "SRC-GOVERNED-API-ADAPTER-DESIGN",
        "SRC-JUDGMENT-CAPTURE-REUSE-SYSTEM-DESIGN",
        "SRC-PRODUCTION-AI-WORKFLOW-BEST-PRACTICES",
        "SRC-SBGE-DESIGN",
    ]

    obligation_ids = [entry["obligation_id"] for entry in obligation_index["obligations"]]
    assert obligation_ids == sorted(obligation_ids)

    component_ids = [entry["component_id"] for entry in component_source_map["components"]]
    assert component_ids == sorted(component_ids)


def test_build_source_indexes_fails_on_undocumented_duplicate_obligation_id(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    structured_dir = tmp_path / "source_structured"
    indexes_dir = tmp_path / "source_indexes"
    structured_dir.mkdir(parents=True)
    indexes_dir.mkdir(parents=True)

    duplicate_obligation_id = "OBL-DUPLICATE-001"
    _write_markdown_source(structured_dir / "one.source.md", "SRC-ONE", duplicate_obligation_id)
    _write_markdown_source(structured_dir / "two.source.md", "SRC-TWO", duplicate_obligation_id)

    monkeypatch.setattr(build_source_indexes, "SOURCE_STRUCTURED_DIR", structured_dir)
    monkeypatch.setattr(build_source_indexes, "SOURCE_INDEXES_DIR", indexes_dir)

    with pytest.raises(ValueError, match="Duplicate obligation_id"):
        build_source_indexes.build_indexes()


def test_build_source_indexes_allows_documented_duplicate_obligation_id(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    structured_dir = tmp_path / "source_structured"
    indexes_dir = tmp_path / "source_indexes"
    structured_dir.mkdir(parents=True)
    indexes_dir.mkdir(parents=True)

    duplicate_obligation_id = "OBL-DUPLICATE-DOCUMENTED-001"
    reason = "Shared control requirement across sources."
    _write_markdown_source(
        structured_dir / "a.source.md",
        "SRC-A",
        duplicate_obligation_id,
        duplicate_allowed=True,
        duplicate_reason=reason,
    )
    _write_markdown_source(
        structured_dir / "b.source.md",
        "SRC-B",
        duplicate_obligation_id,
        duplicate_allowed=True,
        duplicate_reason=reason,
    )

    monkeypatch.setattr(build_source_indexes, "SOURCE_STRUCTURED_DIR", structured_dir)
    monkeypatch.setattr(build_source_indexes, "SOURCE_INDEXES_DIR", indexes_dir)

    build_source_indexes.build_indexes()

    obligation_index = _load(indexes_dir / "obligation_index.json")
    obligations = [row for row in obligation_index["obligations"] if row["obligation_id"] == duplicate_obligation_id]
    assert len(obligations) == 2
