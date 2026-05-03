#!/usr/bin/env python3
"""Core Loop Pre-PR Gate runner (CLP-01).

Runs the canonical pre-admission check bundle (authority shape, authority
leak, contract enforcement, TLS generated artifact freshness, contract
preflight, selected tests) before a repo-mutating agent slice can be handed
off as PR-ready. Emits a ``core_loop_pre_pr_gate_result`` artifact.

This runner performs observation-only pre-PR readiness aggregation. It
reports the canonical preflight outputs and does not authorize, admit,
promote, enforce, or decide policy. Policy and admissibility decisions
remain with TPA. Continuation and closure decisions remain with CDE.
Enforcement decisions remain with SEL / PRG / GOV per existing repo
conventions. The artifact emitted by this runner carries the
``observation_only`` metadata note; the schema pins it via a const
constraint.

Exit codes
----------
0 — gate_status=pass
1 — gate_status=warn
2 — gate_status=block (fail-closed: do not proceed to PR-ready handoff)
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.contracts import validate_artifact  # noqa: E402
from spectrum_systems.modules.runtime.core_loop_pre_pr_gate import (  # noqa: E402
    build_check,
    build_gate_result,
    consume_shard_artifacts,
    consume_shard_first_readiness_observation,
    diff_hash_maps,
    gate_status_to_exit_code,
    hash_paths,
    utc_now_iso,
    write_json,
)
from spectrum_systems.modules.runtime.core_loop_pre_pr_gate_policy import (  # noqa: E402
    DEFAULT_POLICY_REL_PATH,
    PolicyLoadError,
    load_policy,
)
from spectrum_systems.modules.runtime.pr_test_selection import (  # noqa: E402
    is_docs_only_non_governed,
    resolve_required_tests,
)
from spectrum_systems.modules.governance.changed_files import (  # noqa: E402
    ChangedFilesResolutionError,
    resolve_changed_files,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="CLP-01 Core Loop Pre-PR Gate")
    parser.add_argument("--work-item-id", required=True)
    parser.add_argument(
        "--agent-type",
        default="unknown",
        choices=["codex", "claude", "other", "unknown"],
    )
    parser.add_argument("--base-ref", default="origin/main")
    parser.add_argument("--head-ref", default="HEAD")
    parser.add_argument(
        "--output-dir",
        default="outputs/core_loop_pre_pr_gate",
    )
    parser.add_argument(
        "--execution-context",
        default="pqx_governed",
        help="Forwarded to contract preflight as --execution-context.",
    )
    parser.add_argument(
        "--max-repair-attempts",
        type=int,
        default=0,
        help="CLP-01 does not auto-fix. Repair belongs to PRL/FRE/CDE/PQX. Default 0.",
    )
    parser.add_argument(
        "--repo-mutating",
        default="auto",
        choices=["auto", "true", "false"],
        help="Override repo-mutating detection. Default 'auto' uses changed-file heuristics.",
    )
    parser.add_argument(
        "--changed-file",
        action="append",
        default=[],
        help="Optional explicit changed file path. Repeat as needed.",
    )
    parser.add_argument(
        "--source-artifact",
        action="append",
        default=[],
        help="Optional upstream source artifact path. Repeat as needed.",
    )
    parser.add_argument(
        "--skip",
        action="append",
        default=[],
        help="Skip a named check (DEBUG ONLY: gate will block on missing required check).",
    )
    parser.add_argument(
        "--policy",
        default=DEFAULT_POLICY_REL_PATH,
        help=(
            "Path to docs/governance/core_loop_pre_pr_gate_policy.json. "
            "Loaded for traceability and recorded in source_artifacts_used. "
            "TPA owns policy authority; CLP only consumes it."
        ),
    )
    return parser.parse_args()


def _run_subcommand(
    *,
    cmd: list[str],
    log_path: Path,
    cwd: Path = REPO_ROOT,
) -> tuple[int, str]:
    """Run a subprocess command. Always tee combined stdout+stderr to log_path."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        cmd,
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
        env=os.environ.copy(),
    )
    combined = (proc.stdout or "") + (proc.stderr or "")
    log_path.write_text(combined, encoding="utf-8")
    return proc.returncode, combined


