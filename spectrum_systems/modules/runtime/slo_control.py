"""SLO Control Layer (Prompt BR).

Evaluates artifact quality, timeliness, and traceability across BE, BF, and
BG outputs and determines whether the system is allowed to proceed.

This is a control system, not a reporting feature.  When SLOs are violated or
the error budget is exhausted the layer returns ``allowed_to_proceed=False``
and downstream execution must stop.

Failure-safe by design:
- Returns deterministic outputs on any input combination.
- Never crashes on missing optional data.
- Works with BE-only inputs (no BF or BG required).

SLI thresholds
--------------
>=0.95  healthy
0.85–0.95  degraded
<0.85  violated

Error budget
------------
remaining = mean(sli values)
burn_rate  = 1 - remaining
allowed_to_proceed = False  when status=="violated" OR burn_rate > 0.2
"""

from __future__ import annotations

import hashlib
import json
import statistics
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from jsonschema import Draft202012Validator

_SCHEMA_DIR = Path(__file__).resolve().parents[3] / "contracts" / "schemas"
_SLO_SCHEMA_PATH = _SCHEMA_DIR / "slo_evaluation.schema.json"

# Required top-level sections in a BG working_paper_evidence_pack artifact
_REQUIRED_BG_SECTIONS = [
    "executive_summary",
    "study_objective",
    "technical_findings",
    "comparative_results",
    "operational_implications",
    "limitations_and_caveats",
    "agency_questions",
    "recommended_next_steps",
]

# Expected range for number of ranked findings in a healthy BG artifact
_FINDINGS_MIN = 3
_FINDINGS_MAX = 7

_SCHEMA_VERSION = "1.0.0"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _evaluation_id(seed: str) -> str:
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:12].upper()
    return f"SLO-{digest}"


def _artifact_id(seed: str) -> str:
    digest = hashlib.sha256(f"ART:{seed}".encode("utf-8")).hexdigest()[:12].upper()
    return f"SLOE-{digest}"


