"""AEX admission replay tests (TLS-03 missing_replay signal anchor).

This file lives under tests/aex/ and contains "replay" in its path so the
TLS-01 evidence scanner attributes a replay-bearing test to AEX. AEX
participates in replay observation only; REP retains replay authority.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from spectrum_systems.aex.admission_replay import (
    AEXReplayError,
    DEFAULT_REPLAY_COMMAND,
    build_admission_replay_record,
    load_fixture,
    replay_admission,
    replay_and_verify,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = REPO_ROOT / "tests" / "aex" / "fixtures"


def test_replay_admit_fixture_is_deterministic() -> None:
    fixture_path = FIXTURES / "admission_admit_repo_write.json"
    record = replay_and_verify(fixture_path)
    assert record["replay_status"] == "pass"
    assert record["deterministic"] is True
    assert record["replay_owner_ref"] == "REP"
    assert record["producer_authority"] == "AEX"
    # Hashes are stable across two-pass replay.
    assert record["input_hash"].startswith("sha256:")
    assert record["output_hash"].startswith("sha256:")


def test_replay_reject_missing_field_fixture_is_deterministic() -> None:
    fixture_path = FIXTURES / "admission_reject_missing_field.json"
    record = replay_and_verify(fixture_path)
    assert record["replay_status"] == "pass"


def test_replay_reject_indeterminate_fixture_is_deterministic() -> None:
    fixture_path = FIXTURES / "admission_reject_indeterminate.json"
    record = replay_and_verify(fixture_path)
    assert record["replay_status"] == "pass"


def test_replay_default_command_format_includes_fixture_path() -> None:
    cmd = DEFAULT_REPLAY_COMMAND.format(fixture_path="tests/aex/fixtures/x.json")
    assert "scripts/replay_aex_admission.py" in cmd
    assert "tests/aex/fixtures/x.json" in cmd


def test_replay_missing_fixture_fails_closed(tmp_path: Path) -> None:
    bogus = tmp_path / "nope.json"
    with pytest.raises(AEXReplayError):
        replay_and_verify(bogus)


def test_replay_record_validates_against_supplemental_schema() -> None:
    fixture_path = FIXTURES / "admission_admit_repo_write.json"
    fixture = load_fixture(fixture_path)
    result = replay_admission(fixture)
    record = build_admission_replay_record(
        fixture_path=fixture_path,
        fixture=fixture,
        result=result,
    )
    schema_path = REPO_ROOT / "schemas" / "aex" / "aex_admission_replay_record.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    from jsonschema import Draft202012Validator
    Draft202012Validator(schema).validate(record)
    assert record["replay_owner_ref"] == "REP"


def test_replay_script_emits_artifact_under_artifacts_aex(tmp_path: Path) -> None:
    out = tmp_path / "replay.json"
    completed = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "replay_aex_admission.py"),
            "--fixture",
            str(FIXTURES / "admission_admit_repo_write.json"),
            "--out",
            str(out),
        ],
        check=False,
        capture_output=True,
    )
    assert completed.returncode == 0, completed.stderr.decode()
    assert out.is_file()
    record = json.loads(out.read_text(encoding="utf-8"))
    assert record["replay_status"] == "pass"
    assert record["replay_owner_ref"] == "REP"


def test_replay_default_filename_sanitizes_path_traversal(tmp_path: Path) -> None:
    """A fixture with a path-traversal request_id must not let the default
    output path escape artifacts/aex/. The script either sanitizes the
    request_id to a safe single-segment name OR fails closed.
    """
    bad_fixture = tmp_path / "bad.json"
    bad_fixture.write_text(
        json.dumps(
            {
                "request_id": "../../../etc/passwd",
                "prompt_text": "modify contracts and tests",
                "trace_id": "trace-bad",
                "created_at": "2026-04-29T12:00:00Z",
                "produced_by": "codex",
                "target_paths": [
                    "contracts/schemas/build_admission_record.schema.json"
                ],
                "requested_outputs": ["patch"],
                "source_prompt_kind": "codex_build_request",
            }
        ),
        encoding="utf-8",
    )
    completed = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "replay_aex_admission.py"),
            "--fixture",
            str(bad_fixture),
        ],
        check=False,
        capture_output=True,
    )
    # Script either produced a sanitized in-bounds path or failed closed.
    if completed.returncode == 0:
        # The security property: every file under artifacts/aex/ resolves
        # inside artifacts/aex/. The basename may contain literal "..." as
        # safe characters, but path resolution must not walk out of the
        # allowed directory. The basename must also be a single segment
        # (no '/') and must not be the bare ".." traversal token.
        out_dir = (REPO_ROOT / "artifacts" / "aex").resolve()
        for path in out_dir.iterdir():
            assert "/" not in path.name
            assert path.name not in {"..", "."}
            assert path.resolve().parent == out_dir, (
                f"replay artifact {path} escaped artifacts/aex/"
            )
    else:
        # If failed: must be a controlled fail-closed message, not an
        # uncaught traceback.
        assert b"FAIL" in completed.stderr or b"FAIL" in completed.stdout


def test_load_fixture_rejects_non_mapping_root(tmp_path: Path) -> None:
    """load_fixture must fail-closed (AEXReplayError) when the JSON root is
    a list or primitive, instead of letting AttributeError leak."""
    list_fixture = tmp_path / "list.json"
    list_fixture.write_text(json.dumps(["not", "a", "mapping"]), encoding="utf-8")
    with pytest.raises(AEXReplayError, match="must be a JSON object"):
        load_fixture(list_fixture)

    primitive_fixture = tmp_path / "scalar.json"
    primitive_fixture.write_text(json.dumps("just a string"), encoding="utf-8")
    with pytest.raises(AEXReplayError, match="must be a JSON object"):
        load_fixture(primitive_fixture)


def test_load_fixture_rejects_invalid_json(tmp_path: Path) -> None:
    """load_fixture must fail-closed when the file contains invalid JSON."""
    bad = tmp_path / "broken.json"
    bad.write_text("{not: valid: json", encoding="utf-8")
    with pytest.raises(AEXReplayError, match="not valid JSON"):
        load_fixture(bad)


def test_build_admission_replay_record_rejects_non_mapping_fixture(tmp_path: Path) -> None:
    """build_admission_replay_record must defensively reject non-mapping
    fixtures even when callers reach it directly (not via load_fixture)."""
    fixture_path = FIXTURES / "admission_admit_repo_write.json"
    fixture = load_fixture(fixture_path)
    result = replay_admission(fixture)
    with pytest.raises(AEXReplayError, match="must be a Mapping"):
        build_admission_replay_record(
            fixture_path=fixture_path,
            fixture=["not", "a", "mapping"],  # type: ignore[arg-type]
            result=result,
        )
