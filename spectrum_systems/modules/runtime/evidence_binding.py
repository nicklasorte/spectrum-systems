"""HS-09 deterministic evidence binding for final artifacts.

This module classifies important claims and binds directly supported claims to
validated context/source references with fail-closed enforcement.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Mapping, Sequence, Set, Tuple

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import ValidationError

from spectrum_systems.contracts import load_schema
from spectrum_systems.utils.deterministic_id import deterministic_id


class EvidenceBindingError(RuntimeError):
    """Fail-closed runtime error for HS-09 evidence binding."""


@dataclass(frozen=True)
class EvidenceBindingPolicy:
    """Deterministic policy for unsupported/inferred claim allowance."""

    mode: str = "required_grounded"


_IMPORTANT_TOP_LEVEL_FIELDS: Tuple[str, ...] = ("summary", "decision", "recommendation", "conclusion")
_ALLOWED_POLICY_MODES = {"required_grounded", "allow_inferred", "allow_unsupported"}


def _deterministic_timestamp(payload: Mapping[str, Any], *, stage: str) -> str:
    seed = json.dumps({"stage": stage, "payload": payload}, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    offset_seconds = int(digest[:8], 16) % (365 * 24 * 60 * 60)
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return (base + timedelta(seconds=offset_seconds)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _validate_contract(instance: Dict[str, Any], schema_name: str) -> None:
    schema = load_schema(schema_name)
    try:
        Draft202012Validator(schema, format_checker=FormatChecker()).validate(instance)
    except ValidationError as exc:
        raise EvidenceBindingError(f"{schema_name} validation failed: {exc.message}") from exc


def _normalize(value: Any) -> Any:
    return json.loads(json.dumps(value, sort_keys=True, ensure_ascii=False))


def _context_trace(validated_context_bundle: Mapping[str, Any]) -> Tuple[str, str]:
    trace = validated_context_bundle.get("trace")
    if not isinstance(trace, Mapping):
        raise EvidenceBindingError("validated_context_bundle.trace is required")
    trace_id = str(trace.get("trace_id") or "").strip()
    run_id = str(trace.get("run_id") or "").strip()
    if not trace_id or not run_id:
        raise EvidenceBindingError("validated_context_bundle.trace.trace_id and trace.run_id are required")
    return trace_id, run_id


def _allowed_reference_sets(validated_context_bundle: Mapping[str, Any]) -> Tuple[Set[str], Set[str], Dict[str, Set[str]]]:
    evidence_item_refs: Set[str] = set()
    evidence_item_to_provenance: Dict[str, Set[str]] = {}
    for item in list(validated_context_bundle.get("context_items") or []):
        item_id = str(item.get("item_id") or "").strip()
        if item_id:
            evidence_item_refs.add(item_id)
            provenance_refs = {
                str(ref or "").strip() for ref in list(item.get("provenance_refs") or []) if str(ref or "").strip()
            }
            single_provenance_ref = str(item.get("provenance_ref") or "").strip()
            if single_provenance_ref:
                provenance_refs.add(single_provenance_ref)
            evidence_item_to_provenance[item_id] = provenance_refs

    source_artifact_refs: Set[str] = set()
    for artifact in list(validated_context_bundle.get("prior_artifacts") or []):
        artifact_id = str(artifact.get("artifact_id") or "").strip()
        if artifact_id:
            source_artifact_refs.add(artifact_id)
    for artifact in list(validated_context_bundle.get("retrieved_context") or []):
        artifact_id = str(artifact.get("artifact_id") or "").strip()
        if artifact_id:
            source_artifact_refs.add(artifact_id)
    for artifact_id in list(((validated_context_bundle.get("metadata") or {}).get("source_artifact_ids") or [])):
        normalized = str(artifact_id or "").strip()
        if normalized:
            source_artifact_refs.add(normalized)
    return evidence_item_refs, source_artifact_refs, evidence_item_to_provenance


def _extract_important_claim_candidates(final_artifact: Mapping[str, Any]) -> List[Dict[str, Any]]:
    candidates: List[Dict[str, Any]] = []
    claims = final_artifact.get("claims")
    if isinstance(claims, list):
        for index, claim in enumerate(claims):
            candidates.append({"kind": "claims_list", "path": f"claims[{index}]", "payload": claim})

    for field in _IMPORTANT_TOP_LEVEL_FIELDS:
        value = final_artifact.get(field)
        if isinstance(value, str) and value.strip():
            candidates.append(
                {
                    "kind": "top_level",
                    "path": field,
                    "payload": {
                        "text": value.strip(),
                        "supporting_evidence_refs": list(final_artifact.get(f"{field}_evidence_refs") or []),
                        "source_artifact_refs": list(final_artifact.get(f"{field}_source_artifact_refs") or []),
                    },
                }
            )
    return candidates


def _claim_text(payload: Any) -> str:
    if isinstance(payload, str):
        return payload.strip()
    if isinstance(payload, dict):
        if isinstance(payload.get("text"), str):
            return payload["text"].strip()
        normalized = _normalize(payload)
        return json.dumps(normalized, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return str(payload)


def _as_str_list(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []
    output: List[str] = []
    for item in value:
        normalized = str(item or "").strip()
        if normalized:
            output.append(normalized)
    return output


def _classify_claim(payload: Any, evidence_refs: List[str]) -> str:
    explicit = str((payload or {}).get("claim_classification") or "").strip() if isinstance(payload, dict) else ""
    inferred_links = _as_str_list((payload or {}).get("inferred_from_claim_ids") if isinstance(payload, dict) else [])
    inferred_flag = bool((payload or {}).get("inferred") is True) if isinstance(payload, dict) else False

    derived = "unsupported"
    if evidence_refs:
        derived = "directly_supported"
    elif inferred_flag or inferred_links:
        derived = "inferred"

    if explicit and explicit != derived:
        raise EvidenceBindingError(f"inconsistent claim classification state: explicit={explicit} derived={derived}")
    return explicit or derived


def _validate_claim_state(
    *,
    claim_id: str,
    classification: str,
    evidence_refs: List[str],
    inferred_from_claim_ids: List[str],
    allowed_evidence_refs: Set[str],
    source_artifact_refs: List[str],
    allowed_source_artifact_refs: Set[str],
    evidence_item_to_provenance: Mapping[str, Set[str]],
) -> None:
    if classification not in {"directly_supported", "inferred", "unsupported"}:
        raise EvidenceBindingError(f"unsupported claim classification '{classification}' for claim_id={claim_id}")

    if classification == "directly_supported" and not evidence_refs:
        raise EvidenceBindingError(f"claim classified as directly_supported with no evidence refs: claim_id={claim_id}")
    if classification == "inferred" and evidence_refs:
        raise EvidenceBindingError(f"inferred claim must not include direct evidence refs: claim_id={claim_id}")
    if classification == "unsupported" and (evidence_refs or inferred_from_claim_ids):
        raise EvidenceBindingError(f"unsupported claim contains forbidden refs: claim_id={claim_id}")
    if classification == "directly_supported" and not source_artifact_refs:
        raise EvidenceBindingError(f"directly_supported claim requires source_artifact_refs: claim_id={claim_id}")

    invalid_evidence = sorted(set(evidence_refs) - allowed_evidence_refs)
    if invalid_evidence:
        raise EvidenceBindingError(
            f"evidence refs point to non-existent context items: claim_id={claim_id} refs={invalid_evidence}"
        )

    invalid_artifacts = sorted(set(source_artifact_refs) - allowed_source_artifact_refs)
    if invalid_artifacts:
        raise EvidenceBindingError(
            f"source artifact refs are invalid: claim_id={claim_id} refs={invalid_artifacts}"
        )

    if classification == "directly_supported":
        evidence_provenance_refs: Set[str] = set()
        missing_provenance_refs: List[str] = []
        for evidence_ref in evidence_refs:
            provenance_refs = set(evidence_item_to_provenance.get(evidence_ref) or set())
            if not provenance_refs:
                missing_provenance_refs.append(evidence_ref)
            evidence_provenance_refs.update(provenance_refs)
        if missing_provenance_refs:
            raise EvidenceBindingError(
                f"evidence refs are missing provenance linkage: claim_id={claim_id} refs={sorted(missing_provenance_refs)}"
            )
        orphan_source_refs = sorted(set(source_artifact_refs) - evidence_provenance_refs)
        if orphan_source_refs:
            raise EvidenceBindingError(
                "source artifact refs are not linked to evidence provenance: "
                f"claim_id={claim_id} refs={orphan_source_refs}"
            )


def build_evidence_binding_record(
    *,
    run_id: str,
    trace_id: str,
    final_artifact: Mapping[str, Any],
    validated_context_bundle: Mapping[str, Any],
    parent_multi_pass_record_id: str,
    final_pass_id: str = "final",
    final_pass_output_ref: str = "",
    policy: EvidenceBindingPolicy | None = None,
) -> Dict[str, Any]:
    """Build and validate canonical HS-09 evidence binding record."""
    if not run_id or not trace_id:
        raise EvidenceBindingError("run_id and trace_id are required")
    if not isinstance(final_artifact, Mapping):
        raise EvidenceBindingError("final_artifact must be an object")
    if not isinstance(validated_context_bundle, Mapping):
        raise EvidenceBindingError("validated_context_bundle must be an object")
    if not parent_multi_pass_record_id:
        raise EvidenceBindingError("parent_multi_pass_record_id is required")

    cfg = policy or EvidenceBindingPolicy()
    if cfg.mode not in _ALLOWED_POLICY_MODES:
        raise EvidenceBindingError(f"unsupported policy mode '{cfg.mode}'")

    context_trace_id, context_run_id = _context_trace(validated_context_bundle)
    if context_trace_id != trace_id or context_run_id != run_id:
        raise EvidenceBindingError(
            "validated_context_bundle trace linkage mismatch: "
            f"expected trace_id={trace_id} run_id={run_id} got trace_id={context_trace_id} run_id={context_run_id}"
        )

    allowed_evidence_refs, allowed_source_artifact_refs, evidence_item_to_provenance = _allowed_reference_sets(
        validated_context_bundle
    )
    candidates = _extract_important_claim_candidates(final_artifact)
    if not candidates:
        raise EvidenceBindingError("final_artifact must include at least one governed output claim candidate")

    claim_records: List[Dict[str, Any]] = []
    all_claim_ids: List[str] = []

    for index, candidate in enumerate(candidates):
        payload = candidate["payload"]
        normalized_payload = payload if isinstance(payload, dict) else {"text": _claim_text(payload)}
        claim_text = _claim_text(payload)
        evidence_refs = _as_str_list(normalized_payload.get("supporting_evidence_refs") or normalized_payload.get("evidence_item_refs"))
        source_artifact_refs = _as_str_list(normalized_payload.get("source_artifact_refs"))
        inferred_from_claim_ids = _as_str_list(normalized_payload.get("inferred_from_claim_ids"))

        classification = _classify_claim(normalized_payload, evidence_refs)
        claim_id = deterministic_id(
            prefix="ebc",
            namespace="evidence_binding_claim",
            payload={
                "run_id": run_id,
                "trace_id": trace_id,
                "index": index,
                "path": candidate["path"],
                "claim_text": claim_text,
                "classification": classification,
            },
        )
        _validate_claim_state(
            claim_id=claim_id,
            classification=classification,
            evidence_refs=evidence_refs,
            inferred_from_claim_ids=inferred_from_claim_ids,
            allowed_evidence_refs=allowed_evidence_refs,
            source_artifact_refs=source_artifact_refs,
            allowed_source_artifact_refs=allowed_source_artifact_refs,
            evidence_item_to_provenance=evidence_item_to_provenance,
        )

        claim_record = {
            "claim_id": claim_id,
            "claim_path": str(candidate["path"]),
            "claim_text": claim_text,
            "claim_classification": classification,
            "evidence_item_refs": sorted(set(evidence_refs)),
            "source_artifact_refs": sorted(set(source_artifact_refs)),
            "inferred_from_claim_ids": sorted(set(inferred_from_claim_ids)),
            "pass_id": final_pass_id,
            "trace_id": trace_id,
            "pass_output_ref": final_pass_output_ref or f"multi-pass://{run_id}/{final_pass_id}",
        }
        claim_records.append(claim_record)
        all_claim_ids.append(claim_id)

    known_claim_ids = set(all_claim_ids)
    for claim in claim_records:
        unknown_inference = sorted(set(claim["inferred_from_claim_ids"]) - known_claim_ids)
        if unknown_inference:
            raise EvidenceBindingError(
                f"inferred claim references unknown claim ids: claim_id={claim['claim_id']} refs={unknown_inference}"
            )

    unsupported_claims = [claim["claim_id"] for claim in claim_records if claim["claim_classification"] == "unsupported"]
    inferred_claims = [claim["claim_id"] for claim in claim_records if claim["claim_classification"] == "inferred"]

    if cfg.mode == "required_grounded" and (unsupported_claims or inferred_claims):
        raise EvidenceBindingError(
            "required-grounded mode rejected non-direct claims: "
            f"unsupported={unsupported_claims} inferred={inferred_claims}"
        )
    if cfg.mode == "allow_inferred" and unsupported_claims:
        raise EvidenceBindingError(f"allow_inferred mode rejected unsupported claims: {unsupported_claims}")

    directly_supported_claims = [claim["claim_id"] for claim in claim_records if claim["claim_classification"] == "directly_supported"]
    if not directly_supported_claims:
        raise EvidenceBindingError("governed outputs require at least one directly_supported claim with evidence linkage")

    record_payload = {
        "run_id": run_id,
        "trace_id": trace_id,
        "final_artifact": _normalize(final_artifact),
        "context_item_refs": sorted(allowed_evidence_refs),
        "source_artifact_refs": sorted(allowed_source_artifact_refs),
        "claims": claim_records,
        "policy_mode": cfg.mode,
        "parent_multi_pass_record_id": parent_multi_pass_record_id,
    }
    record = {
        "artifact_type": "evidence_binding_record",
        "schema_version": "1.0.0",
        "record_id": deterministic_id(prefix="ebr", namespace="evidence_binding_record", payload=record_payload),
        "run_id": run_id,
        "trace_id": trace_id,
        "parent_multi_pass_record_id": parent_multi_pass_record_id,
        "policy_mode": cfg.mode,
        "claims": claim_records,
        "summary": {
            "total_claims": len(claim_records),
            "directly_supported_count": sum(1 for c in claim_records if c["claim_classification"] == "directly_supported"),
            "inferred_count": sum(1 for c in claim_records if c["claim_classification"] == "inferred"),
            "unsupported_count": sum(1 for c in claim_records if c["claim_classification"] == "unsupported"),
        },
        "created_at": _deterministic_timestamp(record_payload, stage="evidence_binding_record"),
    }

    _validate_contract(record, "evidence_binding_record")
    return record
