"""Deterministic MAP process-flow document generator."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List


def _line(item: str) -> str:
    return f"- {item}"


def _derive_weak_points(snapshot: Dict[str, Any], eval_result: Dict[str, Any]) -> List[str]:
    findings = snapshot.get("findings_summary", {})
    weakness: List[str] = []
    if int(findings.get("eval_coverage_gaps", 0)) > 0:
        weakness.append("missing eval coverage for governed seams")
    if int(findings.get("redundancy_findings", 0)) > 0:
        weakness.append("high redundancy across inspected files")
    if int(findings.get("drift_findings", 0)) > 0:
        weakness.append("drift risk exceeds preferred baseline")
    if int(findings.get("control_bypass_findings", 0)) > 0:
        weakness.append("control-bypass findings require hard remediation")

    failure_modes = eval_result.get("failure_modes", [])
    if isinstance(failure_modes, list):
        for mode in sorted(set(str(item) for item in failure_modes)):
            weakness.append(f"eval signal present: {mode}")

    if not weakness:
        weakness.append("no active weak points detected from current review/eval artifacts")
    return sorted(set(weakness))


def generate_repo_process_flow_markdown(
    *,
    snapshot: Dict[str, Any],
    eval_result: Dict[str, Any],
    eval_summary: Dict[str, Any],
    control_decision: Dict[str, Any],
    roadmap_plan: Dict[str, Any],
    sequence_state: Dict[str, Any],
) -> str:
    weak_points = _derive_weak_points(snapshot, eval_result)
    ordered_steps = roadmap_plan.get("ordered_steps", [])

    lines = [
        "# Repo Process Flow",
        "",
        "## Basic flow",
        "Program Direction (PRG)",
        "  ↓",
        "Review Triggering + Artifacts (RVW/RPT)",
        "  ↓",
        "Review → Eval → Control",
        "  ↓",
        "Context Selection / Ranking / Injection (CTX)",
        "  ↓",
        "TPA Plan → Build → Simplify → Gate",
        "  ↓",
        "Roadmap Selection + Authorization (MAP/RDX)",
        "  ↓",
        "Bounded Batch Execution + Progress",
        "  ↓",
        "Certification + Stop Conditions",
        "  ↓",
        "Replay + Determinism Proof",
        "",
        "## Expanded flow",
        "Program Direction Layer (program_artifact)",
        "  - constraint propagation to roadmap execution targets",
        "  - no override of control freeze/block authority",
        "  ↓",
        "Review Triggering + Artifact Layer (review_artifact / review_control_signal)",
        "  - review produces evidence + findings only",
        "  - review cannot directly authorize execution",
        "  ↓",
        "Review → Eval Bridge (review_eval_bridge)",
        "  - deterministic translation of review signal to eval_result",
        "  ↓",
        "Control Layer",
        f"  - allow / warn / freeze / block => {control_decision.get('system_response')}",
        "  - hard-stop control outcomes remain authoritative",
        "  ↓",
        "Context Layer (context_bundle_v2)",
        "  - deterministic selection + ranking",
        "  - context remains advisory (cannot alter control authority)",
        "  ↓",
        "TPA Layer (plan/build/simplify/gate)",
        "  - constrained by context + review/eval risk references",
        "  - gate does not replace control; gate only verifies local build discipline",
        "  ↓",
        "Roadmap Generation + Selection (MAP)",
        "  - deterministic next-batch proposal only",
        "  - program constraints applied before selection output is finalized",
        "  ↓",
        "Roadmap Execution (RDX + PQX)",
        "  - bounded batch execution under control authorization",
        "  - single-batch loop validation + multi-batch stop-reason enforcement",
        "  ↓",
        "Progress + Certification",
        "  - roadmap_progress_update + control_loop_certification_pack",
        "  ↓",
        "Continuation Gate (batch_continuation_record)",
        "  - captures continue/stop/escalate for each governed batch boundary",
        "  - stop immediately on freeze/block/failure/missing-signal/replay/hard-gate/max-limit conditions",
        "  ↓",
        "Stop / Escalate / Continue",
        "  - continue only when program constraints and control conditions remain aligned",
        "  ↓",
        "Replay + Determinism",
        "  - replay chain complete only with program/review/context/tpa/roadmap/control/cert refs",
        "",
        "### Compatibility details (current run snapshot)",
        "Review Snapshot (repo_review_snapshot)",
        "  ↓",
        "Eval Runner (repo_health_eval)",
        f"  - redundancy density: {eval_result.get('score')}",
        f"  - drift risk: {eval_summary.get('drift_rate')}",
        f"  - readiness score: {eval_result.get('score')}",
        "  ↓",
        "Eval Summary",
        "  ↓",
        "Roadmap Generator",
        f"  - build targets: {', '.join(roadmap_plan.get('build_candidates', []))}",
        f"  - hardening targets: {', '.join(roadmap_plan.get('hardening_targets', []))}",
        f"  - sequencing constraints: {len(roadmap_plan.get('sequencing_constraints', []))}",
        "  ↓",
        "Roadmap Selection (roadmap_selection_result)",
        "  - deterministic next-batch proposal only",
        "  ↓",
        "Control Authorization (roadmap_execution_authorization)",
        "  - control decision allow|warn|freeze|block gates execution",
        "  ↓",
        "Authorized Batch Execution (PQX)",
        f"  - slice execution: {', '.join(sequence_state.get('requested_slice_ids', []))}",
        "  - per-slice enforcement: enabled",
        "  ↓",
        "Roadmap Progress Update (roadmap_progress_update)",
        "  - selected batch only state mutation",
        "  - deterministic status transition + trace linkage",
        "  ↓",
        "Loop Validation (roadmap_execution_loop_validation)",
        "  - stage consistency, replay readiness, determinism checks",
        "  - bounded multi-batch continuation under strict stop conditions",
        "  ↓",
        "Continuation Gate (bounded by max_batches_per_run + hard-stop conditions)",
        "  - emits continue/stop/escalate with reason codes and trace linkage",
        "  ↓",
        "Stop / Escalate / Continue",
        "  - stop on any fail-closed condition; escalate on manual-review requirements",
        "  ↓",
        "Next Candidate Selection (if continue, within run limit)",
        "  ↓",
        "Artifacts",
        "  - execution record",
        "  - eval summary",
        "  - control decision",
        "  ↓",
        "Context Selection",
        "  - bounded governed sources only",
        "  ↓",
        "Context Ranking",
        "  - deterministic rules (scope/locality/risk/review/eval/recency)",
        "  ↓",
        "Context Injection",
        "  - advisory only; control/eval/certification remain authority",
        "  ↓",
        "Codex/PQX Execution",
        "  ↓",
        "Replay + Determinism Check",
        "  ↓",
        "Final Drill Report (mvp_20_slice_execution_report)",
        "  - summarizes attempted/completed/blocked/escalated slices and parity results",
        "",
        "## Current Weak Points",
    ]
    lines.extend(_line(item) for item in weak_points)
    lines.extend(
        [
            "",
            "## Derived Roadmap Steps",
            *[
                _line(f"{step.get('category')}::{step.get('target')}")
                for step in ordered_steps
            ],
            "",
        ]
    )
    return "\n".join(lines)


def write_repo_process_flow_doc(markdown: str, output_path: str | Path = "docs/reviews/repo_process_flow.md") -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(markdown.rstrip() + "\n", encoding="utf-8")
    return path


__all__ = ["generate_repo_process_flow_markdown", "write_repo_process_flow_doc"]
