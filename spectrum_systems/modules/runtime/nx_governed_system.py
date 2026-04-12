"""NX governed system integration surface.

This module wires NX preparatory/runtime intelligence into canonical governed paths:
- canonical schema + manifest resolution
- artifact persistence/retrieve
- TLC routing handoff (route-only)
- CDE/TPA/SEL authority-boundary consumption
- RQX review-loop feed integration
- PRG roadmap recommendation persistence
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from jsonschema import Draft202012Validator, FormatChecker

from spectrum_systems.contracts import load_schema


class NXGovernedSystemError(ValueError):
    """Raised when governed NX system integration fails closed."""


_REPO_ROOT = Path(__file__).resolve().parents[3]
_STANDARDS_MANIFEST_PATH = _REPO_ROOT / "contracts" / "standards-manifest.json"

NX_ARTIFACT_CONTRACTS: dict[str, dict[str, str]] = {
    "artifact_intelligence_index": {"schema_name": "artifact_intelligence_index", "schema_version": "1.0.0"},
    "artifact_intelligence_report": {"schema_name": "artifact_intelligence_report", "schema_version": "1.0.0"},
    "fused_signal_record": {"schema_name": "fused_signal_record", "schema_version": "1.0.0"},
    "multi_run_aggregate": {"schema_name": "multi_run_aggregate", "schema_version": "1.0.0"},
    "pattern_mining_recommendation": {"schema_name": "pattern_mining_recommendation", "schema_version": "1.0.0"},
    "decision_explainability_artifact": {"schema_name": "decision_explainability_artifact", "schema_version": "1.0.0"},
    "system_trust_score_artifact": {"schema_name": "system_trust_score_artifact", "schema_version": "1.0.0"},
    "policy_evolution_candidate_set": {"schema_name": "policy_evolution_candidate_set", "schema_version": "1.0.0"},
    "autonomy_expansion_gate_result": {"schema_name": "autonomy_expansion_gate_result", "schema_version": "1.0.0"},
    "nx_review_intelligence_link_artifact": {"schema_name": "nx_review_intelligence_link_artifact", "schema_version": "1.0.0"},
    "nx_roadmap_candidate_artifact": {"schema_name": "nx_roadmap_candidate_artifact", "schema_version": "1.0.0"},
}


def _load_manifest() -> dict[str, Any]:
    try:
        payload = json.loads(_STANDARDS_MANIFEST_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise NXGovernedSystemError(f"standards manifest not found: {_STANDARDS_MANIFEST_PATH}") from exc
    except json.JSONDecodeError as exc:
        raise NXGovernedSystemError("standards manifest invalid JSON") from exc
    if not isinstance(payload, dict):
        raise NXGovernedSystemError("standards manifest root must be object")
    return payload


def resolve_nx_contract(artifact_type: str) -> dict[str, str]:
    spec = NX_ARTIFACT_CONTRACTS.get(str(artifact_type))
    if spec is None:
        raise NXGovernedSystemError(f"unregistered nx artifact_type: {artifact_type}")

    contracts = _load_manifest().get("contracts", [])
    if not isinstance(contracts, list):
        raise NXGovernedSystemError("standards manifest contracts must be list")

    entry = next((row for row in contracts if isinstance(row, dict) and row.get("artifact_type") == artifact_type), None)
    if entry is None:
        raise NXGovernedSystemError(f"nx artifact not published in standards manifest: {artifact_type}")
    manifest_version = str(entry.get("schema_version") or "")
    if manifest_version != spec["schema_version"]:
        raise NXGovernedSystemError(
            f"nx artifact schema mismatch for {artifact_type}: runtime={spec['schema_version']} manifest={manifest_version}"
        )
    return spec


def validate_nx_artifact(artifact: dict[str, Any]) -> None:
    if not isinstance(artifact, dict):
        raise NXGovernedSystemError("nx artifact must be object")
    artifact_type = str(artifact.get("artifact_type") or "")
    if not artifact_type:
        raise NXGovernedSystemError("nx artifact missing artifact_type")

    spec = resolve_nx_contract(artifact_type)
    schema = load_schema(spec["schema_name"])
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(artifact), key=lambda err: list(err.absolute_path))
    if errors:
        details = "; ".join(error.message for error in errors)
        raise NXGovernedSystemError(f"nx artifact failed schema validation: {artifact_type}: {details}")



def persist_nx_artifact(*, artifact: dict[str, Any], store_root: Path, trace_id: str) -> Path:
    if not isinstance(trace_id, str) or not trace_id.strip():
        raise NXGovernedSystemError("trace_id required")
    validate_nx_artifact(artifact)

    artifact_type = str(artifact["artifact_type"])
    artifact_id = str(artifact.get("artifact_id") or f"{artifact_type}-{trace_id}")
    safe_type = artifact_type.replace("/", "_")
    path = store_root / safe_type / f"{artifact_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)

    payload = dict(artifact)
    validate_nx_artifact(payload)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def load_nx_artifact(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise NXGovernedSystemError(f"nx artifact not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise NXGovernedSystemError(f"nx artifact invalid json: {path}") from exc
    if not isinstance(payload, dict):
        raise NXGovernedSystemError("nx artifact payload must be object")
    validate_nx_artifact(payload)
    return payload


def tlc_route_nx_flow(
    *,
    run_id: str,
    trace_id: str,
    nx_request: dict[str, Any],
    ril_executor: Callable[[dict[str, Any]], list[dict[str, Any]]],
    store_root: Path,
) -> dict[str, Any]:
    if not run_id.strip() or not trace_id.strip():
        raise NXGovernedSystemError("run_id and trace_id required")
    produced = ril_executor(nx_request)
    if not isinstance(produced, list) or not produced:
        raise NXGovernedSystemError("ril executor must return non-empty artifact list")

    refs: list[str] = []
    for artifact in produced:
        path = persist_nx_artifact(artifact=artifact, store_root=store_root, trace_id=trace_id)
        refs.append(str(path))

    return {
        "artifact_type": "tlc_nx_handoff_record",
        "authority_owner": "TLC",
        "run_id": run_id,
        "trace_id": trace_id,
        "handoff_to": "RIL",
        "routed_only": True,
        "nx_artifact_refs": sorted(refs),
    }


def cde_consume_nx_preparatory(*, fused_signal: dict[str, Any], closure_context: dict[str, Any]) -> dict[str, Any]:
    validate_nx_artifact(fused_signal)
    if fused_signal.get("artifact_type") != "fused_signal_record":
        raise NXGovernedSystemError("CDE requires fused_signal_record")
    if str(fused_signal.get("authority_scope")) != "preparatory_non_authoritative":
        raise NXGovernedSystemError("CDE input must remain preparatory_non_authoritative")
    return {
        "artifact_type": "cde_nx_preparatory_input",
        "authority_owner": "CDE",
        "requires_cde_decision": True,
        "closure_context": closure_context,
        "nx_input_ref": fused_signal.get("artifact_type"),
        "readiness_signal": bool(fused_signal.get("signals", {}).get("judgment_eval", {}).get("all_required_passed", False)),
    }


def tpa_consume_nx_candidates(*, policy_candidates: dict[str, Any], policy_context: dict[str, Any]) -> dict[str, Any]:
    validate_nx_artifact(policy_candidates)
    if policy_candidates.get("artifact_type") != "policy_evolution_candidate_set":
        raise NXGovernedSystemError("TPA requires policy_evolution_candidate_set")
    if str(policy_candidates.get("authority_scope")) != "recommendation_only":
        raise NXGovernedSystemError("TPA input must remain recommendation_only")
    return {
        "artifact_type": "tpa_nx_candidate_input",
        "authority_owner": "TPA",
        "requires_tpa_authority": True,
        "candidate_count": len(policy_candidates.get("candidates", [])),
        "policy_context": policy_context,
    }


def sel_enforce_with_authority(*, nx_trust: dict[str, Any], cde_authority: dict[str, Any] | None, tpa_authority: dict[str, Any] | None) -> dict[str, Any]:
    validate_nx_artifact(nx_trust)
    if nx_trust.get("artifact_type") != "system_trust_score_artifact":
        raise NXGovernedSystemError("SEL trust hook requires system_trust_score_artifact")
    if cde_authority is None or tpa_authority is None:
        return {
            "artifact_type": "sel_nx_enforcement_hook",
            "authority_owner": "SEL",
            "enforcement_allowed": False,
            "blocking_reason": "missing_canonical_authority_inputs",
        }
    return {
        "artifact_type": "sel_nx_enforcement_hook",
        "authority_owner": "SEL",
        "enforcement_allowed": True,
        "cde_ref": cde_authority.get("artifact_type"),
        "tpa_ref": tpa_authority.get("artifact_type"),
        "derived_trust_score": nx_trust.get("trust_score"),
    }


def integrate_rqx_review_cycle(*, review_cycle: dict[str, Any], ril_interpreter: Callable[[list[dict[str, Any]]], dict[str, Any]]) -> dict[str, Any]:
    if str(review_cycle.get("authority_owner")) != "RQX":
        raise NXGovernedSystemError("review cycle must be RQX owned")
    completed = review_cycle.get("completed_reviews")
    if not isinstance(completed, list):
        raise NXGovernedSystemError("review cycle completed_reviews must be list")

    interpreted = ril_interpreter(completed)
    return {
        "artifact_type": "nx_review_intelligence_link_artifact",
        "schema_version": "1.0.0",
        "authority_scope": "non_authoritative",
        "trace_id": str(review_cycle.get("trace_id") or ""),
        "review_cycle_ref": str(review_cycle.get("cycle_id") or ""),
        "pattern_support": interpreted.get("pattern_support", []),
        "trust_inputs": interpreted.get("trust_inputs", []),
        "judgment_support": interpreted.get("judgment_support", []),
        "roadmap_candidates": interpreted.get("roadmap_candidates", []),
    }


def persist_prg_roadmap_candidates(*, trace_id: str, run_id: str, candidates: list[dict[str, Any]], output_path: Path) -> Path:
    artifact = {
        "artifact_type": "nx_roadmap_candidate_artifact",
        "schema_version": "1.0.0",
        "authority_scope": "recommendation_only",
        "trace_id": trace_id,
        "run_id": run_id,
        "authority_owner": "PRG",
        "admission_required": True,
        "candidate_items": candidates,
    }
    validate_nx_artifact(artifact)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


__all__ = [
    "NXGovernedSystemError",
    "NX_ARTIFACT_CONTRACTS",
    "resolve_nx_contract",
    "validate_nx_artifact",
    "persist_nx_artifact",
    "load_nx_artifact",
    "tlc_route_nx_flow",
    "cde_consume_nx_preparatory",
    "tpa_consume_nx_candidates",
    "sel_enforce_with_authority",
    "integrate_rqx_review_cycle",
    "persist_prg_roadmap_candidates",
]
