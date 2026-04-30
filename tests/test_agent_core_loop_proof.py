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
