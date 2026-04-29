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
