# RE-03 Candidate Roadmap (Source-Grounded)

## 1) Intent
Generate the next candidate roadmap as a **gap-closing execution sequence** grounded in source obligations and RE-02 repo truth, without redesigning architecture, breaking parser/mirror compatibility, or introducing parallel trust spines.

## 2) Source Inputs Used
Authoritative inputs used directly for this candidate:
1. `docs/source_indexes/obligation_index.json`
2. `docs/roadmaps/execution_state_inventory.md` (including March 31, 2026 RE-02 scan block)
3. `docs/source_structured/ai_durability_strategy.source.md`
4. `docs/architecture/strategy_control_document.md`
5. Repository seams (modules/schemas/tests) in `spectrum_systems/modules/`, `contracts/schemas/`, and `tests/`

## 3) Current System State (RE-02 Summary)
- Contracts and fail-closed core seams are broadly implemented, but enforcement remains distributed for promotion/lineage/eval-policy coupling.
- PQX and review/repair capabilities are present with broad coverage, but sequence-level dominance and long-chain confidence remain partial/fragmented.
- The largest risk is **distributed partial enforcement** across promotion and learning-to-prevention boundaries, not total absence.
- No obligation is fully missing, but five obligations remain partial and are the exclusive focus of this roadmap.

## 4) Obligation Coverage (Refined)

| Obligation ID | RE-02 Status | RE-03 Refined Status | Repo-grounded reason |
| --- | --- | --- | --- |
| OBL-AIDUR-ARTIFACT-SOR | covered | covered | Artifact envelope + governed artifact handling are already enforced in runtime/governance seams. |
| OBL-AIDUR-MODEL-REPLACEABLE | covered | covered | Stable adapter request/response contracts and tests are already in place. |
| OBL-AIDUR-CONTROL-EXTERNALIZED | covered | covered | Control decisions are externalized via control-loop and evaluation-control artifacts. |
| OBL-AIDUR-FAIL-CLOSED-MISSING-EVIDENCE | covered | covered | Missing evidence paths are fail-closed in control/runtime/certification seams. |
| OBL-AIDUR-SCHEMA-BEFORE-CONSUME | partial | partial (unchanged) | Enforcement exists in local seams; no single universal downstream-consumption authority gate yet. |
| OBL-AIDUR-LINEAGE-BEFORE-PROMOTION | partial | partial (unchanged) | Lineage checks are present but not consolidated as one platform-wide promotion authority seam. |
| OBL-AIDUR-EVAL-POLICY-BEFORE-PROMOTION | partial | partial (unchanged) | Eval/policy checks exist but remain distributed across multiple promotion-related paths. |
| OBL-AIDUR-MEASURABLE-PROMOTION-ROLLOUT | partial | partial (unchanged) | Rollout states and canary controls exist; measurable-threshold-to-promotion closure is not yet singular. |
| OBL-AIDUR-LEARNING-PREVENTION-CLOSURE | partial | **partial (dominant bottleneck)** | Learning outputs exist but are not yet mandatory recurrence-prevention authority for progression/promotion. |

### Covered / Partial / Missing Counts
- Covered: 4
- Partial: 5
- Missing: 0

## 5) Dominant Bottleneck
Learning-loop outputs are not yet hard-bound as mandatory recurrence-prevention authority in the single promotion/progression spine.

## 6) Roadmap Table

> Scope rule: Every step below closes one or more **partial** obligations; no already-covered obligation is used as primary scope.

