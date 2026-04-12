import json
from pathlib import Path

import pytest

from scripts import sync_project_design_sources as sync


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_fake_pdf(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = b"%PDF-1.4\n" + text.encode("latin-1", errors="ignore") + b"\n%%EOF\n"
    path.write_bytes(payload)


def test_normalize_and_canonical_mapping() -> None:
    assert sync.normalize_name("Strategy Control Document.PDF") == "strategy_control_document"
    assert sync.canonical_source_key("agent_eval_integration_design_spectrum_systems") == "agent_eval_integration_design"


def test_discovery_and_grouping_finds_md_pdf_and_manifest(tmp_path: Path) -> None:
    root = tmp_path / "upstream"
    _write_text(root / "docs/architecture/project_design/README.md", "# catalog")
    _write_text(root / "docs/architecture/project_design/foundation_design.md", "# Foundation Design\nThe system must fail closed.")
    _write_fake_pdf(root / "raw/strategic_sources/project_design/foundation_design.pdf", "Foundation Design PDF must enforce policy.")

    candidates = sync.discover_candidates(root)
    grouped = sync.group_candidates(candidates)

    assert any(c.file_type == "manifest" for c in candidates)
    assert "foundation_design" in grouped
    assert sorted({c.file_type for c in grouped["foundation_design"]}) == ["md", "pdf"]


def test_run_sync_updates_indexes_and_structured_outputs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    upstream = tmp_path / "upstream"
    _write_text(upstream / "docs/architecture/project_design/ai_durability_strategy.md", "# AI Durability Strategy\nSystem must fail closed.")

    raw_root = tmp_path / "repo/docs/source_raw/project_design"
    structured_root = tmp_path / "repo/docs/source_structured"
    index_root = tmp_path / "repo/docs/source_indexes"

    monkeypatch.setattr(sync, "REPO_ROOT", tmp_path / "repo")
    monkeypatch.setattr(sync, "RAW_ROOT", raw_root)
    monkeypatch.setattr(sync, "STRUCTURED_ROOT", structured_root)
    monkeypatch.setattr(sync, "INDEX_ROOT", index_root)

    rc = sync.run_sync(upstream, "nicklasorte/spectrum-data-lake", allow_missing_required=True, validate_only=False)
    assert rc == 2

    structured = json.loads((structured_root / "project_design_ai_durability_strategy.json").read_text(encoding="utf-8"))
    assert structured["source_document"]["status"] in {"available", "missing"}
    assert structured["source_document"]["source_id"].startswith("SRC-PROJECT-DESIGN-")
    assert "source_traceability_rows" in structured
    inventory = json.loads((index_root / "source_inventory.json").read_text(encoding="utf-8"))
    assert any("AI Durability Strategy" in row["title"] for row in inventory["sources"])


def test_fail_closed_validation_for_missing_required(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    upstream = tmp_path / "upstream"
    upstream.mkdir(parents=True)

    monkeypatch.setattr(sync, "REPO_ROOT", tmp_path / "repo")
    monkeypatch.setattr(sync, "RAW_ROOT", tmp_path / "repo/docs/source_raw/project_design")
    monkeypatch.setattr(sync, "STRUCTURED_ROOT", tmp_path / "repo/docs/source_structured")
    monkeypatch.setattr(sync, "INDEX_ROOT", tmp_path / "repo/docs/source_indexes")

    with pytest.raises(RuntimeError, match="Completeness validation failed"):
        sync.run_sync(upstream, "nicklasorte/spectrum-data-lake", allow_missing_required=False, validate_only=True)


def test_idempotent_rerun_keeps_same_raw_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    upstream = tmp_path / "upstream"
    _write_text(upstream / "docs/architecture/project_design/context_as_infrastructure.md", "# Context as Infrastructure\nAdapters shall remain replaceable.")

    repo_root = tmp_path / "repo"
    monkeypatch.setattr(sync, "REPO_ROOT", repo_root)
    monkeypatch.setattr(sync, "RAW_ROOT", repo_root / "docs/source_raw/project_design")
    monkeypatch.setattr(sync, "STRUCTURED_ROOT", repo_root / "docs/source_structured")
    monkeypatch.setattr(sync, "INDEX_ROOT", repo_root / "docs/source_indexes")

    sync.run_sync(upstream, "nicklasorte/spectrum-data-lake", allow_missing_required=True, validate_only=False)
    first = json.loads((repo_root / "docs/source_structured/project_design_context_as_infrastructure.json").read_text(encoding="utf-8"))
    sync.run_sync(upstream, "nicklasorte/spectrum-data-lake", allow_missing_required=True, validate_only=False)
    second = json.loads((repo_root / "docs/source_structured/project_design_context_as_infrastructure.json").read_text(encoding="utf-8"))

    assert first["source_document"]["file_path"] == second["source_document"]["file_path"]


def test_run_sync_blocks_canonical_repo_writes_without_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    upstream = tmp_path / "upstream"
    _write_text(upstream / "docs/architecture/project_design/ai_durability_strategy.md", "# AI Durability Strategy\nSystem must fail closed.")
    monkeypatch.delenv("SPECTRUM_ALLOW_SOURCE_AUTHORITY_WRITE", raising=False)

    with pytest.raises(PermissionError, match="Refusing to mutate canonical source authority path"):
        sync.run_sync(upstream, "nicklasorte/spectrum-data-lake", allow_missing_required=True, validate_only=False)
