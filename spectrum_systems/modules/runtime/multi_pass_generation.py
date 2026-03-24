"""HS-08 deterministic multi-pass artifact generation engine.

Fixed pass sequence (no dynamic branching):
1) pass_1 / extract
2) pass_2 / critique
3) pass_3 / refine
4) final / finalize
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Mapping, Sequence

from jsonschema import Draft202012Validator, FormatChecker

from spectrum_systems.contracts import load_schema
from spectrum_systems.utils.deterministic_id import deterministic_id
from spectrum_systems.modules.runtime.evidence_binding import (
    EvidenceBindingError,
    EvidenceBindingPolicy,
    build_evidence_binding_record,
)
from spectrum_systems.modules.runtime.grounding_factcheck_eval import (
    GroundingFactCheckEvalError,
    GroundingFactCheckPolicy,
    build_grounding_factcheck_eval,
)
from spectrum_systems.modules.runtime.grounding_control import (
    GroundingControlError,
    build_grounding_control_decision,
)

_PASS_SEQUENCE = (
    ("pass_1", "extract"),
    ("pass_2", "critique"),
    ("pass_3", "refine"),
    ("final", "final"),
)


class MultiPassGenerationError(RuntimeError):
    """Fail-closed runtime error for HS-08 multi-pass generation."""


@dataclass(frozen=True)
class MultiPassConfig:
    """Deterministic bounded configuration for critique/refinement behavior."""

    unsupported_claim_markers: Sequence[str] = ("TODO", "TBD", "UNSUPPORTED")
    evidence_binding_policy_mode: str = "required_grounded"
    grounding_factcheck_required: bool = True
    fail_on_fact_check_fail: bool = True


def _deterministic_timestamp(payload: Mapping[str, Any], *, stage: str) -> str:
    seed = json.dumps({"stage": stage, "payload": payload}, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    offset_seconds = int(digest[:8], 16) % (365 * 24 * 60 * 60)
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return (base + timedelta(seconds=offset_seconds)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _validate_contract(instance: Dict[str, Any], schema_name: str) -> None:
    schema = load_schema(schema_name)
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(instance)


def _normalize_artifact(artifact: Dict[str, Any]) -> Dict[str, Any]:
    normalized = json.loads(json.dumps(artifact, sort_keys=True, ensure_ascii=False))
    return normalized


def _build_critique(*, extract_output: Dict[str, Any], config: MultiPassConfig) -> Dict[str, Any]:
    missing_elements: List[Dict[str, str]] = []
    inconsistencies: List[Dict[str, str]] = []
    weak_reasoning: List[Dict[str, str]] = []

    for key in sorted(extract_output.keys()):
        value = extract_output[key]
        if value is None or (isinstance(value, str) and value == ""):
            missing_elements.append({"field": key, "issue": "missing_or_empty"})
        if key.endswith("_id") and value is not None and not isinstance(value, str):
            inconsistencies.append({"field": key, "issue": "expected_string_id"})

    claims = extract_output.get("claims")
    if isinstance(claims, list):
        for idx, claim in enumerate(claims):
            if isinstance(claim, dict):
                text = str(claim.get("text") or "")
                refs = claim.get("supporting_evidence_refs")
                if isinstance(refs, list) and len(refs) == 0:
                    weak_reasoning.append({"path": f"claims[{idx}]", "issue": "unsupported_claim"})
                if any(marker in text for marker in config.unsupported_claim_markers):
                    weak_reasoning.append({"path": f"claims[{idx}]", "issue": "weak_reasoning_marker"})

    return {
        "missing_elements": missing_elements,
        "inconsistencies": inconsistencies,
        "weak_reasoning": weak_reasoning,
        "summary": {
            "missing_count": len(missing_elements),
            "inconsistency_count": len(inconsistencies),
            "weak_reasoning_count": len(weak_reasoning),
        },
    }


def _refine_artifact(*, extract_output: Dict[str, Any], critique: Dict[str, Any]) -> Dict[str, Any]:
    refined = _normalize_artifact(extract_output)
    actions: List[Dict[str, str]] = []

    for finding in critique["missing_elements"]:
        field = finding["field"]
        if field not in refined or refined[field] in (None, "", [], {}):
            refined[field] = "MISSING_REQUIRED_VALUE"
            actions.append({"action": "fill_missing", "field": field})

    for finding in critique["inconsistencies"]:
        field = finding["field"]
        if field in refined and refined[field] is not None:
            refined[field] = str(refined[field])
            actions.append({"action": "normalize_id_type", "field": field})

    weak_paths = {finding["path"] for finding in critique["weak_reasoning"] if finding["issue"] == "unsupported_claim"}
    claims = refined.get("claims")
    if weak_paths and isinstance(claims, list):
        kept_claims: List[Any] = []
        for idx, claim in enumerate(claims):
            if f"claims[{idx}]" not in weak_paths:
                kept_claims.append(claim)
        if len(kept_claims) != len(claims):
            refined["claims"] = kept_claims
            actions.append({"action": "drop_unsupported_claims", "field": "claims"})

    return {
        "refined_artifact": refined,
        "refinement_actions": actions,
    }


def _pass_record(
    *,
    run_id: str,
    trace_id: str,
    pass_id: str,
    pass_type: str,
    parent_pass_ids: Sequence[str],
    input_refs: Sequence[str],
    output: Dict[str, Any],
) -> Dict[str, Any]:
    seed = {
        "run_id": run_id,
        "trace_id": trace_id,
        "pass_id": pass_id,
        "pass_type": pass_type,
        "parent_pass_ids": list(parent_pass_ids),
        "input_refs": list(input_refs),
        "output": output,
    }
    return {
        "pass_id": pass_id,
        "pass_type": pass_type,
        "pass_record_id": deterministic_id(prefix="mpr", namespace="multi_pass_record", payload=seed),
        "trace_id": trace_id,
        "parent_pass_ids": list(parent_pass_ids),
        "input_refs": list(input_refs),
        "output_ref": f"multi-pass://{run_id}/{pass_id}",
        "output": output,
        "created_at": _deterministic_timestamp(seed, stage=pass_id),
    }


def run_multi_pass_generation(
    *,
    run_id: str,
    trace_id: str,
    input_artifact: Dict[str, Any],
    validated_context_bundle: Mapping[str, Any] | None = None,
    config: MultiPassConfig | None = None,
) -> Dict[str, Any]:
    """Execute fixed deterministic HS-08 pass chain and return governed record."""
    if not run_id or not trace_id:
        raise MultiPassGenerationError("run_id and trace_id are required")
    if not isinstance(input_artifact, dict):
        raise MultiPassGenerationError("input_artifact must be an object")

    cfg = config or MultiPassConfig()
    if cfg.evidence_binding_policy_mode not in {"required_grounded", "allow_inferred", "allow_unsupported"}:
        raise MultiPassGenerationError("unsupported evidence binding policy mode")

    context_bundle = validated_context_bundle if validated_context_bundle is not None else {"context_items": []}
    if not isinstance(context_bundle, Mapping):
        raise MultiPassGenerationError("validated_context_bundle must be an object")

    pass_records: List[Dict[str, Any]] = []

    extract_output = _normalize_artifact(input_artifact)
    pass_records.append(
        _pass_record(
            run_id=run_id,
            trace_id=trace_id,
            pass_id="pass_1",
            pass_type="extract",
            parent_pass_ids=[],
            input_refs=[f"input://{run_id}"],
            output=extract_output,
        )
    )

    critique_output = _build_critique(extract_output=extract_output, config=cfg)
    if sorted(critique_output.keys()) != ["inconsistencies", "missing_elements", "summary", "weak_reasoning"]:
        raise MultiPassGenerationError("critique output missing required structure")
    pass_records.append(
        _pass_record(
            run_id=run_id,
            trace_id=trace_id,
            pass_id="pass_2",
            pass_type="critique",
            parent_pass_ids=["pass_1"],
            input_refs=[pass_records[0]["output_ref"]],
            output=critique_output,
        )
    )

    refinement_output = _refine_artifact(extract_output=extract_output, critique=critique_output)
    refined_artifact = refinement_output.get("refined_artifact")
    if not isinstance(refined_artifact, dict):
        raise MultiPassGenerationError("refinement output missing refined_artifact object")
    pass_records.append(
        _pass_record(
            run_id=run_id,
            trace_id=trace_id,
            pass_id="pass_3",
            pass_type="refine",
            parent_pass_ids=["pass_1", "pass_2"],
            input_refs=[pass_records[0]["output_ref"], pass_records[1]["output_ref"]],
            output=refinement_output,
        )
    )

    final_output = _normalize_artifact(refined_artifact)
    pass_records.append(
        _pass_record(
            run_id=run_id,
            trace_id=trace_id,
            pass_id="final",
            pass_type="final",
            parent_pass_ids=["pass_3"],
            input_refs=[pass_records[2]["output_ref"]],
            output={"final_artifact": final_output},
        )
    )

    expected_ids = [pass_id for pass_id, _ in _PASS_SEQUENCE]
    actual_ids = [record["pass_id"] for record in pass_records]
    if actual_ids != expected_ids:
        raise MultiPassGenerationError("missing required pass or pass ordering inconsistency")

    parent_record_id = deterministic_id(
        prefix="mpg",
        namespace="multi_pass_generation",
        payload={"run_id": run_id, "trace_id": trace_id, "input_artifact": input_artifact},
    )

    try:
        evidence_binding_record = build_evidence_binding_record(
            run_id=run_id,
            trace_id=trace_id,
            final_artifact=final_output,
            validated_context_bundle=context_bundle,
            parent_multi_pass_record_id=parent_record_id,
            final_pass_id="final",
            final_pass_output_ref=pass_records[3]["output_ref"],
            policy=EvidenceBindingPolicy(mode=cfg.evidence_binding_policy_mode),
        )
    except EvidenceBindingError as exc:
        raise MultiPassGenerationError(f"evidence binding failed: {exc}") from exc

    try:
        grounding_eval = build_grounding_factcheck_eval(
            run_id=run_id,
            trace_id=trace_id,
            source_artifact_id=f"agent-output://{run_id}",
            final_artifact=final_output,
            evidence_binding_record=evidence_binding_record,
            validated_context_bundle=context_bundle,
            parent_multi_pass_record_id=parent_record_id,
            final_pass_output_ref=pass_records[3]["output_ref"],
            policy=GroundingFactCheckPolicy(
                required=cfg.grounding_factcheck_required,
                allow_inferred_claims=cfg.evidence_binding_policy_mode in {"allow_inferred", "allow_unsupported"},
                allow_unsupported_claims=cfg.evidence_binding_policy_mode == "allow_unsupported",
                fail_on_fact_check_fail=cfg.fail_on_fact_check_fail,
            ),
        )
    except GroundingFactCheckEvalError as exc:
        raise MultiPassGenerationError(f"grounding fact-check eval failed: {exc}") from exc

    if cfg.grounding_factcheck_required and not grounding_eval:
        raise MultiPassGenerationError("policy requires grounding eval but eval did not run")
    try:
        grounding_control_decision = build_grounding_control_decision(
            grounding_eval,
            policy={
                "policy_id": "grounding-control-v1",
                "generated_by_version": "hs-20.1.0",
            },
        )
    except GroundingControlError as exc:
        raise MultiPassGenerationError(f"grounding control decision failed: {exc}") from exc

    record = {
        "artifact_type": "multi_pass_generation_record",
        "schema_version": "1.3.0",
        "record_id": parent_record_id,
        "trace_id": trace_id,
        "run_id": run_id,
        "pass_sequence": [
            {"pass_id": pass_id, "pass_type": pass_type, "pass_order": idx + 1}
            for idx, (pass_id, pass_type) in enumerate(_PASS_SEQUENCE)
        ],
        "passes": pass_records,
        "critique": critique_output,
        "refinement": refinement_output,
        "final_output": final_output,
        "evidence_binding": {
            "record_id": evidence_binding_record["record_id"],
            "policy_mode": evidence_binding_record["policy_mode"],
            "claim_ids": [claim["claim_id"] for claim in evidence_binding_record["claims"]],
        },
        "grounding_factcheck_eval": {
            "eval_id": grounding_eval["eval_id"],
            "overall_status": grounding_eval["overall_status"],
            "failure_classes": list(grounding_eval["failure_classes"]),
        },
        "grounding_control_decision": grounding_control_decision,
        "created_at": _deterministic_timestamp({"run_id": run_id, "trace_id": trace_id, "input": input_artifact}, stage="record"),
    }
    _validate_contract(record, "multi_pass_generation_record")
    return record
