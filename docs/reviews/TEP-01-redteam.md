# TEP-01 Red-Team Review

## Questions and findings

### Did we create another layer of complexity?
- **Finding:** Added artifacts are bounded to five concrete contract records plus two scripts; complexity is constrained by executable checks.
- **Must-fix:** Ensure checker and audit scripts fail closed and remain deterministic.
- **Fix applied:** `scripts/check_top_engineer_practices.py` exits non-zero on any violation; `scripts/audit_removable_systems.py` emits deterministic markdown from current mapping.

### Did every new artifact prevent a real failure?
- **Finding:** Yes; each artifact maps to a concrete failure class (promotion gaps, unknown-state leaks, stale signals, missing rollback, uncaptured human intervention).

### Did we strengthen the core loop?
- **Finding:** Yes; system mapping requires per-system loop strengthening declaration or bounded justification.

### Are unknown states blocked or escalated?
- **Finding:** Yes; policy requires `silent_allowed=false` and mode `block`/`escalate`; checker hard-fails otherwise.

### Is promotion discipline stronger?
- **Finding:** Yes; promotion requirements must include eval + policy + replay booleans.

### Can a new engineer debug failures faster?
- **Finding:** Yes; debugability surfaces, near misses, and dashboard detection/control fields are now required.

### What should be removed or simplified?
- **Recommendation:** Continue remove-one-system audits and fold systems with duplicate responsibilities after evidence review.
