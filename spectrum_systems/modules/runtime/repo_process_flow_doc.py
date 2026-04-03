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
        "Review Snapshot",
        "  ↓",
        "Repo Health Eval",
        "  ↓",
        "Eval Summary",
        "  ↓",
        "Control Decision",
        "  ↓",
        "Roadmap Selection",
        "  ↓",
        "Control Authorization",
        "  ↓",
        "Authorized Batch Execution (PQX)",
        "  ↓",
        "Roadmap Progress Update (roadmap_progress_update)",
        "  ↓",
        "Next Candidate Selection",
        "  ↓",
        "Artifacts Produced",
        "  ↓",
        "Replay + Determinism",
        "",
        "## Expanded flow",
        "Review Snapshot (repo_review_snapshot)",
        "  ↓",
        "Eval Runner (repo_health_eval)",
        f"  - redundancy density: {eval_result.get('score')}",
        f"  - drift risk: {eval_summary.get('drift_rate')}",
        f"  - readiness score: {eval_result.get('score')}",
        "  ↓",
        "Eval Summary",
        "  ↓",
        "Control Loop",
        f"  - allow / warn / freeze / block => {control_decision.get('system_response')}",
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
        "Next Candidate Selection",
        "  ↓",
        "Artifacts",
        "  - execution record",
        "  - eval summary",
        "  - control decision",
        "  ↓",
        "Replay + Determinism Check",
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
