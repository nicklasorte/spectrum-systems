"""PRL-02: Bounded repair candidate generator.

INVARIANT: auto_apply is always False. This module MUST NOT apply any fix.
All output is advisory. Fail-closed: schema validation failure raises — no partial artifacts.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import jsonschema

from spectrum_systems.utils.artifact_envelope import build_artifact_envelope
from spectrum_systems.utils.deterministic_id import deterministic_id
from spectrum_systems.modules.prl.failure_classifier import Classification

_SCHEMA_DIR = Path(__file__).resolve().parents[3] / "contracts" / "schemas"

_REPAIR_TEMPLATES: dict[str, dict[str, str]] = {
    "pytest_selection_missing": {
        "repair_prompt": (
            "Add a pytest selection guard or explicit test target to the changed module. "
            "Ensure at least one test exercises the changed surface. "
            "Check that tests/ contains a matching test file for each changed module."
        ),
        "minimal_fix_scope": "Add test file covering changed module or fix pytest collection error",
        "safety_classification": "safe",
    },
    "authority_shape_violation": {
        "repair_prompt": (
            "Fix the authority shape violation in the changed file. "
            "Remove authority-bearing logic from non-owner modules. "
            "Consult docs/architecture/system_registry.md for canonical ownership assignments."
        ),
        "minimal_fix_scope": "Remove authority-leaked logic and route to canonical owner module",
        "safety_classification": "requires_review",
    },
    "system_registry_mismatch": {
        "repair_prompt": (
            "Update docs/architecture/system_registry.md and any affected module manifest "
            "to declare the canonical owner of the changed surface. "
            "Re-run validate_system_registry.py to confirm consistency."
        ),
        "minimal_fix_scope": "Update system registry canonical owner entry and re-validate",
        "safety_classification": "requires_review",
    },
    "contract_schema_violation": {
        "repair_prompt": (
            "Fix the schema validation failure. Ensure all artifact fields match the "
            "canonical JSON schema in contracts/schemas/. "
            "Check additionalProperties=false — remove any undeclared fields. "
            "Ensure all required fields are present with correct types."
        ),
        "minimal_fix_scope": "Align artifact fields with schema definition in contracts/schemas/",
        "safety_classification": "safe",
    },
    "missing_required_artifact": {
        "repair_prompt": (
            "Ensure the required artifact is produced and stored before downstream steps. "
            "Check that all artifact producers run in the correct pipeline order. "
            "Verify artifact path references match the canonical artifact store."
        ),
        "minimal_fix_scope": "Add missing artifact production step or fix artifact path reference",
        "safety_classification": "requires_review",
    },
    "trace_missing": {
        "repair_prompt": (
            "Add trace_id and trace_refs to the artifact using build_artifact_envelope() "
            "from spectrum_systems/utils/artifact_envelope.py. "
            "Every governed artifact requires a non-empty trace_refs.primary."
        ),
        "minimal_fix_scope": "Add trace_refs to artifact envelope using build_artifact_envelope()",
        "safety_classification": "safe",
    },
    "replay_mismatch": {
        "repair_prompt": (
            "Investigate non-deterministic behavior in the artifact producer. "
            "Ensure all artifact IDs use deterministic_id() from "
            "spectrum_systems/utils/deterministic_id.py. "
            "Remove timestamp-based, random, or UUID-based ID generation. "
            "Verify that canonical_json() is used for payload serialization."
        ),
        "minimal_fix_scope": "Replace non-deterministic ID generation with deterministic_id()",
        "safety_classification": "requires_review",
    },
    "policy_mismatch": {
        "repair_prompt": (
            "Review the policy violation against contracts/governance/. "
            "Update the artifact or execution flow to comply with the declared policy. "
            "Check contracts/governance/policy-registry-manifest.json for current active policy."
        ),
        "minimal_fix_scope": "Align artifact or execution path with canonical policy definition",
        "safety_classification": "requires_review",
    },
    "timeout": {
        "repair_prompt": (
            "Investigate the timed-out operation. Consider splitting into smaller bounded slices "
            "via PQX. Review the timeout budget in the execution configuration. "
            "If the operation is inherently long, batch it across multiple bounded cycles."
        ),
        "minimal_fix_scope": "Split long-running operation into bounded slices or adjust timeout config",
        "safety_classification": "requires_review",
    },
    "rate_limited": {
        "repair_prompt": (
            "Add retry logic with exponential backoff for the rate-limited operation. "
            "Retry schedule: 2s, 4s, 8s, 16s (max 4 retries). "
            "Consider batching requests to reduce API call frequency."
        ),
        "minimal_fix_scope": "Add exponential backoff retry (2s/4s/8s/16s) or reduce request rate",
        "safety_classification": "safe",
    },
    "unknown_failure": {
        "repair_prompt": (
            "This failure could not be classified automatically. "
            "Inspect the raw_log_excerpt in the capture record manually. "
            "Route to FRE for structured root-cause diagnosis. "
            "Do not proceed until failure_class is determined."
        ),
        "minimal_fix_scope": "Manual investigation required — route to FRE for structured diagnosis",
        "safety_classification": "requires_review",
    },
}


def _load_schema(name: str) -> dict[str, Any]:
    path = _SCHEMA_DIR / f"{name}.schema.json"
    if not path.exists():
        raise FileNotFoundError(f"PRL schema not found — fail-closed: {path}")
    with path.open() as f:
        return json.load(f)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def generate_repair_candidate(
    *,
    failure_packet: dict[str, Any],
    classification: Classification,
    run_id: str,
    trace_id: str,
) -> dict[str, Any]:
    """Generate a bounded repair candidate artifact.

    NEVER applies fixes. Advisory only.
    """
    ts = _now_iso()
    packet_ref = f"pre_pr_failure_packet:{failure_packet['id']}"
    template = _REPAIR_TEMPLATES.get(
        classification.failure_class,
        _REPAIR_TEMPLATES["unknown_failure"],
    )
    payload = {
        "packet_ref": packet_ref,
        "failure_class": classification.failure_class,
        "repair_prompt": template["repair_prompt"],
        "run_id": run_id,
    }
    artifact_id = deterministic_id(
        prefix="prl-rep",
        payload=payload,
        namespace="prl::repair",
    )
    envelope = build_artifact_envelope(
        artifact_id=artifact_id,
        timestamp=ts,
        schema_version="1.0.0",
        primary_trace_ref=trace_id,
        related_trace_refs=[failure_packet["trace_id"]],
    )
    artifact: dict[str, Any] = {
        "artifact_type": "prl_repair_candidate",
        "schema_version": "1.0.0",
        "id": envelope["id"],
        "timestamp": envelope["timestamp"],
        "run_id": run_id,
        "trace_id": trace_id,
        "trace_refs": envelope["trace_refs"],
        "failure_packet_ref": packet_ref,
        "failure_class": classification.failure_class,
        "target_files": list(failure_packet.get("file_refs", [])),
        "repair_prompt": template["repair_prompt"],
        "minimal_fix_scope": template["minimal_fix_scope"],
        "safety_classification": template["safety_classification"],
        "auto_apply": False,
        "requires_human_review": template["safety_classification"] == "requires_review",
    }
    schema = _load_schema("prl_repair_candidate")
    try:
        jsonschema.validate(artifact, schema)
    except jsonschema.ValidationError as exc:
        raise ValueError(
            f"repair_candidate failed schema validation: {exc.message}"
        ) from exc
    return artifact
