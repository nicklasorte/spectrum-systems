# Runbook: GATE-O Failures (Observability)

**Gate:** GATE-O  
**Category:** SAFETY  
**Checks:** OBS emitter + lineage verifier + replay determinism gate

---

## What GATE-O validates

1. `OBSEmitter` can emit an observability record
2. `verify_lineage_completeness` runs without error
3. `check_replay_determinism` confirms consistent replay hashes

---

## Pattern 1: OBS emitter fails

```
GATE-O failed: OBSEmitter().emit_obs_record() raised <error>
```

**Cause:** The OBS emitter module has an initialization or emission error.

**Fix:**
1. Run: `python -c "from spectrum_systems.modules.observability.obs_emitter import OBSEmitter; OBSEmitter().emit_obs_record('TRC', [], 0, 0)"`
2. Fix the import or initialization error
3. The OBS emitter must be functional before observability is valid

---

## Pattern 2: Lineage verification fails

```
GATE-O failed: verify_lineage_completeness raised <error>
```

**Fix:**
1. Check `spectrum_systems/modules/lineage/lineage_verifier.py` for import errors
2. The verifier should handle artifacts with `upstream_artifacts=[]` (root artifacts)
3. Ensure the artifact store is accessible

---

## Pattern 3: Replay non-deterministic

```
GATE-O failed: replay_deterministic=False
```

**Cause:** The same artifact produces different outputs on replay — non-determinism detected.

**Fix:**
1. Find the execution path for this artifact
2. Identify the source of non-determinism (random state, timestamp, external call)
3. Fix the non-determinism before this artifact can be promoted
4. Non-deterministic artifacts cannot be safely promoted

---

## See Also

- `spectrum_systems/modules/observability/obs_emitter.py`
- `spectrum_systems/modules/lineage/lineage_verifier.py`
- `spectrum_systems/modules/replay/replay_gate.py`
