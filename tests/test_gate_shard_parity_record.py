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


# ---------------------------------------------------------------------------
# M3L-03D — Pytest selection mapping coverage for the M3L-03 changed-path set.
# Regression coverage for the contract preflight failure where adding a new
# governed contract surface (the gate_shard_parity_record schema/example/builder)
# did not bind tests/test_contracts.py to the selection, producing
# pytest_selection_missing / PYTEST_SELECTION_MISMATCH. Each test below pins
# the artifact-backed mapping evidence so the binding cannot regress silently.
# ---------------------------------------------------------------------------


_OVERRIDE_PATH = REPO_ROOT / "docs" / "governance" / "preflight_required_surface_test_overrides.json"
_POLICY_PATH = REPO_ROOT / "docs" / "governance" / "pytest_pr_selection_integrity_policy.json"

_M3L_03_PATHS: tuple[str, ...] = (
    "scripts/build_gate_shard_parity_record.py",
    "contracts/schemas/gate_shard_parity_record.schema.json",
    "contracts/examples/gate_shard_parity_record.example.json",
    "tests/test_gate_shard_parity_record.py",
)


def _load_override_map() -> dict[str, list[str]]:
    return json.loads(_OVERRIDE_PATH.read_text(encoding="utf-8"))


def _load_policy_surface_rules() -> dict[str, list[str]]:
    policy = json.loads(_POLICY_PATH.read_text(encoding="utf-8"))
    rules: dict[str, list[str]] = {}
    for rule in policy.get("surface_rules") or []:
        if not isinstance(rule, dict):
            continue
        prefix = rule.get("path_prefix")
        targets = rule.get("required_test_targets") or []
        if isinstance(prefix, str) and isinstance(targets, list):
            rules[prefix] = [t for t in targets if isinstance(t, str)]
    return rules


def test_m3l_03_schema_path_maps_to_test_contracts_and_parity_test() -> None:
    overrides = _load_override_map()
    targets = overrides.get("contracts/schemas/gate_shard_parity_record.schema.json", [])
    assert "tests/test_contracts.py" in targets, (
        "schema must map to test_contracts.py so contract preflight selects it"
    )
    assert "tests/test_gate_shard_parity_record.py" in targets


def test_m3l_03_example_path_maps_to_test_contracts_and_parity_test() -> None:
    overrides = _load_override_map()
    targets = overrides.get("contracts/examples/gate_shard_parity_record.example.json", [])
    assert "tests/test_contracts.py" in targets
    assert "tests/test_gate_shard_parity_record.py" in targets


def test_m3l_03_builder_script_maps_to_parity_test() -> None:
    overrides = _load_override_map()
    targets = overrides.get("scripts/build_gate_shard_parity_record.py", [])
    assert "tests/test_gate_shard_parity_record.py" in targets


def test_m3l_03_paths_have_explicit_selection_integrity_surface_rules() -> None:
    rules = _load_policy_surface_rules()
    for prefix in (
        "scripts/build_gate_shard_parity_record.py",
        "contracts/schemas/gate_shard_parity_record.schema.json",
        "contracts/examples/gate_shard_parity_record.example.json",
    ):
        assert prefix in rules, f"missing surface_rule for {prefix}"
        assert "tests/test_gate_shard_parity_record.py" in rules[prefix]
    # Schema and example must additionally pin tests/test_contracts.py.
    for prefix in (
        "contracts/schemas/gate_shard_parity_record.schema.json",
        "contracts/examples/gate_shard_parity_record.example.json",
    ):
        assert "tests/test_contracts.py" in rules[prefix]


def test_m3l_03_changed_path_set_produces_allow_selection_integrity() -> None:
    """The full M3L-03 governed changed-path set must produce ALLOW once the
    required test targets are selected."""
    from spectrum_systems.modules.runtime.pytest_selection_integrity import (
        evaluate_pytest_selection_integrity,
    )

    selected = [
        "tests/test_contracts.py",
        "tests/test_gate_shard_parity_record.py",
    ]
    result = evaluate_pytest_selection_integrity(
        changed_paths=list(_M3L_03_PATHS) + ["contracts/standards-manifest.json"],
        selected_test_targets=selected,
        required_test_targets=selected,
        pytest_execution_record={"executed": True, "selection_reason_codes": []},
        policy_path=_POLICY_PATH,
        generated_at="2026-05-02T00:00:00Z",
    )
    assert result.decision == "ALLOW", result.blocking_reasons
    assert result.blocking_reasons == []


