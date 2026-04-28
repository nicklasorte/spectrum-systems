"""D3L-MASTER-01 Phase 0 — registry contract artifact tests.

Pins the ranking/maturity universe contract:
  * active_system_ids comes only from registry-active systems.
  * future / deprecated / merged ids land in excluded_ids.
  * forbidden_node_examples contains H01, TLS-BND-*, D3L-FIX-*.
  * ranking_universe and maturity_universe equal active_system_ids.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "build_d3l_registry_contract.py"
SOURCE = REPO_ROOT / "artifacts" / "tls" / "system_registry_dependency_graph.json"
ARTIFACT = REPO_ROOT / "artifacts" / "tls" / "d3l_registry_contract.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def contract() -> dict:
    if not ARTIFACT.exists():  # pragma: no cover — defensive
        pytest.skip(f"missing contract artifact: {ARTIFACT}")
    return _load(ARTIFACT)


@pytest.fixture(scope="module")
def graph() -> dict:
    if not SOURCE.exists():  # pragma: no cover — defensive
        pytest.skip(f"missing source artifact: {SOURCE}")
    return _load(SOURCE)


def test_artifact_type_and_phase(contract: dict) -> None:
    assert contract["artifact_type"] == "d3l_registry_contract"
    assert contract["phase"] == "D3L-MASTER-01"
    assert contract["schema_version"].startswith("d3l-master-01")


def test_active_system_ids_match_source(contract: dict, graph: dict) -> None:
    expected = sorted(row["system_id"] for row in graph.get("active_systems", []))
    assert contract["active_system_ids"] == expected
    assert contract["ranking_universe"] == expected
    assert contract["maturity_universe"] == expected


def test_excluded_ids_cover_future_and_deprecated(contract: dict, graph: dict) -> None:
    future = [row["system_id"] for row in graph.get("future_systems", [])]
    demoted = [row["system_id"] for row in graph.get("merged_or_demoted", [])]
    expected = sorted(future + demoted)
    assert contract["excluded_ids"] == expected
    assert contract["future_system_ids"] == sorted(future)
    assert contract["deprecated_or_merged_system_ids"] == sorted(demoted)


def test_forbidden_node_examples_present(contract: dict) -> None:
    for forbidden in ("H01", "TLS-BND-01", "D3L-FIX-01"):
        assert forbidden in contract["forbidden_node_examples"], (
            f"forbidden label {forbidden} missing from contract"
        )


def test_no_overlap_between_active_and_excluded(contract: dict) -> None:
    overlap = set(contract["active_system_ids"]) & set(contract["excluded_ids"])
    assert overlap == set(), f"active and excluded must be disjoint; overlap={overlap}"


def test_no_active_system_is_a_forbidden_label(contract: dict) -> None:
    forbidden = set(contract["forbidden_node_examples"])
    overlap = set(contract["active_system_ids"]) & forbidden
    assert overlap == set(), f"forbidden label appears in active list: {overlap}"


def test_script_is_idempotent(tmp_path: Path) -> None:
    """Running the builder twice must produce the same artifact bytes."""
    import subprocess

    out = tmp_path / "out.json"
    for _ in range(2):
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "--output", str(out), "--source", str(SOURCE)],
            capture_output=True,
            text=True,
            check=True,
        )
        assert proc.returncode == 0
    first = out.read_text(encoding="utf-8")

    out2 = tmp_path / "out2.json"
    subprocess.run(
        [sys.executable, str(SCRIPT), "--output", str(out2), "--source", str(SOURCE)],
        capture_output=True,
        text=True,
        check=True,
    )
    # Drop generated_at timestamp because it is allowed to vary; everything
    # else must be byte-identical.
    a = json.loads(first)
    b = json.loads(out2.read_text(encoding="utf-8"))
    a.pop("generated_at", None)
    b.pop("generated_at", None)
    assert a == b
