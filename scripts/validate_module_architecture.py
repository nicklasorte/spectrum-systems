#!/usr/bin/env python3
"""
validate_module_architecture.py

Validates the module architecture of spectrum-systems:

1. Required module manifests exist.
2. All manifests conform to the module-manifest schema.
3. Non-shared modules do not redefine shared-truth structures.
4. forbidden_responsibilities is present and non-empty in all manifests.

Exits with code 0 on success, 1 if any violations are found.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "schemas" / "module-manifest.schema.json"
MANIFESTS_DIR = REPO_ROOT / "docs" / "module-manifests"

# Modules that must have a manifest for CI to pass.
REQUIRED_MANIFESTS: list[str] = [
    "control_plane/evaluation.json",
    "control_plane/work_items.json",
    "orchestration/pipeline.json",
    "workflow_modules/meeting_intelligence.json",
    "workflow_modules/comment_resolution.json",
    "domain_modules/knowledge_capture.json",
    "shared/artifact_models.json",
    "shared/ids.json",
    "shared/lineage.json",
    "shared/readiness.json",
]

# Keywords that indicate a file is attempting to define shared-truth structures.
# Keys are the category name used in error messages; values are the search terms.
SHARED_TRUTH_KEYWORDS: dict[str, list[str]] = {
    "artifact_model": [
        "ArtifactEnvelope",
        "artifact_envelope",
        "artifact_bundle",
        "ArtifactBundle",
        "ArtifactMetadata",
    ],
    "identifier_scheme": [
        "ArtifactID",
        "artifact_id",
        "ModuleID",
        "module_id_scheme",
        "SystemID",
        "system_id_scheme",
        "RunID",
        "run_id_scheme",
    ],
    "lineage_primitive": [
        "LineageRecord",
        "lineage_record",
        "ArtifactLineageChain",
        "lineage_chain",
    ],
    "provenance_primitive": [
        "ProvenanceRecord",
        "provenance_record",
    ],
    "readiness_primitive": [
        "ReadinessState",
        "readiness_state",
        "ReadinessAssessment",
        "readiness_assessment",
    ],
}

# File extensions that may contain redefined shared structures (schema/contract files).
SCHEMA_EXTENSIONS = {".json", ".yaml", ".yml"}

# Paths that are exempt from shared-truth checks (the shared layer itself and
# the canonical schemas/contracts directories which are governed separately).
SHARED_TRUTH_EXEMPT_PREFIXES = (
    "docs/module-manifests/shared/",
    "schemas/",
    "contracts/",
)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _rel(path: Path) -> str:
    """Return a path string relative to REPO_ROOT, or the absolute path if outside."""
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _relm(path: Path) -> str:
    """Return a path string relative to MANIFESTS_DIR, or the absolute path if outside."""
    try:
        return str(path.relative_to(MANIFESTS_DIR))
    except ValueError:
        return str(path)


# ---------------------------------------------------------------------------
# Rule 1: Required manifests exist
# ---------------------------------------------------------------------------


def check_required_manifests() -> list[dict]:
    violations: list[dict] = []
    for rel in REQUIRED_MANIFESTS:
        path = MANIFESTS_DIR / rel
        if not path.is_file():
            violations.append(
                {
                    "rule": "required_manifest_missing",
                    "module": rel,
                    "file": _rel(path),
                    "message": f"Required module manifest is missing: {rel}",
                }
            )
    return violations


# ---------------------------------------------------------------------------
# Rule 2: All manifests conform to schema
# ---------------------------------------------------------------------------


def check_manifest_schema_conformance(schema: dict) -> list[dict]:
    violations: list[dict] = []
    validator = Draft202012Validator(schema)
    for manifest_path in sorted(MANIFESTS_DIR.rglob("*.json")):
        try:
            instance = load_json(manifest_path)
        except json.JSONDecodeError as exc:
            violations.append(
                {
                    "rule": "manifest_invalid_json",
                    "module": _relm(manifest_path),
                    "file": _rel(manifest_path),
                    "message": f"Invalid JSON: {exc}",
                }
            )
            continue

        schema_errors = sorted(validator.iter_errors(instance), key=lambda e: list(e.path))
        for error in schema_errors:
            path_str = "/".join(map(str, error.path)) or "<root>"
            violations.append(
                {
                    "rule": "manifest_schema_violation",
                    "module": _relm(manifest_path),
                    "file": _rel(manifest_path),
                    "message": f"Schema violation at {path_str}: {error.message}",
                }
            )
    return violations


# ---------------------------------------------------------------------------
# Rule 3: Non-shared modules do not define shared-truth structures
# ---------------------------------------------------------------------------


def _is_exempt(path: Path) -> bool:
    try:
        rel = path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return False
    return any(rel.startswith(prefix) for prefix in SHARED_TRUTH_EXEMPT_PREFIXES)


def _file_defines_keyword(content: str, keywords: list[str]) -> list[str]:
    """Return any keywords found in a file that looks like a definition site."""
    found = []
    for kw in keywords:
        # Look for the keyword appearing as a key, type, or top-level property
        # in a schema/contract context — simple heuristic checks.
        if f'"{kw}"' in content or f"'{kw}'" in content:
            found.append(kw)
    return found


def check_no_shared_truth_redefinition() -> list[dict]:
    """
    Walk non-shared schema/contract files and flag any that appear to define
    shared-truth primitives that should only exist in shared/.
    """
    violations: list[dict] = []

    # Gather candidate files: JSON/YAML files outside the exempt prefixes that
    # live outside the docs/module-manifests directory (manifests themselves are
    # not schema definition files).
    candidate_roots = [
        REPO_ROOT / "spectrum_systems",
    ]

    for root in candidate_roots:
        if not root.exists():
            continue
        for fpath in sorted(root.rglob("*")):
            if not fpath.is_file():
                continue
            if fpath.suffix not in SCHEMA_EXTENSIONS:
                continue
            if _is_exempt(fpath):
                continue

            content = fpath.read_text(encoding="utf-8", errors="replace")
            for category, keywords in SHARED_TRUTH_KEYWORDS.items():
                found_kws = _file_defines_keyword(content, keywords)
                if found_kws:
                    violations.append(
                        {
                            "rule": "shared_truth_redefined",
                            "module": _rel(fpath),
                            "file": _rel(fpath),
                            "message": (
                                f"File appears to define shared-truth primitives "
                                f"({category}): {', '.join(found_kws)}. "
                                f"These must only be defined in shared/."
                            ),
                        }
                    )

    return violations


# ---------------------------------------------------------------------------
# Rule 4: forbidden_responsibilities is present and non-empty
# ---------------------------------------------------------------------------


def check_forbidden_responsibilities(schema: dict) -> list[dict]:
    """
    Validate that every manifest has forbidden_responsibilities with at least
    one entry. The JSON Schema already enforces minItems: 1; this check provides
    a clear, targeted CI message for the common case of an empty list.
    """
    violations: list[dict] = []
    for manifest_path in sorted(MANIFESTS_DIR.rglob("*.json")):
        try:
            instance = load_json(manifest_path)
        except json.JSONDecodeError:
            continue  # already caught in schema check

        fr = instance.get("forbidden_responsibilities")
        if fr is None or len(fr) == 0:
            violations.append(
                {
                    "rule": "forbidden_responsibilities_empty",
                    "module": _relm(manifest_path),
                    "file": _rel(manifest_path),
                    "message": (
                        "forbidden_responsibilities must be present and contain "
                        "at least one entry."
                    ),
                }
            )
    return violations


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def run_all_checks() -> list[dict]:
    schema = load_json(SCHEMA_PATH)
    violations: list[dict] = []
    violations.extend(check_required_manifests())
    violations.extend(check_manifest_schema_conformance(schema))
    violations.extend(check_no_shared_truth_redefinition())
    violations.extend(check_forbidden_responsibilities(schema))
    return violations


def main() -> int:
    if not SCHEMA_PATH.is_file():
        print(f"ERROR: Module manifest schema not found: {SCHEMA_PATH.relative_to(REPO_ROOT)}")
        return 1

    violations = run_all_checks()

    if not violations:
        print("Module architecture validation passed — no violations detected.")
        return 0

    print(f"Module architecture validation FAILED — {len(violations)} violation(s) found:\n")
    for v in violations:
        print(f"  [VIOLATION] module={v['module']}")
        print(f"              rule={v['rule']}")
        if v.get("file"):
            print(f"              file={v['file']}")
        print(f"              message={v['message']}")
        print()
    return 1


if __name__ == "__main__":
    sys.exit(main())
