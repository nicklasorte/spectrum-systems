# AI Operating Substrate Gap Analysis

## Scope
Comparison baseline:
- `docs/architecture/ai_operating_substrate_and_artifact_intelligence.md`

Repo reality checked against:
- contracts in `contracts/schemas/`
- standards pinning in `contracts/standards-manifest.json`
- runtime modules in `spectrum_systems/modules/runtime/`
- authoritative roadmap `docs/roadmaps/system_roadmap.md`

## 1) Existing components already present
- Canonical model boundary contracts exist: `ai_model_request`, `ai_model_response`.
- Prompt lifecycle anchor exists via `prompt_registry_entry` schema and runtime docs.
- Routing artifact exists as `routing_decision` and is referenced in runtime policy docs.
- Context admission artifact exists as `context_admission_decision`.
- Eval registry baseline artifact exists as `eval_registry_snapshot`.
- Judgment reuse primitives exist (`judgment_application_record`, `judgment_record`, `judgment_outcome_label`).
- Override governance primitives exist (`hitl_override_decision`, `evaluation_override_authorization`).
- Foundation-chain contracts for eval/control/enforcement/replay/trace/certification exist (`eval_result`, `eval_summary`, `evaluation_control_decision`, `evaluation_enforcement_action`, `replay_result`, `trace`, `done_certification_record`).

## 2) Partial components / weak seams
- Prompt governance is present but task-level lifecycle governance appears implicit; no canonical `task_registry_entry` artifact found.
- Routing decision artifact exists, but substrate target artifact name (`routing_decision_record`) and minimal required reason-code/alternative-set semantics are not standardized as a dedicated contract.
- Context admission exists, but substrate-level source-admission lineage contract (`context_source_admission_record`) is absent as a dedicated artifact.
- Eval registry exists as snapshot artifact, but per-entry governance artifact (`eval_registry_entry`) is not standardized.
- Judgment artifacts exist, but explicit reuse efficacy reporting is not codified as a required derived artifact family.
- Golden-path control-chain seams appear distributed across multiple modules/contracts and remain vulnerable to bypass if all governed runtime entrypoints do not hard-require the same chain.

## 3) Missing must-add components
- Task lifecycle governance contract and runtime enforcement seam (`task_registry_entry` equivalent) are missing.
- Dedicated `routing_decision_record` contract (or authoritative alias/migration policy) is missing.
- Dedicated `context_source_admission_record` contract (or authoritative alias/migration policy) is missing.
- Dedicated `eval_registry_entry` contract is missing.
- Derived intelligence contracts for hotspot reporting are missing:
  - `override_hotspot_report`
  - `evidence_gap_hotspot_report`

## 4) Missing should-have components
- Comparative route/model tournament intelligence artifacts.
- Dynamic policy tuning recommendation artifacts grounded in derived intelligence outputs.
- Artifact-intelligence lineage query acceleration or index materialization artifacts.
- Proactive anomaly detection outputs over cross-run artifact streams.

## 5) Missing artifact families
- **Task lifecycle artifacts** (registry, admission, promotion, revocation) as first-class contracts.
- **Derived intelligence report artifacts** for recurring override/evidence deficits.
- **Substrate-specific decision audit family** aligned to new canonical naming (`*_record`) for routing/context admission/eval entry.

## 6) Missing derived artifact intelligence jobs
- No governed scheduled/batch job artifact family found for override hotspot aggregation.
- No governed scheduled/batch job artifact family found for evidence gap hotspot aggregation.
- No documented consumption seam from derived hotspots into roadmap prioritization artifacts.

## 7) Hard gates that should block broader expansion
Broader AI expansion should be blocked until:
1. must-add substrate contracts are present for task lifecycle, routing decision record parity, context source admission record parity, and eval registry entry,
2. adapter-bound governance proves no bypass path for governed model calls,
3. at least one derived artifact-intelligence job is operational and consumed by planning/control,
4. MVP substrate slice golden path emits request/response + routing + context admission + eval registry linkage + derived report lineage.

## 8) Recommended MVP slice to build first
Narrow first wave:
1. Contract and standards-manifest additions for:
   - `task_registry_entry`
   - `routing_decision_record` (alias/migration from `routing_decision` allowed)
   - `context_source_admission_record` (alias/migration from `context_admission_decision` allowed)
   - `eval_registry_entry` (complements `eval_registry_snapshot`)
2. Runtime wiring to emit those artifacts on governed golden path.
3. One eval slice family linkage proving `eval_registry_entry` is consumed by control gating.
4. One derived intelligence job and artifact (`override_hotspot_report` preferred) with deterministic input lineage.
5. Roadmap/controller consumption seam that uses hotspot output as explicit prioritization signal.

This MVP is dependency-valid, governance-first, and avoids broad autonomy or taxonomy overbuild.

## Golden Path Buildability Status
**PARTIALLY BUILDABLE**

### Already implemented seams
- Artifact creation and schema surfaces are present for core foundation chain artifacts (`ai_model_request`, `ai_model_response`, `eval_result`, `eval_summary`, `evaluation_control_decision`, `evaluation_enforcement_action`, `replay_result`, `trace`, `done_certification_record`).
- Deterministic routing/context/eval/control concepts are present in existing contracts and runtime docs (`routing_decision`, `context_admission_decision`, `eval_registry_snapshot`, roadmap rows for context gate and adapter boundary).
- Replay and trace contracts exist and are referenced as governed requirements in roadmap and strategy docs.

### Missing seams
- Substrate-required contracts are missing: `task_registry_entry`, `routing_decision_record`, `context_source_admission_record`, `eval_registry_entry`.
- Derived artifact-intelligence job output contracts are missing: `override_hotspot_report`, `evidence_gap_hotspot_report`.
- No single authoritative MVP substrate golden-path implementation artifact proving end-to-end execution from request through certification with the new substrate artifact set.

### Bypassable or weak seams
- Current naming/contract mismatch between existing artifacts (`routing_decision`, `context_admission_decision`, `eval_registry_snapshot`) and required substrate artifacts (`*_record`, `eval_registry_entry`) creates ambiguous enforcement seams.
- Task lifecycle governance is prompt-anchored but lacks explicit task contract hard-binding, allowing potential governance drift.
- Derived intelligence is not yet mandatory in planning/control loop, weakening recurrence-prevention leverage.

### Must be fixed before further expansion
1. Add and wire missing must-add substrate contracts.
2. Enforce non-bypassable task→prompt→request lineage.
3. Hard-bind eval registry entry coverage to execution control gates.
4. Add one derived intelligence job/report and require its consumption in roadmap/control prioritization.
5. Demonstrate full MVP golden-path run artifact bundle with replay + trace + certification linkage.

## Expansion Decision
**EXPANSION BLOCKED**

Expansion is blocked because the current slice is only partially buildable and still has missing must-add substrate contracts, weak/bypassable seams, and absent derived artifact intelligence jobs. Roadmap sequencing must prioritize substrate stabilization and hardening before any broader AI expansion (workflow breadth, model breadth, artifact-family breadth, or autonomy increase).