def _detect_repo_mutating(changed_files: list[str], override: str) -> bool:
    if override == "true":
        return True
    if override == "false":
        return False
    if not changed_files:
        return False
    return not is_docs_only_non_governed(changed_files)


def _check_authority_shape(
    *, base_ref: str, head_ref: str, output_dir: Path
) -> dict[str, Any]:
    out_path = output_dir / "authority_shape_preflight_result.json"
    log_path = output_dir / "authority_shape_preflight.log"
    cmd = [
        sys.executable,
        "scripts/run_authority_shape_preflight.py",
        "--base-ref",
        base_ref,
        "--head-ref",
        head_ref,
        "--suggest-only",
        "--output",
        str(out_path.relative_to(REPO_ROOT)),
    ]
    rc, _ = _run_subcommand(cmd=cmd, log_path=log_path)
    status = "pass"
    failure_class: str | None = None
    reason_codes: list[str] = []
    if not out_path.is_file():
        status = "block"
        failure_class = "missing_required_artifact"
        reason_codes = ["authority_shape_output_missing"]
        return build_check(
            check_name="authority_shape_preflight",
            command=" ".join(shlex.quote(p) for p in cmd),
            status=status,
            output_ref=None if status == "skipped" else str(out_path.relative_to(REPO_ROOT)),
            failure_class=failure_class,
            reason_codes=reason_codes,
            next_action="rerun_authority_shape_preflight",
        )
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    payload_status = str(payload.get("status") or "").lower()
    if rc != 0 or payload_status == "fail":
        status = "block"
        failure_class = "authority_shape_violation"
        reason_codes = sorted(
            {str(v.get("rule") or "authority_shape_violation") for v in payload.get("violations", [])}
        ) or ["authority_shape_violation"]
    return build_check(
        check_name="authority_shape_preflight",
        command=" ".join(shlex.quote(p) for p in cmd),
        status=status,
        output_ref=str(out_path.relative_to(REPO_ROOT)),
        failure_class=failure_class,
        reason_codes=reason_codes,
        next_action="resolve_authority_shape_violations" if status == "block" else "none",
    )


def _check_authority_leak(
    *, base_ref: str, head_ref: str, output_dir: Path
) -> dict[str, Any]:
    out_path = output_dir / "authority_leak_guard_result.json"
    log_path = output_dir / "authority_leak_guard.log"
    cmd = [
        sys.executable,
        "scripts/run_authority_leak_guard.py",
        "--base-ref",
        base_ref,
        "--head-ref",
        head_ref,
        "--output",
        str(out_path.relative_to(REPO_ROOT)),
    ]
    rc, _ = _run_subcommand(cmd=cmd, log_path=log_path)
    status = "pass"
    failure_class: str | None = None
    reason_codes: list[str] = []
    if not out_path.is_file():
        return build_check(
            check_name="authority_leak_guard",
            command=" ".join(shlex.quote(p) for p in cmd),
            status="block",
            output_ref=None,
            failure_class="missing_required_artifact",
            reason_codes=["authority_leak_output_missing"],
            next_action="rerun_authority_leak_guard",
        )
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    payload_status = str(payload.get("status") or "").lower()
    if rc != 0 or payload_status == "fail":
        status = "block"
        failure_class = "authority_leak_violation"
        reason_codes = list(payload.get("normalized_reason_codes") or []) or [
            "authority_leak_violation"
        ]
    return build_check(
        check_name="authority_leak_guard",
        command=" ".join(shlex.quote(p) for p in cmd),
        status=status,
        output_ref=str(out_path.relative_to(REPO_ROOT)),
        failure_class=failure_class,
        reason_codes=reason_codes,
        next_action="resolve_authority_leak_violations" if status == "block" else "none",
    )


