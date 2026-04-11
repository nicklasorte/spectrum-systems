"""Tests for scripts/generate_repo_dashboard_snapshot.py."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "generate_repo_dashboard_snapshot.py"
DEFAULT_OUTPUT = REPO_ROOT / "artifacts" / "dashboard" / "repo_snapshot.json"

REQUIRED_TOP_LEVEL_KEYS = {
    "generated_at",
    "repo_name",
    "root_counts",
    "core_areas",
    "constitutional_center",
    "runtime_hotspots",
    "operational_signals",
    "key_state",
}

REQUIRED_ROOT_COUNT_KEYS = {
    "files_total",
    "runtime_modules",
    "tests",
    "contracts_total",
    "schemas",
    "examples",
    "docs",
    "run_artifacts",
}


def _run_generator(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH), *args],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=True,
    )


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_script_exists() -> None:
    assert SCRIPT_PATH.is_file(), "scripts/generate_repo_dashboard_snapshot.py is missing"


def test_default_output_created_and_contract_shape() -> None:
    _run_generator()
    assert DEFAULT_OUTPUT.is_file(), "default snapshot output was not created"

    payload = _load_json(DEFAULT_OUTPUT)
    assert REQUIRED_TOP_LEVEL_KEYS <= set(payload.keys())
    assert REQUIRED_ROOT_COUNT_KEYS <= set(payload["root_counts"].keys())


def test_arrays_exist_and_are_sorted_deterministically() -> None:
    _run_generator()
    payload = _load_json(DEFAULT_OUTPUT)

    assert isinstance(payload["core_areas"], list)
    assert isinstance(payload["constitutional_center"], list)
    assert isinstance(payload["runtime_hotspots"], list)
    assert isinstance(payload["operational_signals"], list)

    core_names = [entry["name"] for entry in payload["core_areas"]]
    assert core_names == sorted(core_names)

    constitutional_center = payload["constitutional_center"]
    if constitutional_center:
        expected_tail = sorted(constitutional_center[1:]) if constitutional_center[0] == "docs/architecture/system_registry.md" else sorted(constitutional_center)
        observed_tail = constitutional_center[1:] if constitutional_center[0] == "docs/architecture/system_registry.md" else constitutional_center
        assert observed_tail == expected_tail


def test_custom_output_path_works() -> None:
    custom_output = Path("/tmp/repo_snapshot.json")
    if custom_output.exists():
        custom_output.unlink()

    result = _run_generator("--output", str(custom_output))
    assert result.returncode == 0
    assert custom_output.is_file(), "custom snapshot output was not created"

    payload = _load_json(custom_output)
    assert payload["repo_name"] == REPO_ROOT.name


def test_counts_are_non_negative_integers() -> None:
    _run_generator()
    payload = _load_json(DEFAULT_OUTPUT)
    counts = payload["root_counts"]

    for key in REQUIRED_ROOT_COUNT_KEYS:
        assert isinstance(counts[key], int), f"{key} must be int"
        assert counts[key] >= 0, f"{key} must be non-negative"


def test_handles_optional_directories_absent() -> None:
    sys.path.insert(0, str(REPO_ROOT))
    from scripts.generate_repo_dashboard_snapshot import RepoSurface, build_snapshot  # noqa: PLC0415

    with tempfile.TemporaryDirectory(prefix="snapshot-minimal-") as tmpdir:
        temp_repo = Path(tmpdir)
        (temp_repo / "docs/architecture").mkdir(parents=True)
        (temp_repo / "docs/architecture/system_registry.md").write_text("registry", encoding="utf-8")
        (temp_repo / "README.md").write_text("root", encoding="utf-8")

        payload = build_snapshot(RepoSurface(repo_root=temp_repo, runtime_root=temp_repo / "spectrum_systems/modules/runtime"))

        assert payload["root_counts"]["runtime_modules"] == 0
        assert payload["root_counts"]["tests"] == 0
        assert payload["root_counts"]["contracts_total"] == 0
