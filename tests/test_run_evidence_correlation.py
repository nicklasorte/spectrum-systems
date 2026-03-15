import json
from pathlib import Path

from scripts import validate_run_evidence_bundle


def write_artifact(bundle_dir: Path, filename: str, run_id: str) -> None:
    payload = {"run_id": run_id, "artifact": filename}
    (bundle_dir / filename).write_text(json.dumps(payload), encoding="utf-8")


def test_validate_bundle_pass(tmp_path: Path) -> None:
    bundle = tmp_path / "evidence"
    bundle.mkdir()
    for name in validate_run_evidence_bundle.REQUIRED_FILES:
        write_artifact(bundle, name, run_id="run-123")

    result = validate_run_evidence_bundle.validate_bundle(bundle)

    assert result["status"] == "pass"
    assert result["errors"] == []
    assert set(result["run_ids"].values()) == {"run-123"}


def test_validate_bundle_run_id_mismatch(tmp_path: Path) -> None:
    bundle = tmp_path / "evidence"
    bundle.mkdir()
    for name in validate_run_evidence_bundle.REQUIRED_FILES:
        run_id = "run-abc" if name != "evaluation_results.json" else "run-xyz"
        write_artifact(bundle, name, run_id=run_id)

    result = validate_run_evidence_bundle.validate_bundle(bundle)

    assert result["status"] == "fail"
    assert any("run_id mismatch" in error for error in result["errors"])
