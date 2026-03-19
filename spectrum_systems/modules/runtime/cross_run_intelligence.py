"""Cross-Run Intelligence Layer (Prompt BF).

Consumes BE normalized_run_result artifacts, aligns metrics across runs,
produces cross-run comparison summaries, detects anomalies, ranks scenarios,
and emits two governed decision artifacts.

This layer assumes BE has already normalized artifacts, but defends itself
against malformed or schema-invalid NRR inputs.

Failure types
-------------
none
    All checks pass.
no_inputs
    No input paths or payloads were provided.
malformed_input
    An input file contained invalid JSON or could not be read.
schema_invalid
    An input NRR failed schema validation against the governed NRR schema.
mixed_study_types
    Multiple conflicting non-generic study types were found across inputs.
no_comparable_metrics
    No metric was found to be comparable across the provided runs.
comparison_error
    An unexpected error occurred during comparison logic.
anomaly_detection_error
    An unexpected error occurred during anomaly detection.
"""

from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from jsonschema import Draft202012Validator

_SCHEMA_DIR = Path(__file__).resolve().parents[3] / "contracts" / "schemas"
_NRR_SCHEMA_PATH = _SCHEMA_DIR / "normalized_run_result.schema.json"
_CRC_SCHEMA_PATH = _SCHEMA_DIR / "cross_run_comparison.schema.json"
_CRI_SCHEMA_PATH = _SCHEMA_DIR / "cross_run_intelligence_decision.schema.json"

_SCHEMA_VERSION = "1.0.0"

# Governed study types (non-generic)
_STRONG_STUDY_TYPES = frozenset(
    {"p2p_interference", "adjacency_analysis", "retuning_analysis", "sharing_study"}
)

# Default ranking bases per study type: list of (metric_name, direction)
_RANKING_BASES: Dict[str, List[Tuple[str, str]]] = {
    "p2p_interference": [
        ("interference_power_dbm", "descending"),
        ("in_ratio_db", "descending"),
    ],
    "adjacency_analysis": [
        ("interference_power_dbm", "descending"),
    ],
    "retuning_analysis": [
        ("incumbent_links_impacted", "descending"),
        ("retune_candidate_count", "descending"),
    ],
    "sharing_study": [
        ("interference_power_dbm", "descending"),
        ("affected_receivers_count", "descending"),
    ],
    "generic": [],
}

