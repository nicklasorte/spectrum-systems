# Phase 5: Attack the 10 Fragile Points

## Overview

Spectrum Systems has 10 critical gaps holding it back from production durability. Phase 5 implements clusters A-E (gaps 1-5, blocking production release) with follow-up on gaps 6-10 (governance scaling).

**Production Release Blocking**: Gaps 1-5 must be closed before production.  
**Governance Scaling**: Gaps 6-10 required for sustainable operations.

---

## Gap Definitions

### Gap 1: TRACE + PROVENANCE COMPLETENESS (Critical)
**Problem**: Weak trace + provenance completeness. Without propagation you lose causal visibility.

- Replay verification works, but causality reconstruction fails
- Loss of trace_id at any step breaks root cause analysis
- Provenance chain incomplete (inputs → code → model version → outputs)

**Blocking**: Root cause analysis, incident learning, reproducible debugging

### Gap 2: SIGNED PROVENANCE & SUPPLY-CHAIN INTEGRITY (Critical)
**Problem**: Insufficient supply-chain-grade integrity for promoted artifacts.

- Artifacts promoted without verifiable evidence of clean builds
- No cryptographic proof of certification artifact trustworthiness
- Promotion API lacks verification gates

**Blocking**: Trust in released artifacts, compliance, auditability

### Gap 3: JUDGMENT SYSTEM & DECISION RATIONALE (Critical)
**Problem**: No first-class judgment_record artifact between artifacts and control.

- Control loop makes "freeze" decision but generates no artifact capturing WHY
- No structured decision rationale, evidence, alternatives
- Judgment policy registry doesn't exist
- Can't reuse decisions or detect contradictions

**Blocking**: Explainability, contradiction detection, learning, policy enforcement

### Gap 4: POLICY TESTING AS FIRST-CLASS GATE (Critical)
**Problem**: Missing policy testing gate. Policies treated as execution, not governed releases.

- No test suite before policy deployment
- No regression detection when policy behavior changes
- Policies not versioned/reviewed/gated like code
- Can't replay decision to verify it still holds

**Blocking**: Safe policy evolution, regression detection, reproducibility

### Gap 5: FAIL-CLOSED VALIDATION & SCHEMA ENFORCEMENT (Critical)
**Problem**: Unvalidated outputs treated as truth. Artifacts lack schema validation gates.

- MVPs generate artifacts without schema validation on admission
- Model outputs accepted even if non-conformant
- Malformed artifacts proceed through pipeline
- No fail-closed gate preventing invalid artifacts from promotion

**Blocking**: Reliability, composability, downstream integrity

### Gap 6: HIDDEN LOGIC CREEP DETECTION (High Priority)
**Problem**: Decision logic migrates into ungoverned places (prompts, scripts, tribal knowledge).

- MVP prompts contain decision heuristics not in policies
- Model routing logic in code, not policy artifacts
- No audit detecting ungoverned decision surfaces

**Blocking**: Governance transparency, policy auditability

### Gap 7: SLICE-BASED EVAL COVERAGE AUDITS (High Priority)
**Problem**: Evaluation blind spots. Regressions hidden in aggregate metrics.

- eval_pass_rate = 99% but high-priority findings = 85%
- No coverage tracking per slice (issue type, priority, section)
- Missing slices not detected

**Blocking**: Quality assurance, regression detection, minority-case safety

### Gap 8: INCIDENT-LEARNING INTEGRATION (High Priority)
**Problem**: Missing incident-learning loop. Failures recur without formalized automation.

- Postmortems exist but don't drive new eval cases
- No automation: incident → action → policy change → gated rollout
- Human overrides don't become rules

**Blocking**: System improvement, error recurrence prevention

### Gap 9: EXCEPTION ECONOMICS & OVERRIDE GOVERNANCE (High Priority)
**Problem**: Insufficient exception economics. Exceptions become the real system.

- Exceptions age without conversion to policy
- Override backlog grows unbounded
- No metrics on which decisions need human approval
- Control flow degrades as exceptions pile up

**Blocking**: Governance health, SRE-style budget management

### Gap 10: SINGLE SOURCE OF TRUTH FOR DECISION STATE (High Priority)
**Problem**: Lack of canonical declared state. Drift endemic without GitOps discipline.

- Active policy version unclear when multiple exist
- Precedents can be superseded but active set not queryable
- Policy registry doesn't enforce single-active constraint
- Out-of-band changes not detected as drift

**Blocking**: Auditability, canonicality, drift detection

---

## Phase 5 Build Plan

### Cluster A: Trace & Provenance Completeness

**Artifacts**:
1. W3C Trace Context propagation enforcement
   - Every artifact must have valid trace_id
   - Trace_id must propagate through all steps
   - Test: reject artifacts with missing/broken trace_id

2. Provenance chain reconstruction
   - Schema: inputs → code version → model version → outputs
   - Verify complete chain exists at promotion time
   - Enable replay from provenance alone

3. Provenance completeness checks at promotion
   - Validation step: is chain complete?
   - Block promotion if incomplete
   - Metrics: provenance_completeness_rate

4. Replay fidelity verification
   - Can we recreate artifact from provenance?
   - Test suite for replay scenarios

**Files to create/modify**:
- `src/core/trace/trace_context.py` - W3C context propagation
- `src/core/provenance/chain_validator.py` - completeness checks
- `src/core/promotion/pre_promotion_checks.py` - add provenance validation
- `tests/unit/trace/test_trace_propagation.py`
- `tests/integration/provenance/test_replay_fidelity.py`

### Cluster B: Signed Provenance & SLSA