def _check_contract_enforcement(*, output_dir: Path) -> dict[str, Any]:
    log_path = output_dir / "contract_enforcement.log"
    cmd = [sys.executable, "scripts/run_contract_enforcement.py"]
    rc, combined = _run_subcommand(cmd=cmd, log_path=log_path)
    status = "pass" if rc == 0 else "block"
    failure_class = None
    reason_codes: list[str] = []
    if status == "block":
        failure_class = "contract_enforcement_violation"
        reason_codes = ["contract_compliance_findings"]
    return build_check(
        check_name="contract_enforcement",
        command=" ".join(shlex.quote(p) for p in cmd),
        status=status,
        output_ref=str(log_path.relative_to(REPO_ROOT)),
        failure_class=failure_class,
        reason_codes=reason_codes,
        next_action="resolve_contract_enforcement_findings" if status == "block" else "none",
    )


def _check_tls_freshness(*, output_dir: Path) -> dict[str, Any]:
    """Run TLS generators and detect stale generated artifacts via hash diff."""
    artifact_paths = [
        REPO_ROOT / "artifacts" / "tls" / "system_registry_dependency_graph.json",
        REPO_ROOT / "artifacts" / "tls" / "system_evidence_attachment.json",
        REPO_ROOT / "artifacts" / "tls" / "system_candidate_classification.json",
        REPO_ROOT / "artifacts" / "tls" / "system_trust_gap_report.json",
        REPO_ROOT / "artifacts" / "tls" / "system_dependency_priority_report.json",
        REPO_ROOT / "artifacts" / "system_dependency_priority_report.json",
    ]
    health_path = REPO_ROOT / "artifacts" / "ecosystem_health_report.json"
    if health_path.exists() or (REPO_ROOT / "artifacts").exists():
        artifact_paths.append(health_path)
    before = hash_paths(artifact_paths)
    log_path = output_dir / "tls_freshness.log"
    obs_path = output_dir / "tls_freshness_observation.json"
    tls_cmd = [
        sys.executable,
        "scripts/build_tls_dependency_priority.py",
        "--out",
        "artifacts/tls",
        "--top-level-out",
        "artifacts",
        "--candidates",
        "",
    ]
    eco_cmd = [sys.executable, "scripts/generate_ecosystem_health_report.py"]
    rc1, _ = _run_subcommand(cmd=tls_cmd, log_path=log_path)
    rc2, _ = _run_subcommand(cmd=eco_cmd, log_path=output_dir / "ecosystem_health.log")
    after = hash_paths(artifact_paths)
    changed = diff_hash_maps(before, after)
    payload = {
        "artifact_type": "tls_freshness_observation",
        "authority_scope": "observation_only",
        "tls_command_returncode": rc1,
        "ecosystem_command_returncode": rc2,
        "checked_paths": [str(p.relative_to(REPO_ROOT)) for p in artifact_paths],
        "changed_paths": [str(Path(p).relative_to(REPO_ROOT)) for p in changed if Path(p).is_absolute()]
        or changed,
        "before_digests": {str(Path(k).relative_to(REPO_ROOT)) if Path(k).is_absolute() else k: v for k, v in before.items()},
        "after_digests": {str(Path(k).relative_to(REPO_ROOT)) if Path(k).is_absolute() else k: v for k, v in after.items()},
    }
    write_json(obs_path, payload)
    status = "pass"
    failure_class: str | None = None
    reason_codes: list[str] = []
    if rc1 != 0 or rc2 != 0:
        status = "block"
        failure_class = "tls_generated_artifact_stale"
        reason_codes = ["tls_generator_returned_nonzero"]
    elif changed:
        status = "block"
        failure_class = "tls_generated_artifact_stale"
        reason_codes = ["tls_generated_artifact_drift"]
    return build_check(
        check_name="tls_generated_artifact_freshness",
        command=" && ".join(
            [
                " ".join(shlex.quote(p) for p in tls_cmd),
                " ".join(shlex.quote(p) for p in eco_cmd),
            ]
        ),
        status=status,
        output_ref=str(obs_path.relative_to(REPO_ROOT)),
        failure_class=failure_class,
        reason_codes=reason_codes,
        next_action="regenerate_and_commit_tls_artifacts" if status == "block" else "none",
    )


