from spectrum_systems.modules.wpg.redteam import run_redteam_eval_blind_spots


def test_redteam_blind_spots_detect_fake_green() -> None:
    findings = run_redteam_eval_blind_spots()
    assert findings["artifact_type"] == "eval_redteam_findings"
    assert findings["summary"]["scenario_count"] == 4
    assert findings["summary"]["status"] in {"PASS", "BLOCK"}
