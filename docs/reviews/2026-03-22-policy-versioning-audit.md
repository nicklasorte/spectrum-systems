# Policy Versioning Governance Audit — BAS

## 1. Review Metadata
- **Review Date:** 2026-03-22
- **Repository:** spectrum-systems
- **Reviewer:** Claude (Reasoning Agent — Sonnet 4.6)
- **Review Type:** Critical governance audit — Policy Versioning System (BAS)
- **Inputs Consulted:**
  - `governance/policies/policy-registry.json`
  - `governance/policies/policy-registry.schema.json`
  - `governance/policies/run-policy-engine.py`
  - `data/policy/slo_policy_registry.json`
  - `contracts/schemas/slo_policy_registry.schema.json`
  - `config/regression_policy.json`
  - `contracts/schemas/regression_policy.schema.json`
  - `contracts/schemas/eval_admission_policy.schema.json`
  - `contracts/examples/eval_admission_policy.json`
  - `governance/schemas/provenance.schema.json`
  - `schemas/provenance-schema.json`
  - `spectrum_systems/modules/runtime/policy_registry.py`
  - `contracts/standards-manifest.json`
  - `docs/data-provenance-standard.md`
  - `docs/contract-versioning.md`
  - `docs/governance-enforcement-roadmap.md`
  - `docs/adr/ADR-006-governance-manifest-policy-engine.md`
  - `docs/adr/ADR-007-phase-1-governance-enforcement.md`
  - `docs/adr/ADR-008-schema-authority-designation.md`

## 2. Scope
- **In-bounds:** Policy immutability, policy identity strength, artifact-to-policy linkage, snapshot consistency, silent policy drift, version history traceability, fail-closed policy resolution, policy scope clarity.
- **Out-of-bounds:** Contract schema correctness (reviewed separately), evaluation engine internals, replay engine, downstream implementation repos.

## 3. Decision

**FAIL**

The system has at least two independently sufficient failure conditions: (1) the runtime policy resolver is explicitly fail-open, and (2) no mechanism prevents silent in-place mutation of policy definitions. Either alone is a governance-critical failure. Together they undermine every auditability claim the system makes.

## 4. Critical Findings

### CF-1 — CRITICAL: Policy Resolution Is Fail-Open

`spectrum_systems/modules/runtime/policy_registry.py` documents an explicit three-step resolution order:

1. Explicit caller-provided policy (beats everything)
2. Stage-bound default (if stage provided and has binding)
3. **System default policy (permissive) as final fallback**

When a caller provides no `policy_id` and no stage binding matches, the system silently applies the **permissive** profile — the profile that allows warnings and degraded lineage, and that would admit artifacts `decision_grade` would reject. There is no error raised. There is no record in the artifact that a fallback occurred. A decision-grade artifact evaluated without an explicit policy parameter receives permissive treatment with a valid-looking provenance record. This is not an edge case — it is the specified default behavior.

**This single failure invalidates the fail-closed contract of the entire system.**

---

### CF-2 — CRITICAL: No Policy Immutability Enforcement

All three policy registries are mutable plaintext JSON files:
- `governance/policies/policy-registry.json` (GOV-001 through GOV-010)
- `data/policy/slo_policy_registry.json` (permissive, decision_grade, exploratory)
- `config/regression_policy.json` (threshold definitions)

There is no write-once mechanism, no content-addressed identity (e.g., SHA-256 of policy body embedded in or verifiable against `policy_id`), no cryptographic signing, and no append-only structure. Any in-place edit to an existing policy definition silently changes the behavior of all prior artifacts that reference that `policy_id`. The system cannot detect this has occurred. Retroactive mutation is not just possible — it is the default mode of operation, enabled by the file format itself.

---

### CF-3 — CRITICAL: `policy_id: "default"` in `config/regression_policy.json`

The regression policy carries `"policy_id": "default"`. This violates every requirement for strong policy identity:

