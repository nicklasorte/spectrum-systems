from __future__ import annotations

MAP = [
    ("owner_ref", "rfx_unknown_owner"),
    ("trace_ref", "rfx_unknown_trace"),
    ("source_artifact", "rfx_unknown_source_artifact"),
    ("policy_posture", "rfx_unknown_policy_posture"),
    ("eval_evidence", "rfx_unknown_eval_evidence"),
    ("replay_evidence", "rfx_unknown_replay_evidence"),
    ("lineage_evidence", "rfx_unknown_lineage_evidence"),
    ("reason_codes", "rfx_unknown_reason_code"),
    ("operator_action", "rfx_unknown_operator_action"),
    ("operator_proof_ref", "rfx_unknown_operator_proof"),
]


def run_rfx_unknown_state_campaign(*, states: list[dict]) -> dict:
    reason = []
    for state in states:
        for key, code in MAP:
            value = state.get(key)
            if value in (None, "", [], {}):
                reason.append(code)
        if state.get("ambiguous_lookup"):
            reason.append("rfx_unknown_source_artifact")

    return {
        "artifact_type": "rfx_unknown_state_campaign_result",
        "schema_version": "1.0.0",
        "status": "blocked" if reason else "clean",
        "reason_codes_emitted": sorted(set(reason)),
        "signals": {
            "unknown_state_block_rate": 1.0 if reason else 0.0,
            "operator_proof_coverage": 0.0 if reason else 1.0,
        },
    }
