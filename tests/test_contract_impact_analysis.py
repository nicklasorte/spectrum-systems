from __future__ import annotations

import json
import subprocess
from pathlib import Path

from spectrum_systems.governance.contract_impact import analyze_contract_impact


def _init_repo(tmp_path: Path) -> None:
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True)
    # Pin temp-repo signing so the host's global commit.gpgsign cannot leak in.
    subprocess.run(["git", "config", "commit.gpgsign", "false"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "tag.gpgsign", "false"], cwd=tmp_path, check=True)


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _baseline_schema() -> dict:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "required": ["id", "status"],
        "properties": {
            "id": {"type": "string"},
            "status": {"type": "string", "enum": ["new", "done"]},
            "count": {"type": ["integer", "null"]},
        },
    }


def _commit_all(tmp_path: Path, message: str) -> None:
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", message], cwd=tmp_path, check=True, capture_output=True)


def test_required_field_added_detected_and_blocks() -> None:
    from tempfile import TemporaryDirectory

    with TemporaryDirectory() as td:
        root = Path(td)
        _init_repo(root)
        schema_path = root / "contracts/schemas/test_contract.schema.json"
        _write(schema_path, _baseline_schema())
        _write(root / "contracts/examples/test_contract.json", {"id": "1", "status": "new", "count": 1})
        _write(root / "tests/test_ref.py", {"contract": "test_contract"})
        _commit_all(root, "baseline")

        updated = _baseline_schema()
        updated["required"] = ["id", "status", "owner"]
        updated["properties"]["owner"] = {"type": "string"}
        _write(schema_path, updated)

        artifact = analyze_contract_impact(
            repo_root=root,
            changed_contract_paths=["contracts/schemas/test_contract.schema.json"],
            changed_example_paths=[],
            generated_at="2026-03-30T00:00:00Z",
        )

        assert artifact["compatibility_class"] == "breaking"
        assert artifact["blocking"] is True
        assert artifact["safe_to_execute"] is False


def test_enum_narrowing_and_type_change_detected() -> None:
    from tempfile import TemporaryDirectory

    with TemporaryDirectory() as td:
        root = Path(td)
        _init_repo(root)
        schema_path = root / "contracts/schemas/test_contract.schema.json"
        _write(schema_path, _baseline_schema())
        _commit_all(root, "baseline")

        updated = _baseline_schema()
        updated["properties"]["status"]["enum"] = ["done"]
        updated["properties"]["count"] = {"type": "string"}
        _write(schema_path, updated)

        artifact = analyze_contract_impact(
            repo_root=root,
            changed_contract_paths=["contracts/schemas/test_contract.schema.json"],
            generated_at="2026-03-30T00:00:00Z",
        )
        reasons = " ".join(artifact["blocking_reasons"])
        assert "enum narrowing" in reasons
        assert "type changes" in reasons
        assert artifact["compatibility_class"] == "breaking"


def test_artifact_deterministic_for_identical_inputs() -> None:
    from tempfile import TemporaryDirectory

    with TemporaryDirectory() as td:
        root = Path(td)
        _init_repo(root)
        schema_path = root / "contracts/schemas/test_contract.schema.json"
        _write(schema_path, _baseline_schema())
        _commit_all(root, "baseline")

        artifact_one = analyze_contract_impact(
            repo_root=root,
            changed_contract_paths=["contracts/schemas/test_contract.schema.json"],
            generated_at="2026-03-30T00:00:00Z",
        )
        artifact_two = analyze_contract_impact(
            repo_root=root,
            changed_contract_paths=["contracts/schemas/test_contract.schema.json"],
            generated_at="2026-03-30T00:00:00Z",
        )
        assert artifact_one == artifact_two


def test_missing_or_malformed_inputs_fail_closed_indeterminate() -> None:
    from tempfile import TemporaryDirectory

    with TemporaryDirectory() as td:
        root = Path(td)
        _init_repo(root)
        bad_schema = root / "contracts/schemas/test_contract.schema.json"
        bad_schema.parent.mkdir(parents=True, exist_ok=True)
        bad_schema.write_text("{not-json", encoding="utf-8")
        _commit_all(root, "baseline")

        bad_schema.write_text("{still-bad", encoding="utf-8")
        artifact = analyze_contract_impact(
            repo_root=root,
            changed_contract_paths=["contracts/schemas/test_contract.schema.json"],
            generated_at="2026-03-30T00:00:00Z",
        )
        assert artifact["compatibility_class"] == "indeterminate"
        assert artifact["blocking"] is True


def test_failure_class_required_added_without_example_update_blocked() -> None:
    from tempfile import TemporaryDirectory

    with TemporaryDirectory() as td:
        root = Path(td)
        _init_repo(root)
        schema_path = root / "contracts/schemas/test_contract.schema.json"
        _write(schema_path, _baseline_schema())
        _write(root / "contracts/examples/test_contract.json", {"id": "1", "status": "new", "count": 1})
        _write(root / "spectrum_systems/modules/runtime/consumer.py", {"uses": "test_contract"})
        _commit_all(root, "baseline")

        updated = _baseline_schema()
        updated["required"] = ["id", "status", "owner"]
        updated["properties"]["owner"] = {"type": "string"}
        _write(schema_path, updated)

        artifact = analyze_contract_impact(
            repo_root=root,
            changed_contract_paths=["contracts/schemas/test_contract.schema.json"],
            changed_example_paths=[],
            generated_at="2026-03-30T00:00:00Z",
        )
        assert artifact["compatibility_class"] == "breaking"
        assert artifact["blocking"] is True
        assert any("update downstream" in item or "update impacted" in item for item in artifact["required_remediations"])
