# 3LS Simplification: Migration Guide

**Phase 8: Backward Compatibility**
**From:** TPA, TLC, PRG, WPG, CHK, GOV (6 systems)
**To:** EXEC, GOVERN, EVAL (3 systems)

---

## Old → New Mapping

| Old Call | New Call | System |
|----------|----------|--------|
| `tpa_check(artifact)` | `EXECSystem.exec_check(artifact)` | EXEC |
| `tpa_lineage(id, refs)` | `EXECSystem.validate_lineage(id, refs)` | EXEC |
| `tpa_scope(artifact)` | `EXECSystem.trust_scope_check(artifact)` | EXEC |
| `prg_roadmap(artifact)` | `EXECSystem.roadmap_alignment_check(artifact)` | EXEC |
| `prg_priority_report(health)` | `EXECSystem.generate_priority_report(health)` | EXEC |
| `tlc_route(artifact)` | `GOVERNSystem.route_artifact(artifact)` | GOVERN |
| `tlc_lifecycle(artifact, state)` | `GOVERNSystem.lifecycle_check(artifact, state)` | GOVERN |
| `gov_policy(artifact)` | `GOVERNSystem.policy_check(artifact)` | GOVERN |
| `gov_drift(declared, observed)` | `GOVERNSystem.detect_policy_drift(declared, observed)` | GOVERN |
| `wpg_gate(artifact, results)` | `EVALSystem.eval_gate(artifact, results)` | EVAL |
| `wkg_provenance(artifact)` | `EVALSystem.validate_provenance(artifact)` | EVAL |
| `chk_batch(artifact)` | `EVALSystem.batch_constraint_check(artifact)` | EVAL |
| `chk_umbrella(artifact)` | `EVALSystem.umbrella_constraint_check(artifact)` | EVAL |

---

## Migration Timeline

| Week | Action |
|------|--------|
| 1-2 | Deprecation warnings — old calls still work |
| 3-4 | Deprecation errors — old calls raise warnings with stacklevel=2 |
| 5+ | Old code removed — migrate before this window |

---

## Using the Deprecation Layer (Week 1-2)

Old code continues to work via `DeprecationLayer`:

```python
from spectrum_systems.compat import DeprecationLayer

compat = DeprecationLayer(event_log=my_event_log)

# These still work (with deprecation warning):
allowed, reason = compat.tpa_check(artifact)
owner, reason = compat.tlc_route(artifact)
passed, reason = compat.chk_batch(batch_artifact)
```

---

## Migrating to New Code

### Before (old):
```python
# TPA
from spectrum_systems.governance import some_tpa_function
allowed, reason = tpa_check(artifact)

# TLC  
owner = tlc_route(artifact)

# WPG + CHK
result = wpg_gate(artifact, eval_results)
ok = chk_batch(batch)
```

### After (new):
```python
from spectrum_systems.exec_system import EXECSystem
from spectrum_systems.govern import GOVERNSystem
from spectrum_systems.eval_system import EVALSystem

exec_sys = EXECSystem(event_log=log)
govern = GOVERNSystem(event_log=log)
eval_sys = EVALSystem(event_log=log)

# EXEC (was TPA + PRG)
allowed, reason = exec_sys.exec_check(artifact)

# GOVERN (was TLC + GOV)
owner, reason = govern.route_artifact(artifact)

# EVAL (was WPG + CHK)
result = eval_sys.eval_gate(artifact, eval_results)
ok, reason = eval_sys.batch_constraint_check(batch)
```

---

## Integration Test Checklist

After migrating each call site, verify:

- [ ] `exec_sys.exec_check()` rejects artifacts with missing fields
- [ ] `exec_sys.validate_lineage()` blocks empty lineage
- [ ] `govern.policy_check()` blocks `authorization_level=unauthorized`
- [ ] `govern.lifecycle_check()` blocks invalid transitions
- [ ] `eval_sys.eval_gate()` blocks on `pass_rate < 0.95`
- [ ] `eval_sys.batch_constraint_check()` blocks `> 10 slices`
- [ ] All events still flow to `ExecutionEventLog`
- [ ] `EventFilter.operator_view()` shows correct subset

---

## System Policy Update

Updated policy references new system names:

```json
{
  "systems": {
    "GOVERN": {
      "owns": ["policy_check", "lifecycle_check", "route_artifact", "detect_policy_drift"],
      "gates": ["policy_check", "lifecycle_check"]
    },
    "EXEC": {
      "owns": ["exec_check", "validate_lineage", "trust_scope_check", "roadmap_alignment_check"],
      "gates": ["exec_check", "roadmap_alignment_check"]
    },
    "EVAL": {
      "owns": ["eval_gate", "validate_provenance", "batch_constraint_check", "umbrella_constraint_check"],
      "gates": ["eval_gate", "batch_constraint_check"]
    }
  }
}
```

See: `config/policy/consolidated_systems_policy.json`
