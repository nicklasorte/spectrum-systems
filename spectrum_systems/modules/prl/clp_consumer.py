"""CLP-02 — PRL consumer for core_loop_pre_pr_gate_result.

PRL ingests CLP block evidence as structured input. CLP failure classes are
normalized to PRL's canonical KNOWN_FAILURE_CLASSES so existing
`failure_classifier` / repair / eval generation flows can act on them.

PRL retains all classification, repair, and eval-generation authority. This
module is a translator only: it reads a CLP artifact and emits PRL-shaped
ParsedFailure records. It performs no auto-repair (CLP-02 forbids that).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from spectrum_systems.modules.prl.failure_parser import ParsedFailure


# Mapping CLP failure classes (and CLP check reason codes) onto canonical
# PRL KNOWN_FAILURE_CLASSES. Anything not in this table degrades to
# unknown_failure inside the PRL classifier — which is the correct
# fail-closed behavior.
CLP_TO_PRL_FAILURE_CLASS: dict[str, str] = {
    "authority_shape_violation": "authority_shape_violation",
    "authority_shape_review_language_lint": "authority_shape_violation",
    "authority_leak_violation": "authority_shape_violation",
    "authority_leak_guard_failure": "authority_shape_violation",
    "forbidden_authority_value": "authority_shape_violation",
    "contract_enforcement_violation": "contract_schema_violation",
    "contract_compliance_findings": "contract_schema_violation",
    "contract_preflight_block": "contract_schema_violation",
    "contract_mismatch": "contract_schema_violation",
    "schema_violation": "contract_schema_violation",
    "tls_generated_artifact_stale": "missing_required_artifact",
    "tls_generated_artifact_drift": "missing_required_artifact",
    "tls_generator_returned_nonzero": "missing_required_artifact",
    "generated_artifact_stale": "missing_required_artifact",
    "missing_required_artifact": "missing_required_artifact",
    "missing_required_check_output": "missing_required_artifact",
    "pytest_selection_missing": "pytest_selection_missing",
    "no_tests_selected_for_governed_changes": "pytest_selection_missing",
    "selected_test_failure": "pytest_selection_missing",
    "policy_mismatch": "policy_mismatch",
    "system_registry_mismatch": "system_registry_mismatch",
    # CLP-02 guard-only reason codes (PR-ready guard)
    "clp_evidence_missing": "missing_required_artifact",
    "clp_authority_scope_invalid": "policy_mismatch",
    "clp_warn_unapproved": "policy_mismatch",
    "agent_pr_ready_evidence_invalid": "missing_required_artifact",
    "pre_pr_gate_blocked": "policy_mismatch",
}


def normalize_clp_reason_code(code: str) -> str:
    """Translate a CLP reason code or failure class to a PRL failure class.

    Unknown codes fall through to ``unknown_failure`` so the PRL classifier
    can fail-closed.
    """
    return CLP_TO_PRL_FAILURE_CLASS.get(code, "unknown_failure")


def load_clp_result(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    if payload.get("artifact_type") != "core_loop_pre_pr_gate_result":
        return None
    return payload


def parsed_failures_from_clp_result(
    clp_result: dict[str, Any],
    *,
    clp_path: str | None = None,
) -> list[ParsedFailure]:
    """Translate a CLP block into PRL ParsedFailure records.

    Returns an empty list when ``gate_status`` is not ``block`` — PRL has
    nothing to classify. PRL retains all downstream authority (repair, eval
    generation, gate signal aggregation).
    """
    if not isinstance(clp_result, dict):
        return []
    if clp_result.get("gate_status") != "block":
        return []
    failures: list[ParsedFailure] = []
    seen: set[tuple[str, str]] = set()

    # Prefer per-check granularity so PRL can classify each blocking check
    # independently.
    for check in clp_result.get("checks") or []:
        if not isinstance(check, dict):
            continue
        if check.get("status") != "block":
            continue
        clp_class = check.get("failure_class") or "missing_required_check_output"
        prl_class = normalize_clp_reason_code(clp_class)
        excerpt_parts = [
            f"clp:{check.get('check_name')}",
            f"failure_class={clp_class}",
        ]
        reasons = [c for c in check.get("reason_codes") or [] if isinstance(c, str)]
        if reasons:
            excerpt_parts.append("reason_codes=" + ",".join(reasons))
        excerpt = " ".join(excerpt_parts)
        key = (prl_class, str(check.get("check_name")))
        if key in seen:
            continue
        seen.add(key)
        file_refs: tuple[str, ...] = ()
        ref = check.get("output_ref")
        if isinstance(ref, str) and ref:
            file_refs = (ref,)
        elif clp_path:
            file_refs = (clp_path,)
        failures.append(
            ParsedFailure(
                failure_class=prl_class,
                raw_excerpt=excerpt[:500],
                normalized_message=(
                    f"CLP block: {check.get('check_name')} -> {clp_class}"
                ),
                file_refs=file_refs,
                line_number=None,
                exit_code=2,
            )
        )

    if failures:
        return failures

    # Fallback: top-level failure_classes only (no per-check granularity).
    for clp_class in clp_result.get("failure_classes") or []:
        if not isinstance(clp_class, str):
            continue
        prl_class = normalize_clp_reason_code(clp_class)
        key = (prl_class, clp_class)
        if key in seen:
            continue
        seen.add(key)
        file_refs = (clp_path,) if clp_path else ()
        failures.append(
            ParsedFailure(
                failure_class=prl_class,
                raw_excerpt=f"clp_failure_class={clp_class}",
                normalized_message=f"CLP block: {clp_class}",
                file_refs=file_refs,
                line_number=None,
                exit_code=2,
            )
        )

    return failures
