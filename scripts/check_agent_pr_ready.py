#!/usr/bin/env python3
"""CLP-02 — Agent PR-Ready Guard.

Loads a ``core_loop_pre_pr_gate_result`` artifact and the
``docs/governance/core_loop_pre_pr_gate_policy.json`` policy, then emits an
``agent_pr_ready_result`` artifact recording whether a repo-mutating
Codex/Claude slice may be marked PR-ready.

This script is observation-only. It does not approve, certify, promote, or
enforce. AEX retains admission authority, PQX retains execution closure
authority, TPA retains policy authority, CDE retains continuation/closure
authority, SEL retains final compliance authority. The guard's only job is
to translate CLP evidence into a structured PR-ready signal that AGL, PRL,
and the existing required_pr_checks pytest gate can consume.

Exit codes
----------
0 — pr_ready_status=ready
1 — pr_ready_status=human_review_required
2 — pr_ready_status=not_ready (fail-closed: do not handoff as PR-ready)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.contracts import validate_artifact  # noqa: E402
from spectrum_systems.modules.runtime.core_loop_pre_pr_gate_policy import (  # noqa: E402
    DEFAULT_CLP_RESULT_REL_PATH,
    DEFAULT_POLICY_REL_PATH,
    PolicyLoadError,
    build_agent_pr_ready_result,
    evaluate_pr_ready,
    load_clp_result,
    load_policy,
    pr_ready_status_to_exit_code,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="CLP-02 Agent PR-Ready Guard")
    parser.add_argument("--work-item-id", required=True)
    parser.add_argument(
        "--agent-type",
        default="unknown",
        choices=["codex", "claude", "other", "unknown"],
    )
    parser.add_argument(
        "--clp-result",
        default=DEFAULT_CLP_RESULT_REL_PATH,
        help="Path to the core_loop_pre_pr_gate_result artifact.",
    )
    parser.add_argument(
        "--policy",
        default=DEFAULT_POLICY_REL_PATH,
        help="Path to docs/governance/core_loop_pre_pr_gate_policy.json.",
    )
    parser.add_argument(
        "--output",
        default="outputs/core_loop_pre_pr_gate/agent_pr_ready_result.json",
        help="Path to write the agent_pr_ready_result artifact.",
    )
    parser.add_argument(
        "--repo-mutating",
        default="auto",
        choices=["auto", "true", "false"],
        help=(
            "Override repo-mutating detection. Default 'auto' uses the CLP "
            "result's repo_mutating field; if no CLP result is present, "
            "defaults to true (fail-closed)."
        ),
    )
    return parser.parse_args()


def _resolve_repo_mutating(override: str, clp_result: dict | None) -> bool | None:
    if override == "true":
        return True
    if override == "false":
        return False
    if clp_result is not None and isinstance(clp_result.get("repo_mutating"), bool):
        return bool(clp_result["repo_mutating"])
    # Caller-provided "auto" with no CLP result: leave None so the evaluator
    # applies its fail-closed default.
    return None


def main() -> int:
    args = _parse_args()
    policy_path = (REPO_ROOT / args.policy).resolve()
    try:
        policy = load_policy(policy_path)
    except PolicyLoadError as exc:
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

    clp_path = (REPO_ROOT / args.clp_result).resolve()
    clp_result = load_clp_result(clp_path)
    clp_result_ref: str | None = None
    if clp_result is not None:
        try:
            clp_result_ref = str(clp_path.relative_to(REPO_ROOT))
        except ValueError:
            clp_result_ref = str(clp_path)

    repo_mutating = _resolve_repo_mutating(args.repo_mutating, clp_result)

    evaluation = evaluate_pr_ready(
        policy=policy,
        clp_result=clp_result,
        repo_mutating=repo_mutating,
    )
    artifact = build_agent_pr_ready_result(
        work_item_id=args.work_item_id,
        agent_type=args.agent_type,
        policy_ref=policy_ref,
        clp_result_ref=clp_result_ref,
        evaluation=evaluation,
    )
    validate_artifact(artifact, "agent_pr_ready_result")

    output_path = (REPO_ROOT / args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")

    summary = {
        "pr_ready_status": artifact["pr_ready_status"],
        "clp_gate_status": artifact["clp_gate_status"],
        "reason_codes": artifact["reason_codes"],
        "human_review_required": artifact["human_review_required"],
        "output": str(output_path.relative_to(REPO_ROOT)),
    }
    print(json.dumps(summary, indent=2))
    return pr_ready_status_to_exit_code(artifact["pr_ready_status"])


if __name__ == "__main__":
    raise SystemExit(main())
