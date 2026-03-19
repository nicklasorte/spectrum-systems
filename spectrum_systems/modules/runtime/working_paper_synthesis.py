"""Working Paper Evidence Pack Synthesis Layer (Prompt BG).

Consumes BE normalized_run_result artifacts and an optional BF
cross_run_comparison artifact. Produces a governed evidence pack organised by
working-paper-relevant sections plus a synthesis decision artifact.

This layer does NOT generate polished final prose. Its job is to assemble
trustworthy, traceable, decision-relevant evidence blocks that can later feed
working paper generation.

Failure types
-------------
none
    Synthesis completed without errors or warnings.
no_inputs
    No BE or BF inputs were provided.
malformed_input
    An input file contained invalid JSON or could not be read.
schema_invalid
    An input artifact failed schema validation against its governed schema.
mixed_study_types
    Multiple conflicting non-generic study types across BE inputs.
insufficient_evidence
    Evidence from the provided inputs is too thin to support any meaningful pack.
synthesis_error
    An unexpected error occurred during evidence synthesis.
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
_WPE_SCHEMA_PATH = _SCHEMA_DIR / "working_paper_evidence_pack.schema.json"
_WPS_SCHEMA_PATH = _SCHEMA_DIR / "working_paper_synthesis_decision.schema.json"

_SCHEMA_VERSION = "1.0.0"

_STRONG_STUDY_TYPES = frozenset(
    {"p2p_interference", "adjacency_analysis", "retuning_analysis", "sharing_study"}
)

# Section definitions: key → title
_SECTION_DEFS: List[Tuple[str, str]] = [
    ("executive_summary", "Executive Summary"),
    ("study_objective", "Study Objective"),
    ("technical_findings", "Technical Findings"),
    ("comparative_results", "Comparative Results"),
    ("operational_implications", "Operational Implications"),
    ("limitations_and_caveats", "Limitations and Caveats"),
    ("agency_questions", "Agency Questions"),
    ("recommended_next_steps", "Recommended Next Steps"),
]

# Evidence types that route to each section by default
_SECTION_EVIDENCE_TYPES: Dict[str, List[str]] = {
    "executive_summary": [],  # Populated from ranked_findings only
    "study_objective": ["scenario_summary"],
    "technical_findings": ["metric_observation", "threshold_result"],
    "comparative_results": ["ranked_result"],
    "operational_implications": [],  # Populated from high-priority findings
    "limitations_and_caveats": ["completeness_gap", "anomaly", "caveat"],
    "agency_questions": [],  # Populated from followup_questions
    "recommended_next_steps": [],  # Populated from evidence-triggered actions
}

# Failure priority (lower = higher priority)
_FAILURE_PRIORITY: Dict[str, int] = {
    "no_inputs": 0,
    "malformed_input": 1,
    "schema_invalid": 2,
    "mixed_study_types": 3,
    "synthesis_error": 4,
    "insufficient_evidence": 5,
    "none": 99,
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha_id(prefix: str, seed: str) -> str:
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:12].upper()
    return f"{prefix}-{digest}"


def _load_schema(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _finding(code: str, severity: str, message: str, artifact_path: str = "") -> Dict[str, Any]:
    return {
        "code": code,
        "severity": severity,
        "message": message,
        "artifact_path": artifact_path,
    }


def _counter(prefix: str, base: str, idx: int) -> str:
    seed = f"{prefix}:{base}:{idx}"
    return _sha_id(prefix, seed)


# ---------------------------------------------------------------------------
# Public API — artifact loading
# ---------------------------------------------------------------------------


def load_governed_artifact(path: Any) -> Any:
    """Load and parse a governed JSON artifact from *path*.

    Raises
    ------
    OSError
        When the file cannot be opened.
    json.JSONDecodeError
        When the file contains invalid JSON.
    """
    return json.loads(Path(path).read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------


def validate_be_input(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
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


def validate_bf_input(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Validate *payload* against the governed CRC schema.

    Returns a list of finding dicts (empty = valid).
    """
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


# ---------------------------------------------------------------------------
# Study type inference
# ---------------------------------------------------------------------------


def infer_synthesis_study_type(
    be_payloads: List[Dict[str, Any]],
    bf_payload: Optional[Dict[str, Any]],
) -> Tuple[Optional[str], List[Dict[str, Any]]]:
    """Determine the governing study type for this synthesis.

    Returns ``(study_type, findings)``.
    - Single non-generic type across all BE inputs: use it.
    - All generic: use generic.
    - Multiple conflicting non-generic: return None + error finding.
    - BF study_type conflicts with resolved BE study_type: warning.
    """
    findings: List[Dict[str, Any]] = []

    be_types = [p.get("study_type", "generic") for p in be_payloads]
    strong_types = [t for t in be_types if t in _STRONG_STUDY_TYPES]
    distinct_strong = set(strong_types)

    if len(distinct_strong) > 1:
        findings.append(
            _finding(
                code="mixed_study_types",
                severity="error",
                message=(
                    f"Multiple conflicting study types across BE inputs: "
                    f"{sorted(distinct_strong)}. Cannot synthesize mixed study types."
                ),
                artifact_path="",
            )
        )
        return None, findings

    if len(distinct_strong) == 1:
        resolved = next(iter(distinct_strong))
    else:
        resolved = "generic"

    if bf_payload is not None:
        bf_type = bf_payload.get("study_type", "generic")
        if bf_type not in ("generic", resolved) and bf_type in _STRONG_STUDY_TYPES:
            findings.append(
                _finding(
                    code="study_type_mismatch",
                    severity="warning",
                    message=(
                        f"BF study_type={bf_type!r} differs from resolved BE study_type={resolved!r}. "
                        "BF evidence may carry comparability caveats."
                    ),
                    artifact_path="cross_run_comparison",
                )
            )

    return resolved, findings


# ---------------------------------------------------------------------------
# Source artifact collection
# ---------------------------------------------------------------------------


