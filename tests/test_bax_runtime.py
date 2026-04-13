from spectrum_systems.modules.runtime.bax import (
    compute_cost_budget_status,
    compute_quality_budget_status,
    compute_risk_budget_status,
    merge_budget_states,
)


def _policy() -> dict:
    return {
        "cost_limits": {"usd": 100.0, "tokens": 1000, "retries": 4, "wall_clock_minutes": 60},
        "quality_limits": {
            "eval_failure_rate": 0.1,
            "indeterminate_rate": 0.1,
            "replay_mismatch_rate": 0.1,
            "override_rate": 0.1,
            "policy_alignment_failure_rate": 0.1,
        },
        "risk_limits": {
            "guardrail_violations": 2,
            "trace_incompleteness": 2,
            "missing_material_evidence": 2,
            "unsafe_tool_attempt_rate": 0.2,
            "human_review_backlog": 2,
        },
    }


def test_bax_allow_warn_freeze_block_transitions() -> None:
    base = {
        "cost": {"usd": 60.0, "tokens": 600, "retries": 1, "wall_clock_minutes": 20},
        "quality": {
            "eval_failure_rate": 0.01,
            "indeterminate_rate": 0.01,
            "replay_mismatch_rate": 0.0,
            "override_rate": 0.0,
            "policy_alignment_failure_rate": 0.0,
        },
        "risk": {
            "guardrail_violations": 0,
            "trace_incompleteness": 0,
            "missing_material_evidence": 0,
            "unsafe_tool_attempt_rate": 0.0,
            "human_review_backlog": 0,
        },
    }
    cost_allow, _ = compute_cost_budget_status(consumption=base, policy=_policy())
    assert cost_allow == "allow"

    warn_case = dict(base)
    warn_case["cost"] = dict(base["cost"], usd=80.0)
    cost_warn, _ = compute_cost_budget_status(consumption=warn_case, policy=_policy())
    assert cost_warn == "warn"

    freeze_case = dict(base)
    freeze_case["cost"] = dict(base["cost"], usd=95.0)
    cost_freeze, _ = compute_cost_budget_status(consumption=freeze_case, policy=_policy())
    assert cost_freeze == "freeze"

    block_case = dict(base)
    block_case["cost"] = dict(base["cost"], usd=120.0)
    cost_block, _ = compute_cost_budget_status(consumption=block_case, policy=_policy())
    assert cost_block == "block"


def test_bax_merge_prefers_most_severe() -> None:
    assert merge_budget_states(cost_status="warn", quality_status="freeze", risk_status="allow") == "freeze"
    quality, _ = compute_quality_budget_status(consumption={"quality": _policy()["quality_limits"]}, policy=_policy())
    risk, _ = compute_risk_budget_status(consumption={"risk": _policy()["risk_limits"]}, policy=_policy())
    assert quality == "block"
    assert risk == "block"
