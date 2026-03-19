"""Run Output Normalization + Evaluation Layer (Prompt BE).

Reads a BD-valid run bundle manifest and its declared result/provenance
artifacts, normalises the outputs into a strict governed shape, performs
semantic completeness checks, attaches evaluation signals, and emits two
decision artifacts.

This layer assumes BD has already passed, but defends itself against
malformed or missing output files.

Failure types
-------------
none
    All checks pass.
missing_output_file
    A declared results_summary_json or provenance_json file is absent.
malformed_json
    A declared output file contains invalid JSON.
schema_invalid
    A produced normalized artifact fails schema validation.
semantic_incomplete
    Required metrics for the study type are missing.
unsupported_study_type
    study_type cannot be determined or is not in the governed enum.
missing_required_metric
    One or more required metrics are absent (synonym for semantic_incomplete
    used in classify logic).
invalid_threshold_definition
    A threshold definition in the manifest or results_summary is malformed.
normalization_error
    An unexpected error occurred during normalization.
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
_ROE_SCHEMA_PATH = _SCHEMA_DIR / "run_output_evaluation_decision.schema.json"

_SCHEMA_VERSION = "1.0.0"

# Governed study types
_STUDY_TYPES = frozenset(
    {"p2p_interference", "adjacency_analysis", "retuning_analysis", "sharing_study", "generic"}
)

# Required metric catalogs per study type
_REQUIRED_METRICS: Dict[str, List[str]] = {
    "p2p_interference": ["interference_power_dbm", "in_ratio_db", "path_loss_db"],
    "adjacency_analysis": ["frequency_separation_mhz", "interference_power_dbm"],
    "retuning_analysis": ["incumbent_links_impacted", "retune_candidate_count"],
    "sharing_study": ["interference_power_dbm", "affected_receivers_count"],
    "generic": [],
}

# Threshold operator functions
_OPERATORS = {
    "lt": lambda v, t: v < t,
    "lte": lambda v, t: v <= t,
    "gt": lambda v, t: v > t,
    "gte": lambda v, t: v >= t,
    "eq": lambda v, t: v == t,
}

# Failure type priority (lower = higher priority)
_FAILURE_PRIORITY: Dict[str, int] = {
    "missing_output_file": 0,
    "malformed_json": 1,
    "schema_invalid": 2,
    "normalization_error": 3,
    "unsupported_study_type": 4,
    "invalid_threshold_definition": 5,
    "missing_required_metric": 6,
    "semantic_incomplete": 7,
    "none": 99,
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _artifact_id(source_bundle_id: str, generated_at: str) -> str:
    digest = hashlib.sha256(
        f"NRR:{source_bundle_id}:{generated_at}".encode("utf-8")
    ).hexdigest()[:12].upper()
    return f"NRR-{digest}"


def _decision_id(source_bundle_id: str, generated_at: str) -> str:
    digest = hashlib.sha256(
        f"ROE:{source_bundle_id}:{generated_at}".encode("utf-8")
    ).hexdigest()[:12].upper()
    return f"ROE-{digest}"


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
# Public API — file loading
# ---------------------------------------------------------------------------


def load_json_file(path: Any) -> Any:
    """Load and parse a JSON file from *path*.

    Raises
    ------
    OSError
        When the file cannot be opened.
    json.JSONDecodeError
        When the file contains invalid JSON.
    """
    return json.loads(Path(path).read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Manifest path resolution
# ---------------------------------------------------------------------------


def resolve_manifest_output_paths(
    manifest: Dict[str, Any],
    bundle_root: Optional[Path],
) -> Dict[str, Any]:
    """Resolve declared output paths from *manifest* to absolute Paths.

    Returns a dict with keys:
    - ``results_summary_path`` — Path or None
    - ``provenance_path`` — Path or None
    Each value is an absolute :class:`Path` when a bundle_root is provided and
    the output type is declared, otherwise None.
    """
    expected_outputs: List[Dict[str, Any]] = manifest.get("expected_outputs") or []
    result: Dict[str, Any] = {
        "results_summary_path": None,
        "provenance_path": None,
    }
    for output in expected_outputs:
        otype = output.get("type", "")
        rel_path = output.get("path", "")
        if not rel_path:
            continue
        if bundle_root is not None:
            abs_path = Path(bundle_root) / rel_path
        else:
            abs_path = None
        if otype == "results_summary_json":
            result["results_summary_path"] = abs_path
        elif otype == "provenance_json":
            result["provenance_path"] = abs_path
    return result


# ---------------------------------------------------------------------------
# Extraction helpers
# ---------------------------------------------------------------------------


def extract_results_summary(outputs: Dict[str, Any]) -> Dict[str, Any]:
    """Return the parsed results_summary dict from *outputs*.

    *outputs* is the resolved_paths dict from resolve_manifest_output_paths
    combined with loaded content. Returns an empty dict when not available.
    """
    return outputs.get("results_summary_json") or {}


def extract_provenance(outputs: Dict[str, Any]) -> Dict[str, Any]:
    """Return the parsed provenance dict from *outputs*."""
    return outputs.get("provenance_json") or {}


# ---------------------------------------------------------------------------
# Study type inference
# ---------------------------------------------------------------------------


def infer_study_type(manifest: Dict[str, Any], results_summary: Dict[str, Any]) -> str:
    """Infer the study_type from *manifest* or *results_summary*.

    Priority:
    1. manifest["study_type"]
    2. results_summary["study_type"]
    3. "generic" as fallback
    """
    for source in (manifest, results_summary):
        st = source.get("study_type", "")
        if isinstance(st, str) and st.strip() in _STUDY_TYPES:
            return st.strip()
    return "generic"


# ---------------------------------------------------------------------------
# Required metrics
# ---------------------------------------------------------------------------


def get_required_metrics_for_study_type(study_type: str) -> List[str]:
    """Return the list of required metric names for *study_type*."""
    return list(_REQUIRED_METRICS.get(study_type, []))


# ---------------------------------------------------------------------------
# Metric normalization
# ---------------------------------------------------------------------------


def normalize_summary_metrics(
    study_type: str,
    results_summary: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Normalize result metrics into the governed summary_metrics array.

    Supports:
    - top-level "metrics" list
    - top-level "summary_metrics" list
    - flat scalar fields
    - nested "results" object
    """
    required = set(get_required_metrics_for_study_type(study_type))
    normalized: List[Dict[str, Any]] = []
    seen_names: set = set()

    def _emit(name: str, value: Any, unit: str, source_path: str) -> Dict[str, Any]:
        classification = "core" if name in required else "supporting"
        return {
            "name": name,
            "value": value,
            "unit": unit,
            "classification": classification,
            "source_path": source_path,
        }

    def _process_list(items: List[Any], prefix: str) -> None:
        for i, item in enumerate(items):
            if not isinstance(item, dict):
                continue
            name = item.get("name") or item.get("metric_name") or item.get("key")
            value = item.get("value") if "value" in item else item.get("val")
            unit = item.get("unit", "")
            if name is not None and value is not None:
                normalized.append(_emit(str(name), value, str(unit), f"{prefix}[{i}]"))
                seen_names.add(str(name))

    def _process_scalars(d: Dict[str, Any], prefix: str) -> None:
        skip_keys = {
            "metrics", "summary_metrics", "results", "study_type",
            "evaluation_thresholds", "scenario", "scenario_id",
            "scenario_label", "frequency_range_mhz", "assumptions_summary",
        }
        for key, val in d.items():
            if key in skip_keys:
                continue
            if key in seen_names:
                continue
            if isinstance(val, (int, float, bool)):
                normalized.append(_emit(key, val, "", f"/{key}"))
                seen_names.add(key)

    # 1. metrics list
    metrics_list = results_summary.get("metrics")
    if isinstance(metrics_list, list):
        _process_list(metrics_list, "/metrics")

    # 2. summary_metrics list
    summary_list = results_summary.get("summary_metrics")
    if isinstance(summary_list, list):
        _process_list(summary_list, "/summary_metrics")

    # 3. nested results object
    results_obj = results_summary.get("results")
    if isinstance(results_obj, dict):
        results_list = results_obj.get("metrics") or results_obj.get("summary_metrics")
        if isinstance(results_list, list):
            _process_list(results_list, "/results/metrics")
        else:
            _process_scalars(results_obj, "/results")

    # 4. flat scalar fields on the root
    _process_scalars(results_summary, "")

    return normalized


