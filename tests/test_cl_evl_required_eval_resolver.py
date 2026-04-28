"""CL-10 / CL-11 / CL-12: EVL required-eval resolver, eval-set red team, fix pass."""

from __future__ import annotations

import pytest

from spectrum_systems.modules.governance.core_loop_required_eval_resolver import (
    REASON_DUPLICATE,
    REASON_OK,
    REASON_OPTIONAL_AS_REQUIRED,
    REASON_REQUIRED_AS_OPTIONAL,
    REASON_REQUIRED_FAILED,
    REASON_REQUIRED_MISSING,
    REASON_UNSUPPORTED,
    RequiredEvalResolverError,
    build_eval_summary,
    resolve_required_evals,
)


# --- CL-10 minimal happy path -------------------------------------------


def test_cl10_resolves_required_pass_only() -> None:
    res = resolve_required_evals(
        declared_catalog=[
            {"name": "core", "required": True},
            {"name": "smoke", "required": False},
        ],
        submitted_evals=[
            {"name": "core", "required": True, "result": "pass"},
        ],
    )
    assert res["ok"], res["violations"]
    assert res["primary_reason"] == REASON_OK
    assert res["required_passed"] == ["core"]
    assert res["required_missing"] == []


def test_cl10_resolves_with_optional_seen() -> None:
    res = resolve_required_evals(
        declared_catalog=[
            {"name": "core", "required": True},
            {"name": "smoke", "required": False},
        ],
        submitted_evals=[
            {"name": "core", "required": True, "result": "pass"},
            {"name": "smoke", "required": False, "result": "pass"},
        ],
    )
    assert res["ok"]
    assert "smoke" in res["optional_seen"]


def test_cl10_resolver_rejects_non_sequence() -> None:
    with pytest.raises(RequiredEvalResolverError):
        resolve_required_evals(declared_catalog={}, submitted_evals=[])  # type: ignore[arg-type]


# --- CL-11 red team -----------------------------------------------------


def test_cl11_required_missing_blocks() -> None:
    res = resolve_required_evals(
        declared_catalog=[{"name": "core", "required": True}],
        submitted_evals=[],
    )
    assert not res["ok"]
    assert res["primary_reason"] == REASON_REQUIRED_MISSING
    assert res["required_missing"] == ["core"]


def test_cl11_required_failed_blocks() -> None:
    res = resolve_required_evals(
        declared_catalog=[{"name": "core", "required": True}],
        submitted_evals=[{"name": "core", "required": True, "result": "fail"}],
    )
    assert not res["ok"]
    # Missing is more severe than failed; here only failed exists.
    assert res["primary_reason"] == REASON_REQUIRED_FAILED


def test_cl11_duplicate_evals_blocks() -> None:
    res = resolve_required_evals(
        declared_catalog=[{"name": "core", "required": True}],
        submitted_evals=[
            {"name": "core", "required": True, "result": "pass"},
            {"name": "core", "required": True, "result": "pass"},
        ],
    )
    assert not res["ok"]
    assert "core" in res["duplicates"]
    assert res["primary_reason"] == REASON_DUPLICATE


def test_cl11_unsupported_eval_blocks() -> None:
    res = resolve_required_evals(
        declared_catalog=[{"name": "core", "required": True}],
        submitted_evals=[
            {"name": "core", "required": True, "result": "pass"},
            {"name": "unknown_eval", "required": False, "result": "pass"},
        ],
    )
    assert not res["ok"]
    assert "unknown_eval" in res["unsupported"]
    assert res["primary_reason"] == REASON_UNSUPPORTED


def test_cl11_optional_marked_required_blocks() -> None:
    res = resolve_required_evals(
        declared_catalog=[{"name": "smoke", "required": False}],
        submitted_evals=[{"name": "smoke", "required": True, "result": "pass"}],
    )
    assert not res["ok"]
    assert any(v["reason_code"] == REASON_OPTIONAL_AS_REQUIRED for v in res["violations"])


def test_cl11_required_marked_optional_blocks() -> None:
    res = resolve_required_evals(
        declared_catalog=[{"name": "core", "required": True}],
        submitted_evals=[{"name": "core", "required": False, "result": "pass"}],
    )
    assert not res["ok"]
    assert any(v["reason_code"] == REASON_REQUIRED_AS_OPTIONAL for v in res["violations"])


def test_cl11_mixed_results_with_missing_picks_missing_as_primary() -> None:
    res = resolve_required_evals(
        declared_catalog=[
            {"name": "core", "required": True},
            {"name": "second", "required": True},
        ],
        submitted_evals=[
            {"name": "second", "required": True, "result": "fail"},
        ],
    )
    assert not res["ok"]
    assert res["primary_reason"] == REASON_REQUIRED_MISSING
    # supporting reasons still preserved
    assert any(v["reason_code"] == REASON_REQUIRED_FAILED for v in res["violations"])


# --- CL-12 fix pass: eval summary -------------------------------------


def test_cl12_eval_summary_pass_shape() -> None:
    res = resolve_required_evals(
        declared_catalog=[{"name": "core", "required": True}],
        submitted_evals=[{"name": "core", "required": True, "result": "pass"}],
    )
    summary = build_eval_summary(summary_id="evs-1", trace_id="t1", resolution=res)
    assert summary["status"] == "healthy"
    assert summary["primary_reason"] == REASON_OK
    assert summary["required_passed"] == ["core"]


def test_cl12_eval_summary_block_shape() -> None:
    res = resolve_required_evals(
        declared_catalog=[{"name": "core", "required": True}],
        submitted_evals=[],
    )
    summary = build_eval_summary(summary_id="evs-2", trace_id="t1", resolution=res)
    assert summary["status"] == "blocked"
    assert summary["primary_reason"] == REASON_REQUIRED_MISSING
