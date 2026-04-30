from pathlib import Path
from spectrum_systems.modules.runtime.pr_repair_loop import observe_failures,normalize_failure,build_candidate,prepare_repair_readiness,execute_repair,summarize
import pytest

def _mk(tmp_path: Path, rel: str, payload: dict):
    p=tmp_path/rel; p.parent.mkdir(parents=True,exist_ok=True); p.write_text(__import__('json').dumps(payload));

def test_attempt_3_fails_validation(tmp_path: Path):
    with pytest.raises(ValueError):
        observe_failures(1,'r','h',3,tmp_path)

def test_unknown_failure_requires_human_review(tmp_path: Path):
    obs=observe_failures(1,'r','h',1,tmp_path)
    norm=normalize_failure(obs)
    assert norm['human_review_required'] is True

def test_no_readiness_blocks_repair(tmp_path: Path):
    obs=observe_failures(1,'r','h',1,tmp_path); norm=normalize_failure(obs); cand=build_candidate(norm)
    auth={'repair_readiness_status':'not_ready_for_control_review'}
    exe=execute_repair(cand,auth,apply_repair=True)
    assert exe['status']=='not_ready_for_control_review'

def test_unready_file_change_blocks(tmp_path: Path):
    obs=observe_failures(1,'r','h',1,tmp_path); norm=normalize_failure(obs); cand=build_candidate(norm)
    auth=prepare_repair_readiness(cand)
    exe=execute_repair(cand,auth,apply_repair=False)
    assert exe['status']=='not_ready_for_control_review'

def test_tests_weakened_false_and_gate_not_skipped(tmp_path: Path):
    obs=observe_failures(1,'r','h',1,tmp_path); norm=normalize_failure(obs); cand=build_candidate(norm); auth=prepare_repair_readiness(cand)
    exe=execute_repair(cand,auth,False)
    assert exe['tests_weakened'] is False and exe['skipped_required_gate'] is False

def test_known_authority_shape_candidate(tmp_path: Path):
    _mk(tmp_path,'authority_shape_preflight/authority_shape_preflight_result.json',{'status':'fail'})
    cand=build_candidate(normalize_failure(observe_failures(1,'r','h',1,tmp_path)))
    assert cand['failure_class']=='authority_shape_violation'

def test_known_authority_leak_candidate(tmp_path: Path):
    _mk(tmp_path,'authority_leak_guard/authority_leak_guard_result.json',{'status':'fail'})
    cand=build_candidate(normalize_failure(observe_failures(1,'r','h',1,tmp_path)))
    assert cand['failure_class']=='authority_leak_observation'

def test_second_failed_attempt_emits_human_review(tmp_path: Path):
    obs=observe_failures(1,'r','h',2,tmp_path); norm=normalize_failure(obs); cand=build_candidate(norm); auth=prepare_repair_readiness(cand); exe=execute_repair(cand,auth,False)
    summ=summarize(obs,norm,cand,auth,exe)
    assert summ['human_review_required'] is True

def test_candidate_forbidden_files_present(tmp_path: Path):
    cand=build_candidate(normalize_failure(observe_failures(1,'r','h',1,tmp_path)))
    assert 'contracts/schemas' in cand['forbidden_files']
