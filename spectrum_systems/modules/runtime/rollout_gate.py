"""Phase-14 hard rollout and A2A intake gates."""
from __future__ import annotations

def enforce_rollout_gate(*, checks:dict[str,bool])->tuple[bool,list[str]]:
    missing=sorted([k for k,v in checks.items() if not v])
    return (not missing, [f'missing:{k}' for k in missing])

def enforce_a2a_intake(*, lineage:bool, context_preflight:bool, eval_coverage:bool, authority_lineage:bool, policy_permission:bool, budget_compatible:bool, handoff_integrity:bool=True)->tuple[bool,list[str]]:
    checks={'lineage':lineage,'context_preflight':context_preflight,'eval_coverage':eval_coverage,'authority_lineage':authority_lineage,'policy_permission':policy_permission,'budget_compatible':budget_compatible,'handoff_integrity':handoff_integrity}
    return enforce_rollout_gate(checks=checks)
