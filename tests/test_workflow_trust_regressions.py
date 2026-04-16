from spectrum_systems.modules.runtime.workflow_semantic_audit import audit_workflow_semantics

def test_semantics_allow_clean() -> None:
    out=audit_workflow_semantics(trace_id="t", has_reachable_refs=True, check_names_align=True, false_authority=False)
    assert out["outputs"]["decision"]=="ALLOW"
