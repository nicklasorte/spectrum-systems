# Runbook: GATE-C Failures (Context/Eval)

**Gate:** GATE-C  
**Category:** SAFETY  
**Checks:** Context admission policy + stale fixture detection

---

## What GATE-C validates

1. `ContextAdmissionPolicy` is importable and `admit_context_bundle` runs
2. `detect_stale_fixtures` runs and reports stale count without error

---

## Pattern 1: Context admission import error

```
GATE-C failed: cannot import 'ContextAdmissionPolicy'
```

**Fix:**
1. Run: `python -c "from spectrum_systems.modules.ai_workflow.context_admission import ContextAdmissionPolicy"`
2. Fix the import error
3. Re-run gate

---

## Pattern 2: Stale fixture detection fails

```
GATE-C failed: detect_stale_fixtures() raised <error>
```

**Fix:**
1. Check `spectrum_systems/modules/ai_workflow/stale_fixture_detector.py` for errors
2. Stale fixture detection should not raise — it returns a list (possibly empty)
3. If fixtures are stale: update them before proceeding

---

## Pattern 3: High stale fixture count

GATE-C will report `stale_fixtures_detected=N` in evidence. A non-zero count is a warning but
does not block (the gate passes). However, stale fixtures degrade eval quality.

**Fix:**
1. Run the fixture regeneration script for the affected module
2. Update eval cases with fresh fixture data

---

## See Also

- `spectrum_systems/modules/ai_workflow/context_admission.py`
- `spectrum_systems/modules/ai_workflow/stale_fixture_detector.py`
