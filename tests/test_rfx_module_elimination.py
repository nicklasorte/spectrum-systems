from spectrum_systems.modules.runtime.rfx_module_elimination import evaluate_rfx_module_elimination


def test_rt_n08_unjustified_module_recommended_then_revalidate():
    bad = evaluate_rfx_module_elimination(modules=[{"module": "m"}])
    assert "rfx_module_unjustified" in bad["reason_codes_emitted"]

    good = evaluate_rfx_module_elimination(modules=[{"module": "m", "impacts": ["signal_loss"]}])
    assert any(item["recommendation"] == "keep" for item in good["recommendations"])


def test_rt_n08_duplicate_responsibility_fails_then_revalidate():
    bad = evaluate_rfx_module_elimination(
        modules=[
            {"module": "m1", "impacts": ["signal_loss"], "responsibility": "loop-proof-render"},
            {"module": "m2", "impacts": ["signal_loss"], "responsibility": "loop-proof-render"},
        ]
    )
    assert "rfx_module_responsibility_duplicate" in bad["reason_codes_emitted"]

    good = evaluate_rfx_module_elimination(
        modules=[
            {"module": "m1", "impacts": ["signal_loss"], "responsibility": "loop-proof-render"},
            {"module": "m2", "impacts": ["signal_loss"], "responsibility": "super-check"},
        ]
    )
    assert "rfx_module_responsibility_duplicate" not in good["reason_codes_emitted"]
