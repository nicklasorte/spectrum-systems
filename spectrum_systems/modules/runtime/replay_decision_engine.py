"""Replay Decision Integrity Engine (BQ).

Evaluates whether a replayed execution reproduces the same SLO decision and
enforcement outcome as the original run.  Establishes decision reproducibility
and enables drift detection.

Design principles
-----------------
- Fail closed:  missing original decision, replay failure, or schema validation
  failure all raise errors — no silent degradation.
- Schema-governed:  every analysis artifact is validated against
  ``replay_decision_analysis.schema.json`` before being returned.
- Trace propagation:  ``trace_id`` is included in all log messages.
- Deterministic scoring:  the same inputs always produce the same
  ``reproducibility_score``.

Replay → decision → analysis data flow
---------------------------------------
    trace_store
         │  load_trace(trace_id)
         ▼
    original execution trace
         │  extract SLO enforcement span events
         ▼
    original_decision (summary dict)
         │
    execute_replay(trace_id)
         ▼
    replay_result artifact
         │  recompute_decision_from_replay(replay_result)
         ▼
    replay_decision (summary dict)
         │
    compare_decisions(original, replay)
         ▼
    decision_consistency artifact
         │
    classify_drift(original, replay, context)
         ▼
    drift_type (or None)
         │
    compute_reproducibility_score(consistency, drift_type)
         ▼
    reproducibility_score in [0.0, 1.0]
         │
    build_analysis_artifact(...)
         ▼
    replay_decision_analysis (governed, schema-validated artifact)

Public API
----------
load_original_decision(trace_id, ...)        → decision summary dict
recompute_decision_from_replay(replay_result) → decision summary dict
compare_decisions(original, replay)           → decision_consistency dict
classify_drift(original, replay, context)     → drift_type str | None
compute_reproducibility_score(consistency, drift_type) → float
build_analysis_artifact(...)                  → replay_decision_analysis dict
validate_analysis(artifact)                   → list[str]  (empty = valid)
run_replay_decision_analysis(trace_id, ...)   → replay_decision_analysis dict
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from jsonschema import Draft202012Validator, FormatChecker

from spectrum_systems.modules.runtime.replay_engine import (
    ReplayPrerequisiteError,
    execute_replay,
)
from spectrum_systems.modules.runtime.trace_store import (
    TraceNotFoundError as StoreTraceNotFoundError,
    TraceStoreError,
    load_trace,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SCHEMA_VERSION: str = "1.0.0"
ARTIFACT_TYPE: str = "replay_decision_analysis"

# Consistency statuses
CONSISTENCY_CONSISTENT: str = "consistent"
CONSISTENCY_DRIFTED: str = "drifted"
CONSISTENCY_INDETERMINATE: str = "indeterminate"

# Drift types
DRIFT_INPUT: str = "INPUT_DRIFT"
DRIFT_LOGIC: str = "LOGIC_DRIFT"
DRIFT_ENVIRONMENT: str = "ENVIRONMENT_DRIFT"
DRIFT_NON_DETERMINISTIC: str = "NON_DETERMINISTIC_DRIFT"

# Decision fields compared for consistency
_DECISION_STATUS_FIELD: str = "decision_status"
_REASON_CODE_FIELD: str = "decision_reason_code"
_POLICY_FIELD: str = "enforcement_policy"
_RECOMMENDED_ACTION_FIELD: str = "recommended_action"

# SLO enforcement span names emitted by the trace engine
_SLO_ENFORCEMENT_SPAN_NAME: str = "slo_enforcement_decision"

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCHEMA_DIR = _REPO_ROOT / "contracts" / "schemas"
_ANALYSIS_SCHEMA_PATH = _SCHEMA_DIR / "replay_decision_analysis.schema.json"

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _new_id() -> str:
    return str(uuid.uuid4())


def _load_analysis_schema() -> Dict[str, Any]:
    return json.loads(_ANALYSIS_SCHEMA_PATH.read_text(encoding="utf-8"))


def _extract_enforcement_event(span: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Return the first enforcement_decision event payload from a span, or None."""
    for event in span.get("events") or []:
        if event.get("name") == "enforcement_decision":
            return event.get("data") or {}
    return None


