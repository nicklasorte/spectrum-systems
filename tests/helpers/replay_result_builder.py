"""Shared canonical replay_result fixture builder for runtime tests."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any, Dict, Optional

from spectrum_systems.contracts import load_example, load_schema


def _current_replay_schema_version() -> str:
    schema = load_schema("replay_result")
    return str(schema["properties"]["schema_version"].get("const") or "")


def _stable_artifact_id(payload: Dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def make_canonical_replay_result(
    *,
    replay_id: str = "RPL-test-001",
    trace_id: str = "trace-eval-001",
    original_run_id: str = "eval-run-001",
    replay_run_id: str = "eval-run-001",
    overrides: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Return a minimal schema-valid replay_result payload for tests."""
    observability = deepcopy(load_example("observability_metrics"))
    observability["trace_refs"]["trace_id"] = trace_id
    observability["metrics"]["drift_exceed_threshold_rate"] = float(
        observability["metrics"].get("drift_exceed_threshold_rate", 0.0)
    )

    error_budget = deepcopy(load_example("error_budget_status"))
    error_budget["trace_refs"]["trace_id"] = trace_id
    error_budget["observability_metrics_id"] = observability["artifact_id"]

    result: Dict[str, Any] = {
        "artifact_id": "",
        "artifact_type": "replay_result",
        "schema_version": _current_replay_schema_version(),
        "replay_id": replay_id,
        "original_run_id": original_run_id,
        "replay_run_id": replay_run_id,
        "timestamp": "2026-03-22T00:00:00Z",
        "trace_id": trace_id,
        "input_artifact_reference": "eval_summary:eval-run-001",
        "original_decision_reference": "ECD-eval-run-001-ALLOW",
        "original_enforcement_reference": "ENF-000000000001",
        "replay_decision_reference": "ECD-eval-run-001-ALLOW",
        "replay_enforcement_reference": "ENF-000000000002",
        "replay_decision": "allow",
        "replay_enforcement_action": "allow_execution",
        "replay_final_status": "allow",
        "original_enforcement_action": "allow_execution",
        "original_final_status": "allow",
        "consistency_status": "match",
        "drift_detected": False,
        "failure_reason": None,
        "replay_path": "bag_replay_engine",
        "provenance": {
            "source_artifact_type": "eval_summary",
            "source_artifact_id": "eval-run-001",
            "trace_id": trace_id,
        },
        "observability_metrics": observability,
        "error_budget_status": error_budget,
    }
    result["artifact_id"] = _stable_artifact_id({k: v for k, v in result.items() if k != "artifact_id"})
    if overrides:
        merged = deepcopy(result)
        merged.update(overrides)
        if "provenance" in overrides and isinstance(overrides["provenance"], dict):
            merged_prov = deepcopy(result["provenance"])
            merged_prov.update(overrides["provenance"])
            merged["provenance"] = merged_prov
        if merged.get("consistency_status") == "mismatch":
            merged["drift_detected"] = True
        if "artifact_id" not in overrides:
            merged["artifact_id"] = _stable_artifact_id({k: v for k, v in merged.items() if k != "artifact_id"})
        return merged
    if result.get("consistency_status") == "mismatch":
        result["drift_detected"] = True
    return result
