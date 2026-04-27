from __future__ import annotations

import json
from pathlib import Path

from scripts.tls_next_01_integration import build_integration


def _copy_required_inputs(src_root: Path, dst_root: Path) -> None:
    required = [
        "artifacts/system_dependency_priority_report.json",
        "artifacts/tls/system_trust_gap_report.json",
        "artifacts/tls/system_candidate_classification.json",
        "artifacts/tls/system_evidence_attachment.json",
        "artifacts/tls/system_registry_dependency_graph.json",
        "docs/architecture/system_registry.md",
    ]
    for rel in required:
        src = src_root / rel
        dst = dst_root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")


def test_tls_next_01_integration_emits_required_artifacts(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    _copy_required_inputs(repo_root, tmp_path)

    rc, report = build_integration(
        repo_root=tmp_path,
        artifacts_dir=tmp_path / "artifacts",
        registry_path=tmp_path / "docs" / "architecture" / "system_registry.md",
        generated_at="2026-04-27T00:00:00Z",
    )

    assert rc == 1
    assert report["source_mix"]["counts"]["artifact_store"] > report["source_mix"]["counts"]["stub_fallback"]
    assert report["source_mix"]["counts"]["repo_registry"] > 0

    validation = json.loads((tmp_path / "artifacts" / "tls" / "system_graph_validation_report.json").read_text(encoding="utf-8"))
    assert validation["artifact_type"] == "system_graph_validation_report"
    assert "checks" in validation

    redteam = json.loads((tmp_path / "artifacts" / "tls" / "tls_integration_redteam_report.json").read_text(encoding="utf-8"))
    assert redteam["artifact_type"] == "tls_integration_redteam_report"
    assert "stub_fallback_dominance" in redteam["findings"]

    roadmap = json.loads((tmp_path / "artifacts" / "tls" / "tls_integration_roadmap.json").read_text(encoding="utf-8"))
    assert roadmap["artifact_type"] == "tls_integration_roadmap"
    assert roadmap["next_recommended_phases"] == ["TLS-05", "TLS-06", "TLS-07"]


def test_tls_next_01_integration_lineage_and_replay_present(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    _copy_required_inputs(repo_root, tmp_path)

    rc, _ = build_integration(
        repo_root=tmp_path,
        artifacts_dir=tmp_path / "artifacts",
        registry_path=tmp_path / "docs" / "architecture" / "system_registry.md",
        generated_at="2026-04-27T00:00:00Z",
    )

    assert rc == 1

    integration = json.loads((tmp_path / "artifacts" / "tls" / "system_graph_integration_report.json").read_text(encoding="utf-8"))
    assert integration["graph"]["system_count"] > 0

    for row in integration["graph"]["systems"]:
        assert "classification" in row
        assert row["lineage"]["classification"]["source_artifact_ref"]
        assert row["lineage"]["trust_gap"]["artifact_type"]
        assert row["lineage"]["ranking"]["generation_step"] == "TLS-04"
        assert row["replay"]["artifact_paths"]
        assert row["replay"]["generation_commands"]
        assert row["replay"]["trace_linkage"]

    assert integration["derived"]["eval_coverage"]["present_count"] >= 1
