from scripts.run_rfx_super_check import REQUIRED_STEPS, run_rfx_super_check


def test_rt_h15_integrity_and_steps_present(monkeypatch):
    monkeypatch.setattr(
        "scripts.run_rfx_super_check._authority_shape_check",
        lambda **_: {"status": "pass", "changed_files": [], "violation_count": 0, "details": []},
    )
    result = run_rfx_super_check(base_ref="base", head_ref="head")
    assert result["status"] == "pass"
    assert set(REQUIRED_STEPS) == set(result["checks"])
    assert result["authority_shape_preflight"]["violation_count"] == 0


def test_super_check_fails_when_authority_shape_violation_detected(monkeypatch):
    violation_detail = {
        "file": "docs/reviews/TST-01_ci_test_inventory.md",
        "line": 10,
        "symbol": "enforcement",
        "cluster": "enforcement",
        "suggested_replacements": ["enforcement_signal", "compliance_observation"],
    }
    monkeypatch.setattr(
        "scripts.run_rfx_super_check._authority_shape_check",
        lambda **_: {
            "status": "fail",
            "changed_files": ["docs/reviews/TST-01_ci_test_inventory.md"],
            "violation_count": 1,
            "details": [violation_detail],
        },
    )

    result = run_rfx_super_check(base_ref="base", head_ref="head")

    assert result["status"] == "fail"
    assert result["checks"]["authority_shape_preflight"] == "fail"
    assert "rfx_super_check_step_failed" in result["reason_codes_emitted"]
    assert result["authority_shape_preflight"]["details"][0] == violation_detail


def test_super_check_records_safe_replacement_terms(monkeypatch):
    monkeypatch.setattr(
        "scripts.run_rfx_super_check._authority_shape_check",
        lambda **_: {
            "status": "fail",
            "changed_files": ["docs/reviews/TST-01_ci_test_inventory.md"],
            "violation_count": 1,
            "details": [
                {
                    "file": "docs/reviews/TST-01_ci_test_inventory.md",
                    "line": 20,
                    "symbol": "enforce",
                    "cluster": "enforcement",
                    "suggested_replacements": [
                        "enforcement_signal",
                        "compliance_observation",
                        "enforcement_input",
                        "policy_observation",
                    ],
                }
            ],
        },
    )

    result = run_rfx_super_check(base_ref="base", head_ref="head")

    suggested = result["authority_shape_preflight"]["details"][0]["suggested_replacements"]
    assert "enforcement_signal" in suggested
    assert "compliance_observation" in suggested
    assert "enforcement_input" in suggested
    assert "policy_observation" in suggested
