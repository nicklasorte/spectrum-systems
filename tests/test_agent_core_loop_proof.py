import json
from pathlib import Path
import pytest
from spectrum_systems.contracts import validate_artifact
from spectrum_systems.modules.runtime.agent_core_loop_proof import build_agent_core_loop_record

ROOT=Path(__file__).resolve().parents[1]


def load_example(name:str):
    return json.loads((ROOT/'contracts'/'examples'/name).read_text())


def test_schema_examples_validate():
    for n in [
        'agent_core_loop_run_record.codex.example.json',
        'agent_core_loop_run_record.claude.example.json',
        'agent_core_loop_run_record.blocked.example.json',
    ]:
        validate_artifact(load_example(n),'agent_core_loop_run_record')


def test_present_leg_without_artifact_refs_fails():
    x=load_example('agent_core_loop_run_record.codex.example.json')
    x['loop_legs']['AEX']['artifact_refs']=[]
    with pytest.raises(Exception):
        validate_artifact(x,'agent_core_loop_run_record')


def test_builder_blocks_missing_aex_pqx():
    rec=build_agent_core_loop_record('X','codex',None)
    assert rec['compliance_status']=='BLOCK'
    assert rec['loop_legs']['AEX']['status'] in {'unknown','missing'}


def test_safe_reason_codes_present_in_examples():
    blocked=load_example('agent_core_loop_run_record.blocked.example.json')
    assert 'cde_signal_missing' in blocked['loop_legs']['CDE']['reason_codes']
    assert 'sel_signal_missing' in blocked['loop_legs']['SEL']['reason_codes']


def test_missing_leg_without_reason_codes_fails():
    x=load_example('agent_core_loop_run_record.claude.example.json')
    x['loop_legs']['EVL']['reason_codes']=[]
    with pytest.raises(Exception):
        validate_artifact(x,'agent_core_loop_run_record')


def test_core_loop_complete_true_with_missing_leg_fails():
    x=load_example('agent_core_loop_run_record.claude.example.json')
    x['core_loop_complete']=True
    with pytest.raises(Exception):
        validate_artifact(x,'agent_core_loop_run_record')


def test_builder_output_validates_schema():
    rec=build_agent_core_loop_record('T-1','codex',None)
    validate_artifact(rec,'agent_core_loop_run_record')


def test_repo_mutating_example_keeps_aex_pqx_present_when_true():
    claude=load_example('agent_core_loop_run_record.claude.example.json')
    assert claude['repo_mutating'] is True
    assert claude['loop_legs']['AEX']['status']=='present'
    assert claude['loop_legs']['PQX']['status']=='present'


def test_invalid_leg_status_enum_fails():
    x=load_example('agent_core_loop_run_record.codex.example.json')
    x['loop_legs']['AEX']['status']='bad_status'
    with pytest.raises(Exception):
        validate_artifact(x,'agent_core_loop_run_record')


def test_builder_handles_unsupported_source_artifact_shape(tmp_path):
    src=tmp_path/'bad.json'
    src.write_text('"not-an-object"',encoding='utf-8')
    rec=build_agent_core_loop_record('T-unsupported','codex',str(src))
    assert rec['loop_legs']['AEX']['status'] in {'unknown','missing'}
    assert rec['loop_legs']['AEX']['reason_codes']
    assert rec['compliance_status']=='BLOCK'
