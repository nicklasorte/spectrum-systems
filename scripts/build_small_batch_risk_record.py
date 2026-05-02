#!/usr/bin/env python3
"""SMALL-BATCH-RISK-01 small-batch risk record builder.

Emits an observation-only ``small_batch_risk_record`` artifact at
``outputs/small_batch_risk/small_batch_risk_record.json`` describing
the breadth of governed surfaces touched by a PR diff. The builder
classifies changed paths into surface classes, counts touches per
governed surface, and surfaces an observation-only ``risk_level`` and
``split_recommendation`` along with ``split_findings`` and
``recommended_batches``.

Authority scope: observation_only. The artifact emits risk
observations and split findings only. It does not block PRs and does
not gate any upstream readiness check. Canonical ownership of
admission, execution closure, eval evidence, policy/scope,
continuation/closure, and final-gate signal remains with the systems
declared in ``docs/architecture/system_registry.md``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.contracts import validate_artifact  # noqa: E402
from spectrum_systems.modules.runtime.changed_path_resolution import (  # noqa: E402
    resolve_changed_paths,
)

DEFAULT_OUTPUT_REL_PATH = "outputs/small_batch_risk/small_batch_risk_record.json"

# Surface class names (must match the schema enum).
SURFACE_CLASSES: tuple[str, ...] = (
    "contracts_schemas",
    "contracts_examples",
    "standards_manifest",
    "runtime",
    "scripts",
    "tests",
    "docs_reviews",
    "docs_review_actions",
    "docs_governance",
    "generated_artifacts",
    "github_workflows",
    "dashboard",
    "other",
)

_DASHBOARD_PATH_PREFIXES: tuple[str, ...] = (
    "apps/dashboard-3ls/",
    "artifacts/dashboard_metrics/",
    "artifacts/dashboard_cases/",
    "dashboard/",
)

_GENERATED_PATH_PREFIXES: tuple[str, ...] = (
    "artifacts/tls/",
    "artifacts/dashboard_",
    "artifacts/system_dependency_priority_report.json",
    "governance/reports/",
    "ecosystem/",
    "artifacts/",
)


def _utc_now_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _stable_record_id(*, base_ref: str, head_ref: str, created_at: str) -> str:
    raw = f"{base_ref}|{head_ref}|{created_at}".encode("utf-8")
    return "sbr-" + hashlib.sha256(raw).hexdigest()[:16]


def classify_surface(path: str) -> str:
    """Classify a single changed path into a surface class.

    Returns one of the surface class names from ``SURFACE_CLASSES`` or
    ``"other"`` for paths that do not match any specific surface.
    """
    if not path or not isinstance(path, str):
        return "other"

    # Dashboard takes priority over generated artifacts because
    # ``artifacts/dashboard_*`` would otherwise be classified as a
    # generated artifact.
    for prefix in _DASHBOARD_PATH_PREFIXES:
        if path.startswith(prefix):
            return "dashboard"
    if path == "apps/dashboard-3ls/app/page.tsx":
        return "dashboard"

    if path == "contracts/standards-manifest.json":
        return "standards_manifest"
    if path.startswith("contracts/schemas/"):
        return "contracts_schemas"
    if path.startswith("contracts/examples/"):
        return "contracts_examples"

    if path.startswith("spectrum_systems/"):
        return "runtime"

    if path.startswith("scripts/"):
        return "scripts"

    if path.startswith("tests/"):
        return "tests"

    if path.startswith("docs/reviews/"):
        return "docs_reviews"
    if path.startswith("docs/review-actions/"):
        return "docs_review_actions"
    if path.startswith("docs/governance/"):
        return "docs_governance"

    if path.startswith(".github/workflows/"):
        return "github_workflows"

    for prefix in _GENERATED_PATH_PREFIXES:
        if path.startswith(prefix):
            return "generated_artifacts"

    return "other"


def _surface_class_known(surface_class: str) -> bool:
    return surface_class in SURFACE_CLASSES


def _classify_all(changed_paths: list[str]) -> tuple[dict[str, list[str]], bool]:
    """Group changed paths by surface class.

    Returns ``(by_class, classification_failed)``. ``classification_failed``
    is True when any path returns a class name that is not a known surface
    class enum value (i.e., the classifier produced an unknown).
    """
    by_class: dict[str, list[str]] = {}
    classification_failed = False
    for path in changed_paths:
        cls = classify_surface(path)
        if not _surface_class_known(cls):
            classification_failed = True
            cls = "other"
        by_class.setdefault(cls, []).append(path)
    return by_class, classification_failed


def _compute_risk_level(
    *,
    by_class: dict[str, list[str]],
    classification_failed: bool,
    schema_touched: bool,
    runtime_touched: bool,
    generated_touched: bool,
    workflow_touched: bool,
) -> tuple[str, list[str]]:
    """Return ``(risk_level, reason_codes)``.

    Thresholds are deliberately simple and testable:
      - unknown : classification failed for at least one path
      - very_high : 5+ surface classes, or schema+runtime+generated+workflow
      - high     : 3 or 4 surface classes
      - medium   : exactly 2 surface classes
      - low      : 1 surface class with a small file count (<= 3)
      - medium   : 1 surface class with > 3 files (not "low" because the
        single class still represents a wider batch)
    """
    reason_codes: list[str] = []

    if classification_failed:
        reason_codes.append("path_classification_failed")
        return "unknown", reason_codes

    distinct_classes = sorted(by_class.keys())
    distinct_count = len(distinct_classes)

    risky_combo = (
        schema_touched and runtime_touched and generated_touched and workflow_touched
    )
    if risky_combo:
        reason_codes.append("schema_runtime_generated_workflow_combination")

    if distinct_count >= 5 or risky_combo:
        if distinct_count >= 5 and "many_governed_surface_classes" not in reason_codes:
            reason_codes.append("many_governed_surface_classes")
        return "very_high", reason_codes

    if distinct_count >= 3:
        reason_codes.append("multiple_governed_surface_classes")
        return "high", reason_codes

    if distinct_count == 2:
        reason_codes.append("two_governed_surface_classes")
        return "medium", reason_codes

    if distinct_count == 1:
        only_class = distinct_classes[0]
        file_count = len(by_class[only_class])
        if file_count <= 3:
            return "low", reason_codes
        reason_codes.append("single_class_high_file_count")
        return "medium", reason_codes

    # No changed paths at all.
    reason_codes.append("no_changed_paths")
    return "low", reason_codes


def _compute_split_recommendation(
    *,
    risk_level: str,
    by_class: dict[str, list[str]],
) -> tuple[str, list[dict[str, Any]], list[dict[str, Any]]]:
    """Return ``(split_recommendation, split_findings, recommended_batches)``.

    For ``high`` and ``very_high`` risk levels, this populates split
    findings and recommended batches grouping changed paths by surface
    class. Recommendations are observation-only.
    """
    if risk_level == "unknown":
        return "human_review_required", [], []

    if risk_level in {"low", "medium"}:
        return "keep_together", [], []

    findings: list[dict[str, Any]] = []
    if risk_level == "high":
        findings.append(
            {
                "finding": (
                    "PR touches 3 or more governed surface classes; sequential "
                    "guard failures are more likely than for a narrower batch"
                ),
                "evidence_paths": sorted(
                    p for paths in by_class.values() for p in paths
                ),
                "observation_only": True,
                "rationale": (
                    "broad governed-surface batches increase failure surface "
                    "across authority, contract, selection, generated freshness, "
                    "workflow, and test guards"
                ),
            }
        )
    elif risk_level == "very_high":
        findings.append(
            {
                "finding": (
                    "PR touches 5 or more governed surface classes, or combines "
                    "schema + runtime + generated + workflow surfaces in one batch"
                ),
                "evidence_paths": sorted(
                    p for paths in by_class.values() for p in paths
                ),
                "observation_only": True,
                "rationale": (
                    "this combination historically increases sequential failures "
                    "across guard surfaces and lengthens repair cycles"
                ),
            }
        )

    # Build recommended batches by grouping per surface class.
    recommended: list[dict[str, Any]] = []
    for cls in SURFACE_CLASSES:
        paths = sorted(by_class.get(cls, []))
        if not paths:
            continue
        recommended.append(
            {
                "batch_name": cls,
                "paths": paths,
                "observation_only": True,
                "rationale": (
                    f"group changes for surface class '{cls}' into a narrower "
                    "batch so guards run against a smaller surface"
                ),
            }
        )

    if risk_level == "high":
        return "consider_split", findings, recommended
    return "split_recommended", findings, recommended


def build_small_batch_risk_record(
    *,
    base_ref: str,
    head_ref: str,
    changed_paths: list[str],
    record_id: str,
    created_at: str,
) -> dict[str, Any]:
    """Build a ``small_batch_risk_record`` dict from changed paths.

    Pure function (no filesystem I/O). The schema/example/manifest etc.
    touch counts are derived from the input ``changed_paths`` only.
    """
    paths_unique = sorted({p for p in changed_paths if isinstance(p, str) and p})
    by_class, classification_failed = _classify_all(paths_unique)

    schema_count = len(by_class.get("contracts_schemas", []))
    example_count = len(by_class.get("contracts_examples", []))
    manifest_count = len(by_class.get("standards_manifest", []))
    runtime_count = len(by_class.get("runtime", []))
    script_count = len(by_class.get("scripts", []))
    test_count = len(by_class.get("tests", []))
    docs_count = (
        len(by_class.get("docs_reviews", []))
        + len(by_class.get("docs_review_actions", []))
        + len(by_class.get("docs_governance", []))
    )
    workflow_count = len(by_class.get("github_workflows", []))
    dashboard_count = len(by_class.get("dashboard", []))
    generated_count = len(by_class.get("generated_artifacts", []))

    schema_touched = schema_count > 0
    runtime_touched = runtime_count > 0
    generated_touched = generated_count > 0
    workflow_touched = workflow_count > 0
    dashboard_touched = dashboard_count > 0
    contract_surface_touched = (
        schema_count > 0 or example_count > 0 or manifest_count > 0
    )

    # Governed surface classes are all surface classes other than "other".
    governed_classes = sorted(
        cls for cls in by_class.keys() if cls != "other"
    )
    governed_count = sum(
        len(by_class[cls]) for cls in governed_classes
    )

    risk_level, reason_codes = _compute_risk_level(
        by_class=by_class,
        classification_failed=classification_failed,
        schema_touched=schema_touched,
        runtime_touched=runtime_touched,
        generated_touched=generated_touched,
        workflow_touched=workflow_touched,
    )
    split_recommendation, split_findings, recommended_batches = (
        _compute_split_recommendation(
            risk_level=risk_level,
            by_class=by_class,
        )
    )

    return {
        "artifact_type": "small_batch_risk_record",
        "schema_version": "1.0.0",
        "record_id": record_id,
        "created_at": created_at,
        "base_ref": base_ref,
        "head_ref": head_ref,
        "changed_file_count": len(paths_unique),
        "changed_paths": paths_unique,
        "governed_surface_classes": governed_classes,
        "governed_surface_count": governed_count,
        "generated_artifact_touch_count": generated_count,
        "schema_touch_count": schema_count,
        "example_touch_count": example_count,
        "manifest_touch_count": manifest_count,
        "runtime_touch_count": runtime_count,
        "script_touch_count": script_count,
        "test_touch_count": test_count,
        "docs_touch_count": docs_count,
        "workflow_touch_count": workflow_count,
        "dashboard_touch_count": dashboard_count,
        "contract_surface_touched": contract_surface_touched,
        "generated_surface_touched": generated_touched,
        "workflow_surface_touched": workflow_touched,
        "dashboard_surface_touched": dashboard_touched,
        "risk_level": risk_level,
        "reason_codes": reason_codes,
        "split_recommendation": split_recommendation,
        "split_findings": split_findings,
        "recommended_batches": recommended_batches,
        "authority_scope": "observation_only",
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "SMALL-BATCH-RISK-01 small-batch risk record builder "
            "(observation-only)."
        ),
    )
    parser.add_argument("--base-ref", default="origin/main")
    parser.add_argument("--head-ref", default="HEAD")
    parser.add_argument("--output", default=DEFAULT_OUTPUT_REL_PATH)
    return parser.parse_args()


def _resolve_output_path(arg: str) -> Path:
    candidate = Path(arg)
    if candidate.is_absolute():
        return candidate.resolve()
    return (REPO_ROOT / candidate).resolve()


def _format_output_ref(output_path: Path) -> str:
    try:
        return str(output_path.relative_to(REPO_ROOT))
    except ValueError:
        return str(output_path)


def main() -> int:
    args = _parse_args()
    output_path = _resolve_output_path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    resolution = resolve_changed_paths(
        repo_root=REPO_ROOT,
        base_ref=args.base_ref,
        head_ref=args.head_ref,
    )
    changed_paths = list(resolution.changed_paths)

    created_at = _utc_now_iso()
    record_id = _stable_record_id(
        base_ref=args.base_ref,
        head_ref=args.head_ref,
        created_at=created_at,
    )
    record = build_small_batch_risk_record(
        base_ref=args.base_ref,
        head_ref=args.head_ref,
        changed_paths=changed_paths,
        record_id=record_id,
        created_at=created_at,
    )

    validate_artifact(record, "small_batch_risk_record")
    output_path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")

    summary = {
        "risk_level": record["risk_level"],
        "split_recommendation": record["split_recommendation"],
        "changed_file_count": record["changed_file_count"],
        "governed_surface_count": record["governed_surface_count"],
        "governed_surface_classes": record["governed_surface_classes"],
        "output": _format_output_ref(output_path),
    }
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
