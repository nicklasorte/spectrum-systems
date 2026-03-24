"""HS-X3 Prompt injection defense layer.

Deterministic, explicit-pattern detection at the context->agent seam.
This module classifies instruction-shaped untrusted content and returns a
schema-governed assessment artifact + deterministic enforcement outcome.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from spectrum_systems.utils.deterministic_id import deterministic_id

ASSESSMENT_ARTIFACT_TYPE = "prompt_injection_assessment"
ASSESSMENT_SCHEMA_VERSION = "1.0.0"

DETECTION_STATUS_CLEAN = "clean"
DETECTION_STATUS_SUSPICIOUS = "suspicious"

ACTION_ALLOW_AS_DATA = "allow_as_data"
ACTION_QUARANTINE = "quarantine"
ACTION_BLOCK_BUNDLE = "block_bundle"

_ALLOWED_ACTIONS: Tuple[str, ...] = (
    ACTION_ALLOW_AS_DATA,
    ACTION_QUARANTINE,
    ACTION_BLOCK_BUNDLE,
)

_DEFAULT_POLICY: Dict[str, Any] = {
    "policy_id": "prompt_injection-default-v1",
    "require_assessment": True,
    "on_detection": ACTION_QUARANTINE,
}

_PATTERN_DEFINITIONS: Tuple[Dict[str, Any], ...] = (
    {
        "pattern_id": "pi-override-system-instructions",
        "pattern_class": "override_system_instructions",
        "regex": re.compile(
            r"(?i)\b(ignore|override|replace)\b.{0,48}\b(system|developer|governance|policy)\b.{0,48}\b(instruction|prompt|rule)s?\b"
        ),
    },
    {
        "pattern_id": "pi-ignore-prior-instructions",
        "pattern_class": "ignore_prior_instructions_or_policies",
        "regex": re.compile(r"(?i)\b(ignore|disregard|forget)\b.{0,40}\b(previous|prior|earlier)\b.{0,40}\b(instruction|policy|rule)s?\b"),
    },
    {
        "pattern_id": "pi-reveal-hidden-prompts",
        "pattern_class": "reveal_hidden_prompts_or_policies",
        "regex": re.compile(r"(?i)\b(reveal|print|show|expose|leak)\b.{0,48}\b(hidden|internal|system|developer)\b.{0,48}\b(prompt|policy|instruction)s?\b"),
    },
    {
        "pattern_id": "pi-tool-coercion",
        "pattern_class": "tool_usage_coercion_outside_rules",
        "regex": re.compile(r"(?i)\b(call|invoke|use|run|execute)\b.{0,36}\b(tool|function|shell|command)s?\b.{0,48}\b(ignore|without|bypass)\b.{0,24}\b(policy|permission|approval|rules?)\b"),
    },
)


class PromptInjectionDefenseError(RuntimeError):
    """Fail-closed prompt injection defense error."""


def default_prompt_injection_policy() -> Dict[str, Any]:
    """Return the canonical default policy."""
    return dict(_DEFAULT_POLICY)


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _deterministic_created_at(seed_payload: Mapping[str, Any]) -> str:
    canonical = _canonical(dict(seed_payload))
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    offset_seconds = int(digest[:8], 16) % (365 * 24 * 60 * 60)
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return (base + timedelta(seconds=offset_seconds)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _normalize_policy(policy: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    normalized = dict(default_prompt_injection_policy())
    if policy:
        normalized.update(dict(policy))
    normalized["policy_id"] = str(normalized.get("policy_id") or _DEFAULT_POLICY["policy_id"])
    normalized["require_assessment"] = bool(normalized.get("require_assessment", True))
    normalized["on_detection"] = str(normalized.get("on_detection") or ACTION_QUARANTINE)
    if normalized["on_detection"] not in _ALLOWED_ACTIONS:
        raise PromptInjectionDefenseError(
            f"unsupported prompt injection action '{normalized['on_detection']}'"
        )
    return normalized


def _extract_strings(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        if value.strip():
            yield value
        return
    if isinstance(value, Mapping):
        for key in sorted(value.keys()):
            yield from _extract_strings(value[key])
        return
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        for item in value:
            yield from _extract_strings(item)


def _snippet(text: str, start: int, end: int, radius: int = 40) -> str:
    left = max(0, start - radius)
    right = min(len(text), end + radius)
    return text[left:right].strip()


def assess_prompt_injection(
    *,
    context_bundle: Mapping[str, Any],
    trace_id: str,
    run_id: str,
    policy: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Build deterministic prompt-injection assessment for a context bundle."""
    normalized_policy = _normalize_policy(policy)

    context_bundle_id = str(
        context_bundle.get("context_bundle_id") or context_bundle.get("context_id") or ""
    ).strip()
    if not context_bundle_id:
        raise PromptInjectionDefenseError("context bundle missing context_bundle_id/context_id")

    context_items = list(context_bundle.get("context_items") or [])
    assessed_item_refs: List[str] = []
    detected_patterns: List[Dict[str, Any]] = []

    for item in context_items:
        item_id = str(item.get("item_id") or "").strip()
        if not item_id:
            raise PromptInjectionDefenseError("context item missing item_id")
        assessed_item_refs.append(item_id)

        content_strings = list(_extract_strings(item.get("content")))
        if not content_strings:
            continue

        item_text = "\n".join(content_strings)
        for definition in _PATTERN_DEFINITIONS:
            match = definition["regex"].search(item_text)
            if match is None:
                continue
            detected_patterns.append(
                {
                    "pattern_ref": f"{definition['pattern_id']}:{item_id}",
                    "item_ref": item_id,
                    "pattern_id": definition["pattern_id"],
                    "pattern_class": definition["pattern_class"],
                    "match_snippet": _snippet(item_text, match.start(), match.end()),
                }
            )

    detection_status = (
        DETECTION_STATUS_SUSPICIOUS if detected_patterns else DETECTION_STATUS_CLEAN
    )
    enforcement_action = (
        normalized_policy["on_detection"]
        if detection_status == DETECTION_STATUS_SUSPICIOUS
        else ACTION_ALLOW_AS_DATA
    )

    identity_payload = {
        "context_bundle_id": context_bundle_id,
        "trace_id": trace_id,
        "run_id": run_id,
        "policy": {
            "policy_id": normalized_policy["policy_id"],
            "require_assessment": normalized_policy["require_assessment"],
            "on_detection": normalized_policy["on_detection"],
        },
        "assessed_item_refs": sorted(assessed_item_refs),
        "detection_status": detection_status,
        "detected_patterns": detected_patterns,
        "enforcement_action": enforcement_action,
    }

    assessment_id = deterministic_id(
        prefix="pia",
        namespace="prompt_injection_assessment",
        payload=identity_payload,
    )

    return {
        "artifact_type": ASSESSMENT_ARTIFACT_TYPE,
        "schema_version": ASSESSMENT_SCHEMA_VERSION,
        "assessment_id": assessment_id,
        "created_at": _deterministic_created_at(identity_payload),
        "context_bundle_id": context_bundle_id,
        "assessed_item_refs": sorted(assessed_item_refs),
        "detection_status": detection_status,
        "detected_patterns": detected_patterns,
        "enforcement_action": enforcement_action,
        "policy": {
            "policy_id": normalized_policy["policy_id"],
            "require_assessment": normalized_policy["require_assessment"],
            "on_detection": normalized_policy["on_detection"],
        },
        "trace": {
            "trace_id": str(trace_id),
            "run_id": str(run_id),
            "source_artifact_refs": [f"context_bundle:{context_bundle_id}"],
        },
        "provenance_refs": [f"context_bundle:{context_bundle_id}"],
    }