# ---------------------------------------------------------------------------
# Completeness
# ---------------------------------------------------------------------------


def compute_completeness(
    required_metrics: List[str],
    normalized_metrics: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Compute completeness statistics for *normalized_metrics*.

    Completeness status:
    - complete   — all required metrics present
    - partial    — some required metrics present but not all (and count > 0)
    - insufficient — no required metrics present (or required count is 0 and
                     normalized_metrics is empty, in which case complete)
    """
    present_names = {m["name"] for m in normalized_metrics}
    required_set = set(required_metrics)
    missing = [r for r in required_metrics if r not in present_names]
    present_count = len(required_set) - len(missing)

    total = len(required_set)
    if total == 0:
        status = "complete"
    elif present_count == total:
        status = "complete"
    elif present_count == 0:
        status = "insufficient"
    else:
        status = "partial"

    return {
        "required_metric_count": total,
        "present_required_metric_count": present_count,
        "missing_required_metrics": missing,
        "status": status,
    }


# ---------------------------------------------------------------------------
# Threshold assessments
# ---------------------------------------------------------------------------


def build_threshold_assessments(
    study_type: str,
    normalized_metrics: List[Dict[str, Any]],
    manifest: Dict[str, Any],
    results_summary: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Build threshold assessment objects from declared thresholds.

    Looks for threshold definitions in:
    1. manifest["evaluation_thresholds"]
    2. results_summary["evaluation_thresholds"]
    """
    metric_map = {m["name"]: m["value"] for m in normalized_metrics}
    assessments: List[Dict[str, Any]] = []

    threshold_sources = []
    for src_name, src in (("manifest", manifest), ("results_summary", results_summary)):
        thresholds = src.get("evaluation_thresholds")
        if isinstance(thresholds, list):
            for t in thresholds:
                threshold_sources.append((src_name, t))

    for src_name, threshold in threshold_sources:
        metric_name = threshold.get("metric_name", "")
        threshold_name = threshold.get("threshold_name", "")
        operator = threshold.get("operator", "")
        thresh_value = threshold.get("value")

        if not metric_name or not threshold_name or operator not in _OPERATORS or thresh_value is None:
            assessments.append({
                "metric_name": metric_name or "(unknown)",
                "threshold_name": threshold_name or "(unknown)",
                "status": "unknown",
                "detail": f"Malformed threshold definition in {src_name}.",
            })
            continue

        if metric_name not in metric_map:
            assessments.append({
                "metric_name": metric_name,
                "threshold_name": threshold_name,
                "status": "unknown",
                "detail": f"Metric '{metric_name}' not found in normalized metrics.",
            })
            continue

        metric_value = metric_map[metric_name]
        try:
            result = _OPERATORS[operator](metric_value, thresh_value)
            status = "pass" if result else "fail"
            detail = f"{metric_name} {operator} {thresh_value}: {metric_value} → {status}"
        except (TypeError, ValueError) as exc:
            status = "unknown"
            detail = f"Cannot evaluate threshold: {exc}"

        assessments.append({
            "metric_name": metric_name,
            "threshold_name": threshold_name,
            "status": status,
            "detail": detail,
        })

    return assessments


# ---------------------------------------------------------------------------
# Outlier detection
# ---------------------------------------------------------------------------


def detect_outlier_flags(normalized_metrics: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Detect numeric outlier conditions in *normalized_metrics*."""
    flags: List[Dict[str, Any]] = []
    for metric in normalized_metrics:
        name = metric.get("name", "")
        value = metric.get("value")
        if not isinstance(value, (int, float)):
            continue
        if isinstance(value, bool):
            continue
        if math.isnan(value):
            flags.append({
                "flag_type": "nan_value",
                "metric_name": name,
                "detail": f"Metric '{name}' has a NaN value.",
            })
        elif math.isinf(value):
            flags.append({
                "flag_type": "infinite_value",
                "metric_name": name,
                "detail": f"Metric '{name}' has an infinite value.",
            })
        elif abs(value) > 1e12:
            flags.append({
                "flag_type": "extreme_magnitude",
                "metric_name": name,
                "detail": f"Metric '{name}' has extreme magnitude: {value}.",
            })
    return flags


# ---------------------------------------------------------------------------
# Readiness computation
# ---------------------------------------------------------------------------


def compute_readiness(
    completeness: Dict[str, Any],
    threshold_assessments: List[Dict[str, Any]],
    findings: List[Dict[str, Any]],
) -> str:
    """Determine readiness signal from completeness, thresholds, and findings.

    Rules:
    - not_ready if completeness.status == insufficient OR any error-level finding
    - limited_use if completeness.status == partial OR any threshold fails OR any outlier flags
    - ready_for_comparison otherwise
    """
    if completeness.get("status") == "insufficient":
        return "not_ready"
    if any(f.get("severity") == "error" for f in findings):
        return "not_ready"
    if completeness.get("status") == "partial":
        return "limited_use"
    if any(a.get("status") == "fail" for a in threshold_assessments):
        return "limited_use"
    return "ready_for_comparison"


# ---------------------------------------------------------------------------
# Build normalized run result
# ---------------------------------------------------------------------------


def build_normalized_run_result(
    manifest: Dict[str, Any],
    results_summary: Dict[str, Any],
    provenance_json: Dict[str, Any],
    bundle_root: Optional[Path] = None,
) -> Dict[str, Any]:
    """Build the governed normalized_run_result artifact.

    Parameters
    ----------
    manifest:
        Raw manifest dict.
    results_summary:
        Parsed results_summary JSON content.
    provenance_json:
        Parsed provenance JSON content.
    bundle_root:
        Optional bundle root path for source path annotation.
    """
    generated_at = _now_iso()
    source_bundle_id = str(manifest.get("run_id", "unknown"))
    artifact_id = _artifact_id(source_bundle_id, generated_at)

    study_type = infer_study_type(manifest, results_summary)
    required = get_required_metrics_for_study_type(study_type)
    normalized_metrics = normalize_summary_metrics(study_type, results_summary)
    completeness = compute_completeness(required, normalized_metrics)
    threshold_assessments = build_threshold_assessments(
        study_type, normalized_metrics, manifest, results_summary
    )
    outlier_flags = detect_outlier_flags(normalized_metrics)

    # Build findings list for readiness (outlier flags as warnings)
    readiness_findings: List[Dict[str, Any]] = []
    for flag in outlier_flags:
        readiness_findings.append(
            _finding(
                code="outlier_detected",
                severity="warning",
                message=flag["detail"],
                artifact_path="",
            )
        )

    readiness = compute_readiness(completeness, threshold_assessments, readiness_findings)

    # Build trust notes
    trust_notes: List[str] = []
    if outlier_flags:
        trust_notes.append(f"{len(outlier_flags)} outlier flag(s) detected.")
    failed_thresholds = [a for a in threshold_assessments if a["status"] == "fail"]
    if failed_thresholds:
        trust_notes.append(
            f"{len(failed_thresholds)} threshold assessment(s) failed: "
            + ", ".join(a["threshold_name"] for a in failed_thresholds)
        )
    if completeness["status"] != "complete" and completeness["missing_required_metrics"]:
        trust_notes.append(
            "Missing required metrics: "
            + ", ".join(completeness["missing_required_metrics"])
        )

    # Scenario from manifest or results_summary
    scenario_raw = manifest.get("scenario") or results_summary.get("scenario") or {}
    freq_range = scenario_raw.get("frequency_range_mhz") or {}
    scenario = {
        "scenario_id": str(scenario_raw.get("scenario_id", source_bundle_id)),
        "scenario_label": str(scenario_raw.get("scenario_label", source_bundle_id)),
        "frequency_range_mhz": {
            "low_mhz": float(freq_range.get("low_mhz", 0.0)),
            "high_mhz": float(freq_range.get("high_mhz", 0.0)),
        },
        "assumptions_summary": str(scenario_raw.get("assumptions_summary", "")),
    }

    # Provenance
    manifest_prov = manifest.get("provenance") or {}
    rng_mode = "seed" if "rng_seed" in manifest_prov else "state_ref"
    rng_value = manifest_prov.get("rng_seed", manifest_prov.get("rng_state_ref", None))

    resolved_paths = resolve_manifest_output_paths(manifest, bundle_root)
    results_source = (
        str(resolved_paths["results_summary_path"])
        if resolved_paths.get("results_summary_path")
        else results_summary.get("_source_path", "")
    )
    prov_source = (
        str(resolved_paths["provenance_path"])
        if resolved_paths.get("provenance_path")
        else provenance_json.get("_source_path", "")
    )

    provenance = {
        "manifest_author": str(manifest_prov.get("manifest_author", "")),
        "source_case_ids": list(manifest_prov.get("source_case_ids") or []),
        "creation_context": str(manifest_prov.get("creation_context", "")),
        "rng_reference": {
            "mode": rng_mode,
            "value": rng_value,
        },
        "results_summary_source": results_source,
        "provenance_source": prov_source,
    }

    metric_set_id = f"mset-{source_bundle_id}-{generated_at[:10]}"

    return {
        "artifact_id": artifact_id,
        "artifact_type": "normalized_run_result",
        "schema_version": _SCHEMA_VERSION,
        "source_bundle_id": source_bundle_id,
        "study_type": study_type,
        "scenario": scenario,
        "metrics": {
            "metric_set_id": metric_set_id,
            "summary_metrics": normalized_metrics,
            "completeness": completeness,
        },
        "evaluation_signals": {
            "readiness": readiness,
            "outlier_flags": outlier_flags,
            "threshold_assessments": threshold_assessments,
            "trust_notes": trust_notes,
        },
        "provenance": provenance,
        "generated_at": generated_at,
    }


# ---------------------------------------------------------------------------
# Build evaluation decision
# ---------------------------------------------------------------------------


def classify_evaluation_failure(findings: List[Dict[str, Any]]) -> Tuple[str, str]:
    """Classify the overall status and failure_type from *findings*.

    Returns (overall_status, failure_type).
    """
    if not findings:
        return "pass", "none"

    has_error = any(f.get("severity") == "error" for f in findings)
    has_warning = any(f.get("severity") == "warning" for f in findings)

    # Map finding codes to failure_type
    code_to_failure = {
        "missing_output_file": "missing_output_file",
        "malformed_json": "malformed_json",
        "schema_invalid": "schema_invalid",
        "semantic_incomplete": "semantic_incomplete",
        "unsupported_study_type": "unsupported_study_type",
        "missing_required_metric": "missing_required_metric",
        "invalid_threshold_definition": "invalid_threshold_definition",
        "normalization_error": "normalization_error",
    }

    best_priority = 99
    best_failure_type = "none"
    for f in findings:
        code = f.get("code", "")
        ft = code_to_failure.get(code, "none")
        priority = _FAILURE_PRIORITY.get(ft, 99)
        if priority < best_priority:
            best_priority = priority
            best_failure_type = ft

    if has_error:
        return "fail", best_failure_type
    if has_warning:
        return "warning", "none"
    return "pass", "none"


def build_run_output_evaluation_decision(
    source_bundle_id: str,
    findings: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Build the governed run_output_evaluation_decision artifact."""
    generated_at = _now_iso()
    overall_status, failure_type = classify_evaluation_failure(findings)
    return {
        "artifact_type": "run_output_evaluation_decision",
        "schema_version": _SCHEMA_VERSION,
        "decision_id": _decision_id(source_bundle_id, generated_at),
        "source_bundle_id": source_bundle_id,
        "overall_status": overall_status,
        "failure_type": failure_type,
        "findings": findings,
        "generated_at": generated_at,
    }


# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------


def validate_normalized_run_result(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Validate *payload* against the normalized_run_result schema.

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


def validate_run_output_evaluation_decision(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Validate *payload* against the run_output_evaluation_decision schema."""
    findings: List[Dict[str, Any]] = []
    try:
        schema = _load_schema(_ROE_SCHEMA_PATH)
    except (OSError, json.JSONDecodeError) as exc:
        findings.append(
            _finding(
                code="schema_invalid",
                severity="error",
                message=f"Cannot load ROE schema: {exc}",
                artifact_path=str(_ROE_SCHEMA_PATH),
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
                artifact_path="run_output_evaluation_decision",
            )
        )
    return findings


# ---------------------------------------------------------------------------
# Top-level entry point
# ---------------------------------------------------------------------------


def evaluate_run_outputs(
    manifest_path: Any = None,
    bundle_root: Any = None,
    manifest_payload: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Top-level BE evaluation entry point.

    Accepts:
    - manifest_path: path to the run_bundle_manifest.json
    - bundle_root: path to the bundle root directory (used to resolve outputs)
    - manifest_payload: pre-loaded manifest dict (skips file loading when provided)

    Returns a dict with:
    - ``normalized_run_result``: the NRR artifact (or None on hard failure)
    - ``run_output_evaluation_decision``: the ROE decision artifact
    - ``findings``: list of all findings
    """
    findings: List[Dict[str, Any]] = []

    # --- 1. Load manifest ---
    manifest: Dict[str, Any] = {}
    if manifest_payload is not None:
        manifest = manifest_payload
    elif manifest_path is not None:
        try:
            manifest = load_json_file(manifest_path)
        except OSError as exc:
            findings.append(
                _finding(
                    code="missing_output_file",
                    severity="error",
                    message=f"Cannot read manifest: {exc}",
                    artifact_path=str(manifest_path),
                )
            )
            decision = build_run_output_evaluation_decision(
                source_bundle_id="unknown", findings=findings
            )
            return {
                "normalized_run_result": None,
                "run_output_evaluation_decision": decision,
                "findings": findings,
            }
        except json.JSONDecodeError as exc:
            findings.append(
                _finding(
                    code="malformed_json",
                    severity="error",
                    message=f"Malformed JSON in manifest: {exc}",
                    artifact_path=str(manifest_path),
                )
            )
            decision = build_run_output_evaluation_decision(
                source_bundle_id="unknown", findings=findings
            )
            return {
                "normalized_run_result": None,
                "run_output_evaluation_decision": decision,
                "findings": findings,
            }
    else:
        findings.append(
            _finding(
                code="missing_output_file",
                severity="error",
                message="No manifest_path or manifest_payload provided.",
                artifact_path="",
            )
        )
        decision = build_run_output_evaluation_decision(
            source_bundle_id="unknown", findings=findings
        )
        return {
            "normalized_run_result": None,
            "run_output_evaluation_decision": decision,
            "findings": findings,
        }

    source_bundle_id = str(manifest.get("run_id", "unknown"))

    # --- 2. Resolve output paths ---
    resolved_root = Path(bundle_root).resolve() if bundle_root is not None else None
    resolved_paths = resolve_manifest_output_paths(manifest, resolved_root)

    # --- 3. Load results_summary ---
    results_summary: Dict[str, Any] = {}
    rs_path = resolved_paths.get("results_summary_path")
    if rs_path is not None:
        try:
            results_summary = load_json_file(rs_path)
            results_summary["_source_path"] = str(rs_path)
        except OSError as exc:
            findings.append(
                _finding(
                    code="missing_output_file",
                    severity="error",
                    message=f"results_summary_json file not found: {exc}",
                    artifact_path=str(rs_path),
                )
            )
        except json.JSONDecodeError as exc:
            findings.append(
                _finding(
                    code="malformed_json",
                    severity="error",
                    message=f"Malformed JSON in results_summary: {exc}",
                    artifact_path=str(rs_path),
                )
            )

    # --- 4. Load provenance ---
    provenance_json: Dict[str, Any] = {}
    prov_path = resolved_paths.get("provenance_path")
    if prov_path is not None:
        try:
            provenance_json = load_json_file(prov_path)
            provenance_json["_source_path"] = str(prov_path)
        except OSError as exc:
            findings.append(
                _finding(
                    code="missing_output_file",
                    severity="error",
                    message=f"provenance_json file not found: {exc}",
                    artifact_path=str(prov_path),
                )
            )
        except json.JSONDecodeError as exc:
            findings.append(
                _finding(
                    code="malformed_json",
                    severity="error",
                    message=f"Malformed JSON in provenance: {exc}",
                    artifact_path=str(prov_path),
                )
            )

    # --- 5. Check for hard errors before normalization ---
    if any(f["severity"] == "error" for f in findings):
        decision = build_run_output_evaluation_decision(
            source_bundle_id=source_bundle_id, findings=findings
        )
        return {
            "normalized_run_result": None,
            "run_output_evaluation_decision": decision,
            "findings": findings,
        }

    # --- 6. Build normalized run result ---
    try:
        nrr = build_normalized_run_result(
            manifest=manifest,
            results_summary=results_summary,
            provenance_json=provenance_json,
            bundle_root=resolved_root,
        )
    except Exception as exc:  # noqa: BLE001
        findings.append(
            _finding(
                code="normalization_error",
                severity="error",
                message=f"Normalization failed unexpectedly: {exc}",
                artifact_path="",
            )
        )
        decision = build_run_output_evaluation_decision(
            source_bundle_id=source_bundle_id, findings=findings
        )
        return {
            "normalized_run_result": None,
            "run_output_evaluation_decision": decision,
            "findings": findings,
        }

    # --- 7. Add completeness findings ---
    completeness = nrr["metrics"]["completeness"]
    if completeness["status"] == "insufficient":
        findings.append(
            _finding(
                code="semantic_incomplete",
                severity="error",
                message=(
                    f"Insufficient metrics for study_type '{nrr['study_type']}'. "
                    f"Missing: {completeness['missing_required_metrics']}"
                ),
                artifact_path="results_summary_json",
            )
        )
    elif completeness["status"] == "partial":
        findings.append(
            _finding(
                code="semantic_incomplete",
                severity="warning",
                message=(
                    f"Partial metrics for study_type '{nrr['study_type']}'. "
                    f"Missing: {completeness['missing_required_metrics']}"
                ),
                artifact_path="results_summary_json",
            )
        )

    # --- 8. Add outlier findings ---
    for flag in nrr["evaluation_signals"]["outlier_flags"]:
        findings.append(
            _finding(
                code="outlier_detected",
                severity="warning",
                message=flag["detail"],
                artifact_path="results_summary_json",
            )
        )

    # --- 9. Add threshold findings ---
    for assessment in nrr["evaluation_signals"]["threshold_assessments"]:
        if assessment["status"] == "fail":
            findings.append(
                _finding(
                    code="threshold_failed",
                    severity="warning",
                    message=assessment["detail"],
                    artifact_path="results_summary_json",
                )
            )
        elif assessment["status"] == "unknown":
            findings.append(
                _finding(
                    code="invalid_threshold_definition",
                    severity="warning",
                    message=assessment["detail"],
                    artifact_path="results_summary_json",
                )
            )

    # --- 10. Validate NRR schema ---
    schema_findings = validate_normalized_run_result(nrr)
    findings.extend(schema_findings)
    if any(f["severity"] == "error" for f in schema_findings):
        decision = build_run_output_evaluation_decision(
            source_bundle_id=source_bundle_id, findings=findings
        )
        return {
            "normalized_run_result": nrr,
            "run_output_evaluation_decision": decision,
            "findings": findings,
        }

    # --- 11. Build final decision ---
    decision = build_run_output_evaluation_decision(
        source_bundle_id=source_bundle_id, findings=findings
    )

    return {
        "normalized_run_result": nrr,
        "run_output_evaluation_decision": decision,
        "findings": findings,
    }
