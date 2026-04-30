"""CLP-02 — pure-logic policy loader and PR-ready evaluator.

This module is observation-only. It loads
``docs/governance/core_loop_pre_pr_gate_policy.json`` and applies it to a
``core_loop_pre_pr_gate_result`` artifact to produce an
``agent_pr_ready_result`` payload.

CLP does not own admission, execution closure, eval certification, policy
adjudication, control decisions, or final compliance enforcement. Those
authorities remain with AEX, PQX, EVL, TPA, CDE, and SEL respectively
(per ``docs/architecture/system_registry.md``). This evaluator emits
PR-ready evidence only — it does not approve, certify, promote, or enforce.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_POLICY_REL_PATH = "docs/governance/core_loop_pre_pr_gate_policy.json"
DEFAULT_CLP_RESULT_REL_PATH = (
    "outputs/core_loop_pre_pr_gate/core_loop_pre_pr_gate_result.json"
)


class PolicyLoadError(ValueError):
    """Raised when the CLP-02 policy cannot be loaded or is malformed."""


def utc_now_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def stable_guard_id(*, work_item_id: str, generated_at: str) -> str:
    raw = f"{work_item_id}|{generated_at}".encode("utf-8")
    return "agent-pr-ready-" + hashlib.sha256(raw).hexdigest()[:16]


def load_policy(path: Path) -> dict[str, Any]:
    """Load the CLP-02 policy artifact, fail-closed on missing/malformed input."""
    if not path.is_file():
        raise PolicyLoadError(f"policy not found: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PolicyLoadError(f"policy JSON parse error: {exc}") from exc
    if not isinstance(payload, dict):
        raise PolicyLoadError("policy must be a JSON object")
    if payload.get("policy_id") != "CLP-02":
        raise PolicyLoadError("policy_id must be 'CLP-02'")
    if payload.get("authority_scope") != "observation_only":
        raise PolicyLoadError("policy authority_scope must be 'observation_only'")
    required = payload.get("required_checks")
    if not isinstance(required, list) or not required:
        raise PolicyLoadError("policy.required_checks must be a non-empty list")
    return payload


def load_clp_result(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    if payload.get("artifact_type") != "core_loop_pre_pr_gate_result":
        return None
    return payload


def evaluate_pr_ready(
    *,
    policy: dict[str, Any],
    clp_result: dict[str, Any] | None,
    repo_mutating: bool | None = None,
) -> dict[str, Any]:
    """Apply policy to a CLP result. Returns a partial agent_pr_ready_result payload.

    Returns a dict with keys: pr_ready_status, reason_codes, required_follow_up,
    clp_gate_status, human_review_required, repo_mutating.

    Rules (fail-closed):
      - repo_mutating=true and CLP missing -> not_ready (clp_evidence_missing)
      - CLP gate_status=block -> not_ready (clp_gate_block + failure_classes)
      - CLP gate_status=warn:
          * any reason code outside policy.allowed_warn_reason_codes -> not_ready
          * otherwise -> ready
      - CLP gate_status=pass -> ready
      - CLP human_review_required=true -> human_review_required
      - CLP authority_scope != observation_only -> not_ready (policy_mismatch)
    """
    rules = policy.get("rules") or {}
    allowed_warn = set(policy.get("allowed_warn_reason_codes") or [])
    reasons: list[str] = []
    follow_up: list[dict[str, str]] = []
    human_review = False
    clp_gate_status: str | None = None

    if clp_result is None:
        repo_mut = bool(repo_mutating) if repo_mutating is not None else True
        if repo_mut and rules.get("missing_clp_evidence_blocks_pr_ready", True):
            reasons.append("clp_evidence_missing")
            follow_up.append(
                {
                    "owner_system": "PRL",
                    "action_type": "produce_clp_evidence",
                    "reason_code": "clp_evidence_missing",
                    "source_failure_ref": DEFAULT_CLP_RESULT_REL_PATH,
                }
            )
            return {
                "pr_ready_status": "not_ready",
                "reason_codes": reasons,
                "required_follow_up": follow_up,
                "clp_gate_status": None,
                "human_review_required": False,
                "repo_mutating": repo_mut,
            }
        # non-repo-mutating + missing CLP is allowed only if policy permits.
        return {
            "pr_ready_status": "ready",
            "reason_codes": [],
            "required_follow_up": [],
            "clp_gate_status": None,
            "human_review_required": False,
            "repo_mutating": repo_mut,
        }

    # CLP result present.
    repo_mut = bool(clp_result.get("repo_mutating")) if repo_mutating is None else bool(repo_mutating)
    clp_gate_status = clp_result.get("gate_status")
    if clp_result.get("authority_scope") != "observation_only":
        reasons.append("clp_authority_scope_invalid")
        follow_up.append(
            {
                "owner_system": "TPA",
                "action_type": "review_clp_authority_scope",
                "reason_code": "clp_authority_scope_invalid",
                "source_failure_ref": DEFAULT_CLP_RESULT_REL_PATH,
            }
        )
        return {
            "pr_ready_status": "not_ready",
            "reason_codes": reasons,
            "required_follow_up": follow_up,
            "clp_gate_status": clp_gate_status,
            "human_review_required": True,
            "repo_mutating": repo_mut,
        }

    if clp_result.get("human_review_required") is True:
        human_review = True

    if clp_gate_status == "block":
        failure_classes = clp_result.get("failure_classes") or []
        if not failure_classes:
            failure_classes = ["clp_gate_block"]
        reasons.extend(failure_classes)
        first_failed = clp_result.get("first_failed_check")
        follow_up.append(
            {
                "owner_system": "PRL",
                "action_type": "resolve_clp_block",
                "reason_code": failure_classes[0],
                "source_failure_ref": (
                    f"clp:{first_failed}" if first_failed else DEFAULT_CLP_RESULT_REL_PATH
                ),
            }
        )
        return {
            "pr_ready_status": "human_review_required" if human_review else "not_ready",
            "reason_codes": reasons,
            "required_follow_up": follow_up,
            "clp_gate_status": clp_gate_status,
            "human_review_required": human_review,
            "repo_mutating": repo_mut,
        }

    if clp_gate_status == "warn":
        # Collect warn reason codes from checks.
        warn_codes: list[str] = []
        for check in clp_result.get("checks") or []:
            if not isinstance(check, dict):
                continue
            if check.get("status") != "warn":
                continue
            for code in check.get("reason_codes") or []:
                if isinstance(code, str) and code:
                    warn_codes.append(code)
        unapproved = [c for c in warn_codes if c not in allowed_warn]
        if unapproved or rules.get("clp_warn_requires_explicit_allow", True) and not allowed_warn and warn_codes:
            reasons.extend(["clp_warn_unapproved"] + unapproved)
            follow_up.append(
                {
                    "owner_system": "TPA",
                    "action_type": "review_clp_warn_reason_codes",
                    "reason_code": (unapproved or warn_codes or ["clp_warn_unapproved"])[0],
                    "source_failure_ref": DEFAULT_CLP_RESULT_REL_PATH,
                }
            )
            return {
                "pr_ready_status": "not_ready",
                "reason_codes": reasons,
                "required_follow_up": follow_up,
                "clp_gate_status": clp_gate_status,
                "human_review_required": human_review,
                "repo_mutating": repo_mut,
            }

    if clp_gate_status not in {"pass", "warn"}:
        reasons.append("clp_gate_status_unknown")
        return {
            "pr_ready_status": "not_ready",
            "reason_codes": reasons,
            "required_follow_up": follow_up,
            "clp_gate_status": clp_gate_status,
            "human_review_required": True,
            "repo_mutating": repo_mut,
        }

    return {
        "pr_ready_status": "ready",
        "reason_codes": [],
        "required_follow_up": [],
        "clp_gate_status": clp_gate_status,
        "human_review_required": False,
        "repo_mutating": repo_mut,
    }


def build_agent_pr_ready_result(
    *,
    work_item_id: str,
    agent_type: str,
    policy_ref: str,
    clp_result_ref: str | None,
    evaluation: dict[str, Any],
    trace_refs: list[str] | None = None,
    replay_refs: list[str] | None = None,
    generated_at: str | None = None,
    guard_id: str | None = None,
) -> dict[str, Any]:
    if agent_type not in {"codex", "claude", "other", "unknown"}:
        agent_type = "unknown"
    ts = generated_at or utc_now_iso()
    gid = guard_id or stable_guard_id(work_item_id=work_item_id, generated_at=ts)
    return {
        "artifact_type": "agent_pr_ready_result",
        "schema_version": "1.0.0",
        "guard_id": gid,
        "work_item_id": work_item_id,
        "agent_type": agent_type,
        "repo_mutating": bool(evaluation.get("repo_mutating")),
        "policy_ref": policy_ref,
        "clp_result_ref": clp_result_ref,
        "clp_gate_status": evaluation.get("clp_gate_status"),
        "pr_ready_status": evaluation.get("pr_ready_status", "not_ready"),
        "reason_codes": list(evaluation.get("reason_codes") or []),
        "required_follow_up": list(evaluation.get("required_follow_up") or []),
        "trace_refs": list(trace_refs or []),
        "replay_refs": list(replay_refs or []),
        "authority_scope": "observation_only",
        "human_review_required": bool(evaluation.get("human_review_required")),
        "generated_at": ts,
    }


def pr_ready_status_to_exit_code(status: str) -> int:
    """ready=0, human_review_required=1, not_ready=2."""
    return {"ready": 0, "human_review_required": 1, "not_ready": 2}.get(status, 2)
