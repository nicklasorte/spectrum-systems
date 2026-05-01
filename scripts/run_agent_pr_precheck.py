#!/usr/bin/env python3
"""APR-01 — Agent PR Precheck Runner.

APR composes the existing per-gate scripts that CI's
``governed-contract-preflight`` job runs and emits a single
``agent_pr_precheck_result`` aggregate. Use it before opening or updating
a PR to catch the same readiness issues CI surfaces.

APR is observation-only. It surfaces pre-PR readiness inputs and
compliance observations only. Canonical authority remains with AEX
(admission), PQX (bounded execution closure), EVL (eval evidence), TPA
(policy/scope), CDE (continuation/closure), SEL (final gate signal),
LIN (lineage), REP (replay), and GOV per
``docs/architecture/system_registry.md``. APR emits no admission,
execution, eval, policy, control, or final-gate signal of its own.

Phases (3LS grouping; AEX runs first because it's the cheapest and
catches MISSING_REQUIRED_SURFACE_MAPPING in <2 seconds):

  AEX  — required-surface test mapping for changed paths (in-process)
  TPA  — authority-shape preflight, authority-leak guard,
         system registry guard, contract-compliance gate
  PQX  — build_preflight_pqx_wrapper + run_contract_preflight
         (with --execution-context pqx_governed)
  EVL  — generated-artifact freshness (TLS + ecosystem regen, run twice)
         and selected pytest targets
  CDE  — run_core_loop_pre_pr_gate (CLP-01) + check_agent_pr_ready (CLP-02)
  SEL  — check_agent_pr_update_ready (APU)

Exit codes
----------
0 — overall_status=pass
1 — overall_status=warn (all warn reason_codes policy-allowed)
2 — overall_status=block (or either pr_ready/pr_update_ready=not_ready)
3 — overall_status=human_review_required
4 — internal runner error (subprocess crash, missing dependency,
    unreachable git refs, etc.)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.contracts import validate_artifact  # noqa: E402
from spectrum_systems.modules.runtime.pr_test_selection import (  # noqa: E402
    classify_changed_path,
    load_override_map,
    resolve_required_tests,
)

DEFAULT_OUTPUT_REL_PATH = "outputs/agent_pr_precheck/agent_pr_precheck_result.json"
DEFAULT_PHASE_OUTPUT_DIR = "outputs/agent_pr_precheck"

PHASES: tuple[str, ...] = ("AEX", "TPA", "PQX", "EVL", "CDE", "SEL")

# Status sets used to derive phase + overall rollups.
_BLOCKING_STATUSES = {"block", "missing", "unknown"}
_WARNING_STATUSES = {"warn"}
_PASS_STATUSES = {"pass"}


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def utc_now_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def stable_precheck_id(*, work_item_id: str, generated_at: str) -> str:
    raw = f"{work_item_id}|{generated_at}".encode("utf-8")
    return "apr-precheck-" + hashlib.sha256(raw).hexdigest()[:16]


def _run_subprocess(cmd: list[str], cwd: Path) -> tuple[int, str]:
    """Run ``cmd`` and return ``(exit_code, combined_output)``."""
    try:
        proc = subprocess.run(
            cmd,
            cwd=cwd,
            check=False,
            capture_output=True,
            text=True,
            env=os.environ.copy(),
        )
    except (FileNotFoundError, OSError) as exc:
        return -1, f"subprocess launch failed: {exc}"
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def _git_diff_name_only(base_ref: str, head_ref: str) -> tuple[list[str] | None, str | None]:
    rc, out = _run_subprocess(
        ["git", "diff", "--name-only", f"{base_ref}..{head_ref}"], cwd=REPO_ROOT
    )
    if rc != 0:
        return None, out.strip() or "git diff failed"
    return sorted({line.strip() for line in out.splitlines() if line.strip()}), None


# ---------------------------------------------------------------------------
# Check / phase model
# ---------------------------------------------------------------------------


@dataclass
class CheckResult:
    check_name: str
    phase: str
    command: str
    status: str
    exit_code: int | None = None
    output_artifact_refs: list[str] = field(default_factory=list)
    reason_codes: list[str] = field(default_factory=list)
    next_action: str | None = None

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "check_name": self.check_name,
            "phase": self.phase,
            "command": self.command,
            "status": self.status,
            "exit_code": self.exit_code,
            "output_artifact_refs": list(self.output_artifact_refs),
            "reason_codes": list(self.reason_codes),
        }
        if self.next_action is not None:
            out["next_action"] = self.next_action
        return out


def _summarize_phase(phase: str, checks: list[CheckResult]) -> dict[str, Any]:
    phase_checks = [c for c in checks if c.phase == phase]
    fail_count = sum(
        1 for c in phase_checks if c.status in _BLOCKING_STATUSES or c.status == "warn"
    )
    if any(c.status in _BLOCKING_STATUSES for c in phase_checks):
        status = "block"
    elif any(c.status == "warn" for c in phase_checks):
        status = "warn"
    elif phase_checks and all(c.status == "skipped" for c in phase_checks):
        status = "skipped"
    elif phase_checks and any(c.status == "pass" for c in phase_checks):
        status = "pass"
    else:
        status = "skipped"
    reason_codes: list[str] = []
    for c in phase_checks:
        for code in c.reason_codes:
            if code and code not in reason_codes:
                reason_codes.append(code)
    return {
        "status": status,
        "check_count": len(phase_checks),
        "fail_count": sum(1 for c in phase_checks if c.status in _BLOCKING_STATUSES),
        "owner_system": phase,
        "reason_codes": reason_codes,
    }


# ---------------------------------------------------------------------------
# AEX phase (in-process)
# ---------------------------------------------------------------------------


def _ref_relative_to(path: Path, repo_root: Path) -> str:
    try:
        return str(path.relative_to(repo_root))
    except ValueError:
        return str(path)


def aex_required_surface_check(
    *,
    repo_root: Path,
    changed_paths: list[str],
    output_dir: Path,
) -> CheckResult:
    """Detect required-surface mapping gaps using ``pr_test_selection``.

    Mirrors ``run_contract_preflight`` semantics: a governed surface is
    treated as missing its required-surface mapping when its resolved
    test target list is empty AND it is not itself a contract surface
    (``contracts/schemas/`` or ``contracts/examples/``).
    """
    contract_surfaces = {
        p
        for p in changed_paths
        if p.startswith("contracts/schemas/") or p.startswith("contracts/examples/")
    }
    governed_paths = [
        p for p in changed_paths if classify_changed_path(p).get("is_governed")
    ]
    targets_by_path = resolve_required_tests(repo_root, governed_paths)
    overrides = load_override_map(repo_root)
    unmapped = []
    for path, targets in targets_by_path.items():
        if path in contract_surfaces:
            continue
        if path in overrides:
            # explicit override entry — counts as mapped even if needle-match
            # would also produce some targets.
            continue
        if not targets:
            unmapped.append(path)

    output_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = output_dir / "aex_required_surface_mapping.json"
    payload = {
        "artifact_type": "apr_aex_phase_observation",
        "phase": "AEX",
        "changed_paths": list(changed_paths),
        "governed_paths": list(governed_paths),
        "contract_surface_paths": sorted(contract_surfaces),
        "targets_by_path": targets_by_path,
        "unmapped_governed_paths": list(unmapped),
        "authority_scope": "observation_only",
    }
    artifact_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    if unmapped:
        suggested = {p: ["tests/<add an explicit binding here>"] for p in unmapped}
        return CheckResult(
            check_name="aex_required_surface_mapping",
            phase="AEX",
            command="in-process: pr_test_selection.resolve_required_tests",
            status="block",
            exit_code=2,
            output_artifact_refs=[_ref_relative_to(artifact_path, repo_root)],
            reason_codes=[
                "MISSING_REQUIRED_SURFACE_MAPPING",
                *[f"unmapped:{p}" for p in unmapped],
            ],
            next_action=(
                "Add entries to docs/governance/preflight_required_surface_test_overrides.json: "
                + json.dumps(suggested, sort_keys=True)
            ),
        )
    return CheckResult(
        check_name="aex_required_surface_mapping",
        phase="AEX",
        command="in-process: pr_test_selection.resolve_required_tests",
        status="pass",
        exit_code=0,
        output_artifact_refs=[_ref_relative_to(artifact_path, repo_root)],
        next_action="none",
    )


# ---------------------------------------------------------------------------
# Subprocess phase wrappers (TPA / PQX / EVL / CDE / SEL)
# ---------------------------------------------------------------------------


def _wrap_subprocess_check(
    *,
    check_name: str,
    phase: str,
    cmd: list[str],
    expected_output: Path | None,
    failure_reason_code: str,
) -> CheckResult:
    rc, combined = _run_subprocess(cmd, cwd=REPO_ROOT)
    cmd_str = " ".join(shlex.quote(p) for p in cmd)
    output_refs: list[str] = []
    if expected_output is not None and expected_output.is_file():
        try:
            output_refs.append(str(expected_output.relative_to(REPO_ROOT)))
        except ValueError:
            output_refs.append(str(expected_output))
    if rc == 0:
        return CheckResult(
            check_name=check_name,
            phase=phase,
            command=cmd_str,
            status="pass",
            exit_code=rc,
            output_artifact_refs=output_refs,
            next_action="none",
        )
    reason_codes = [failure_reason_code]
    if rc < 0:
        reason_codes.append("subprocess_launch_failed")
    return CheckResult(
        check_name=check_name,
        phase=phase,
        command=cmd_str,
        status="block",
        exit_code=rc,
        output_artifact_refs=output_refs,
        reason_codes=reason_codes,
        next_action=f"investigate: {(combined.splitlines() or ['(no output)'])[-1][:200]}",
    )


def tpa_authority_shape(*, base_ref: str, head_ref: str, output_dir: Path) -> CheckResult:
    out = REPO_ROOT / "outputs" / "authority_shape_preflight" / "authority_shape_preflight_result.json"
    return _wrap_subprocess_check(
        check_name="tpa_authority_shape_preflight",
        phase="TPA",
        cmd=[
            sys.executable,
            "scripts/run_authority_shape_preflight.py",
            "--base-ref", base_ref,
            "--head-ref", head_ref,
            "--suggest-only",
            "--output", str(out.relative_to(REPO_ROOT)),
        ],
        expected_output=out,
        failure_reason_code="authority_shape_preflight_finding",
    )


def tpa_authority_leak(*, base_ref: str, head_ref: str, output_dir: Path) -> CheckResult:
    out = REPO_ROOT / "outputs" / "authority_leak_guard" / "authority_leak_guard_result.json"
    return _wrap_subprocess_check(
        check_name="tpa_authority_leak_guard",
        phase="TPA",
        cmd=[
            sys.executable,
            "scripts/run_authority_leak_guard.py",
            "--base-ref", base_ref,
            "--head-ref", head_ref,
            "--output", str(out.relative_to(REPO_ROOT)),
        ],
        expected_output=out,
        failure_reason_code="authority_leak_guard_finding",
    )


def tpa_system_registry(*, base_ref: str, head_ref: str, output_dir: Path) -> CheckResult:
    out = REPO_ROOT / "outputs" / "system_registry_guard" / "system_registry_guard_result.json"
    return _wrap_subprocess_check(
        check_name="tpa_system_registry_guard",
        phase="TPA",
        cmd=[
            sys.executable,
            "scripts/run_system_registry_guard.py",
            "--base-ref", base_ref,
            "--head-ref", head_ref,
            "--output", str(out.relative_to(REPO_ROOT)),
        ],
        expected_output=out,
        failure_reason_code="system_registry_guard_finding",
    )


def tpa_contract_compliance(*, output_dir: Path) -> CheckResult:
    out = REPO_ROOT / "governance" / "reports" / "contract-dependency-graph.json"
    return _wrap_subprocess_check(
        check_name="tpa_contract_compliance_observation",
        phase="TPA",
        cmd=[sys.executable, "scripts/run_contract_enforcement.py"],
        expected_output=out,
        failure_reason_code="contract_compliance_finding",
    )


def pqx_build_wrapper(*, base_ref: str, head_ref: str, output_dir: Path) -> CheckResult:
    out = REPO_ROOT / "outputs" / "contract_preflight" / "preflight_pqx_task_wrapper.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    return _wrap_subprocess_check(
        check_name="pqx_preflight_pqx_wrapper",
        phase="PQX",
        cmd=[
            sys.executable,
            "scripts/build_preflight_pqx_wrapper.py",
            "--base-ref", base_ref,
            "--head-ref", head_ref,
            "--output", str(out.relative_to(REPO_ROOT)),
        ],
        expected_output=out,
        failure_reason_code="preflight_wrapper_build_failed",
    )


def pqx_contract_preflight(*, base_ref: str, head_ref: str, output_dir: Path) -> CheckResult:
    wrapper = REPO_ROOT / "outputs" / "contract_preflight" / "preflight_pqx_task_wrapper.json"
    out_dir = REPO_ROOT / "outputs" / "contract_preflight"
    return _wrap_subprocess_check(
        check_name="pqx_governed_contract_preflight",
        phase="PQX",
        cmd=[
            sys.executable,
            "scripts/run_contract_preflight.py",
            "--base-ref", base_ref,
            "--head-ref", head_ref,
            "--output-dir", str(out_dir.relative_to(REPO_ROOT)),
            "--execution-context", "pqx_governed",
            "--pqx-wrapper-path", str(wrapper.relative_to(REPO_ROOT)),
            "--authority-evidence-ref",
            "artifacts/pqx_runs/preflight.pqx_slice_execution_record.json",
        ],
        expected_output=out_dir / "contract_preflight_report.json",
        failure_reason_code="contract_mismatch",
    )


def evl_generated_artifact_freshness(*, output_dir: Path) -> CheckResult:
    """Run TLS + ecosystem regenerators twice; both runs must be byte-stable."""
    output_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = output_dir / "evl_generated_artifact_freshness.json"
    targets = [
        REPO_ROOT / "artifacts" / "tls" / "system_dependency_priority_report.json",
        REPO_ROOT / "artifacts" / "tls" / "system_evidence_attachment.json",
        REPO_ROOT / "artifacts" / "system_dependency_priority_report.json",
        REPO_ROOT / "governance" / "reports" / "ecosystem-health.json",
    ]
    volatile_keys = {"generated_at", "created_at", "last_updated", "run_at", "timestamp"}

    def _normalize(obj: Any) -> Any:
        if isinstance(obj, dict):
            return {k: _normalize(v) for k, v in sorted(obj.items()) if k not in volatile_keys}
        if isinstance(obj, list):
            return [_normalize(x) for x in obj]
        return obj

    def _capture_norm(path: Path) -> str | None:
        if not path.is_file():
            return None
        try:
            return json.dumps(_normalize(json.loads(path.read_text(encoding="utf-8"))), sort_keys=True)
        except Exception:
            return None

    def _regenerate() -> int:
        rc1, _ = _run_subprocess(
            [
                sys.executable,
                "scripts/build_tls_dependency_priority.py",
                "--out", "artifacts/tls",
                "--top-level-out", "artifacts",
                "--candidates", "",
            ],
            cwd=REPO_ROOT,
        )
        rc2, _ = _run_subprocess(
            [sys.executable, "scripts/generate_ecosystem_health_report.py"], cwd=REPO_ROOT
        )
        return rc1 or rc2

    rc_first = _regenerate()
    snapshot1 = {str(p.relative_to(REPO_ROOT)): _capture_norm(p) for p in targets}
    rc_second = _regenerate()
    snapshot2 = {str(p.relative_to(REPO_ROOT)): _capture_norm(p) for p in targets}

    drift = sorted(k for k in snapshot1 if snapshot1[k] != snapshot2[k])
    payload = {
        "artifact_type": "apr_evl_phase_observation",
        "phase": "EVL",
        "regen_returncode_first": rc_first,
        "regen_returncode_second": rc_second,
        "twice_stable": not drift,
        "drift_paths": drift,
        "authority_scope": "observation_only",
    }
    artifact_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    if rc_first != 0 or rc_second != 0:
        return CheckResult(
            check_name="evl_generated_artifact_freshness",
            phase="EVL",
            command=(
                "python scripts/build_tls_dependency_priority.py --out artifacts/tls "
                "--top-level-out artifacts --candidates '' && "
                "python scripts/generate_ecosystem_health_report.py (run twice)"
            ),
            status="block",
            exit_code=rc_first or rc_second,
            output_artifact_refs=[str(artifact_path.relative_to(REPO_ROOT))],
            reason_codes=["tls_generator_returned_nonzero"],
            next_action="rerun_generators_and_inspect_logs",
        )
    if drift:
        return CheckResult(
            check_name="evl_generated_artifact_freshness",
            phase="EVL",
            command="(see EVL phase artifact)",
            status="block",
            exit_code=2,
            output_artifact_refs=[str(artifact_path.relative_to(REPO_ROOT))],
            reason_codes=["tls_generated_artifact_drift"],
            next_action="commit_regenerated_artifacts_and_rerun",
        )
    return CheckResult(
        check_name="evl_generated_artifact_freshness",
        phase="EVL",
        command="(twice-stable regen verified)",
        status="pass",
        exit_code=0,
        output_artifact_refs=[str(artifact_path.relative_to(REPO_ROOT))],
        next_action="none",
    )


def evl_selected_tests(
    *, repo_root: Path, changed_paths: list[str], output_dir: Path
) -> CheckResult:
    """Run pytest on the test set ``pr_test_selection`` resolves for the diff."""
    output_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = output_dir / "evl_selected_tests.json"
    governed = [p for p in changed_paths if classify_changed_path(p).get("is_governed")]
    targets_by_path = resolve_required_tests(repo_root, governed)
    targets = sorted(
        {
            t
            for ts in targets_by_path.values()
            for t in ts
            if (repo_root / t).is_file()
        }
    )
    payload = {
        "artifact_type": "apr_evl_selected_tests_observation",
        "phase": "EVL",
        "selected_targets": targets,
        "authority_scope": "observation_only",
    }
    if not targets:
        payload["pytest_returncode"] = None
        payload["reason"] = "no_selected_tests_resolved"
        artifact_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        return CheckResult(
            check_name="evl_selected_tests",
            phase="EVL",
            command="(no targeted tests resolved)",
            status="skipped",
            exit_code=None,
            output_artifact_refs=[str(artifact_path.relative_to(repo_root))],
            reason_codes=["no_selected_tests_resolved"],
            next_action="none",
        )
    cmd = [sys.executable, "-m", "pytest", "-q", *targets]
    rc, combined = _run_subprocess(cmd, cwd=repo_root)
    payload["pytest_returncode"] = rc
    payload["pytest_tail"] = "\n".join(combined.splitlines()[-25:])
    artifact_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    if rc == 0:
        return CheckResult(
            check_name="evl_selected_tests",
            phase="EVL",
            command=" ".join(shlex.quote(p) for p in cmd),
            status="pass",
            exit_code=0,
            output_artifact_refs=[str(artifact_path.relative_to(repo_root))],
            next_action="none",
        )
    return CheckResult(
        check_name="evl_selected_tests",
        phase="EVL",
        command=" ".join(shlex.quote(p) for p in cmd),
        status="block",
        exit_code=rc,
        output_artifact_refs=[str(artifact_path.relative_to(repo_root))],
        reason_codes=[f"pytest_returncode_{rc}"],
        next_action="repair_failing_tests",
    )


def cde_core_loop_pre_pr_gate(
    *, work_item_id: str, agent_type: str, base_ref: str, head_ref: str, output_dir: Path
) -> CheckResult:
    out = REPO_ROOT / "outputs" / "core_loop_pre_pr_gate" / "core_loop_pre_pr_gate_result.json"
    return _wrap_subprocess_check(
        check_name="cde_core_loop_pre_pr_gate",
        phase="CDE",
        cmd=[
            sys.executable,
            "scripts/run_core_loop_pre_pr_gate.py",
            "--work-item-id", work_item_id,
            "--agent-type", agent_type if agent_type in {"codex", "claude", "other", "unknown"} else "unknown",
            "--base-ref", base_ref,
            "--head-ref", head_ref,
        ],
        expected_output=out,
        failure_reason_code="clp_pre_pr_gate_block",
    )


def cde_check_agent_pr_ready(
    *, work_item_id: str, agent_type: str, output_dir: Path
) -> CheckResult:
    out = REPO_ROOT / "outputs" / "core_loop_pre_pr_gate" / "agent_pr_ready_result.json"
    return _wrap_subprocess_check(
        check_name="cde_check_agent_pr_ready",
        phase="CDE",
        cmd=[
            sys.executable,
            "scripts/check_agent_pr_ready.py",
            "--work-item-id", work_item_id,
            "--agent-type", agent_type if agent_type in {"codex", "claude", "other", "unknown"} else "unknown",
        ],
        expected_output=out,
        failure_reason_code="clp_pr_ready_not_ready",
    )


def sel_check_agent_pr_update_ready(
    *, work_item_id: str, agent_type: str, output_dir: Path
) -> CheckResult:
    out = REPO_ROOT / "outputs" / "agent_pr_update" / "agent_pr_update_ready_result.json"
    return _wrap_subprocess_check(
        check_name="sel_check_agent_pr_update_ready",
        phase="SEL",
        cmd=[
            sys.executable,
            "scripts/check_agent_pr_update_ready.py",
            "--work-item-id", work_item_id,
            "--agent-type", agent_type if agent_type in {"codex", "claude", "other", "unknown"} else "unknown",
        ],
        expected_output=out,
        failure_reason_code="apu_pr_update_not_ready",
    )


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------


def _aggregate_overall_status(
    *,
    repo_mutating: bool | None,
    checks: list[CheckResult],
) -> tuple[str, str, str, list[str]]:
    """Return (overall_status, pr_ready_status, pr_update_ready_status, reason_codes)."""
    reason_codes: list[str] = []

    # repo_mutating unknown -> block
    if repo_mutating is None:
        reason_codes.append("repo_mutating_unknown")
        return "block", "not_ready", "not_ready", reason_codes

    blocking = [c for c in checks if c.status in _BLOCKING_STATUSES]
    warning = [c for c in checks if c.status in _WARNING_STATUSES]

    cde_blocking = any(c.phase == "CDE" and c.status in _BLOCKING_STATUSES for c in checks)
    sel_blocking = any(c.phase == "SEL" and c.status in _BLOCKING_STATUSES for c in checks)

    pr_ready = "ready"
    pr_update_ready = "ready"
    if cde_blocking or blocking:
        pr_ready = "not_ready"
    if sel_blocking or blocking:
        pr_update_ready = "not_ready"

    for c in blocking:
        for rc in c.reason_codes:
            if rc not in reason_codes:
                reason_codes.append(rc)

    if blocking:
        overall = "block"
    elif warning:
        overall = "warn"
        for c in warning:
            for rc in c.reason_codes:
                if rc not in reason_codes:
                    reason_codes.append(rc)
    else:
        overall = "pass"

    return overall, pr_ready, pr_update_ready, reason_codes


def build_agent_pr_precheck_result(
    *,
    work_item_id: str,
    agent_type: str,
    repo_mutating: bool | None,
    base_ref: str,
    head_ref: str,
    checks: list[CheckResult],
    overall_status: str,
    pr_ready_status: str,
    pr_update_ready_status: str,
    reason_codes: list[str],
    warnings: list[str] | None = None,
    clp_artifact_ref: str | None = None,
    apu_artifact_ref: str | None = None,
    contract_preflight_artifact_refs: list[str] | None = None,
    generated_artifact_freshness_refs: list[str] | None = None,
    authority_artifact_refs: list[str] | None = None,
    selected_test_refs: list[str] | None = None,
    trace_refs: list[str] | None = None,
    replay_refs: list[str] | None = None,
    policy_ref: str | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    if agent_type not in {"codex", "claude", "unknown_ai_agent"}:
        agent_type = "unknown_ai_agent"
    ts = generated_at or utc_now_iso()
    pid = stable_precheck_id(work_item_id=work_item_id, generated_at=ts)
    first_failed = next(
        (c.check_name for c in checks if c.status in _BLOCKING_STATUSES), None
    )
    first_missing = next(
        (
            ref
            for c in checks
            if c.status == "missing"
            for ref in (c.reason_codes or [])
        ),
        None,
    )
    return {
        "artifact_type": "agent_pr_precheck_result",
        "schema_version": "1.0.0",
        "precheck_id": pid,
        "created_at": ts,
        "work_item_id": work_item_id,
        "agent_type": agent_type,
        "repo_mutating": repo_mutating,
        "base_ref": base_ref,
        "head_ref": head_ref,
        "overall_status": overall_status,
        "pr_ready_status": pr_ready_status,
        "pr_update_ready_status": pr_update_ready_status,
        "checks": [c.to_dict() for c in checks],
        "phase_summaries": {phase: _summarize_phase(phase, checks) for phase in PHASES},
        "clp_artifact_ref": clp_artifact_ref,
        "apu_artifact_ref": apu_artifact_ref,
        "contract_preflight_artifact_refs": list(contract_preflight_artifact_refs or []),
        "generated_artifact_freshness_refs": list(generated_artifact_freshness_refs or []),
        "authority_artifact_refs": list(authority_artifact_refs or []),
        "selected_test_refs": list(selected_test_refs or []),
        "first_failed_check": first_failed,
        "first_missing_artifact": first_missing,
        "reason_codes": list(reason_codes),
        "warnings": list(warnings or []),
        "trace_refs": list(trace_refs or []),
        "replay_refs": list(replay_refs or []),
        "policy_ref": policy_ref,
        "authority_scope": "observation_only",
    }


def overall_status_to_exit_code(overall_status: str) -> int:
    return {
        "pass": 0,
        "warn": 1,
        "block": 2,
        "human_review_required": 3,
    }.get(overall_status, 4)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="APR-01 Agent PR Precheck Runner")
    parser.add_argument("--base-ref", default="origin/main")
    parser.add_argument("--head-ref", default="HEAD")
    parser.add_argument("--work-item-id", default="APR-01-LOCAL")
    parser.add_argument(
        "--agent-type",
        default="unknown_ai_agent",
        choices=["codex", "claude", "unknown_ai_agent"],
    )
    parser.add_argument(
        "--repo-mutating",
        default="auto",
        choices=["auto", "true", "false", "unknown"],
        help=(
            "auto = derive from changed paths (any governed surface = true). "
            "unknown = force null (will block per APR policy)."
        ),
    )
    parser.add_argument("--output", default=DEFAULT_OUTPUT_REL_PATH)
    parser.add_argument(
        "--phase-output-dir", default=DEFAULT_PHASE_OUTPUT_DIR
    )
    parser.add_argument(
        "--skip-phase",
        action="append",
        default=[],
        choices=list(PHASES),
        help="Skip a phase (DEBUG ONLY: skipped phases will be reported as skipped).",
    )
    return parser.parse_args()


def _resolve_repo_mutating(directive: str, changed_paths: list[str]) -> bool | None:
    if directive == "true":
        return True
    if directive == "false":
        return False
    if directive == "unknown":
        return None
    if not changed_paths:
        return False
    for path in changed_paths:
        info = classify_changed_path(path)
        if info.get("is_governed"):
            return True
    return False


def main() -> int:
    args = _parse_args()
    output_path = (REPO_ROOT / args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    phase_output_dir = (REPO_ROOT / args.phase_output_dir).resolve()
    phase_output_dir.mkdir(parents=True, exist_ok=True)

    changed_paths, diff_err = _git_diff_name_only(args.base_ref, args.head_ref)
    if changed_paths is None:
        artifact = build_agent_pr_precheck_result(
            work_item_id=args.work_item_id,
            agent_type=args.agent_type,
            repo_mutating=None,
            base_ref=args.base_ref,
            head_ref=args.head_ref,
            checks=[],
            overall_status="block",
            pr_ready_status="not_ready",
            pr_update_ready_status="not_ready",
            reason_codes=[
                "git_diff_unavailable",
                f"git_diff_error:{diff_err or 'unknown'}",
            ],
        )
        validate_artifact(artifact, "agent_pr_precheck_result")
        output_path.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"overall_status": "block", "reason": "git_diff_unavailable"}, indent=2))
        return 4

    repo_mutating = _resolve_repo_mutating(args.repo_mutating, changed_paths)
    skipped = set(args.skip_phase or [])

    checks: list[CheckResult] = []

    # AEX phase
    if "AEX" not in skipped:
        checks.append(
            aex_required_surface_check(
                repo_root=REPO_ROOT,
                changed_paths=changed_paths,
                output_dir=phase_output_dir,
            )
        )

    # Short-circuit: AEX block stops further work (cheap-fast-fail).
    aex_block = any(c.phase == "AEX" and c.status in _BLOCKING_STATUSES for c in checks)
    if not aex_block:
        if "TPA" not in skipped:
            checks.append(tpa_authority_shape(base_ref=args.base_ref, head_ref=args.head_ref, output_dir=phase_output_dir))
            checks.append(tpa_authority_leak(base_ref=args.base_ref, head_ref=args.head_ref, output_dir=phase_output_dir))
            checks.append(tpa_system_registry(base_ref=args.base_ref, head_ref=args.head_ref, output_dir=phase_output_dir))
            checks.append(tpa_contract_compliance(output_dir=phase_output_dir))
        if "PQX" not in skipped:
            wrapper_check = pqx_build_wrapper(base_ref=args.base_ref, head_ref=args.head_ref, output_dir=phase_output_dir)
            checks.append(wrapper_check)
            if wrapper_check.status == "pass":
                checks.append(pqx_contract_preflight(base_ref=args.base_ref, head_ref=args.head_ref, output_dir=phase_output_dir))
        if "EVL" not in skipped:
            checks.append(evl_generated_artifact_freshness(output_dir=phase_output_dir))
            checks.append(
                evl_selected_tests(
                    repo_root=REPO_ROOT,
                    changed_paths=changed_paths,
                    output_dir=phase_output_dir,
                )
            )
        if "CDE" not in skipped:
            checks.append(
                cde_core_loop_pre_pr_gate(
                    work_item_id=args.work_item_id,
                    agent_type=args.agent_type,
                    base_ref=args.base_ref,
                    head_ref=args.head_ref,
                    output_dir=phase_output_dir,
                )
            )
            checks.append(
                cde_check_agent_pr_ready(
                    work_item_id=args.work_item_id,
                    agent_type=args.agent_type,
                    output_dir=phase_output_dir,
                )
            )
        if "SEL" not in skipped:
            checks.append(
                sel_check_agent_pr_update_ready(
                    work_item_id=args.work_item_id,
                    agent_type=args.agent_type,
                    output_dir=phase_output_dir,
                )
            )

    overall, pr_ready, pr_update_ready, reasons = _aggregate_overall_status(
        repo_mutating=repo_mutating, checks=checks
    )

    # Collect cross-cutting artifact refs from per-phase outputs.
    contract_preflight_refs = [
        ref
        for c in checks
        if c.phase == "PQX" and c.status == "pass"
        for ref in c.output_artifact_refs
    ]
    freshness_refs = [
        ref
        for c in checks
        if c.check_name == "evl_generated_artifact_freshness"
        for ref in c.output_artifact_refs
    ]
    authority_refs = [
        ref
        for c in checks
        if c.phase == "TPA"
        for ref in c.output_artifact_refs
    ]
    selected_test_refs = []
    for c in checks:
        if c.check_name != "evl_selected_tests":
            continue
        for ref in c.output_artifact_refs:
            selected_test_refs.append(ref)
    clp_ref = next(
        (
            ref
            for c in checks
            if c.check_name == "cde_core_loop_pre_pr_gate"
            for ref in c.output_artifact_refs
        ),
        None,
    )
    apu_ref = next(
        (
            ref
            for c in checks
            if c.check_name == "sel_check_agent_pr_update_ready"
            for ref in c.output_artifact_refs
        ),
        None,
    )

    artifact = build_agent_pr_precheck_result(
        work_item_id=args.work_item_id,
        agent_type=args.agent_type,
        repo_mutating=repo_mutating,
        base_ref=args.base_ref,
        head_ref=args.head_ref,
        checks=checks,
        overall_status=overall,
        pr_ready_status=pr_ready,
        pr_update_ready_status=pr_update_ready,
        reason_codes=reasons,
        clp_artifact_ref=clp_ref,
        apu_artifact_ref=apu_ref,
        contract_preflight_artifact_refs=contract_preflight_refs,
        generated_artifact_freshness_refs=freshness_refs,
        authority_artifact_refs=authority_refs,
        selected_test_refs=selected_test_refs,
    )
    validate_artifact(artifact, "agent_pr_precheck_result")
    output_path.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")

    summary = {
        "overall_status": overall,
        "pr_ready_status": pr_ready,
        "pr_update_ready_status": pr_update_ready,
        "first_failed_check": artifact["first_failed_check"],
        "reason_codes": reasons,
        "output": str(output_path.relative_to(REPO_ROOT)),
    }
    print(json.dumps(summary, indent=2))
    return overall_status_to_exit_code(overall)


if __name__ == "__main__":
    raise SystemExit(main())
