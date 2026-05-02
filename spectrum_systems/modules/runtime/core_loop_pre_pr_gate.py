"""Core Loop Pre-PR Gate (CLP-01) — pure-logic helpers.

This module provides deterministic, testable functions for assembling a
``core_loop_pre_pr_gate_result`` artifact. The runner script in
``scripts/run_core_loop_pre_pr_gate.py`` invokes the underlying canonical
preflight tools (authority shape, authority leak, contract enforcement,
TLS freshness, contract preflight, selected tests) and feeds their outputs
into these helpers.

Authority scope: observation_only.

CLP is an evidence-bundle runner. It does NOT own admission, execution
closure, eval certification, policy adjudication, control decision, or
final compliance enforcement. Those authorities remain with AEX, PQX, EVL,
TPA, CDE, and SEL respectively (per docs/architecture/system_registry.md).
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

REQUIRED_CHECK_NAMES: tuple[str, ...] = (
    "authority_shape_preflight",
    "authority_leak_guard",
    "contract_enforcement",
    "tls_generated_artifact_freshness",
    "contract_preflight",
    "selected_tests",
    "evl_shard_artifacts",
)

# Re-exported gate-status constants. CLP-02 modules consume these so they do
# not need to repeat the canonical authority-shape vocabulary as inline
# string literals (this module is the canonical CLP gate runtime and is
# allow-listed by the authority-leak guard for these values).
GATE_STATUS_PASS = "pass"
GATE_STATUS_WARN = "warn"
GATE_STATUS_BLOCK = "block"
CHECK_STATUS_PASS = GATE_STATUS_PASS
CHECK_STATUS_WARN = GATE_STATUS_WARN
CHECK_STATUS_BLOCK = GATE_STATUS_BLOCK
CHECK_STATUS_SKIPPED = "skipped"

CHECK_OWNER: dict[str, str] = {
    "authority_shape_preflight": "AEX",
    "authority_leak_guard": "AEX",
    "contract_enforcement": "EVL",
    "tls_generated_artifact_freshness": "LIN",
    "contract_preflight": "EVL",
    "selected_tests": "EVL",
    "evl_shard_artifacts": "EVL",
}

KNOWN_FAILURE_CLASSES: frozenset[str] = frozenset(
    {
        "authority_shape_violation",
        "authority_leak_violation",
        "contract_enforcement_violation",
        "tls_generated_artifact_stale",
        "contract_preflight_block",
        "contract_schema_violation",
        "pytest_selection_missing",
        "selected_test_failure",
        "missing_required_artifact",
        "missing_required_check_output",
        "policy_mismatch",
        "system_registry_mismatch",
        "trace_missing",
        "replay_mismatch",
        "rate_limited",
        "timeout",
        "evl_shard_evidence_missing",
        "evl_shard_evidence_invalid",
        "evl_required_shard_failed",
        "evl_required_shard_missing",
        "evl_required_shard_unknown",
        "evl_required_shard_skipped",
        "evl_pass_shard_missing_artifact_refs",
        "evl_non_pass_shard_missing_reason_codes",
    }
)


def utc_now_iso() -> str:
    """Return a UTC ISO-8601 timestamp suitable for ``generated_at``."""
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def stable_gate_id(*, work_item_id: str, head_ref: str, generated_at: str) -> str:
    """Return a deterministic gate identifier."""
    raw = f"{work_item_id}|{head_ref}|{generated_at}".encode("utf-8")
    return "clp-gate-" + hashlib.sha256(raw).hexdigest()[:16]


def build_check(
    *,
    check_name: str,
    command: str,
    status: str,
    output_ref: str | None,
    failure_class: str | None = None,
    reason_codes: list[str] | None = None,
    next_action: str = "none",
    required: bool = True,
    owner_system: str | None = None,
) -> dict[str, Any]:
    """Build a single check entry. Enforces internal invariants."""
    if check_name not in REQUIRED_CHECK_NAMES and required:
        raise ValueError(f"unknown required check_name: {check_name}")
    if status not in {"pass", "warn", "block", "skipped"}:
        raise ValueError(f"invalid check status: {status}")
    owner = owner_system or CHECK_OWNER.get(check_name)
    if not owner:
        raise ValueError(f"check {check_name} has no owner_system mapping")
    if status in {"pass", "warn", "block"} and not output_ref:
        raise ValueError(
            f"check {check_name} status={status} requires output_ref"
        )
    codes = list(reason_codes or [])
    if status in {"block", "warn"} and not codes:
        codes = ["unspecified_failure"]
    return {
        "check_name": check_name,
        "owner_system": owner,
        "command": command,
        "status": status,
        "output_ref": output_ref,
        "failure_class": failure_class,
        "reason_codes": codes,
        "next_action": next_action,
        "required": required,
    }


def evaluate_gate(
    *,
    checks: list[dict[str, Any]],
    repo_mutating: bool,
) -> tuple[str, str | None, list[str], bool]:
    """Compute (gate_status, first_failed_check, failure_classes, human_review_required).

    Rules:
    - any required check status=block → gate_status=block
    - any required check missing (when repo_mutating) → gate_status=block
    - any required check missing output_ref → gate_status=block
    - any required check failure_class outside KNOWN_FAILURE_CLASSES → block
      AND human_review_required=true
    - any required check status=warn (no block) → gate_status=warn
    - otherwise → gate_status=pass
    """
    seen: dict[str, dict[str, Any]] = {}
    for check in checks:
        name = check.get("check_name")
        if isinstance(name, str):
            seen[name] = check

    failure_classes: list[str] = []
    blocked = False
    warned = False
    human_review_required = False
    first_failed: str | None = None

    if repo_mutating:
        for required_name in REQUIRED_CHECK_NAMES:
            if required_name not in seen:
                blocked = True
                if first_failed is None:
                    first_failed = required_name
                failure_classes.append("missing_required_check_output")
                continue
            check = seen[required_name]
            status = check.get("status")
            if status in {"pass", "warn", "block"} and not check.get("output_ref"):
                blocked = True
                if first_failed is None:
                    first_failed = required_name
                failure_classes.append("missing_required_check_output")
                continue
            if status == "skipped" and check.get("required", True):
                blocked = True
                if first_failed is None:
                    first_failed = required_name
                failure_classes.append("missing_required_check_output")
                continue
            if status == "block":
                blocked = True
                if first_failed is None:
                    first_failed = required_name
                fc = check.get("failure_class")
                if isinstance(fc, str) and fc:
                    failure_classes.append(fc)
                    if fc not in KNOWN_FAILURE_CLASSES:
                        human_review_required = True
                else:
                    failure_classes.append("unspecified_failure")
                    human_review_required = True
            elif status == "warn":
                warned = True
                fc = check.get("failure_class")
                if isinstance(fc, str) and fc:
                    failure_classes.append(fc)
                    if fc not in KNOWN_FAILURE_CLASSES:
                        human_review_required = True
                        blocked = True
                        if first_failed is None:
                            first_failed = required_name
    else:
        for check in checks:
            status = check.get("status")
            if status == "block":
                blocked = True
                if first_failed is None:
                    first_failed = check.get("check_name")
                fc = check.get("failure_class") or "unspecified_failure"
                failure_classes.append(fc)
                if fc not in KNOWN_FAILURE_CLASSES:
                    human_review_required = True
            elif status == "warn":
                warned = True

    if blocked:
        gate_status = "block"
    elif warned:
        gate_status = "warn"
    else:
        gate_status = "pass"
    deduped: list[str] = []
    for fc in failure_classes:
        if fc not in deduped:
            deduped.append(fc)
    return gate_status, first_failed, deduped, human_review_required


def build_gate_result(
    *,
    work_item_id: str,
    agent_type: str,
    repo_mutating: bool,
    base_ref: str,
    head_ref: str,
    changed_files: list[str],
    checks: list[dict[str, Any]],
    source_artifacts_used: list[str] | None = None,
    emitted_artifacts: list[str] | None = None,
    trace_refs: list[str] | None = None,
    replay_refs: list[str] | None = None,
    generated_at: str | None = None,
    gate_id: str | None = None,
    evl_shard_evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Assemble a fully-validated ``core_loop_pre_pr_gate_result`` payload."""
    if agent_type not in {"codex", "claude", "other", "unknown"}:
        agent_type = "unknown"
    ts = generated_at or utc_now_iso()
    gid = gate_id or stable_gate_id(
        work_item_id=work_item_id, head_ref=head_ref, generated_at=ts
    )
    gate_status, first_failed, failure_classes, human_review_required = evaluate_gate(
        checks=checks, repo_mutating=repo_mutating
    )
    follow_up: list[dict[str, Any]] = []
    for check in checks:
        if check.get("status") == "block":
            follow_up.append(
                {
                    "owner_system": check.get("owner_system", "PRL"),
                    "action_type": "diagnose_and_repair",
                    "reason_code": (check.get("reason_codes") or ["unspecified_failure"])[0],
                    "source_failure_ref": check.get("output_ref")
                    or "outputs/core_loop_pre_pr_gate/missing_output_ref.json",
                }
            )
    payload: dict[str, Any] = {
        "artifact_type": "core_loop_pre_pr_gate_result",
        "schema_version": "1.0.0",
        "gate_id": gid,
        "work_item_id": work_item_id,
        "agent_type": agent_type,
        "repo_mutating": repo_mutating,
        "base_ref": base_ref,
        "head_ref": head_ref,
        "changed_files": list(changed_files),
        "gate_status": gate_status,
        "checks": list(checks),
        "first_failed_check": first_failed,
        "failure_classes": failure_classes,
        "source_artifacts_used": list(source_artifacts_used or []),
        "emitted_artifacts": list(emitted_artifacts or []),
        "required_follow_up": follow_up,
        "trace_refs": list(trace_refs or []),
        "replay_refs": list(replay_refs or []),
        "authority_scope": "observation_only",
        "human_review_required": human_review_required,
        "generated_at": ts,
    }
    if evl_shard_evidence is not None:
        payload["evl_shard_evidence"] = dict(evl_shard_evidence)
    return payload