def _check_contract_preflight(
    *, base_ref: str, head_ref: str, output_dir: Path, execution_context: str
) -> dict[str, Any]:
    sub_dir = output_dir / "contract_preflight"
    sub_dir.mkdir(parents=True, exist_ok=True)
    wrapper_path = sub_dir / "preflight_pqx_task_wrapper.json"
    log_path = output_dir / "contract_preflight.log"
    build_cmd = [
        sys.executable,
        "scripts/build_preflight_pqx_wrapper.py",
        "--base-ref",
        base_ref,
        "--head-ref",
        head_ref,
        "--output",
        str(wrapper_path.relative_to(REPO_ROOT)),
    ]
    rc_build, _ = _run_subcommand(cmd=build_cmd, log_path=output_dir / "preflight_pqx_wrapper.log")
    if rc_build != 0 or not wrapper_path.is_file():
        return build_check(
            check_name="contract_preflight",
            command=" ".join(shlex.quote(p) for p in build_cmd),
            status="block",
            output_ref=str((output_dir / "preflight_pqx_wrapper.log").relative_to(REPO_ROOT)),
            failure_class="missing_required_artifact",
            reason_codes=["preflight_wrapper_build_failed"],
            next_action="diagnose_preflight_wrapper_build_failure",
        )
    preflight_cmd = [
        sys.executable,
        "scripts/run_contract_preflight.py",
        "--base-ref",
        base_ref,
        "--head-ref",
        head_ref,
        "--output-dir",
        str(sub_dir.relative_to(REPO_ROOT)),
        "--execution-context",
        execution_context,
        "--pqx-wrapper-path",
        str(wrapper_path.relative_to(REPO_ROOT)),
        "--authority-evidence-ref",
        "artifacts/pqx_runs/preflight.pqx_slice_execution_record.json",
    ]
    rc, _ = _run_subcommand(cmd=preflight_cmd, log_path=log_path)
    artifact_path = sub_dir / "contract_preflight_result_artifact.json"
    output_ref = (
        str(artifact_path.relative_to(REPO_ROOT))
        if artifact_path.is_file()
        else str(log_path.relative_to(REPO_ROOT))
    )
    if not artifact_path.is_file():
        return build_check(
            check_name="contract_preflight",
            command=" ".join(shlex.quote(p) for p in preflight_cmd),
            status="block",
            output_ref=output_ref,
            failure_class="missing_required_artifact",
            reason_codes=["contract_preflight_artifact_missing"],
            next_action="diagnose_preflight_run_failure",
        )
    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    decision = (
        payload.get("control_signal", {}).get("strategy_gate_decision") or ""
    ).upper()
    status = "pass"
    failure_class: str | None = None
    reason_codes: list[str] = []
    if rc != 0 or decision in {"BLOCK", "FREEZE"}:
        status = "block"
        failure_class = "contract_preflight_block"
        reason_codes = [decision.lower() or "contract_preflight_block"]
    return build_check(
        check_name="contract_preflight",
        command=" ".join(shlex.quote(p) for p in preflight_cmd),
        status=status,
        output_ref=output_ref,
        failure_class=failure_class,
        reason_codes=reason_codes,
        next_action="diagnose_preflight_block_bundle" if status == "block" else "none",
    )