- **Not globally unique.** Any other system, profile, or configuration artifact could declare the same id.
- **Not unambiguous.** `"default"` encodes fallback semantics into the identity itself — it implies a policy that is resolved by convention, not by explicit reference.
- **Not collision-safe.** The three policy namespaces (GOV-NNN, SLO profile names, regression/eval policy ids) have no cross-namespace deduplication. `"default"` could resolve to any of them depending on resolution context.
- **Invites ambient resolution.** Downstream consumers may match on the literal string `"default"` rather than on a specific governed policy reference.

This is not a naming style issue. Encoding `"default"` as a policy_id structurally conflates identity with fallback, making the governance trail ambiguous by design.

---

### CF-4 — HIGH: Provenance Schema Does Not Require `policy_id`

`governance/schemas/provenance.schema.json` mandates `contract_version` as a required field but contains no `policy_id` field at all — neither required nor optional. An artifact can be created, admitted, evaluated, and emitted with a fully schema-valid provenance record that contains zero information about which policy governed it.

The fundamental audit requirement is: given an artifact, you must be able to recover the exact policy under which it was admitted and evaluated. That recovery is currently impossible from the provenance record alone. It would require out-of-band correlation against system logs that may not exist. This gap makes the provenance standard insufficient for external audit purposes.

---

### CF-5 — HIGH: Governance Policy Definitions Have No Version History

`governance/policies/policy-registry.json` defines 10 active governance policies (GOV-001 through GOV-010). None of these entries contain:
- a `version` field
- `created_at` / `modified_at` timestamps
- a `superseded_by` reference
- a changelog reference

There is no mechanism to reconstruct what GOV-007 required on any specific historical date. If GOV-007 is edited today, every artifact ever evaluated against GOV-007 is retroactively re-governed by the new definition. The system cannot produce evidence of what the policy said at the time enforcement occurred. This is an audit failure by definition — the document that should be the immutable record of enforcement rules is instead a mutable configuration file.

## 5. Required Fixes

### RF-1: Remove the permissive fallback from `policy_registry.py`

The final fallback in the stage binding resolution order must be replaced with a hard error. If no explicit `policy_id` is provided and no stage binding matches, the call must raise an error with a descriptive message identifying the missing parameter. There is no legitimate governance scenario in which "caller did not specify a policy" should silently succeed with permissive treatment.

**Concrete change:** In the resolution logic, replace the step-3 fallback assignment with:

```python
raise PolicyResolutionError(
    "No explicit policy_id provided and no stage binding found. "
    "Policy resolution requires an explicit policy_id."
)
```

All callers must be updated to pass an explicit `policy_id`.

---

### RF-2: Enforce content-addressed or append-only policy identity

Policy registries must be restructured so that a policy definition can never be silently overwritten. Two viable approaches:

**Option A (content-addressed):** Derive `policy_id` deterministically from a hash of the policy body (e.g., `sha256:<first-16-chars-of-body-hash>`). Any change to policy content produces a new `policy_id` automatically. Store old definitions permanently.

**Option B (append-only files with manifest):** Split each policy into an individual versioned file (e.g., `GOV-007.v1.json`, `GOV-007.v2.json`) in an append-only directory. A manifest file references the current active version of each policy. Retired policy files are never deleted. Version transitions require a new file, not an edit.

Either option must be accompanied by CI enforcement that detects modifications to existing policy definition files and fails the build.

---

### RF-3: Replace `policy_id: "default"` in `regression_policy.json`

Assign a specific, unambiguous, version-tagged identifier (e.g., `regression-policy-v1.0.0`). Update all artifacts and system references that currently resolve against `"default"`. Treat this as a policy change requiring a new policy record, not an in-place edit.

Additionally, define a namespace convention for the three policy identity spaces to prevent future collisions:
- Governance policies: `gov:<GOV-NNN>`
- SLO profiles: `slo:<profile-name>`
- Regression/admission policies: named with system prefix and version

---

### RF-4: Add `policy_id` as a required field in provenance schema