| Step ID | Step Name | Obligation IDs | What It Enforces | Repo Seams (module/schema/test) | Control Loop Stage | Learning Loop Stage | Why Now | Dependencies | DoD |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CL-01 | Failure→Eval→Policy Hard Binding | OBL-AIDUR-EVAL-POLICY-BEFORE-PROMOTION; OBL-AIDUR-LEARNING-PREVENTION-CLOSURE | Every critical failure class must produce linked eval case + policy reference artifact before progression eligibility can advance. | `spectrum_systems/modules/runtime/control_loop.py`; `spectrum_systems/modules/runtime/evaluation_enforcement_bridge.py`; `contracts/schemas/evaluation_control_decision.schema.json`; tests in `tests/test_control_loop.py`, `tests/test_evaluation_enforcement_bridge.py` | Learn → Decide | Detection → Root Cause | Converts advisory failure analysis into governed inputs. | none | Progression/promotion decision fails closed when failure has no linked eval+policy artifacts; passing tests prove blocking behavior. |
| CL-02 | Error-Budget Enforcement Activation | OBL-AIDUR-MEASURABLE-PROMOTION-ROLLOUT; OBL-AIDUR-EVAL-POLICY-BEFORE-PROMOTION | Budget burn-rate and readiness thresholds are mandatory decision inputs for warn/freeze/block and promotion eligibility. | `spectrum_systems/modules/runtime/judgment_policy_lifecycle.py`; `spectrum_systems/modules/runtime/pqx_canary_rollout.py`; `contracts/schemas/judgment_policy_rollout_record.schema.json`; `contracts/schemas/error_budget_policy.schema.json`; tests `tests/test_judgment_policy_lifecycle.py`, `tests/test_pqx_canary_rollout.py` | Interpret → Enforce | Validation | Makes measurable thresholds authoritative, not informational. | CL-01 | Promotion eligibility cannot pass with missing/violated thresholds; tests include fail-closed threshold absence and budget-exceeded freeze/block. |
| CL-03 | Recurrence Prevention Gate | OBL-AIDUR-LEARNING-PREVENTION-CLOSURE | Serious failures require prevention assets (regression fixture and/or policy tightening record) prior to closure. | `spectrum_systems/modules/runtime/judgment_learning.py`; `spectrum_systems/modules/runtime/control_loop.py`; policy schemas (`contracts/schemas/regression_policy.schema.json`, `contracts/schemas/drift_remediation_policy.schema.json`); tests `tests/test_judgment_learning.py`, `tests/test_control_loop_hardening.py` | Learn → Enforce | Fix → Prevention | Closes the failure→prevention gap identified by RE-02 bottleneck. | CL-02 | Closure artifact without prevention linkage is rejected; deterministic recurrence-prevention gate tests pass. |
| CL-04 | Judgment Authority Consumption Gate | OBL-AIDUR-EVAL-POLICY-BEFORE-PROMOTION; OBL-AIDUR-MEASURABLE-PROMOTION-ROLLOUT | Transition/promotion decisions must consume judgment lifecycle artifacts as hard authority inputs. | `spectrum_systems/modules/runtime/judgment_policy_lifecycle.py`; `spectrum_systems/modules/prompt_queue/post_execution_policy.py`; `contracts/schemas/judgment_policy_lifecycle_record.schema.json`; `contracts/schemas/next_step_decision_policy.schema.json`; tests `tests/test_prompt_queue_post_execution_policy.py`, `tests/test_next_step_decision_policy.py` | Decide → Enforce | Classification → Validation | Eliminates side-channel judgment records that do not alter decisions. | CL-03 | Decision artifacts show required judgment lifecycle references; missing refs fail closed across queue/runtime decision seams. |
| CL-05 | Longitudinal Calibration & Revoke Hooks | OBL-AIDUR-LEARNING-PREVENTION-CLOSURE; OBL-AIDUR-MEASURABLE-PROMOTION-ROLLOUT | Delayed outcomes must update calibration and permit freeze/revoke when prevention efficacy decays. | `spectrum_systems/modules/runtime/policy_backtesting.py`; `spectrum_systems/modules/governance/policy_backtest_accuracy.py`; `contracts/schemas/policy_backtest_result.schema.json`; tests `tests/test_policy_backtesting.py`, `tests/test_policy_backtest_accuracy.py` | Observe → Learn → Decide | Validation → Prevention | Required to prove recurrence reduction over time before scale-up. | CL-04 | Calibration artifacts demonstrably influence lifecycle state transitions; failing efficacy triggers freeze/revoke decisions. |
| NX-01 | Universal Schema-Consumption Authority Gate | OBL-AIDUR-SCHEMA-BEFORE-CONSUME | Single ingress/egress contract-runtime gate blocks all downstream consumption on schema absence/failure. | `spectrum_systems/modules/runtime/contract_runtime.py`; `contracts/schemas/artifact_envelope.schema.json`; target integration seams in `spectrum_systems/modules/runtime/pqx_sequence_runner.py`; tests `tests/test_contract_runtime_enforcement.py`, `tests/test_pqx_sequence_runner.py` | Enforce | Validation | Closes distributed local schema checks into one dominant trust spine. | CL-05 | All dominant-path consumption calls route through authority gate; bypass attempts fail tests. |
| NX-02 | Unified Promotion Authority (Lineage + Eval + Policy) | OBL-AIDUR-LINEAGE-BEFORE-PROMOTION; OBL-AIDUR-EVAL-POLICY-BEFORE-PROMOTION | Promotion decision is singular and fail-closed on missing lineage/eval/policy evidence. | `spectrum_systems/modules/governance/done_certification.py`; `spectrum_systems/modules/governance/promotion_gate_attack.py`; `contracts/schemas/done_certification_record.schema.json`; tests `tests/test_done_certification.py`, `tests/test_promotion_gate_attack.py`, `tests/test_control_loop_certification.py` | Decide → Enforce | Validation | Removes multi-path promotion ambiguity prior to grouped execution. | NX-01 | One promotion gate artifact authority exists; test matrix proves deny on missing lineage/eval/policy combinations. |
| NX-03 | 3-Slice Dominant Spine Proof Pack | OBL-AIDUR-SCHEMA-BEFORE-CONSUME; OBL-AIDUR-LINEAGE-BEFORE-PROMOTION; OBL-AIDUR-EVAL-POLICY-BEFORE-PROMOTION; OBL-AIDUR-LEARNING-PREVENTION-CLOSURE | Certification proof for deterministic 1→2→3 sequential slices with recurrence-prevention effect evidence. | `spectrum_systems/modules/runtime/pqx_sequence_runner.py`; `spectrum_systems/modules/prompt_queue/queue_audit_bundle.py`; `contracts/schemas/control_loop_certification_pack.schema.json`; `contracts/schemas/prompt_queue_sequence_run.schema.json`; tests `tests/test_pqx_sequence_runner.py`, `tests/test_control_loop_certification.py`, `tests/test_prompt_queue_audit_bundle.py` | Observe → Interpret → Decide → Enforce | Validation → Prevention | Mandatory hard proof before `NX-04+`. | NX-02 | Certification pack includes pass evidence for schema, lineage, eval-policy, recurrence-prevention gates across 3 sequential slices; manual override not required. |
| NX-04..NX-12 | Conditional Grouped Execution Hardening | OBL-AIDUR-SCHEMA-BEFORE-CONSUME; OBL-AIDUR-EVAL-POLICY-BEFORE-PROMOTION; OBL-AIDUR-LEARNING-PREVENTION-CLOSURE | Apply proven single-spine enforcement to grouped review/repair/reentry without introducing alternate trust paths. | `spectrum_systems/modules/prompt_queue/*`; grouped schemas under `contracts/schemas/prompt_queue_*.schema.json`; existing grouped tests under `tests/test_prompt_queue_*` | Decide → Enforce → Learn | Root Cause → Fix → Prevention | Expansion only after proof; closes partiality at grouped scale. | NX-03 hard gate pass | No grouped transition path can bypass NX-01/NX-02 authorities; grouped certification results remain fail-closed. |
| NX-13..NX-21 | Certification + Source Hardening | OBL-AIDUR-LINEAGE-BEFORE-PROMOTION; OBL-AIDUR-MEASURABLE-PROMOTION-ROLLOUT; OBL-AIDUR-LEARNING-PREVENTION-CLOSURE | Extend certification lineage/proof and source-obligation coverage so promotion claims are machine-verifiable at system scope. | Certification/audit seams (`spectrum_systems/modules/governance/done_certification.py`, `spectrum_systems/modules/prompt_queue/queue_audit_bundle.py`), source indexes in `docs/source_indexes/` and validation tests | Decide → Enforce | Validation → Prevention | Needed to preserve trust under broader operational scope. | NX-04..NX-12 complete | Certification and source-coverage bundles prove no obligation drift and no lineage/promotion bypass. |
| NX-22..NX-24 | AI Execution Expansion (Last) | OBL-AIDUR-MEASURABLE-PROMOTION-ROLLOUT; OBL-AIDUR-LEARNING-PREVENTION-CLOSURE | Adapter/runtime expansion remains gated by measured calibration/prevention efficacy from earlier phases. | `spectrum_systems/modules/runtime/model_adapter.py`; routing/policy seams; adapter contracts in `contracts/schemas/ai_model_request.schema.json` + `ai_model_response.schema.json`; tests `tests/test_model_adapter.py`, routing/policy suites | Observe → Interpret → Decide → Enforce | Validation → Prevention | Prevents capability expansion without demonstrated control-loop efficacy. | NX-13..NX-21 + hard-gate evidence | AI expansion blocked unless bounded-window recurrence and calibration metrics remain within governed thresholds. |

