"""HS-06 Context Bundle v2 (Typed + Trusted).

Narrow deterministic composition + fail-closed validation boundary for runtime
context bundles. This module intentionally does not perform retrieval/ranking.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import ValidationError

from spectrum_systems.contracts import load_schema
from spectrum_systems.utils.deterministic_id import deterministic_id

BUNDLE_ARTIFACT_TYPE = "context_bundle"
BUNDLE_SCHEMA_VERSION = "2.0.0"

ALLOWED_ITEM_TYPES: Tuple[str, ...] = (
    "primary_input",
    "policy_constraints",
    "retrieved_context",
    "prior_artifact",
    "glossary_term",
    "unresolved_question",
)
ALLOWED_TRUST_LEVELS: Tuple[str, ...] = ("high", "medium", "low", "untrusted")
ALLOWED_SOURCE_CLASSIFICATIONS: Tuple[str, ...] = (
    "internal",
    "external",
    "inferred",
    "user_provided",
)

LEGACY_PRIORITY_ORDER: Tuple[str, ...] = (
    "primary_input",
    "policy_constraints",
    "prior_artifacts",
    "retrieved_context",
    "glossary_terms",
    "unresolved_questions",
)


class ContextBundleValidationError(RuntimeError):
    """Fail-closed validation/composition error for context bundles."""


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _deterministic_created_at(seed_payload: Dict[str, Any]) -> str:
    canonical = _canonical(seed_payload)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    offset_seconds = int(digest[:8], 16) % (365 * 24 * 60 * 60)
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return (base + timedelta(seconds=offset_seconds)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sort_context_objects(values: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return sorted(
        [dict(v) for v in values],
        key=lambda item: (
            str(item.get("artifact_id") or ""),
            str(item.get("content") or ""),
            _canonical(item.get("provenance") or {}),
        ),
    )


def _ensure_provenance_refs(value: Any, *, default_ref: Optional[str] = None) -> List[str]:
    refs: List[str] = []
    if isinstance(value, dict):
        for key in ("provenance_ref", "provenance_id", "id", "artifact_id", "source_id"):
            candidate = value.get(key)
            if isinstance(candidate, str) and candidate.strip():
                refs.append(candidate.strip())
        raw_refs = value.get("provenance_refs")
        if isinstance(raw_refs, list):
            for candidate in raw_refs:
                if isinstance(candidate, str) and candidate.strip():
                    refs.append(candidate.strip())
    elif isinstance(value, str) and value.strip():
        refs.append(value.strip())

    if default_ref:
        refs.append(default_ref)

    normalized = sorted(set(refs))
    if not normalized:
        raise ContextBundleValidationError("context item missing required provenance linkage")
    return normalized


def _append_item(
    items: List[Dict[str, Any]],
    *,
    item_type: str,
    trust_level: str,
    source_classification: str,
    provenance_refs: Iterable[str],
    content: Any,
) -> None:
    if item_type not in ALLOWED_ITEM_TYPES:
        raise ContextBundleValidationError(f"unknown item_type '{item_type}'")
    if trust_level not in ALLOWED_TRUST_LEVELS:
        raise ContextBundleValidationError(f"unknown trust_level '{trust_level}'")
    if source_classification not in ALLOWED_SOURCE_CLASSIFICATIONS:
        raise ContextBundleValidationError(
            f"invalid source_classification '{source_classification}'"
        )

    item_index = len(items)
    refs = sorted(set(str(ref).strip() for ref in provenance_refs if str(ref).strip()))
    if not refs:
        raise ContextBundleValidationError("context item missing required provenance linkage")

    identity_payload = {
        "item_index": item_index,
        "item_type": item_type,
        "trust_level": trust_level,
        "source_classification": source_classification,
        "provenance_refs": refs,
        "content": content,
    }
    items.append(
        {
            "item_index": item_index,
            "item_id": deterministic_id(
                prefix="ctxi",
                namespace="context_bundle_item",
                payload=identity_payload,
            ),
            "item_type": item_type,
            "trust_level": trust_level,
            "source_classification": source_classification,
            "provenance_refs": refs,
            "content": content,
        }
    )


def compose_context_items(
    *,
    input_payload: Dict[str, Any],
    policy_constraints: Any,
    retrieved_context: Sequence[Dict[str, Any]],
    prior_artifacts: Sequence[Dict[str, Any]],
    glossary_terms: Sequence[Any],
    unresolved_questions: Sequence[Any],
) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []

    _append_item(
        items,
        item_type="primary_input",
        trust_level="high",
        source_classification="user_provided",
        provenance_refs=_ensure_provenance_refs(input_payload, default_ref="input_payload"),
        content=input_payload,
    )

    _append_item(
        items,
        item_type="policy_constraints",
        trust_level="high",
        source_classification="internal",
        provenance_refs=_ensure_provenance_refs(policy_constraints, default_ref="policy_constraints"),
        content=policy_constraints,
    )

    for idx, retrieval_item in enumerate(_sort_context_objects(retrieved_context)):
        provenance = retrieval_item.get("provenance")
        refs = _ensure_provenance_refs(provenance, default_ref=str(retrieval_item.get("artifact_id") or ""))
        _append_item(
            items,
            item_type="retrieved_context",
            trust_level="medium",
            source_classification="external",
            provenance_refs=refs,
            content=retrieval_item,
        )

    for artifact in _sort_context_objects(prior_artifacts):
        artifact_id = str(artifact.get("artifact_id") or "").strip()
        if not artifact_id:
            raise ContextBundleValidationError("prior_artifacts item missing artifact_id")
        _append_item(
            items,
            item_type="prior_artifact",
            trust_level="high",
            source_classification="internal",
            provenance_refs=[artifact_id],
            content=artifact,
        )

    for idx, term in enumerate(glossary_terms):
        _append_item(
            items,
            item_type="glossary_term",
            trust_level="medium",
            source_classification="internal",
            provenance_refs=[f"glossary_term:{idx}"],
            content=term,
        )

    for idx, question in enumerate(unresolved_questions):
        _append_item(
            items,
            item_type="unresolved_question",
            trust_level="low",
            source_classification="inferred",
            provenance_refs=[f"unresolved_question:{idx}"],
            content=question,
        )

    return items




def _estimate_tokens(value: Any) -> int:
    if value is None:
        return 0
    payload = value if isinstance(value, str) else _canonical(value)
    if not payload:
        return 0
    return max(1, int(len(payload) / 4.0))


def compose_context_bundle(
    *,
    task_type: str,
    input_payload: Dict[str, Any],
    policy_constraints: Any,
    retrieved_context: Sequence[Dict[str, Any]],
    prior_artifacts: Sequence[Dict[str, Any]],
    glossary_terms: Sequence[Any],
    unresolved_questions: Sequence[Any],
    source_artifact_ids: Sequence[str],
    trace_id: str,
    run_id: str,
) -> Dict[str, Any]:
    if not trace_id or not run_id:
        raise ContextBundleValidationError("trace_id and run_id are required for context bundle linkage")

    context_items = compose_context_items(
        input_payload=input_payload,
        policy_constraints=policy_constraints,
        retrieved_context=retrieved_context,
        prior_artifacts=prior_artifacts,
        glossary_terms=glossary_terms,
        unresolved_questions=unresolved_questions,
    )

    identity_payload = {
        "task_type": task_type,
        "context_items": context_items,
        "trace": {"trace_id": trace_id, "run_id": run_id},
    }
    context_bundle_id = deterministic_id(
        prefix="ctx",
        namespace="context_bundle_v2",
        payload=identity_payload,
    )
    created_at = _deterministic_created_at(identity_payload)

    bundle = {
        "artifact_type": BUNDLE_ARTIFACT_TYPE,
        "schema_version": BUNDLE_SCHEMA_VERSION,
        "context_bundle_id": context_bundle_id,
        "context_id": context_bundle_id,
        "task_type": task_type,
        "created_at": created_at,
        "trace": {
            "trace_id": trace_id,
            "run_id": run_id,
        },
        "context_items": context_items,
        "primary_input": input_payload,
        "policy_constraints": policy_constraints,
        "retrieved_context": list(retrieved_context),
        "prior_artifacts": list(prior_artifacts),
        "glossary_terms": list(glossary_terms),
        "unresolved_questions": list(unresolved_questions),
        "metadata": {
            "created_at": created_at,
            "retrieval_status": "available" if retrieved_context else "unavailable",
            "source_artifact_ids": sorted(set(source_artifact_ids)),
        },
        "token_estimates": {
            "primary_input": _estimate_tokens(input_payload),
            "policy_constraints": _estimate_tokens(policy_constraints),
            "prior_artifacts": _estimate_tokens(prior_artifacts),
            "retrieved_context": _estimate_tokens(retrieved_context),
            "glossary_terms": _estimate_tokens(glossary_terms),
            "unresolved_questions": _estimate_tokens(unresolved_questions),
            "total": 0,
        },
        "truncation_log": [],
        "priority_order": list(LEGACY_PRIORITY_ORDER),
    }
    bundle["token_estimates"]["total"] = sum(
        bundle["token_estimates"][name]
        for name in (
            "primary_input",
            "policy_constraints",
            "prior_artifacts",
            "retrieved_context",
            "glossary_terms",
            "unresolved_questions",
        )
    )
    validate_context_bundle(bundle)
    return bundle


def validate_context_bundle(bundle: Dict[str, Any]) -> Dict[str, Any]:
    items = bundle.get("context_items")
    if not isinstance(items, list) or not items:
        raise ContextBundleValidationError("context_items must be a non-empty ordered list")

    for expected_index, item in enumerate(items):
        if not isinstance(item, dict):
            raise ContextBundleValidationError("context_items must contain object items")
        item_type = item.get("item_type")
        trust_level = item.get("trust_level")
        source_classification = item.get("source_classification")
        if item_type not in ALLOWED_ITEM_TYPES:
            raise ContextBundleValidationError(f"unknown item_type '{item_type}'")
        if trust_level not in ALLOWED_TRUST_LEVELS:
            raise ContextBundleValidationError(f"unknown trust_level '{trust_level}'")
        if source_classification not in ALLOWED_SOURCE_CLASSIFICATIONS:
            raise ContextBundleValidationError(
                f"invalid source_classification '{source_classification}'"
            )

        idx = item.get("item_index")
        if idx != expected_index:
            raise ContextBundleValidationError(
                f"non-deterministic ordering: expected item_index {expected_index}, got {idx}"
            )

        refs = item.get("provenance_refs")
        if not isinstance(refs, list) or not refs or any(not str(ref).strip() for ref in refs):
            raise ContextBundleValidationError("context item missing required provenance linkage")

    if bundle.get("context_bundle_id") != bundle.get("context_id"):
        raise ContextBundleValidationError("context_bundle_id and context_id must match")

    trace = bundle.get("trace") or {}
    if not str(trace.get("trace_id") or "").strip() or not str(trace.get("run_id") or "").strip():
        raise ContextBundleValidationError("context bundle trace linkage is required")

    schema = load_schema("context_bundle")
    try:
        Draft202012Validator(schema, format_checker=FormatChecker()).validate(bundle)
    except ValidationError as exc:
        raise ContextBundleValidationError(str(exc.message)) from exc

    return bundle


__all__ = [
    "ALLOWED_ITEM_TYPES",
    "ALLOWED_SOURCE_CLASSIFICATIONS",
    "ALLOWED_TRUST_LEVELS",
    "ContextBundleValidationError",
    "compose_context_bundle",
    "compose_context_items",
    "validate_context_bundle",
]
