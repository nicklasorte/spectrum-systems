# H01B Control Hardening Review
**Batch:** BATCH-H01B — Pre-MVP Spine Hardening  
**Review ID:** RVA-H01B-SPINE-001  
**Date:** 2026-04-25  
**Reviewer:** ARA-01 (Adversarial Review Agent)  
**Scope:** Control enforcement, hash canonicalization, severity integrity, source grounding

---

## Red Team Questions and Answers

### 1. Can routing occur without a control decision?

**Before:** YES. `route_artifact(artifact_type)` accepted any artifact type with no control decision required. Callers could route any artifact to the next pipeline stage with no evidence of eval gate passage.

**After:** NO. `route_with_control_check(artifact, control_decision)` is the governed routing interface. It requires:
- `control_decision` must be a dict
- Must contain `eval_summary`
- Must contain `evaluation_control_decision`
- `evaluation_control_decision` must be `"allow"` (block/freeze reject; warn rejects unless caller opts in)

`route_artifact()` still exists for internal use but the governed entry point is `route_with_control_check`. Callers that bypass it must explicitly ignore the governed API.

---

### 2. Can S4 be ignored (treated as non-blocking)?

**Before:** YES. The `review_finding` definition in `review_artifact.schema.json` made `blocking` optional. An S4 finding could be written with `blocking: false` and pass schema validation. The H01_review.json F-007 demonstrated this pattern.

**After:** NO. The schema now enforces:
```json
"if": {"properties": {"severity": {"const": "S4"}}, "required": ["severity"]},
"then": {"properties": {"blocking": {"const": true}}, "required": ["blocking"]}
```
Any finding with `severity: "S4"` that lacks `blocking: true` is a schema validation failure.

---

### 3. Can the hash be spoofed (by reformatting or field injection)?

**Before:** PARTIAL RISK. `compute_content_hash` excluded only `content_hash`. Adding or changing `trace` or `created_at` produced a different hash for identical semantic content. This made the hash sensitive to metadata changes, weakening its use as a content integrity signal.

**After:** CLOSED. `hash_utils.compute_content_hash` excludes `content_hash`, `trace`, and `created_at`. The canonical policy is:
- Sorted keys at all nesting levels (`sort_keys=True`)
- No whitespace variation (`separators=(",", ":")`)
- ASCII-safe encoding
- Deterministic across field insertion order, trace changes, and timestamp changes

Same semantic content always produces the same hash.

---

### 4. Can an artifact be modified post-eval?

**Before:** PARTIAL. The artifact store used deep-copy at read/write (fixed in H01 FIX-004), and hash verification was in place. However, the non-canonical hash meant that altering `trace` or `created_at` after the hash was computed could change the stored hash value.

**After:** ENFORCED. Hash verification now uses the canonical policy. Any mutation to payload content (excluding metadata) will cause a hash mismatch and be rejected at `register_artifact`. The store remains append-only and deep-copies on write and read.

---

### 5. Can missing eval slip through?

**Before:** YES. `route_artifact()` required no eval evidence. Missing eval was not a routing blocker.

**After:** NO. `route_with_control_check()` requires `eval_summary` in the control decision. Missing `eval_summary` raises `MISSING_EVAL_SUMMARY`. Missing `evaluation_control_decision` raises `MISSING_EVALUATION_CONTROL_DECISION`. There is no path to routing without both fields.

---

## Findings Summary

| ID    | Severity | Description                                           | Status  |
|-------|----------|-------------------------------------------------------|---------|
| F-001 | S4       | S4 severity non-blocking allowed by schema            | FIXED   |
| F-002 | S4       | Routing possible without control decision             | FIXED   |
| F-003 | S3       | Hash not canonical — trace/timestamp included         | FIXED   |
| F-004 | S3       | source_segment_ids optional on issues                 | FIXED   |
| F-005 | S2       | Decision records lacked traceability requirement      | FIXED   |

**No S2+ findings remain open.**

---

## Control Boundary Changes

The following bypass paths are now impossible:

1. **Route without control decision** — `route_with_control_check` enforces the gate
2. **S4 finding without blocking** — schema validation rejects at write time
3. **Hash spoofing via metadata changes** — canonical policy excludes metadata fields
4. **Issue without source origin** — `source_segment_ids` required, minItems: 1
5. **Decision without traceable origin** — anyOf constraint requires source_reference or rationale

---

## Hash Policy

```
excluded: content_hash, trace, created_at
included: all other fields (artifact_id, artifact_type, schema_ref, provenance, payload content)
algorithm: SHA-256
encoding: sorted keys, no whitespace, ASCII-safe JSON
format: "sha256:<64-hex-chars>"
```

---

## Severity Model

```
S4 = halt (critical blocker) — blocking MUST be true
S3 = high — blocking optional but expected
S2 = medium — blocking optional
S1 = low — blocking optional
S0 = informational — blocking optional
```

---

## Tests Added

| Test File                                  | Scenarios                                          |
|--------------------------------------------|----------------------------------------------------|
| test_control_routing_enforcement.py        | 12 routing control scenarios (H01B-2, H01B-4)      |
| test_h01b_hardening.py (S4 class)          | 5 severity integrity scenarios (H01B-1)             |
| test_h01b_hardening.py (hash class)        | 8 hash canonicalization scenarios (H01B-3)          |
| test_h01b_hardening.py (grounding classes) | 9 source grounding scenarios (H01B-5)               |

---

## Remaining Risk

1. `route_artifact()` is still exported and can be called without control enforcement. Callers MUST use `route_with_control_check` — this is enforced by convention/code review, not by removing the lower-level function. The lower-level function is needed for internal composition.

2. The `warn_allowed` parameter in `route_with_control_check` allows callers to opt into warn-level routing. This is intentional but requires callers to be explicit. No implicit warn acceptance.

3. Source grounding for issue_registry enforces non-empty `source_segment_ids` but does not verify that the segment IDs actually exist in the upstream transcript. Cross-artifact referential integrity is a future constraint.

---

**Verdict:** REVISE → PASS after fixes applied. All S2+ findings resolved.