## 7) Control Loop Closure Gate Definition (CL-01..CL-05)

### Required Artifacts
- Failure classification artifact with canonical failure class.
- Linked eval-case artifact and policy reference/update artifact.
- Budget/readiness status artifact and escalation action/outcome record.
- Recurrence-prevention closure artifact (fixture/policy-tightening linkage).
- Judgment lifecycle record consumed by decision artifacts.
- Longitudinal calibration artifact with freeze/revoke eligibility signal.

### Required Evidence
- Deterministic test evidence that missing artifacts at each stage fail closed.
- 3-slice replay/certification evidence showing failure class recurrence is reduced by enforced prevention actions.
- Promotion-eligibility evidence showing deny decisions when lineage/eval/policy/budget proofs are incomplete.

### Pass/Fail Semantics
- **Pass:** all CL artifacts exist, validate, and are consumed by decision/enforcement seams with no bypass path in dominant spine.
- **Fail:** any missing artifact, unconsumed authority artifact, or bypass-capable transition path causes gate failure.

### Transition Blocking Behavior
- While gate is failing, progression is restricted to CL remediation + NX-01..NX-03 hardening work only.
- `NX-04+` grouped expansion, certification broadening, and AI execution expansion are blocked.

## 8) Execution Phases

### Phase A — Control Loop Closure Gate (CL-01..CL-05)
Objective: convert learning from advisory output into mandatory progression/promotion authority.