Both `governance/schemas/provenance.schema.json` and `schemas/provenance-schema.json` must be updated to include `policy_id` as a required field referencing the governing policy at the time of artifact creation. This field must be populated by the system that generates the artifact, not inferred post-hoc.

This change should be accompanied by a schema version bump and a migration note for existing provenance records.

---

### RF-5: Add version history fields to all policy definitions

Every policy entry in every registry must include at minimum:
- `schema_version` — version of the policy definition schema
- `created_at` — ISO 8601 timestamp of initial creation
- `last_modified_at` — ISO 8601 timestamp of most recent change
- `status` — enum: `draft | active | retired`
- `superseded_by` — reference to replacement policy_id (when retired)

The registry schema (`policy-registry.schema.json`) must enforce these fields as required properties. Existing entries must be backfilled with their creation dates estimated from git history.

## 6. Optional Improvements

### OI-1: Unify policy identity namespace

Define a global policy identity namespace schema with prefix conventions enforced by the policy registry schemas. Maintain a cross-namespace collision registry in the standards-manifest so `policy_id` uniqueness can be verified at CI time across all three registries.

### OI-2: Operationalize Phase 2 CI enforcement

Phase 2 (automated schema and contract validation) is designed, documented, and planned — but not yet active. Policy snapshot consistency enforcement has no automated gate. Phase 2 activation should be a hard prerequisite before any artifact is designated production-grade. Until CI prevents `policy_id` mismatches between registry state and artifact records, governance is aspirational rather than operative.

### OI-3: Register policy registries as governed artifacts in standards-manifest

The standards-manifest currently tracks contract versions. Policy registries (`slo_policy_registry`, `regression_policy`, governance policy registry) should also be versioned entries in the manifest so that governance state at any point in time can be reconstructed from a single manifest snapshot — enabling full historical audit.

### OI-4: Extend GOV policies to detect fallback policy usage

Add a new governance policy (GOV-011) that inspects enforcement result artifacts and flags any result where the `policy_id` field indicates permissive treatment was applied to an artifact whose `stage` binding maps to `decision_grade`. This would surface fallback-policy misapplication as a governance check even before RF-1 is implemented.

## 7. Trust Assessment

**NO — policy governance cannot be trusted to never drift silently.**

The system has an explicit fail-open fallback in its runtime enforcement module, no immutability mechanism preventing in-place policy rewrites, no `policy_id` requirement in provenance records, and no version history for the governance policies themselves. An artifact evaluated today and re-evaluated tomorrow against a silently mutated policy would produce different results with identical `policy_id` references and no record of the change. The system cannot detect this, report it, or prevent it.

## 8. Failure Mode Summary

**Worst realistic governance failure this system can produce:**

A decision-grade artifact (recommend or synthesis stage) is evaluated by a caller that omits `policy_id`. The Python runtime silently falls back to `permissive`. The artifact is admitted with degraded lineage that `decision_grade` would have blocked. The provenance record carries a valid `contract_version` but no `policy_id`. Between evaluation and audit, the governance policies are silently edited in-place — no new `policy_id` is generated, no changelog entry is created.

Six months later, during an external audit, the artifact is challenged. The system cannot produce:
- which policy was in effect at evaluation time
- that permissive policy was applied rather than decision_grade
- whether the policy definition has been changed since the artifact was created

The artifact passes external review by default because the audit trail is technically schema-valid — it simply omits the information that would have triggered rejection. The governance system has produced a laundered artifact: compliant-looking, ungoverned in practice, and impossible to retroactively challenge. This failure is silent, automatic, and structurally enabled by the current design.

## 9. Follow-up Triggers

- When RF-1 (fail-closed policy resolution) is implemented: re-audit `policy_registry.py` and all callers for correct explicit `policy_id` propagation.
- When RF-2 (policy immutability) is implemented: verify that CI correctly rejects in-place edits to existing policy definitions.
- When RF-4 (provenance `policy_id` field) is merged: audit existing provenance records for backfill completeness.
- When Phase 2 CI enforcement is activated: re-run snapshot consistency check against all artifact stores.
