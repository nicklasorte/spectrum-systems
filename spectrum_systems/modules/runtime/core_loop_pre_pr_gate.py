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
    "evl_shard_first_readiness",
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
    "evl_shard_first_readiness": "EVL",
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
        "evl_shard_first_readiness_missing",
        "evl_shard_first_readiness_invalid",
        "evl_shard_first_readiness_partial",
        "evl_shard_first_readiness_unknown",
        "evl_shard_first_readiness_fallback_unjustified",
        "evl_shard_first_readiness_shard_refs_empty",
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
    evl_shard_first_evidence: dict[str, Any] | None = None,
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
    if evl_shard_first_evidence is not None:
        payload["evl_shard_first_evidence"] = dict(evl_shard_first_evidence)
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


# ---------------------------------------------------------------------------
# EVL shard-first readiness observation consumption (EVL-RT-04)
# ---------------------------------------------------------------------------
#
# CLP consumes the existing
# ``pr_test_shard_first_readiness_observation`` artifact emitted by the
# EVL-RT-03 builder. CLP does not run pytest, recompute selection, or
# rebuild the shard-first observation. CLP records the observation as
# pre-PR evidence and surfaces a derived ``evl_shard_first_readiness``
# check for ``evaluate_gate``.
#
# Authority scope: observation_only. CLP only consumes artifact-backed
# shard-first / fallback observations; canonical authorities for the
# selector, shard runner, runtime budget observation, and policy remain
# with the systems declared in ``docs/architecture/system_registry.md``.

_VALID_SHARD_FIRST_STATUSES: frozenset[str] = frozenset(
    {"shard_first", "fallback_justified", "missing", "partial", "unknown"}
)


def _empty_shard_first_evidence() -> dict[str, Any]:
    return {
        "evl_shard_first_observation_ref": None,
        "evl_shard_first_status": "unknown",
        "evl_shard_first_required_shard_refs": [],
        "evl_shard_first_missing_shard_refs": [],
        "evl_shard_first_failed_shard_refs": [],
        "evl_shard_first_fallback_used": False,
        "evl_shard_first_full_suite_detected": False,
        "evl_shard_first_fallback_justification_ref": None,
        "evl_shard_first_fallback_reason_codes": [],
        "evl_shard_first_reason_codes": [],
    }


