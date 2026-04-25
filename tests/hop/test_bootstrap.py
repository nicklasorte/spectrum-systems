"""Tests for the optional HOP bootstrap snapshot generator."""

from __future__ import annotations

import json

import pytest

from spectrum_systems.modules.hop import bootstrap


def test_bootstrap_snapshot_includes_required_fields() -> None:
    snap = bootstrap.build_bootstrap_snapshot()
    assert snap["snapshot_kind"] == "hop_bootstrap_v1"
    for required in (
        "modules",
        "schemas",
        "eval_manifest",
        "cli_commands",
        "test_commands",
        "patterns",
        "sandbox",
    ):
        assert required in snap


def test_bootstrap_snapshot_lists_hop_modules() -> None:
    snap = bootstrap.build_bootstrap_snapshot()
    expected = {
        "spectrum_systems/modules/hop/sandbox.py",
        "spectrum_systems/modules/hop/bootstrap.py",
        "spectrum_systems/modules/hop/patterns/__init__.py",
        "spectrum_systems/modules/hop/patterns/draft_verify.py",
        "spectrum_systems/modules/hop/patterns/label_primer.py",
        "spectrum_systems/modules/hop/patterns/domain_router.py",
    }
    assert expected.issubset(set(snap["modules"]))


def test_bootstrap_snapshot_lists_registered_schemas() -> None:
    snap = bootstrap.build_bootstrap_snapshot()
    assert "hop_harness_candidate" in snap["schemas"]["registered"]
    assert "hop_harness_faq_output" in snap["schemas"]["registered"]


def test_bootstrap_snapshot_advertises_cli_and_test_commands() -> None:
    snap = bootstrap.build_bootstrap_snapshot()
    cli_names = {c["name"] for c in snap["cli_commands"]}
    test_names = {c["name"] for c in snap["test_commands"]}
    assert "hop_evaluate" in cli_names
    assert "hop_unit" in test_names


def test_bootstrap_snapshot_describes_sandbox_blocks() -> None:
    snap = bootstrap.build_bootstrap_snapshot()
    sandbox_info = snap["sandbox"]
    assert "network" in sandbox_info["blocks"]
    assert "subprocess" in sandbox_info["blocks"]
    assert "process_environment" in sandbox_info["blocks"]
    assert "filesystem_writes_outside_scratch" in sandbox_info["blocks"]


def test_bootstrap_snapshot_within_default_budget() -> None:
    snap = bootstrap.build_bootstrap_snapshot()
    serialized = bootstrap.serialize_snapshot(snap)
    assert len(serialized.encode("utf-8")) <= bootstrap.DEFAULT_MAX_TOTAL_BYTES


def test_bootstrap_snapshot_raises_when_budget_too_small() -> None:
    tight = bootstrap.BootstrapBudget(max_total_bytes=128, max_field_bytes=64)
    with pytest.raises(bootstrap.BootstrapBudgetExceeded):
        bootstrap.build_bootstrap_snapshot(budget=tight)


def test_bootstrap_snapshot_is_json_serializable() -> None:
    snap = bootstrap.build_bootstrap_snapshot()
    text = bootstrap.serialize_snapshot(snap)
    # Round-trip
    parsed = json.loads(text)
    assert parsed["snapshot_kind"] == "hop_bootstrap_v1"


def test_bootstrap_budget_validates_inputs() -> None:
    with pytest.raises(ValueError):
        bootstrap.BootstrapBudget(max_total_bytes=0)
    with pytest.raises(ValueError):
        bootstrap.BootstrapBudget(max_field_bytes=0)
    with pytest.raises(ValueError):
        bootstrap.BootstrapBudget(max_total_bytes=10, max_field_bytes=100)