def test_m3l_03_paths_select_tests_via_resolve_required_tests() -> None:
    """End-to-end mapping observation: resolve_required_tests must include the
    paired contracts/parity test targets after the override file edit."""
    from spectrum_systems.modules.runtime.pr_test_selection import resolve_required_tests

    targets_by_path = resolve_required_tests(REPO_ROOT, list(_M3L_03_PATHS))
    schema_targets = set(targets_by_path["contracts/schemas/gate_shard_parity_record.schema.json"])
    example_targets = set(targets_by_path["contracts/examples/gate_shard_parity_record.example.json"])
    builder_targets = set(targets_by_path["scripts/build_gate_shard_parity_record.py"])
    assert "tests/test_contracts.py" in schema_targets
    assert "tests/test_gate_shard_parity_record.py" in schema_targets
    assert "tests/test_contracts.py" in example_targets
    assert "tests/test_gate_shard_parity_record.py" in example_targets
    assert "tests/test_gate_shard_parity_record.py" in builder_targets


# ---------------------------------------------------------------------------
# Generated artifact family mapping — pre-existing needle-match coverage.
# These tests pin the observation that representative generated artifact paths
# resolve to at least one required test target through the canonical needle
# match, AND that they remain non-governed (so they do NOT silently expand the
# integrity policy's governed_surface_prefixes set).
# ---------------------------------------------------------------------------


_GENERATED_FAMILY_REPRESENTATIVES: tuple[tuple[str, str], ...] = (
    (
        "artifacts/tls/system_evidence_attachment.json",
        "tls",
    ),
    (
        "artifacts/certification_judgment_40_explicit/checkpoint-1.json",
        "certification_judgment_40_explicit",
    ),
    (
        "artifacts/review_fix_loop_36_explicit/checkpoint-1.json",
        "review_fix_loop_36_explicit",
    ),
    (
        "artifacts/ops_master_01/checkpoint-1.json",
        "ops_master_01",
    ),
    (
        "artifacts/rdx_runs/AUTHENTICITY-HARDGATE-24-01-artifact-trace.json",
        "rdx_runs",
    ),
    (
        "governance/reports/ecosystem-architecture-graph.json",
        "governance_reports",
    ),
    (
        "docs/governance-reports/ecosystem-dashboard.md",
        "docs_governance_reports",
    ),
    (
        "ecosystem/dependency-graph.json",
        "ecosystem",
    ),
)


def test_generated_artifact_families_resolve_to_at_least_one_test_target() -> None:
    """Each representative generated artifact path must resolve to at least one
    required test target via needle matching, so the contract preflight's
    pytest_selection_missing diagnostic does not surface them as orphans."""
    from spectrum_systems.modules.runtime.pr_test_selection import resolve_required_tests

    paths = [path for path, _label in _GENERATED_FAMILY_REPRESENTATIVES]
    targets_by_path = resolve_required_tests(REPO_ROOT, paths)
    for path, label in _GENERATED_FAMILY_REPRESENTATIVES:
        assert targets_by_path.get(path), (
            f"{label} representative {path} resolved no required tests via needle match"
        )


def test_generated_artifact_families_remain_non_governed() -> None:
    """Generated artifact families must NOT be silently promoted into the
    governed surface set — broadening governed scope would force every
    timestamp-only regen to require a test selection."""
    from spectrum_systems.modules.runtime.pr_test_selection import (
        classify_changed_path,
        is_governed_path,
    )

    for path, label in _GENERATED_FAMILY_REPRESENTATIVES:
        classification = classify_changed_path(path)
        assert classification["is_governed"] is False, (
            f"{label} representative {path} classified as governed; mapping "
            "would expand governed scope without explicit policy review"
        )
        assert is_governed_path(path) is False, (
            f"{label} representative {path} matches a governed surface prefix"
        )


def test_unrelated_random_path_is_not_classified_as_governed_generated_artifact() -> None:
    """Smoke test that a random non-governance path does not land in any of
    the generated artifact mapping branches."""
    from spectrum_systems.modules.runtime.pr_test_selection import (
        classify_changed_path,
        is_governed_path,
    )

    sentinel = "examples/some_unrelated_module/notes.txt"
    classification = classify_changed_path(sentinel)
    assert classification["is_governed"] is False
    assert is_governed_path(sentinel) is False
    assert classification["surface"] == "other"
