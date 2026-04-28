"""CL-10 / CL-12: EVL required-eval resolver — pure validator.

Given a candidate eval-set (the actual evals attached to an execution)
and the catalog of declared evals (with their required/optional flag),
classify each as required, optional, missing, duplicate, or unsupported.

The resolver is non-owning. EVL retains canonical authority over the
required-eval registry. The resolver's role is to make eval-set
confusion (duplicates, optional-as-required, required-as-optional,
unsupported names, mixed pass/fail on required) deterministically
visible with stable canonical reason codes.
"""

from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List, Mapping, Optional, Sequence

REASON_OK = "EVAL_REQUIRED_OK"
REASON_REQUIRED_MISSING = "EVAL_REQUIRED_MISSING"
REASON_REQUIRED_FAILED = "EVAL_REQUIRED_FAILED"
REASON_DUPLICATE = "EVAL_DUPLICATE"
REASON_UNSUPPORTED = "EVAL_UNSUPPORTED_NAME"
REASON_OPTIONAL_AS_REQUIRED = "EVAL_OPTIONAL_MARKED_REQUIRED"
REASON_REQUIRED_AS_OPTIONAL = "EVAL_REQUIRED_MARKED_OPTIONAL"
REASON_UNDETERMINED = "EVAL_UNDETERMINED"


class RequiredEvalResolverError(ValueError):
    """Raised only on programmer-misuse."""


def _violation(code: str, **details: Any) -> Dict[str, Any]:
    return {"reason_code": code, **details}


def resolve_required_evals(
    *,
    declared_catalog: Sequence[Mapping[str, Any]],
    submitted_evals: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    """Classify the supplied eval-set against the declared catalog.

    ``declared_catalog`` items: ``{"name": str, "required": bool}``.
    ``submitted_evals`` items: ``{"name": str, "required": bool, "result": "pass"|"fail"|"skip"}``.

    Returns a deterministic resolution:

      * ``required``    — declared-required names with a passing result;
      * ``optional``    — declared-optional names with any result;
      * ``missing``     — declared-required names not submitted (or submitted but ``skip``);
      * ``failed``      — declared-required names that failed;
      * ``duplicates``  — submitted names appearing more than once;
      * ``unsupported`` — submitted names not in the declared catalog;
      * ``mismatched``  — submitted required-flag disagrees with catalog.
    """
    if not isinstance(declared_catalog, Sequence):
        raise RequiredEvalResolverError("declared_catalog must be a sequence")
    if not isinstance(submitted_evals, Sequence):
        raise RequiredEvalResolverError("submitted_evals must be a sequence")

    declared_map: Dict[str, bool] = {}
    for entry in declared_catalog:
        if not isinstance(entry, Mapping):
            continue
        name = entry.get("name")
        if not isinstance(name, str) or not name.strip():
            continue
        declared_map[name] = bool(entry.get("required"))

    name_counter: Counter = Counter()
    submitted_by_name: Dict[str, Mapping[str, Any]] = {}
    for s in submitted_evals:
        if not isinstance(s, Mapping):
            continue
        name = s.get("name")
        if not isinstance(name, str) or not name.strip():
            continue
        name_counter[name] += 1
        submitted_by_name.setdefault(name, s)

    duplicates = [n for n, c in name_counter.items() if c > 1]
    unsupported = [n for n in submitted_by_name if n not in declared_map]

    required_passed: List[str] = []
    required_failed: List[str] = []
    required_missing: List[str] = []
    optional_seen: List[str] = []
    mismatched: List[Dict[str, Any]] = []

    for name, declared_required in declared_map.items():
        sub = submitted_by_name.get(name)
        if declared_required:
            if sub is None:
                required_missing.append(name)
                continue
            result = (sub.get("result") or "").lower()
            if result == "skip":
                required_missing.append(name)
            elif result == "fail":
                required_failed.append(name)
            elif result == "pass":
                required_passed.append(name)
            else:
                required_missing.append(name)
        else:
            if sub is not None:
                optional_seen.append(name)

    for name, sub in submitted_by_name.items():
        if name not in declared_map:
            continue
        declared_required = declared_map[name]
        submitted_required = bool(sub.get("required"))
        if declared_required != submitted_required:
            mismatched.append(
                {
                    "name": name,
                    "declared_required": declared_required,
                    "submitted_required": submitted_required,
                }
            )

    violations: List[Dict[str, Any]] = []

    for name in required_missing:
        violations.append(_violation(REASON_REQUIRED_MISSING, name=name))
    for name in required_failed:
        violations.append(_violation(REASON_REQUIRED_FAILED, name=name))
    for name in duplicates:
        violations.append(_violation(REASON_DUPLICATE, name=name))
    for name in unsupported:
        violations.append(_violation(REASON_UNSUPPORTED, name=name))
    for entry in mismatched:
        if entry["declared_required"] and not entry["submitted_required"]:
            violations.append(_violation(REASON_REQUIRED_AS_OPTIONAL, name=entry["name"]))
        else:
            violations.append(_violation(REASON_OPTIONAL_AS_REQUIRED, name=entry["name"]))

    primary_reason = REASON_OK
    if violations:
        # Stable precedence inside eval class: missing > failed > duplicate >
        # unsupported > mismatched. Keeps the primary reason deterministic
        # under reason floods within the eval stage.
        order = (
            REASON_REQUIRED_MISSING,
            REASON_REQUIRED_FAILED,
            REASON_DUPLICATE,
            REASON_UNSUPPORTED,
            REASON_REQUIRED_AS_OPTIONAL,
            REASON_OPTIONAL_AS_REQUIRED,
        )
        for code in order:
            if any(v["reason_code"] == code for v in violations):
                primary_reason = code
                break

    return {
        "ok": not violations,
        "violations": violations,
        "primary_reason": primary_reason,
        "required_passed": required_passed,
        "required_failed": required_failed,
        "required_missing": required_missing,
        "optional_seen": optional_seen,
        "duplicates": duplicates,
        "unsupported": unsupported,
        "mismatched": mismatched,
    }


def build_eval_summary(
    *,
    summary_id: str,
    trace_id: str,
    resolution: Mapping[str, Any],
) -> Dict[str, Any]:
    """Construct an eval_summary view from a resolver result."""
    overall = "healthy" if resolution.get("ok") else "blocked"
    return {
        "artifact_type": "core_loop_eval_summary",
        "schema_version": "1.0.0",
        "summary_id": summary_id,
        "trace_id": trace_id,
        "status": overall,
        "primary_reason": resolution.get("primary_reason") or REASON_OK,
        "required_passed": list(resolution.get("required_passed") or ()),
        "required_failed": list(resolution.get("required_failed") or ()),
        "required_missing": list(resolution.get("required_missing") or ()),
        "duplicates": list(resolution.get("duplicates") or ()),
        "unsupported": list(resolution.get("unsupported") or ()),
    }


__all__ = [
    "RequiredEvalResolverError",
    "REASON_OK",
    "REASON_REQUIRED_MISSING",
    "REASON_REQUIRED_FAILED",
    "REASON_DUPLICATE",
    "REASON_UNSUPPORTED",
    "REASON_OPTIONAL_AS_REQUIRED",
    "REASON_REQUIRED_AS_OPTIONAL",
    "REASON_UNDETERMINED",
    "resolve_required_evals",
    "build_eval_summary",
]
