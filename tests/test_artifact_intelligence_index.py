from spectrum_systems.modules.runtime.artifact_intelligence_index import build_artifact_intelligence_index

def test_index_rows() -> None:
    out=build_artifact_intelligence_index(trace_id="t", artifacts=[{"artifact_type":"a","outputs":{}}])
    assert out["outputs"]["rows"]