def _load_schema() -> Dict[str, Any]:
    return json.loads(_SLO_SCHEMA_PATH.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Input loading
# ---------------------------------------------------------------------------


def load_inputs(
    be_paths: List[str],
    bf_path: Optional[str],
    bg_path: Optional[str],
) -> Dict[str, Any]:
    """Load BE, BF, and BG artifacts from the filesystem.

    Parameters
    ----------
    be_paths:
        Paths to BE (normalized_run_result) JSON artifacts.  May be empty.
    bf_path:
        Path to the BF (cross_run_intelligence_decision) JSON artifact, or
        ``None`` / empty string if not provided.
    bg_path:
        Path to the BG (working_paper_evidence_pack) JSON artifact, or
        ``None`` / empty string if not provided.

    Returns
    -------
    dict with keys:
        ``be_artifacts``  – list of parsed BE dicts (may be empty)
        ``bf_artifact``   – parsed BF dict or ``None``
        ``bg_artifact``   – parsed BG dict or ``None``
        ``load_errors``   – list of error strings encountered during loading
        ``be_paths``      – original be_paths list
        ``bf_path``       – original bf_path or ``None``
        ``bg_path``       – original bg_path or ``None``
    """
    errors: List[str] = []
    be_artifacts: List[Dict[str, Any]] = []
    bf_artifact: Optional[Dict[str, Any]] = None
    bg_artifact: Optional[Dict[str, Any]] = None

    for p in be_paths or []:
        try:
            be_artifacts.append(json.loads(Path(p).read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"be_artifact load error [{p}]: {exc}")

    if bf_path:
        try:
            bf_artifact = json.loads(Path(bf_path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"bf_artifact load error [{bf_path}]: {exc}")

    if bg_path:
        try:
            bg_artifact = json.loads(Path(bg_path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"bg_artifact load error [{bg_path}]: {exc}")

    return {
        "be_artifacts": be_artifacts,
        "bf_artifact": bf_artifact,
        "bg_artifact": bg_artifact,
        "load_errors": errors,
        "be_paths": list(be_paths or []),
        "bf_path": bf_path or None,
        "bg_path": bg_path or None,
    }


# ---------------------------------------------------------------------------
# Input schema validation (best-effort; non-fatal)
# ---------------------------------------------------------------------------


def validate_inputs_against_schema(loaded: Dict[str, Any]) -> List[str]:
    """Validate loaded BE/BF/BG artifacts against their governed schemas.

    Returns a list of validation error strings.  An empty list means all
    loaded artifacts are schema-compliant.
    """
    errors: List[str] = []

    # Validate BE artifacts against the normalized_run_result schema
    nrr_schema_path = _SCHEMA_DIR / "normalized_run_result.schema.json"
    if nrr_schema_path.exists():
        try:
            nrr_schema = json.loads(nrr_schema_path.read_text(encoding="utf-8"))
            validator = Draft202012Validator(nrr_schema)
            for idx, be in enumerate(loaded.get("be_artifacts") or []):
                ve = sorted(validator.iter_errors(be), key=lambda e: e.path)
                for err in ve:
                    errors.append(f"be_artifact[{idx}] schema error: {err.message}")
        except Exception as exc:  # noqa: BLE001
            errors.append(f"be_artifact schema load error: {exc}")

    # Validate BF artifact
    bf = loaded.get("bf_artifact")
    if bf is not None:
        cri_schema_path = _SCHEMA_DIR / "cross_run_intelligence_decision.schema.json"
        if cri_schema_path.exists():
            try:
                cri_schema = json.loads(cri_schema_path.read_text(encoding="utf-8"))
                validator = Draft202012Validator(cri_schema)
                ve = sorted(validator.iter_errors(bf), key=lambda e: e.path)
                for err in ve:
                    errors.append(f"bf_artifact schema error: {err.message}")
            except Exception as exc:  # noqa: BLE001
                errors.append(f"bf_artifact schema load error: {exc}")

    # Validate BG artifact
    bg = loaded.get("bg_artifact")
    if bg is not None:
        wpe_schema_path = _SCHEMA_DIR / "working_paper_evidence_pack.schema.json"
        if wpe_schema_path.exists():
            try:
                wpe_schema = json.loads(wpe_schema_path.read_text(encoding="utf-8"))
                validator = Draft202012Validator(wpe_schema)
                ve = sorted(validator.iter_errors(bg), key=lambda e: e.path)
                for err in ve:
                    errors.append(f"bg_artifact schema error: {err.message}")
            except Exception as exc:  # noqa: BLE001
                errors.append(f"bg_artifact schema load error: {exc}")

    return errors


# ---------------------------------------------------------------------------
# SLI computation
# ---------------------------------------------------------------------------


def compute_completeness_sli(loaded: Dict[str, Any]) -> float:
    """Compute the completeness SLI.

    Scoring is based on:
    - Whether required sections are present and populated in the BG evidence pack.
    - Whether the number of ranked_findings falls in the expected range (3–7).
    - Missing sections reduce the score proportionally.

    Returns a float in [0.0, 1.0].
    """
    bg = loaded.get("bg_artifact")
    if bg is None:
        # No BG artifact — completeness is minimal but not zero (BE may be present)
        be_count = len(loaded.get("be_artifacts") or [])
        if be_count == 0:
            return 0.0
        # BE-only path: partial completeness
        return 0.5

    score = 1.0

    # Section completeness: check section_evidence array for populated sections
    section_evidence = bg.get("section_evidence") or []
    populated_sections: set = set()
    for sec in section_evidence:
        if isinstance(sec, dict):
            status = sec.get("synthesis_status", "")
            key = sec.get("section_key", "")
            if status in ("populated", "partial") and key:
                populated_sections.add(key)

    if _REQUIRED_BG_SECTIONS:
        present = sum(1 for s in _REQUIRED_BG_SECTIONS if s in populated_sections)
        section_fraction = present / len(_REQUIRED_BG_SECTIONS)
        score = min(score, section_fraction) if section_fraction < 1.0 else score

    # Findings count: penalise if outside expected range
    ranked_findings = bg.get("ranked_findings") or []
    findings_count = len(ranked_findings)
    if findings_count == 0:
        score = min(score, 0.5)
    elif findings_count < _FINDINGS_MIN:
        # Partial credit
        score = min(score, 0.70 + 0.10 * findings_count)
    elif findings_count > _FINDINGS_MAX:
        # Mild penalty for over-generation (may indicate noise)
        score = min(score, 0.90)
    # else: within expected range — no penalty

    return round(max(0.0, min(1.0, score)), 4)


def compute_timeliness_sli(loaded: Dict[str, Any]) -> float:
    """Compute the timeliness SLI.

    Based on timestamps if present; falls back to 1.0 when not measurable.
    This function MUST NOT crash on missing or malformed timestamp data.

    Returns a float in [0.0, 1.0].
    """
    try:
        bg = loaded.get("bg_artifact")
        if bg is None:
            return 1.0

        generated_at_str = bg.get("generated_at")
        if not generated_at_str:
            return 1.0

        try:
            generated_at = datetime.fromisoformat(generated_at_str.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            return 1.0

        now = datetime.now(timezone.utc)
        age_hours = (now - generated_at).total_seconds() / 3600.0

        if age_hours < 0:
            # Future-dated timestamp — treat as fresh
            return 1.0
        if age_hours <= 24:
            return 1.0
        if age_hours <= 72:
            return 0.95
        if age_hours <= 168:  # 1 week
            return 0.90
        # Older than a week — degraded timeliness
        return 0.80

    except Exception:  # noqa: BLE001
        # Never crash on timeliness computation
        return 1.0


def compute_traceability_sli(loaded: Dict[str, Any]) -> float:
    """Compute the traceability SLI.

    Based on:
    - Presence of evidence references in the BG evidence pack.
    - Linkage of evidence items back to BE/BF source artifacts.
    - Missing linkage reduces the score.

    Returns a float in [0.0, 1.0].
    """
    bg = loaded.get("bg_artifact")
    be_artifacts = loaded.get("be_artifacts") or []

    if bg is None:
        # No BG — traceability cannot be assessed from BE alone
        if not be_artifacts:
            return 0.0
        # BE present but no BG to link back through — partial traceability
        return 0.7

    # Collect all known source artifact IDs from BE and BF
    known_ids: set = set()
    for be in be_artifacts:
        aid = be.get("artifact_id")
        if aid:
            known_ids.add(str(aid))
        bid = be.get("source_bundle_id")
        if bid:
            known_ids.add(str(bid))

    bf = loaded.get("bf_artifact")
    if bf is not None:
        for key in ("decision_id", "comparison_id", "artifact_id"):
            val = bf.get(key)
            if val:
                known_ids.add(str(val))

    # Check source_artifacts list in BG
    source_artifacts = bg.get("source_artifacts") or []
    if not source_artifacts:
        return 0.5

    linked = 0
    for sa in source_artifacts:
        if not isinstance(sa, dict):
            continue
        art_id = sa.get("artifact_id", "")
        bundle_id = sa.get("source_bundle_id", "")
        if known_ids:
            # Full linkage verification: IDs must exist in the known source artifact registry.
            if (art_id and art_id in known_ids) or (bundle_id and bundle_id in known_ids):
                linked += 1
        else:
            # Degraded validation mode: presence check only — no registry to verify
            # correctness against.  This does NOT confirm actual artifact linkage.
            if art_id or bundle_id:
                linked += 1

    if not source_artifacts:
        return 0.5

    base_score = linked / len(source_artifacts)

    # Additional check: do any section evidence items cite sources?
    section_evidence = bg.get("section_evidence") or []
    total_items = 0
    cited_items = 0
    for sec in section_evidence:
        if not isinstance(sec, dict):
            continue
        for item in sec.get("evidence_items") or []:
            if not isinstance(item, dict):
                continue
            total_items += 1
            # Traceability may be a nested object (governed schema) or flat fields
            traceability_obj = item.get("traceability")
            if isinstance(traceability_obj, dict):
                if traceability_obj.get("source_artifact_id") or traceability_obj.get("source_bundle_id"):
                    cited_items += 1
            elif item.get("source_artifact_id") or item.get("source_bundle_id"):
                cited_items += 1

    if total_items > 0:
        citation_rate = cited_items / total_items
        # Blend base score with citation rate
        base_score = 0.6 * base_score + 0.4 * citation_rate

    return round(max(0.0, min(1.0, base_score)), 4)


def compute_traceability_integrity_sli(
    lineage_registry: Optional[Dict[str, Any]] = None,
) -> Tuple[float, bool, List[str]]:
    """Compute the traceability integrity SLI from a lineage registry.

    This SLI measures whether the artifact lineage chain for this SLO
    evaluation is structurally valid.  A value of 1.0 means all lineage
    checks passed; 0.0 means at least one lineage error was detected.

    Parameters
    ----------
    lineage_registry:
        Optional dict mapping artifact_id → artifact metadata.  When
        ``None`` or empty the SLI defaults to 1.0 (lineage not assessed).

    Returns
    -------
    Tuple[float, bool, List[str]]
        (sli_value, lineage_valid, lineage_errors)
    """
    if not lineage_registry:
        return (1.0, True, [])

    try:
        from spectrum_systems.modules.runtime.artifact_lineage import validate_full_registry

        result = validate_full_registry(lineage_registry)
        if result["valid"]:
            return (1.0, True, [])

        # Collect all errors from all artifacts
        all_errors: List[str] = []
        for aid_result in result["artifact_results"].values():
            all_errors.extend(aid_result.get("errors", []))

        return (0.0, False, all_errors)
    except Exception as exc:  # noqa: BLE001
        return (0.0, False, [f"Lineage validation error: {exc}"])


# ---------------------------------------------------------------------------
# Classification and status
# ---------------------------------------------------------------------------


def classify_violation(sli_name: str, value: float) -> Optional[Dict[str, Any]]:
    """Classify an SLI value as a violation or return None if healthy.

    Thresholds:
        >=0.95  → healthy  (no violation)
        0.85–0.95 → degraded
        <0.85   → violated

    Parameters
    ----------
    sli_name:
        One of ``"completeness"``, ``"timeliness"``, ``"traceability"``.
    value:
        The measured SLI value in [0.0, 1.0].

    Returns
    -------
    dict with keys ``sli``, ``severity``, ``description`` or ``None``.
    """
    if value >= 0.95:
        return None

    if value >= 0.85:
        severity = "low"
        status_label = "degraded"
    elif value >= 0.70:
        severity = "medium"
        status_label = "violated"
    elif value >= 0.50:
        severity = "high"
        status_label = "violated"
    else:
        severity = "critical"
        status_label = "violated"

    return {
        "sli": sli_name,
        "severity": severity,
        "description": (
            f"{sli_name} SLI is {status_label} (value={value:.4f}). "
            f"Expected >=0.95 for healthy operation."
        ),
    }


def compute_slo_status(slis: Dict[str, float]) -> str:
    """Compute overall SLO status from individual SLI values.

    Rules:
    - Any critical violation → "violated"
    - Any degraded SLI (0.85–0.95) → "degraded"
    - All SLIs >=0.95 → "healthy"

    Returns one of ``"healthy"``, ``"degraded"``, ``"violated"``.
    """
    worst = "healthy"
    for sli_name, value in slis.items():
        v = classify_violation(sli_name, value)
        if v is None:
            continue
        sev = v["severity"]
        if sev == "critical":
            return "violated"
        if sev in ("high", "medium"):
            worst = "violated"
        elif sev == "low" and worst == "healthy":
            worst = "degraded"
    return worst


def compute_error_budget(slis: Dict[str, float]) -> Dict[str, float]:
    """Compute the error budget from SLI values.

    Model:
        remaining = mean(sli values)
        burn_rate = 1 - remaining

    Returns a dict with ``remaining`` and ``burn_rate``.
    """
    if not slis:
        return {"remaining": 0.0, "burn_rate": 1.0}
    values = list(slis.values())
    remaining = round(statistics.mean(values), 6)
    burn_rate = round(1.0 - remaining, 6)
    return {
        "remaining": max(0.0, min(1.0, remaining)),
        "burn_rate": max(0.0, burn_rate),
    }


def determine_allowed_to_proceed(status: str, error_budget: Dict[str, float]) -> bool:
    """Determine whether downstream execution is allowed to proceed.

    Returns ``False`` when:
    - ``status == "violated"``
    - OR ``burn_rate > 0.2``

    Otherwise returns ``True``.
    """
    if status == "violated":
        return False
    if error_budget.get("burn_rate", 0.0) > 0.2:
        return False
    return True


# ---------------------------------------------------------------------------
# Artifact construction
# ---------------------------------------------------------------------------


def build_slo_evaluation_artifact(
    loaded: Dict[str, Any],
    slis: Dict[str, float],
    violations: List[Dict[str, Any]],
    slo_status: str,
    error_budget: Dict[str, float],
    allowed_to_proceed: bool,
    created_at: Optional[str] = None,
    lineage_valid: Optional[bool] = None,
    parent_artifact_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Assemble the governed SLO evaluation artifact dict.

    Parameters
    ----------
    loaded:
        The dict returned by :func:`load_inputs`.
    slis:
        Dict mapping SLI name → measured value.
    violations:
        List of violation dicts (from :func:`classify_violation`).
    slo_status:
        Overall status string: ``"healthy"``, ``"degraded"``, or ``"violated"``.
    error_budget:
        Dict with ``remaining`` and ``burn_rate``.
    allowed_to_proceed:
        Whether downstream execution is permitted.
    created_at:
        ISO 8601 timestamp string.  Defaults to the current UTC time.
    lineage_valid:
        Optional boolean indicating whether the artifact lineage chain is
        valid.  Included in the artifact when provided.
    parent_artifact_ids:
        Optional list of parent artifact IDs (decision + synthesis) that
        drove this SLO evaluation.  Included in the artifact when provided.

    Returns
    -------
    A dict that is schema-compliant with the slo_evaluation schema.
    """
    ts = created_at or _now_iso()
    eval_id = _evaluation_id(f"{ts}:{slo_status}")
    art_id = _artifact_id(eval_id)

    be_paths = [str(p) for p in (loaded.get("be_paths") or [])]
    bf_path = loaded.get("bf_path")
    bg_path = loaded.get("bg_path")

    slis_out: Dict[str, float] = {
        "completeness": slis.get("completeness", 0.0),
        "timeliness": slis.get("timeliness", 0.0),
        "traceability": slis.get("traceability", 0.0),
        # Default 1.0 is intentional for this assembler function: the caller
        # (run_slo_control) always computes and supplies this value.  When this
        # function is called directly without a precomputed value, 1.0 signals
        # "not assessed by this call path" — not "verified valid".  If you are
        # calling this function directly you are responsible for computing the SLI
        # and including it in the slis dict.
        "traceability_integrity": slis.get("traceability_integrity", 1.0),
    }

    artifact: Dict[str, Any] = {
        "artifact_id": art_id,
        "evaluation_id": eval_id,
        "slo_status": slo_status,
        "allowed_to_proceed": allowed_to_proceed,
        "slis": slis_out,
        "violations": violations,
        "error_budget": error_budget,
        "inputs": {
            "be_artifacts": be_paths,
            "bf_artifact": bf_path if bf_path else None,
            "bg_artifact": bg_path if bg_path else None,
        },
        "created_at": ts,
    }

    if lineage_valid is not None:
        artifact["lineage_valid"] = lineage_valid
    else:
        # Fail-safe default: when lineage has not been assessed, record as unverified.
        artifact["lineage_valid"] = False
    if parent_artifact_ids is not None:
        artifact["parent_artifact_ids"] = list(parent_artifact_ids)

    return artifact


def validate_output_against_schema(artifact: Dict[str, Any]) -> List[str]:
    """Validate *artifact* against the governed SLO evaluation JSON schema.

    Returns a list of validation error strings (empty = valid).
    """
    errors: List[str] = []
    try:
        schema = _load_schema()
        validator = Draft202012Validator(schema)
        ve = sorted(validator.iter_errors(artifact), key=lambda e: e.path)
        for err in ve:
            errors.append(f"slo_evaluation schema error: {err.message}")
    except Exception as exc:  # noqa: BLE001
        errors.append(f"schema load error: {exc}")
    return errors


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def run_slo_control(
    be_inputs: List[str],
    bf_input: Optional[str] = None,
    bg_input: Optional[str] = None,
    created_at: Optional[str] = None,
    lineage_registry: Optional[Dict[str, Any]] = None,
    parent_artifact_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Run the full SLO control evaluation pipeline.

    Parameters
    ----------
    be_inputs:
        List of paths to BE (normalized_run_result) artifacts.
    bf_input:
        Path to the BF (cross_run_intelligence_decision) artifact, or ``None``.
    bg_input:
        Path to the BG (working_paper_evidence_pack) artifact, or ``None``.
    created_at:
        Optional ISO 8601 timestamp override (useful for deterministic tests).
    lineage_registry:
        Optional dict mapping artifact_id → artifact metadata for lineage
        integrity validation.  When provided, a ``traceability_integrity``
        SLI is computed and included in the artifact.
    parent_artifact_ids:
        Optional list of parent artifact IDs (decision + synthesis) that
        drove this SLO evaluation.  Included in the artifact lineage metadata.

    Returns
    -------
    dict with keys:
        ``slo_evaluation``    – the governed SLO evaluation artifact
        ``slo_status``        – overall status string
        ``allowed_to_proceed`` – boolean
        ``load_errors``       – list of load/validation errors
        ``schema_errors``     – list of schema validation errors
        ``lineage_valid``     – boolean lineage validity flag
        ``lineage_errors``    – list of lineage validation errors
    """
    # 1. Load inputs
    loaded = load_inputs(be_inputs, bf_input, bg_input)

    # 2. Validate inputs against schemas (best-effort, non-fatal)
    schema_errors = validate_inputs_against_schema(loaded)

    # 3. Compute SLIs
    completeness = compute_completeness_sli(loaded)
    timeliness = compute_timeliness_sli(loaded)
    traceability = compute_traceability_sli(loaded)
    ti_value, lineage_valid, lineage_errors = compute_traceability_integrity_sli(
        lineage_registry
    )
    slis: Dict[str, float] = {
        "completeness": completeness,
        "timeliness": timeliness,
        "traceability": traceability,
        "traceability_integrity": ti_value,
    }

    # 4. Classify violations
    violations: List[Dict[str, Any]] = []
    for sli_name, value in slis.items():
        v = classify_violation(sli_name, value)
        if v is not None:
            violations.append(v)

    # 5. Compute overall SLO status
    slo_status = compute_slo_status(slis)

    # 6. Compute error budget
    error_budget = compute_error_budget(slis)

    # 7. Determine whether to proceed
    allowed = determine_allowed_to_proceed(slo_status, error_budget)

    # 8. Build governed artifact
    artifact = build_slo_evaluation_artifact(
        loaded=loaded,
        slis=slis,
        violations=violations,
        slo_status=slo_status,
        error_budget=error_budget,
        allowed_to_proceed=allowed,
        created_at=created_at,
        lineage_valid=lineage_valid,
        parent_artifact_ids=parent_artifact_ids,
    )

    # 9. Validate output artifact against schema
    out_errors = validate_output_against_schema(artifact)

    return {
        "slo_evaluation": artifact,
        "slo_status": slo_status,
        "allowed_to_proceed": allowed,
        "load_errors": loaded.get("load_errors", []),
        "schema_errors": schema_errors + out_errors,
        "lineage_valid": lineage_valid,
        "lineage_errors": lineage_errors,
    }
