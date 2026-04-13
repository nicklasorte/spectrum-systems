from spectrum_systems.modules.runtime.ctx import (
    assemble_context_bundle,
    emit_context_preflight_result,
    enforce_context_admission,
    run_context_preflight,
)
from spectrum_systems.modules.runtime.tlx import (
    apply_tool_output_limits,
    enforce_tool_permission_profile,
    normalize_tool_output,
)


def test_ctx_deterministic_bundle_and_preflight_gate() -> None:
    recipe = {
        "recipe_id": "CTX-RCP-1",
        "artifact_family": "review_projection_bundle_artifact",
        "strict_mode": True,
        "required_sources": ["a", "b"],
    }
    candidates = [
        {"source_id": "b", "trace_ref": "t", "content_hash": "h2", "priority": 2, "fresh": True},
        {"source_id": "a", "trace_ref": "t", "content_hash": "h1", "priority": 1, "fresh": True},
    ]
    admitted, _ = enforce_context_admission(recipe=recipe, candidates=candidates)
    bundle1 = assemble_context_bundle(run_id="run", trace_id="trace", recipe=recipe, candidates=admitted)
    bundle2 = assemble_context_bundle(run_id="run", trace_id="trace", recipe=recipe, candidates=list(reversed(admitted)))
    assert bundle1["manifest_hash"] == bundle2["manifest_hash"]
    passed, reasons = run_context_preflight(recipe=recipe, admitted_candidates=admitted)
    assert passed is True
    result = emit_context_preflight_result(
        run_id="run", trace_id="trace", bundle_ref=f"context_bundle:{bundle1['bundle_id']}", passed=passed, reason_codes=reasons
    )
    assert result["passed"] is True


def test_tlx_output_limits_and_permissions() -> None:
    env = normalize_tool_output(tool_id="search", raw_output=[{"result": "x" * 100}])
    limited = apply_tool_output_limits(envelope=env, max_records=1, max_chars=32)
    assert limited["record_count"] == 1
    allow, reasons = enforce_tool_permission_profile(
        permission_profile={"allowed_permissions": ["read"], "allow_network": False},
        dispatch_request={"permission": "write", "network": True},
    )
    assert allow is False
    assert "permission_not_allowed" in reasons
    assert "network_not_allowed" in reasons
