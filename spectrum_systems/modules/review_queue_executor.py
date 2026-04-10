"""RQX-01 bounded review queue executor.

Consumes a strict `review_request_artifact`, inspects declared references,
emits structured review artifacts, and writes a markdown review artifact
under `docs/reviews/`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from spectrum_systems.contracts import load_schema

REVIEW_RESULT_FILE_SUFFIX = "_review_result_artifact.json"
MERGE_READINESS_FILE_SUFFIX = "_review_merge_readiness_artifact.json"
FIX_SLICE_FILE_SUFFIX = "_review_fix_slice_artifact.json"
OPERATOR_HANDOFF_FILE_SUFFIX = "_review_operator_handoff_artifact.json"


class ReviewQueueValidationError(ValueError):
    """Raised when an RQX artifact fails schema validation."""


def _validate(instance: dict[str, Any], schema_name: str) -> None:
    schema = load_schema(schema_name)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(instance), key=lambda error: str(error.path))
    if errors:
        raise ReviewQueueValidationError("; ".join(error.message for error in errors))


def validate_review_request_artifact(request_artifact: dict[str, Any]) -> None:
    _validate(request_artifact, "review_request_artifact")


def validate_review_result_artifact(result_artifact: dict[str, Any]) -> None:
    _validate(result_artifact, "review_result_artifact")


def validate_review_merge_readiness_artifact(merge_artifact: dict[str, Any]) -> None:
    _validate(merge_artifact, "review_merge_readiness_artifact")


def validate_review_fix_slice_artifact(fix_slice_artifact: dict[str, Any]) -> None:
    _validate(fix_slice_artifact, "review_fix_slice_artifact")


def validate_review_operator_handoff_artifact(handoff_artifact: dict[str, Any]) -> None:
    _validate(handoff_artifact, "review_operator_handoff_artifact")


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read_optional_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace").lower()


def _build_findings(request: dict[str, Any], repo_root: Path) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []

    for changed_file in request["changed_files"]:
        changed_path = repo_root / changed_file
        if not changed_path.exists():
            findings.append(
                {
                    "finding_id": f"F-{len(findings) + 1}",
                    "title": "Declared changed file is missing",
                    "severity": "blocker",
                    "evidence": [f"missing_file:{changed_file}"],
                    "why_it_matters": "Review scope cannot be trusted when declared changed files are not retrievable.",
                }
            )

    for validation_ref in request["validation_result_refs"]:
        validation_path = repo_root / validation_ref
        content = _read_optional_text(validation_path)
        if not validation_path.exists():
            findings.append(
                {
                    "finding_id": f"F-{len(findings) + 1}",
                    "title": "Validation reference is missing",
                    "severity": "high",
                    "evidence": [f"missing_validation_ref:{validation_ref}"],
                    "why_it_matters": "Merge readiness cannot be granted without retrievable validation evidence.",
                }
            )
            continue

        if any(token in content for token in ("\"status\": \"failed\"", "failure", "failed")):
            findings.append(
                {
                    "finding_id": f"F-{len(findings) + 1}",
                    "title": "Validation evidence contains failure signal",
                    "severity": "high",
                    "evidence": [validation_ref],
                    "why_it_matters": "Failing validation indicates the reviewed execution is not merge-ready.",
                }
            )

    if not findings:
        findings.append(
            {
                "finding_id": "F-1",
                "title": "No blocking signals detected in declared review inputs",
                "severity": "low",
                "evidence": [request["produced_artifact_refs"][0]],
                "why_it_matters": "A bounded review still records explicit evidence for replay and traceability.",
            }
        )

    return findings


def _verdict_for_findings(findings: list[dict[str, Any]]) -> str:
    severities = {finding["severity"] for finding in findings}
    if "blocker" in severities:
        return "not_safe_to_merge"
    if "high" in severities or "medium" in severities:
        return "fix_required"
    return "safe_to_merge"


def _required_follow_up(verdict: str, findings: list[dict[str, Any]]) -> list[str]:
    if verdict == "safe_to_merge":
        return []
    follow_up = [
        "Resolve findings and regenerate review_result_artifact before merge.",
    ]
    if verdict == "not_safe_to_merge":
        follow_up.append("Do not merge until blocker findings are closed with new validation evidence.")
    if any(f["severity"] == "high" for f in findings):
        follow_up.append("Address high-severity validation or evidence gaps.")
    return follow_up


def _deterministic_fix_slice_id(review_id: str, findings: list[dict[str, Any]]) -> str:
    finding_seed = "|".join(f"{finding['finding_id']}:{finding['severity']}:{finding['title']}" for finding in findings)
    digest = hashlib.sha256(f"{review_id}|{finding_seed}".encode("utf-8")).hexdigest()
    return f"rfs-{digest[:12]}"


def _build_fix_slice_artifact(
    request_artifact: dict[str, Any],
    result_artifact: dict[str, Any],
    *,
    emitted_at: str,
) -> dict[str, Any]:
    return {
        "artifact_type": "review_fix_slice_artifact",
        "artifact_version": "1.0.0",
        "schema_version": "1.0.0",
        "standards_version": "1.0.0",
        "fix_slice_id": _deterministic_fix_slice_id(request_artifact["review_id"], result_artifact["findings"]),
        "review_id": request_artifact["review_id"],
        "review_name": request_artifact["review_name"],
        "review_result_ref": f"review_result_artifact:{request_artifact['review_id']}",
        "source_review_request_ref": f"review_request_artifact:{request_artifact['review_id']}",
        "objective": "Resolve high/medium review findings in bounded scope and regenerate review artifacts for merge readiness re-check.",
        "fix_scope": "bounded_single_slice_remediation",
        "target_surface_refs": request_artifact["changed_files"],
        "validation_requirements": request_artifact["validation_result_refs"],
        "max_repair_attempts": 1,
        "provenance": {
            "emitted_by_system": "RQX",
            "emission_reason": "fix_required_verdict",
            "automatic_execution": "disabled",
        },
        "trace_linkage": {
            "run_id": request_artifact.get("run_id", "not_provided"),
            "batch_id": request_artifact.get("batch_id", "not_provided"),
        },
        "generated_at": emitted_at,
    }


def _render_markdown(result: dict[str, Any], generated_at: str, fix_slice_ref: str | None = None) -> str:
    findings_lines: list[str] = []
    for finding in result["findings"]:
        evidence = ", ".join(finding["evidence"])
        findings_lines.extend(
            [
                f"### {finding['finding_id']}: {finding['title']}",
                f"- Severity: {finding['severity']}",
                f"- Evidence: {evidence}",
                f"- Why it matters: {finding['why_it_matters']}",
                "",
            ]
        )

    follow_up = "\n".join(f"- {item}" for item in result["required_follow_up"]) or "- None"
    files = "\n".join(f"- {path}" for path in result["files_inspected"])

    fix_slice_section = (
        "\n## Bounded Fix Slice\n"
        f"- Emitted: yes\n- Fix Slice Artifact Ref: {fix_slice_ref}\n"
        if fix_slice_ref
        else ""
    )

    return (
        f"# {result['review_name']}\n\n"
        f"**Date:** {generated_at}\n"
        f"**Scope:** {result['scope']}\n"
        f"**Review Type:** {result['review_type']}\n"
        f"**Verdict:** {result['verdict']}\n\n"
        f"## Files Inspected\n{files}\n\n"
        f"## Findings\n"
        + "\n".join(findings_lines)
        + f"## Merge Decision\n{result['rationale']}\n\n"
        f"## Required Follow-Up\n{follow_up}\n"
        f"{fix_slice_section}"
    )


def _build_operator_handoff_artifact(
    request_artifact: dict[str, Any],
    result_artifact: dict[str, Any],
    *,
    emitted_at: str,
) -> dict[str, Any]:
    review_id = request_artifact["review_id"]
    unresolved_finding_refs = [
        f"review_result_artifact:{review_id}#{finding['finding_id']}"
        for finding in result_artifact["findings"]
        if isinstance(finding, dict) and isinstance(finding.get("finding_id"), str) and finding["finding_id"].strip()
    ]
    handoff = {
        "artifact_type": "review_operator_handoff_artifact",
        "artifact_version": "1.0.0",
        "schema_version": "1.0.0",
        "standards_version": "1.0.0",
        "handoff_id": f"roha:rqx:{review_id}",
        "review_id": review_id,
        "source_review_result_ref": f"review_result_artifact:{review_id}",
        "source_review_fix_execution_result_ref": f"review_fix_execution_result_artifact:rqx-review:{review_id}",
        "post_cycle_verdict": result_artifact["verdict"],
        "handoff_reason": "review_incomplete",
        "recommended_next_action": "manual_review_required",
        "blocking_conditions": ["review_verdict:not_safe_to_merge"],
        "unresolved_finding_refs": unresolved_finding_refs,
        "target_scope": request_artifact["scope"],
        "target_files": request_artifact["changed_files"],
        "target_surface_refs": request_artifact["produced_artifact_refs"],
        "future_fix_cycle_permitted": True,
        "provenance": {
            "emitted_by_system": "RQX",
            "loop_execution_mode": "single_bounded_cycle",
            "auto_reentry_triggered": False,
        },
        "trace_linkage": {
            "request_ref": f"review_fix_execution_request_artifact:rqx-review:{review_id}",
            "fix_slice_ref": f"review_fix_slice_artifact:none:{review_id}",
            "tpa_artifact_ref": f"tpa_slice_artifact:none:{review_id}",
            "pqx_execution_ref": None,
        },
        "emitted_at": emitted_at,
    }
    validate_review_operator_handoff_artifact(handoff)
    return handoff


def run_review_queue_executor(
    request_artifact: dict[str, Any],
    *,
    repo_root: Path,
    output_dir: Path,
    review_docs_dir: Path,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Run bounded RQX review execution and write artifacts."""
    validate_review_request_artifact(request_artifact)
    emitted_at = generated_at or _utc_now()

    findings = _build_findings(request_artifact, repo_root)
    verdict = _verdict_for_findings(findings)
    follow_up = _required_follow_up(verdict, findings)

    result_artifact: dict[str, Any] = {
        "artifact_type": "review_result_artifact",
        "artifact_version": "1.0.0",
        "schema_version": "1.0.0",
        "standards_version": "1.0.0",
        "review_id": request_artifact["review_id"],
        "review_name": request_artifact["review_name"],
        "review_type": request_artifact["review_type"],
        "scope": request_artifact["scope"],
        "files_inspected": request_artifact["changed_files"],
        "findings": findings,
        "verdict": verdict,
        "rationale": (
            "Blocker findings prevent merge readiness."
            if verdict == "not_safe_to_merge"
            else "Findings require remediation before merge readiness." if verdict == "fix_required"
            else "No blocker/high/medium findings were detected in the bounded review scope."
        ),
        "required_follow_up": follow_up,
        "source_review_request_ref": f"review_request_artifact:{request_artifact['review_id']}",
        "generated_at": emitted_at,
        "bounded_review": True,
        "automatic_fix_execution": "disabled",
    }
    if "run_id" in request_artifact:
        result_artifact["run_id"] = request_artifact["run_id"]
    if "batch_id" in request_artifact:
        result_artifact["batch_id"] = request_artifact["batch_id"]

    validate_review_result_artifact(result_artifact)

    merge_artifact = {
        "artifact_type": "review_merge_readiness_artifact",
        "artifact_version": "1.0.0",
        "schema_version": "1.0.0",
        "standards_version": "1.0.0",
        "review_id": request_artifact["review_id"],
        "review_name": request_artifact["review_name"],
        "review_result_ref": f"review_result_artifact:{request_artifact['review_id']}",
        "verdict": verdict,
        "readiness_signal": "review_safe" if verdict == "safe_to_merge" else ("review_fix_required" if verdict == "fix_required" else "review_not_safe"),
        "cde_decision_required": True,
        "rationale": result_artifact["rationale"],
        "required_follow_up": follow_up,
        "generated_at": emitted_at,
    }
    validate_review_merge_readiness_artifact(merge_artifact)
    fix_slice_artifact: dict[str, Any] | None = None
    if verdict == "fix_required":
        fix_slice_artifact = _build_fix_slice_artifact(
            request_artifact,
            result_artifact,
            emitted_at=emitted_at,
        )
        validate_review_fix_slice_artifact(fix_slice_artifact)

    output_dir.mkdir(parents=True, exist_ok=True)
    review_docs_dir.mkdir(parents=True, exist_ok=True)

    result_path = output_dir / f"{request_artifact['review_name']}{REVIEW_RESULT_FILE_SUFFIX}"
    merge_path = output_dir / f"{request_artifact['review_name']}{MERGE_READINESS_FILE_SUFFIX}"
    fix_slice_path = output_dir / f"{request_artifact['review_name']}{FIX_SLICE_FILE_SUFFIX}"
    handoff_path = output_dir / f"{request_artifact['review_name']}{OPERATOR_HANDOFF_FILE_SUFFIX}"
    markdown_path = review_docs_dir / f"{request_artifact['review_name']}_review.md"

    result_path.write_text(json.dumps(result_artifact, indent=2) + "\n", encoding="utf-8")
    merge_path.write_text(json.dumps(merge_artifact, indent=2) + "\n", encoding="utf-8")
    if fix_slice_artifact is not None:
        fix_slice_path.write_text(json.dumps(fix_slice_artifact, indent=2) + "\n", encoding="utf-8")
    handoff_artifact: dict[str, Any] | None = None
    if verdict == "not_safe_to_merge":
        handoff_artifact = _build_operator_handoff_artifact(
            request_artifact,
            result_artifact,
            emitted_at=emitted_at,
        )
        handoff_path.write_text(json.dumps(handoff_artifact, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(
        _render_markdown(
            result_artifact,
            emitted_at,
            fix_slice_ref=f"review_fix_slice_artifact:{fix_slice_artifact['fix_slice_id']}"
            if fix_slice_artifact
            else None,
        ),
        encoding="utf-8",
    )

    response = {
        "review_result_artifact": result_artifact,
        "review_merge_readiness_artifact": merge_artifact,
        "review_result_artifact_path": str(result_path),
        "review_merge_readiness_artifact_path": str(merge_path),
        "markdown_review_path": str(markdown_path),
    }
    if fix_slice_artifact is not None:
        response["review_fix_slice_artifact"] = fix_slice_artifact
        response["review_fix_slice_artifact_path"] = str(fix_slice_path)
    if handoff_artifact is not None:
        response["review_operator_handoff_artifact"] = handoff_artifact
        response["review_operator_handoff_artifact_path"] = str(handoff_path)
    return response


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the bounded RQX review queue executor.")
    parser.add_argument("--request", required=True, help="Path to review_request_artifact JSON file.")
    parser.add_argument(
        "--output-dir",
        default="artifacts/reviews",
        help="Directory where structured review artifacts are emitted.",
    )
    parser.add_argument(
        "--review-docs-dir",
        default="docs/reviews",
        help="Directory where markdown review artifacts are written.",
    )
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Repository root used for retrieving declared input refs.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    request_path = Path(args.request)
    request = json.loads(request_path.read_text(encoding="utf-8"))
    result = run_review_queue_executor(
        request,
        repo_root=Path(args.repo_root),
        output_dir=Path(args.output_dir),
        review_docs_dir=Path(args.review_docs_dir),
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
