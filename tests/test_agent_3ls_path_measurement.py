"""M3L-02 — Tests for the Agent 3LS Path Measurement Record.

These tests cover the measurement-only aggregation logic that fuses
APR / CLP / APU / AGL evidence into a single
``agent_3ls_path_measurement_record``. They never recompute upstream
gates — they only assert that the aggregation reflects the inputs.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from spectrum_systems.contracts import validate_artifact
from spectrum_systems.modules.runtime.agent_3ls_path_measurement import (
    LOOP_ORDER,
    build_agent_3ls_path_measurement_record,
)

ROOT = Path(__file__).resolve().parents[1]
M3L_OWNED_FILES = (
    ROOT / "scripts" / "build_agent_3ls_path_measurement.py",
    ROOT / "spectrum_systems" / "modules" / "runtime" / "agent_3ls_path_measurement.py",
    ROOT / "contracts" / "schemas" / "agent_3ls_path_measurement_record.schema.json",
    ROOT / "contracts" / "examples" / "agent_3ls_path_measurement_record.example.json",
    ROOT / "tests" / "test_agent_3ls_path_measurement.py",
)


# ---------------------------------------------------------------------------
# Synthetic input artifacts
# ---------------------------------------------------------------------------


def _full_apr_pass() -> dict:
    checks = []
    phases = ("AEX", "TPA", "PQX", "EVL", "CDE", "SEL")
    for phase in phases:
        checks.append(
            {
                "check_name": f"{phase.lower()}_pass",
                "phase": phase,
                "command": "(test)",
                "status": "pass",
                "exit_code": 0,
                "output_artifact_refs": [f"outputs/x/{phase.lower()}.json"],
                "reason_codes": [],
            }
        )
    return {
        "artifact_type": "agent_pr_precheck_result",
        "schema_version": "1.0.0",
        "precheck_id": "apr-precheck-test",
        "created_at": "2026-05-01T00:00:00Z",
        "work_item_id": "M3L-02-TEST",
        "agent_type": "claude",
        "repo_mutating": True,
        "base_ref": "origin/main",
        "head_ref": "HEAD",
        "overall_status": "pass",
        "pr_ready_status": "ready",
        "pr_update_ready_status": "ready",
        "checks": checks,
        "phase_summaries": {
            phase: {
                "status": "pass",
                "check_count": 1,
                "fail_count": 0,
                "owner_system": phase,
                "reason_codes": [],
            }
            for phase in phases
        },
        "clp_artifact_ref": "outputs/core_loop_pre_pr_gate/core_loop_pre_pr_gate_result.json",
        "apu_artifact_ref": "outputs/agent_pr_update/agent_pr_update_ready_result.json",
        "contract_preflight_artifact_refs": [],
        "generated_artifact_freshness_refs": [],
        "authority_artifact_refs": [],
        "selected_test_refs": [],
        "first_failed_check": None,
        "first_missing_artifact": None,
        "reason_codes": [],
        "warnings": [],
        "trace_refs": [],
        "replay_refs": [],
        "authority_scope": "observation_only",
    }


def _apr_with_phase(phase_status_map: dict[str, str], *, first_failed: str | None = None) -> dict:
    apr = _full_apr_pass()
    new_checks = []
    new_phase_summaries = {}
    overall = "pass"
    pr_ready = "ready"
    pr_update_ready = "ready"
    for phase in ("AEX", "TPA", "PQX", "EVL", "CDE", "SEL"):
        status = phase_status_map.get(phase, "pass")
        if status == "pass":
            new_checks.append(
                {
                    "check_name": f"{phase.lower()}_pass",
                    "phase": phase,
                    "command": "(test)",
                    "status": "pass",
                    "exit_code": 0,
                    "output_artifact_refs": [f"outputs/x/{phase.lower()}.json"],
                    "reason_codes": [],
                }
            )
            new_phase_summaries[phase] = {
                "status": "pass",
                "check_count": 1,
                "fail_count": 0,
                "owner_system": phase,
                "reason_codes": [],
            }
        elif status == "block":
            new_checks.append(
                {
                    "check_name": f"{phase.lower()}_failed",
                    "phase": phase,
                    "command": "(test)",
                    "status": "block",
                    "exit_code": 2,
                    "output_artifact_refs": [],
                    "reason_codes": [f"{phase.lower()}_blocked"],
                }
            )
            new_phase_summaries[phase] = {
                "status": "block",
                "check_count": 1,
                "fail_count": 1,
                "owner_system": phase,
                "reason_codes": [f"{phase.lower()}_blocked"],
            }
            overall = "block"
            pr_ready = "not_ready"
            pr_update_ready = "not_ready"
        elif status == "skipped":
            new_checks.append(
                {
                    "check_name": f"{phase.lower()}_skipped",
                    "phase": phase,
                    "command": "(test)",
                    "status": "skipped",
                    "exit_code": None,
                    "output_artifact_refs": [],
                    "reason_codes": [f"{phase.lower()}_skipped"],
                }
            )
            new_phase_summaries[phase] = {
                "status": "skipped",
                "check_count": 1,
                "fail_count": 0,
                "owner_system": phase,
                "reason_codes": [f"{phase.lower()}_skipped"],
            }
        else:
            raise ValueError(f"unsupported synthetic status: {status}")
    apr["checks"] = new_checks
    apr["phase_summaries"] = new_phase_summaries
    apr["overall_status"] = overall
    apr["pr_ready_status"] = pr_ready
    apr["pr_update_ready_status"] = pr_update_ready
    apr["first_failed_check"] = first_failed
    return apr


# ---------------------------------------------------------------------------
# Case 0 — canonical example validates against the schema
# ---------------------------------------------------------------------------


def test_canonical_example_validates_against_schema():
    example = json.loads(
        (
            ROOT
            / "contracts"
            / "examples"
            / "agent_3ls_path_measurement_record.example.json"
        ).read_text(encoding="utf-8")
    )
    validate_artifact(example, "agent_3ls_path_measurement_record")


# ---------------------------------------------------------------------------
# Case 1 — full loop present -> loop_complete=true
# ---------------------------------------------------------------------------


def test_full_loop_present_loop_complete_true():
    apr = _full_apr_pass()
    record = build_agent_3ls_path_measurement_record(
        work_item_id="M3L-02-TEST-FULL",
        agent_type="claude",
        repo_mutating=True,
        apr_result=apr,
    )
    validate_artifact(record, "agent_3ls_path_measurement_record")
    assert record["loop_complete"] is True
    assert record["first_missing_leg"] is None
    assert record["fell_out_at"] is None
    for leg in LOOP_ORDER:
        assert record["loop_path"][leg]["status"] == "present"
        assert record["loop_path"][leg]["artifact_refs"]
        # APR-supplied artifact ref is surfaced into M3L loop_path leg.
        assert f"outputs/x/{leg.lower()}.json" in record["loop_path"][leg]["artifact_refs"]


# ---------------------------------------------------------------------------
# Case 2 — missing PQX -> first_missing_leg == "PQX"
# ---------------------------------------------------------------------------


def test_missing_pqx_first_missing_leg():
    apr = _apr_with_phase(
        {"PQX": "block"},
        first_failed="pqx_failed",
    )
    record = build_agent_3ls_path_measurement_record(
        work_item_id="M3L-02-TEST-MISSING-PQX",
        agent_type="claude",
        repo_mutating=True,
        apr_result=apr,
    )
    validate_artifact(record, "agent_3ls_path_measurement_record")
    assert record["loop_complete"] is False
    assert record["first_missing_leg"] == "PQX"
    assert record["fell_out_at"] == "PQX"
    assert record["loop_path"]["PQX"]["status"] == "missing"
    assert record["loop_path"]["AEX"]["status"] == "present"
    assert record["loop_path"]["TPA"]["status"] == "present"


# ---------------------------------------------------------------------------
# Case 3 — missing EVL -> fell_out_at == "EVL"
# ---------------------------------------------------------------------------


def test_missing_evl_fell_out_at_evl():
    apr = _apr_with_phase(
        {"EVL": "block"},
        first_failed="evl_failed",
    )
    record = build_agent_3ls_path_measurement_record(
        work_item_id="M3L-02-TEST-MISSING-EVL",
        agent_type="claude",
        repo_mutating=True,
        apr_result=apr,
    )
    validate_artifact(record, "agent_3ls_path_measurement_record")
    assert record["fell_out_at"] == "EVL"
    assert record["first_missing_leg"] == "EVL"
    assert record["loop_complete"] is False
    assert record["loop_path"]["EVL"]["status"] == "missing"


# ---------------------------------------------------------------------------
# Case 4 — present without artifact_refs -> downgraded to partial,
#          schema rejects a forged ``present``-without-refs payload.
# ---------------------------------------------------------------------------


def test_present_without_artifact_refs_is_invalid():
    forged = {
        "artifact_type": "agent_3ls_path_measurement_record",
        "schema_version": "1.0.0",
        "measurement_id": "m3l-bogus",
        "created_at": "2026-05-01T00:00:00Z",
        "work_item_id": "M3L-02-TEST-FORGED",
        "agent_type": "claude",
        "repo_mutating": True,
        "loop_path": {
            leg: {
                "status": "present",
                "artifact_refs": [],
                "reason_codes": [],
            }
            for leg in LOOP_ORDER
        },
        "first_missing_leg": None,
        "first_failed_check": None,
        "fell_out_at": None,
        "loop_complete": True,
        "pr_ready_status": "ready",
        "pr_update_ready_status": "ready",
        "source_artifact_refs": [],
        "reason_codes": [],
        "authority_scope": "observation_only",
    }
    with pytest.raises(Exception):
        validate_artifact(forged, "agent_3ls_path_measurement_record")

    # Builder must downgrade present-without-refs APU evidence to partial
    # rather than reproducing it verbatim.
    apu = {
        "artifact_type": "agent_pr_update_ready_result",
        "schema_version": "1.0.0",
        "guard_id": "gid",
        "work_item_id": "M3L-02-TEST",
        "agent_type": "claude",
        "repo_mutating": True,
        "policy_ref": "policy",
        "readiness_status": "not_ready",
        "clp_status": "pass",
        "reason_codes": ["aex_present_without_artifact_refs"],
        "evidence": {
            "AEX": {
                "status": "present",
                "artifact_refs": [],
                "reason_codes": [],
            },
            "PQX": {"status": "missing", "artifact_refs": [], "reason_codes": ["pqx_missing"]},
            "EVL": {"status": "missing", "artifact_refs": [], "reason_codes": ["evl_missing"]},
            "TPA": {"status": "missing", "artifact_refs": [], "reason_codes": ["tpa_missing"]},
            "CDE": {"status": "missing", "artifact_refs": [], "reason_codes": ["cde_missing"]},
            "SEL": {"status": "missing", "artifact_refs": [], "reason_codes": ["sel_missing"]},
            "LIN": {"status": "missing", "artifact_refs": [], "reason_codes": ["lin_missing"]},
            "REP": {"status": "missing", "artifact_refs": [], "reason_codes": ["rep_missing"]},
            "CLP": {"status": "missing", "artifact_refs": [], "reason_codes": ["clp_missing"]},
            "APU": {"status": "missing", "artifact_refs": [], "reason_codes": ["apu_missing"]},
            "AGL": {"status": "missing", "artifact_refs": [], "reason_codes": ["agl_missing"]},
        },
        "allowed_warning_reason_codes": [],
        "blocked_warning_reason_codes": [],
        "source_artifact_refs": [],
        "evidence_hash": "sha256-test",
        "trace_refs": [],
        "replay_refs": [],
        "authority_scope": "observation_only",
        "human_review_required": False,
        "pr_evidence_section_markdown": "test",
        "generated_at": "2026-05-01T00:00:00Z",
    }
    record = build_agent_3ls_path_measurement_record(
        work_item_id="M3L-02-TEST",
        agent_type="claude",
        repo_mutating=True,
        apu_result=apu,
    )
    assert record["loop_path"]["AEX"]["status"] == "partial"
    validate_artifact(record, "agent_3ls_path_measurement_record")


# ---------------------------------------------------------------------------
# Case 5 — partial without reason_codes -> schema invalid
# ---------------------------------------------------------------------------


def test_partial_without_reason_codes_is_schema_invalid():
    forged = {
        "artifact_type": "agent_3ls_path_measurement_record",
        "schema_version": "1.0.0",
        "measurement_id": "m3l-bogus",
        "created_at": "2026-05-01T00:00:00Z",
        "work_item_id": "M3L-02-TEST-FORGED",
        "agent_type": "claude",
        "repo_mutating": True,
        "loop_path": {
            leg: {
                "status": "partial",
                "artifact_refs": [],
                "reason_codes": [],
            }
            for leg in LOOP_ORDER
        },
        "first_missing_leg": "AEX",
        "first_failed_check": None,
        "fell_out_at": "AEX",
        "loop_complete": False,
        "pr_ready_status": "not_ready",
        "pr_update_ready_status": "not_ready",
        "source_artifact_refs": [],
        "reason_codes": [],
        "authority_scope": "observation_only",
    }
    with pytest.raises(Exception):
        validate_artifact(forged, "agent_3ls_path_measurement_record")


# ---------------------------------------------------------------------------
# Case 6 — repo_mutating unknown -> pr_update_ready_status=not_ready
# ---------------------------------------------------------------------------


def test_repo_mutating_unknown_yields_pr_update_not_ready():
    record = build_agent_3ls_path_measurement_record(
        work_item_id="M3L-02-TEST-UNKNOWN",
        agent_type="claude",
        repo_mutating=None,
    )
    validate_artifact(record, "agent_3ls_path_measurement_record")
    assert record["repo_mutating"] is None
    assert record["pr_update_ready_status"] == "not_ready"


# ---------------------------------------------------------------------------
# Case 7 — mismatched APR/APU states -> correct derivation
# ---------------------------------------------------------------------------


def test_mismatched_apr_apu_states_correct_derivation():
    """APR shows AEX pass; APU shows AEX missing. The merge prefers the
    higher-confidence ``present`` from APR, but reason codes from APU are
    surfaced. (Status priority is present > partial > missing > unknown.)
    """
    apr = _full_apr_pass()
    apu_evidence = {
        "AEX": {"status": "missing", "artifact_refs": [], "reason_codes": ["aex_evidence_missing"]},
        "PQX": {"status": "present", "artifact_refs": ["outputs/y/pqx.json"], "reason_codes": []},
        "EVL": {"status": "missing", "artifact_refs": [], "reason_codes": ["evl_evidence_missing"]},
        "TPA": {"status": "missing", "artifact_refs": [], "reason_codes": ["tpa_evidence_missing"]},
        "CDE": {"status": "missing", "artifact_refs": [], "reason_codes": ["cde_evidence_missing"]},
        "SEL": {"status": "missing", "artifact_refs": [], "reason_codes": ["sel_evidence_missing"]},
        "LIN": {"status": "missing", "artifact_refs": [], "reason_codes": ["lin_missing"]},
        "REP": {"status": "missing", "artifact_refs": [], "reason_codes": ["rep_missing"]},
        "CLP": {"status": "missing", "artifact_refs": [], "reason_codes": ["clp_missing"]},
        "APU": {"status": "missing", "artifact_refs": [], "reason_codes": ["apu_missing"]},
        "AGL": {"status": "missing", "artifact_refs": [], "reason_codes": ["agl_missing"]},
    }
    apu = {
        "artifact_type": "agent_pr_update_ready_result",
        "schema_version": "1.0.0",
        "guard_id": "gid",
        "work_item_id": "M3L-02-TEST",
        "agent_type": "claude",
        "repo_mutating": True,
        "policy_ref": "policy",
        "readiness_status": "not_ready",
        "clp_status": "pass",
        "reason_codes": [],
        "evidence": apu_evidence,
        "allowed_warning_reason_codes": [],
        "blocked_warning_reason_codes": [],
        "source_artifact_refs": [],
        "evidence_hash": "sha256-test",
        "trace_refs": [],
        "replay_refs": [],
        "authority_scope": "observation_only",
        "human_review_required": False,
        "pr_evidence_section_markdown": "test",
        "generated_at": "2026-05-01T00:00:00Z",
    }
    record = build_agent_3ls_path_measurement_record(
        work_item_id="M3L-02-TEST",
        agent_type="claude",
        repo_mutating=True,
        apr_result=apr,
        apu_result=apu,
    )
    validate_artifact(record, "agent_3ls_path_measurement_record")
    # APR shows AEX present, so the merge keeps present.
    assert record["loop_path"]["AEX"]["status"] == "present"
    # PR statuses are pulled from APR, which is the primary source.
    assert record["pr_ready_status"] == "ready"
    assert record["pr_update_ready_status"] == "ready"


# ---------------------------------------------------------------------------
# Case 8 — no inference from PR prose: a free-form string in source_artifact_refs
#          cannot rescue a missing leg.
# ---------------------------------------------------------------------------


def test_no_inference_from_pr_prose():
    """A leg with no real artifact reference must not be promoted to
    ``present`` even when the surrounding artifact carries free-form
    references like a commit message or PR body string.
    """
    apr = _apr_with_phase(
        {"SEL": "block"},
        first_failed="sel_failed",
    )
    # Inject some PR-body-style trace_refs that look like sentences.
    apr["trace_refs"] = ["see PR description for SEL evidence"]
    record = build_agent_3ls_path_measurement_record(
        work_item_id="M3L-02-TEST-PROSE",
        agent_type="claude",
        repo_mutating=True,
        apr_result=apr,
    )
    validate_artifact(record, "agent_3ls_path_measurement_record")
    assert record["loop_path"]["SEL"]["status"] == "missing"
    assert record["loop_complete"] is False


# ---------------------------------------------------------------------------
# Case 9 — first_failed_check passthrough from APR, fallback to CLP
# ---------------------------------------------------------------------------


def test_first_failed_check_falls_back_to_clp_when_apr_missing():
    clp = {
        "artifact_type": "core_loop_pre_pr_gate_result",
        "schema_version": "1.0.0",
        "gate_id": "gate-test",
        "work_item_id": "M3L-02-TEST",
        "agent_type": "claude",
        "repo_mutating": True,
        "base_ref": "origin/main",
        "head_ref": "HEAD",
        "changed_files": [],
        "gate_status": "warn",
        "checks": [
            {
                "check_name": "authority_shape_preflight",
                "owner_system": "AEX",
                "command": "(test)",
                "status": "warn",
                "output_ref": "outputs/x/aex.json",
                "failure_class": None,
                "reason_codes": ["soft_finding"],
                "next_action": "investigate",
                "required": True,
            }
        ],
        "first_failed_check": "authority_shape_preflight",
        "failure_classes": [],
        "source_artifacts_used": [],
        "emitted_artifacts": [],
        "required_follow_up": [],
        "trace_refs": [],
        "replay_refs": [],
        "authority_scope": "observation_only",
        "human_review_required": False,
        "generated_at": "2026-05-01T00:00:00Z",
    }
    record = build_agent_3ls_path_measurement_record(
        work_item_id="M3L-02-TEST",
        agent_type="claude",
        repo_mutating=True,
        clp_result=clp,
    )
    validate_artifact(record, "agent_3ls_path_measurement_record")
    assert record["first_failed_check"] == "authority_shape_preflight"


# ---------------------------------------------------------------------------
# Case 10 — authority-safe vocabulary lint on M3L-owned files.
# ---------------------------------------------------------------------------


def test_no_banned_authority_tokens_in_m3l_owned_files():
    banned_substrings = [
        "approve",
        "approved",
        "approval",
        "certify",
        "certification",
        "certifies",
        "promote",
        "promotion",
        "enforce",
        "enforced",
        "enforcement",
        "decide",
        "decision-of-record",
        "adjudication",
        "authorize",
        "authorization",
    ]
    failures: list[str] = []
    for f in M3L_OWNED_FILES:
        if not f.is_file():
            continue
        if f.name == "test_agent_3ls_path_measurement.py":
            continue
        for line_no, line in enumerate(
            f.read_text(encoding="utf-8").splitlines(), start=1
        ):
            lower = line.lower()
            for tok in banned_substrings:
                if tok in lower:
                    failures.append(
                        f"{f.relative_to(ROOT)}:{line_no}: banned token {tok!r}"
                    )
    assert not failures, "Authority-safe vocabulary violations:\n" + "\n".join(failures)
