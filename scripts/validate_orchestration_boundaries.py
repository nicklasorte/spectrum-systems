#!/usr/bin/env python3
"""
validate_orchestration_boundaries.py

Validates orchestration boundary enforcement in spectrum-systems:

A. Orchestration-boundary rules
   1. No orchestration-flow files outside orchestration/ or canonical schemas/
   2. No cross-module routing metadata in non-orchestration modules
   3. No duplicated artifact-bus-message schemas outside the canonical location
   4. No execution-order keywords in non-orchestration module manifests

B. Artifact handoff rules (validate any artifact-bus messages in docs/examples/)
   1. Artifact-bus messages conform to the canonical schema
   2. source_module and target_module resolve to real module manifests
   3. artifact_type is declared in the target module's manifest inputs
   4. lifecycle_state is recognized per lifecycle_states.json
   5. lineage_ref is present (required for all governed handoffs)

C. Orchestration-flow manifest rules (validate any flow manifests in docs/examples/)
   1. Orchestration-flow manifests conform to the canonical schema
   2. All stage source_module / target_module values resolve to real manifests
   3. All stage artifact_types are declared in the relevant target module inputs

Exits 0 on success, 1 on any violation.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

REPO_ROOT = Path(__file__).resolve().parents[1]

# ── Canonical schema paths ────────────────────────────────────────────────────
ARTIFACT_BUS_SCHEMA_PATH = REPO_ROOT / "schemas" / "artifact-bus-message.schema.json"
ORCHESTRATION_FLOW_SCHEMA_PATH = REPO_ROOT / "schemas" / "orchestration-flow.schema.json"
MODULE_MANIFEST_SCHEMA_PATH = REPO_ROOT / "schemas" / "module-manifest.schema.json"
LIFECYCLE_STATES_PATH = (
    REPO_ROOT / "control_plane" / "lifecycle" / "lifecycle_states.json"
)

# ── Canonical locations ───────────────────────────────────────────────────────
MANIFESTS_DIR = REPO_ROOT / "docs" / "module-manifests"
EXAMPLES_DIR = REPO_ROOT / "docs" / "examples"

# ── Dirs that legitimately own orchestration/flow/bus files ──────────────────
ORCHESTRATION_OWNER_PREFIXES = (
    "schemas/",
    "docs/examples/",
    "orchestration/",
    "docs/architecture/",
)

# ── Modules whose dirs are non-orchestration (check in these trees) ───────────
NON_ORCHESTRATION_ROOTS = [
    REPO_ROOT / "workflow_modules",
    REPO_ROOT / "domain_modules",
    REPO_ROOT / "control_plane",
    REPO_ROOT / "shared",
    REPO_ROOT / "spectrum_systems",
]

# ── Keywords indicating cross-module routing in a schema/JSON file ────────────
ROUTING_KEYWORDS: dict[str, list[str]] = {
    "execution_order": ["execution_order", "next_module", "pipeline_stage", "routing_target"],
    "flow_definition": ["orchestration_flow", "flow_definition", "module_sequence"],
}

# ── Filenames that indicate a locally-defined orchestration-flow or bus schema ─
ORCHESTRATION_FLOW_FILENAMES = {
    "orchestration-flow.schema.json",
    "orchestration_flow.schema.json",
    "orchestration-flow.json",
}

ARTIFACT_BUS_FILENAMES = {
    "artifact-bus-message.schema.json",
    "artifact-bus.schema.json",
    "artifact_bus_message.schema.json",
    "artifact_bus.schema.json",
}

SCHEMA_EXTENSIONS = {".json", ".yaml", ".yml"}


# ── Utilities ─────────────────────────────────────────────────────────────────


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _rel(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _is_orchestration_owner(path: Path) -> bool:
    try:
        rel = path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return False
    return any(rel.startswith(prefix) for prefix in ORCHESTRATION_OWNER_PREFIXES)


# ── Load module manifests into a lookup table ─────────────────────────────────


def load_all_module_manifests() -> dict[str, dict]:
    """Return a dict of module_id → manifest for all manifests in MANIFESTS_DIR."""
    manifests: dict[str, dict] = {}
    if not MANIFESTS_DIR.exists():
        return manifests
    for p in MANIFESTS_DIR.rglob("*.json"):
        try:
            m = load_json(p)
            mid = m.get("module_id")
            if mid:
                manifests[mid] = m
        except (json.JSONDecodeError, KeyError):
            pass
    return manifests


def load_lifecycle_states() -> set[str]:
    """Return the set of recognized lifecycle state names."""
    if not LIFECYCLE_STATES_PATH.is_file():
        return set()
    doc = load_json(LIFECYCLE_STATES_PATH)
    return {s["state"] for s in doc.get("states", [])}


# ═════════════════════════════════════════════════════════════════════════════
# Rule set A — Orchestration boundary rules
# ═════════════════════════════════════════════════════════════════════════════


def check_no_orchestration_flow_files_outside_orchestration() -> list[dict]:
    """
    Rule A1 — No orchestration-flow files outside orchestration/ or schemas/.
    """
    violations: list[dict] = []
    for root in NON_ORCHESTRATION_ROOTS:
        if not root.exists():
            continue
        for fpath in sorted(root.rglob("*")):
            if not fpath.is_file():
                continue
            if _is_orchestration_owner(fpath):
                continue
            if fpath.name.lower() in ORCHESTRATION_FLOW_FILENAMES:
                violations.append(
                    {
                        "rule": "orchestration_flow_file_in_non_orchestration_module",
                        "module": _rel(fpath.parent),
                        "file": _rel(fpath),
                        "message": (
                            f"Orchestration-flow file '{fpath.name}' found outside "
                            "orchestration/.  Flow definitions must live in "
                            "orchestration/ or schemas/."
                        ),
                    }
                )
    return violations


def check_no_artifact_bus_duplicates() -> list[dict]:
    """
    Rule A3 — No duplicated artifact-bus schemas outside the canonical location.
    """
    violations: list[dict] = []
    for root in NON_ORCHESTRATION_ROOTS:
        if not root.exists():
            continue
        for fpath in sorted(root.rglob("*")):
            if not fpath.is_file():
                continue
            if _is_orchestration_owner(fpath):
                continue
            if fpath.name.lower() in ARTIFACT_BUS_FILENAMES:
                violations.append(
                    {
                        "rule": "artifact_bus_schema_duplicated",
                        "module": _rel(fpath.parent),
                        "file": _rel(fpath),
                        "message": (
                            f"Artifact-bus schema file '{fpath.name}' found outside "
                            "the canonical location.  The artifact bus schema must "
                            "only exist at schemas/artifact-bus-message.schema.json."
                        ),
                    }
                )
    return violations


def check_no_routing_keywords_in_non_orchestration_modules() -> list[dict]:
    """
    Rule A2 — No cross-module routing metadata in non-orchestration schema files.

    Scans JSON/YAML files under non-orchestration roots for known routing
    keywords that indicate a module is attempting to define cross-module flow.
    """
    violations: list[dict] = []
    for root in NON_ORCHESTRATION_ROOTS:
        if not root.exists():
            continue
        for fpath in sorted(root.rglob("*")):
            if not fpath.is_file():
                continue
            if fpath.suffix not in SCHEMA_EXTENSIONS:
                continue
            if _is_orchestration_owner(fpath):
                continue

            content = fpath.read_text(encoding="utf-8", errors="replace")
            for category, keywords in ROUTING_KEYWORDS.items():
                for kw in keywords:
                    if f'"{kw}"' in content or f"'{kw}'" in content:
                        violations.append(
                            {
                                "rule": "routing_keyword_in_non_orchestration_module",
                                "module": _rel(fpath.parent),
                                "file": _rel(fpath),
                                "message": (
                                    f"Routing keyword '{kw}' (category: {category}) "
                                    f"found in a non-orchestration schema file.  "
                                    "Cross-module routing metadata must only appear "
                                    "in orchestration/ or schemas/."
                                ),
                            }
                        )
    return violations


# ═════════════════════════════════════════════════════════════════════════════
# Rule set B — Artifact handoff validation
# ═════════════════════════════════════════════════════════════════════════════


def _validate_artifact_bus_message(
    message: dict,
    schema: dict,
    manifests: dict[str, dict],
    lifecycle_states: set[str],
    source_path: Path,
) -> list[dict]:
    """Validate a single artifact bus message against all handoff rules."""
    violations: list[dict] = []
    source_label = _rel(source_path)

    # B1 — Schema conformance
    v = Draft202012Validator(schema)
    schema_errors = list(v.iter_errors(message))
    for err in schema_errors:
        path_str = "/".join(map(str, err.path)) or "<root>"
        violations.append(
            {
                "rule": "artifact_bus_message_schema_violation",
                "module": source_label,
                "file": source_label,
                "message": f"Artifact bus message schema violation at {path_str}: {err.message}",
            }
        )
    if schema_errors:
        # Skip semantic checks when schema conformance fails
        return violations

    src_mod = message.get("source_module", "")
    tgt_mod = message.get("target_module", "")
    art_type = message.get("artifact_type", "")
    lc_state = message.get("lifecycle_state", "")
    lineage_ref = message.get("lineage_ref", "")

    # B2 — source_module resolves to a real manifest
    if manifests and src_mod not in manifests:
        violations.append(
            {
                "rule": "artifact_bus_source_module_not_found",
                "module": src_mod,
                "file": source_label,
                "artifact_type": art_type,
                "message": (
                    f"source_module '{src_mod}' does not resolve to a known module "
                    "manifest.  All source modules must have a manifest in "
                    "docs/module-manifests/."
                ),
            }
        )

    # B2 — target_module resolves to a real manifest
    if manifests and tgt_mod not in manifests:
        violations.append(
            {
                "rule": "artifact_bus_target_module_not_found",
                "module": tgt_mod,
                "file": source_label,
                "artifact_type": art_type,
                "message": (
                    f"target_module '{tgt_mod}' does not resolve to a known module "
                    "manifest.  All target modules must have a manifest in "
                    "docs/module-manifests/."
                ),
            }
        )
    elif manifests and tgt_mod in manifests:
        # B3 — artifact_type declared in target module's manifest inputs
        target_inputs = manifests[tgt_mod].get("inputs", [])
        if art_type and art_type not in target_inputs:
            violations.append(
                {
                    "rule": "artifact_type_not_declared_in_target_inputs",
                    "module": tgt_mod,
                    "file": source_label,
                    "artifact_type": art_type,
                    "message": (
                        f"artifact_type '{art_type}' is not declared in the inputs "
                        f"of target_module '{tgt_mod}'.  A target module cannot "
                        "receive an artifact type it did not declare as input in "
                        "its module manifest."
                    ),
                }
            )

    # B4 — lifecycle_state is recognized
    if lifecycle_states and lc_state and lc_state not in lifecycle_states:
        violations.append(
            {
                "rule": "artifact_bus_invalid_lifecycle_state",
                "module": src_mod,
                "file": source_label,
                "artifact_type": art_type,
                "message": (
                    f"lifecycle_state '{lc_state}' is not a recognized state in "
                    "lifecycle_states.json.  Valid states: "
                    + ", ".join(sorted(lifecycle_states))
                ),
            }
        )

    # B5 — lineage_ref is present (already enforced by schema required, but belt+suspenders)
    if not lineage_ref:
        violations.append(
            {
                "rule": "artifact_bus_missing_lineage_ref",
                "module": src_mod,
                "file": source_label,
                "artifact_type": art_type,
                "message": "lineage_ref is required on all governed artifact bus messages.",
            }
        )

    return violations


def check_artifact_bus_examples(
    manifests: dict[str, dict],
    lifecycle_states: set[str],
) -> list[dict]:
    """
    Rule B — Validate all artifact-bus message examples in docs/examples/.
    """
    violations: list[dict] = []
    if not ARTIFACT_BUS_SCHEMA_PATH.is_file():
        violations.append(
            {
                "rule": "artifact_bus_schema_missing",
                "module": "schemas",
                "file": _rel(ARTIFACT_BUS_SCHEMA_PATH),
                "message": "Canonical artifact bus schema is missing: "
                "schemas/artifact-bus-message.schema.json",
            }
        )
        return violations

    schema = load_json(ARTIFACT_BUS_SCHEMA_PATH)

    if not EXAMPLES_DIR.exists():
        return violations

    for fpath in sorted(EXAMPLES_DIR.glob("artifact-bus-message*.json")):
        try:
            message = load_json(fpath)
        except json.JSONDecodeError as exc:
            violations.append(
                {
                    "rule": "artifact_bus_example_invalid_json",
                    "module": _rel(fpath.parent),
                    "file": _rel(fpath),
                    "message": f"Invalid JSON in artifact bus example: {exc}",
                }
            )
            continue

        violations.extend(
            _validate_artifact_bus_message(
                message, schema, manifests, lifecycle_states, fpath
            )
        )

    return violations


# ═════════════════════════════════════════════════════════════════════════════
# Rule set C — Orchestration-flow manifest rules
# ═════════════════════════════════════════════════════════════════════════════


def check_orchestration_flow_examples(
    manifests: dict[str, dict],
    lifecycle_states: set[str],
) -> list[dict]:
    """
    Rule C — Validate orchestration-flow example manifests in docs/examples/.
    """
    violations: list[dict] = []
    if not ORCHESTRATION_FLOW_SCHEMA_PATH.is_file():
        violations.append(
            {
                "rule": "orchestration_flow_schema_missing",
                "module": "schemas",
                "file": _rel(ORCHESTRATION_FLOW_SCHEMA_PATH),
                "message": "Canonical orchestration flow schema is missing: "
                "schemas/orchestration-flow.schema.json",
            }
        )
        return violations

    schema = load_json(ORCHESTRATION_FLOW_SCHEMA_PATH)

    if not EXAMPLES_DIR.exists():
        return violations

    for fpath in sorted(EXAMPLES_DIR.glob("orchestration-flow*.json")):
        try:
            flow = load_json(fpath)
        except json.JSONDecodeError as exc:
            violations.append(
                {
                    "rule": "orchestration_flow_invalid_json",
                    "module": _rel(fpath.parent),
                    "file": _rel(fpath),
                    "message": f"Invalid JSON in orchestration flow example: {exc}",
                }
            )
            continue

        # C1 — Schema conformance
        v = Draft202012Validator(schema)
        schema_errors = list(v.iter_errors(flow))
        for err in schema_errors:
            path_str = "/".join(map(str, err.path)) or "<root>"
            violations.append(
                {
                    "rule": "orchestration_flow_schema_violation",
                    "module": _rel(fpath.parent),
                    "file": _rel(fpath),
                    "flow": flow.get("flow_id", "<unknown>"),
                    "message": f"Orchestration flow schema violation at {path_str}: {err.message}",
                }
            )
        if schema_errors:
            continue

        flow_id = flow.get("flow_id", "<unknown>")

        # C2 / C3 — Validate per-stage module and artifact_type references
        for stage in flow.get("stages", []):
            stage_id = stage.get("stage_id", "<unknown>")
            src = stage.get("source_module", "")
            tgt = stage.get("target_module", "")
            art = stage.get("artifact_type", "")
            lcs = stage.get("lifecycle_state_at_handoff", "")

            # C2 — source_module must resolve to a manifest
            if manifests and src and src not in manifests:
                violations.append(
                    {
                        "rule": "orchestration_flow_source_module_not_found",
                        "module": src,
                        "file": _rel(fpath),
                        "flow": flow_id,
                        "stage": stage_id,
                        "artifact_type": art,
                        "message": (
                            f"Stage {stage_id}: source_module '{src}' does not "
                            "resolve to a known module manifest."
                        ),
                    }
                )

            # C2 — target_module must resolve to a manifest
            if manifests and tgt and tgt not in manifests:
                violations.append(
                    {
                        "rule": "orchestration_flow_target_module_not_found",
                        "module": tgt,
                        "file": _rel(fpath),
                        "flow": flow_id,
                        "stage": stage_id,
                        "artifact_type": art,
                        "message": (
                            f"Stage {stage_id}: target_module '{tgt}' does not "
                            "resolve to a known module manifest."
                        ),
                    }
                )
            elif manifests and tgt and tgt in manifests:
                # C3 — artifact_type must be in target module's inputs
                target_inputs = manifests[tgt].get("inputs", [])
                if art and art not in target_inputs:
                    violations.append(
                        {
                            "rule": "orchestration_flow_artifact_type_not_in_target_inputs",
                            "module": tgt,
                            "file": _rel(fpath),
                            "flow": flow_id,
                            "stage": stage_id,
                            "artifact_type": art,
                            "message": (
                                f"Stage {stage_id}: artifact_type '{art}' is not "
                                f"declared in the inputs of target_module '{tgt}'."
                            ),
                        }
                    )

            # lifecycle_state_at_handoff must be recognized
            if lifecycle_states and lcs and lcs not in lifecycle_states:
                violations.append(
                    {
                        "rule": "orchestration_flow_invalid_lifecycle_state",
                        "module": tgt,
                        "file": _rel(fpath),
                        "flow": flow_id,
                        "stage": stage_id,
                        "message": (
                            f"Stage {stage_id}: lifecycle_state_at_handoff '{lcs}' "
                            "is not recognized in lifecycle_states.json."
                        ),
                    }
                )

    return violations


# ═════════════════════════════════════════════════════════════════════════════
# Main
# ═════════════════════════════════════════════════════════════════════════════


def run_all_checks() -> list[dict]:
    manifests = load_all_module_manifests()
    lifecycle_states = load_lifecycle_states()

    violations: list[dict] = []

    # A — Boundary rules
    violations.extend(check_no_orchestration_flow_files_outside_orchestration())
    violations.extend(check_no_artifact_bus_duplicates())
    violations.extend(check_no_routing_keywords_in_non_orchestration_modules())

    # B — Artifact handoff validation
    violations.extend(check_artifact_bus_examples(manifests, lifecycle_states))

    # C — Orchestration flow manifest validation
    violations.extend(check_orchestration_flow_examples(manifests, lifecycle_states))

    return violations


def main() -> int:
    violations = run_all_checks()

    if not violations:
        print(
            "Orchestration boundary validation passed — no violations detected."
        )
        return 0

    print(
        f"Orchestration boundary validation FAILED — "
        f"{len(violations)} violation(s) found:\n"
    )
    for v in violations:
        print(f"  [VIOLATION] rule={v['rule']}")
        if v.get("module"):
            print(f"              module={v['module']}")
        if v.get("flow"):
            print(f"              flow={v['flow']}")
        if v.get("stage"):
            print(f"              stage={v['stage']}")
        if v.get("artifact_type"):
            print(f"              artifact_type={v['artifact_type']}")
        if v.get("file"):
            print(f"              file={v['file']}")
        print(f"              message={v['message']}")
        print()
    return 1


if __name__ == "__main__":
    sys.exit(main())
