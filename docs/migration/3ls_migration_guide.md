# 3LS Migration Guide: Old System Names → Consolidated Systems

**Version:** 1.0  
**Phase:** 8 (Backward Compatibility)  
**Date:** 2026-04-23  
**Migration Deadline:** 2026-05-13

---

## Overview

The 3LS simplification consolidates 10 original systems into 6. All old system names (TPA, PRG, GOV, TLC, WPG, CHK) are deprecated with a 3-week migration window.

During the migration window, old code continues to work via `DeprecationLayer` — but emits `DeprecationWarning` on every call. After the deadline, old calls fail.

---

## Migration Timeline

### Week 1-2: Deprecation Warnings (Current)

- Old code works but logs `DeprecationWarning` on every call
- Warning format: `"{old_name}() is deprecated. Use {new_name}() instead."`
- Zero breaking changes
- **Action:** Update your call sites before Week 3

### Week 3: Deprecation Errors (Fail-Closed)

- Old code raises `DeprecationError` and fails
- Any caller still using old names will break
- **Action:** Complete all migrations before this phase begins

### Week 4+: Removal

- `DeprecationLayer` class removed from codebase
- Old module paths removed
- **Action:** All callers must use new system names

---

## System Name Mapping

### TPA → EXEC

TPA (Trust Policy Application) is now `EXECSystem`.

| Old | New |
|-----|-----|
| `DeprecationLayer.tpa_check(artifact)` | `EXECSystem.exec_check(artifact)` |
| `DeprecationLayer.tpa_lineage(id, refs)` | `EXECSystem.validate_lineage(id, refs)` |
| `DeprecationLayer.tpa_scope(artifact)` | `EXECSystem.trust_scope_check(artifact)` |

```python
# Before
from spectrum_systems.compat.deprecation_layer import DeprecationLayer
compat = DeprecationLayer()
allowed, reason = compat.tpa_check(artifact)

# After
from spectrum_systems.exec_system.exec_system import EXECSystem
exec_sys = EXECSystem(event_log=event_log)
allowed, reason = exec_sys.exec_check(artifact)
```

---

### PRG → EXEC

PRG (Program Governance) is now `EXECSystem`.

| Old | New |
|-----|-----|
| `DeprecationLayer.prg_roadmap(artifact, items)` | `EXECSystem.roadmap_alignment_check(artifact, items)` |
| `DeprecationLayer.prg_priority_report(health, metrics)` | `EXECSystem.generate_priority_report(health, metrics)` |

```python
# Before
aligned, reason = compat.prg_roadmap(artifact, active_items)

# After
from spectrum_systems.exec_system.exec_system import EXECSystem
exec_sys = EXECSystem()
aligned, reason = exec_sys.roadmap_alignment_check(artifact, active_items)
```

---

### GOV → GOVERN

GOV (Governance evidence packaging) is now `GOVERNSystem`.

| Old | New |
|-----|-----|
| `DeprecationLayer.gov_policy(artifact, ref)` | `GOVERNSystem.policy_check(artifact, ref)` *(records governance evidence after TPA policy decisions)* |
| `DeprecationLayer.gov_drift(declared, observed)` | `GOVERNSystem.detect_policy_drift(declared, observed)` *(evidence packaging; no policy authority transfer)* |

```python
# Before
passed, reason = compat.gov_policy(artifact, policy_ref)

# After
from spectrum_systems.govern.govern import GOVERNSystem
govern = GOVERNSystem(event_log=event_log)
passed, reason = govern.policy_check(artifact, policy_ref)
```

---

### TLC → GOVERN

TLC (Top Level Conductor) is now `GOVERNSystem`.

| Old | New |
|-----|-----|
| `DeprecationLayer.tlc_route(artifact, registry)` | `GOVERNSystem.route_artifact(artifact, registry)` |
| `DeprecationLayer.tlc_lifecycle(artifact, target)` | `GOVERNSystem.lifecycle_check(artifact, target)` |

```python
# Before
owner, reason = compat.tlc_route(artifact, registry)

# After
from spectrum_systems.govern.govern import GOVERNSystem
govern = GOVERNSystem()
owner, reason = govern.route_artifact(artifact, registry)
```

---

### WPG → EVAL

WPG (Working Paper Generator) is now `EVALSystem`.

| Old | New |
|-----|-----|
| `DeprecationLayer.wpg_gate(artifact, results)` | `EVALSystem.eval_gate(artifact, results)` |
| `DeprecationLayer.wkg_provenance(artifact)` | `EVALSystem.validate_provenance(artifact)` |

```python
# Before
decision = compat.wpg_gate(artifact, eval_results)

# After
from spectrum_systems.eval_system.eval_system import EVALSystem
eval_sys = EVALSystem(event_log=event_log)
decision = eval_sys.eval_gate(artifact, eval_results)
```

---

### CHK → EVAL

CHK (Checkpoint/Resume Governance) is now `EVALSystem`.

| Old | New |
|-----|-----|
| `DeprecationLayer.chk_batch(artifact)` | `EVALSystem.batch_constraint_check(artifact)` |
| `DeprecationLayer.chk_umbrella(artifact)` | `EVALSystem.umbrella_constraint_check(artifact)` |

```python
# Before
ok, reason = compat.chk_batch(batch_artifact)

# After
from spectrum_systems.eval_system.eval_system import EVALSystem
eval_sys = EVALSystem()
ok, reason = eval_sys.batch_constraint_check(batch_artifact)
```

---

## Migration Checklist

Complete each step before the Week 3 deadline (2026-05-13):

- [ ] Search codebase for `DeprecationLayer` usage: `grep -r "DeprecationLayer\|tpa_check\|gov_policy\|tlc_route\|wpg_gate\|chk_batch\|chk_umbrella\|prg_roadmap\|tlc_lifecycle\|prg_priority" --include="*.py"`
- [ ] Update each call site to use the new system class
- [ ] Run tests with new call sites: `pytest -q`
- [ ] Verify no `DeprecationWarning` in test output
- [ ] Verify no `DeprecationWarning` in staging environment logs
- [ ] Remove `DeprecationLayer` imports from updated files

---

## Rollback Plan

If issues are found after moving to Week 3 (error mode):

1. Revert call sites to use `DeprecationLayer` (compatible with Week 1-2 mode)
2. Re-enable Week 1-2 mode (warnings only) in deployment configuration
3. Diagnose the root cause
4. Fix the underlying issue
5. Re-migrate and verify before re-entering Week 3 mode

There is no rollback past the system consolidation itself — GOVERN, EXEC, and EVAL are the canonical systems. The rollback only covers call sites, not the underlying system architecture.

---

## Verification

After migrating a call site, verify with:

```python
import warnings

# Should produce no DeprecationWarning
with warnings.catch_warnings():
    warnings.simplefilter("error", DeprecationWarning)
    result = new_system.new_method(artifact)  # Raises if deprecated path used
```

---

## Getting Help

- Architecture questions: `docs/operations/3ls_simplified_architecture_runbook.md`
- Failure diagnosis: `docs/training/3ls_training_guide.md`
- Migration status: `spectrum_systems/compat/deprecation_layer.MigrationTimeline.migration_status()`
- Full deprecation mapping: `spectrum_systems/compat/deprecation_layer.MigrationTimeline.MIGRATION_STEPS`
