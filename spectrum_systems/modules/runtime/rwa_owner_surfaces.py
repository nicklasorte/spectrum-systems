"""Owner-native runtime surfaces for long-horizon trustworthy execution.

This module intentionally keeps responsibilities partitioned by canonical owners.
TLC composes these surfaces; it does not recompute owner-native decisions.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any


LONG_HORIZON_STATES = ["PLAN", "EXECUTE", "REVIEW", "FIX", "VALIDATE", "DECIDE", "MAINTAIN"]
VALIDATION_LADDER_ORDER = [
    "registry_guard",
    "contracts",
    "owner_boundary_tests",
    "integration_tests",
    "red_team_reruns",
    "final_rerun",
]


class RuntimeWiringFailure(RuntimeError):
    """Fail-closed runtime wiring error."""


@dataclass(frozen=True)
class ThinPromptRequest:
    prompt_id: str
    objective: str
    requested_change_refs: list[str]


@dataclass(frozen=True)
class TLCRuntimeSurface:
    run_id: str

    def compile_execution_ready_plan(self, request: ThinPromptRequest) -> dict[str, Any]:
        return {
            "artifact_type": "rdx_tlc_execution_bridge_record",
            "owner": "RDX",
            "run_id": self.run_id,
            "prompt_id": request.prompt_id,
            "objective": request.objective,
            "steps": ["review_selection", "review_execution", "red_team_execution", "fix_pack_compilation", "pqx_fix_execution", "rerun", "cde_decision"],
            "change_refs": list(request.requested_change_refs),
            "status": "execution_ready",
        }

    def run_validation_ladder(self, *, executed_order: list[str]) -> dict[str, Any]:
        if executed_order != VALIDATION_LADDER_ORDER:
            raise RuntimeWiringFailure("tlc_validation_ladder_order_violation")
        return {
            "artifact_type": "tlc_runtime_validation_ladder_result",
            "owner": "TLC",
            "run_id": self.run_id,
            "status": "pass",
            "executed_order": list(executed_order),
        }

    def execute_state_machine(self, *, step_count: int, transitions: list[dict[str, Any]]) -> dict[str, Any]:
        visited_states = [t["state"] for t in transitions]
        invalid_state = next((state for state in visited_states if state not in LONG_HORIZON_STATES), None)
        invalid_transition = any(t.get("driver") != "artifact" for t in transitions)
        status = "pass"
        reason_codes: list[str] = []
        if invalid_state:
            status = "fail"
            reason_codes.append("unknown_state")
        if invalid_transition:
            status = "fail"
            reason_codes.append("non_artifact_transition")
        return {
            "artifact_type": "tlc_execution_state_machine_record",
            "owner": "TLC",
            "run_id": self.run_id,
            "status": status,
            "step_count": step_count,
            "states": LONG_HORIZON_STATES,
            "visited_states": visited_states,
            "reason_codes": reason_codes,
        }


@dataclass(frozen=True)
class CONRuntimeSurface:
    run_id: str

    def composition_check(self, *, owner_recompute_detected: bool) -> dict[str, Any]:
        return {
            "artifact_type": "con_runtime_composition_only_result",
            "owner": "CON",
            "run_id": self.run_id,
            "status": "fail" if owner_recompute_detected else "pass",
        }

    def lint_runtime_boundary(self, *, module_routes: dict[str, str]) -> dict[str, Any]:
        centralized = [name for name, owner in module_routes.items() if owner == "TLC"]
        concentrated_cross_owner_logic = [name for name in centralized if name != "top_level_composition"]
        return {
            "artifact_type": "con_runtime_boundary_lint_result",
            "owner": "CON",
            "run_id": self.run_id,
            "status": "fail" if concentrated_cross_owner_logic else "pass",
            "centralized_modules": concentrated_cross_owner_logic,
        }


@dataclass(frozen=True)
class CTXRuntimeSurface:
    run_id: str

    def inject_minimal_context(self, *, recipe: dict[str, Any], plan: dict[str, Any]) -> dict[str, Any]:
        required = {"scope", "constraints", "evidence_refs"}
        if not required.issubset(set(recipe)):
            raise RuntimeWiringFailure("ctx_minimal_context_recipe_invalid")
        return {
            "artifact_type": "ctx_runtime_minimal_context_injection_result",
            "owner": "CTX",
            "run_id": self.run_id,
            "status": "pass",
            "recipe": dict(recipe),
            "plan_ref": plan["artifact_type"],
            "bounded": True,
        }

    def enforce_freshness_gate(self, *, context_timestamp: datetime, now: datetime, max_age_minutes: int) -> dict[str, Any]:
        age = now - context_timestamp
        stale = age > timedelta(minutes=max_age_minutes)
        return {
            "artifact_type": "ctx_context_freshness_gate_result",
            "owner": "CTX",
            "run_id": self.run_id,
            "status": "fail" if stale else "pass",
            "age_minutes": int(age.total_seconds() // 60),
            "max_age_minutes": max_age_minutes,
        }

    def detect_delayed_drift(self, *, drift_signals: list[bool], threshold: int = 3) -> dict[str, Any]:
        delayed_drift = sum(1 for signal in drift_signals if signal) >= threshold
        return {
            "artifact_type": "ctx_delayed_drift_detection_record",
            "owner": "CTX",
            "run_id": self.run_id,
            "status": "fail" if delayed_drift else "pass",
            "drift_signal_count": sum(1 for signal in drift_signals if signal),
            "threshold": threshold,
        }


@dataclass(frozen=True)
class RDXRuntimeSurface:
    run_id: str

    def compile_autonomous_windows(self, *, total_steps: int, window_size: int = 10) -> dict[str, Any]:
        windows = []
        start = 1
        while start <= total_steps:
            end = min(start + window_size - 1, total_steps)
            windows.append({"window_id": f"win-{len(windows)+1}", "start": start, "end": end})
            start = end + 1
        return {
            "artifact_type": "rdx_autonomous_window_compilation_record",
            "owner": "RDX",
            "run_id": self.run_id,
            "status": "pass",
            "windows": windows,
        }

    def plan_recertification_boundaries(self, *, windows: list[dict[str, Any]], cadence: int = 2) -> dict[str, Any]:
        checkpoints = [w for idx, w in enumerate(windows, 1) if idx % cadence == 0]
        return {
            "artifact_type": "rdx_recertification_boundary_plan",
            "owner": "RDX",
            "run_id": self.run_id,
            "status": "pass",
            "checkpoints": checkpoints,
        }


@dataclass(frozen=True)
class RILRuntimeSurface:
    run_id: str

    def execute_reviews(self, *, review_types: list[str], red_team_packages: list[str]) -> dict[str, dict[str, Any]]:
        review_record = {
            "artifact_type": "ril_runtime_review_execution_record",
            "owner": "RIL",
            "run_id": self.run_id,
            "status": "pass",
            "review_types": list(review_types),
            "findings": [{"finding_id": f"rvw-{index}", "severity": "medium", "issue": issue} for index, issue in enumerate(review_types, start=1)],
            "non_authoritative": True,
        }
        red_team_record = {
            "artifact_type": "ril_runtime_red_team_execution_record",
            "owner": "RIL",
            "run_id": self.run_id,
            "status": "pass",
            "packages": list(red_team_packages),
            "findings": [
                {
                    "finding_id": f"rt-{index}",
                    "severity": "high" if "bypass" in pkg or "silent" in pkg else "medium",
                    "issue": pkg,
                    "serious_exploit": "bypass" in pkg or "silent" in pkg,
                }
                for index, pkg in enumerate(red_team_packages, start=1)
            ],
            "non_authoritative": True,
        }
        return {"review": review_record, "red_team": red_team_record}

    def detect_late_failure(self, *, step_outcomes: list[bool]) -> dict[str, Any]:
        prefix_success = any(step_outcomes[: max(1, len(step_outcomes) // 2)]) and all(step_outcomes[: max(1, len(step_outcomes) // 2)])
        late_failure = prefix_success and (False in step_outcomes[max(1, len(step_outcomes) // 2) :])
        return {
            "artifact_type": "ril_late_failure_review_record",
            "owner": "RIL",
            "run_id": self.run_id,
            "status": "fail" if late_failure else "pass",
            "late_failure_detected": late_failure,
            "non_authoritative": True,
        }


@dataclass(frozen=True)
class FRERuntimeSurface:
    run_id: str

    def compile_fix_pack(self, *, findings: list[dict[str, Any]]) -> dict[str, Any]:
        fixes = []
        for finding in findings:
            severity = str(finding.get("severity", "medium"))
            fixes.append({"finding_id": finding["finding_id"], "fix_id": f"fix-{finding['finding_id']}", "mandatory": severity in {"high", "critical"}, "status": "pending"})
        return {
            "artifact_type": "fre_runtime_fix_pack_compilation_record",
            "owner": "FRE",
            "run_id": self.run_id,
            "status": "pass",
            "fixes": fixes,
            "non_authoritative": True,
        }

    def classify_fix_severity(self, *, fix_pack: dict[str, Any]) -> dict[str, Any]:
        mandatory = [fix["fix_id"] for fix in fix_pack["fixes"] if fix["mandatory"]]
        return {
            "artifact_type": "fre_runtime_fix_severity_enforcement_record",
            "owner": "FRE",
            "run_id": self.run_id,
            "mandatory_fix_ids": mandatory,
            "advisory_fix_ids": [fix["fix_id"] for fix in fix_pack["fixes"] if not fix["mandatory"]],
            "status": "pass",
            "non_authoritative": True,
        }

    def anti_oscillation_plan(self, *, prior_fix_fail_loops: int) -> dict[str, Any]:
        constrained = prior_fix_fail_loops >= 2
        return {
            "artifact_type": "fre_anti_oscillation_plan_record",
            "owner": "FRE",
            "run_id": self.run_id,
            "status": "pass",
            "loop_stabilization_required": constrained,
            "non_authoritative": True,
        }


@dataclass(frozen=True)
class CDERuntimeSurface:
    run_id: str

    def bounded_autonomy_decision(self, *, requested_steps: int, max_allowed_steps: int) -> dict[str, Any]:
        return {
            "artifact_type": "cde_bounded_autonomy_decision",
            "owner": "CDE",
            "run_id": self.run_id,
            "status": "pass" if requested_steps <= max_allowed_steps else "fail",
            "requested_steps": requested_steps,
            "max_allowed_steps": max_allowed_steps,
            "decision": "continue" if requested_steps <= max_allowed_steps else "halt",
        }

    def recertification_gate(self, *, checkpoint_due: bool, recertified: bool) -> dict[str, Any]:
        blocked = checkpoint_due and not recertified
        return {
            "artifact_type": "cde_recertification_gate_result",
            "owner": "CDE",
            "run_id": self.run_id,
            "status": "fail" if blocked else "pass",
            "decision": "halt" if blocked else "continue",
        }

    def false_green_stop(self, *, local_pass_rate: float, global_failure_detected: bool) -> dict[str, Any]:
        stop = local_pass_rate >= 0.9 and global_failure_detected
        return {
            "artifact_type": "cde_false_green_stop_result",
            "owner": "CDE",
            "run_id": self.run_id,
            "status": "fail" if stop else "pass",
            "decision": "halt" if stop else "continue",
        }

    def final_continuation_decision(self, *, gate_records: list[dict[str, Any]]) -> dict[str, Any]:
        failing = [record["artifact_type"] for record in gate_records if record.get("status") != "pass"]
        return {
            "artifact_type": "cde_runtime_post_loop_continuation_decision",
            "owner": "CDE",
            "run_id": self.run_id,
            "status": "pass" if not failing else "fail",
            "decision": "continue" if not failing else "halt",
            "reason_codes": ["all_gates_passed"] if not failing else failing,
        }


@dataclass(frozen=True)
class EVLRuntimeSurface:
    run_id: str

    def convert_exploit_to_eval(self, *, red_team_findings: list[dict[str, Any]]) -> dict[str, Any]:
        obligations = [{"eval_id": f"eval-{finding['finding_id']}", "finding_id": finding["finding_id"]} for finding in red_team_findings if finding.get("serious_exploit")]
        return {
            "artifact_type": "evl_runtime_exploit_to_eval_conversion_record",
            "owner": "EVL",
            "run_id": self.run_id,
            "status": "pass" if obligations else "fail",
            "eval_obligations": obligations,
        }

    def enforce_eval_gate(self, *, obligations: list[dict[str, Any]], completed_eval_ids: set[str]) -> dict[str, Any]:
        missing = [ob["eval_id"] for ob in obligations if ob["eval_id"] not in completed_eval_ids]
        return {
            "artifact_type": "evl_runtime_eval_gating_result",
            "owner": "EVL",
            "run_id": self.run_id,
            "status": "fail" if missing else "pass",
            "missing_eval_ids": missing,
        }

    def eval_debt_gate(self, *, debt_count: int, debt_limit: int) -> dict[str, Any]:
        return {
            "artifact_type": "evl_eval_debt_gate_result",
            "owner": "EVL",
            "run_id": self.run_id,
            "status": "fail" if debt_count > debt_limit else "pass",
            "debt_count": debt_count,
            "debt_limit": debt_limit,
        }


@dataclass(frozen=True)
class OBSRuntimeSurface:
    run_id: str

    def long_run_trace_report(self, *, expected_steps: int, traced_steps: int) -> dict[str, Any]:
        gaps = max(0, expected_steps - traced_steps)
        return {
            "artifact_type": "obs_long_run_trace_completeness_report",
            "owner": "OBS",
            "run_id": self.run_id,
            "status": "fail" if gaps else "pass",
            "trace_gaps": gaps,
        }


@dataclass(frozen=True)
class LINRuntimeSurface:
    run_id: str

    def lineage_survivability(self, *, expected_links: int, actual_links: int) -> dict[str, Any]:
        missing = max(0, expected_links - actual_links)
        return {
            "artifact_type": "lin_lineage_survivability_report",
            "owner": "LIN",
            "run_id": self.run_id,
            "status": "fail" if missing else "pass",
            "missing_links": missing,
        }


@dataclass(frozen=True)
class REPRuntimeSurface:
    run_id: str

    def replay_sufficiency(self, *, expected_steps: int, replayed_steps: int) -> dict[str, Any]:
        return {
            "artifact_type": "rep_replay_sufficiency_result",
            "owner": "REP",
            "run_id": self.run_id,
            "status": "pass" if replayed_steps >= expected_steps else "fail",
            "expected_steps": expected_steps,
            "replayed_steps": replayed_steps,
        }


@dataclass(frozen=True)
class MNTRuntimeSurface:
    run_id: str

    def trigger(self, *, drift_count: int, failure_count: int, eval_debt_count: int, prompt_bloat_count: int) -> dict[str, Any]:
        severe = (drift_count + failure_count + eval_debt_count + prompt_bloat_count) >= 3
        return {
            "artifact_type": "mnt_runtime_maintain_trigger_record",
            "owner": "MNT",
            "run_id": self.run_id,
            "status": "triggered" if severe else "idle",
            "triggered": severe,
            "non_authoritative": True,
        }

    def eval_expansion(self, *, eval_obligations: list[dict[str, Any]], recurring_failures: int) -> dict[str, Any]:
        jobs = []
        if recurring_failures >= 2:
            jobs = [{"job_id": f"mnt-eval-expand-{index}", "from_eval": ob["eval_id"]} for index, ob in enumerate(eval_obligations, 1)]
        return {
            "artifact_type": "mnt_runtime_eval_expansion_record",
            "owner": "MNT",
            "run_id": self.run_id,
            "status": "pass",
            "jobs": jobs,
            "non_authoritative": True,
        }

    def learning_feeder(self, *, failures: list[str]) -> dict[str, Any]:
        roadmap_items = [{"roadmap_item": f"mnt-learn-{idx}", "source_failure": failure} for idx, failure in enumerate(failures, 1)]
        return {
            "artifact_type": "mnt_runtime_learning_feeder_record",
            "owner": "MNT",
            "run_id": self.run_id,
            "status": "pass",
            "roadmap_inputs": roadmap_items,
            "non_authoritative": True,
        }


@dataclass(frozen=True)
class AILRuntimeSurface:
    run_id: str

    def recommendation_bundle(self, *, failures: list[str]) -> dict[str, Any]:
        clusters: dict[str, int] = {}
        for failure in failures:
            key = failure.split("_", 1)[0]
            clusters[key] = clusters.get(key, 0) + 1
        return {
            "artifact_type": "ail_runtime_recommendation_bundle",
            "owner": "AIL",
            "run_id": self.run_id,
            "status": "pass",
            "clusters": [{"cluster": key, "count": count} for key, count in sorted(clusters.items())],
            "non_authoritative": True,
        }


def default_now() -> datetime:
    return datetime.now(timezone.utc)
