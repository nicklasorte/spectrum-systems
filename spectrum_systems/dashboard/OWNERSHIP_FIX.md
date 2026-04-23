# Dashboard Ownership Boundary Fix

## Problem
The initial dashboard implementation had a **SHADOW_OWNERSHIP_OVERLAP** violation:
- Dashboard hardcoded system definitions in `health_calculator.py`
- Included definitions for systems not owned by the dashboard module
- Violated module boundary rule: "No module may cross-write another module's artifact types"

Error details:
```
reason_code: SHADOW_OWNERSHIP_OVERLAP
file: spectrum_systems/dashboard/backend/health_calculator.py
symbol: [various 3-letter systems]
canonical_owner: [respective owning modules]
```

## Root Cause
The health_calculator had a hardcoded SYSTEMS dictionary listing system metadata:
```python
SYSTEMS = {
    'SYSTEM_A': {'name': 'Description', 'type': 'type'},
    'SYSTEM_B': {'name': 'Description', 'type': 'type'},
    # ... many more ...
}
```

This attempted to define systems that should only be defined by their owning modules.

## Solution
Refactored to **parameterized registry loading**:

1. **Removed hardcoded SYSTEMS dict** from `health_calculator.py`
   - Made `system_registry` a parameter (defaults to empty dict)
   - Dashboard observes health, doesn't define systems

2. **Created `canonical_registry_loader.py`**
   - Loads system definitions from authoritative source: `docs/architecture/system_registry.md`
   - Parses "System Map" section with regex
   - Returns clean dict of system_id -> {id, description, type}

3. **Updated `data_refresh.py`**
   - Calls `get_canonical_system_registry()` on startup
   - Passes loaded systems to HealthCalculator
   - Loads all system metadata from canonical source

4. **Updated exports** in `__init__.py`
   - Added `CanonicalRegistryLoader`
   - Added `get_canonical_system_registry()`

## Benefits

### Immediate
- ✅ Fixes SHADOW_OWNERSHIP_OVERLAP violation
- ✅ Respects module boundaries per CLAUDE.md
- ✅ All systems loaded from canonical authoritative registry
- ✅ No hardcoded system definitions in dashboard module

### Early Detection
- Parameterization makes ownership violations visible immediately
- If dashboard tried to override system definitions, it would fail at runtime
- Stronger coupling to canonical source prevents drift

### Flexibility
- Dashboard works with any set of systems (empty, subset, full registry)
- New systems added to registry automatically available
- No hardcoding = no maintenance burden

## Verification

The canonical registry loader successfully extracts system metadata from authoritative source:
- Execution systems loaded
- Governance systems loaded
- Orchestration systems loaded
- Data systems loaded
- All specialized systems loaded via canonical registry pattern

## Code Changes

```
spectrum_systems/dashboard/backend/
  ├─ health_calculator.py        # Removed SYSTEMS dict, added system_registry param
  ├─ data_refresh.py             # Added canonical registry loading
  ├─ canonical_registry_loader.py # NEW: Loads from authoritative source
  └─ __init__.py                 # Added new exports
```

## Commit
- **d23f443**: fix(dashboard): respect module boundaries by parameterizing system registry

## Governance Alignment
Per CLAUDE.md module boundaries:
- ❌ Was: Dashboard owns system definitions
- ✅ Now: Dashboard loads from canonical definitions
- ✅ Authority: Distributed among owning modules
- ✅ No cross-module artifact type ownership
