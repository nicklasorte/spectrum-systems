#!/usr/bin/env python3
"""APU-3LS-01 — Agent PR-Update Ready Guard.

Loads a ``core_loop_pre_pr_gate_result`` (CLP), an
``agent_core_loop_run_record`` (AGL), and (optionally) the upstream
``agent_pr_ready_result`` guard, then evaluates them against
``docs/governance/agent_pr_update_policy.json`` and emits an
``agent_pr_update_ready_result`` evidence artifact recording whether a
repo-mutating Codex/Claude slice has the artifact-backed 3LS evidence
required to be safely handed off as PR-update ready.

This script is observation-only. It surfaces PR-update readiness inputs
and compliance observations only. Canonical authority remains with AEX
(admission), PQX (execution closure), EVL (eval evidence), TPA
(policy/scope), CDE (continuation/closure), SEL (final gate signal),
LIN (lineage), REP (replay), and GOV per
``docs/architecture/system_registry.md``.

Exit codes
----------
0 — readiness_status=ready
1 — readiness_status=human_review_required
2 — readiness_status=not_ready (fail-closed: do not hand off as PR-update ready)
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
from spectrum_systems.modules.runtime.agent_pr_update_policy import (  # noqa: E402
    DEFAULT_AGENT_PR_READY_REL_PATH,
    DEFAULT_AGL_RECORD_REL_PATH,
    DEFAULT_CLP_RESULT_REL_PATH,
    DEFAULT_OUTPUT_REL_PATH,
    DEFAULT_POLICY_REL_PATH,
    DEFAULT_PRL_ARTIFACT_INDEX_REL_PATH,
    DEFAULT_PRL_RESULT_REL_PATH,
    DEFAULT_SHARD_FIRST_READINESS_REL_PATH,
    PolicyLoadError,
    build_agent_pr_update_ready_result,
    evaluate_pr_update_ready,
    load_agent_pr_ready,
    load_agl_record,
    load_clp_result,
    load_policy,
    load_prl_artifact_index,
    load_prl_result,
    load_shard_first_readiness_observation,
    readiness_status_to_exit_code,
)
from spectrum_systems.modules.runtime.prl_auto_invoker import (  # noqa: E402
    auto_run_prl_if_clp_blocked,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="APU-3LS-01 Agent PR-Update Ready Guard"
    )
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
        "--agl-record",
        default=DEFAULT_AGL_RECORD_REL_PATH,
        help="Path to the agent_core_loop_run_record artifact.",
    )
    parser.add_argument(
        "--agent-pr-ready",
        default=DEFAULT_AGENT_PR_READY_REL_PATH,
        help="Path to the agent_pr_ready_result (CLP-02) artifact.",
    )
    parser.add_argument(
        "--prl-result",
        default=DEFAULT_PRL_RESULT_REL_PATH,
        help=(
            "Path to a prl_gate_result artifact. PRL evidence is required "
            "when CLP gate_status is the blocking-status and the slice is "
            "repo_mutating; in that case absence of PRL evidence yields "
            "readiness_status=not_ready. PRL retains all classification, "
            "repair-candidate, and eval-candidate authority."
        ),
    )
    parser.add_argument(
        "--prl-artifact-index",
        default=DEFAULT_PRL_ARTIFACT_INDEX_REL_PATH,
        help=(
            "F3L-03 — path to a prl_artifact_index artifact. The index is "
            "the canonical entrypoint into the file-backed PRL evidence "
            "chain. APU consumes file-backed PRL refs from the index "
            "rather than parsing the legacy stdout NDJSON. PRL retains "
            "all classification, repair-candidate, and eval-candidate "
            "authority."
        ),
    )
    parser.add_argument(
        "--shard-first-readiness",
        default=DEFAULT_SHARD_FIRST_READINESS_REL_PATH,
        help=(
            "EVL-RT-05 — path to a pr_test_shard_first_readiness_observation "
            "artifact. APU consumes this readiness observation directly when "
            "supplied; otherwise APU falls back to the evl_shard_first_evidence "
            "block recorded by CLP. APU does not run pytest, recompute shard "
            "selection, or rebuild the observation. EVL retains all selection, "
            "shard mapping, and shard-execution authority."
        ),
    )
    parser.add_argument(
        "--policy",
        default=DEFAULT_POLICY_REL_PATH,
        help="Path to docs/governance/agent_pr_update_policy.json.",
    )
    parser.add_argument(
        "--output",
        default=DEFAULT_OUTPUT_REL_PATH,
        help="Path to write the agent_pr_update_ready_result artifact.",
    )
    parser.add_argument(
        "--repo-mutating",
        default="auto",
        choices=["auto", "true", "false", "unknown"],
        help=(
            "Force a repo-mutating value instead of reading the value from "
            "the supplied artifacts. Default 'auto' reads CLP/AGL "
            "repo_mutating; if neither artifact provides the value, it is "
            "left unknown (which yields not_ready by policy)."
        ),
    )
    parser.add_argument(
        "--auto-run-prl-on-clp-block",
        dest="auto_run_prl_on_clp_block",
        action="store_true",
        default=True,
        help=(
            "F3L-02 — When CLP gate_status=block and repo_mutating is true, "
            "auto-invoke scripts/run_pre_pr_reliability_gate.py before "
            "evaluating PR-update readiness. PRL retains all repair / eval "
            "authority; this flag closes the manual seam so APU has "
            "artifact-backed PRL evidence to observe. Default: enabled."
        ),
    )
    parser.add_argument(
        "--no-auto-run-prl-on-clp-block",
        dest="auto_run_prl_on_clp_block",
        action="store_false",
        help="Disable F3L-02 auto-run (e.g. for tests or replay).",
    )
    return parser.parse_args()


def _resolve_repo_mutating(
    directive: str,
    *,
    clp_result: dict | None,
    agl_record: dict | None,
) -> bool | None:
    if directive == "true":
        return True
    if directive == "false":
        return False
    if directive == "unknown":
        return None
    # auto
    if isinstance(clp_result, dict) and isinstance(clp_result.get("repo_mutating"), bool):
        return bool(clp_result["repo_mutating"])
    if isinstance(agl_record, dict) and isinstance(agl_record.get("repo_mutating"), bool):
        return bool(agl_record["repo_mutating"])
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
    agl_path = (REPO_ROOT / args.agl_record).resolve()
    pr_ready_path = (REPO_ROOT / args.agent_pr_ready).resolve()
    prl_path = (REPO_ROOT / args.prl_result).resolve()
    prl_index_path = (REPO_ROOT / args.prl_artifact_index).resolve()
    shard_first_path = (REPO_ROOT / args.shard_first_readiness).resolve()

    clp_result = load_clp_result(clp_path)
    agl_record = load_agl_record(agl_path)
    agent_pr_ready = load_agent_pr_ready(pr_ready_path)
    shard_first_readiness = load_shard_first_readiness_observation(shard_first_path)

    repo_mutating = _resolve_repo_mutating(
        args.repo_mutating, clp_result=clp_result, agl_record=agl_record
    )

    # F3L-02 — auto-invoke PRL when CLP blocks and PRL evidence is missing.
    # The auto-invoker is observation-only and never claims PRL authority;
    # PRL retains all classification, repair-candidate, and eval-candidate
    # authority. The invocation record is recorded on the readiness artifact
    # so APU does not infer readiness from silence.
    auto_invocation = auto_run_prl_if_clp_blocked(
        clp_result=clp_result,
        repo_mutating=repo_mutating,
        prl_path=prl_path,
        clp_path=clp_path,
        auto_run_enabled=bool(args.auto_run_prl_on_clp_block),
    )

    prl_result = load_prl_result(prl_path)
    prl_artifact_index = load_prl_artifact_index(prl_index_path)

    def _ref(path: Path, loaded: object | None) -> str | None:
        if loaded is None and not path.is_file():
            return None
        try:
            return str(path.relative_to(REPO_ROOT))
        except ValueError:
            return str(path)

    clp_ref = _ref(clp_path, clp_result)
    agl_ref = _ref(agl_path, agl_record)
    pr_ready_ref = _ref(pr_ready_path, agent_pr_ready)
    prl_ref = _ref(prl_path, prl_result)
    prl_index_ref = _ref(prl_index_path, prl_artifact_index)
    shard_first_ref = _ref(shard_first_path, shard_first_readiness)

    auto_invocation_record = auto_invocation.to_dict()

    evaluation = evaluate_pr_update_ready(
        policy=policy,
        clp_result=clp_result,
        agl_record=agl_record,
        agent_pr_ready=agent_pr_ready,
        repo_mutating=repo_mutating,
        clp_result_ref=clp_ref,
        agl_record_ref=agl_ref,
        agent_pr_ready_result_ref=pr_ready_ref,
        policy_ref=policy_ref,
        prl_result=prl_result,
        prl_result_ref=prl_ref,
        prl_auto_invocation=auto_invocation_record,
        prl_artifact_index=prl_artifact_index,
        prl_artifact_index_ref=prl_index_ref,
        shard_first_readiness=shard_first_readiness,
        shard_first_readiness_ref=shard_first_ref,
    )
    artifact = build_agent_pr_update_ready_result(
        work_item_id=args.work_item_id,
        agent_type=args.agent_type,
        policy_ref=policy_ref,
        evaluation=evaluation,
        clp_result_ref=clp_ref,
        agl_record_ref=agl_ref,
        agent_pr_ready_result_ref=pr_ready_ref,
        prl_result_ref=prl_ref,
        prl_artifact_index_ref=prl_index_ref,
        prl_auto_invocation=auto_invocation_record,
        shard_first_readiness_ref=shard_first_ref,
    )
    validate_artifact(artifact, "agent_pr_update_ready_result")

    output_path = (REPO_ROOT / args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")

    summary = {
        "readiness_status": artifact["readiness_status"],
        "clp_status": artifact["clp_status"],
        "repo_mutating": artifact["repo_mutating"],
        "reason_codes": artifact["reason_codes"],
        "human_review_required": artifact["human_review_required"],
        "evidence_hash": artifact["evidence_hash"],
        "prl_evidence_status": artifact["prl_evidence_status"],
        "prl_gate_recommendation": artifact["prl_gate_recommendation"],
        "prl_auto_invocation_status": (
            artifact["prl_auto_invocation"].get("status")
            if isinstance(artifact.get("prl_auto_invocation"), dict)
            else None
        ),
        "shard_first_status": artifact["shard_first_status"],
        "shard_first_evidence_status": artifact["shard_first_evidence_status"],
        "shard_first_readiness_ref": artifact["shard_first_readiness_ref"],
        "output": str(output_path.relative_to(REPO_ROOT)),
    }
    print(json.dumps(summary, indent=2))
    return readiness_status_to_exit_code(artifact["readiness_status"])


if __name__ == "__main__":
    raise SystemExit(main())
