"""M3L-03 — Tests for the Gate / Shard Parity Measurement record.

These tests cover the measurement-only aggregation logic that fuses APR,
CLP, and the GitHub-driven shard summary into a single
``gate_shard_parity_record``. The builder must never run tests, never
invoke the shard runner, never recompute selection, and never compute
readiness or any gate decision.

Authority scope: observation_only. Canonical authority remains with the
systems declared in docs/architecture/system_registry.md.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.contracts import validate_artifact  # noqa: E402
from scripts.build_gate_shard_parity_record import (  # noqa: E402
    build_gate_shard_parity_record,
    classify_apr_status,
    classify_clp_status,
    classify_github_shard_status,
    detect_parity,
    extract_apr_shard_refs,
    extract_clp_shard_refs,
    extract_github_shard_refs,
    find_missing_artifact_refs,
)

_EXAMPLE_PATH = (
    REPO_ROOT / "contracts" / "examples" / "gate_shard_parity_record.example.json"
)
_SCHEMA_PATH = REPO_ROOT / "contracts" / "schemas" / "gate_shard_parity_record.schema.json"

CANONICAL_REFS: tuple[str, ...] = (
    "outputs/pr_test_shards/changed_scope.json",
    "outputs/pr_test_shards/contract.json",
    "outputs/pr_test_shards/governance.json",
    "outputs/pr_test_shards/pr_test_shards_summary.json",
)

_FORBIDDEN_AUTHORITY_TOKENS = (
    "approve",
    "approval",
    "certify",
    "certification",
    "promote",
    "promotion",
    "enforce",
    "enforcement",
    "decide",
    "decision",
    "authorize",
    "authorization",
    "verdict",
)


# ---------------------------------------------------------------------------
# Synthetic input artifacts
# ---------------------------------------------------------------------------


def _make_apr(*, status: str = "pass", refs: tuple[str, ...] = CANONICAL_REFS) -> dict[str, Any]:
    return {
        "artifact_type": "agent_pr_precheck_result",
        "overall_status": status,
        "selected_test_refs": list(refs),
    }


def _make_clp(*, status: str = "pass", refs: tuple[str, ...] = CANONICAL_REFS) -> dict[str, Any]:
    return {
        "artifact_type": "core_loop_pre_pr_gate_result",
        "gate_status": status,
        "evl_shard_evidence": {
            "evl_shard_artifact_refs": list(refs),
            "evl_shard_status": status if status in {"pass", "block", "unknown"} else "unknown",
        },
    }


def _make_summary(
    *,
    overall: str = "pass",
    refs: tuple[str, ...] = CANONICAL_REFS,
    blocking: tuple[str, ...] = (),
) -> dict[str, Any]:
    return {
        "artifact_type": "pr_test_shards_summary",
        "overall_status": overall,
        "shard_artifact_refs": list(refs),
        "blocking_reasons": list(blocking),
    }


def _materialize_refs(repo_root: Path, refs: tuple[str, ...]) -> None:
    """Create empty placeholder files for each ref under ``repo_root``."""
    for ref in refs:
        path = (repo_root / ref).resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}", encoding="utf-8")


def _build(
    *,
    repo_root: Path,
    apr: dict[str, Any] | None,
    clp: dict[str, Any] | None,
    summary: dict[str, Any] | None,
    work_item_id: str = "M3L-03-TEST",
) -> dict[str, Any]:
    return build_gate_shard_parity_record(
        work_item_id=work_item_id,
        base_ref="origin/main",
        head_ref="HEAD",
        apr_result=apr,
        clp_result=clp,
        m3l_result=None,
        shard_summary=summary,
        apr_result_ref="outputs/agent_pr_precheck/agent_pr_precheck_result.json"
        if apr is not None
        else None,
        clp_result_ref="outputs/core_loop_pre_pr_gate/core_loop_pre_pr_gate_result.json"
        if clp is not None
        else None,
        m3l_result_ref=None,
        shard_summary_ref="outputs/pr_test_shards/pr_test_shards_summary.json"
        if summary is not None
        else None,
        repo_root=repo_root,
    )


# ---------------------------------------------------------------------------
# Schema / example
# ---------------------------------------------------------------------------


def test_canonical_example_validates_against_schema():
    data = json.loads(_EXAMPLE_PATH.read_text(encoding="utf-8"))
    validate_artifact(data, "gate_shard_parity_record")


def test_schema_forbids_present_aligned_without_refs():
    """An aligned record with empty shard_artifact_refs must fail validation."""
    forged = json.loads(_EXAMPLE_PATH.read_text(encoding="utf-8"))
    forged["shard_artifact_refs"] = []
    forged["apr_shard_refs"] = []
    forged["clp_shard_refs"] = []
    forged["github_shard_refs"] = []
    with pytest.raises(Exception):
        validate_artifact(forged, "gate_shard_parity_record")


# ---------------------------------------------------------------------------
# Case 1 — All systems aligned
# ---------------------------------------------------------------------------


def test_all_systems_aligned(tmp_path):
    _materialize_refs(tmp_path, CANONICAL_REFS)
    record = _build(
        repo_root=tmp_path,
        apr=_make_apr(),
        clp=_make_clp(),
        summary=_make_summary(),
    )
    validate_artifact(record, "gate_shard_parity_record")
    assert record["parity_status"] == "aligned"
    assert record["github_escape"] is False
    assert record["apr_clp_mismatch"] is False
    assert record["clp_github_mismatch"] is False
    assert record["missing_artifact_refs"] == []
    assert record["mismatch_findings"] == []
    assert record["reason_codes"] == []
    assert record["apr_status"] == "pass"
    assert record["clp_status"] == "pass"
    assert record["github_shard_status"] == "pass"
    assert record["authority_scope"] == "observation_only"


# ---------------------------------------------------------------------------
# Case 2 — APR pass + GitHub fail -> drift + github_escape
# ---------------------------------------------------------------------------


def test_apr_pass_github_fail_drift_with_github_escape(tmp_path):
    _materialize_refs(tmp_path, CANONICAL_REFS)
    summary = _make_summary(
        overall="block",
        blocking=("contract:required_shard_failed",),
    )
    record = _build(
        repo_root=tmp_path,
        apr=_make_apr(status="pass"),
        clp=_make_clp(status="pass"),
        summary=summary,
    )
    validate_artifact(record, "gate_shard_parity_record")
    assert record["parity_status"] == "drift"
    assert record["github_escape"] is True
    assert record["clp_github_mismatch"] is True
    assert record["github_shard_status"] == "fail"
    assert "github_escape_apr_pass_github_non_pass" in record["reason_codes"]
    # Mismatch findings must reference shard artifacts (artifact-backed evidence).
    codes = {f["code"] for f in record["mismatch_findings"]}
    assert "github_escape_apr_pass_github_non_pass" in codes


# ---------------------------------------------------------------------------
# Case 3 — CLP pass + GitHub fail -> drift + clp_github_mismatch
# ---------------------------------------------------------------------------


def test_clp_pass_github_fail_drift_with_clp_github_mismatch(tmp_path):
    _materialize_refs(tmp_path, CANONICAL_REFS)
    summary = _make_summary(
        overall="block",
        blocking=("governance:required_shard_failed",),
    )
    # Mark APR non-pass so we isolate the CLP/GitHub mismatch case.
    record = _build(
        repo_root=tmp_path,
        apr=_make_apr(status="block"),
        clp=_make_clp(status="pass"),
        summary=summary,
    )
    validate_artifact(record, "gate_shard_parity_record")
    assert record["parity_status"] == "drift"
    assert record["github_escape"] is False
    assert record["clp_github_mismatch"] is True
    assert "clp_github_mismatch_clp_pass_github_non_pass" in record["reason_codes"]


# ---------------------------------------------------------------------------
# Case 4 — APR and CLP reference different shard refs -> drift
# ---------------------------------------------------------------------------


def test_apr_clp_ref_set_mismatch(tmp_path):
    _materialize_refs(tmp_path, CANONICAL_REFS)
    apr = _make_apr(refs=CANONICAL_REFS)
    # CLP references a different (smaller) shard set.
    clp_refs = CANONICAL_REFS[:2] + (
        "outputs/pr_test_shards/runtime_core.json",
    )
    _materialize_refs(tmp_path, ("outputs/pr_test_shards/runtime_core.json",))
    clp = _make_clp(refs=clp_refs)
    record = _build(
        repo_root=tmp_path,
        apr=apr,
        clp=clp,
        summary=_make_summary(),
    )
    validate_artifact(record, "gate_shard_parity_record")
    assert record["apr_clp_mismatch"] is True
    assert record["parity_status"] == "drift"
    assert "apr_clp_shard_ref_mismatch" in record["reason_codes"]


# ---------------------------------------------------------------------------
# Case 5 — Missing shard summary -> unknown with reason codes
# ---------------------------------------------------------------------------


def test_missing_shard_summary_unknown(tmp_path):
    _materialize_refs(tmp_path, CANONICAL_REFS)
    record = _build(
        repo_root=tmp_path,
        apr=_make_apr(),
        clp=_make_clp(),
        summary=None,
    )
    validate_artifact(record, "gate_shard_parity_record")
    assert record["parity_status"] == "unknown"
    assert record["github_shard_status"] == "missing"
    assert "shard_summary_missing" in record["reason_codes"]


# ---------------------------------------------------------------------------
# Case 6 — Missing APR or CLP result -> unknown with reason codes
# ---------------------------------------------------------------------------


def test_missing_apr_unknown(tmp_path):
    _materialize_refs(tmp_path, CANONICAL_REFS)
    record = _build(
        repo_root=tmp_path,
        apr=None,
        clp=_make_clp(),
        summary=_make_summary(),
    )
    validate_artifact(record, "gate_shard_parity_record")
    assert record["parity_status"] == "unknown"
    assert record["apr_status"] == "missing"
    assert "apr_result_missing" in record["reason_codes"]


def test_missing_clp_unknown(tmp_path):
    _materialize_refs(tmp_path, CANONICAL_REFS)
    record = _build(
        repo_root=tmp_path,
        apr=_make_apr(),
        clp=None,
        summary=_make_summary(),
    )
    validate_artifact(record, "gate_shard_parity_record")
    assert record["parity_status"] == "unknown"
    assert record["clp_status"] == "missing"
    assert "clp_result_missing" in record["reason_codes"]


# ---------------------------------------------------------------------------
# Case 7 — Partial refs (referenced but not present on disk) -> partial
# ---------------------------------------------------------------------------


def test_partial_refs_missing_on_disk(tmp_path):
    # Materialize only a subset of the canonical refs.
    present_subset = CANONICAL_REFS[:2]
    _materialize_refs(tmp_path, present_subset)
    record = _build(
        repo_root=tmp_path,
        apr=_make_apr(),
        clp=_make_clp(),
        summary=_make_summary(),
    )
    validate_artifact(record, "gate_shard_parity_record")
    assert record["parity_status"] == "partial"
    # Missing refs surface explicitly.
    missing = set(record["missing_artifact_refs"])
    assert missing == set(CANONICAL_REFS) - set(present_subset)
    assert "shard_artifact_missing_on_disk" in record["reason_codes"]


# ---------------------------------------------------------------------------
# Case 8 — Builder must NOT rerun tests
# ---------------------------------------------------------------------------


def test_builder_does_not_invoke_subprocess(tmp_path, monkeypatch):
    """The builder must aggregate artifacts only — no subprocess / no test exec."""
    import subprocess as _subprocess

    sentinel: dict[str, Any] = {"called": False}

    def _explode(*args, **kwargs):  # pragma: no cover - sentinel
        sentinel["called"] = True
        raise AssertionError(
            "build_gate_shard_parity_record must not run subprocesses"
        )

    monkeypatch.setattr(_subprocess, "run", _explode)
    monkeypatch.setattr(_subprocess, "Popen", _explode)
    monkeypatch.setattr(_subprocess, "check_call", _explode)
    monkeypatch.setattr(_subprocess, "check_output", _explode)
    monkeypatch.setattr(_subprocess, "call", _explode)

    _materialize_refs(tmp_path, CANONICAL_REFS)
    record = _build(
        repo_root=tmp_path,
        apr=_make_apr(),
        clp=_make_clp(),
        summary=_make_summary(),
    )
    validate_artifact(record, "gate_shard_parity_record")
    assert sentinel["called"] is False


def test_builder_does_not_mutate_inputs(tmp_path):
    """The builder must not mutate any input artifact dict."""
    _materialize_refs(tmp_path, CANONICAL_REFS)
    apr = _make_apr()
    clp = _make_clp()
    summary = _make_summary()
    apr_snapshot = json.dumps(apr, sort_keys=True)
    clp_snapshot = json.dumps(clp, sort_keys=True)
    summary_snapshot = json.dumps(summary, sort_keys=True)

    _build(repo_root=tmp_path, apr=apr, clp=clp, summary=summary)

    assert json.dumps(apr, sort_keys=True) == apr_snapshot
    assert json.dumps(clp, sort_keys=True) == clp_snapshot
    assert json.dumps(summary, sort_keys=True) == summary_snapshot


# ---------------------------------------------------------------------------
# Case 9 — Builder must NOT compute readiness or gate decisions
# ---------------------------------------------------------------------------


def test_record_has_no_readiness_or_gate_fields(tmp_path):
    _materialize_refs(tmp_path, CANONICAL_REFS)
    record = _build(
        repo_root=tmp_path,
        apr=_make_apr(),
        clp=_make_clp(),
        summary=_make_summary(),
    )
    forbidden_field_substrings = (
        "ready",
        "ready_status",
        "gate_decision",
        "promote",
        "approve",
        "certify",
        "enforce",
    )
    for key in record.keys():
        lowered = key.lower()
        for token in forbidden_field_substrings:
            # parity_status is allowed; never any *_ready_* / promotion / enforcement key.
            if token in lowered:
                assert lowered == "parity_status" or token == "parity_status", (
                    f"forbidden field token {token!r} appears in record key {key!r}"
                )


def test_record_does_not_carry_authority_verbs_in_reason_codes(tmp_path):
    """Reason codes must use measurement vocabulary, never authority verbs."""
    _materialize_refs(tmp_path, CANONICAL_REFS[:1])
    summary = _make_summary(
        overall="block",
        blocking=("contract:required_shard_failed",),
    )
    record = _build(
        repo_root=tmp_path,
        apr=_make_apr(status="pass"),
        clp=_make_clp(status="pass"),
        summary=summary,
    )
    blob = json.dumps(record).lower()
    for token in _FORBIDDEN_AUTHORITY_TOKENS:
        assert token not in blob, (
            f"authority token {token!r} leaked into parity record"
        )


# ---------------------------------------------------------------------------
# Helpers — ref extraction and status classification
# ---------------------------------------------------------------------------


def test_extract_apr_shard_refs_handles_missing():
    assert extract_apr_shard_refs(None) == []
    assert extract_apr_shard_refs({}) == []
    assert extract_apr_shard_refs({"selected_test_refs": ["a", "b"]}) == ["a", "b"]


def test_extract_clp_shard_refs_handles_missing():
    assert extract_clp_shard_refs(None) == []
    assert extract_clp_shard_refs({}) == []
    assert extract_clp_shard_refs(
        {"evl_shard_evidence": {"evl_shard_artifact_refs": ["a"]}}
    ) == ["a"]


def test_extract_github_shard_refs_handles_missing():
    assert extract_github_shard_refs(None) == []
    assert extract_github_shard_refs({}) == []
    assert extract_github_shard_refs({"shard_artifact_refs": ["a"]}) == ["a"]


def test_classify_apr_status_handles_missing():
    assert classify_apr_status(None) == "missing"
    assert classify_apr_status({"overall_status": "pass"}) == "pass"
    assert classify_apr_status({"overall_status": "warn"}) == "warn"
    assert classify_apr_status({"overall_status": "garbage"}) == "unknown"


def test_classify_clp_status_handles_missing():
    assert classify_clp_status(None) == "missing"
    assert classify_clp_status({"gate_status": "pass"}) == "pass"
    assert classify_clp_status({"gate_status": "warn"}) == "warn"
    assert classify_clp_status({"gate_status": "garbage"}) == "unknown"


def test_classify_github_shard_status_translates_blocking_reason():
    assert classify_github_shard_status(None) == "missing"
    pass_summary = _make_summary()
    assert classify_github_shard_status(pass_summary) == "pass"
    fail_summary = _make_summary(
        overall="block", blocking=("contract:required_shard_failed",)
    )
    assert classify_github_shard_status(fail_summary) == "fail"
    missing_summary = _make_summary(
        overall="block", blocking=("contract:required_shard_missing_artifact",)
    )
    assert classify_github_shard_status(missing_summary) == "missing"
    unknown_summary = _make_summary(
        overall="block", blocking=("contract:required_shard_unknown",)
    )
    assert classify_github_shard_status(unknown_summary) == "unknown"


def test_find_missing_artifact_refs(tmp_path):
    _materialize_refs(tmp_path, CANONICAL_REFS[:2])
    missing = find_missing_artifact_refs(list(CANONICAL_REFS), repo_root=tmp_path)
    assert set(missing) == set(CANONICAL_REFS[2:])


def test_detect_parity_pure_unit():
    """Sanity check the pure detection function on aligned inputs."""
    parity, escape, apr_clp, clp_gh, findings, reasons = detect_parity(
        apr_status="pass",
        clp_status="pass",
        github_shard_status="pass",
        apr_shard_refs=list(CANONICAL_REFS),
        clp_shard_refs=list(CANONICAL_REFS),
        github_shard_refs=list(CANONICAL_REFS),
        missing_artifact_refs=[],
        apr_present=True,
        clp_present=True,
        summary_present=True,
    )
    assert parity == "aligned"
    assert escape is False
    assert apr_clp is False
    assert clp_gh is False
    assert findings == []
    assert reasons == []