def _check_evl_shard_artifacts(
    *,
    output_dir: Path,
    base_ref: str,
    head_ref: str,
    required_shards: list[str],
    allowed_skipped_shards: list[str],
    invoke_runner_if_missing: bool,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """CLP-side EVL shard evidence consumer.

    CLP consumes existing shard artifacts written by
    ``scripts/run_pr_test_shards.py``. It does NOT recompute shard
    selection or per-shard pytest results. Per the active CLP policy,
    the runner may be invoked here only as an evidence-production
    convenience when the artifacts are absent — the artifacts emitted
    are still the canonical observation surface.
    """
    shard_dir = REPO_ROOT / "outputs" / "pr_test_shards"
    summary_path = shard_dir / "pr_test_shards_summary.json"

    if not summary_path.is_file() and invoke_runner_if_missing:
        log_path = output_dir / "evl_shard_artifacts_runner.log"
        cmd = [
            sys.executable,
            "scripts/run_pr_test_shards.py",
            "--base-ref",
            base_ref,
            "--head-ref",
            head_ref,
            "--output-dir",
            str(shard_dir.relative_to(REPO_ROOT)),
        ]
        _run_subcommand(cmd=cmd, log_path=log_path)

    evidence, check = consume_shard_artifacts(
        shard_dir=shard_dir,
        repo_root=REPO_ROOT,
        required_shards=tuple(required_shards),
        allowed_skipped_shards=tuple(allowed_skipped_shards),
    )

    obs_path = output_dir / "evl_shard_artifacts_observation.json"
    write_json(
        obs_path,
        {
            "artifact_type": "evl_shard_artifacts_observation",
            "authority_scope": "observation_only",
            "evl_shard_evidence": evidence,
        },
    )
    return evidence, check


def _check_evl_shard_first_readiness(
    *,
    output_dir: Path,
    base_ref: str,
    head_ref: str,
    observation_rel_path: str,
    allowed_fallback_reason_codes: list[str],
    invoke_builder_if_missing: bool,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """CLP-side EVL shard-first readiness observation consumer.

    CLP reads the existing
    ``pr_test_shard_first_readiness_observation`` artifact emitted by
    ``scripts/build_pr_test_shard_first_readiness_observation.py``. CLP
    does NOT run pytest, recompute selection, or rebuild the
    observation. Per the active CLP policy, the builder may be invoked
    here only as an evidence-production convenience when the
    observation is absent — the artifact emitted is still the canonical
    pre-PR shard-first observation surface.
    """
    observation_path = (REPO_ROOT / observation_rel_path).resolve()

    if not observation_path.is_file() and invoke_builder_if_missing:
        log_path = output_dir / "evl_shard_first_readiness_builder.log"
        cmd = [
            sys.executable,
            "scripts/build_pr_test_shard_first_readiness_observation.py",
            "--base-ref",
            base_ref,
            "--head-ref",
            head_ref,
            "--output",
            observation_rel_path,
        ]
        _run_subcommand(cmd=cmd, log_path=log_path)

    evidence, check = consume_shard_first_readiness_observation(
        observation_path=observation_path,
        repo_root=REPO_ROOT,
        allowed_fallback_reason_codes=tuple(allowed_fallback_reason_codes),
    )

    obs_path = output_dir / "evl_shard_first_readiness_observation.json"
    write_json(
        obs_path,
        {
            "artifact_type": "evl_shard_first_readiness_observation",
            "authority_scope": "observation_only",
            "evl_shard_first_evidence": evidence,
        },
    )
    return evidence, check


def _check_selected_tests(
    *, changed_files: list[str], output_dir: Path
) -> dict[str, Any]:
    targets_map = resolve_required_tests(REPO_ROOT, changed_files)
    test_targets = sorted({t for ts in targets_map.values() for t in ts})
    obs_path = output_dir / "selected_tests_result.json"
    log_path = output_dir / "selected_tests.log"
    if not test_targets:
        if changed_files and is_docs_only_non_governed(changed_files):
            payload = {
                "artifact_type": "selected_tests_observation",
                "authority_scope": "observation_only",
                "changed_files": changed_files,
                "selected_tests": [],
                "reason": "docs_only_non_governed",
                "returncode": None,
            }
            write_json(obs_path, payload)
            return build_check(
                check_name="selected_tests",
                command="(no governed tests required)",
                status="pass",
                output_ref=str(obs_path.relative_to(REPO_ROOT)),
                next_action="none",
            )
        # Repo-mutating without selectable tests: fail closed.
        payload = {
            "artifact_type": "selected_tests_observation",
            "authority_scope": "observation_only",
            "changed_files": changed_files,
            "selected_tests": [],
            "reason": "no_tests_selected_for_governed_changes",
            "returncode": None,
        }
        write_json(obs_path, payload)
        return build_check(
            check_name="selected_tests",
            command="(canonical selector returned empty test set)",
            status="block",
            output_ref=str(obs_path.relative_to(REPO_ROOT)),
            failure_class="pytest_selection_missing",
            reason_codes=["no_tests_selected_for_governed_changes"],
            next_action="add_canonical_test_for_changed_surface",
        )
    cmd = [sys.executable, "-m", "pytest", "-q", *test_targets]
    rc, combined = _run_subcommand(cmd=cmd, log_path=log_path)
    payload = {
        "artifact_type": "selected_tests_observation",
        "authority_scope": "observation_only",
        "changed_files": changed_files,
        "selected_tests": test_targets,
        "returncode": rc,
        "log_ref": str(log_path.relative_to(REPO_ROOT)),
    }
    write_json(obs_path, payload)
    status = "pass" if rc == 0 else "block"
    failure_class = None if rc == 0 else "selected_test_failure"
    reason_codes: list[str] = [] if rc == 0 else [f"pytest_returncode_{rc}"]
    return build_check(
        check_name="selected_tests",
        command=" ".join(shlex.quote(p) for p in cmd),
        status=status,
        output_ref=str(obs_path.relative_to(REPO_ROOT)),
        failure_class=failure_class,
        reason_codes=reason_codes,
        next_action="repair_failing_tests" if status == "block" else "none",
    )


def main() -> int:
    args = _parse_args()
    output_dir = (REPO_ROOT / args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    policy_path = (REPO_ROOT / args.policy).resolve()
    try:
        policy = load_policy(policy_path)
    except PolicyLoadError as exc:
        # Fail-closed: refuse to emit a CLP result without a valid policy ref.
        print(
            json.dumps(
                {
                    "error": "policy_load_failed",
                    "policy": str(policy_path),
                    "detail": str(exc),
                },
                indent=2,
            ),
            file=sys.stderr,
        )
        return 2
    policy_ref = str(policy_path.relative_to(REPO_ROOT))
    shard_policy = policy.get("evl_shard_evidence") or {}
    required_shards: list[str] = list(
        shard_policy.get("required_shards") or ["contract", "governance", "changed_scope"]
    )
    allowed_skipped_shards: list[str] = list(
        shard_policy.get("allowed_skipped_shards") or []
    )
    invoke_runner_if_missing: bool = bool(
        shard_policy.get("invoke_runner_if_missing", False)
    )

    shard_first_policy = policy.get("evl_shard_first_readiness_evidence") or {}
    shard_first_observation_rel_path: str = str(
        shard_first_policy.get("observation_path")
        or "outputs/pr_test_shard_first_readiness/"
        "pr_test_shard_first_readiness_observation.json"
    )
    shard_first_allowed_fallback_reason_codes: list[str] = list(
        shard_first_policy.get("allowed_fallback_reason_codes") or []
    )
    shard_first_invoke_builder_if_missing: bool = bool(
        shard_first_policy.get("invoke_builder_if_missing", False)
    )

    try:
        changed_files = resolve_changed_files(
            repo_root=REPO_ROOT,
            base_ref=args.base_ref,
            head_ref=args.head_ref,
            explicit_changed_files=list(args.changed_file or []),
        )
    except ChangedFilesResolutionError as exc:
        changed_files = list(args.changed_file or [])
        warning_path = output_dir / "changed_files_resolution.warning"
        warning_path.write_text(str(exc), encoding="utf-8")

    repo_mutating = _detect_repo_mutating(changed_files, args.repo_mutating)

    skip = set(args.skip or [])
    checks: list[dict[str, Any]] = []
    if "authority_shape_preflight" not in skip:
        checks.append(
            _check_authority_shape(
                base_ref=args.base_ref, head_ref=args.head_ref, output_dir=output_dir
            )
        )
    if "authority_leak_guard" not in skip:
        checks.append(
            _check_authority_leak(
                base_ref=args.base_ref, head_ref=args.head_ref, output_dir=output_dir
            )
        )
    if "contract_enforcement" not in skip:
        checks.append(_check_contract_enforcement(output_dir=output_dir))
    if "tls_generated_artifact_freshness" not in skip:
        checks.append(_check_tls_freshness(output_dir=output_dir))
    if "contract_preflight" not in skip:
        checks.append(
            _check_contract_preflight(
                base_ref=args.base_ref,
                head_ref=args.head_ref,
                output_dir=output_dir,
                execution_context=args.execution_context,
            )
        )
    if "selected_tests" not in skip:
        checks.append(
            _check_selected_tests(changed_files=changed_files, output_dir=output_dir)
        )
    evl_shard_evidence: dict[str, Any] | None = None
    if "evl_shard_artifacts" not in skip:
        evl_shard_evidence, evl_shard_check = _check_evl_shard_artifacts(
            output_dir=output_dir,
            base_ref=args.base_ref,
            head_ref=args.head_ref,
            required_shards=required_shards,
            allowed_skipped_shards=allowed_skipped_shards,
            invoke_runner_if_missing=invoke_runner_if_missing,
        )
        checks.append(evl_shard_check)

    evl_shard_first_evidence: dict[str, Any] | None = None
    if "evl_shard_first_readiness" not in skip:
        evl_shard_first_evidence, evl_shard_first_check = (
            _check_evl_shard_first_readiness(
                output_dir=output_dir,
                base_ref=args.base_ref,
                head_ref=args.head_ref,
                observation_rel_path=shard_first_observation_rel_path,
                allowed_fallback_reason_codes=shard_first_allowed_fallback_reason_codes,
                invoke_builder_if_missing=shard_first_invoke_builder_if_missing,
            )
        )
        checks.append(evl_shard_first_check)

    emitted_path = output_dir / "core_loop_pre_pr_gate_result.json"
    source_artifacts = list(args.source_artifact or [])
    if policy_ref not in source_artifacts:
        source_artifacts.append(policy_ref)
    artifact = build_gate_result(
        work_item_id=args.work_item_id,
        agent_type=args.agent_type,
        repo_mutating=repo_mutating,
        base_ref=args.base_ref,
        head_ref=args.head_ref,
        changed_files=changed_files,
        checks=checks,
        source_artifacts_used=source_artifacts,
        emitted_artifacts=[str(emitted_path.relative_to(REPO_ROOT))],
        generated_at=utc_now_iso(),
        evl_shard_evidence=evl_shard_evidence,
        evl_shard_first_evidence=evl_shard_first_evidence,
    )
    validate_artifact(artifact, "core_loop_pre_pr_gate_result")
    write_json(emitted_path, artifact)
    print(
        json.dumps(
            {
                "gate_status": artifact["gate_status"],
                "first_failed_check": artifact["first_failed_check"],
                "failure_classes": artifact["failure_classes"],
                "human_review_required": artifact["human_review_required"],
                "output": str(emitted_path.relative_to(REPO_ROOT)),
            },
            indent=2,
        )
    )
    return gate_status_to_exit_code(artifact["gate_status"])


if __name__ == "__main__":
    raise SystemExit(main())
