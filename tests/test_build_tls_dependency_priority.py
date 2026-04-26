from __future__ import annotations

import json
from pathlib import Path

import scripts.build_tls_dependency_priority as tls_build


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _stub_pipeline(monkeypatch) -> None:
    def parser_writer(target: Path):
        payload = {"active_systems": ["H01"]}
        _write_json(target, payload)
        return payload

    def evidence_writer(target: Path, _graph: dict):
        payload = {"systems": []}
        _write_json(target, payload)
        return payload

    def classification_writer(target: Path, _graph: dict, _evidence: dict):
        payload = {"classified": []}
        _write_json(target, payload)
        return payload

    def trust_writer(target: Path, _graph: dict, _evidence: dict, _classification: dict):
        payload = {"gaps": []}
        _write_json(target, payload)
        return payload

    def ranking_writer(
        target: Path,
        _graph: dict,
        _evidence: dict,
        _classification: dict,
        _trust_gaps: dict,
        requested_candidates=None,
    ):
        payload = {
            "schema_version": "tls-04.v1",
            "phase": "TLS-04",
            "top_5": [],
            "ranked_systems": [],
            "requested_candidates": requested_candidates or [],
        }
        _write_json(target, payload)
        return payload

    monkeypatch.setattr(tls_build.registry_parser, "write_artifact", parser_writer)
    monkeypatch.setattr(tls_build.evidence_scanner, "write_artifact", evidence_writer)
    monkeypatch.setattr(tls_build.classification_module, "write_artifact", classification_writer)
    monkeypatch.setattr(tls_build.trust_gaps_module, "write_artifact", trust_writer)
    monkeypatch.setattr(tls_build.ranking, "write_artifact", ranking_writer)


def test_fail_if_missing_returns_nonzero_when_published_artifact_is_not_written(tmp_path, monkeypatch):
    _stub_pipeline(monkeypatch)
    out = tmp_path / "tls"
    top = tmp_path / "artifacts"

    original_write_text = Path.write_text

    def skip_top_level_publish(self: Path, data: str, *args, **kwargs):
        if self == top / "system_dependency_priority_report.json":
            return len(data)
        return original_write_text(self, data, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", skip_top_level_publish)

    rc = tls_build.main(
        [
            "--out",
            str(out),
            "--top-level-out",
            str(top),
            "--candidates",
            "H01,RFX,HOP,MET,METS",
            "--fail-if-missing",
        ]
    )
    assert rc == 1


def test_fail_if_missing_succeeds_when_all_required_artifacts_exist(tmp_path, monkeypatch):
    _stub_pipeline(monkeypatch)
    out = tmp_path / "tls"
    top = tmp_path / "artifacts"

    rc = tls_build.main(
        [
            "--out",
            str(out),
            "--top-level-out",
            str(top),
            "--candidates",
            "H01,RFX,HOP,MET,METS",
            "--fail-if-missing",
        ]
    )
    assert rc == 0
    assert (top / "system_dependency_priority_report.json").is_file()
