# Spectrum Systems — Red Team Audit

**Date:** 2026-04-09  
**Branch:** work  
**Scope:** Full system structural audit  
**Verdict:** NOT_SAFE_TO_SCALE  

---

## OVERALL ASSESSMENT

- Is the system safe to operate at scale?
  - No. The repository contains multiple first-class execution entrypoints that can invoke PQX execution directly without provable mandatory TPA pre-gating, and SEL enforcement can be configured to skip TPA evidence checks when `tpa_required` is false.
- What is the single biggest structural risk?
  - Authority-chain break: execution can proceed through direct PQX pathways (CLI + module calls) where TPA is either evaluated after execution or represented by a synthetic/static decision surface rather than an input-constrained pre-execution gate.

---

## TOP 5 RISKS (Ranked)

### RISK 1 — TPA pre-execution gate is not globally mandatory
- Severity: BLOCKER
- Failure Mode:
  - PQX execution is callable directly from CLI/module seams without a cryptographically bound, mandatory TPA artifact precondition.
- Exploit Scenario:
  - Operator or script calls `scripts/pqx_runner.py` or `run_pqx_slice(...)` directly with acceptable local inputs; execution advances without a required TPA artifact lineage proving pre-authorization of that specific slice.
- Why it exists:
  - PQX entry surfaces are distributed, and enforcement checks are contextual/optional rather than globally hard-required at every execution seam.

### RISK 2 — TLC default path executes PQX before TPA decision
- Severity: BLOCKER
- Failure Mode:
  - In the TLC loop, PQX is invoked, artifacts emitted, and only then TPA is invoked.
- Exploit Scenario:
  - A run that should have been denied by policy still performs execution side effects before policy disposition is computed.
- Why it exists:
  - Orchestration order in core TLC state progression runs `PQX -> TPA` instead of enforcing `TPA -> PQX` as a non-bypass invariant.

### RISK 3 — SEL can allow execution with TPA evidence absent
- Severity: HIGH
- Failure Mode:
  - SEL only enforces TPA evidence when `execution_request.tpa_required == true`; flows can set false and skip TPA checks.
- Exploit Scenario:
  - Caller supplies valid-looking PQX proof and governance refs, sets `tpa_required: false`, and bypasses TPA artifact requirements while still passing SEL allow.
- Why it exists:
  - Boundary enforcement uses conditional policy flags instead of an immutable runtime invariant for governed execution.

### RISK 4 — Repair recursion bounded by budget, not single-fix invariant
- Severity: HIGH
- Failure Mode:
  - TLC supports repeated `continue_repair_bounded` attempts while retry budget remains.
- Exploit Scenario:
  - A failure class keeps bouncing between CDE continue and PQX repair attempts, creating multi-repair cycles in one run contrary to strict one-fix-slice-per-cycle guarantees.
- Why it exists:
  - Control logic is budget-gated and state-looped; no hard structural cap of one fix emission per cycle execution instance.

### RISK 5 — Markdown review text can dominate downstream decision inputs
- Severity: MEDIUM
- Failure Mode:
  - Review parsing handoff trusts markdown section parsing for decision/finding interpretation; malformed but syntactically compliant markdown can steer findings.
- Exploit Scenario:
  - Provider output with crafted markdown headings/decision text passes parser shape checks, producing deterministic but adversary-steered findings and queue step decisions.
- Why it exists:
  - Parser assurance emphasizes section presence and regex extraction, not strong semantic cross-validation against structured independent truth sources.

---

## BYPASS PATHS

List all concrete ways to bypass:
- PQX
  - Direct invocation of `run_pqx_slice(...)` from scripts/modules bypassing TLC route enforcement.
  - Direct CLI entry through `scripts/pqx_runner.py` without mandatory upstream TLC/AEX handoff artifacts.
  - Bundle/sequence runners invoking PQX execution seams directly from runtime orchestration utilities.
- TPA
  - TLC invokes PQX first and TPA second in execution state path.
  - SEL allows no-TPA-evidence paths when `tpa_required` is false.
  - `_real_tpa` in TLC adapter path is effectively synthetic policy context (static positive posture), not bound to concrete per-slice risk evidence.
- SEL
  - SEL checks are caller-context dependent; subsystem overrides in run requests can replace SEL adapter behavior.
  - Direct PQX script/module entrypoints can run outside TLC SEL-wrapped state transitions.
- Promotion gate
  - Multiple gate surfaces exist (judgment promotion gate, GitHub continuation promotion gate, canary/promotion consistency checks) with non-unified authority. Divergent pathways increase chance of an allow path inconsistent with strict single gate semantics.

---

## HIDDEN FAILURE MODES

Non-obvious failure conditions.

- Execution/policy inversion: policy denial arrives after execution already happened.
- Conditional enforcement drift: developers forget to set `tpa_required`, silently downgrading enforcement.
- Artifact lineage split-brain: promotion evidence can be inferred/synthesized from refs rather than irreducible mandatory artifacts in some paths.
- Retry-induced state inflation: repeated repair attempts mutate lineage and emitted refs, increasing ambiguity for closure authority.
- Adapter substitution risk: injectable subsystem functions create testability power but also production-hardening risk if not locked by environment/profile.

---

## FALSE GUARANTEES

List guarantees that are claimed but not actually enforced.

- “All execution gated by TPA before PQX.”
  - Not enforced globally; concrete path executes PQX then TPA.
- “PQX is the only executor and always entered via governed orchestration.”
  - Multiple direct script/module execution seams allow PQX access.
- “No recursive auto-fix loops / one fix slice max per cycle.”
  - TLC repair path supports repeated bounded attempts while budget remains.
- “Promotion gate is singular and fail-closed.”
  - Gate logic is distributed across multiple modules/surfaces, increasing inconsistency risk.
- “No raw prompt execution.”
  - Markdown-derived review interpretation can materially drive downstream decisions without independent structured corroboration.

---

## DRIFT VECTORS

Where the system will degrade over time.

- New scripts will continue to add convenience entrypoints around PQX without hard central admission enforcement.
- Optional booleans (`tpa_required`, mode flags) will be mis-set and silently weaken trust boundaries.
- Parallel governance surfaces for promotion/closure will diverge semantically.
- Test-only subsystem override hooks can leak into operational run patterns.
- Documentation claims will outpace executable invariant checks, creating compliance theater.

---

## REQUIRED FIXES (Minimal)

Only structural fixes required before scale.

No refactors.
No polish.

- Enforce hard ordering invariant: TPA artifact verification must occur before any PQX execution call in all execution-capable paths.
- Add a single mandatory PQX admission guard callable at every entrypoint (CLI/module/orchestrator) that requires TPA lineage artifact + SEL allow proof.
- Remove conditional TPA bypass in SEL for governed execution context; TPA evidence must be required when `execution_context` is governed.
- Enforce single repair attempt invariant per cycle artifact (or explicit formalized multi-attempt contract with different guarantee language).
- Consolidate promotion authority to one canonical gate artifact consumed by all promotion-capable paths; block on absence or mismatch.

---

## SAFE TO SCALE?

Answer clearly:
- NO

---
