"""Deterministic Review Intelligence Layer (RIL-002) signal classification engine."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from jsonschema import Draft202012Validator

from spectrum_systems.contracts import load_schema
from spectrum_systems.utils.deterministic_id import deterministic_id


class ReviewSignalClassificationError(ValueError):
    """Raised when a review_signal_artifact cannot be deterministically classified."""


_ALLOWED_SIGNAL_CLASSES = (
    "control_escalation",
    "enforcement_block",
    "roadmap_priority",
    "drift_watch",
    "recovery_followup",
    "governance_attention",
)


@dataclass(frozen=True)
class _SignalRule:
    signal_class: str
    signal_priority: str
    rationale: str


def _normalize_text(value: str) -> str:
    return value.strip().lower()


def _validate_source_artifact(review_signal_artifact: dict[str, Any]) -> None:
    validator = Draft202012Validator(load_schema("review_signal_artifact"))
    errors = sorted(validator.iter_errors(review_signal_artifact), key=lambda err: str(list(err.absolute_path)))
    if errors:
        details = "; ".join(error.message for error in errors)
        raise ReviewSignalClassificationError(f"review_signal_artifact failed schema validation: {details}")


def _required_keys_present(review_signal_artifact: dict[str, Any]) -> None:
    required_fields = (
        "review_signal_id",
        "source_review_path",
        "source_action_tracker_path",
        "review_date",
        "system_scope",
        "severity_counts",
        "action_items",
        "provenance",
    )
    for field in required_fields:
        if field not in review_signal_artifact:
            raise ReviewSignalClassificationError(f"missing required field: {field}")


def _build_action_item_index(action_items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for item in action_items:
        item_id = str(item.get("id", "")).strip()
        if not item_id:
            raise ReviewSignalClassificationError("all action_items must include a non-empty id")
        if item_id in index:
            raise ReviewSignalClassificationError(f"duplicate action_item id: {item_id}")
        index[item_id] = item
    return index


def _ensure_item_integrity(
    *,
    bucket_name: str,
    items: list[dict[str, Any]],
    expected_severity: str,
    action_index: dict[str, dict[str, Any]],
) -> None:
    for item in items:
        item_id = str(item.get("id", "")).strip()
        if not item_id:
            raise ReviewSignalClassificationError(f"{bucket_name} items require non-empty id")
        if item_id not in action_index:
            raise ReviewSignalClassificationError(f"{bucket_name} item missing from action_items: {item_id}")
        severity = str(item.get("severity", "")).strip().lower()
        if severity != expected_severity:
            raise ReviewSignalClassificationError(
                f"{bucket_name} item {item_id} has unexpected severity {severity!r}; expected {expected_severity!r}"
            )
        trace = item.get("trace")
        if not isinstance(trace, dict):
            raise ReviewSignalClassificationError(f"{bucket_name} item {item_id} missing trace object")
        if not str(trace.get("source_path", "")).strip():
            raise ReviewSignalClassificationError(f"{bucket_name} item {item_id} missing trace.source_path")
        if not isinstance(trace.get("line_number"), int):
            raise ReviewSignalClassificationError(f"{bucket_name} item {item_id} missing trace.line_number")


def _signal_rules_for_item(
    *,
    bucket_name: str,
    item: dict[str, Any],
    blocker_ids: set[str],
    system_scope: str,
    reason_codes: set[str],
) -> list[_SignalRule]:
    item_id = str(item["id"])
    description = _normalize_text(str(item.get("description", "")))
    recommended_action = _normalize_text(str(item.get("recommended_action", "")))
    status = _normalize_text(str(item.get("status", "")))
    signal_rules: list[_SignalRule] = []

    is_blocker = item_id in blocker_ids or "block" in description
    is_unresolved = status in {"open", "unresolved", "reopened", "blocked"}
    mentions_recovery = any(token in f"{description} {recommended_action}" for token in ("recovery", "repair", "remediation", "fre"))
    mentions_tpa_pqx = any(token in f"{system_scope} {description} {recommended_action}" for token in ("tpa", "pqx", "control"))

    if bucket_name == "critical_risks":
        if is_blocker:
            signal_rules.append(_SignalRule("enforcement_block", "P0", "Critical blocker item in action tracker"))
            signal_rules.append(_SignalRule("control_escalation", "P0", "Critical blocker requires control escalation"))
        else:
            signal_rules.append(_SignalRule("control_escalation", "P1", "Critical non-blocking risk requires escalation"))
            signal_rules.append(_SignalRule("governance_attention", "P1", "Critical risk requires governance attention"))

    elif bucket_name == "high_priority_items":
        signal_rules.append(_SignalRule("roadmap_priority", "P1", "High-priority item mapped to roadmap priority"))
        signal_rules.append(_SignalRule("governance_attention", "P2", "High-priority governance risk from review signal"))
        if is_blocker:
            signal_rules.append(_SignalRule("enforcement_block", "P0", "High-priority item explicitly marked as blocker"))
        elif mentions_tpa_pqx:
            signal_rules.append(_SignalRule("control_escalation", "P1", "High-priority control-boundary finding"))

    elif bucket_name == "medium_priority_items":
        if is_unresolved:
            signal_rules.append(_SignalRule("drift_watch", "monitor", "Medium unresolved item mapped to drift watch"))
        else:
            signal_rules.append(_SignalRule("governance_attention", "P2", "Medium item requires governance visibility"))

    else:
        raise ReviewSignalClassificationError(f"unsupported bucket: {bucket_name}")

    if mentions_recovery or "R8" in reason_codes:
        signal_rules.append(_SignalRule("recovery_followup", "P2", "Recovery-related finding requires follow-up"))

    if mentions_tpa_pqx and all(rule.signal_class != "control_escalation" for rule in signal_rules):
        signal_rules.append(_SignalRule("control_escalation", "P1", "TPA/PQX control-boundary finding"))

    deduped: list[_SignalRule] = []
    seen: set[tuple[str, str, str]] = set()
    for rule in signal_rules:
        key = (rule.signal_class, rule.signal_priority, rule.rationale)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(rule)
    return deduped


def _classify_item(
    *,
    review_signal_id: str,
    item: dict[str, Any],
    bucket_name: str,
    blocker_ids: set[str],
    system_scope: str,
    reason_codes: set[str],
) -> list[dict[str, Any]]:
    rules = _signal_rules_for_item(
        bucket_name=bucket_name,
        item=item,
        blocker_ids=blocker_ids,
        system_scope=system_scope,
        reason_codes=reason_codes,
    )
    trace = item["trace"]
    source_item_id = str(item["id"])

    signals: list[dict[str, Any]] = []
    for rule in rules:
        if rule.signal_class not in _ALLOWED_SIGNAL_CLASSES:
            raise ReviewSignalClassificationError(f"unsupported signal class generated: {rule.signal_class}")
        signal_seed = {
            "review_signal_id": review_signal_id,
            "source_item_id": source_item_id,
            "signal_class": rule.signal_class,
        }
        signals.append(
            {
                "signal_id": deterministic_id(prefix="rsi", namespace="review_control_signal_item", payload=signal_seed),
                "source_item_id": source_item_id,
                "signal_class": rule.signal_class,
                "signal_priority": rule.signal_priority,
                "severity": str(item["severity"]),
                "affected_systems": [system_scope],
                "rationale": rule.rationale,
                "trace_refs": [
                    {
                        "source_path": str(trace["source_path"]),
                        "line_number": int(trace["line_number"]),
                        "source_excerpt": str(trace["source_excerpt"]),
                    }
                ],
            }
        )
    return signals


def classify_review_signal(review_signal_artifact: dict[str, Any]) -> dict[str, Any]:
    """Classify a ``review_signal_artifact`` into deterministic ``review_control_signal_artifact`` output."""
    _required_keys_present(review_signal_artifact)
    _validate_source_artifact(review_signal_artifact)

    source_review_path = str(review_signal_artifact["source_review_path"]).strip()
    source_action_tracker_path = str(review_signal_artifact["source_action_tracker_path"]).strip()
    if not source_review_path or not source_action_tracker_path:
        raise ReviewSignalClassificationError("source provenance paths must be non-empty")

    review_signal_id = str(review_signal_artifact["review_signal_id"]).strip()
    if not review_signal_id:
        raise ReviewSignalClassificationError("review_signal_id must be non-empty")

    system_scope = str(review_signal_artifact["system_scope"]).strip()
    blocker_ids = {str(item).strip() for item in review_signal_artifact.get("blocker_ids", []) if str(item).strip()}
    reason_codes = {str(code).strip() for code in review_signal_artifact.get("extracted_reason_codes", []) if str(code).strip()}

    action_items = review_signal_artifact["action_items"]
    action_index = _build_action_item_index(action_items)

    critical_items = review_signal_artifact.get("critical_risks", [])
    high_items = review_signal_artifact.get("high_priority_items", [])
    medium_items = review_signal_artifact.get("medium_priority_items", [])

    _ensure_item_integrity(
        bucket_name="critical_risks",
        items=critical_items,
        expected_severity="critical",
        action_index=action_index,
    )
    _ensure_item_integrity(
        bucket_name="high_priority_items",
        items=high_items,
        expected_severity="high",
        action_index=action_index,
    )
    _ensure_item_integrity(
        bucket_name="medium_priority_items",
        items=medium_items,
        expected_severity="medium",
        action_index=action_index,
    )

    all_signals: list[dict[str, Any]] = []
    classification_order = (
        ("critical_risks", critical_items),
        ("high_priority_items", high_items),
        ("medium_priority_items", medium_items),
    )
    for bucket_name, items in classification_order:
        for item in sorted(items, key=lambda value: str(value["id"])):
            all_signals.extend(
                _classify_item(
                    review_signal_id=review_signal_id,
                    item=item,
                    bucket_name=bucket_name,
                    blocker_ids=blocker_ids,
                    system_scope=system_scope,
                    reason_codes=reason_codes,
                )
            )

    all_signals = sorted(all_signals, key=lambda signal: (signal["source_item_id"], signal["signal_class"], signal["signal_id"]))

    blocker_signal_ids = [signal["signal_id"] for signal in all_signals if signal["signal_class"] == "enforcement_block"]
    escalation_present = any(signal["signal_class"] == "control_escalation" for signal in all_signals)
    counts_by_class: dict[str, int] = {}
    for signal in all_signals:
        key = str(signal["signal_class"])
        counts_by_class[key] = counts_by_class.get(key, 0) + 1

    control_seed = {
        "review_signal_id": review_signal_id,
        "review_date": review_signal_artifact["review_date"],
        "signal_ids": [signal["signal_id"] for signal in all_signals],
    }

    output = {
        "artifact_type": "review_control_signal_artifact",
        "schema_version": "1.0.0",
        "review_control_signal_id": deterministic_id(
            prefix="rca",
            namespace="review_control_signal_artifact",
            payload=control_seed,
        ),
        "source_review_signal_ref": review_signal_id,
        "source_review_path": source_review_path,
        "source_action_tracker_path": source_action_tracker_path,
        "review_date": str(review_signal_artifact["review_date"]),
        "system_scope": system_scope,
        "overall_verdict": review_signal_artifact.get("overall_verdict"),
        "classified_signals": all_signals,
        "blocker_present": len(blocker_signal_ids) > 0,
        "blocker_signal_ids": blocker_signal_ids,
        "escalation_present": escalation_present,
        "severity_summary": dict(review_signal_artifact["severity_counts"]),
        "signal_counts_by_class": counts_by_class,
        "emitted_at": str(review_signal_artifact["emitted_at"]),
        "provenance": {
            "classifier": "review_signal_classifier",
            "deterministic_hash_basis": "canonical-json-sha256",
            "source_review_signal_id": review_signal_id,
            "source_review_hash": review_signal_artifact["provenance"]["source_review_hash"],
            "source_action_tracker_hash": review_signal_artifact["provenance"]["source_action_tracker_hash"],
        },
    }

    validator = Draft202012Validator(load_schema("review_control_signal_artifact"))
    errors = sorted(validator.iter_errors(output), key=lambda err: str(list(err.absolute_path)))
    if errors:
        details = "; ".join(error.message for error in errors)
        raise ReviewSignalClassificationError(f"review_control_signal_artifact failed schema validation: {details}")

    return output


__all__ = ["ReviewSignalClassificationError", "classify_review_signal"]
