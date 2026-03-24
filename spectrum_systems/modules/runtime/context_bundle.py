"""HS-06/HS-07/HS-18 Context Bundle composition and validation.

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
from spectrum_systems.modules.runtime.glossary_registry import (
    GlossaryRegistryError,
    select_glossary_entries,
)
from spectrum_systems.utils.deterministic_id import deterministic_id

BUNDLE_ARTIFACT_TYPE = "context_bundle"
BUNDLE_SCHEMA_VERSION = "2.2.0"

ALLOWED_ITEM_TYPES: Tuple[str, ...] = (
    "primary_input",
    "policy_constraints",
    "retrieved_context",
    "prior_artifact",
    "glossary_definition",
    "unresolved_question",
)
ALLOWED_TRUST_LEVELS: Tuple[str, ...] = ("high", "medium", "low", "untrusted")
ALLOWED_SOURCE_CLASSIFICATIONS: Tuple[str, ...] = (
    "internal",
    "external",
    "inferred",
    "user_provided",
)
SOURCE_CLASSIFICATION_ORDER: Tuple[str, ...] = ALLOWED_SOURCE_CLASSIFICATIONS

ALLOWED_SOURCE_BY_ITEM_TYPE: Dict[str, Tuple[str, ...]] = {
    "primary_input": ("user_provided",),
    "policy_constraints": ("internal",),
    "retrieved_context": ("external",),
    "prior_artifact": ("internal",),
    "glossary_definition": ("internal",),
    "unresolved_question": ("inferred",),
}

ALLOWED_TRUST_BY_SOURCE: Dict[str, Tuple[str, ...]] = {
    "internal": ("high", "medium"),
    "external": ("medium", "low"),
    "inferred": ("low", "untrusted"),
    "user_provided": ("high", "medium", "low", "untrusted"),
}

LEGACY_PRIORITY_ORDER: Tuple[str, ...] = (
    "primary_input",
    "policy_constraints",
    "prior_artifacts",
    "retrieved_context",
    "glossary_definitions",
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


def _validate_item_boundary(item_type: str, trust_level: str, source_classification: str) -> None:
    if item_type not in ALLOWED_ITEM_TYPES:
        raise ContextBundleValidationError(f"unknown item_type '{item_type}'")
    if trust_level not in ALLOWED_TRUST_LEVELS:
        raise ContextBundleValidationError(f"unknown trust_level '{trust_level}'")
    if source_classification not in ALLOWED_SOURCE_CLASSIFICATIONS:
        raise ContextBundleValidationError(
            f"invalid source_classification '{source_classification}'"
        )

    allowed_sources = ALLOWED_SOURCE_BY_ITEM_TYPE[item_type]
    if source_classification not in allowed_sources:
        raise ContextBundleValidationError(
            f"mixed-source violation: item_type '{item_type}' requires source_classification in {allowed_sources}"
        )

    allowed_trust = ALLOWED_TRUST_BY_SOURCE[source_classification]
    if trust_level not in allowed_trust:
        raise ContextBundleValidationError(
            f"inconsistent trust_level '{trust_level}' for source_classification '{source_classification}'"
        )


def _append_item(
    items: List[Dict[str, Any]],
    *,
    item_type: str,
    trust_level: str,
    source_classification: str,
    provenance_refs: Iterable[str],
    content: Any,
) -> None:
    _validate_item_boundary(item_type, trust_level, source_classification)

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


def _build_source_segmentation(items: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    refs_by_class: Dict[str, List[str]] = {
        classification: [] for classification in SOURCE_CLASSIFICATION_ORDER
    }

    for item in items:
        classification = str(item.get("source_classification") or "")
        item_id = str(item.get("item_id") or "").strip()
        if classification not in refs_by_class:
            raise ContextBundleValidationError(
                f"invalid source_classification '{classification}'"
            )
        if not item_id:
            raise ContextBundleValidationError("context item missing required item_id")
        refs_by_class[classification].append(item_id)

    classification_counts = {
        classification: len(refs_by_class[classification])
        for classification in SOURCE_CLASSIFICATION_ORDER
    }
    grounded_refs = sorted(
        refs_by_class["internal"] + refs_by_class["external"] + refs_by_class["user_provided"]
    )
    inferred_refs = sorted(refs_by_class["inferred"])

    return {
        "classification_order": list(SOURCE_CLASSIFICATION_ORDER),
        "classification_counts": classification_counts,
        "item_refs_by_class": {
            classification: refs_by_class[classification]
            for classification in SOURCE_CLASSIFICATION_ORDER
        },
        "grounded_item_refs": grounded_refs,
        "inferred_item_refs": inferred_refs,
    }


def _normalize_glossary_injection_policy(policy: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    normalized = dict(policy or {})
    return {
        "default_domain_scope": str(normalized.get("default_domain_scope") or "general"),
        "allow_deprecated": bool(normalized.get("allow_deprecated", False)),
        "fail_on_missing_required": bool(normalized.get("fail_on_missing_required", True)),
        "enabled": bool(normalized.get("enabled", True)),
    }


def compose_context_items(
    *,
    input_payload: Dict[str, Any],
    policy_constraints: Any,
    retrieved_context: Sequence[Dict[str, Any]],
    prior_artifacts: Sequence[Dict[str, Any]],
    glossary_definitions: Sequence[Dict[str, Any]],
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

    for retrieval_item in _sort_context_objects(retrieved_context):
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

    for entry in sorted(
        [dict(item) for item in glossary_definitions],
        key=lambda item: (
            str(item.get("domain_scope") or ""),
            str(item.get("term_id") or ""),
            str(item.get("version") or ""),
            str(item.get("glossary_entry_id") or ""),
        ),
    ):
        _append_item(
            items,
            item_type="glossary_definition",
            trust_level="medium",
            source_classification="internal",
            provenance_refs=_ensure_provenance_refs(entry, default_ref=entry.get("glossary_entry_id")),
            content=entry,
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
    glossary_registry_entries: Optional[Sequence[Dict[str, Any]]] = None,
    glossary_injection_policy: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if not trace_id or not run_id:
        raise ContextBundleValidationError("trace_id and run_id are required for context bundle linkage")

    injection_policy = _normalize_glossary_injection_policy(glossary_injection_policy)
    glossary_selection = {
        "selected_entries": [],
        "selected_glossary_entry_ids": [],
        "unresolved_terms": [],
        "match_mode": "exact",
        "selection_mode": "explicit_then_exact_text",
    }
    if injection_policy["enabled"] and glossary_terms:
        try:
            glossary_selection = select_glossary_entries(
                glossary_registry_entries or [],
                glossary_terms,
                default_domain_scope=injection_policy["default_domain_scope"],
                allow_deprecated=injection_policy["allow_deprecated"],
                fail_on_missing_required=injection_policy["fail_on_missing_required"],
            )
        except GlossaryRegistryError as exc:
            raise ContextBundleValidationError(f"glossary injection failed: {exc}") from exc

    context_items = compose_context_items(
        input_payload=input_payload,
        policy_constraints=policy_constraints,
        retrieved_context=retrieved_context,
        prior_artifacts=prior_artifacts,
        glossary_definitions=glossary_selection["selected_entries"],
        unresolved_questions=unresolved_questions,
    )
    source_segmentation = _build_source_segmentation(context_items)

    identity_payload = {
        "task_type": task_type,
        "context_items": context_items,
        "source_segmentation": source_segmentation,
        "trace": {"trace_id": trace_id, "run_id": run_id},
        "glossary_selection": {
            "selected_glossary_entry_ids": glossary_selection["selected_glossary_entry_ids"],
            "unresolved_terms": glossary_selection["unresolved_terms"],
            "match_mode": glossary_selection["match_mode"],
        },
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
        "source_segmentation": source_segmentation,
        "primary_input": input_payload,
        "policy_constraints": policy_constraints,
        "retrieved_context": list(retrieved_context),
        "prior_artifacts": list(prior_artifacts),
        "glossary_terms": list(glossary_terms),
        "glossary_definitions": glossary_selection["selected_entries"],
        "glossary_canonicalization": {
            "match_mode": glossary_selection["match_mode"],
            "selection_mode": glossary_selection["selection_mode"],
            "fail_on_missing_required": injection_policy["fail_on_missing_required"],
            "selected_glossary_entry_ids": glossary_selection["selected_glossary_entry_ids"],
            "unresolved_terms": glossary_selection["unresolved_terms"],
        },
        "unresolved_questions": list(unresolved_questions),
        "metadata": {
            "created_at": created_at,
            "retrieval_status": "available" if retrieved_context else "unavailable",
            "source_artifact_ids": sorted(set(source_artifact_ids)),
            "glossary_injection_status": "applied" if glossary_selection["selected_entries"] else "not_requested",
        },
        "token_estimates": {
            "primary_input": _estimate_tokens(input_payload),
            "policy_constraints": _estimate_tokens(policy_constraints),
            "prior_artifacts": _estimate_tokens(prior_artifacts),
            "retrieved_context": _estimate_tokens(retrieved_context),
            "glossary_terms": _estimate_tokens(glossary_terms),
            "glossary_definitions": _estimate_tokens(glossary_selection["selected_entries"]),
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
            "glossary_definitions",
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
        _validate_item_boundary(
            str(item_type or ""),
            str(trust_level or ""),
            str(source_classification or ""),
        )

        idx = item.get("item_index")
        if idx != expected_index:
            raise ContextBundleValidationError(
                f"non-deterministic ordering: expected item_index {expected_index}, got {idx}"
            )

        refs = item.get("provenance_refs")
        if not isinstance(refs, list) or not refs or any(not str(ref).strip() for ref in refs):
            raise ContextBundleValidationError("context item missing required provenance linkage")

    source_segmentation = bundle.get("source_segmentation")
    expected_segmentation = _build_source_segmentation(items)
    if source_segmentation != expected_segmentation:
        raise ContextBundleValidationError(
            "source segmentation mismatch: deterministic segmentation failed or ambiguous source blending detected"
        )

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
