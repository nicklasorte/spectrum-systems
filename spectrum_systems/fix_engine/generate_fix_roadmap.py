"""Generate deterministic fix roadmap artifacts from implementation reviews."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

from jsonschema import Draft202012Validator

from spectrum_systems.contracts import load_schema


def _normalize_text(value: str) -> str:
    return " ".join(value.lower().strip().split())


def _seam_key(paths: Iterable[str]) -> str:
    """Use first two path segments as deterministic shared-seam grouping key."""
    normalized: List[str] = []
    for raw in sorted(set(paths)):
        parts = [p for p in raw.split("/") if p]
        normalized.append("/".join(parts[:2]) if len(parts) >= 2 else raw)
    return "+".join(normalized) if normalized else "unscoped"


def _classification_from_severity(severity: str) -> str:
    sev = severity.lower()
    if sev in {"critical", "blocker"}:
        return "blocker"
    if sev in {"high", "medium"}:
        return "required_fix"
    return "optional_improvement"


def _severity_rank(severity: str) -> int:
    ranks = {"critical": 5, "blocker": 5, "high": 4, "medium": 3, "low": 2, "info": 1}
    return ranks.get(severity.lower(), 0)


def _dedupe_key(finding: Dict[str, Any]) -> str:
    fingerprint = finding.get("fingerprint")
    if isinstance(fingerprint, str) and fingerprint:
        return f"fp:{_normalize_text(fingerprint)}"
    title = _normalize_text(str(finding.get("title", "")))
    category = _normalize_text(str(finding.get("category", "")))
    paths = "|".join(sorted(set(str(p) for p in finding.get("affected_paths", []))))
    return f"title:{title}|category:{category}|paths:{paths}"


def _load_review(path: str) -> Dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    schema = load_schema("implementation_review_artifact")
    Draft202012Validator(schema).validate(payload)
    return payload


def _render_markdown(artifact: Dict[str, Any]) -> str:
    lines = [
        "# Fix Roadmap",
        "",
        f"Cycle: `{artifact['cycle_id']}`",
        "",
        "## Summary",
        f"- blocker: {artifact['summary']['blocker']}",
        f"- required_fix: {artifact['summary']['required_fix']}",
        f"- optional_improvement: {artifact['summary']['optional_improvement']}",
        f"- total_unique_findings: {artifact['summary']['total_unique_findings']}",
        "",
        "## Bundles",
    ]
    for bundle in artifact["bundles"]:
        lines.extend(
            [
                f"### {bundle['bundle_id']} ({bundle['classification']})",
                f"- rationale: {bundle['rationale']}",
                f"- target_seams: {', '.join(bundle['target_seams'])}",
            ]
        )
        for finding in bundle["findings"]:
            lines.append(
                f"- [{finding['finding_id']}] {finding['title']} ({finding['severity']}) — reviewers: {', '.join(finding['source_reviewers'])}"
            )
        lines.append("")
    return "\n".join(lines) + "\n"


def generate_fix_roadmap(
    *,
    cycle_id: str,
    review_artifact_paths: List[str],
    output_json_path: str,
    output_markdown_path: str,
    generated_at: str,
) -> Dict[str, Any]:
    """Merge, dedupe, classify, and bundle review findings deterministically."""
    if not review_artifact_paths:
        raise ValueError("review_artifact_paths must contain at least one artifact")

    merged: Dict[str, Dict[str, Any]] = {}
    source_paths = sorted(review_artifact_paths)

    for review_path in source_paths:
        review = _load_review(review_path)
        reviewer = str(review.get("reviewer"))
        for finding in review.get("findings", []):
            key = _dedupe_key(finding)
            item = merged.get(key)
            if item is None:
                merged[key] = {
                    "finding_id": finding.get("finding_id", key),
                    "title": finding.get("title", "untitled"),
                    "severity": finding.get("severity", "info"),
                    "category": finding.get("category", "docs"),
                    "affected_paths": sorted(set(finding.get("affected_paths", []))),
                    "source_reviewers": [reviewer],
                    "classification": _classification_from_severity(str(finding.get("severity", "info"))),
                }
            else:
                item["source_reviewers"] = sorted(set([*item["source_reviewers"], reviewer]))
                existing_severity = str(item.get("severity", "info"))
                new_severity = str(finding.get("severity", "info"))
                if _severity_rank(new_severity) > _severity_rank(existing_severity):
                    item["severity"] = new_severity
                    item["classification"] = _classification_from_severity(new_severity)

    grouped: Dict[Tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
    for item in sorted(merged.values(), key=lambda x: (x["classification"], x["title"], x["finding_id"])):
        seam = _seam_key(item["affected_paths"])
        grouped[(item["classification"], seam)].append(item)

    bundles: List[Dict[str, Any]] = []
    order = {"blocker": 0, "required_fix": 1, "optional_improvement": 2}
    for idx, ((classification, seam), findings) in enumerate(
        sorted(grouped.items(), key=lambda x: (order[x[0][0]], x[0][1]))
    ):
        bundles.append(
            {
                "bundle_id": f"bundle-{classification}-{idx + 1:03d}",
                "classification": classification,
                "rationale": (
                    "Grouped by shared repository seam and dependency proximity; "
                    "same seam implies minimum coherent PQX bundle with reduced cross-module churn."
                ),
                "target_seams": seam.split("+"),
                "findings": [{k:v for k,v in finding.items() if k != "classification"} for finding in findings],
            }
        )

    summary = {
        "blocker": sum(1 for v in merged.values() if v["classification"] == "blocker"),
        "required_fix": sum(1 for v in merged.values() if v["classification"] == "required_fix"),
        "optional_improvement": sum(1 for v in merged.values() if v["classification"] == "optional_improvement"),
        "total_unique_findings": len(merged),
    }

    artifact = {
        "artifact_id": f"fix-roadmap-{cycle_id}",
        "artifact_type": "fix_roadmap_artifact",
        "schema_version": "1.0.0",
        "cycle_id": cycle_id,
        "generated_at": generated_at,
        "source_review_paths": source_paths,
        "summary": summary,
        "bundles": bundles,
    }

    Draft202012Validator(load_schema("fix_roadmap_artifact")).validate(artifact)
    Path(output_json_path).write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    Path(output_markdown_path).write_text(_render_markdown(artifact), encoding="utf-8")
    return artifact
