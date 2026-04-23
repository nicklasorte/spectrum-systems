# Runbook: GATE-F Failures (Foundation)

**Gate:** GATE-F  
**Category:** SAFETY  
**Checks:** Registry validator importable + drift check runs

---

## What GATE-F validates

1. `RegistryDriftValidator` is importable and runs without error
2. The drift report returns a valid `systems_checked` count

---

## Pattern 1: Import error

```
GATE-F failed: cannot import 'RegistryDriftValidator'
```

**Cause:** `spectrum_systems.governance.registry_drift_validator` has a syntax or import error.

**Fix:**
1. Run: `python -c "from spectrum_systems.governance.registry_drift_validator import RegistryDriftValidator"`
2. Fix the import error in the module
3. Re-run gate

---

## Pattern 2: Drift report returns zero systems

```
systems_checked=0
```

**Cause:** System registry is empty or unreadable.

**Fix:**
1. Check `docs/architecture/system_registry.md` is present and parseable
2. Check that `RegistryDriftValidator` correctly parses the registry
3. The registry must list at least GOVERN, EXEC, EVAL, PQX, CDE, SEL

---

## See Also

- `spectrum_systems/governance/registry_drift_validator.py`
- `docs/architecture/system_registry.md`
