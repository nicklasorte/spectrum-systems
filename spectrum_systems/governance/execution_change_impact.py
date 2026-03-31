"""Deterministic fail-closed execution change impact analysis for governed PQX paths."""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from spectrum_systems.contracts import validate_artifact

REPO_ROOT = Path(__file__).resolve().parents[2]
ANALYZER_VERSION = "1.0.0"
RULE_SET = "execution-change-impact-g14"


class ExecutionChangeImpactAnalysisError(ValueError):
    """Raised when execution impact analysis cannot be completed deterministically."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _git_exists(repo_root: Path, ref: str, relative_path: str) -> bool:
    proc = subprocess.run(
        ["git", "-C", str(repo_root), "cat-file", "-e", f"{ref}:{relative_path}"],
        check=False,
        capture_output=True,
        text=True,
    )
    return proc.returncode == 0


def _classify_surface(path: str) -> tuple[str, list[str], list[str], bool, bool, str | None]:
    surfaces: set[str] = set()
    reason_codes: set[str] = set()
    review_required = False
    eval_required = False
    blocking_reason = None

    if path.startswith("contracts/"):
        surfaces.add("contract")
        reason_codes.add("contract_surface_changed")
    if path.startswith("spectrum_systems/orchestration/"):
        surfaces.update({"orchestration", "control"})
        reason_codes.add("runtime_orchestration_or_pqx_change")
        review_required = True
        eval_required = True
    if path.startswith("spectrum_systems/modules/runtime/"):
        surfaces.update({"runtime", "control"})
        reason_codes.add("runtime_orchestration_or_pqx_change")
        review_required = True
        eval_required = True
        if "pqx" in path.lower():
            surfaces.add("pqx")
    if path.startswith("scripts/"):
        lowered = path.lower()
        if "pqx" in lowered or "control" in lowered or "orchestration" in lowered or "execution" in lowered:
            surfaces.add("control")
            reason_codes.add("governed_control_script_changed")
            review_required = True
            eval_required = True
    if path.startswith("docs/"):
        governance_docs = {
            "docs/architecture/autonomous_execution_loop.md",
            "docs/architecture/system_strategy.md",
            "docs/governance/contract-impact-gate.md",
            "docs/governance/execution-change-impact-gate.md",
        }
        if path in governance_docs:
            surfaces.add("docs_governance")
            reason_codes.add("governance_docs_changed")
            review_required = True

    critical_test_paths = {
        "tests/test_pqx_slice_runner.py",
        "tests/test_execution_change_impact_analysis.py",
        "tests/test_contracts.py",
        "tests/test_contract_enforcement.py",
    }
    if path in critical_test_paths:
        surfaces.add("tests_critical")
        reason_codes.add("critical_tests_touched")
        eval_required = True

    if not surfaces and (path.startswith("spectrum_systems/") or path.startswith("scripts/") or path.startswith("docs/")):
        surfaces.add("unknown")
        reason_codes.add("unclassified_governed_candidate")
        blocking_reason = "changed path could not be confidently classified in governed surfaces"

    if not surfaces:
        reason_codes.add("general_non_governed_path")

    sensitivity = "low"
    if "unknown" in surfaces:
        sensitivity = "critical"
    elif any(surface in surfaces for surface in ("orchestration", "runtime", "control", "pqx")):
        sensitivity = "critical"
    elif any(surface in surfaces for surface in ("contract", "docs_governance", "certification", "review", "tests_critical")):
        sensitivity = "high"
    elif surfaces:
        sensitivity = "moderate"

    return sensitivity, sorted(surfaces), sorted(reason_codes), review_required, eval_required, blocking_reason


def _max_sensitivity(values: list[str]) -> str:
    order = {"low": 0, "moderate": 1, "high": 2, "critical": 3}
    return max(values, key=lambda item: order[item])


def _change_type(path: str, exists_in_baseline: bool, exists_in_worktree: bool) -> str:
    if exists_in_worktree and not exists_in_baseline:
        return "added"
    if exists_in_baseline and not exists_in_worktree:
        return "deleted"
    if exists_in_baseline and exists_in_worktree:
        return "modified"
    return "unknown"


def analyze_execution_change_impact(
    *,
    repo_root: Path,
    changed_paths: list[str],
    baseline_ref: str = "HEAD",
    generated_at: str | None = None,
    provided_reviews: list[str] | None = None,
    provided_eval_artifacts: list[str] | None = None,
) -> dict[str, Any]:
    if not changed_paths:
        raise ExecutionChangeImpactAnalysisError("at least one changed path is required")

    normalized_paths = sorted(set(path.strip() for path in changed_paths if path and path.strip()))
    if not normalized_paths:
        raise ExecutionChangeImpactAnalysisError("at least one non-empty changed path is required")

    review_inputs = sorted(set(provided_reviews or []))
    eval_inputs = sorted(set(provided_eval_artifacts or []))

    assessments: list[dict[str, Any]] = []
    touched_surfaces: set[str] = set()
    rationale: list[str] = []
    required_reviews: set[str] = set()
    required_eval_artifacts: set[str] = set()
    required_followup_actions: set[str] = set()
    risk_classification = "safe"
    blocking = False
    indeterminate = False

    for path in normalized_paths:
        exists_in_baseline = _git_exists(repo_root, baseline_ref, path)
        exists_in_worktree = (repo_root / path).exists()
        change_type = _change_type(path, exists_in_baseline, exists_in_worktree)

        sensitivity, governed_surfaces, reason_codes, review_required, eval_required, blocking_reason = _classify_surface(path)
        touched_surfaces.update(surface for surface in governed_surfaces if surface != "unknown")

        if "unknown" in governed_surfaces:
            indeterminate = True
            blocking = True
            risk_classification = "indeterminate"
            required_followup_actions.add("classify_unknown_governed_surface")
            rationale.append(f"{path}: unclassified governed candidate path triggered fail-closed indeterminate block")

        if review_required:
            required_reviews.add("runtime-governance-review")
        if eval_required:
            required_eval_artifacts.update({"regression_result", "control_loop_certification_pack"})

        assessments.append(
            {
                "path": path,
                "exists_in_baseline": exists_in_baseline,
                "exists_in_worktree": exists_in_worktree,
                "change_type": change_type,
                "sensitivity_class": sensitivity,
                "governed_surface_types": governed_surfaces or ["unknown"],
                "impact_reason_codes": reason_codes,
                "review_required": review_required,
                "eval_required": eval_required,
                "blocking_reason": blocking_reason,
            }
        )

    critical_code_touched = any(
        any(surface in row["governed_surface_types"] for surface in ("runtime", "orchestration", "control", "pqx"))
        for row in assessments
    )
    critical_tests_touched = any("tests_critical" in row["governed_surface_types"] for row in assessments)

    if not indeterminate:
        highest = _max_sensitivity([row["sensitivity_class"] for row in assessments])

        if required_reviews and not review_inputs:
            blocking = True
            risk_classification = "blocking"
            required_followup_actions.add("attach_required_reviews")
            rationale.append("Critical governed runtime/control paths changed without provided review evidence")
            for row in assessments:
                if row["review_required"] and not row["blocking_reason"]:
                    row["impact_reason_codes"].append("review_evidence_missing")
                    row["impact_reason_codes"] = sorted(set(row["impact_reason_codes"]))
                    row["blocking_reason"] = "critical governed surface touched without mandatory review evidence"

        if required_eval_artifacts and not eval_inputs:
            blocking = True
            risk_classification = "blocking"
            required_followup_actions.add("attach_required_eval_artifacts")
            rationale.append("Critical governed runtime/control paths changed without provided evaluation artifacts")
            for row in assessments:
                if row["eval_required"] and not row["blocking_reason"]:
                    row["impact_reason_codes"].append("eval_evidence_missing")
                    row["impact_reason_codes"] = sorted(set(row["impact_reason_codes"]))
                    row["blocking_reason"] = "critical governed surface touched without mandatory evaluation evidence"

        if critical_code_touched and not critical_tests_touched:
            if risk_classification == "safe":
                risk_classification = "high_risk"
            blocking = True
            required_followup_actions.add("add_or_update_critical_tests")
            rationale.append("Critical governed code changed without simultaneous critical test updates")
            for row in assessments:
                if row["sensitivity_class"] == "critical" and not row["blocking_reason"]:
                    row["impact_reason_codes"].append("critical_test_coverage_unverified")
                    row["impact_reason_codes"] = sorted(set(row["impact_reason_codes"]))
                    row["blocking_reason"] = "critical governed code changed without critical test evidence"

        if any("docs_governance" in row["governed_surface_types"] for row in assessments) and risk_classification == "safe":
            risk_classification = "cautionary"
            rationale.append("Governance semantics documentation changed; requires cautionary handling")

        if risk_classification == "safe" and highest in {"high", "critical"}:
            risk_classification = "high_risk"
        elif risk_classification == "safe" and highest == "moderate":
            risk_classification = "cautionary"

    highest_sensitivity = _max_sensitivity([row["sensitivity_class"] for row in assessments])
    if not rationale:
        rationale.append("Changed files stayed outside governed execution/control/review/certification surfaces")

    safe_to_execute = (not blocking) and (not indeterminate) and risk_classification == "safe"

    identity = {
        "baseline_ref": baseline_ref,
        "changed_paths": normalized_paths,
        "provided_reviews": review_inputs,
        "provided_eval_artifacts": eval_inputs,
    }
    impact_id = hashlib.sha256(json.dumps(identity, sort_keys=True).encode("utf-8")).hexdigest()

    artifact = {
        "artifact_type": "execution_change_impact_artifact",
        "schema_version": "1.0.0",
        "impact_id": impact_id,
        "generated_at": generated_at or _utc_now(),
        "baseline_ref": baseline_ref,
        "changed_paths": normalized_paths,
        "analyzed_paths": normalized_paths,
        "path_assessments": assessments,
        "touched_sensitive_surfaces": sorted(touched_surfaces),
        "highest_sensitivity": highest_sensitivity,
        "risk_classification": risk_classification,
        "blocking": blocking,
        "safe_to_execute": safe_to_execute,
        "indeterminate": indeterminate,
        "required_reviews": sorted(required_reviews),
        "required_eval_artifacts": sorted(required_eval_artifacts),
        "required_followup_actions": sorted(required_followup_actions),
        "rationale": sorted(set(rationale)),
        "provenance": {
            "analyzer_version": ANALYZER_VERSION,
            "standards_manifest_path": "contracts/standards-manifest.json",
            "rule_set": RULE_SET,
            "deterministic": True,
        },
    }

    validate_artifact(artifact, "execution_change_impact_artifact")
    return artifact


def write_execution_change_impact_artifact(artifact: dict[str, Any], output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    return output_path
