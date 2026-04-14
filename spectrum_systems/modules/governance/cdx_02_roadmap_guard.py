"""Deterministic CDX-02 roadmap ownership and authority guard."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from spectrum_systems.modules.governance.system_registry_guard import parse_system_registry

EXPECTED_AUTHORITY_SOURCE = "docs/architecture/system_registry.md"
ALLOWED_TRUE_NEW_OWNERS = {"CRS", "MGV"}


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def evaluate_cdx_02_roadmap_guard(*, repo_root: Path) -> dict[str, Any]:
    schema_path = repo_root / "docs" / "governance" / "cdx_02_3ls_roadmap.schema.json"
    roadmap_path = repo_root / "docs" / "governance" / "cdx_02_3ls_roadmap.json"
    registry_path = repo_root / "docs" / "architecture" / "system_registry.md"

    schema = _load_json(schema_path)
    roadmap = _load_json(roadmap_path)

    validator = Draft202012Validator(schema)
    schema_errors = sorted(validator.iter_errors(roadmap), key=lambda err: err.path)
    violations: list[str] = []
    findings: list[dict[str, Any]] = []

    if schema_errors:
        violations.append("INVALID_SCHEMA")
        findings.extend(
            {
                "code": "SCHEMA_VALIDATION_ERROR",
                "path": "/" + "/".join(str(token) for token in err.path),
                "message": err.message,
            }
            for err in schema_errors
        )

    model = parse_system_registry(registry_path)
    active = set(model.active_systems)

    if roadmap.get("authority_source") != EXPECTED_AUTHORITY_SOURCE:
        violations.append("NON_CANONICAL_AUTHORITY_SOURCE")

    allowed = set(roadmap.get("allowed_true_new_owners", []))
    if allowed != ALLOWED_TRUE_NEW_OWNERS:
        violations.append("INVALID_TRUE_NEW_OWNER_SET")

    steps = roadmap.get("steps", [])
    expected_ids = [f"3LS-{i:02d}" for i in range(1, 45)]
    ids = [str(step.get("id", "")) for step in steps]
    if ids != expected_ids:
        violations.append("STEP_SEQUENCE_INVALID")

    for idx, step in enumerate(steps):
        sid = step["id"]
        owner = step["owner"]
        if owner not in active and owner not in ALLOWED_TRUE_NEW_OWNERS:
            violations.append("UNKNOWN_OWNER")
            findings.append({"code": "UNKNOWN_OWNER", "step": sid, "owner": owner})

        deps = step.get("dependencies", [])
        if owner in deps:
            violations.append("OWNER_LISTED_AS_DEPENDENCY")

        new_owner = bool(step.get("new_owner", False))
        if new_owner and owner not in ALLOWED_TRUE_NEW_OWNERS:
            violations.append("UNAUTHORIZED_NEW_OWNER")

        if owner in ALLOWED_TRUE_NEW_OWNERS:
            title = str(step.get("title", "")).lower()
            if "decide" in title or "enforce" in title:
                violations.append("PROTECTED_AUTHORITY_VIOLATION")
                findings.append({"code": "PROTECTED_AUTHORITY_VIOLATION", "step": sid, "owner": owner})

        if step.get("classification") == "non_authoritative_mode_or_prep_artifact":
            forbidden = {"CDE", "TPA", "SEL", "PQX"}
            if owner in forbidden:
                violations.append("AUTHORITATIVE_OWNER_MISCLASSIFIED_NON_AUTH")
                findings.append({"code": "AUTHORITATIVE_OWNER_MISCLASSIFIED_NON_AUTH", "step": sid, "owner": owner})

        # deterministic duplicate owner-like check per step
        if len({owner, *deps}) != (1 + len(deps)):
            violations.append("DUPLICATE_OWNER_LIKE_DECLARATION")
            findings.append({"code": "DUPLICATE_OWNER_LIKE_DECLARATION", "step": sid})

        findings.append({
            "step": sid,
            "owner": owner,
            "classification": step.get("classification"),
            "registry_safe": sid in expected_ids and owner != "",
            "index": idx + 1,
        })

    unique_violations = sorted(set(violations))
    return {
        "artifact_type": "cdx_02_roadmap_guard_result",
        "status": "PASS" if not unique_violations else "BLOCK",
        "authority_source": roadmap.get("authority_source"),
        "violations": unique_violations,
        "findings": findings,
        "roadmap_id": roadmap.get("roadmap_id"),
    }