def _read_shard_first_observation(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    if (
        payload.get("artifact_type")
        != "pr_test_shard_first_readiness_observation"
    ):
        return None
    return payload


def consume_shard_first_readiness_observation(
    *,
    observation_path: Path,
    repo_root: Path,
    allowed_fallback_reason_codes: tuple[str, ...] | list[str] = (),
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Consume an existing shard-first readiness observation artifact.

    Returns ``(evidence, check)`` derived from the observation. CLP does
    not re-run pytest, recompute selection, or rebuild the observation;
    a missing observation always produces a block check.

    Behavior (fail-closed):

    - missing observation file -> block (``evl_shard_first_readiness_missing``).
    - unreadable / wrong artifact_type -> block (``evl_shard_first_readiness_invalid``).
    - shard_first_status=shard_first with empty required_shard_refs -> block.
    - shard_first_status=fallback_justified with valid fallback refs and
      reason codes -> pass.
    - fallback_used or full_suite_detected without
      ``fallback_justification_ref`` or empty ``fallback_reason_codes``
      -> block (``evl_shard_first_readiness_fallback_unjustified``).
    - shard_first_status=partial -> block.
    - shard_first_status=missing -> block.
    - shard_first_status=unknown -> block.
    """
    evidence = _empty_shard_first_evidence()
    try:
        rel_path = str(observation_path.relative_to(repo_root))
    except ValueError:
        rel_path = str(observation_path)

    observation = _read_shard_first_observation(observation_path)
    if observation is None:
        evidence["evl_shard_first_observation_ref"] = rel_path
        if not observation_path.is_file():
            failure_class = "evl_shard_first_readiness_missing"
            reason_codes = ["pr_test_shard_first_readiness_observation_missing"]
        else:
            failure_class = "evl_shard_first_readiness_invalid"
            reason_codes = ["pr_test_shard_first_readiness_observation_invalid"]
        evidence["evl_shard_first_reason_codes"] = list(reason_codes)
        evidence["evl_shard_first_status"] = "unknown"
        check = build_check(
            check_name="evl_shard_first_readiness",
            command=(
                "(read outputs/pr_test_shard_first_readiness/"
                "pr_test_shard_first_readiness_observation.json)"
            ),
            status="block",
            output_ref=rel_path,
            failure_class=failure_class,
            reason_codes=reason_codes,
            next_action=(
                "run scripts/build_pr_test_shard_first_readiness_observation.py "
                "to emit the observation"
            ),
        )
        return evidence, check

    evidence["evl_shard_first_observation_ref"] = rel_path
    raw_status = str(observation.get("shard_first_status") or "").lower()
    if raw_status not in _VALID_SHARD_FIRST_STATUSES:
        evidence["evl_shard_first_status"] = "unknown"
        reason_codes = ["pr_test_shard_first_readiness_observation_invalid"]
        evidence["evl_shard_first_reason_codes"] = list(reason_codes)
        check = build_check(
            check_name="evl_shard_first_readiness",
            command="(consume pr_test_shard_first_readiness_observation)",
            status="block",
            output_ref=rel_path,
            failure_class="evl_shard_first_readiness_invalid",
            reason_codes=reason_codes,
            next_action="repair_pr_test_shard_first_readiness_observation",
        )
        return evidence, check

    required_shard_refs = [
        r for r in (observation.get("required_shard_refs") or []) if isinstance(r, str)
    ]
    missing_shard_refs = [
        r for r in (observation.get("missing_shard_refs") or []) if isinstance(r, str)
    ]
    failed_shard_refs = [
        r for r in (observation.get("failed_shard_refs") or []) if isinstance(r, str)
    ]
    fallback_used = bool(observation.get("fallback_used"))
    full_suite_detected = bool(observation.get("full_suite_detected"))
    fallback_justification_ref = observation.get("fallback_justification_ref")
    if not isinstance(fallback_justification_ref, str) or not fallback_justification_ref:
        fallback_justification_ref = None
    fallback_reason_codes = [
        r for r in (observation.get("fallback_reason_codes") or []) if isinstance(r, str)
    ]
    upstream_reason_codes = [
        r for r in (observation.get("reason_codes") or []) if isinstance(r, str)
    ]

    evidence["evl_shard_first_status"] = raw_status
    evidence["evl_shard_first_required_shard_refs"] = list(required_shard_refs)
    evidence["evl_shard_first_missing_shard_refs"] = list(missing_shard_refs)
    evidence["evl_shard_first_failed_shard_refs"] = list(failed_shard_refs)
    evidence["evl_shard_first_fallback_used"] = fallback_used
    evidence["evl_shard_first_full_suite_detected"] = full_suite_detected
    evidence["evl_shard_first_fallback_justification_ref"] = fallback_justification_ref
    evidence["evl_shard_first_fallback_reason_codes"] = list(fallback_reason_codes)

    derived_reason_codes: list[str] = list(upstream_reason_codes)
    failure_class: str | None = None
    next_action = "none"
    status = "pass"

    fallback_signalled = fallback_used or full_suite_detected
    fallback_justified_ok = bool(fallback_justification_ref) and bool(fallback_reason_codes)

    if raw_status == "shard_first":
        if fallback_signalled:
            status = "block"
            failure_class = "evl_shard_first_readiness_fallback_unjustified"
            derived_reason_codes.append(
                "shard_first_status_inconsistent_with_fallback_signals"
            )
        elif not required_shard_refs:
            status = "block"
            failure_class = "evl_shard_first_readiness_shard_refs_empty"
            derived_reason_codes.append(
                "shard_first_status_missing_required_shard_refs"
            )
        next_action = (
            "repair_pr_test_shard_first_readiness_observation"
            if status == "block"
            else "none"
        )
    elif raw_status == "fallback_justified":
        if not fallback_justified_ok:
            status = "block"
            failure_class = "evl_shard_first_readiness_fallback_unjustified"
            if not fallback_justification_ref:
                derived_reason_codes.append(
                    "fallback_justified_status_missing_fallback_justification_ref"
                )
            if not fallback_reason_codes:
                derived_reason_codes.append(
                    "fallback_justified_status_missing_fallback_reason_codes"
                )
            next_action = "repair_pr_test_shard_first_readiness_observation"
    elif raw_status == "partial":
        status = "block"
        failure_class = "evl_shard_first_readiness_partial"
        if not derived_reason_codes:
            derived_reason_codes.append(
                "shard_first_status_partial_without_upstream_reason_codes"
            )
        next_action = "repair_pr_test_shard_first_readiness_observation"
    elif raw_status == "missing":
        status = "block"
        failure_class = "evl_shard_first_readiness_missing"
        if not derived_reason_codes:
            derived_reason_codes.append(
                "shard_first_status_missing_without_upstream_reason_codes"
            )
        next_action = "produce_shard_first_readiness_observation"
    elif raw_status == "unknown":
        status = "block"
        failure_class = "evl_shard_first_readiness_unknown"
        if not derived_reason_codes:
            derived_reason_codes.append(
                "shard_first_status_unknown_without_upstream_reason_codes"
            )
        next_action = "repair_pr_test_shard_first_readiness_observation"

    # Independent fail-closed: if fallback is signalled at all without
    # justification, surface a block even if status is fallback_justified
    # somehow inconsistent with that.
    if fallback_signalled and not fallback_justified_ok and status != "block":
        status = "block"
        failure_class = "evl_shard_first_readiness_fallback_unjustified"
        if not fallback_justification_ref:
            derived_reason_codes.append(
                "fallback_signal_without_fallback_justification_ref"
            )
        if not fallback_reason_codes:
            derived_reason_codes.append(
                "fallback_signal_without_fallback_reason_codes"
            )
        next_action = "repair_pr_test_shard_first_readiness_observation"

    # Allow-list-based warn: a fallback_justified observation whose
    # fallback_reason_codes are all in allowed_fallback_reason_codes
    # passes. Anything else stays at status (pass/block). This keeps CLP
    # observation-only — TPA owns the policy that names allow-listed
    # codes.
    if (
        status == "pass"
        and raw_status == "fallback_justified"
        and allowed_fallback_reason_codes
    ):
        allowed = set(allowed_fallback_reason_codes)
        not_allowed = [c for c in fallback_reason_codes if c not in allowed]
        if not_allowed:
            status = "warn"
            failure_class = "evl_shard_first_readiness_fallback_unjustified"
            for code in not_allowed:
                if code not in derived_reason_codes:
                    derived_reason_codes.append(code)
            next_action = "tpa_review_fallback_reason_codes"

    # Deduplicate while preserving order.
    deduped: list[str] = []
    for code in derived_reason_codes:
        if code and code not in deduped:
            deduped.append(code)
    evidence["evl_shard_first_reason_codes"] = deduped

    check = build_check(
        check_name="evl_shard_first_readiness",
        command="(consume pr_test_shard_first_readiness_observation)",
        status=status,
        output_ref=rel_path,
        failure_class=failure_class,
        reason_codes=deduped,
        next_action=next_action,
    )
    return evidence, check
