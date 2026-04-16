from spectrum_systems.modules.runtime.eval_slice_summary import build_eval_slice_summary

def test_eval_slice_summary_missing() -> None:
    out=build_eval_slice_summary(trace_id="t", artifact_family="wpg", stage="s", required_eval_ids=["a"], observed_eval_ids=[])
    assert out["status"]=="blocked"
