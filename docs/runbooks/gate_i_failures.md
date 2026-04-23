# Runbook: GATE-I Failures (Integration)

**Gate:** GATE-I  
**Category:** OPTIMIZATION  
**Checks:** Cross-system schema consistency (CRS) + merge self-authorization guard (MGV)

---

## What GATE-I validates

1. Schema versions are compatible across systems (CRS check)
2. No system is authorizing its own merge (MGV no-self-auth)

---

## Pattern 1: Schema version incompatible

```
GATE-I failed: crs_compat_ok=False
WHY: schema_version=1.1 not in supported_versions=['1.0']
```

**Cause:** An artifact was produced with a schema version that downstream systems do not support.

**Fix:**
1. Check which systems consume this artifact type
2. Update all consumers to support the new schema version, OR
3. Downgrade the producer to use the supported version
4. Schema changes require CRS review before rolling out

---

## Pattern 2: Self-authorization attempt blocked

```
GATE-I failed: mgv_self_auth_blocked=False
WHY: System attempted to authorize its own merge (feature → main)
```

**Cause:** A system is trying to approve its own promotion — violates the four-eyes principle.

**Fix:**
1. Identify which system set the authorization for its own merge
2. Promotion must be authorized by a different system or a human reviewer
3. Never route self-authorizations through the promotion gate

---

## Note

GATE-I is an `OPTIMIZATION` gate (not SAFETY). A failure here is a warning-level issue
that should be investigated but does not indicate data loss or security risk.

---

## See Also

- `spectrum_systems/modules/governance/cross_system_consistency.py`
- `spectrum_systems/governance/merge_governance_authority.py`
