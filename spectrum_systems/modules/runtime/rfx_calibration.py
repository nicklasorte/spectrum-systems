"""RFX calibration + confidence control — RFX-13.

Detects miscalibrated confidence in fixes, evals, judgments, or
recommendations. The module is a non-owning phase-label support helper.
Closure-signal authority remains with CDE; eval coverage with EVL;
judgment semantics with JDX; policy lifecycle with POL.

Output:

  * ``rfx_calibration_record``

Reason codes:

  * ``rfx_overconfidence_risk``
  * ``rfx_underconfidence_signal``
  * ``rfx_confidence_without_evidence``
  * ``rfx_confidence_drift_detected``
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


class RFXCalibrationError(ValueError):
    """Raised when calibration verification fails closed."""


_DEFAULT_HIGH_CONFIDENCE = 0.8
_DEFAULT_LOW_CONFIDENCE = 0.3
_DEFAULT_DRIFT_DELTA = 0.25


def _stable_id(payload: Any, *, prefix: str) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}-{digest}"


def _coerce_confidence(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        v = float(value)
        if 0.0 <= v <= 1.0:
            return v
    return None


def assert_rfx_calibration(
    *,
    samples: list[dict[str, Any]] | None,
    historical_samples: list[dict[str, Any]] | None = None,
    high_confidence_threshold: float = _DEFAULT_HIGH_CONFIDENCE,
    low_confidence_threshold: float = _DEFAULT_LOW_CONFIDENCE,
    drift_delta: float = _DEFAULT_DRIFT_DELTA,
) -> dict[str, Any]:
    """Assert calibration invariants over a list of confidence samples.

    Each sample is a mapping with at least:

      * ``confidence``: float in [0, 1]
      * ``outcome``: one of ``"correct"`` / ``"incorrect"`` (or ``True`` /
        ``False`` for boolean shorthand)
      * ``evidence_refs``: list of source references

    Fails closed by aggregating reason codes when:

      * ``confidence ≥ high_confidence_threshold`` and outcome is incorrect
        → ``rfx_overconfidence_risk``
      * ``confidence`` is set without any evidence refs
        → ``rfx_confidence_without_evidence``
      * mean confidence vs. ``historical_samples`` mean differs by more than
        ``drift_delta`` → ``rfx_confidence_drift_detected``

    Always reports an ``rfx_underconfidence_signal`` advisory entry — it is
    informational, not blocking, but recorded so the calibration record
    surfaces under-confident correct outcomes.
    """
    if not isinstance(samples, list) or not samples:
        raise RFXCalibrationError(
            "rfx_confidence_without_evidence: samples list absent or empty"
        )

    reasons: list[str] = []
    overconfidence: list[dict[str, Any]] = []
    underconfidence: list[dict[str, Any]] = []
    no_evidence: list[dict[str, Any]] = []
    confidences: list[float] = []

    for idx, s in enumerate(samples):
        if not isinstance(s, dict):
            continue
        c = _coerce_confidence(s.get("confidence"))
        if c is None:
            reasons.append(
                f"rfx_confidence_without_evidence: sample[{idx}] confidence missing or out of [0,1]"
            )
            continue
        confidences.append(c)

        outcome = s.get("outcome")
        if outcome is True:
            outcome_correct: bool | None = True
        elif outcome is False:
            outcome_correct = False
        elif isinstance(outcome, str):
            if outcome.strip().lower() in {"correct", "pass", "ok"}:
                outcome_correct = True
            elif outcome.strip().lower() in {"incorrect", "fail", "wrong"}:
                outcome_correct = False
            else:
                outcome_correct = None
        else:
            outcome_correct = None

        evidence_refs = s.get("evidence_refs")
        has_evidence = isinstance(evidence_refs, list) and any(
            isinstance(r, str) and r.strip() for r in evidence_refs
        )
        if not has_evidence:
            no_evidence.append({"index": idx, "confidence": c})
            reasons.append(
                f"rfx_confidence_without_evidence: sample[{idx}] confidence={c} has no evidence refs"
            )

        if c >= high_confidence_threshold and outcome_correct is False:
            overconfidence.append({"index": idx, "confidence": c})
            reasons.append(
                f"rfx_overconfidence_risk: sample[{idx}] confidence={c} but outcome is incorrect"
            )
        if c <= low_confidence_threshold and outcome_correct is True:
            underconfidence.append({"index": idx, "confidence": c})

    drift = None
    if isinstance(historical_samples, list) and historical_samples:
        hist_confidences = [
            _coerce_confidence(s.get("confidence"))
            for s in historical_samples
            if isinstance(s, dict)
        ]
        hist_confidences = [c for c in hist_confidences if c is not None]
        if confidences and hist_confidences:
            current_mean = sum(confidences) / len(confidences)
            hist_mean = sum(hist_confidences) / len(hist_confidences)
            drift = current_mean - hist_mean
            if abs(drift) > drift_delta:
                reasons.append(
                    f"rfx_confidence_drift_detected: current_mean={current_mean:.3f} "
                    f"vs. historical_mean={hist_mean:.3f}; |drift|={abs(drift):.3f} > {drift_delta}"
                )

    if reasons:
        raise RFXCalibrationError("; ".join(reasons))

    record = {
        "artifact_type": "rfx_calibration_record",
        "schema_version": "1.0.0",
        "sample_count": len(samples),
        "overconfidence_events": overconfidence,
        "underconfidence_events": underconfidence,
        "no_evidence_events": no_evidence,
        "confidence_drift": drift,
        "thresholds": {
            "high_confidence": high_confidence_threshold,
            "low_confidence": low_confidence_threshold,
            "drift_delta": drift_delta,
        },
    }
    record["calibration_id"] = _stable_id(
        {"sample_count": record["sample_count"]}, prefix="rfx-calibration"
    )
    return record


__all__ = [
    "RFXCalibrationError",
    "assert_rfx_calibration",
]
