from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
from typing import Any


def _stable_id(prefix: str, payload: dict[str, Any]) -> str:
    canonical = repr(sorted(payload.items())).encode("utf-8")
    return f"{prefix}-{hashlib.sha256(canonical).hexdigest()[:16]}"


def _parse_utc(ts: str) -> datetime:
    if ts.endswith("Z"):
        ts = ts[:-1] + "+00:00"
    return datetime.fromisoformat(ts).astimezone(timezone.utc)


@dataclass(frozen=True)
class RSMRuntime:
    """Deterministic non-authoritative reconciliation state manager."""

    cde_owner: str = "CDE"

    def build_desired_state_artifact(
        self,
        trace_id: str,
        desired_module_posture: dict[str, dict[str, Any]],
        desired_operator_posture: dict[str, Any],
        desired_portfolio_posture: dict[str, Any],
        *,
        source_ref: str,
        source_kind: str,
        generated_at: str,
        desired_state_version: str = "1.0.0",
    ) -> dict[str, Any]:
        artifact = {
            "artifact_type": "rsm_desired_state_artifact",
            "schema_version": "1.0.0",
            "trace_id": trace_id,
            "desired_state_version": desired_state_version,
            "source": {"source_ref": source_ref, "source_kind": source_kind},
            "generated_at": generated_at,
            "desired_module_posture": desired_module_posture,
            "desired_operator_posture": desired_operator_posture,
            "desired_portfolio_posture": desired_portfolio_posture,
            "non_authoritative": True,
        }
        artifact["desired_state_id"] = _stable_id("rsm-desired", artifact)
        return artifact

    def build_actual_state_artifact(
        self,
        trace_id: str,
        interpreted_artifacts: list[dict[str, Any]],
    ) -> dict[str, Any]:
        self.enforce_ril_contract(interpreted_artifacts)
        modules: dict[str, dict[str, Any]] = {}
        total_conflicts = 0
        for item in interpreted_artifacts:
            mid = item["module_id"]
            modules[mid] = {
                "status": item.get("status", "unknown"),
                "trust": float(item.get("trust", 0.0)),
                "burden": float(item.get("burden", 0.0)),
                "freeze": bool(item.get("freeze", False)),
                "readiness": float(item.get("readiness", 0.0)),
            }
            total_conflicts += int(item.get("conflict_count", 0))

        artifact = {
            "artifact_type": "rsm_actual_state_artifact",
            "schema_version": "1.0.0",
            "trace_id": trace_id,
            "modules": modules,
            "interpreted_inputs": [i["artifact_ref"] for i in interpreted_artifacts],
            "conflict_count": total_conflicts,
            "non_authoritative": True,
        }
        artifact["actual_state_id"] = _stable_id("rsm-actual", artifact)
        return artifact

    def compute_state_delta_artifact(self, desired: dict[str, Any], actual: dict[str, Any]) -> dict[str, Any]:
        deltas: list[dict[str, Any]] = []
        desired_modules = desired["desired_module_posture"]
        actual_modules = actual["modules"]
        for module_id in sorted(set(desired_modules) | set(actual_modules)):
            d = desired_modules.get(module_id, {})
            a = actual_modules.get(module_id, {})
            for field in ("status", "trust", "burden", "freeze", "readiness"):
                if d.get(field) != a.get(field):
                    magnitude = abs(float(d.get(field, 0)) - float(a.get(field, 0))) if field in {"trust", "burden", "readiness"} else 1.0
                    deltas.append(
                        {
                            "module_id": module_id,
                            "field": field,
                            "desired": d.get(field),
                            "actual": a.get(field),
                            "magnitude": round(magnitude, 4),
                            "domain": "module_posture",
                            "evidence_refs": [f"desired:{desired['desired_state_id']}", f"actual:{actual['actual_state_id']}"],
                        }
                    )

        artifact = {
            "artifact_type": "rsm_state_delta_artifact",
            "schema_version": "1.0.0",
            "trace_id": desired["trace_id"],
            "deltas": deltas,
            "non_authoritative": True,
        }
        artifact["state_delta_id"] = _stable_id("rsm-delta", artifact)
        return artifact

    def classify_divergence(self, delta_artifact: dict[str, Any]) -> dict[str, Any]:
        records = []
        for item in delta_artifact["deltas"]:
            mag = item["magnitude"]
            if item["actual"] is None:
                level = "inconsistent"
            elif mag >= 0.6 or item["field"] == "status":
                level = "critical"
            elif mag >= 0.3:
                level = "degraded"
            else:
                level = "normal"
            records.append({**item, "classification": level})
        return {
            "artifact_type": "rsm_divergence_record",
            "schema_version": "1.0.0",
            "trace_id": delta_artifact["trace_id"],
            "divergences": records,
            "non_authoritative": True,
        }

    def generate_reconciliation_plan(self, divergence_record: dict[str, Any]) -> dict[str, Any]:
        ranked = self.rank_divergences(divergence_record["divergences"], top_k=5)
        moves = []
        for d in ranked:
            moves.append(
                {
                    "module_id": d["module_id"],
                    "bounded_next_moves": ["request_review", "collect_new_evidence", "hold"],
                    "evidence_refs": d["evidence_refs"],
                    "blocked_paths": ["direct_execute", "direct_enforce"],
                }
            )
        return {
            "artifact_type": "rsm_reconciliation_plan_artifact",
            "schema_version": "1.0.0",
            "trace_id": divergence_record["trace_id"],
            "candidate_moves": moves,
            "authoritative": False,
            "authority_owner": self.cde_owner,
            "non_authority_assertions": ["CDE decides bounded next step", "SEL enforces", "PQX executes"],
        }

    def build_portfolio_snapshot(self, desired: dict[str, Any], actual: dict[str, Any], divergences: dict[str, Any]) -> dict[str, Any]:
        modules = actual["modules"]
        count = max(len(modules), 1)
        burden = round(sum(m["burden"] for m in modules.values()) / count, 4)
        trust = round(sum(m["trust"] for m in modules.values()) / count, 4)
        freeze_ratio = round(sum(1 for m in modules.values() if m["freeze"]) / count, 4)
        readiness = round(sum(m["readiness"] for m in modules.values()) / count, 4)
        conflict_density = round(actual["conflict_count"] / count, 4)
        return {
            "artifact_type": "rsm_portfolio_state_snapshot",
            "schema_version": "1.0.0",
            "trace_id": desired["trace_id"],
            "metrics": {
                "burden": burden,
                "trust": trust,
                "drift": round(len(divergences["divergences"]) / count, 4),
                "freeze_ratio": freeze_ratio,
                "readiness": readiness,
                "conflict_density": conflict_density,
            },
            "non_authoritative": True,
        }

    def build_cde_input_bundle(self, reconciliation_plan: dict[str, Any], portfolio_snapshot: dict[str, Any]) -> dict[str, Any]:
        return {
            "artifact_type": "rsm_cde_input_bundle",
            "trace_id": reconciliation_plan["trace_id"],
            "decision_owner": self.cde_owner,
            "inputs": [reconciliation_plan["artifact_type"], portfolio_snapshot["artifact_type"]],
            "authoritative": False,
        }

    def validate_desired_state_freshness(
        self,
        desired_artifact: dict[str, Any],
        *,
        now: str,
        max_age_hours: int,
        allowed_sources: set[str],
    ) -> dict[str, Any]:
        generated = _parse_utc(desired_artifact["generated_at"])
        current = _parse_utc(now)
        age_h = (current - generated).total_seconds() / 3600
        source_valid = desired_artifact["source"]["source_kind"] in allowed_sources
        stale = age_h > max_age_hours
        return {
            "artifact_type": "rsm_desired_state_freshness_result",
            "trace_id": desired_artifact["trace_id"],
            "age_hours": round(age_h, 4),
            "source_valid": source_valid,
            "stale": stale,
            "trust_degraded": stale or not source_valid,
        }

    def enforce_output_guardrails(self, artifact: dict[str, Any]) -> None:
        forbidden_keys = {"decision", "enforcement_action", "execution_command"}
        if any(k in artifact for k in forbidden_keys):
            raise PermissionError("rsm_authority_leakage_blocked")
        text = repr(artifact)
        if "SEL" in text and "authority_owner" not in artifact:
            raise PermissionError("rsm_direct_sel_path_blocked")
        if "PQX" in text and "authority_owner" not in artifact:
            raise PermissionError("rsm_direct_pqx_path_blocked")

    def enforce_ril_contract(self, interpreted_artifacts: list[dict[str, Any]]) -> None:
        for item in interpreted_artifacts:
            kind = item.get("artifact_kind", "")
            if not kind.startswith("ril_"):
                raise ValueError("rsm_requires_ril_interpreted_inputs")
            if item.get("raw_evidence") is True:
                raise ValueError("rsm_raw_evidence_path_blocked")

    def apply_stability_control(self, ranked_divergences: list[dict[str, Any]], history: list[str], *, cooldown_cycles: int = 2) -> list[dict[str, Any]]:
        stabilized = []
        for item in ranked_divergences:
            key = f"{item['module_id']}::{item['field']}"
            recent = history[-cooldown_cycles:]
            item = dict(item)
            item["cooldown_blocked"] = key in recent
            if not item["cooldown_blocked"]:
                stabilized.append(item)
        return stabilized

    def rank_divergences(self, divergences: list[dict[str, Any]], top_k: int) -> list[dict[str, Any]]:
        severity_score = {"critical": 4, "inconsistent": 3, "degraded": 2, "normal": 1}
        scored = []
        for d in divergences:
            score = (
                severity_score.get(d.get("classification", "normal"), 1) * 100
                + d.get("magnitude", 0) * 10
                + (5 if d.get("field") == "status" else 0)
            )
            scored.append({**d, "priority_score": round(score, 4)})
        return sorted(scored, key=lambda x: (-x["priority_score"], x["module_id"], x["field"]))[:top_k]

    def compute_conflict_density(self, actual_state: dict[str, Any], module_count: int) -> dict[str, Any]:
        count = max(module_count, 1)
        density = round(actual_state["conflict_count"] / count, 4)
        return {"artifact_type": "rsm_conflict_density_artifact", "density": density, "module_count": module_count}

    def protect_operator_overload(self, ranked_divergences: list[dict[str, Any]], *, top_k: int, collapse_threshold: float = 0.2) -> dict[str, Any]:
        actionable = [d for d in ranked_divergences if d.get("magnitude", 0) >= collapse_threshold]
        collapsed = [d for d in ranked_divergences if d.get("magnitude", 0) < collapse_threshold]
        return {
            "artifact_type": "rsm_operator_overload_artifact",
            "top_k": actionable[:top_k],
            "collapsed_low_impact_count": len(collapsed),
            "non_authoritative": True,
        }