def _decision_summary_from_span(span: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Extract a decision summary dict from an SLO enforcement span.

    Returns None if the span does not contain sufficient enforcement data.
    """
    event_data = _extract_enforcement_event(span)
    if event_data is None:
        return None

    action = event_data.get("action")
    if action is None:
        return None

    # Map the action stored in the span event to a canonical decision_status.
    # The slo_enforcer stores "action" in events; map to decision_status vocabulary.
    status_map = {
        "allow": "allow",
        "allow_with_warning": "allow_with_warning",
        "block": "fail",
        "fail": "fail",
    }
    decision_status = status_map.get(str(action).lower(), str(action))

    return {
        "decision_status": decision_status,
        "decision_reason_code": event_data.get("reason") or "unknown",
        "enforcement_policy": event_data.get("enforcement_policy", None),
        "recommended_action": event_data.get("recommended_action", None),
        "traceability_integrity_sli": event_data.get("traceability_integrity_sli", None),
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def load_original_decision(
    trace_id: str,
    base_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Load and extract the original SLO enforcement decision from a persisted trace.

    Searches the trace's spans for an SLO enforcement decision span and extracts
    the decision summary from its recorded events.

    Parameters
    ----------
    trace_id:
        The trace to load.
    base_dir:
        Override the trace store directory (primarily for testing).

    Returns
    -------
    dict
        A decision summary with keys: decision_status, decision_reason_code,
        enforcement_policy, recommended_action, traceability_integrity_sli.

    Raises
    ------
    ReplayDecisionError
        If the trace cannot be loaded or contains no enforcement decision.
    """
    logger.debug("load_original_decision: loading trace trace_id=%s", trace_id)

    if not trace_id or not isinstance(trace_id, str):
        raise ReplayDecisionError(
            f"load_original_decision: trace_id must be a non-empty string [trace_id={trace_id!r}]"
        )

    try:
        envelope = load_trace(trace_id, base_dir=base_dir)
    except StoreTraceNotFoundError as exc:
        raise ReplayDecisionError(
            f"load_original_decision: no persisted trace found for trace_id='{trace_id}': {exc}"
        ) from exc
    except TraceStoreError as exc:
        raise ReplayDecisionError(
            f"load_original_decision: trace store error for trace_id='{trace_id}': {exc}"
        ) from exc

    inner_trace = envelope.get("trace") or {}
    spans: List[Dict[str, Any]] = inner_trace.get("spans") or []

    # Find the enforcement span and extract the decision
    for span in spans:
        if span.get("name") == _SLO_ENFORCEMENT_SPAN_NAME:
            summary = _decision_summary_from_span(span)
            if summary is not None:
                logger.info(
                    "load_original_decision: found enforcement decision trace_id=%s status=%s",
                    trace_id,
                    summary["decision_status"],
                )
                return summary

    # No enforcement span found — check if the trace has any artifact with a decision
    artifacts: List[Dict[str, Any]] = inner_trace.get("artifacts") or []
    for artifact in artifacts:
        if artifact.get("artifact_type") == "slo_enforcement_decision":
            status = artifact.get("decision_status")
            reason = artifact.get("decision_reason_code")
            if status and reason:
                return {
                    "decision_status": status,
                    "decision_reason_code": reason,
                    "enforcement_policy": artifact.get("enforcement_policy"),
                    "recommended_action": artifact.get("recommended_action"),
                    "traceability_integrity_sli": artifact.get("traceability_integrity_sli"),
                }

    raise ReplayDecisionError(
        f"load_original_decision: no SLO enforcement decision found in trace_id='{trace_id}'. "
        f"Trace must contain a span named '{_SLO_ENFORCEMENT_SPAN_NAME}' with enforcement events, "
        f"or an attached slo_enforcement_decision artifact."
    )


def recompute_decision_from_replay(
    replay_result: Dict[str, Any],
) -> Dict[str, Any]:
    """Extract or recompute the SLO enforcement decision from a replay result.

    Inspects the replay result's steps for enforcement-related outcomes and
    derives a decision summary representing what the replay produced.

    Parameters
    ----------
    replay_result:
        A validated replay_result artifact dict (from execute_replay).

    Returns
    -------
    dict
        A decision summary with keys: decision_status, decision_reason_code,
        enforcement_policy, recommended_action, traceability_integrity_sli.

    Raises
    ------
    ReplayDecisionError
        If the replay result is invalid or contains no usable decision data.
    """
    if not isinstance(replay_result, dict):
        raise ReplayDecisionError(
            "recompute_decision_from_replay: replay_result must be a dict"
        )

    replay_id = replay_result.get("replay_id", "(unknown)")
    trace_id = replay_result.get("source_trace_id", "(unknown)")
    logger.debug(
        "recompute_decision_from_replay: trace_id=%s replay_id=%s", trace_id, replay_id
    )

    status = replay_result.get("status")
    if status == "blocked":
        raise ReplayDecisionError(
            f"recompute_decision_from_replay: replay was blocked (prerequisites not met) "
            f"for trace_id='{trace_id}', replay_id='{replay_id}'. Cannot recompute decision."
        )

    if status == "failed":
        raise ReplayDecisionError(
            f"recompute_decision_from_replay: replay failed for trace_id='{trace_id}', "
            f"replay_id='{replay_id}'. Cannot recompute decision."
        )

    # Derive decision from step outcomes
    steps: List[Dict[str, Any]] = replay_result.get("steps_executed") or []
    enforcement_steps = [
        s for s in steps if _SLO_ENFORCEMENT_SPAN_NAME in (s.get("span_name") or "")
    ]

    if enforcement_steps:
        # Use the first enforcement step outcome
        step = enforcement_steps[0]
        step_status = step.get("status", "ok")
        # Map replay step statuses to decision vocabulary
        status_map = {
            "ok": "allow",
            "blocked": "fail",
            "error": "fail",
            "skipped": "allow",
        }
        decision_status = status_map.get(step_status, "allow")
        return {
            "decision_status": decision_status,
            "decision_reason_code": "replayed_from_step",
            "enforcement_policy": None,
            "recommended_action": None,
            "traceability_integrity_sli": None,
        }

    # No enforcement steps — derive from overall replay status
    overall_status_map = {
        "success": "allow",
        "partial": "allow_with_warning",
        "failed": "fail",
        "blocked": "fail",
    }
    decision_status = overall_status_map.get(status or "", "allow")
    logger.info(
        "recompute_decision_from_replay: no enforcement span in replay steps; "
        "derived decision from overall status=%s → decision_status=%s trace_id=%s",
        status,
        decision_status,
        trace_id,
    )
    return {
        "decision_status": decision_status,
        "decision_reason_code": "derived_from_replay_status",
        "enforcement_policy": None,
        "recommended_action": None,
        "traceability_integrity_sli": None,
    }


def compare_decisions(
    original: Dict[str, Any],
    replay: Dict[str, Any],
) -> Dict[str, Any]:
    """Compare the original and replay decision summaries field by field.

    The primary consistency gate is ``decision_status``.  Optional fields
    (reason_code, policy, action) are included in ``differences`` only when
    both sides carry a meaningful (non-None, non-synthetic) value.

    Synthetic replay reason codes (``"replayed_from_step"``,
    ``"derived_from_replay_status"``) are not compared against the original
    because the replay pipeline cannot re-derive the original reason code
    without re-running the full SLO logic.

    Parameters
    ----------
    original:
        Decision summary from the original execution.
    replay:
        Decision summary recomputed from the replay.

    Returns
    -------
    dict
        A ``decision_consistency`` object with keys:
        - ``status``: "consistent" | "drifted" | "indeterminate"
        - ``differences``: list of difference dicts
    """
    if not isinstance(original, dict) or not isinstance(replay, dict):
        return {
            "status": CONSISTENCY_INDETERMINATE,
            "differences": [],
        }

    # Synthetic reason codes produced by recompute_decision_from_replay are
    # not comparable to the original reason code.
    _SYNTHETIC_REASON_CODES: frozenset = frozenset({
        "replayed_from_step",
        "derived_from_replay_status",
    })

    differences: List[Dict[str, Any]] = []

    # --- Primary field: decision_status (always compared) ---
    orig_status = original.get(_DECISION_STATUS_FIELD)
    replay_status = replay.get(_DECISION_STATUS_FIELD)
    if orig_status != replay_status:
        differences.append(
            {
                "field": _DECISION_STATUS_FIELD,
                "original_value": orig_status,
                "replay_value": replay_status,
            }
        )

    # --- Secondary fields: only compared when both carry meaningful values ---
    secondary_fields = [_REASON_CODE_FIELD, _POLICY_FIELD, _RECOMMENDED_ACTION_FIELD]
    for field in secondary_fields:
        orig_val = original.get(field)
        replay_val = replay.get(field)

        # Skip when either side is None or when replay carries a synthetic code
        if orig_val is None or replay_val is None:
            continue
        if field == _REASON_CODE_FIELD and replay_val in _SYNTHETIC_REASON_CODES:
            continue

        if orig_val != replay_val:
            differences.append(
                {
                    "field": field,
                    "original_value": orig_val,
                    "replay_value": replay_val,
                }
            )

    status = CONSISTENCY_CONSISTENT if not differences else CONSISTENCY_DRIFTED
    return {
        "status": status,
        "differences": differences,
    }


def classify_drift(
    original: Dict[str, Any],
    replay: Dict[str, Any],
    replay_context: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    """Classify the type of drift between original and replay decisions.

    TI SLI is checked first — differing TI values signal INPUT_DRIFT regardless
    of whether the final ``decision_status`` changed (the input to the decision
    logic changed even if the outcome happened to be the same).

    Parameters
    ----------
    original:
        Decision summary from the original execution.
    replay:
        Decision summary recomputed from the replay.
    replay_context:
        Optional replay context metadata (e.g. replay_mode, triggered_by).

    Returns
    -------
    str or None
        One of DRIFT_INPUT, DRIFT_LOGIC, DRIFT_ENVIRONMENT,
        DRIFT_NON_DETERMINISTIC, or None when no drift is detected.
    """
    # --- Check TI SLI first (input-level drift regardless of outcome) ---
    orig_ti = original.get("traceability_integrity_sli")
    replay_ti = replay.get("traceability_integrity_sli")
    if orig_ti is not None and replay_ti is not None and orig_ti != replay_ti:
        return DRIFT_INPUT

    consistency = compare_decisions(original, replay)
    if consistency["status"] != CONSISTENCY_DRIFTED:
        return None

    context = replay_context or {}
    differences = consistency["differences"]
    diffed_fields = {d["field"] for d in differences}

    # If the reason codes differ but the decision status is the same → subtle logic change
    if _REASON_CODE_FIELD in diffed_fields and _DECISION_STATUS_FIELD not in diffed_fields:
        return DRIFT_LOGIC

    # If only policies or actions differ → environment/configuration changed
    policy_only_drift = diffed_fields <= {_POLICY_FIELD, _RECOMMENDED_ACTION_FIELD}
    if policy_only_drift:
        return DRIFT_ENVIRONMENT

    # If the replay context explicitly marks non-determinism
    if context.get("non_deterministic"):
        return DRIFT_NON_DETERMINISTIC

    # Replay reason code is derived from replay status → non-deterministic
    if replay.get("decision_reason_code") in (
        "replayed_from_step",
        "derived_from_replay_status",
    ):
        return DRIFT_NON_DETERMINISTIC

    # Default: logic drift (decision_status changed)
    return DRIFT_LOGIC


def compute_reproducibility_score(
    consistency: Dict[str, Any],
    drift_type: Optional[str],
) -> float:
    """Compute a reproducibility score in [0, 1] from consistency and drift data.

    Scoring logic
    -------------
    - CONSISTENCY_CONSISTENT → 1.0
    - CONSISTENCY_INDETERMINATE → 0.5
    - CONSISTENCY_DRIFTED:
        - NON_DETERMINISTIC_DRIFT → 0.5  (expected non-determinism)
        - ENVIRONMENT_DRIFT → 0.3        (configuration changed)
        - INPUT_DRIFT → 0.2              (inputs changed)
        - LOGIC_DRIFT → 0.0              (logic changed — worst case)
        - unknown drift type → 0.1

    Parameters
    ----------
    consistency:
        The decision_consistency dict from compare_decisions.
    drift_type:
        The drift classification from classify_drift.

    Returns
    -------
    float
        A score in [0.0, 1.0].
    """
    status = (consistency or {}).get("status", CONSISTENCY_INDETERMINATE)

    if status == CONSISTENCY_CONSISTENT:
        return 1.0

    if status == CONSISTENCY_INDETERMINATE:
        return 0.5

    # Drifted — score by drift type
    drift_scores = {
        DRIFT_NON_DETERMINISTIC: 0.5,
        DRIFT_ENVIRONMENT: 0.3,
        DRIFT_INPUT: 0.2,
        DRIFT_LOGIC: 0.0,
    }
    return drift_scores.get(drift_type or "", 0.1)


def build_analysis_artifact(
    trace_id: str,
    replay_result_id: str,
    original_decision: Dict[str, Any],
    replay_decision: Dict[str, Any],
    decision_consistency: Dict[str, Any],
    drift_type: Optional[str],
    reproducibility_score: float,
    explanation: str,
) -> Dict[str, Any]:
    """Assemble the ``replay_decision_analysis`` governed artifact.

    Parameters
    ----------
    trace_id:
        The source trace ID.
    replay_result_id:
        The replay_id from the replay_result artifact.
    original_decision:
        Decision summary from the original execution.
    replay_decision:
        Decision summary recomputed from the replay.
    decision_consistency:
        Consistency assessment from compare_decisions.
    drift_type:
        Drift classification (or None).
    reproducibility_score:
        Score in [0, 1].
    explanation:
        Human-readable explanation of the analysis result.

    Returns
    -------
    dict
        An unvalidated replay_decision_analysis artifact.
    """
    return {
        "analysis_id": _new_id(),
        "trace_id": trace_id,
        "replay_result_id": replay_result_id,
        "original_decision": original_decision,
        "replay_decision": replay_decision,
        "decision_consistency": decision_consistency,
        "drift_type": drift_type,
        "reproducibility_score": reproducibility_score,
        "explanation": explanation,
        "created_at": _now_iso(),
    }


def validate_analysis(artifact: Any) -> List[str]:
    """Validate *artifact* against the ``replay_decision_analysis.schema.json`` contract.

    Parameters
    ----------
    artifact:
        The analysis artifact dict to validate.

    Returns
    -------
    list[str]
        Empty list if valid.  Non-empty list of error messages if invalid.
        Callers MUST treat any non-empty result as a hard failure.
    """
    if not isinstance(artifact, dict):
        return ["validate_analysis: artifact must be a dict"]

    try:
        schema = _load_analysis_schema()
    except (OSError, json.JSONDecodeError) as exc:
        return [f"validate_analysis: could not load analysis schema: {exc}"]

    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(artifact), key=lambda e: list(e.path))
    return [e.message for e in errors]


def run_replay_decision_analysis(
    trace_id: str,
    base_dir: Optional[Path] = None,
    replay_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Execute the full replay decision analysis pipeline for *trace_id*.

    Steps
    -----
    1. Load the original SLO enforcement decision from the persisted trace.
    2. Execute the replay via execute_replay.
    3. Recompute the decision from the replay result.
    4. Compare original and replay decisions.
    5. Classify any drift.
    6. Compute reproducibility score.
    7. Build and validate the governed analysis artifact.

    Parameters
    ----------
    trace_id:
        The trace to analyze.
    base_dir:
        Override the trace store directory (primarily for testing).
    replay_context:
        Optional caller-supplied context metadata forwarded to execute_replay.

    Returns
    -------
    dict
        A fully validated ``replay_decision_analysis`` artifact.

    Raises
    ------
    ReplayDecisionError
        For any failure: missing decision, replay failure, schema validation
        failure.  No silent degradation.
    """
    logger.info("run_replay_decision_analysis: starting trace_id=%s", trace_id)

    # Step 1: Load original decision (fail closed if missing)
    original_decision = load_original_decision(trace_id, base_dir=base_dir)
    logger.info(
        "run_replay_decision_analysis: original decision loaded trace_id=%s status=%s",
        trace_id,
        original_decision["decision_status"],
    )

    # Step 2: Execute replay (fail closed on replay failure)
    try:
        replay_result = execute_replay(
            trace_id,
            base_dir=base_dir,
            context=replay_context,
        )
    except ReplayPrerequisiteError as exc:
        raise ReplayDecisionError(
            f"run_replay_decision_analysis: replay prerequisites not met for "
            f"trace_id='{trace_id}': {exc}"
        ) from exc
    except Exception as exc:  # noqa: BLE001
        raise ReplayDecisionError(
            f"run_replay_decision_analysis: replay failed for trace_id='{trace_id}': {exc}"
        ) from exc

    replay_result_id = replay_result["replay_id"]
    logger.info(
        "run_replay_decision_analysis: replay completed trace_id=%s replay_id=%s status=%s",
        trace_id,
        replay_result_id,
        replay_result.get("status"),
    )

    # Step 3: Recompute decision from replay (fail closed on failure)
    replay_decision = recompute_decision_from_replay(replay_result)
    logger.info(
        "run_replay_decision_analysis: replay decision derived trace_id=%s status=%s",
        trace_id,
        replay_decision["decision_status"],
    )

    # Step 4: Compare decisions
    consistency = compare_decisions(original_decision, replay_decision)

    # Step 5: Classify drift
    drift_type = classify_drift(original_decision, replay_decision, replay_context)

    # Step 6: Compute reproducibility score
    score = compute_reproducibility_score(consistency, drift_type)

    logger.info(
        "run_replay_decision_analysis: analysis complete trace_id=%s "
        "consistency=%s drift_type=%s reproducibility_score=%.3f",
        trace_id,
        consistency["status"],
        drift_type,
        score,
    )

    # Step 7: Build explanation
    if consistency["status"] == CONSISTENCY_CONSISTENT:
        explanation = (
            f"Replay of trace '{trace_id}' produced the same SLO enforcement decision "
            f"as the original run (status={original_decision['decision_status']!r}). "
            f"Decision is reproducible."
        )
    elif consistency["status"] == CONSISTENCY_DRIFTED:
        diffs_summary = "; ".join(
            f"{d['field']}: {d['original_value']!r} → {d['replay_value']!r}"
            for d in consistency["differences"]
        )
        explanation = (
            f"Replay of trace '{trace_id}' produced a DIFFERENT SLO enforcement decision. "
            f"Drift type: {drift_type}. Differences: {diffs_summary}. "
            f"Reproducibility score: {score:.3f}."
        )
    else:
        explanation = (
            f"Comparison of decisions for trace '{trace_id}' was indeterminate. "
            f"The replay may not have contained sufficient enforcement data to conclude "
            f"whether the decision was reproduced."
        )

    # Step 8: Build and validate artifact (fail closed on schema validation failure)
    artifact = build_analysis_artifact(
        trace_id=trace_id,
        replay_result_id=replay_result_id,
        original_decision=original_decision,
        replay_decision=replay_decision,
        decision_consistency=consistency,
        drift_type=drift_type,
        reproducibility_score=score,
        explanation=explanation,
    )

    schema_errors = validate_analysis(artifact)
    if schema_errors:
        raise ReplayDecisionError(
            f"run_replay_decision_analysis: analysis artifact failed schema validation "
            f"for trace_id='{trace_id}': " + "; ".join(schema_errors)
        )

    return artifact


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class ReplayDecisionError(Exception):
    """Raised for any failure in the Replay Decision Integrity Engine.

    This includes missing original decisions, replay failures, and schema
    validation failures.  No silent degradation is permitted.
    """