def hash_paths(paths: Iterable[Path]) -> dict[str, str]:
    """Return path -> sha256 digest map for files that exist."""
    digests: dict[str, str] = {}
    for p in paths:
        if p.is_file():
            digests[str(p)] = hashlib.sha256(p.read_bytes()).hexdigest()
        else:
            digests[str(p)] = "ABSENT"
    return digests


def diff_hash_maps(before: dict[str, str], after: dict[str, str]) -> list[str]:
    """Return list of paths whose hash changed (or that newly appeared/disappeared)."""
    changed: list[str] = []
    for key in sorted(set(before) | set(after)):
        if before.get(key) != after.get(key):
            changed.append(key)
    return changed


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def gate_status_to_exit_code(gate_status: str) -> int:
    """Map gate_status to script exit code (0=pass, 1=warn, 2=block)."""
    return {"pass": 0, "warn": 1, "block": 2}.get(gate_status, 2)


# ---------------------------------------------------------------------------
# EVL shard evidence consumption (PAR-CLP-01)
# ---------------------------------------------------------------------------
#
# CLP consumes existing per-shard ``pr_test_shard_result`` artifacts and the
# ``pr_test_shards_summary`` artifact written by ``scripts/run_pr_test_shards.py``.
# CLP does not recompute shard results. It records artifact-backed shard
# observations (``evl_shard_evidence``) and surfaces a derived
# ``evl_shard_artifacts`` check for ``evaluate_gate``.

