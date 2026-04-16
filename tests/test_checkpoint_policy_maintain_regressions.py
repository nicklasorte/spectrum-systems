from spectrum_systems.modules.runtime.checkpoint_stage_contracts import evaluate_checkpoint_transition

def test_legal_transition_allows() -> None:
    out=evaluate_checkpoint_transition(trace_id="t", current_state="ACTIVE", action="COMPLETE")
    assert out["stage"]["artifact_type"]=="checkpoint_stage_contract_record"