def collect_source_artifacts(
    be_payloads: List[Dict[str, Any]],
    bf_payload: Optional[Dict[str, Any]],
    input_refs: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """Build the source_artifacts array from input payloads.

    *input_refs* provides the file paths or references matching be_payloads
    (index-aligned). BF reference appended last when present.
    """
    refs = list(input_refs) if input_refs else []
    source: List[Dict[str, Any]] = []

    for i, be in enumerate(be_payloads):
        ref = refs[i] if i < len(refs) else ""
        source.append(
            {
                "artifact_type": "normalized_run_result",
                "artifact_id": str(be.get("artifact_id", f"NRR-UNKNOWN-{i}")),
                "source_bundle_id": str(be.get("source_bundle_id", "unknown")),
                "path_or_reference": str(ref),
            }
        )

    if bf_payload is not None:
        bf_ref = refs[len(be_payloads)] if len(refs) > len(be_payloads) else ""
        source.append(
            {
                "artifact_type": "cross_run_comparison",
                "artifact_id": str(bf_payload.get("artifact_id", "CRC-UNKNOWN")),
                "source_bundle_id": bf_payload.get("comparison_id", ""),
                "path_or_reference": str(bf_ref),
            }
        )

    return source


# ---------------------------------------------------------------------------
# Section skeleton
# ---------------------------------------------------------------------------


def map_evidence_sections(study_type: str) -> List[Dict[str, Any]]:
    """Return the initial empty section skeleton for *study_type*."""
    sections: List[Dict[str, Any]] = []
    for key, title in _SECTION_DEFS:
        sections.append(
            {
                "section_key": key,
                "section_title": title,
                "evidence_items": [],
                "synthesis_status": "empty",
            }
        )
    return sections


# ---------------------------------------------------------------------------
# Confidence helpers
# ---------------------------------------------------------------------------


def _confidence_for_be(be: Dict[str, Any], evidence_type: str) -> str:
    """Determine confidence for a BE-sourced evidence item."""
    eval_signals = be.get("evaluation_signals") or {}
    readiness = eval_signals.get("readiness", "not_ready")
    metrics = be.get("metrics") or {}
    completeness = metrics.get("completeness") or {}
    status = completeness.get("status", "insufficient")

    if readiness == "ready_for_comparison" and status == "complete":
        return "high"
    if readiness == "limited_use" and status in ("complete", "partial"):
        return "medium"
    if evidence_type in ("completeness_gap", "anomaly", "caveat"):
        return "low"
    return "low"


def _confidence_for_bf_ranked(bf: Dict[str, Any]) -> str:
    """Determine confidence for BF-sourced ranked result evidence."""
    compared_runs = bf.get("compared_runs") or []
    ready_count = sum(
        1 for r in compared_runs if r.get("readiness") == "ready_for_comparison"
    )
    if ready_count >= 2:
        return "high"
    return "medium"


def _confidence_for_bf_anomaly(anomaly: Dict[str, Any]) -> str:
    sev = anomaly.get("severity", "info")
    if sev == "error":
        return "high"
    if sev == "warning":
        return "medium"
    return "low"


# ---------------------------------------------------------------------------
# Evidence extraction from BE
# ---------------------------------------------------------------------------


def build_evidence_items_from_be(be_payloads: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Extract evidence items from all BE normalized_run_result payloads."""
    items: List[Dict[str, Any]] = []
    item_idx = 0

    for be in be_payloads:
        artifact_id = str(be.get("artifact_id", "NRR-UNKNOWN"))
        bundle_id = str(be.get("source_bundle_id", "unknown"))
        scenario = be.get("scenario") or {}
        scenario_id = str(scenario.get("scenario_id", "unknown"))
        eval_signals = be.get("evaluation_signals") or {}
        metrics = be.get("metrics") or {}
        completeness = metrics.get("completeness") or {}

        # --- Scenario summary ---
        if scenario.get("scenario_label"):
            evi_id = _counter("EVI", f"scen:{artifact_id}", item_idx)
            item_idx += 1
            items.append(
                {
                    "evidence_id": evi_id,
                    "evidence_type": "scenario_summary",
                    "statement": (
                        f"Scenario {scenario_id!r} ({scenario.get('scenario_label', '')}) "
                        f"from bundle {bundle_id!r}: "
                        f"{scenario.get('assumptions_summary', '')}"
                    ).strip(),
                    "support": {
                        "metric_name": "",
                        "value": "",
                        "unit": "",
                        "comparison_context": "",
                    },
                    "confidence": _confidence_for_be(be, "scenario_summary"),
                    "traceability": {
                        "source_artifact_id": artifact_id,
                        "source_bundle_id": bundle_id,
                        "source_path": "scenario",
                    },
                }
            )

        # --- Metric observations ---
        summary_metrics = metrics.get("summary_metrics") or []
        for m in summary_metrics:
            m_name = str(m.get("name", ""))
            m_value = m.get("value")
            m_unit = str(m.get("unit", ""))
            m_src = str(m.get("source_path", ""))
            if not m_name:
                continue

            value_str = str(m_value) if m_value is not None else ""
            evi_id = _counter("EVI", f"metric:{artifact_id}:{m_name}", item_idx)
            item_idx += 1
            items.append(
                {
                    "evidence_id": evi_id,
                    "evidence_type": "metric_observation",
                    "statement": (
                        f"Metric {m_name!r} = {value_str} {m_unit} "
                        f"for scenario {scenario_id!r} (bundle {bundle_id!r})."
                    ).strip(),
                    "support": {
                        "metric_name": m_name,
                        "value": value_str,
                        "unit": m_unit,
                        "comparison_context": "",
                    },
                    "confidence": _confidence_for_be(be, "metric_observation"),
                    "traceability": {
                        "source_artifact_id": artifact_id,
                        "source_bundle_id": bundle_id,
                        "source_path": m_src,
                    },
                }
            )

        # --- Threshold results ---
        for ta in eval_signals.get("threshold_assessments") or []:
            m_name = str(ta.get("metric_name", ""))
            t_name = str(ta.get("threshold_name", ""))
            t_status = str(ta.get("status", "unknown"))
            t_detail = str(ta.get("detail", ""))

            evi_id = _counter("EVI", f"threshold:{artifact_id}:{m_name}:{t_name}", item_idx)
            item_idx += 1
            items.append(
                {
                    "evidence_id": evi_id,
                    "evidence_type": "threshold_result",
                    "statement": (
                        f"Threshold {t_name!r} for metric {m_name!r}: status={t_status}. {t_detail}"
                    ).strip(),
                    "support": {
                        "metric_name": m_name,
                        "value": t_status,
                        "unit": "",
                        "comparison_context": "",
                    },
                    "confidence": _confidence_for_be(be, "threshold_result"),
                    "traceability": {
                        "source_artifact_id": artifact_id,
                        "source_bundle_id": bundle_id,
                        "source_path": "evaluation_signals.threshold_assessments",
                    },
                }
            )

        # --- Completeness gaps ---
        missing_metrics = completeness.get("missing_required_metrics") or []
        for missing_m in missing_metrics:
            evi_id = _counter("EVI", f"gap:{artifact_id}:{missing_m}", item_idx)
            item_idx += 1
            items.append(
                {
                    "evidence_id": evi_id,
                    "evidence_type": "completeness_gap",
                    "statement": (
                        f"Required metric {missing_m!r} is absent from bundle {bundle_id!r} "
                        f"(scenario {scenario_id!r}). Completeness status: "
                        f"{completeness.get('status', 'unknown')}."
                    ),
                    "support": {
                        "metric_name": missing_m,
                        "value": "",
                        "unit": "",
                        "comparison_context": "",
                    },
                    "confidence": "low",
                    "traceability": {
                        "source_artifact_id": artifact_id,
                        "source_bundle_id": bundle_id,
                        "source_path": "metrics.completeness.missing_required_metrics",
                    },
                }
            )

        # --- Readiness caveat when not ready_for_comparison ---
        readiness = eval_signals.get("readiness", "not_ready")
        if readiness in ("limited_use", "not_ready"):
            evi_id = _counter("EVI", f"readiness:{artifact_id}", item_idx)
            item_idx += 1
            trust_notes = eval_signals.get("trust_notes") or []
            note_str = " ".join(trust_notes) if trust_notes else ""
            items.append(
                {
                    "evidence_id": evi_id,
                    "evidence_type": "caveat",
                    "statement": (
                        f"Bundle {bundle_id!r} has readiness={readiness!r} for scenario {scenario_id!r}. "
                        f"{note_str}"
                    ).strip(),
                    "support": {
                        "metric_name": "",
                        "value": readiness,
                        "unit": "",
                        "comparison_context": "",
                    },
                    "confidence": "low",
                    "traceability": {
                        "source_artifact_id": artifact_id,
                        "source_bundle_id": bundle_id,
                        "source_path": "evaluation_signals.readiness",
                    },
                }
            )

    return items


# ---------------------------------------------------------------------------
# Evidence extraction from BF
# ---------------------------------------------------------------------------


def build_evidence_items_from_bf(
    bf_payload: Optional[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Extract evidence items from an optional BF cross_run_comparison payload."""
    if bf_payload is None:
        return []

    items: List[Dict[str, Any]] = []
    item_idx = 0
    artifact_id = str(bf_payload.get("artifact_id", "CRC-UNKNOWN"))
    comparison_id = str(bf_payload.get("comparison_id", "unknown"))

    # --- Scenario rankings → ranked_result evidence ---
    for ranking in bf_payload.get("scenario_rankings") or []:
        basis = str(ranking.get("ranking_basis", ""))
        direction = str(ranking.get("direction", ""))
        for ranked_sc in ranking.get("ranked_scenarios") or []:
            rank = ranked_sc.get("rank", 0)
            bundle_id = str(ranked_sc.get("source_bundle_id", "unknown"))
            sc_id = str(ranked_sc.get("scenario_id", "unknown"))
            sc_label = str(ranked_sc.get("scenario_label", ""))
            metric_name = str(ranked_sc.get("metric_name", ""))
            value = ranked_sc.get("value")

            value_str = str(value) if value is not None else ""
            evi_id = _counter("EVI", f"rank:{artifact_id}:{basis}:{sc_id}:{rank}", item_idx)
            item_idx += 1
            ctx = f"Ranked #{rank} ({direction}) across {len(bf_payload.get('compared_runs', []))} runs."
            items.append(
                {
                    "evidence_id": evi_id,
                    "evidence_type": "ranked_result",
                    "statement": (
                        f"Scenario {sc_id!r} ({sc_label}) ranks #{rank} {direction} "
                        f"on {basis!r}: value={value_str}."
                    ),
                    "support": {
                        "metric_name": metric_name,
                        "value": value_str,
                        "unit": "",
                        "comparison_context": ctx,
                    },
                    "confidence": _confidence_for_bf_ranked(bf_payload),
                    "traceability": {
                        "source_artifact_id": artifact_id,
                        "source_bundle_id": comparison_id,
                        "source_path": "scenario_rankings",
                    },
                }
            )

    # --- Anomaly flags → anomaly evidence ---
    for anomaly in bf_payload.get("anomaly_flags") or []:
        flag_type = str(anomaly.get("flag_type", "unknown"))
        severity = str(anomaly.get("severity", "info"))
        metric_name = str(anomaly.get("metric_name", ""))
        detail = str(anomaly.get("detail", ""))
        affected = anomaly.get("affected_runs") or []

        evi_id = _counter("EVI", f"anomaly:{artifact_id}:{flag_type}:{metric_name}", item_idx)
        item_idx += 1
        items.append(
            {
                "evidence_id": evi_id,
                "evidence_type": "anomaly",
                "statement": (
                    f"Anomaly {flag_type!r} (severity={severity}) on metric {metric_name!r}: {detail}"
                ).strip(),
                "support": {
                    "metric_name": metric_name,
                    "value": flag_type,
                    "unit": "",
                    "comparison_context": f"Affects: {', '.join(affected)}",
                },
                "confidence": _confidence_for_bf_anomaly(anomaly),
                "traceability": {
                    "source_artifact_id": artifact_id,
                    "source_bundle_id": comparison_id,
                    "source_path": "anomaly_flags",
                },
            }
        )

    # --- Mixed-unit comparisons → caveat evidence ---
    for mc in bf_payload.get("metric_comparisons") or []:
        if mc.get("comparability_status") == "mixed_units":
            m_name = str(mc.get("metric_name", ""))
            evi_id = _counter("EVI", f"mixed_units:{artifact_id}:{m_name}", item_idx)
            item_idx += 1
            units = {cv.get("unit", "") for cv in mc.get("compared_values") or []}
            items.append(
                {
                    "evidence_id": evi_id,
                    "evidence_type": "caveat",
                    "statement": (
                        f"Metric {m_name!r} has mixed units across compared runs "
                        f"({sorted(units)}); direct comparison is not valid."
                    ),
                    "support": {
                        "metric_name": m_name,
                        "value": "mixed_units",
                        "unit": "",
                        "comparison_context": f"Units seen: {sorted(units)}",
                    },
                    "confidence": "low",
                    "traceability": {
                        "source_artifact_id": artifact_id,
                        "source_bundle_id": comparison_id,
                        "source_path": "metric_comparisons",
                    },
                }
            )

    return items


# ---------------------------------------------------------------------------
# Section assignment
# ---------------------------------------------------------------------------


def assign_evidence_to_sections(
    evidence_items: List[Dict[str, Any]],
    study_type: str,
) -> List[Dict[str, Any]]:
    """Assign evidence items to section skeletons and compute synthesis_status.

    Returns a populated section_evidence list.
    """
    sections = map_evidence_sections(study_type)
    # Build a lookup by section_key for fast assignment
    section_map: Dict[str, Dict[str, Any]] = {s["section_key"]: s for s in sections}

    for evi in evidence_items:
        evi_type = evi.get("evidence_type", "")
        # Route by evidence type
        for key, types in _SECTION_EVIDENCE_TYPES.items():
            if evi_type in types:
                section_map[key]["evidence_items"].append(evi)
                break

    # Compute synthesis_status
    for section in sections:
        section["synthesis_status"] = compute_synthesis_status(section)

    return sections


def compute_synthesis_status(section: Dict[str, Any]) -> str:
    """Return populated/partial/empty based on section evidence items."""
    items = section.get("evidence_items") or []
    if not items:
        return "empty"
    # partial when any completeness_gap or caveat is present alongside other types
    types = {i.get("evidence_type") for i in items}
    gap_types = {"completeness_gap", "caveat"}
    content_types = types - gap_types
    if content_types and gap_types & types:
        return "partial"
    if content_types:
        return "populated"
    # only gaps/caveats
    return "partial"


# ---------------------------------------------------------------------------
# Ranked findings derivation
# ---------------------------------------------------------------------------


def derive_ranked_findings(
    section_evidence: List[Dict[str, Any]],
    study_type: str,
) -> List[Dict[str, Any]]:
    """Derive sparse, priority-ordered ranked findings from section evidence.

    Targets 3–7 findings when evidence exists.
    """
    findings: List[Dict[str, Any]] = []
    idx = 0

    # Collect all evidence items indexed by evidence_id
    all_items: Dict[str, Dict[str, Any]] = {}
    for sec in section_evidence:
        for evi in sec.get("evidence_items") or []:
            all_items[evi["evidence_id"]] = evi

    ranked_items = [i for i in all_items.values() if i["evidence_type"] == "ranked_result"]
    anomaly_items = [i for i in all_items.values() if i["evidence_type"] == "anomaly"]
    threshold_items = [i for i in all_items.values() if i["evidence_type"] == "threshold_result"]
    metric_items = [i for i in all_items.values() if i["evidence_type"] == "metric_observation"]
    gap_items = [i for i in all_items.values() if i["evidence_type"] == "completeness_gap"]

    # --- Critical: major anomaly with error severity ---
    for anomaly in anomaly_items:
        confidence = anomaly.get("confidence", "low")
        if confidence == "high":
            fid = _counter("FND", f"anomaly:{anomaly['evidence_id']}", idx)
            idx += 1
            findings.append(
                {
                    "finding_id": fid,
                    "priority": "critical",
                    "headline": f"Major anomaly detected: {anomaly['support']['metric_name'] or 'cross-run'}",
                    "rationale": anomaly["statement"],
                    "supporting_evidence_ids": [anomaly["evidence_id"]],
                }
            )
            if len(findings) >= 7:
                return findings

    # --- Critical: severe completeness gap blocking conclusions ---
    large_gaps = [g for g in gap_items if g.get("confidence", "low") == "low"]
    if len(large_gaps) >= 2:
        fid = _counter("FND", f"gaps:{len(large_gaps)}", idx)
        idx += 1
        findings.append(
            {
                "finding_id": fid,
                "priority": "critical",
                "headline": f"Severe evidence gap: {len(large_gaps)} required metric(s) missing across inputs",
                "rationale": (
                    f"{len(large_gaps)} required metrics are absent. "
                    "Key conclusions may be blocked."
                ),
                "supporting_evidence_ids": [g["evidence_id"] for g in large_gaps[:3]],
            }
        )
        if len(findings) >= 7:
            return findings

    # --- High: strongest ranked result (rank 1) ---
    rank1_items = [
        i for i in ranked_items
        if "ranks #1" in i.get("statement", "") and i.get("confidence") in ("high", "medium")
    ]
    for ri in rank1_items[:1]:
        fid = _counter("FND", f"rank1:{ri['evidence_id']}", idx)
        idx += 1
        findings.append(
            {
                "finding_id": fid,
                "priority": "high",
                "headline": f"Top-ranked scenario on {ri['support']['metric_name'] or 'primary metric'}",
                "rationale": ri["statement"],
                "supporting_evidence_ids": [ri["evidence_id"]],
            }
        )
        if len(findings) >= 7:
            return findings

    # --- High: threshold failure ---
    for ti in threshold_items:
        if "fail" in ti.get("statement", "").lower():
            fid = _counter("FND", f"threshold_fail:{ti['evidence_id']}", idx)
            idx += 1
            findings.append(
                {
                    "finding_id": fid,
                    "priority": "high",
                    "headline": f"Threshold failure: {ti['support']['metric_name'] or 'metric'}",
                    "rationale": ti["statement"],
                    "supporting_evidence_ids": [ti["evidence_id"]],
                }
            )
            if len(findings) >= 7:
                return findings

    # --- Medium: notable metric pattern (high-confidence metrics) ---
    high_conf_metrics = [m for m in metric_items if m.get("confidence") == "high"]
    for mi in high_conf_metrics[:2]:
        fid = _counter("FND", f"metric:{mi['evidence_id']}", idx)
        idx += 1
        findings.append(
            {
                "finding_id": fid,
                "priority": "medium",
                "headline": f"Core metric result: {mi['support']['metric_name']}",
                "rationale": mi["statement"],
                "supporting_evidence_ids": [mi["evidence_id"]],
            }
        )
        if len(findings) >= 7:
            return findings

    # --- Medium: limited-use ranked result ---
    medium_ranked = [i for i in ranked_items if i.get("confidence") == "medium"]
    for ri in medium_ranked[:1]:
        fid = _counter("FND", f"medium_rank:{ri['evidence_id']}", idx)
        idx += 1
        findings.append(
            {
                "finding_id": fid,
                "priority": "medium",
                "headline": f"Comparative result available with limited confidence: {ri['support']['metric_name'] or 'metric'}",
                "rationale": ri["statement"],
                "supporting_evidence_ids": [ri["evidence_id"]],
            }
        )
        if len(findings) >= 7:
            return findings

    # --- Low: background metric observations ---
    low_metrics = [m for m in metric_items if m.get("confidence") in ("medium", "low")]
    for mi in low_metrics[:1]:
        fid = _counter("FND", f"background:{mi['evidence_id']}", idx)
        idx += 1
        findings.append(
            {
                "finding_id": fid,
                "priority": "low",
                "headline": f"Background observation: {mi['support']['metric_name']}",
                "rationale": mi["statement"],
                "supporting_evidence_ids": [mi["evidence_id"]],
            }
        )
        if len(findings) >= 7:
            return findings

    return findings


# ---------------------------------------------------------------------------
# Caveat derivation
# ---------------------------------------------------------------------------


def derive_caveats(
    section_evidence: List[Dict[str, Any]],
    be_payloads: List[Dict[str, Any]],
    bf_payload: Optional[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Derive explicit, reusable caveats from evidence and source artifacts."""
    caveats: List[Dict[str, Any]] = []
    idx = 0

    # Collect all evidence items
    all_items: Dict[str, Dict[str, Any]] = {}
    for sec in section_evidence:
        for evi in sec.get("evidence_items") or []:
            all_items[evi["evidence_id"]] = evi

    # --- Completeness gaps → data_gap caveats ---
    gap_items = [i for i in all_items.values() if i["evidence_type"] == "completeness_gap"]
    if gap_items:
        for g in gap_items:
            cid = _counter("CAV", f"gap:{g['evidence_id']}", idx)
            idx += 1
            caveats.append(
                {
                    "caveat_id": cid,
                    "category": "data_gap",
                    "statement": (
                        f"Incomplete metric coverage: {g['support']['metric_name']!r} is absent. "
                        "Comparison confidence is limited."
                    ),
                    "severity": "warning",
                    "supporting_evidence_ids": [g["evidence_id"]],
                }
            )

    # --- Mixed units → comparability_limit caveats ---
    mixed_unit_items = [
        i for i in all_items.values()
        if i["evidence_type"] == "caveat"
        and "mixed units" in i.get("statement", "").lower()
    ]
    for mu in mixed_unit_items:
        cid = _counter("CAV", f"mixed:{mu['evidence_id']}", idx)
        idx += 1
        caveats.append(
            {
                "caveat_id": cid,
                "category": "comparability_limit",
                "statement": mu["statement"],
                "severity": "warning",
                "supporting_evidence_ids": [mu["evidence_id"]],
            }
        )

    # --- Anomaly evidence → anomaly caveats ---
    anomaly_items = [i for i in all_items.values() if i["evidence_type"] == "anomaly"]
    for ai in anomaly_items:
        sev = "error" if ai.get("confidence") == "high" else "warning"
        cid = _counter("CAV", f"anomaly:{ai['evidence_id']}", idx)
        idx += 1
        caveats.append(
            {
                "caveat_id": cid,
                "category": "anomaly",
                "statement": ai["statement"],
                "severity": sev,
                "supporting_evidence_ids": [ai["evidence_id"]],
            }
        )

    # --- Readiness caveats from BE artifacts ---
    for be in be_payloads:
        artifact_id = str(be.get("artifact_id", "NRR-UNKNOWN"))
        bundle_id = str(be.get("source_bundle_id", "unknown"))
        eval_signals = be.get("evaluation_signals") or {}
        readiness = eval_signals.get("readiness", "not_ready")
        if readiness == "not_ready":
            cid = _counter("CAV", f"not_ready:{artifact_id}", idx)
            idx += 1
            caveats.append(
                {
                    "caveat_id": cid,
                    "category": "provenance_limit",
                    "statement": (
                        f"Bundle {bundle_id!r} is marked not_ready. "
                        "Evidence from this run must be treated as unreliable."
                    ),
                    "severity": "error",
                    "supporting_evidence_ids": [],
                }
            )

    # --- Threshold uncertainty: threshold assessments with unknown/not_applicable ---
    for be in be_payloads:
        artifact_id = str(be.get("artifact_id", "NRR-UNKNOWN"))
        bundle_id = str(be.get("source_bundle_id", "unknown"))
        eval_signals = be.get("evaluation_signals") or {}
        for ta in eval_signals.get("threshold_assessments") or []:
            if ta.get("status") in ("unknown", "not_applicable"):
                cid = _counter("CAV", f"threshold_unk:{artifact_id}:{ta.get('metric_name','')}", idx)
                idx += 1
                caveats.append(
                    {
                        "caveat_id": cid,
                        "category": "threshold_uncertainty",
                        "statement": (
                            f"Threshold {ta.get('threshold_name','')!r} for metric "
                            f"{ta.get('metric_name','')!r} has status={ta.get('status')} in bundle {bundle_id!r}."
                        ),
                        "severity": "info",
                        "supporting_evidence_ids": [],
                    }
                )

    return caveats


# ---------------------------------------------------------------------------
# Follow-up question derivation
# ---------------------------------------------------------------------------


def derive_followup_questions(
    section_evidence: List[Dict[str, Any]],
    caveats: List[Dict[str, Any]],
    study_type: str,
) -> List[Dict[str, Any]]:
    """Derive targeted, evidence-triggered follow-up questions."""
    questions: List[Dict[str, Any]] = []
    idx = 0

    all_items: Dict[str, Dict[str, Any]] = {}
    for sec in section_evidence:
        for evi in sec.get("evidence_items") or []:
            all_items[evi["evidence_id"]] = evi

    gap_items = [i for i in all_items.values() if i["evidence_type"] == "completeness_gap"]
    anomaly_items = [i for i in all_items.values() if i["evidence_type"] == "anomaly"]
    mixed_unit_items = [
        i for i in all_items.values()
        if i["evidence_type"] == "caveat"
        and "mixed units" in i.get("statement", "").lower()
    ]

    # --- Questions from completeness gaps ---
    for g in gap_items:
        metric = g["support"]["metric_name"]
        src_artifact = g["traceability"]["source_artifact_id"]
        src_bundle = g["traceability"]["source_bundle_id"]
        qid = _counter("QST", f"gap:{g['evidence_id']}", idx)
        idx += 1
        questions.append(
            {
                "question_id": qid,
                "target_section": "agency_questions",
                "question": (
                    f"What additional inputs or processing steps are required to compute "
                    f"{metric!r} for bundle {src_bundle!r}?"
                ),
                "reason": (
                    f"Metric {metric!r} is missing from {src_artifact!r}, "
                    "limiting completeness and comparison confidence."
                ),
                "supporting_evidence_ids": [g["evidence_id"]],
            }
        )

    # --- Questions from anomalies ---
    for ai in anomaly_items:
        metric = ai["support"]["metric_name"]
        src_artifact = ai["traceability"]["source_artifact_id"]
        qid = _counter("QST", f"anomaly:{ai['evidence_id']}", idx)
        idx += 1
        questions.append(
            {
                "question_id": qid,
                "target_section": "agency_questions",
                "question": (
                    f"How should the anomaly in {metric!r} detected in {src_artifact!r} "
                    "be evaluated against operationally acceptable bounds?"
                ),
                "reason": ai["statement"],
                "supporting_evidence_ids": [ai["evidence_id"]],
            }
        )

    # --- Questions from mixed units ---
    for mu in mixed_unit_items:
        metric = mu["support"]["metric_name"]
        qid = _counter("QST", f"mixed:{mu['evidence_id']}", idx)
        idx += 1
        questions.append(
            {
                "question_id": qid,
                "target_section": "agency_questions",
                "question": (
                    f"Which unit convention should govern comparisons of {metric!r} "
                    "across these runs, and how should inconsistent values be reconciled?"
                ),
                "reason": mu["statement"],
                "supporting_evidence_ids": [mu["evidence_id"]],
            }
        )

    # --- Questions from provenance_limit or not_ready caveats ---
    not_ready_cavs = [
        c for c in caveats
        if c.get("category") == "provenance_limit" and c.get("severity") == "error"
    ]
    for c in not_ready_cavs:
        qid = _counter("QST", f"notready:{c['caveat_id']}", idx)
        idx += 1
        questions.append(
            {
                "question_id": qid,
                "target_section": "agency_questions",
                "question": (
                    "What conditions would need to be satisfied for this bundle to become "
                    "ready_for_comparison, and should this run be excluded from the study?"
                ),
                "reason": c["statement"],
                "supporting_evidence_ids": c["supporting_evidence_ids"],
            }
        )

    # --- Study-type-specific threshold questions ---
    threshold_unk_cavs = [c for c in caveats if c.get("category") == "threshold_uncertainty"]
    for c in threshold_unk_cavs[:2]:
        qid = _counter("QST", f"threshold:{c['caveat_id']}", idx)
        idx += 1
        questions.append(
            {
                "question_id": qid,
                "target_section": "agency_questions",
                "question": (
                    f"What threshold definition should govern the metric referenced in: "
                    f"{c['statement']}"
                ),
                "reason": "Threshold status is unknown or not applicable; governance threshold is needed.",
                "supporting_evidence_ids": c["supporting_evidence_ids"],
            }
        )

    return questions


# ---------------------------------------------------------------------------
# Full evidence pack construction
# ---------------------------------------------------------------------------


def build_working_paper_evidence_pack(
    be_payloads: List[Dict[str, Any]],
    bf_payload: Optional[Dict[str, Any]] = None,
    input_refs: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Build a complete working_paper_evidence_pack from BE and optional BF payloads.

    Does not load files — callers pass already-parsed payloads.
    """
    generated_at = _now_iso()

    study_type, _ = infer_synthesis_study_type(be_payloads, bf_payload)
    if study_type is None:
        study_type = "generic"

    source_artifacts = collect_source_artifacts(be_payloads, bf_payload, input_refs)

    be_evidence = build_evidence_items_from_be(be_payloads)
    bf_evidence = build_evidence_items_from_bf(bf_payload)
    all_evidence = be_evidence + bf_evidence

    section_evidence = assign_evidence_to_sections(all_evidence, study_type)
    ranked_findings = derive_ranked_findings(section_evidence, study_type)
    caveats = derive_caveats(section_evidence, be_payloads, bf_payload)
    followup_questions = derive_followup_questions(section_evidence, caveats, study_type)

    # --- Populate executive_summary from top ranked_findings ---
    exec_sec = next(
        (s for s in section_evidence if s["section_key"] == "executive_summary"), None
    )
    if exec_sec is not None:
        top_findings = [f for f in ranked_findings if f["priority"] in ("critical", "high")]
        for finding in top_findings[:3]:
            evi_ids = finding.get("supporting_evidence_ids") or []
            evi_id = _counter("EVI", f"exec:{finding['finding_id']}", 0)
            exec_sec["evidence_items"].append(
                {
                    "evidence_id": evi_id,
                    "evidence_type": "ranked_result",
                    "statement": finding["headline"] + ". " + finding["rationale"],
                    "support": {
                        "metric_name": "",
                        "value": finding["priority"],
                        "unit": "",
                        "comparison_context": "",
                    },
                    "confidence": "high" if finding["priority"] == "critical" else "medium",
                    "traceability": {
                        "source_artifact_id": evi_ids[0] if evi_ids else "N/A",
                        "source_bundle_id": "synthesis",
                        "source_path": "ranked_findings",
                    },
                }
            )
        exec_sec["synthesis_status"] = compute_synthesis_status(exec_sec)

    # --- Populate operational_implications from high-priority findings ---
    ops_sec = next(
        (s for s in section_evidence if s["section_key"] == "operational_implications"), None
    )
    if ops_sec is not None:
        op_findings = [f for f in ranked_findings if f["priority"] in ("critical", "high", "medium")]
        for finding in op_findings[:3]:
            evi_ids = finding.get("supporting_evidence_ids") or []
            evi_id = _counter("EVI", f"ops:{finding['finding_id']}", 0)
            ops_sec["evidence_items"].append(
                {
                    "evidence_id": evi_id,
                    "evidence_type": "ranked_result",
                    "statement": f"Operational implication: {finding['headline']}. {finding['rationale']}",
                    "support": {
                        "metric_name": "",
                        "value": finding["priority"],
                        "unit": "",
                        "comparison_context": "",
                    },
                    "confidence": "medium",
                    "traceability": {
                        "source_artifact_id": evi_ids[0] if evi_ids else "N/A",
                        "source_bundle_id": "synthesis",
                        "source_path": "ranked_findings",
                    },
                }
            )
        ops_sec["synthesis_status"] = compute_synthesis_status(ops_sec)

    # --- Populate agency_questions section ---
    aq_sec = next(
        (s for s in section_evidence if s["section_key"] == "agency_questions"), None
    )
    if aq_sec is not None:
        for q in followup_questions:
            evi_ids = q.get("supporting_evidence_ids") or []
            evi_id = _counter("EVI", f"aq:{q['question_id']}", 0)
            aq_sec["evidence_items"].append(
                {
                    "evidence_id": evi_id,
                    "evidence_type": "caveat",
                    "statement": q["question"],
                    "support": {
                        "metric_name": "",
                        "value": "",
                        "unit": "",
                        "comparison_context": q["reason"],
                    },
                    "confidence": "low",
                    "traceability": {
                        "source_artifact_id": evi_ids[0] if evi_ids else "N/A",
                        "source_bundle_id": "synthesis",
                        "source_path": "followup_questions",
                    },
                }
            )
        aq_sec["synthesis_status"] = compute_synthesis_status(aq_sec)

    # --- Populate recommended_next_steps from caveats and gaps ---
    rns_sec = next(
        (s for s in section_evidence if s["section_key"] == "recommended_next_steps"), None
    )
    if rns_sec is not None:
        error_cavs = [c for c in caveats if c.get("severity") == "error"]
        for c in error_cavs[:3]:
            evi_id = _counter("EVI", f"rns:{c['caveat_id']}", 0)
            rns_sec["evidence_items"].append(
                {
                    "evidence_id": evi_id,
                    "evidence_type": "caveat",
                    "statement": (
                        f"Resolve the following before advancing this evidence to drafting: {c['statement']}"
                    ),
                    "support": {
                        "metric_name": "",
                        "value": c["severity"],
                        "unit": "",
                        "comparison_context": "",
                    },
                    "confidence": "low",
                    "traceability": {
                        "source_artifact_id": c["supporting_evidence_ids"][0]
                        if c["supporting_evidence_ids"]
                        else "N/A",
                        "source_bundle_id": "synthesis",
                        "source_path": "caveats",
                    },
                }
            )
        rns_sec["synthesis_status"] = compute_synthesis_status(rns_sec)

    evidence_pack_id = _sha_id("EPK", f"EPK:{generated_at}:{len(be_payloads)}")
    artifact_id = _sha_id("WPE", f"WPE:{evidence_pack_id}:{generated_at}")

    return {
        "artifact_id": artifact_id,
        "artifact_type": "working_paper_evidence_pack",
        "schema_version": _SCHEMA_VERSION,
        "evidence_pack_id": evidence_pack_id,
        "study_type": study_type,
        "source_artifacts": source_artifacts,
        "section_evidence": section_evidence,
        "ranked_findings": ranked_findings,
        "caveats": caveats,
        "followup_questions": followup_questions,
        "generated_at": generated_at,
    }


# ---------------------------------------------------------------------------
# Synthesis decision construction
# ---------------------------------------------------------------------------


def classify_synthesis_failure(
    findings: List[Dict[str, Any]],
) -> Tuple[str, str]:
    """Return ``(overall_status, failure_type)`` from a findings list."""
    if not findings:
        return "pass", "none"

    best_priority = 99
    best_failure = "none"
    has_error = False
    has_warning = False

    for f in findings:
        sev = f.get("severity", "info")
        code = f.get("code", "")
        if sev == "error":
            has_error = True
        elif sev == "warning":
            has_warning = True

        priority = _FAILURE_PRIORITY.get(code, 90)
        if priority < best_priority:
            best_priority = priority
            best_failure = code

    # Map code to governed failure_type enum
    governed = {
        "no_inputs": "no_inputs",
        "malformed_input": "malformed_input",
        "schema_invalid": "schema_invalid",
        "mixed_study_types": "mixed_study_types",
        "insufficient_evidence": "insufficient_evidence",
        "synthesis_error": "synthesis_error",
    }
    failure_type = governed.get(best_failure, "synthesis_error" if has_error else "none")

    if has_error:
        return "fail", failure_type
    if has_warning:
        return "warning", failure_type
    return "pass", "none"


def build_working_paper_synthesis_decision(
    evidence_pack_id: str,
    findings: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Build a working_paper_synthesis_decision artifact."""
    generated_at = _now_iso()
    overall_status, failure_type = classify_synthesis_failure(findings)

    decision_id = _sha_id("WPS", f"WPS:{evidence_pack_id}:{generated_at}")

    return {
        "artifact_type": "working_paper_synthesis_decision",
        "schema_version": _SCHEMA_VERSION,
        "decision_id": decision_id,
        "evidence_pack_id": evidence_pack_id,
        "overall_status": overall_status,
        "failure_type": failure_type,
        "findings": findings,
        "generated_at": generated_at,
    }


# ---------------------------------------------------------------------------
# Output artifact validation
# ---------------------------------------------------------------------------


def validate_working_paper_evidence_pack(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Validate *payload* against the governed WPE schema.

    Returns a list of finding dicts (empty = valid).
    """
    findings: List[Dict[str, Any]] = []
    try:
        schema = _load_schema(_WPE_SCHEMA_PATH)
    except (OSError, json.JSONDecodeError) as exc:
        findings.append(
            _finding(
                code="schema_invalid",
                severity="error",
                message=f"Cannot load WPE schema: {exc}",
                artifact_path=str(_WPE_SCHEMA_PATH),
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
                artifact_path="working_paper_evidence_pack",
            )
        )
    return findings


def validate_working_paper_synthesis_decision(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Validate *payload* against the governed WPS schema.

    Returns a list of finding dicts (empty = valid).
    """
    findings: List[Dict[str, Any]] = []
    try:
        schema = _load_schema(_WPS_SCHEMA_PATH)
    except (OSError, json.JSONDecodeError) as exc:
        findings.append(
            _finding(
                code="schema_invalid",
                severity="error",
                message=f"Cannot load WPS schema: {exc}",
                artifact_path=str(_WPS_SCHEMA_PATH),
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
                artifact_path="working_paper_synthesis_decision",
            )
        )
    return findings


# ---------------------------------------------------------------------------
# Top-level synthesize entry point
# ---------------------------------------------------------------------------


def synthesize_working_paper_evidence(
    be_inputs: Optional[List[str]] = None,
    bf_input: Optional[str] = None,
    be_payloads: Optional[List[Dict[str, Any]]] = None,
    bf_payload: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Load, validate, and synthesize BE+BF inputs into a governed evidence pack.

    Accepts either file paths (*be_inputs*, *bf_input*) or pre-parsed dicts
    (*be_payloads*, *bf_payload*). File paths take precedence when both are provided.

    Returns a dict with keys:
    - ``working_paper_evidence_pack`` — the evidence pack or None on hard failure
    - ``working_paper_synthesis_decision`` — the synthesis decision
    - ``findings`` — all process findings
    """
    findings: List[Dict[str, Any]] = []
    input_refs: List[str] = []

    # --- 1. Load BE inputs from files if provided ---
    resolved_be: List[Dict[str, Any]] = []
    if be_inputs:
        for path_str in be_inputs:
            try:
                payload = load_governed_artifact(path_str)
                resolved_be.append(payload)
                input_refs.append(str(path_str))
            except (OSError, json.JSONDecodeError) as exc:
                findings.append(
                    _finding(
                        code="malformed_input",
                        severity="error",
                        message=f"Cannot load BE input {path_str!r}: {exc}",
                        artifact_path=str(path_str),
                    )
                )
    elif be_payloads:
        resolved_be = list(be_payloads)

    # --- 2. Load BF input from file if provided ---
    resolved_bf: Optional[Dict[str, Any]] = None
    if bf_input is not None:
        try:
            resolved_bf = load_governed_artifact(bf_input)
            input_refs.append(str(bf_input))
        except (OSError, json.JSONDecodeError) as exc:
            findings.append(
                _finding(
                    code="malformed_input",
                    severity="error",
                    message=f"Cannot load BF input {bf_input!r}: {exc}",
                    artifact_path=str(bf_input),
                )
            )
    elif bf_payload is not None:
        resolved_bf = bf_payload

    # --- 3. Guard: no usable inputs ---
    if not resolved_be and resolved_bf is None:
        findings.append(
            _finding(
                code="no_inputs",
                severity="error",
                message="No BE or BF inputs were provided or successfully loaded.",
                artifact_path="",
            )
        )
        decision = build_working_paper_synthesis_decision(
            evidence_pack_id="", findings=findings
        )
        return {
            "working_paper_evidence_pack": None,
            "working_paper_synthesis_decision": decision,
            "findings": findings,
        }

    # --- 4. Validate BE inputs ---
    valid_be: List[Dict[str, Any]] = []
    for i, be in enumerate(resolved_be):
        be_findings = validate_be_input(be)
        if be_findings:
            findings.extend(be_findings)
        else:
            valid_be.append(be)

    # --- 5. Validate BF input ---
    valid_bf: Optional[Dict[str, Any]] = None
    if resolved_bf is not None:
        bf_findings = validate_bf_input(resolved_bf)
        if bf_findings:
            findings.extend(bf_findings)
        else:
            valid_bf = resolved_bf

    # --- 6. Guard: no valid inputs remain ---
    if not valid_be and valid_bf is None:
        decision = build_working_paper_synthesis_decision(
            evidence_pack_id="", findings=findings
        )
        return {
            "working_paper_evidence_pack": None,
            "working_paper_synthesis_decision": decision,
            "findings": findings,
        }

    # --- 7. Infer study type ---
    study_type, type_findings = infer_synthesis_study_type(valid_be, valid_bf)
    findings.extend(type_findings)

    if study_type is None:
        decision = build_working_paper_synthesis_decision(
            evidence_pack_id="", findings=findings
        )
        return {
            "working_paper_evidence_pack": None,
            "working_paper_synthesis_decision": decision,
            "findings": findings,
        }

    # --- 8. Build evidence pack ---
    try:
        pack = build_working_paper_evidence_pack(
            be_payloads=valid_be,
            bf_payload=valid_bf,
            input_refs=input_refs if input_refs else None,
        )
    except Exception as exc:  # noqa: BLE001
        findings.append(
            _finding(
                code="synthesis_error",
                severity="error",
                message=f"Evidence pack synthesis failed unexpectedly: {exc}",
                artifact_path="",
            )
        )
        decision = build_working_paper_synthesis_decision(
            evidence_pack_id="", findings=findings
        )
        return {
            "working_paper_evidence_pack": None,
            "working_paper_synthesis_decision": decision,
            "findings": findings,
        }

    evidence_pack_id = pack["evidence_pack_id"]

    # --- 9. Validate produced pack ---
    pack_findings = validate_working_paper_evidence_pack(pack)
    findings.extend(pack_findings)

    # --- 10. Build synthesis decision ---
    decision = build_working_paper_synthesis_decision(
        evidence_pack_id=evidence_pack_id, findings=findings
    )

    # --- 11. Validate decision ---
    decision_findings = validate_working_paper_synthesis_decision(decision)
    findings.extend(decision_findings)

    return {
        "working_paper_evidence_pack": pack,
        "working_paper_synthesis_decision": decision,
        "findings": findings,
    }
