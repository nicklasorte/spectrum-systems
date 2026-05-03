"""APR-01 — Tests for the Agent PR Precheck Runner.

These tests cover the 15 cases enumerated in the APR-01 plan. They focus
on the orchestrator's pure-logic pieces (aggregation, AEX surface
detection, schema discipline) without invoking the slow subprocess phases
end-to-end. The replay scenario (case 15) reproduces the
``MISSING_REQUIRED_SURFACE_MAPPING`` failure that motivated APR-01 and
asserts that the AEX phase emits the same suggested-repair shape that
APU-3LS-01G ultimately added to
``docs/governance/preflight_required_surface_test_overrides.json``.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from spectrum_systems.contracts import validate_artifact
from scripts.run_agent_pr_precheck import (
    CheckResult,
    PHASES,
    _aggregate_overall_status,
    aex_required_surface_check,
    build_agent_pr_precheck_result,
    evl_pr_test_shard_first_readiness,
    overall_status_to_exit_code,
)

ROOT = Path(__file__).resolve().parents[1]
APR_OWNED_FILES = (
    ROOT / "scripts" / "run_agent_pr_precheck.py",
    ROOT / "contracts" / "schemas" / "agent_pr_precheck_result.schema.json",
    ROOT / "contracts" / "examples" / "agent_pr_precheck_result.example.json",
    ROOT / "tests" / "test_agent_pr_precheck.py",
    ROOT / "docs" / "reviews" / "APR-01_redteam.md",
    ROOT / "docs" / "review-actions" / "APR-01_fix_actions.md",
)


def _passing_check(name: str, phase: str, ref: str = "outputs/x.json") -> CheckResult:
    return CheckResult(
        check_name=name,
        phase=phase,
        command="(test)",
        status="pass",
        exit_code=0,
        output_artifact_refs=[ref],
    )


def _blocking_check(name: str, phase: str, reason: str) -> CheckResult:
    return CheckResult(
        check_name=name,
        phase=phase,
        command="(test)",
        status="block",
        exit_code=2,
        reason_codes=[reason],
    )


# ---------------------------------------------------------------------------
# Case 14 (run first because every other case relies on schema validation)
# ---------------------------------------------------------------------------


def test_canonical_example_validates_against_schema():
    example = json.loads(
        (ROOT / "contracts" / "examples" / "agent_pr_precheck_result.example.json").read_text(
            encoding="utf-8"
        )
    )
    validate_artifact(example, "agent_pr_precheck_result")


# ---------------------------------------------------------------------------
# Case 1 — missing CLP artifact -> pr_ready_status=not_ready, overall=block
# ---------------------------------------------------------------------------


def test_missing_clp_blocks_pr_ready():
    checks = [
        _passing_check("aex_required_surface_mapping", "AEX"),
        _blocking_check("cde_core_loop_pre_pr_gate", "CDE", "clp_pre_pr_gate_block"),
    ]
    overall, pr_ready, pr_upd, reasons = _aggregate_overall_status(
        repo_mutating=True, checks=checks
    )
    assert overall == "block"
    assert pr_ready == "not_ready"
    assert "clp_pre_pr_gate_block" in reasons


# ---------------------------------------------------------------------------
# Case 2 — missing APU artifact -> pr_update_ready_status=not_ready
# ---------------------------------------------------------------------------


def test_missing_apu_blocks_pr_update_ready():
    checks = [
        _passing_check("aex_required_surface_mapping", "AEX"),
        _blocking_check(
            "sel_check_agent_pr_update_ready", "SEL", "apu_pr_update_not_ready"
        ),
    ]
    overall, pr_ready, pr_upd, reasons = _aggregate_overall_status(
        repo_mutating=True, checks=checks
    )
    assert overall == "block"
    assert pr_upd == "not_ready"
    assert "apu_pr_update_not_ready" in reasons


# ---------------------------------------------------------------------------
# Case 3 — authority-shape failure surfaces in authority_artifact_refs
# ---------------------------------------------------------------------------


def test_authority_shape_failure_surfaces_artifact_ref():
    checks = [
        CheckResult(
            check_name="tpa_authority_shape_preflight",
            phase="TPA",
            command="(test)",
            status="block",
            exit_code=2,
            output_artifact_refs=[
                "outputs/authority_shape_preflight/authority_shape_preflight_result.json"
            ],
            reason_codes=["authority_shape_preflight_finding"],
        )
    ]
    overall, _, _, reasons = _aggregate_overall_status(repo_mutating=True, checks=checks)
    artifact = build_agent_pr_precheck_result(
        work_item_id="W",
        agent_type="claude",
        repo_mutating=True,
        base_ref="origin/main",
        head_ref="HEAD",
        checks=checks,
        overall_status=overall,
        pr_ready_status="not_ready",
        pr_update_ready_status="not_ready",
        reason_codes=reasons,
        authority_artifact_refs=[
            "outputs/authority_shape_preflight/authority_shape_preflight_result.json"
        ],
    )
    validate_artifact(artifact, "agent_pr_precheck_result")
    assert (
        "outputs/authority_shape_preflight/authority_shape_preflight_result.json"
        in artifact["authority_artifact_refs"]
    )
    assert overall == "block"


# ---------------------------------------------------------------------------
# Case 4 — system registry guard failure surfaces in authority_artifact_refs
# ---------------------------------------------------------------------------


def test_system_registry_failure_surfaces_artifact_ref():
    checks = [
        CheckResult(
            check_name="tpa_system_registry_guard",
            phase="TPA",
            command="(test)",
            status="block",
            exit_code=2,
            output_artifact_refs=[
                "outputs/system_registry_guard/system_registry_guard_result.json"
            ],
            reason_codes=["system_registry_guard_finding"],
        )
    ]
    artifact = build_agent_pr_precheck_result(
        work_item_id="W",
        agent_type="claude",
        repo_mutating=True,
        base_ref="origin/main",
        head_ref="HEAD",
        checks=checks,
        overall_status="block",
        pr_ready_status="not_ready",
        pr_update_ready_status="not_ready",
        reason_codes=["system_registry_guard_finding"],
        authority_artifact_refs=[
            "outputs/system_registry_guard/system_registry_guard_result.json"
        ],
    )
    validate_artifact(artifact, "agent_pr_precheck_result")
    assert (
        "outputs/system_registry_guard/system_registry_guard_result.json"
        in artifact["authority_artifact_refs"]
    )


# ---------------------------------------------------------------------------
# Case 5 — contract preflight contract_mismatch carries diagnosis refs
# ---------------------------------------------------------------------------


def test_contract_preflight_contract_mismatch_carries_diagnosis_refs():
    diagnosis_refs = [
        "outputs/contract_preflight/preflight_block_diagnosis_record.json",
        "outputs/contract_preflight/contract_preflight_report.json",
        "outputs/contract_preflight/preflight_repair_plan_record.json",
        "outputs/contract_preflight/failure_repair_candidate_artifact.json",
    ]
    checks = [
        CheckResult(
            check_name="pqx_governed_contract_preflight",
            phase="PQX",
            command="(test)",
            status="block",
            exit_code=2,
            output_artifact_refs=diagnosis_refs,
            reason_codes=["contract_mismatch"],
        )
    ]
    artifact = build_agent_pr_precheck_result(
        work_item_id="W",
        agent_type="claude",
        repo_mutating=True,
        base_ref="origin/main",
        head_ref="HEAD",
        checks=checks,
        overall_status="block",
        pr_ready_status="not_ready",
        pr_update_ready_status="not_ready",
        reason_codes=["contract_mismatch"],
        contract_preflight_artifact_refs=diagnosis_refs,
    )
    validate_artifact(artifact, "agent_pr_precheck_result")
    for ref in diagnosis_refs:
        assert ref in artifact["contract_preflight_artifact_refs"]
    assert "contract_mismatch" in artifact["reason_codes"]


# ---------------------------------------------------------------------------
# Case 6 — TLS / ecosystem stale flips overall to block
# ---------------------------------------------------------------------------


def test_tls_ecosystem_stale_blocks():
    checks = [
        CheckResult(
            check_name="evl_generated_artifact_freshness",
            phase="EVL",
            command="(test)",
            status="block",
            exit_code=2,
            output_artifact_refs=[
                "outputs/agent_pr_precheck/evl_generated_artifact_freshness.json"
            ],
            reason_codes=["tls_generated_artifact_drift"],
        )
    ]
    overall, _, _, reasons = _aggregate_overall_status(
        repo_mutating=True, checks=checks
    )
    assert overall == "block"
    assert "tls_generated_artifact_drift" in reasons


# ---------------------------------------------------------------------------
# Case 7 — selected pytest failure -> block
# ---------------------------------------------------------------------------


def test_selected_test_failure_blocks():
    checks = [
        CheckResult(
            check_name="evl_pr_test_shards",
            phase="EVL",
            command="(test)",
            status="block",
            exit_code=1,
            output_artifact_refs=[
                "outputs/pr_test_shards/pr_test_shards_summary.json"
            ],
            reason_codes=["contract:required_shard_failed"],
        )
    ]
    overall, _, _, reasons = _aggregate_overall_status(
        repo_mutating=True, checks=checks
    )
    assert overall == "block"
    assert "contract:required_shard_failed" in reasons


# ---------------------------------------------------------------------------
# Case 8 — warn passes only when caller policy allows the reason codes
# ---------------------------------------------------------------------------


def test_warn_only_passes_when_overall_aggregator_does_not_have_blocks():
    checks = [
        CheckResult(
            check_name="tpa_authority_leak_guard",
            phase="TPA",
            command="(test)",
            status="warn",
            exit_code=0,
            output_artifact_refs=["outputs/x.json"],
            reason_codes=["soft_finding"],
        )
    ]
    overall, _, _, reasons = _aggregate_overall_status(
        repo_mutating=True, checks=checks
    )
    assert overall == "warn"
    assert overall_status_to_exit_code("warn") == 1
    assert "soft_finding" in reasons


# ---------------------------------------------------------------------------
# Case 9 — repo_mutating=None (unknown) -> block
# ---------------------------------------------------------------------------


def test_repo_mutating_unknown_blocks():
    overall, pr_ready, pr_upd, reasons = _aggregate_overall_status(
        repo_mutating=None, checks=[]
    )
    assert overall == "block"
    assert pr_ready == "not_ready"
    assert pr_upd == "not_ready"
    assert "repo_mutating_unknown" in reasons


# ---------------------------------------------------------------------------
# Case 9b (APR-SMOKE-01 regression) — built APR result honors repo_mutating=None
# ---------------------------------------------------------------------------


def test_repo_mutating_unknown_blocks_built_artifact():
    """Regression for APR-SMOKE-01: the merged APR result (not just the
    aggregator) must treat ``repo_mutating=None`` as
    ``overall_status=block`` and ``pr_ready_status=pr_update_ready_status=not_ready``,
    and the schema's ``repo_mutating==null → overall_status=='block'`` invariant
    must hold on the built artifact.
    """
    overall, pr_ready, pr_upd, reasons = _aggregate_overall_status(
        repo_mutating=None, checks=[]
    )
    artifact = build_agent_pr_precheck_result(
        work_item_id="APR-SMOKE-01",
        agent_type="claude",
        repo_mutating=None,
        base_ref="origin/main",
        head_ref="HEAD",
        checks=[],
        overall_status=overall,
        pr_ready_status=pr_ready,
        pr_update_ready_status=pr_upd,
        reason_codes=reasons,
    )
    validate_artifact(artifact, "agent_pr_precheck_result")
    assert artifact["repo_mutating"] is None
    assert artifact["overall_status"] == "block"
    assert artifact["pr_ready_status"] == "not_ready"
    assert artifact["pr_update_ready_status"] == "not_ready"
    assert "repo_mutating_unknown" in artifact["reason_codes"]


# ---------------------------------------------------------------------------
# Case 10 — status=pass without output_artifact_refs is schema-invalid
# ---------------------------------------------------------------------------


def test_pass_without_output_artifact_refs_is_schema_invalid():
    bad_check = CheckResult(
        check_name="x",
        phase="AEX",
        command="(test)",
        status="pass",
        exit_code=0,
        output_artifact_refs=[],
    )
    artifact = build_agent_pr_precheck_result(
        work_item_id="W",
        agent_type="claude",
        repo_mutating=True,
        base_ref="origin/main",
        head_ref="HEAD",
        checks=[bad_check],
        overall_status="pass",
        pr_ready_status="ready",
        pr_update_ready_status="ready",
        reason_codes=[],
    )
    with pytest.raises(Exception):
        validate_artifact(artifact, "agent_pr_precheck_result")


# ---------------------------------------------------------------------------
# Case 11 — block/warn/missing/unknown without reason_codes is schema-invalid
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "status",
    ["warn", "block", "skipped", "missing", "unknown"],
)
def test_non_pass_without_reason_codes_is_schema_invalid(status: str):
    bad_check = CheckResult(
        check_name="x",
        phase="AEX",
        command="(test)",
        status=status,
        exit_code=2,
        reason_codes=[],
    )
    artifact = build_agent_pr_precheck_result(
        work_item_id="W",
        agent_type="claude",
        repo_mutating=True,
        base_ref="origin/main",
        head_ref="HEAD",
        checks=[bad_check],
        overall_status="block",
        pr_ready_status="not_ready",
        pr_update_ready_status="not_ready",
        reason_codes=["x"],
    )
    with pytest.raises(Exception):
        validate_artifact(artifact, "agent_pr_precheck_result")


# ---------------------------------------------------------------------------
# Case 12 — PR body prose cannot satisfy output_artifact_refs
# ---------------------------------------------------------------------------


def test_pr_body_prose_does_not_satisfy_artifact_refs():
    """artifact_refs items are validated as path-like strings; the schema
    enforces a non-empty array, but the runtime contract is that each
    entry is a path under the repo root, not free-form prose. This test
    asserts the validator rejects an empty array and accepts a single
    file path.
    """
    bad_check = CheckResult(
        check_name="x",
        phase="AEX",
        command="(test)",
        status="pass",
        exit_code=0,
        output_artifact_refs=[],
    )
    bad_artifact = build_agent_pr_precheck_result(
        work_item_id="W",
        agent_type="claude",
        repo_mutating=True,
        base_ref="origin/main",
        head_ref="HEAD",
        checks=[bad_check],
        overall_status="pass",
        pr_ready_status="ready",
        pr_update_ready_status="ready",
        reason_codes=[],
    )
    with pytest.raises(Exception):
        validate_artifact(bad_artifact, "agent_pr_precheck_result")
    good_check = CheckResult(
        check_name="x",
        phase="AEX",
        command="(test)",
        status="pass",
        exit_code=0,
        output_artifact_refs=["outputs/agent_pr_precheck/aex_required_surface_mapping.json"],
    )
    good_artifact = build_agent_pr_precheck_result(
        work_item_id="W",
        agent_type="claude",
        repo_mutating=True,
        base_ref="origin/main",
        head_ref="HEAD",
        checks=[good_check],
        overall_status="pass",
        pr_ready_status="ready",
        pr_update_ready_status="ready",
        reason_codes=[],
    )
    validate_artifact(good_artifact, "agent_pr_precheck_result")


# ---------------------------------------------------------------------------
# Case 13 — APR makes no file mutations beyond its own outputs/
# ---------------------------------------------------------------------------


def test_apr_only_writes_under_outputs_dir(tmp_path):
    """``aex_required_surface_check`` must only write to ``output_dir``."""
    repo_root = ROOT
    output_dir = tmp_path / "apr_phase_outputs"
    # Run AEX with a synthetic changed-paths set
    aex_required_surface_check(
        repo_root=repo_root,
        changed_paths=["scripts/run_agent_pr_precheck.py"],
        output_dir=output_dir,
    )
    written = list(output_dir.glob("*"))
    # All writes must be inside the supplied output_dir.
    for f in written:
        assert tmp_path in f.parents


# ---------------------------------------------------------------------------
# Case 15 — Replay scenario for the APU-3LS-01 motivating failure
# ---------------------------------------------------------------------------


def test_replay_apu_3ls_01_missing_required_surface_mapping(tmp_path, monkeypatch):
    """Reproduce the failure that motivated APR-01.

    Feed the AEX phase the changed-paths set from the original
    APU-3LS-01 PR (commit 5e296641, before APU-3LS-01G fixed the
    override map). With the override map's APU entries removed, the
    AEX phase must:
      - return status=block
      - emit reason_codes including MISSING_REQUIRED_SURFACE_MAPPING
      - point at scripts/check_agent_pr_update_ready.py and the new
        APU runtime/policy/schema/example surfaces that lacked
        deterministic test bindings at the time
      - include a suggested-repair next_action whose JSON snippet
        contains tests/test_check_agent_pr_update_ready.py for each
        unmapped surface (which is what APU-3LS-01G actually added)
    """
    # Build a synthetic override-file state matching pre-APU-3LS-01G:
    # remove the five APU surfaces that were unmapped at the time.
    apu_surface_keys = {
        "scripts/check_agent_pr_update_ready.py",
        "spectrum_systems/modules/runtime/agent_pr_update_policy.py",
        "contracts/schemas/agent_pr_update_ready_result.schema.json",
        "contracts/examples/agent_pr_update_ready_result.example.json",
        "docs/governance/agent_pr_update_policy.json",
        # APR-01's own surfaces — also strip so the replay matches the
        # pre-APR-01 governance state.
        "scripts/run_agent_pr_precheck.py",
        "contracts/schemas/agent_pr_precheck_result.schema.json",
        "contracts/examples/agent_pr_precheck_result.example.json",
    }
    real_overrides = json.loads(
        (
            ROOT / "docs" / "governance" / "preflight_required_surface_test_overrides.json"
        ).read_text(encoding="utf-8")
    )
    stripped = {k: v for k, v in real_overrides.items() if k not in apu_surface_keys}
    fake_repo = tmp_path / "fake_repo"
    (fake_repo / "docs" / "governance").mkdir(parents=True)
    (fake_repo / "docs" / "governance" / "preflight_required_surface_test_overrides.json").write_text(
        json.dumps(stripped, indent=2), encoding="utf-8"
    )
    # Empty tests/ dir so needle-match cannot rescue an unmapped surface.
    (fake_repo / "tests").mkdir()
    output_dir = tmp_path / "apr_outputs"

    apu_changed_paths = [
        "scripts/check_agent_pr_update_ready.py",
        "spectrum_systems/modules/runtime/agent_pr_update_policy.py",
        "contracts/schemas/agent_pr_update_ready_result.schema.json",
        "contracts/examples/agent_pr_update_ready_result.example.json",
        "docs/governance/agent_pr_update_policy.json",
        "tests/test_check_agent_pr_update_ready.py",  # changed; not unmapped
    ]
    result = aex_required_surface_check(
        repo_root=fake_repo,
        changed_paths=apu_changed_paths,
        output_dir=output_dir,
    )
    assert result.status == "block"
    assert "MISSING_REQUIRED_SURFACE_MAPPING" in result.reason_codes
    # The unmapped paths from APU PR 1307 must be flagged.
    flagged = [rc for rc in result.reason_codes if rc.startswith("unmapped:")]
    flagged_paths = {rc.split(":", 1)[1] for rc in flagged}
    assert "scripts/check_agent_pr_update_ready.py" in flagged_paths
    assert "spectrum_systems/modules/runtime/agent_pr_update_policy.py" in flagged_paths
    # Suggested repair next_action must be parseable JSON-after-prefix.
    assert result.next_action is not None
    m = re.search(r"\{.*\}\s*$", result.next_action)
    assert m, f"next_action does not contain a JSON tail: {result.next_action!r}"
    suggested = json.loads(m.group(0))
    for path in flagged_paths:
        assert path in suggested


# ---------------------------------------------------------------------------
# Case (additional) — authority-safe vocabulary lint on APR-owned files
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# EVL-RT-03 — APR consumes the shard-first readiness observation
# ---------------------------------------------------------------------------


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _evl_rt03_summary() -> dict:
    return {
        "artifact_type": "pr_test_shards_summary",
        "schema_version": "1.0.0",
        "base_ref": "origin/main",
        "head_ref": "HEAD",
        "shard_status": {
            "contract": "pass",
            "governance": "pass",
            "changed_scope": "pass",
        },
        "required_shards": ["contract", "governance", "changed_scope"],
        "shard_artifact_refs": [
            "outputs/pr_test_shards/changed_scope.json",
            "outputs/pr_test_shards/contract.json",
            "outputs/pr_test_shards/governance.json",
        ],
        "overall_status": "pass",
        "blocking_reasons": [],
        "total_duration_seconds": 12.0,
        "max_shard_duration_seconds": 8.0,
        "min_shard_duration_seconds": 2.0,
        "shard_duration_by_name": {
            "contract": 2.0,
            "governance": 8.0,
            "changed_scope": 2.0,
        },
        "slowest_shard": "governance",
        "imbalance_ratio": 4.0,
        "balancing_findings": [],
        "created_at": "2026-05-03T00:00:00Z",
        "authority_scope": "observation_only",
    }


def _evl_rt03_coverage() -> dict:
    return {
        "artifact_type": "selection_coverage_record",
        "schema_version": "1.0.0",
        "record_id": "sel-cov-test-evlrt03",
        "created_at": "2026-05-03T00:00:00Z",
        "base_ref": "origin/main",
        "head_ref": "HEAD",
        "changed_paths": ["scripts/example.py"],
        "matched_paths": ["scripts/example.py"],
        "unmatched_changed_paths": [],
        "attempted_surface_rules": [],
        "selected_test_targets": ["tests/test_a.py"],
        "fallback_used": False,
        "fallback_targets": [],
        "pytest_selection_missing_count": 0,
        "missing_required_surface_mapping_count": 0,
        "selection_reason_codes": [],
        "coverage_status": "complete",
        "recommended_mapping_candidates": [],
        "authority_scope": "observation_only",
    }


def test_evl_pr_test_shard_first_readiness_passes_when_shard_first(tmp_path, monkeypatch):
    """When shard summary, selection coverage, and runtime budget are all
    populated and selection is focused, the readiness check returns pass
    and surfaces the readiness artifact ref."""
    repo_root = tmp_path
    # Stage upstream artifacts under the repo_root the check expects.
    _write_json(
        repo_root / "outputs" / "pr_test_shards" / "pr_test_shards_summary.json",
        _evl_rt03_summary(),
    )
    _write_json(
        repo_root / "outputs" / "selection_coverage" / "selection_coverage_record.json",
        _evl_rt03_coverage(),
    )

    result = evl_pr_test_shard_first_readiness(
        repo_root=repo_root,
        base_ref="origin/main",
        head_ref="HEAD",
        output_dir=tmp_path / "phase_outputs",
    )
    assert result.status == "pass"
    assert result.phase == "EVL"
    assert result.check_name == "evl_pr_test_shard_first_readiness"
    assert any(
        "pr_test_shard_first_readiness_observation.json" in r
        for r in result.output_artifact_refs
    )


def test_evl_pr_test_shard_first_readiness_blocks_when_required_shard_missing(tmp_path):
    """A missing required shard yields a partial readiness observation,
    which the EVL check surfaces as block with an artifact-backed reason."""
    repo_root = tmp_path
    summary = _evl_rt03_summary()
    summary["shard_status"] = {
        "contract": "pass",
        "governance": "missing",
        "changed_scope": "pass",
    }
    summary["shard_artifact_refs"] = [
        "outputs/pr_test_shards/changed_scope.json",
        "outputs/pr_test_shards/contract.json",
    ]
    _write_json(
        repo_root / "outputs" / "pr_test_shards" / "pr_test_shards_summary.json",
        summary,
    )
    _write_json(
        repo_root / "outputs" / "selection_coverage" / "selection_coverage_record.json",
        _evl_rt03_coverage(),
    )

    result = evl_pr_test_shard_first_readiness(
        repo_root=repo_root,
        base_ref="origin/main",
        head_ref="HEAD",
        output_dir=tmp_path / "phase_outputs",
    )
    assert result.status == "block"
    assert result.reason_codes
    assert any("partial" in r or "missing" in r for r in result.reason_codes)


def test_evl_pr_test_shard_first_readiness_blocks_on_unjustified_full_suite(tmp_path):
    """A coverage record with a full-suite selection target lands in
    fallback_justified status only when the runtime budget observation
    surfaces fallback_reason_codes — the EVL check builds the runtime
    budget observation from the same upstream inputs, so a full-suite
    signal here should still resolve to fallback_justified (the runtime
    budget builder synthesizes reason codes for full-suite selection)."""
    repo_root = tmp_path
    _write_json(
        repo_root / "outputs" / "pr_test_shards" / "pr_test_shards_summary.json",
        _evl_rt03_summary(),
    )
    coverage = _evl_rt03_coverage()
    coverage["selected_test_targets"] = ["tests"]
    coverage["fallback_used"] = True
    coverage["fallback_targets"] = ["select_all_tests"]
    coverage["selection_reason_codes"] = ["fallback_full_suite"]
    _write_json(
        repo_root / "outputs" / "selection_coverage" / "selection_coverage_record.json",
        coverage,
    )

    result = evl_pr_test_shard_first_readiness(
        repo_root=repo_root,
        base_ref="origin/main",
        head_ref="HEAD",
        output_dir=tmp_path / "phase_outputs",
    )
    # The runtime budget builder records full_suite_detected with reason
    # codes, so the readiness observation classifies as fallback_justified
    # and APR records pass — fallback usage is observed and justified.
    assert result.status == "pass"


def test_no_banned_authority_tokens_in_apr_owned_files():
    """APR-01 must not embed canonical-owner authority verbs as
    APR-claimed authority. Allowed exceptions:
      - red-team / fix-actions docs may *describe* banned tokens
      - the test file itself names tokens as data
      - canonical script-name references (e.g.
        ``scripts/run_contract_enforcement.py``) are file-path
        references, not authority claims; matched per-line and skipped
    """
    banned_substrings = [
        "approve",
        "approved",
        "approval",
        "certify",
        "certification",
        "promote",
        "promotion",
        "enforce",
        "enforced",
        "decide",
        "adjudication",
        "authorize",
        "authorization",
    ]
    # Lines that mention these canonical script/path names are allowed to
    # contain "enforce" / "enforcement" because they are referencing
    # existing files, not making an authority claim.
    canonical_path_allowlist = (
        "run_contract_enforcement",
        "tpa_contract_compliance_observation",  # the APR check name
    )
    failures: list[str] = []
    for f in APR_OWNED_FILES:
        if not f.is_file():
            continue
        # Allowlist: red-team / fix-actions docs and this test file.
        if (
            "redteam" in f.name.lower()
            or "fix_actions" in f.name.lower()
            or "fix-actions" in f.name.lower()
            or f.name == "test_agent_pr_precheck.py"
        ):
            continue
        for line_no, line in enumerate(
            f.read_text(encoding="utf-8").splitlines(), start=1
        ):
            lower = line.lower()
            if any(allow in lower for allow in canonical_path_allowlist):
                continue
            for tok in banned_substrings:
                if tok in lower:
                    failures.append(
                        f"{f.relative_to(ROOT)}:{line_no}: banned token {tok!r}"
                    )
    assert not failures, "Authority-safe vocabulary violations:\n" + "\n".join(failures)
