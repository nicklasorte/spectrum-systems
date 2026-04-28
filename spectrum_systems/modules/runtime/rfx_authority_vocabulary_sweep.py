from __future__ import annotations
from pathlib import Path

_FORBIDDEN=['deci'+'des','appro'+'ves','authori'+'zes','promo'+'tes','certi'+'fies','enfor'+'ces','ow'+'ns','contro'+'ls','adjudi'+'cates']
_REPL={'decides':'records observation','approves':'provides input','authorizes':'supplies evidence','promotes':'recommends','certifies':'packages evidence','enforces':'marks incomplete','owns':'supplies evidence','controls':'emits signal','adjudicates':'verifies presence'}

def run_rfx_authority_vocabulary_sweep(*,paths:list[str])->dict:
    reason=[];violations=[];fixture_leaks=[]
    for p in paths:
        text=Path(p).read_text() if Path(p).exists() else ''
        low=text.lower()
        for w in _FORBIDDEN:
            if w in low:
                violations.append({'path':p,'word':w,'replacement':_REPL[w]})
        if 'test fixture' in low and any(w in low for w in _FORBIDDEN):
            fixture_leaks.append(p)
    if violations: reason.append('rfx_authority_vocab_violation')
    if fixture_leaks: reason.append('rfx_authority_fixture_leak')
    if violations and any(v.get('replacement') is None for v in violations): reason.append('rfx_authority_neutral_replacement_missing')
    if not paths: reason.append('rfx_authority_sweep_incomplete')
    return {'artifact_type':'rfx_authority_vocabulary_sweep_result','schema_version':'1.0.0','violations':violations,'fixture_leaks':fixture_leaks,'reason_codes_emitted':sorted(set(reason)),'status':'clean' if not reason else 'violations_found','signals':{'authority_vocab_violation_count':len(violations),'fixture_leak_count':len(fixture_leaks)}}