def evaluate_enforcement_outcome(
    assessment: Mapping[str, Any],
    *,
    policy: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Return deterministic enforcement decision for runtime seam."""
    normalized_policy = _normalize_policy(policy)

    if not assessment:
        raise PromptInjectionDefenseError("prompt injection assessment is required")

    detection_status = str(assessment.get("detection_status") or "")
    enforcement_action = str(assessment.get("enforcement_action") or "")

    if detection_status not in {DETECTION_STATUS_CLEAN, DETECTION_STATUS_SUSPICIOUS}:
        raise PromptInjectionDefenseError(
            f"unsupported detection_status '{detection_status}'"
        )
    if enforcement_action not in _ALLOWED_ACTIONS:
        raise PromptInjectionDefenseError(
            f"unsupported enforcement_action '{enforcement_action}'"
        )

    should_block = enforcement_action in {ACTION_QUARANTINE, ACTION_BLOCK_BUNDLE}
    if detection_status == DETECTION_STATUS_CLEAN and should_block:
        raise PromptInjectionDefenseError(
            "inconsistent enforcement outcome: clean detection cannot quarantine/block"
        )

    if normalized_policy["require_assessment"] and not str(assessment.get("assessment_id") or "").strip():
        raise PromptInjectionDefenseError("assessment required but assessment_id missing")

    return {
        "policy_id": normalized_policy["policy_id"],
        "required": normalized_policy["require_assessment"],
        "detection_status": detection_status,
        "enforcement_action": enforcement_action,
        "should_block": should_block,
        "blocked_reason": (
            f"prompt injection action={enforcement_action}"
            if should_block
            else None
        ),
    }