**Artifacts**:
1. Cryptographic signing of promotion artifacts
   - Sign all artifacts at promotion boundary
   - Include code version, model version, inputs, outputs
   
2. SLSA framework integration (level 3)
   - Hermetic build requirement
   - Provenance signed and verifiable
   - Immutable artifact store
   
3. Verification gates in promotion pipeline
   - Verify signature before promotion approval
   - Verify SLSA level compliance
   
4. Audit log of verifications
   - Record all signature checks
   - Timestamp, verifier, artifact_id, result

**Files to create/modify**:
- `src/core/signing/artifact_signer.py` - cryptographic signing
- `src/core/signing/signature_verifier.py` - verification logic
- `src/core/slsa/slsa_builder.py` - SLSA compliance
- `src/core/promotion/signature_verification_gate.py` - gate integration
- `src/audit/signature_audit_log.py`

### Cluster C: Judgment System

**Artifacts**:
1. judgment_record artifact schema
   - decision_id, decision_timestamp, decider_id
   - evidence (list of artifact_ids considered)
   - policy selections (which policies matched)
   - precedents applied (past decisions cited)
   - alternatives rejected (with reasoning)
   - outcome (freeze/block/promote/etc)

2. judgment_policy registry (versioned, tested, gated)
   - policy_name, policy_version, effective_date
   - decision conditions (when policy applies)
   - decision outcome (what policy prescribes)
   - contradiction detection (incompatible policies)
   
3. Contradiction detection
   - If multiple policies match same case, detect
   - Escalate to CDE for resolution
   - Record contradiction as incident signal
   
4. Precedent reuse & similarity matching
   - Given artifact, find similar past judgments
   - Reuse precedent (cite evidence) or override (cite new evidence)

**Files to create/modify**:
- `src/core/judgment/judgment_record.py` - schema and validation
- `src/core/judgment/judgment_artifact_factory.py` - artifact creation
- `src/core/judgment/judgment_policy_registry.py` - policy versioning
- `src/core/judgment/contradiction_detector.py` - conflict detection
- `src/core/judgment/precedent_matcher.py` - similarity matching
- `tests/unit/judgment/test_contradiction_detection.py`
- `tests/integration/judgment/test_precedent_reuse.py`

### Cluster D: Policy Testing Gates

**Artifacts**:
1. Test suite for every policy change
   - Before deployment: must pass test suite
   - After deployment: versioned and immutable
   
2. Regression detection
   - Run new policy v2 against historical cases
   - Compare outcomes to v1 behavior
   - Flag if v2 changes old decisions (regression candidate)
   
3. Fail-closed: block policy promotion if tests fail
   - Gate in CDE before policy activation
   - Require evidence of test passage
   
4. Version immutability
   - Once policy_version deployed, it's read-only
   - Changes = new policy_version
   - Active set tracks only current version

**Files to create/modify**:
- `src/core/policy/policy_test_suite.py` - test framework
- `src/core/policy/regression_detector.py` - v1 vs v2 comparison
- `src/core/policy/policy_versioning.py` - version immutability
- `src/core/cde/policy_promotion_gate.py` - test-required gate
- `tests/unit/policy/test_regression_detection.py`
- `tests/integration/policy/test_policy_versioning.py`

### Cluster E: Schema Validation Gates

**Artifacts**:
1. JSON Schema validation on artifact admission
   - Every artifact has schema contract
   - Validate against schema at MVP output
   - Reject non-conformant artifacts
   
2. Fail-closed: reject artifacts with violations
   - Block invalid artifact from pipeline
   - Log rejection with evidence
   
3. Enforcement at MVP output (not post-hoc)
   - Validation happens during artifact creation
   - Invalid artifact never created
   
4. Schema evolution rules
   - Compatibility checks (new schema vs old)
   - Migration strategy for active artifacts
   - Version tracking for schema changes

**Files to create/modify**:
- `src/core/schema/artifact_schema_validator.py` - validation logic
- `src/core/schema/schema_registry.py` - schema versioning
- `src/core/schema/schema_compatibility_checker.py` - evolution
- `src/core/mvp/output_validation_gate.py` - enforce at MVP output
- `tests/unit/schema/test_artifact_validation.py`
- `tests/integration/schema/test_schema_evolution.py`

---

## Success Criteria

After Phase 5:

- ✅ Zero artifacts promoted without complete trace + provenance
- ✅ All promoted artifacts cryptographically signed + verified  
- ✅ Every control decision has judgment_record with evidence + rationale
- ✅ All policy changes tested before deployment; regressions detected
- ✅ All MVP outputs validated against schema; invalid artifacts blocked
- ✅ System "production-ready" per durability standards

---

## Implementation Sequence

1. **Cluster A** (Trace): Foundation for all other clusters (causal visibility required)
2. **Cluster E** (Schema): Fail-closed validation prevents bad artifacts entering pipeline
3. **Cluster C** (Judgment): Record decision rationale explicitly (required for policy testing)
4. **Cluster D** (Policy): Test and version policies; detect regressions
5. **Cluster B** (SLSA): Cryptographic signing and supply-chain integrity (final gate)

---

## Metrics & Observability

- `trace_context_propagation_rate` - % artifacts with valid trace_id
- `provenance_completeness_rate` - % artifacts with complete chain
- `schema_validation_pass_rate` - % artifacts conforming to schema
- `policy_test_pass_rate` - % policy changes passing test suite
- `judgment_record_creation_rate` - % decisions with recorded rationale
- `signature_verification_success_rate` - % artifacts with verified signatures
- `promotion_ready_artifacts` - count of artifacts in ready_for_merge state