### Phase B — Dominant Trust Spine (NX-01..NX-03)
Objective: enforce one schema+promotion authority path and prove 3-slice deterministic closure.

### Phase C — Conditional Expansion (NX-04..NX-12)
Objective: apply proven spine to grouped PQX/review/repair without parallel trust paths.

### Phase D — Certification + Source Hardening (NX-13..NX-21)
Objective: system-level certification and source-obligation drift resistance.

### Phase E — AI Execution (NX-22..NX-24)
Objective: bounded adapter/runtime expansion only after control-loop efficacy proof.

## 9) Next Hard Gate
**Gate:** Control Loop Closure Certification Gate for NX progression.

**Measurable pass condition:**
- A governed certification pack demonstrates successful fail-closed enforcement and recurrence-prevention closure across **3 sequential slices**,
- with zero promotion decisions accepted when lineage/eval/policy/budget evidence is missing,
- and with calibration evidence showing prevention efficacy is being consumed by lifecycle decisions.

## 10) Risks
- Existing distributed seams may reintroduce bypasses if integration hardening is incomplete.
- Grouped PQX expansion may accidentally create alternate transition paths unless NX-01/NX-02 are reused as mandatory shared gates.
- Certification claims may overstate closure if recurrence-prevention efficacy is not measured longitudinally.
- Source index drift could weaken obligation traceability if source inventory/index tests are not kept mandatory.

## 11) Notes on Anything Not Fully Grounded
- RE-02 marks some batch/sequence readiness conclusions as partly inferred; this roadmap uses those only as prioritization context, not as sole authority.
- No new obligations were inferred beyond `obligation_index.json`; all roadmap steps map exclusively to listed obligations.
- This document intentionally leaves compatibility mirror files and legacy step IDs untouched to preserve parser/runtime expectations.

## Validation Checklist (for this candidate)
- [x] Every roadmap step maps to one or more obligation IDs from `obligation_index.json`.
- [x] Scope is restricted to RE-02 partial obligations (no covered-obligation-first prioritization).
- [x] Execution enforces one dominant trust spine: `CL-01..CL-05` → `NX-01..NX-03` → proof gate → `NX-04+`.
- [x] Control loop closure is explicit: Failure → Policy → Control → Enforcement → Prevention.
- [x] Expansion is proof-gated (no grouped execution before proof).
- [x] Compatibility mirror and legacy step IDs are untouched.
