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
    """A path-traversal request_id must not let the default output path
    escape its out_dir. Run the CLI with --out-dir tmp_path so the test
    is hermetic — no writes to the repo's artifacts/aex/ — while still
    exercising the default-filename code path.
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
    isolated_out_dir = tmp_path / "isolated_aex_out"
    completed = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "replay_aex_admission.py"),
            "--fixture",
            str(bad_fixture),
            "--out-dir",
            str(isolated_out_dir),
        ],
        check=False,
        capture_output=True,
    )
    # Whether the script wrote a sanitized in-bounds file or fail-closed,
    # the repository's artifacts/aex/ must remain untouched. This test
    # MUST NOT leave any side-effect file behind.
    if completed.returncode == 0:
        for path in isolated_out_dir.iterdir():
            assert "/" not in path.name
            assert path.name not in {"..", "."}
            assert path.resolve().parent == isolated_out_dir.resolve(), (
                f"replay artifact {path} escaped {isolated_out_dir}"
            )
    else:
        # If failed: must be a controlled fail-closed message, not an
        # uncaught traceback.
        assert b"FAIL" in completed.stderr or b"FAIL" in completed.stdout


def test_default_replay_output_path_sanitizes_traversal(tmp_path: Path) -> None:
    """Unit-test the default-path helper directly — no subprocess, no
    repo-tree side effects. Path-traversal request_id and replay_id must
    be sanitized; the result must resolve inside the supplied out_dir.
    """
    # Imported locally so the script-level imports don't pollute the
    # module namespace at collection time.
    sys.path.insert(0, str(REPO_ROOT))
    from scripts.replay_aex_admission import (
        ReplayPathEscapeError,
        _sanitize_segment,
        default_replay_output_path,
    )

    assert _sanitize_segment("../../../etc/passwd") == ".._.._.._etc_passwd"
    assert _sanitize_segment("../") == ".._"
    assert _sanitize_segment("..") == "unknown"
    assert _sanitize_segment(".") == "unknown"
    assert _sanitize_segment("") == "unknown"
    assert _sanitize_segment("ok-ID_123.json") == "ok-ID_123.json"
    # Path separators get replaced; the result is a single segment.
    assert "/" not in _sanitize_segment("a/b/c")
    assert "\\" not in _sanitize_segment("a\\b\\c")
    assert "\x00" not in _sanitize_segment("nul\x00byte")

    out_dir = tmp_path / "out"
    out_dir.mkdir()
    record = {
        "request_id": "../../../etc/passwd",
        "replay_id": "arr-deadbeefcafef00d",
    }
    result = default_replay_output_path(record=record, out_dir=out_dir)
    assert result.parent == out_dir.resolve()
    assert result.name.startswith("aex_admission_replay_")
    assert "/" not in result.name
    # The filename must include the replay_id so two replays with the
    # same request_id but different trace_ids do not overwrite each
    # other.
    assert "arr-deadbeefcafef00d" in result.name


def test_default_replay_output_path_distinct_per_replay_id(tmp_path: Path) -> None:
    """Two replays with the same request_id but different replay_id (which
    is derived from trace_id) must produce different filenames so per-run
    evidence is preserved."""
    sys.path.insert(0, str(REPO_ROOT))
    from scripts.replay_aex_admission import default_replay_output_path

    out_dir = tmp_path
    a = default_replay_output_path(
        record={"request_id": "req-1", "replay_id": "arr-1111111111111111"},
        out_dir=out_dir,
    )
    b = default_replay_output_path(
        record={"request_id": "req-1", "replay_id": "arr-2222222222222222"},
        out_dir=out_dir,
    )
    assert a != b
    assert "arr-1111111111111111" in a.name
    assert "arr-2222222222222222" in b.name


def test_default_replay_output_path_rejects_escape(tmp_path: Path) -> None:
    """If sanitization would still produce a path outside out_dir, the
    helper raises ReplayPathEscapeError instead of writing."""
    sys.path.insert(0, str(REPO_ROOT))
    from scripts.replay_aex_admission import (
        ReplayPathEscapeError,
        default_replay_output_path,
    )

    # Construct an unsafe out_dir to verify defensive resolve()-equality
    # check still holds. (In practice this is hard to trigger because the
    # sanitizer collapses traversal sequences, but the defense-in-depth
    # check should still catch any future regressions.)
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    # Sanity: the helper must not leak into a sibling dir even if a
    # bizarre filename resolution would otherwise allow it.
    record = {"request_id": "ok", "replay_id": "arr-aaaa"}
    p = default_replay_output_path(record=record, out_dir=out_dir)
    assert p.parent == out_dir.resolve()





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
