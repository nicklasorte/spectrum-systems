"""Read-only deterministic PR feedback formatter for governed continuation outputs."""

from __future__ import annotations

from typing import Any

from spectrum_systems.contracts import validate_artifact

_ALLOWED_TERMINAL_STATES = {"ready_for_merge", "blocked", "exhausted", "escalated"}


class GithubPrFeedbackError(ValueError):
    """Raised when PR feedback inputs are missing or malformed."""


def _require_dict(value: Any, *, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise GithubPrFeedbackError(f"{field} must be an object")
    return value


def _require_non_empty_str(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise GithubPrFeedbackError(f"{field} must be a non-empty string")
    return value.strip()


def _resolve_terminal_state(
    *,
    continuation_result: dict[str, Any] | None,
    top_level_conductor_run_artifact: dict[str, Any] | None,
) -> str:
    if top_level_conductor_run_artifact is not None:
        state = _require_non_empty_str(
            top_level_conductor_run_artifact.get("current_state"),
            field="top_level_conductor_run_artifact.current_state",
        )
    elif continuation_result is not None:
        state = _require_non_empty_str(
            continuation_result.get("final_terminal_state"),
            field="continuation_result.final_terminal_state",
        )
    else:
        raise GithubPrFeedbackError(
            "terminal state is undefined; provide top_level_conductor_run_artifact or continuation_result"
        )

    if state not in _ALLOWED_TERMINAL_STATES:
        raise GithubPrFeedbackError(f"terminal state is undefined or unsupported: {state}")
    return state


def _resolve_run_id(
    *,
    continuation_result: dict[str, Any] | None,
    closure_decision_artifact: dict[str, Any],
    top_level_conductor_run_artifact: dict[str, Any] | None,
) -> str:
    if top_level_conductor_run_artifact is not None:
        return _require_non_empty_str(top_level_conductor_run_artifact.get("run_id"), field="top_level_conductor_run_artifact.run_id")
    if continuation_result is not None and continuation_result.get("continuation_id"):
        return _require_non_empty_str(continuation_result.get("continuation_id"), field="continuation_result.continuation_id")
    return _require_non_empty_str(closure_decision_artifact.get("run_id"), field="closure_decision_artifact.run_id")


def _build_trace_refs(
    *,
    closure_decision_artifact: dict[str, Any],
    top_level_conductor_run_artifact: dict[str, Any] | None,
) -> list[str]:
    trace_refs: list[str] = []
    trace_refs.append(_require_non_empty_str(closure_decision_artifact.get("trace_id"), field="closure_decision_artifact.trace_id"))

    if top_level_conductor_run_artifact is not None:
        raw_trace_refs = top_level_conductor_run_artifact.get("trace_refs")
        if not isinstance(raw_trace_refs, list) or not raw_trace_refs:
            raise GithubPrFeedbackError("top_level_conductor_run_artifact.trace_refs must be a non-empty array")
        for index, item in enumerate(raw_trace_refs):
            trace_refs.append(_require_non_empty_str(item, field=f"top_level_conductor_run_artifact.trace_refs[{index}]") )

    deduped: list[str] = []
    for ref in trace_refs:
        if ref not in deduped:
            deduped.append(ref)
    return deduped


def build_pr_feedback_comment(artifacts: dict[str, Any]) -> str:
    """Build deterministic read-only PR feedback markdown from governed artifacts."""
    root = _require_dict(artifacts, field="artifacts")

    closure_decision_artifact = _require_dict(root.get("closure_decision_artifact"), field="closure_decision_artifact")
    validate_artifact(closure_decision_artifact, "closure_decision_artifact")

    top_level_conductor_run_artifact: dict[str, Any] | None = None
    if root.get("top_level_conductor_run_artifact") is not None:
        top_level_conductor_run_artifact = _require_dict(
            root.get("top_level_conductor_run_artifact"),
            field="top_level_conductor_run_artifact",
        )
        validate_artifact(top_level_conductor_run_artifact, "top_level_conductor_run_artifact")

    continuation_result: dict[str, Any] | None = None
    if root.get("continuation_result") is not None:
        continuation_result = _require_dict(root.get("continuation_result"), field="continuation_result")
    roadmap_two_step: dict[str, Any] | None = None
    raw_roadmap = root.get("roadmap_two_step_artifact")
    if raw_roadmap is not None:
        roadmap_two_step = _require_dict(raw_roadmap, field="roadmap_two_step_artifact")
        validate_artifact(roadmap_two_step, "roadmap_two_step_artifact")
    elif continuation_result is not None and isinstance(continuation_result.get("roadmap_two_step"), dict):
        inline = _require_dict(continuation_result.get("roadmap_two_step"), field="continuation_result.roadmap_two_step")
        roadmap_id = inline.get("roadmap_id")
        steps = inline.get("steps")
        if isinstance(roadmap_id, str) and roadmap_id and isinstance(steps, list):
            roadmap_two_step = {
                "roadmap_id": roadmap_id,
                "steps": [
                    {"step_id": f"step_{index}", "description": str(item)}
                    for index, item in enumerate(steps[:2], start=1)
                    if isinstance(item, str) and item.strip()
                ],
            }

    artifact_paths = _require_dict(root.get("artifact_paths"), field="artifact_paths")
    closure_path = _require_non_empty_str(artifact_paths.get("closure_decision_artifact"), field="artifact_paths.closure_decision_artifact")
    tlc_path_value = artifact_paths.get("top_level_conductor_run_artifact")
    if top_level_conductor_run_artifact is not None:
        tlc_path = _require_non_empty_str(tlc_path_value, field="artifact_paths.top_level_conductor_run_artifact")
    else:
        tlc_path = "None"

    next_step_path = artifact_paths.get("next_step_prompt_artifact")
    if next_step_path is not None:
        next_step_path = _require_non_empty_str(next_step_path, field="artifact_paths.next_step_prompt_artifact")

    terminal_state = _resolve_terminal_state(
        continuation_result=continuation_result,
        top_level_conductor_run_artifact=top_level_conductor_run_artifact,
    )
    decision_type = _require_non_empty_str(closure_decision_artifact.get("decision_type"), field="closure_decision_artifact.decision_type")
    run_id = _resolve_run_id(
        continuation_result=continuation_result,
        closure_decision_artifact=closure_decision_artifact,
        top_level_conductor_run_artifact=top_level_conductor_run_artifact,
    )
    trace_refs = _build_trace_refs(
        closure_decision_artifact=closure_decision_artifact,
        top_level_conductor_run_artifact=top_level_conductor_run_artifact,
    )

    lines = [
        "## Spectrum Systems — Governed Run Result",
        "",
        f"**Terminal State:** {terminal_state}",
        "",
        f"**Decision Type:** {decision_type}",
        "",
        f"**Run ID:** {run_id}",
        "",
        "**Artifacts:**",
        f"- Closure Decision: {closure_path}",
        f"- TLC Run: {tlc_path}",
    ]

    if next_step_path is not None:
        lines.append(f"- Next Step Prompt: {next_step_path}")
    if roadmap_two_step is not None:
        lines.extend(
            [
                "",
                "**Roadmap Input:**",
                f"- Roadmap ID: {roadmap_two_step['roadmap_id']}",
            ]
        )
        step_descriptions: list[str] = []
        for step in roadmap_two_step.get("steps", []):
            if isinstance(step, dict):
                description = step.get("description")
                if isinstance(description, str) and description.strip():
                    step_descriptions.append(description.strip())
        if step_descriptions:
            for idx, description in enumerate(step_descriptions[:2], start=1):
                lines.append(f"- Step {idx}: {description}")

    lines.extend(
        [
            "",
            "**Trace:**",
        ]
    )
    for ref in trace_refs:
        lines.append(f"- {ref}")

    lines.extend(
        [
            "",
            "**Notes:**",
            "- This output is machine-generated and non-authoritative.",
            "- No action is taken by this system.",
        ]
    )
    return "\n".join(lines) + "\n"


__all__ = ["GithubPrFeedbackError", "build_pr_feedback_comment"]
