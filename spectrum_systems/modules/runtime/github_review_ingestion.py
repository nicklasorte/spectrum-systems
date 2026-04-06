"""Thin GitHub event ingestion adapter for governed review-triggered RIL structuring.

Role boundaries for this module:
- GitHub triggers only (event intake + guardrails).
- Ingestion adapter normalizes only (no semantic review adjudication).
- RIL modules structure only (signal/control/projection/consumer artifacts).
- No closure, continuation, repair, or merge decisions in this module.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from spectrum_systems.contracts import validate_artifact
from spectrum_systems.modules.runtime.review_consumer_wiring import build_review_consumer_outputs
from spectrum_systems.modules.runtime.review_parsing_engine import parse_review_to_signal
from spectrum_systems.modules.runtime.review_projection_adapter import build_review_projection_bundle
from spectrum_systems.modules.runtime.review_signal_classifier import classify_review_signal
from spectrum_systems.modules.runtime.review_signal_consumer import build_review_integration_packet
from spectrum_systems.utils.deterministic_id import deterministic_id

_COMMAND_MARKERS = ("/governed-next-step", "/run-ril")


class GithubReviewIngestionError(ValueError):
    """Raised when GitHub event payloads are malformed or unauthorized for ingestion."""


@dataclass(frozen=True)
class NormalizedReviewInput:
    """Deterministic normalized review intake model used to generate governed artifacts."""

    ingestion_id: str
    event_name: str
    pr_number: int
    review_source: str
    review_date: str
    run_mode: str
    review_body: str
    command_marker: str | None
    source_event_ref: str
    source_actor: str


def _require_mapping(payload: Any, *, field: str) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise GithubReviewIngestionError(f"{field} must be an object")
    return payload


def _require_non_empty_str(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise GithubReviewIngestionError(f"{field} must be a non-empty string")
    return value.strip()


def _require_pr_number(value: Any, *, field: str) -> int:
    if not isinstance(value, int) or value <= 0:
        raise GithubReviewIngestionError(f"{field} must be a positive integer")
    return value


def _extract_pr_number(event_name: str, payload: dict[str, Any], manual_pr_number: int | None) -> int:
    if event_name == "workflow_dispatch":
        if manual_pr_number is None:
            raise GithubReviewIngestionError("workflow_dispatch requires explicit pr_number input")
        return _require_pr_number(manual_pr_number, field="workflow_dispatch.pr_number")

    pr = _require_mapping(payload.get("pull_request"), field="pull_request")
    return _require_pr_number(pr.get("number"), field="pull_request.number")


def _extract_review_body(event_name: str, payload: dict[str, Any], review_source: str, run_mode: str) -> tuple[str, str | None, str]:
    if event_name == "pull_request_review":
        action = _require_non_empty_str(payload.get("action"), field="action")
        if action != "submitted":
            raise GithubReviewIngestionError("pull_request_review must use action=submitted")

        review = _require_mapping(payload.get("review"), field="review")
        body = _require_non_empty_str(review.get("body"), field="review.body")
        review_id = review.get("id")
        source_ref = f"pull_request_review:{review_id}" if review_id is not None else "pull_request_review:submitted"
        return body, None, source_ref

    if event_name == "issue_comment":
        issue = _require_mapping(payload.get("issue"), field="issue")
        if "pull_request" not in issue:
            raise GithubReviewIngestionError("issue_comment trigger is allowed only when comment belongs to a PR")

        comment = _require_mapping(payload.get("comment"), field="comment")
        body = _require_non_empty_str(comment.get("body"), field="comment.body")

        marker = next((candidate for candidate in _COMMAND_MARKERS if candidate in body), None)
        if marker is None:
            raise GithubReviewIngestionError("issue_comment requires a command marker (/governed-next-step or /run-ril)")

        comment_id = comment.get("id")
        source_ref = f"issue_comment:{comment_id}" if comment_id is not None else "issue_comment:command"
        return body, marker, source_ref

    if event_name == "workflow_dispatch":
        source_ref = f"workflow_dispatch:{review_source}:{run_mode}"
        body = (
            "Manual governed RIL trigger. "
            f"review_source={review_source}; run_mode={run_mode}; command=/run-ril"
        )
        return body, "/run-ril", source_ref

    raise GithubReviewIngestionError(f"unsupported event_name: {event_name}")


def build_governed_review_inputs(
    *,
    event_name: str,
    payload: dict[str, Any],
    review_source: str,
    run_mode: str,
    pr_number: int | None = None,
    emitted_at: str,
) -> NormalizedReviewInput:
    """Normalize supported GitHub events into deterministic governed review inputs."""
    normalized_event = _require_non_empty_str(event_name, field="event_name")
    normalized_source = _require_non_empty_str(review_source, field="review_source").lower().replace(" ", "_")
    normalized_run_mode = _require_non_empty_str(run_mode, field="run_mode").lower()
    if normalized_run_mode not in {"strict", "standard"}:
        raise GithubReviewIngestionError("run_mode must be one of: strict, standard")

    event_payload = _require_mapping(payload, field="payload")
    derived_pr_number = _extract_pr_number(normalized_event, event_payload, pr_number)
    review_body, command_marker, source_event_ref = _extract_review_body(
        normalized_event,
        event_payload,
        normalized_source,
        normalized_run_mode,
    )

    actor = "github-actions[bot]"
    sender = event_payload.get("sender")
    if isinstance(sender, dict):
        login = sender.get("login")
        if isinstance(login, str) and login.strip():
            actor = login.strip()

    review_date = _require_non_empty_str(emitted_at, field="emitted_at")[:10]
    seed = {
        "event_name": normalized_event,
        "pr_number": derived_pr_number,
        "review_source": normalized_source,
        "run_mode": normalized_run_mode,
        "source_event_ref": source_event_ref,
        "review_body": review_body,
        "review_date": review_date,
    }

    return NormalizedReviewInput(
        ingestion_id=deterministic_id(prefix="gri", namespace="github_review_ingestion", payload=seed),
        event_name=normalized_event,
        pr_number=derived_pr_number,
        review_source=normalized_source,
        review_date=review_date,
        run_mode=normalized_run_mode,
        review_body=review_body,
        command_marker=command_marker,
        source_event_ref=source_event_ref,
        source_actor=actor,
    )


def _build_review_markdown(normalized: NormalizedReviewInput) -> str:
    return "\n".join(
        [
            "---",
            f"module: {normalized.review_source}",
            f"review_date: {normalized.review_date}",
            "---",
            "# GitHub Governed Review Intake",
            "",
            "## Overall Assessment",
            "**Overall Verdict: CONDITIONAL PASS**",
            "",
            "## Source Context",
            f"- Event: {normalized.event_name}",
            f"- PR: #{normalized.pr_number}",
            f"- Source Ref: {normalized.source_event_ref}",
            f"- Actor: {normalized.source_actor}",
            "",
            "## Trigger Body",
            normalized.review_body,
            "",
        ]
    )


def _build_action_tracker_markdown(normalized: NormalizedReviewInput) -> str:
    body_excerpt = normalized.review_body.replace("|", "/").replace("\n", " ").strip()
    if not body_excerpt:
        body_excerpt = "No body supplied"
    if len(body_excerpt) > 180:
        body_excerpt = body_excerpt[:177] + "..."

    command_note = normalized.command_marker or "(none)"

    return "\n".join(
        [
            "# Action Tracker",
            "",
            "## Critical Items",
            "| ID | Risk | Severity | Recommended Action | Status | Notes |",
            "| --- | --- | --- | --- | --- | --- |",
            "| CR-1 | Ensure trigger guardrails remain fail-closed | Critical | Preserve event/command/pr guardrails for governed ingestion | Open | governance boundary |",
            "",
            "## High-Priority Items",
            "| ID | Risk | Severity | Recommended Action | Status | Notes |",
            "| --- | --- | --- | --- | --- | --- |",
            f"| HI-1 | Ingested trigger body must remain deterministic: {body_excerpt} | High | Keep deterministic normalization and pathing | Open | command={command_note} |",
            "",
            "## Medium-Priority Items",
            "| ID | Risk | Severity | Recommended Action | Status | Notes |",
            "| --- | --- | --- | --- | --- | --- |",
            "| MI-1 | Preserve RIL-only structuring boundary | Medium | Do not add closure/repair logic to ingestion | Open | role-boundary |",
            "",
            "## Blocking Items",
            "- CR-1 blocks governance bypass.",
            "",
        ]
    )


def _build_source_artifact(
    *,
    normalized: NormalizedReviewInput,
    repo: str,
    sha: str,
    emitted_at: str,
    run_id: str,
) -> dict[str, Any]:
    return {
        "artifact_type": "reviewer_comment_set",
        "artifact_class": "review",
        "artifact_id": normalized.ingestion_id.upper(),
        "artifact_version": "1.0.0",
        "schema_version": "1.0.0",
        "standards_version": "2026.03.0",
        "record_id": f"REC-{normalized.ingestion_id.upper()}",
        "run_id": f"run-{run_id}",
        "created_at": emitted_at,
        "created_by": {
            "name": "GitHub Review Trigger Pipeline",
            "role": "review-ingestion",
            "agent_type": "workflow",
        },
        "source_repo": repo,
        "source_repo_version": sha,
        "working_paper_id": f"WKP-PR-{normalized.pr_number}",
        "working_paper_revision": "rev1",
        "comment_set_id": f"CSET-{normalized.ingestion_id.upper()}",
        "comments": [
            {
                "comment_id": "CMT-001",
                "text": normalized.review_body,
                "severity": "major",
                "priority": "high",
                "location": {
                    "section_id": "SEC-GITHUB-TRIGGER",
                    "reference": normalized.source_event_ref,
                },
                "status": "new",
                "proposed_disposition": "Route through governed RIL structuring pipeline.",
                "provenance_id": "PRV-CMT-001",
            }
        ],
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def ingest_github_review_event(
    *,
    event_name: str,
    payload: dict[str, Any],
    output_root: Path,
    review_source: str,
    run_mode: str,
    emitted_at: str,
    repo: str,
    sha: str,
    run_id: str,
    pr_number: int | None = None,
) -> dict[str, Any]:
    """Ingest GitHub event, generate governed artifacts, and run the full deterministic RIL stack."""
    normalized = build_governed_review_inputs(
        event_name=event_name,
        payload=payload,
        review_source=review_source,
        run_mode=run_mode,
        pr_number=pr_number,
        emitted_at=emitted_at,
    )

    artifact_dir = output_root / f"pr-{normalized.pr_number}" / normalized.ingestion_id
    artifact_dir.mkdir(parents=True, exist_ok=True)

    review_path = artifact_dir / "review.md"
    action_tracker_path = artifact_dir / "action_tracker.md"
    review_path.write_text(_build_review_markdown(normalized), encoding="utf-8")
    action_tracker_path.write_text(_build_action_tracker_markdown(normalized), encoding="utf-8")

    source_artifact = _build_source_artifact(
        normalized=normalized,
        repo=repo,
        sha=sha,
        emitted_at=emitted_at,
        run_id=run_id,
    )
    validate_artifact(source_artifact, "reviewer_comment_set")
    source_artifact_path = artifact_dir / "normalized_review_source_artifact.json"
    _write_json(source_artifact_path, source_artifact)

    review_signal = parse_review_to_signal(review_path=review_path, action_tracker_path=action_tracker_path)
    validate_artifact(review_signal, "review_signal_artifact")

    review_control_signal = classify_review_signal(review_signal)
    validate_artifact(review_control_signal, "review_control_signal_artifact")

    integration_packet = build_review_integration_packet(review_control_signal)
    validate_artifact(integration_packet, "review_integration_packet_artifact")

    projection_bundle = build_review_projection_bundle(integration_packet)
    validate_artifact(projection_bundle, "review_projection_bundle_artifact")

    consumer_output_bundle = build_review_consumer_outputs(
        projection_bundle,
        projection_bundle["roadmap_projection"],
        projection_bundle["control_loop_projection"],
        projection_bundle["readiness_projection"],
    )
    validate_artifact(consumer_output_bundle, "review_consumer_output_bundle_artifact")

    artifact_payloads: list[tuple[str, dict[str, Any]]] = [
        ("review_signal_artifact.json", review_signal),
        ("review_control_signal_artifact.json", review_control_signal),
        ("review_integration_packet_artifact.json", integration_packet),
        ("review_projection_bundle_artifact.json", projection_bundle),
        ("review_consumer_output_bundle_artifact.json", consumer_output_bundle),
    ]
    for filename, artifact in artifact_payloads:
        _write_json(artifact_dir / filename, artifact)

    artifact_paths = {
        "normalized_review_source_artifact": str(source_artifact_path),
        "review_markdown": str(review_path),
        "action_tracker_markdown": str(action_tracker_path),
        "review_signal_artifact": str(artifact_dir / "review_signal_artifact.json"),
        "review_control_signal_artifact": str(artifact_dir / "review_control_signal_artifact.json"),
        "review_integration_packet_artifact": str(artifact_dir / "review_integration_packet_artifact.json"),
        "review_projection_bundle_artifact": str(artifact_dir / "review_projection_bundle_artifact.json"),
        "review_consumer_output_bundle_artifact": str(artifact_dir / "review_consumer_output_bundle_artifact.json"),
    }

    summary = {
        "ingestion_id": normalized.ingestion_id,
        "status": "success",
        "event_name": normalized.event_name,
        "pr_number": normalized.pr_number,
        "review_source": normalized.review_source,
        "run_mode": normalized.run_mode,
        "source_event_ref": normalized.source_event_ref,
        "artifact_dir": str(artifact_dir),
        "artifact_paths": artifact_paths,
        "artifacts_produced": sorted(artifact_paths.keys()),
        "guardrails": {
            "github_triggers_only": True,
            "adapter_normalization_only": True,
            "ril_structuring_only": True,
            "closure_or_repair_logic_invoked": False,
        },
    }
    _write_json(artifact_dir / "ingestion_summary.json", summary)
    return summary


def _default_emitted_at() -> str:
    return datetime.now(tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run GitHub review ingestion and deterministic RIL pipeline")
    parser.add_argument("--event-name", required=True)
    parser.add_argument("--event-path", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--review-source", required=True)
    parser.add_argument("--run-mode", required=True)
    parser.add_argument("--repo", default="unknown/repo")
    parser.add_argument("--sha", default="unknown")
    parser.add_argument("--run-id", default="local")
    parser.add_argument("--pr-number", type=int, default=None)
    parser.add_argument("--emitted-at", default=_default_emitted_at())
    args = parser.parse_args(argv)

    payload = json.loads(Path(args.event_path).read_text(encoding="utf-8"))
    summary = ingest_github_review_event(
        event_name=args.event_name,
        payload=payload,
        output_root=Path(args.output_root),
        review_source=args.review_source,
        run_mode=args.run_mode,
        emitted_at=args.emitted_at,
        repo=args.repo,
        sha=args.sha,
        run_id=args.run_id,
        pr_number=args.pr_number,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