# Failure priority for classify_cross_run_failure (lower = higher priority)
_FAILURE_PRIORITY: Dict[str, int] = {
    "no_inputs": 0,
    "malformed_input": 1,
    "schema_invalid": 2,
    "mixed_study_types": 3,
    "comparison_error": 4,
    "anomaly_detection_error": 5,
    "no_comparable_metrics": 6,
    "none": 99,
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _crc_artifact_id(comparison_id: str, generated_at: str) -> str:
    digest = hashlib.sha256(
        f"CRC:{comparison_id}:{generated_at}".encode("utf-8")
    ).hexdigest()[:12].upper()
    return f"CRC-{digest}"


def _comparison_id(generated_at: str, run_count: int) -> str:
    digest = hashlib.sha256(
        f"CMP:{generated_at}:{run_count}".encode("utf-8")
    ).hexdigest()[:12].upper()
    return f"CMP-{digest}"


def _decision_id(comparison_id: str, generated_at: str) -> str:
    digest = hashlib.sha256(
        f"CRI:{comparison_id}:{generated_at}".encode("utf-8")
    ).hexdigest()[:12].upper()
    return f"CRI-{digest}"


def _load_schema(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _finding(code: str, severity: str, message: str, artifact_path: str = "") -> Dict[str, Any]:
    return {
        "code": code,
        "severity": severity,
        "message": message,
        "artifact_path": artifact_path,
    }


# ---------------------------------------------------------------------------
# NRR loading + validation
# ---------------------------------------------------------------------------


def load_normalized_run_result(path: Any) -> Dict[str, Any]:
    """Load and parse a normalized_run_result JSON file from *path*.

    Raises
    ------
    OSError
        When the file cannot be opened.
    json.JSONDecodeError
        When the file contains invalid JSON.
    """
    return json.loads(Path(path).read_text(encoding="utf-8"))


def validate_normalized_run_result_input(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Validate *payload* against the governed NRR schema.

    Returns a list of finding dicts (empty = valid).
    """
    findings: List[Dict[str, Any]] = []
    try:
        schema = _load_schema(_NRR_SCHEMA_PATH)
    except (OSError, json.JSONDecodeError) as exc:
        findings.append(
            _finding(
                code="schema_invalid",
                severity="error",
                message=f"Cannot load NRR schema: {exc}",
                artifact_path=str(_NRR_SCHEMA_PATH),
            )
        )
        return findings

    validator = Draft202012Validator(schema)
    for ve in sorted(validator.iter_errors(payload), key=lambda e: list(e.path)):
        field_path = ".".join(str(p) for p in ve.path) or "(root)"
        findings.append(
            _finding(
                code="schema_invalid",
                severity="error",
                message=f"{field_path}: {ve.message}",
                artifact_path="normalized_run_result",
            )
        )
    return findings


# ---------------------------------------------------------------------------
# Study type inference
# ---------------------------------------------------------------------------


def infer_comparison_study_type(
    nrr_payloads: List[Dict[str, Any]],
) -> Tuple[Optional[str], List[Dict[str, Any]]]:
    """Determine the governing study type for this comparison.

    Returns ``(study_type, findings)``.

    - If all runs share the same study type: return that type with no error findings.
    - If all are ``generic``: return ``generic``.
    - If one non-generic type and some ``generic`` runs: return the non-generic type
      with a warning finding for each generic run.
    - If multiple distinct non-generic types: return ``None`` with an error finding.
    """
    findings: List[Dict[str, Any]] = []

    types_seen = [p.get("study_type", "generic") for p in nrr_payloads]
    strong_types = [t for t in types_seen if t in _STRONG_STUDY_TYPES]
    distinct_strong = set(strong_types)

    if len(distinct_strong) > 1:
        findings.append(
            _finding(
                code="mixed_study_types",
                severity="error",
                message=(
                    f"Multiple conflicting study types found across inputs: "
                    f"{sorted(distinct_strong)}. Cannot compare runs from different study types."
                ),
                artifact_path="",
            )
        )
        return None, findings

    if len(distinct_strong) == 1:
        resolved = next(iter(distinct_strong))
        generic_count = types_seen.count("generic")
        if generic_count > 0:
            findings.append(
                _finding(
                    code="generic_run_included",
                    severity="warning",
                    message=(
                        f"{generic_count} run(s) have study_type=generic while "
                        f"others have study_type={resolved}. Generic runs are "
                        f"included but may lack required metrics."
                    ),
                    artifact_path="",
                )
            )
        return resolved, findings

    # All are generic (or unknown values default to generic)
    return "generic", findings


# ---------------------------------------------------------------------------
# Run descriptor collection
# ---------------------------------------------------------------------------


def collect_compared_runs(nrr_payloads: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Build the ``compared_runs`` array from validated NRR payloads."""
    compared: List[Dict[str, Any]] = []
    for nrr in nrr_payloads:
        scenario = nrr.get("scenario") or {}
        eval_signals = nrr.get("evaluation_signals") or {}
        metrics = nrr.get("metrics") or {}
        completeness = metrics.get("completeness") or {}
        compared.append(
            {
                "source_bundle_id": str(nrr.get("source_bundle_id", "unknown")),
                "normalized_run_result_id": str(nrr.get("artifact_id", "unknown")),
                "scenario_id": str(scenario.get("scenario_id", "unknown")),
                "scenario_label": str(scenario.get("scenario_label", "unknown")),
                "readiness": str(eval_signals.get("readiness", "not_ready")),
                "completeness_status": str(completeness.get("status", "insufficient")),
            }
        )
    return compared


# ---------------------------------------------------------------------------
# Metric index extraction
# ---------------------------------------------------------------------------


def extract_metric_index(nrr_payloads: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """Return a dict mapping metric_name to a list of value records.

    Each value record contains:
    - ``source_bundle_id``
    - ``scenario_id``
    - ``value``
    - ``unit``
    - ``classification``
    - ``source_path``
    """
    index: Dict[str, List[Dict[str, Any]]] = {}
    for nrr in nrr_payloads:
        bundle_id = str(nrr.get("source_bundle_id", "unknown"))
        scenario = nrr.get("scenario") or {}
        scenario_id = str(scenario.get("scenario_id", "unknown"))
        metrics = nrr.get("metrics") or {}
        summary_metrics = metrics.get("summary_metrics") or []

        for m in summary_metrics:
            name = str(m.get("name", ""))
            if not name:
                continue
            record = {
                "source_bundle_id": bundle_id,
                "scenario_id": scenario_id,
                "value": m.get("value"),
                "unit": str(m.get("unit", "")),
                "classification": str(m.get("classification", "supporting")),
                "source_path": str(m.get("source_path", "")),
            }
            index.setdefault(name, []).append(record)
    return index


# ---------------------------------------------------------------------------
# Summary statistics
# ---------------------------------------------------------------------------


def compute_summary_statistics(values: List[float]) -> Dict[str, Any]:
    """Compute count, min, max, range, and mean for *values*.

    Returns null for numeric fields when *values* is empty.
    """
    if not values:
        return {"count": 0, "min": None, "max": None, "range": None, "mean": None}
    v_min = min(values)
    v_max = max(values)
    return {
        "count": len(values),
        "min": v_min,
        "max": v_max,
        "range": v_max - v_min,
        "mean": sum(values) / len(values),
    }


# ---------------------------------------------------------------------------
# Unit mixing detection
# ---------------------------------------------------------------------------


def detect_mixed_units(metric_name: str, compared_values: List[Dict[str, Any]]) -> bool:
    """Return True when *compared_values* for *metric_name* contain more than one distinct unit."""
    units = {cv.get("unit", "") for cv in compared_values}
    return len(units) > 1


# ---------------------------------------------------------------------------
# Metric comparisons
# ---------------------------------------------------------------------------


def build_metric_comparisons(nrr_payloads: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Build the ``metric_comparisons`` array.

    Aligns metrics by name, determines comparability, and computes statistics
    for numeric values.
    """
    index = extract_metric_index(nrr_payloads)
    comparisons: List[Dict[str, Any]] = []

    for metric_name, records in sorted(index.items()):
        # Determine primary unit (most common; or empty string)
        unit_counts: Dict[str, int] = {}
        for r in records:
            unit_counts[r["unit"]] = unit_counts.get(r["unit"], 0) + 1
        primary_unit = max(unit_counts, key=unit_counts.__getitem__) if unit_counts else ""

        compared_values = [
            {
                "source_bundle_id": r["source_bundle_id"],
                "scenario_id": r["scenario_id"],
                "value": r["value"],
                "classification": r["classification"],
                "source_path": r["source_path"],
            }
            for r in records
        ]

        has_mixed_units = detect_mixed_units(metric_name, [
            {"unit": r["unit"]} for r in records
        ])

        if has_mixed_units:
            comparability = "mixed_units"
            numeric_values: List[float] = []
        else:
            # Collect numeric values
            numeric_values = []
            non_numeric_count = 0
            for r in records:
                v = r["value"]
                if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v):
                    numeric_values.append(float(v))
                elif v is not None:
                    non_numeric_count = non_numeric_count + 1

            if len(numeric_values) < 2:
                comparability = "insufficient_data"
            else:
                comparability = "comparable"

        stats = compute_summary_statistics(numeric_values)

        comparisons.append(
            {
                "metric_name": metric_name,
                "unit": primary_unit,
                "compared_values": compared_values,
                "summary_statistics": stats,
                "comparability_status": comparability,
            }
        )

    return comparisons


# ---------------------------------------------------------------------------
# Scenario rankings
# ---------------------------------------------------------------------------


def build_scenario_rankings(
    metric_comparisons: List[Dict[str, Any]],
    study_type: str,
) -> List[Dict[str, Any]]:
    """Build scenario rankings for applicable metrics.

    Rankings are only produced when:
    - The study type defines a ranking basis for the metric.
    - The metric's comparability_status is ``comparable``.
    - At least 2 numeric values exist.
    """
    bases = _RANKING_BASES.get(study_type, [])
    if not bases:
        return []

    # Index metric comparisons by name
    mc_by_name: Dict[str, Dict[str, Any]] = {
        mc["metric_name"]: mc for mc in metric_comparisons
    }

    rankings: List[Dict[str, Any]] = []
    for metric_name, direction in bases:
        mc = mc_by_name.get(metric_name)
        if mc is None:
            continue
        if mc["comparability_status"] != "comparable":
            continue

        # Collect (value, bundle_id, scenario_id, scenario_label) for ranking
        value_entries: List[Tuple[float, str, str, str]] = []
        for cv in mc["compared_values"]:
            v = cv["value"]
            if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v):
                value_entries.append(
                    (float(v), cv["source_bundle_id"], cv["scenario_id"], "")
                )

        if len(value_entries) < 2:
            continue

        # Retrieve scenario labels from mc compared_values (label not stored there);
        # use scenario_id as label fallback
        sorted_entries = sorted(
            value_entries,
            key=lambda e: e[0],
            reverse=(direction == "descending"),
        )

        ranked_scenarios = [
            {
                "rank": idx + 1,
                "source_bundle_id": entry[1],
                "scenario_id": entry[2],
                "scenario_label": entry[2],  # label not available at metric level
                "metric_name": metric_name,
                "value": entry[0],
            }
            for idx, entry in enumerate(sorted_entries)
        ]

        rankings.append(
            {
                "ranking_basis": metric_name,
                "direction": direction,
                "ranked_scenarios": ranked_scenarios,
            }
        )

    return rankings


def _enrich_rankings_with_labels(
    rankings: List[Dict[str, Any]],
    compared_runs: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Replace scenario_id placeholders in ranked_scenarios with actual labels."""
    # Build index: (source_bundle_id, scenario_id) -> scenario_label
    label_index: Dict[Tuple[str, str], str] = {}
    for run in compared_runs:
        key = (run["source_bundle_id"], run["scenario_id"])
        label_index[key] = run["scenario_label"]

    for ranking in rankings:
        for entry in ranking.get("ranked_scenarios", []):
            key = (entry["source_bundle_id"], entry["scenario_id"])
            if key in label_index:
                entry["scenario_label"] = label_index[key]
    return rankings


# ---------------------------------------------------------------------------
# Anomaly detection
# ---------------------------------------------------------------------------


def detect_cross_run_anomalies(
    metric_comparisons: List[Dict[str, Any]],
    nrr_payloads: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Detect lightweight cross-run anomalies.

    Implements:
    - extreme_spread
    - duplicate_scenario_id
    - readiness_mismatch
    - mixed_units
    - low_sample_count
    """
    flags: List[Dict[str, Any]] = []

    # Build scenario_id -> runs index for duplicate detection
    scenario_runs: Dict[str, List[Dict[str, Any]]] = {}
    for nrr in nrr_payloads:
        scenario = nrr.get("scenario") or {}
        sid = str(scenario.get("scenario_id", "unknown"))
        scenario_runs.setdefault(sid, []).append(nrr)

    for mc in metric_comparisons:
        metric_name = mc["metric_name"]
        status = mc["comparability_status"]
        stats = mc["summary_statistics"]
        compared_values = mc["compared_values"]
        affected = [cv["source_bundle_id"] for cv in compared_values]

        # mixed_units anomaly
        if status == "mixed_units":
            flags.append(
                {
                    "flag_type": "mixed_units",
                    "severity": "warning",
                    "metric_name": metric_name,
                    "affected_runs": affected,
                    "detail": (
                        f"Metric '{metric_name}' has inconsistent units across runs. "
                        f"Cannot compare values directly."
                    ),
                }
            )
            continue

        if status != "comparable":
            continue

        v_mean = stats.get("mean")
        v_range = stats.get("range")
        count = stats.get("count", 0)

        # extreme_spread anomaly
        if (
            v_mean is not None
            and v_range is not None
            and abs(v_mean) > 0
            and v_range > 10 * abs(v_mean)
        ):
            flags.append(
                {
                    "flag_type": "extreme_spread",
                    "severity": "error",
                    "metric_name": metric_name,
                    "affected_runs": affected,
                    "detail": (
                        f"Metric '{metric_name}' has extreme spread: "
                        f"range={v_range:.4g}, mean={v_mean:.4g}. "
                        f"Values differ by more than 10x the mean magnitude."
                    ),
                }
            )

        # low_sample_count anomaly
        if count == 2 and v_range is not None and v_mean is not None and abs(v_mean) > 0:
            if v_range > abs(v_mean):
                flags.append(
                    {
                        "flag_type": "low_sample_count",
                        "severity": "warning",
                        "metric_name": metric_name,
                        "affected_runs": affected,
                        "detail": (
                            f"Metric '{metric_name}' has only 2 compared values "
                            f"and a large range ({v_range:.4g}) relative to mean "
                            f"({v_mean:.4g}). Statistical conclusions are unreliable."
                        ),
                    }
                )

        # duplicate_scenario_id: same scenario_id, materially different values
        for sid, runs in scenario_runs.items():
            if len(runs) < 2:
                continue
            # Gather values for this metric across runs with this scenario_id
            sid_values = [
                cv["value"]
                for cv in compared_values
                if cv["scenario_id"] == sid
                and isinstance(cv["value"], (int, float))
                and not isinstance(cv["value"], bool)
                and math.isfinite(float(cv["value"]))
            ]
            if len(sid_values) < 2:
                continue
            sid_min = min(float(v) for v in sid_values)
            sid_max = max(float(v) for v in sid_values)
            sid_range = sid_max - sid_min
            sid_mean = sum(float(v) for v in sid_values) / len(sid_values)
            if abs(sid_mean) > 0 and sid_range > abs(sid_mean):
                flags.append(
                    {
                        "flag_type": "duplicate_scenario_id",
                        "severity": "warning",
                        "metric_name": metric_name,
                        "affected_runs": [
                            cv["source_bundle_id"]
                            for cv in compared_values
                            if cv["scenario_id"] == sid
                        ],
                        "detail": (
                            f"Scenario '{sid}' appears in multiple runs with "
                            f"materially different '{metric_name}' values "
                            f"(range={sid_range:.4g}, mean={sid_mean:.4g})."
                        ),
                    }
                )

    # readiness_mismatch: ready_for_comparison but completeness not complete
    for nrr in nrr_payloads:
        eval_signals = nrr.get("evaluation_signals") or {}
        metrics = nrr.get("metrics") or {}
        completeness = metrics.get("completeness") or {}
        readiness = eval_signals.get("readiness", "not_ready")
        completeness_status = completeness.get("status", "insufficient")

        if readiness == "ready_for_comparison" and completeness_status != "complete":
            bundle_id = str(nrr.get("source_bundle_id", "unknown"))
            flags.append(
                {
                    "flag_type": "readiness_mismatch",
                    "severity": "warning",
                    "metric_name": "",
                    "affected_runs": [bundle_id],
                    "detail": (
                        f"Run '{bundle_id}' is marked ready_for_comparison "
                        f"but completeness_status is '{completeness_status}'. "
                        f"Readiness claim may be overstated."
                    ),
                }
            )

    return flags


# ---------------------------------------------------------------------------
# Cross-run comparison artifact builder
# ---------------------------------------------------------------------------


def build_cross_run_comparison(nrr_payloads: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Build the ``cross_run_comparison`` governed artifact from *nrr_payloads*.

    Does not perform input validation — callers are responsible for ensuring
    payloads have already passed schema validation.
    """
    generated_at = _now_iso()
    cmp_id = _comparison_id(generated_at, len(nrr_payloads))
    artifact_id = _crc_artifact_id(cmp_id, generated_at)

    study_type, _ = infer_comparison_study_type(nrr_payloads)
    study_type = study_type or "generic"

    compared_runs = collect_compared_runs(nrr_payloads)
    metric_comparisons = build_metric_comparisons(nrr_payloads)
    scenario_rankings = build_scenario_rankings(metric_comparisons, study_type)
    scenario_rankings = _enrich_rankings_with_labels(scenario_rankings, compared_runs)
    anomaly_flags = detect_cross_run_anomalies(metric_comparisons, nrr_payloads)

    return {
        "artifact_id": artifact_id,
        "artifact_type": "cross_run_comparison",
        "schema_version": _SCHEMA_VERSION,
        "comparison_id": cmp_id,
        "study_type": study_type,
        "compared_runs": compared_runs,
        "metric_comparisons": metric_comparisons,
        "scenario_rankings": scenario_rankings,
        "anomaly_flags": anomaly_flags,
        "generated_at": generated_at,
    }


# ---------------------------------------------------------------------------
# Failure classification
# ---------------------------------------------------------------------------


def classify_cross_run_failure(
    findings: List[Dict[str, Any]],
) -> Tuple[str, str]:
    """Return ``(overall_status, failure_type)`` from *findings*.

    Selects the highest-priority failure type from error-severity findings,
    then warning, then none.
    """
    error_findings = [f for f in findings if f["severity"] == "error"]
    warning_findings = [f for f in findings if f["severity"] == "warning"]

    if error_findings:
        best_code = min(
            (f["code"] for f in error_findings),
            key=lambda c: _FAILURE_PRIORITY.get(c, 50),
        )
        failure_type = best_code if best_code in _FAILURE_PRIORITY else "comparison_error"
        return "fail", failure_type

    if warning_findings:
        return "warning", "none"

    return "pass", "none"


# ---------------------------------------------------------------------------
# Intelligence decision artifact builder
# ---------------------------------------------------------------------------


def build_cross_run_intelligence_decision(
    comparison_id: str,
    findings: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Build the ``cross_run_intelligence_decision`` governed artifact."""
    generated_at = _now_iso()
    dec_id = _decision_id(comparison_id, generated_at)
    overall_status, failure_type = classify_cross_run_failure(findings)

    return {
        "artifact_type": "cross_run_intelligence_decision",
        "schema_version": _SCHEMA_VERSION,
        "decision_id": dec_id,
        "comparison_id": comparison_id,
        "overall_status": overall_status,
        "failure_type": failure_type,
        "findings": findings,
        "generated_at": generated_at,
    }


# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------


def validate_cross_run_comparison(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Validate *payload* against the cross_run_comparison schema."""
    findings: List[Dict[str, Any]] = []
    try:
        schema = _load_schema(_CRC_SCHEMA_PATH)
    except (OSError, json.JSONDecodeError) as exc:
        findings.append(
            _finding(
                code="schema_invalid",
                severity="error",
                message=f"Cannot load CRC schema: {exc}",
                artifact_path=str(_CRC_SCHEMA_PATH),
            )
        )
        return findings

    validator = Draft202012Validator(schema)
    for ve in sorted(validator.iter_errors(payload), key=lambda e: list(e.path)):
        field_path = ".".join(str(p) for p in ve.path) or "(root)"
        findings.append(
            _finding(
                code="schema_invalid",
                severity="error",
                message=f"{field_path}: {ve.message}",
                artifact_path="cross_run_comparison",
            )
        )
    return findings


def validate_cross_run_intelligence_decision(
    payload: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Validate *payload* against the cross_run_intelligence_decision schema."""
    findings: List[Dict[str, Any]] = []
    try:
        schema = _load_schema(_CRI_SCHEMA_PATH)
    except (OSError, json.JSONDecodeError) as exc:
        findings.append(
            _finding(
                code="schema_invalid",
                severity="error",
                message=f"Cannot load CRI schema: {exc}",
                artifact_path=str(_CRI_SCHEMA_PATH),
            )
        )
        return findings

    validator = Draft202012Validator(schema)
    for ve in sorted(validator.iter_errors(payload), key=lambda e: list(e.path)):
        field_path = ".".join(str(p) for p in ve.path) or "(root)"
        findings.append(
            _finding(
                code="schema_invalid",
                severity="error",
                message=f"{field_path}: {ve.message}",
                artifact_path="cross_run_intelligence_decision",
            )
        )
    return findings


# ---------------------------------------------------------------------------
# Top-level entry point
# ---------------------------------------------------------------------------


def compare_normalized_runs(
    input_paths: Optional[List[str]] = None,
    input_payloads: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Top-level BF entry point.

    Accepts either:
    - ``input_paths``: list of paths to normalized_run_result.json files
    - ``input_payloads``: pre-loaded list of NRR dicts (skips file loading)

    Returns a dict with:
    - ``cross_run_comparison``: the CRC artifact (or None on hard failure)
    - ``cross_run_intelligence_decision``: the CRI decision artifact
    - ``findings``: list of all findings
    """
    findings: List[Dict[str, Any]] = []
    nrr_payloads: List[Dict[str, Any]] = []

    # --- 1. Resolve inputs ---
    if input_payloads is not None:
        nrr_payloads = list(input_payloads)
    elif input_paths is not None and len(input_paths) > 0:
        for path_str in input_paths:
            try:
                payload = load_normalized_run_result(path_str)
                nrr_payloads.append(payload)
            except OSError as exc:
                findings.append(
                    _finding(
                        code="malformed_input",
                        severity="error",
                        message=f"Cannot read input file: {exc}",
                        artifact_path=str(path_str),
                    )
                )
            except json.JSONDecodeError as exc:
                findings.append(
                    _finding(
                        code="malformed_input",
                        severity="error",
                        message=f"Malformed JSON in input: {exc}",
                        artifact_path=str(path_str),
                    )
                )
    else:
        findings.append(
            _finding(
                code="no_inputs",
                severity="error",
                message="No input paths or payloads provided.",
                artifact_path="",
            )
        )

    if any(f["severity"] == "error" for f in findings):
        cmp_id = _comparison_id(_now_iso(), 0)
        decision = build_cross_run_intelligence_decision(
            comparison_id=cmp_id, findings=findings
        )
        return {
            "cross_run_comparison": None,
            "cross_run_intelligence_decision": decision,
            "findings": findings,
        }

    # --- 2. Validate each NRR against schema ---
    valid_payloads: List[Dict[str, Any]] = []
    for nrr in nrr_payloads:
        schema_findings = validate_normalized_run_result_input(nrr)
        if any(f["severity"] == "error" for f in schema_findings):
            bundle_id = nrr.get("source_bundle_id", "unknown")
            for sf in schema_findings:
                sf = dict(sf)
                sf["artifact_path"] = f"nrr:{bundle_id}"
                findings.append(sf)
        else:
            valid_payloads.append(nrr)

    if not valid_payloads:
        findings.append(
            _finding(
                code="schema_invalid",
                severity="error",
                message="No valid NRR inputs remained after schema validation.",
                artifact_path="",
            )
        )
        cmp_id = _comparison_id(_now_iso(), 0)
        decision = build_cross_run_intelligence_decision(
            comparison_id=cmp_id, findings=findings
        )
        return {
            "cross_run_comparison": None,
            "cross_run_intelligence_decision": decision,
            "findings": findings,
        }

    # --- 3. Check study type compatibility ---
    study_type, study_findings = infer_comparison_study_type(valid_payloads)
    findings.extend(study_findings)

    if study_type is None:
        cmp_id = _comparison_id(_now_iso(), len(valid_payloads))
        decision = build_cross_run_intelligence_decision(
            comparison_id=cmp_id, findings=findings
        )
        return {
            "cross_run_comparison": None,
            "cross_run_intelligence_decision": decision,
            "findings": findings,
        }

    # --- 4. Build comparison artifact ---
    try:
        crc = build_cross_run_comparison(valid_payloads)
    except Exception as exc:  # noqa: BLE001
        findings.append(
            _finding(
                code="comparison_error",
                severity="error",
                message=f"Comparison failed unexpectedly: {exc}",
                artifact_path="",
            )
        )
        cmp_id = _comparison_id(_now_iso(), len(valid_payloads))
        decision = build_cross_run_intelligence_decision(
            comparison_id=cmp_id, findings=findings
        )
        return {
            "cross_run_comparison": None,
            "cross_run_intelligence_decision": decision,
            "findings": findings,
        }

    comparison_id = crc["comparison_id"]

    # --- 5. Check for comparable metrics ---
    has_comparable = any(
        mc["comparability_status"] == "comparable"
        for mc in crc.get("metric_comparisons", [])
    )
    if not has_comparable:
        findings.append(
            _finding(
                code="no_comparable_metrics",
                severity="warning",
                message=(
                    "No metric was found to be comparable across the provided runs. "
                    "Rankings and anomaly detection are limited."
                ),
                artifact_path="",
            )
        )

    # --- 6. Surface anomaly flags as findings ---
    for flag in crc.get("anomaly_flags", []):
        findings.append(
            _finding(
                code=flag["flag_type"],
                severity=flag["severity"],
                message=flag["detail"],
                artifact_path="cross_run_comparison",
            )
        )

    # --- 7. Validate CRC schema ---
    crc_schema_findings = validate_cross_run_comparison(crc)
    findings.extend(crc_schema_findings)

    # --- 8. Build decision ---
    decision = build_cross_run_intelligence_decision(
        comparison_id=comparison_id, findings=findings
    )

    # --- 9. Validate decision schema ---
    cri_schema_findings = validate_cross_run_intelligence_decision(decision)
    findings.extend(cri_schema_findings)

    return {
        "cross_run_comparison": crc,
        "cross_run_intelligence_decision": decision,
        "findings": findings,
    }
