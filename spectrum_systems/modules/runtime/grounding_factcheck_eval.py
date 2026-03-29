"""HS-19 deterministic grounding + fact-check evaluation layer.

This module evaluates HS-09 evidence binding claim records against the final
artifact and validated context bundle using explicit rule-based checks only.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Mapping, Sequence, Set, Tuple

from jsonschema import Draft202012Validator, FormatChecker

from spectrum_systems.contracts import load_schema
from spectrum_systems.utils.deterministic_id import deterministic_id


class GroundingFactCheckEvalError(RuntimeError):
    """Fail-closed runtime error for HS-19 grounding/fact-check eval."""


@dataclass(frozen=True)
class GroundingFactCheckPolicy:
    """Deterministic policy for HS-19 claim-level evaluation behavior."""

    required: bool = True
    allow_inferred_claims: bool = False
    allow_unsupported_claims: bool = False
    fail_on_fact_check_fail: bool = True


_FAILURE_CLASSES = {
    "fact_check_fail",
    "semantic_error",
    "evidence_mismatch",
    "unsupported_grounded_claim",
    "incomplete_grounding",
}


def _deterministic_timestamp(payload: Mapping[str, Any], *, stage: str) -> str:
    seed = json.dumps({"stage": stage, "payload": payload}, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    offset_seconds = int(digest[:8], 16) % (365 * 24 * 60 * 60)
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return (base + timedelta(seconds=offset_seconds)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _validate_contract(instance: Dict[str, Any], schema_name: str) -> None:
    schema = load_schema(schema_name)
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(instance)


def _tokenize(text: str) -> Set[str]:
    return {token for token in re.findall(r"[a-z0-9]+", text.lower()) if len(token) >= 3}


def _context_item_index(validated_context_bundle: Mapping[str, Any]) -> Dict[str, str]:
    index: Dict[str, str] = {}
    for item in list(validated_context_bundle.get("context_items") or []):
        item_id = str(item.get("item_id") or "").strip()
        if not item_id:
            continue
        content = item.get("content")
        if isinstance(content, str):
            index[item_id] = content
        elif isinstance(content, Mapping):
            if isinstance(content.get("text"), str):
                index[item_id] = content["text"]
            else:
                index[item_id] = json.dumps(content, sort_keys=True, ensure_ascii=False)
        else:
            index[item_id] = json.dumps(content, sort_keys=True, ensure_ascii=False)
    return index


def _glossary_term_index(validated_context_bundle: Mapping[str, Any]) -> Dict[str, str]:
    terms: Dict[str, str] = {}
    for definition in list(validated_context_bundle.get("glossary_definitions") or []):
        glossary_entry_id = str(definition.get("glossary_entry_id") or "").strip()
        canonical_term = str(definition.get("canonical_term") or "").strip()
        if glossary_entry_id and canonical_term:
            terms[glossary_entry_id] = canonical_term
    return terms


def _resolve_claim_payload(final_artifact: Mapping[str, Any], claim_path: str) -> Mapping[str, Any]:
    if claim_path.startswith("claims[") and claim_path.endswith("]"):
        index_text = claim_path[len("claims[") : -1]
        if index_text.isdigit():
            claims = final_artifact.get("claims")
            idx = int(index_text)
            if isinstance(claims, list) and 0 <= idx < len(claims) and isinstance(claims[idx], Mapping):
                return claims[idx]
        return {}
    payload = final_artifact.get(claim_path)
    return payload if isinstance(payload, Mapping) else {}


def _evidence_overlap_score(claim_text: str, evidence_texts: Sequence[str]) -> bool:
    claim_tokens = _tokenize(claim_text)
    if not claim_tokens:
        return False
    evidence_tokens: Set[str] = set()
    for text in evidence_texts:
        evidence_tokens.update(_tokenize(text))
    return bool(claim_tokens & evidence_tokens)


def _validate_inputs(
    *,
    run_id: str,
    trace_id: str,
    source_artifact_id: str,
    evidence_binding_record: Mapping[str, Any],
    final_artifact: Mapping[str, Any],
    validated_context_bundle: Mapping[str, Any],
) -> None:
    if not run_id or not trace_id:
        raise GroundingFactCheckEvalError("run_id and trace_id are required")
    if not source_artifact_id:
        raise GroundingFactCheckEvalError("source_artifact_id is required")
    if not isinstance(evidence_binding_record, Mapping):
        raise GroundingFactCheckEvalError("evidence_binding_record must be an object")
    if not isinstance(final_artifact, Mapping):
        raise GroundingFactCheckEvalError("final_artifact must be an object")
    if not isinstance(validated_context_bundle, Mapping):
        raise GroundingFactCheckEvalError("validated_context_bundle must be an object")

    if str(evidence_binding_record.get("artifact_type") or "") != "evidence_binding_record":
        raise GroundingFactCheckEvalError("evidence_binding_record artifact_type must be evidence_binding_record")
    if str(evidence_binding_record.get("trace_id") or "") != trace_id:
        raise GroundingFactCheckEvalError("evidence_binding_record trace_id mismatch")


def build_grounding_factcheck_eval(
    *,
    run_id: str,
    trace_id: str,
    source_artifact_id: str,
    final_artifact: Mapping[str, Any],
    evidence_binding_record: Mapping[str, Any],
    validated_context_bundle: Mapping[str, Any],
    parent_multi_pass_record_id: str,
    final_pass_output_ref: str,
    policy: GroundingFactCheckPolicy | None = None,
) -> Dict[str, Any]:
    """Build deterministic HS-19 grounding/fact-check eval artifact."""
    _validate_inputs(
        run_id=run_id,
        trace_id=trace_id,
        source_artifact_id=source_artifact_id,
        evidence_binding_record=evidence_binding_record,
        final_artifact=final_artifact,
        validated_context_bundle=validated_context_bundle,
    )
    if not parent_multi_pass_record_id:
        raise GroundingFactCheckEvalError("parent_multi_pass_record_id is required")

    cfg = policy or GroundingFactCheckPolicy()
    claim_entries = list(evidence_binding_record.get("claims") or [])

    context_index = _context_item_index(validated_context_bundle)
    glossary_term_index = _glossary_term_index(validated_context_bundle)
    selected_glossary_ids = {
        str(item)
        for item in list(((validated_context_bundle.get("glossary_canonicalization") or {}).get("selected_glossary_entry_ids") or []))
        if str(item).strip()
    }

    claim_results: List[Dict[str, Any]] = []
    aggregate_failures: Set[str] = set()

    for claim in claim_entries:
        claim_id = str(claim.get("claim_id") or "").strip()
        if not claim_id:
            raise GroundingFactCheckEvalError("invalid claim refs: claim_id missing")

        classification = str(claim.get("claim_classification") or "").strip()
        if classification not in {"directly_supported", "inferred", "unsupported"}:
            raise GroundingFactCheckEvalError(f"invalid claim refs: unsupported claim classification for {claim_id}")

        evidence_refs = sorted({str(ref or "").strip() for ref in list(claim.get("evidence_item_refs") or []) if str(ref or "").strip()})
        claim_text = str(claim.get("claim_text") or "").strip()
        if not claim_text:
            raise GroundingFactCheckEvalError(f"invalid claim refs: empty claim_text for {claim_id}")

        claim_failures: Set[str] = set()
        rationale_code = "ok_supported"

        if classification == "directly_supported":
            if not evidence_refs:
                claim_failures.update({"incomplete_grounding", "unsupported_grounded_claim"})
                rationale_code = "direct_missing_evidence_refs"
            else:
                missing_refs = sorted(ref for ref in evidence_refs if ref not in context_index)
                if missing_refs:
                    claim_failures.update({"incomplete_grounding", "evidence_mismatch"})
                    rationale_code = "direct_invalid_evidence_ref"
                else:
                    evidence_texts = [context_index[ref] for ref in evidence_refs]
                    if not _evidence_overlap_score(claim_text, evidence_texts):
                        claim_failures.update({"fact_check_fail", "evidence_mismatch"})
                        rationale_code = "direct_text_evidence_mismatch"

        elif classification == "inferred":
            rationale_code = "inferred_retained"
            if evidence_refs:
                claim_failures.add("evidence_mismatch")
                rationale_code = "inferred_masquerades_as_direct"
            if not cfg.allow_inferred_claims:
                claim_failures.add("incomplete_grounding")
                if rationale_code == "inferred_retained":
                    rationale_code = "inferred_disallowed_by_policy"

        elif classification == "unsupported":
            rationale_code = "unsupported_claim"
            if not cfg.allow_unsupported_claims:
                claim_failures.update({"unsupported_grounded_claim", "incomplete_grounding"})
                rationale_code = "unsupported_disallowed_by_policy"

        claim_payload = _resolve_claim_payload(final_artifact, str(claim.get("claim_path") or ""))
        canonical_refs = sorted(
            {
                str(ref or "").strip()
                for ref in list(claim_payload.get("canonical_term_refs") or [])
                if str(ref or "").strip()
            }
        )
        if canonical_refs:
            for term_ref in canonical_refs:
                if term_ref not in selected_glossary_ids:
                    claim_failures.add("semantic_error")
                    rationale_code = "canonical_ref_not_selected"
                    continue
                canonical_term = glossary_term_index.get(term_ref, "")
                if canonical_term and canonical_term.lower() not in claim_text.lower():
                    claim_failures.add("semantic_error")
                    rationale_code = "canonical_term_missing_in_claim_text"

        invalid_failure_classes = sorted(claim_failures - _FAILURE_CLASSES)
        if invalid_failure_classes:
            raise GroundingFactCheckEvalError(
                f"inconsistent eval state: unknown failure classes for {claim_id}: {invalid_failure_classes}"
            )

        if not claim_failures:
            status = "pass"
        elif "semantic_error" in claim_failures and claim_failures == {"semantic_error"}:
            status = "warn"
        else:
            status = "fail"

        claim_result = {
            "claim_id": claim_id,
            "claim_classification_from_binding": classification,
            "eval_status": status,
            "failure_classes": sorted(claim_failures),
            "supporting_evidence_refs_checked": evidence_refs,
            "rationale_code": rationale_code,
        }
        claim_results.append(claim_result)
        aggregate_failures.update(claim_failures)

    overall_status = "pass"
    if any(result["eval_status"] == "fail" for result in claim_results):
        overall_status = "fail"
    elif any(result["eval_status"] == "warn" for result in claim_results):
        overall_status = "warn"

    if cfg.fail_on_fact_check_fail and "fact_check_fail" in aggregate_failures:
        overall_status = "fail"

    eval_payload = {
        "run_id": run_id,
        "trace_id": trace_id,
        "source_artifact_id": source_artifact_id,
        "evidence_binding_record_id": str(evidence_binding_record.get("record_id") or ""),
        "claim_results": claim_results,
        "policy": {
            "required": cfg.required,
            "allow_inferred_claims": cfg.allow_inferred_claims,
            "allow_unsupported_claims": cfg.allow_unsupported_claims,
            "fail_on_fact_check_fail": cfg.fail_on_fact_check_fail,
        },
        "parent_multi_pass_record_id": parent_multi_pass_record_id,
        "final_pass_output_ref": final_pass_output_ref,
    }

    artifact = {
        "artifact_type": "grounding_factcheck_eval",
        "schema_version": "1.0.0",
        "eval_id": deterministic_id(prefix="gfe", namespace="grounding_factcheck_eval", payload=eval_payload),
        "run_id": run_id,
        "trace_id": trace_id,
        "created_at": _deterministic_timestamp(eval_payload, stage="grounding_factcheck_eval"),
        "source_artifact_id": source_artifact_id,
        "evidence_binding_record_id": str(evidence_binding_record.get("record_id") or ""),
        "overall_status": overall_status,
        "failure_classes": sorted(aggregate_failures),
        "claim_results": claim_results,
        "trace_linkage": {
            "run_id": run_id,
            "trace_id": trace_id,
            "parent_multi_pass_record_id": parent_multi_pass_record_id,
            "final_pass_output_ref": final_pass_output_ref,
        },
        "policy": eval_payload["policy"],
    }

    _validate_contract(artifact, "grounding_factcheck_eval")

    if artifact["overall_status"] == "pass" and artifact["failure_classes"]:
        raise GroundingFactCheckEvalError("inconsistent eval state: pass status cannot include failure classes")

    return artifact