_VALID_SHARD_STATUSES: frozenset[str] = frozenset(
    {"pass", "fail", "skipped", "missing", "unknown"}
)


def _empty_shard_evidence() -> dict[str, Any]:
    return {
        "evl_shard_artifact_refs": [],
        "evl_shard_summary_ref": None,
        "evl_shard_status": "unknown",
        "evl_required_shards": [],
        "evl_missing_shards": [],
        "evl_failed_shards": [],
        "evl_unknown_shards": [],
        "evl_skipped_shards": [],
        "evl_shard_reason_codes": [],
    }


def _read_shard_artifact(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    if payload.get("artifact_type") != "pr_test_shard_result":
        return None
    return payload


def _read_shard_summary(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    if payload.get("artifact_type") != "pr_test_shards_summary":
        return None
    return payload


def consume_shard_artifacts(
    *,
    shard_dir: Path,
    repo_root: Path,
    required_shards: tuple[str, ...] | list[str],
    allowed_skipped_shards: tuple[str, ...] | list[str] = (),
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Consume per-shard artifacts and emit (evl_shard_evidence, check) pair.

    ``shard_dir`` is the directory written by ``scripts/run_pr_test_shards.py``
    (defaults to ``outputs/pr_test_shards``). The summary artifact lives at
    ``shard_dir / pr_test_shards_summary.json`` and per-shard artifacts at
    ``shard_dir / <shard>.json``.

    Behavior (fail-closed):
      - Missing summary -> evl_shard_status=unknown, block check.
      - Missing required shard artifact -> block check.
      - Required shard status fail/missing/unknown -> block.
      - Required shard status skipped, not in ``allowed_skipped_shards`` -> block.
      - pass shard with empty output_artifact_refs -> block.
      - non-pass shard with empty reason_codes -> block.
      - Otherwise -> pass.

    CLP does not recompute shard selection. The summary's overall_status is
    used as a corroborating signal but the required-shard scan is the
    primary readiness observation.
    """
    evidence = _empty_shard_evidence()
    evidence["evl_required_shards"] = list(required_shards)

    summary_path = shard_dir / "pr_test_shards_summary.json"
    summary = _read_shard_summary(summary_path)
    summary_ref: str | None
    if summary is not None and summary_path.is_file():
        try:
            summary_ref = str(summary_path.relative_to(repo_root))
        except ValueError:
            summary_ref = str(summary_path)
        evidence["evl_shard_summary_ref"] = summary_ref
    else:
        summary_ref = None

    artifact_refs: list[str] = []
    reason_codes: list[str] = []
    failure_class: str | None = None
    status = "pass"
    next_action = "none"

    if summary is None:
        status = "block"
        failure_class = "evl_shard_evidence_missing"
        reason_codes.append("pr_test_shards_summary_missing")
        evidence["evl_shard_status"] = "unknown"
        evidence["evl_shard_reason_codes"] = list(reason_codes)
        try:
            output_ref = str(summary_path.relative_to(repo_root))
        except ValueError:
            output_ref = str(summary_path)
        check = build_check(
            check_name="evl_shard_artifacts",
            command="(read outputs/pr_test_shards/pr_test_shards_summary.json)",
            status=status,
            output_ref=output_ref,
            failure_class=failure_class,
            reason_codes=reason_codes,
            next_action="run scripts/run_pr_test_shards.py to produce shard artifacts",
        )
        return evidence, check

    artifact_refs.append(summary_ref) if summary_ref else None
    summary_overall = str(summary.get("overall_status") or "").lower()
    summary_blocking = list(summary.get("blocking_reasons") or [])

    allowed_skipped = set(allowed_skipped_shards)
    missing: list[str] = []
    failed: list[str] = []
    unknown: list[str] = []
    skipped: list[str] = []

    for shard_name in required_shards:
        shard_artifact_path = shard_dir / f"{shard_name}.json"
        shard_artifact = _read_shard_artifact(shard_artifact_path)
        if shard_artifact is None:
            missing.append(shard_name)
            reason_codes.append(f"{shard_name}:required_shard_artifact_missing")
            continue
        try:
            ref = str(shard_artifact_path.relative_to(repo_root))
        except ValueError:
            ref = str(shard_artifact_path)
        if ref not in artifact_refs:
            artifact_refs.append(ref)
        shard_status = str(shard_artifact.get("status") or "").lower()
        if shard_status not in _VALID_SHARD_STATUSES:
            unknown.append(shard_name)
            reason_codes.append(f"{shard_name}:required_shard_status_unknown")
            continue
        if shard_status == "fail":
            failed.append(shard_name)
            reason_codes.append(f"{shard_name}:required_shard_failed")
        elif shard_status == "missing":
            missing.append(shard_name)
            reason_codes.append(f"{shard_name}:required_shard_missing")
        elif shard_status == "unknown":
            unknown.append(shard_name)
            reason_codes.append(f"{shard_name}:required_shard_unknown")
        elif shard_status == "skipped":
            skipped.append(shard_name)
            if shard_name not in allowed_skipped:
                reason_codes.append(f"{shard_name}:required_shard_skipped")
        else:  # pass
            shard_refs = shard_artifact.get("output_artifact_refs") or []
            if not shard_refs:
                reason_codes.append(
                    f"{shard_name}:pass_shard_missing_output_artifact_refs"
                )
                failed.append(shard_name)
            for r in shard_refs:
                if isinstance(r, str) and r and r not in artifact_refs:
                    artifact_refs.append(r)
        # Non-pass shard MUST carry reason_codes per upstream contract; if
        # the artifact violates that, surface a CLP-side observation.
        if shard_status != "pass" and not shard_artifact.get("reason_codes"):
            reason_codes.append(
                f"{shard_name}:non_pass_shard_missing_reason_codes"
            )

    # Other (non-required) per-shard artifacts referenced by the summary
    # are still surfaced as artifact refs so consumers can audit the full
    # shard set without re-reading the summary.
    for ref in summary.get("shard_artifact_refs") or []:
        if isinstance(ref, str) and ref and ref not in artifact_refs:
            artifact_refs.append(ref)

    evidence["evl_shard_artifact_refs"] = artifact_refs
    evidence["evl_missing_shards"] = sorted(set(missing))
    evidence["evl_failed_shards"] = sorted(set(failed))
    evidence["evl_unknown_shards"] = sorted(set(unknown))
    evidence["evl_skipped_shards"] = sorted(set(skipped))
    evidence["evl_shard_reason_codes"] = list(reason_codes)

    if failed or missing or unknown:
        status = "block"
    elif any(s not in allowed_skipped for s in skipped):
        status = "block"
    elif summary_overall == "block":
        # Summary's own observation says block — surface it even if our
        # required-shard scan came up clean (defensive fail-closed).
        status = "block"
        for blocking_reason in summary_blocking:
            if isinstance(blocking_reason, str) and blocking_reason:
                if blocking_reason not in reason_codes:
                    reason_codes.append(blocking_reason)
    elif summary_overall not in {"pass", "block"}:
        status = "block"
        reason_codes.append(f"summary_overall_status_{summary_overall or 'empty'}")

    if status == "pass":
        evidence["evl_shard_status"] = "pass"
    else:
        # Distinguish unknown summary state from an explicit block.
        if summary_overall in {"pass", "block"}:
            evidence["evl_shard_status"] = "block"
        else:
            evidence["evl_shard_status"] = "unknown"

    if status == "block":
        if missing or unknown:
            failure_class = "evl_shard_evidence_missing"
        else:
            failure_class = "evl_required_shard_failed"
        next_action = "repair_failing_or_missing_shards"
        if not reason_codes:
            reason_codes.append("evl_shard_evidence_block")

    evidence["evl_shard_reason_codes"] = list(reason_codes)

    output_ref = summary_ref or (
        str(shard_dir.relative_to(repo_root)) if shard_dir.is_dir() else None
    )
    check = build_check(
        check_name="evl_shard_artifacts",
        command="(consume outputs/pr_test_shards/*.json + summary)",
        status=status,
        output_ref=output_ref,
        failure_class=failure_class,
        reason_codes=reason_codes,
        next_action=next_action,
    )
    return evidence, check
