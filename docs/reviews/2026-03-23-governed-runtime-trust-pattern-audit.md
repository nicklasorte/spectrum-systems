# Governed Runtime Trust-Pattern Audit (BAE/BAF/BAG/BAH/BAJ + Control Executor/Validator)

- **Date:** 2026-03-23
- **Decision:** **FAIL**

## Scope Reviewed
- `spectrum_systems/modules/runtime/control_loop.py`
- `spectrum_systems/modules/runtime/evaluation_control.py`
- `spectrum_systems/modules/runtime/enforcement_engine.py`
- `spectrum_systems/modules/runtime/replay_engine.py`
- `spectrum_systems/modules/runtime/drift_detection_engine.py`
- `spectrum_systems/modules/runtime/validator_engine.py`
- `spectrum_systems/modules/runtime/control_executor.py`
- `spectrum_systems/modules/runtime/replay_governance.py`
- `spectrum_systems/modules/runtime/run_bundle_validator.py`
- `contracts/schemas/evaluation_control_decision.schema.json`
- `contracts/schemas/enforcement_result.schema.json`
- `contracts/schemas/replay_result.schema.json`
- `contracts/schemas/drift_result.schema.json`
- `contracts/schemas/control_execution_result.schema.json`
- `contracts/schemas/validator_execution_result.schema.json`
- `tests/test_evaluation_control.py`
- `tests/test_enforcement_engine.py`
- `tests/test_replay_engine.py`
- `tests/test_drift_detection_engine.py`
- `tests/test_validator_engine.py`
- `tests/test_control_executor.py`
- `docs/reviews/2026-03-23-baj-provenance-hardening-surgical-review.md`
- `docs/reviews/bah-drift-detection-surgical-review-2026-03-23.md`
- `docs/reviews/2026-03-22-replay-engine-review.md`
- `docs/review-actions/2026-03-23-baj-provenance-hardening-surgical-review-actions.md`

## Executive Summary
The governed runtime/control-loop slices are directionally stronger than earlier checkpoints (more schema checks, explicit fail-closed blocks, better canonical path assertions), but repeated trust-breaking patterns remain in core boundaries:

1. **Non-deterministic identity/timestamps in governed artifacts that are later used as replay/comparison linkage.**
2. **Dual-shape/dual-contract acceptance in replay and validator surfaces.**
3. **Correlation key integrity still permits placeholder/default linkage values in execution artifacts.**
4. **Silent downgrade/fallback still exists in runtime-adjacent validator paths (`run_bundle_validator`).**

These are advancement blockers for roadmap stages that depend on replay trust, provenance hardening, and observability integrity.

## Critical Findings (ranked)

### P1 — Validator execution emits multiple semantic shapes and can bypass its own contract
- **Severity:** P1
- **File + function:** `spectrum_systems/modules/runtime/validator_engine.py` → `run_validators`
- **Exact issue:** The malformed-trace early return emits `trace_id` / `parent_span_id` fields and returns immediately without governed schema validation, while normal-path payloads omit those fields and go through schema checks.
- **Why it matters to system trust:** A governed artifact type should not have branch-dependent shapes. This weakens deterministic downstream processing and breaks strict contract trust.
- **Realistic failure scenario:** A consumer expecting strict `validator_execution_result` contract receives malformed-trace branch output that diverges from schema and from normal shape, causing either parser branching or dropped evidence.
- **Minimal fix direction:** Unify to one canonical schema-valid shape for all branches; include/require correlation fields in contract (or remove from all outputs) and always run final schema validation before return.

### P1 — Replay validation still supports canonical + legacy dual acceptance in same module surface
- **Severity:** P1
- **File + function:** `spectrum_systems/modules/runtime/replay_engine.py` → `validate_replay_result`
- **Exact issue:** If primary schema validation fails and payload is deemed “not governed path,” legacy replay schema is accepted.
- **Why it matters to system trust:** Governed runtime replay should enforce one canonical replay artifact type. Dual acceptance increases ambiguity and allows legacy shapes to continue entering trust-critical pipelines.
- **Realistic failure scenario:** A tool accidentally feeds legacy replay payloads through current runtime interfaces; validation passes unexpectedly and mixed artifact semantics propagate into governance/replay analytics.
- **Minimal fix direction:** Hard-separate legacy validation entrypoint from BAG governed validation; in governed modules enforce canonical-only contract.

### P1 — Non-deterministic IDs/timestamps still leak into governed control/replay linkage surfaces
- **Severity:** P1
- **File + function:**
  - `spectrum_systems/modules/runtime/enforcement_engine.py` → `_new_id`, `_now_iso`, `enforce_control_decision`
  - `spectrum_systems/modules/runtime/control_loop.py` → `_now_iso`, `_evaluate_signal` (`failure_eval_case` branch)
- **Exact issue:** `enforcement_result_id` and timestamps are wall-clock/random generated; failure-eval decision branch also stamps current time. These values are included in replay linkage references.
- **Why it matters to system trust:** Reproducibility and replay trust degrade when core governed artifacts are regenerated with different identities despite semantically identical inputs.
- **Realistic failure scenario:** Same input replay in different runs yields equivalent decisions/actions but different artifact references/timestamps, complicating deterministic audit diffs and cross-run equivalence checks.
- **Minimal fix direction:** Introduce deterministic identity mode (content-addressed or canonical seed-based IDs) for governance-critical references; keep runtime wall-clock data as optional metadata, not identity anchors.

### P2 — Control execution correlation integrity allows placeholder/default artifact linkage
- **Severity:** P2
- **File + function:** `spectrum_systems/modules/runtime/control_executor.py` → `execute_control_signals`, `build_execution_result`
- **Exact issue:** `artifact_id` defaults to `unknown-artifact`; trace/run defaults are synthesized in several blocked/error branches; attached artifact ID for `control_execution_result` reuses source artifact ID.
- **Why it matters to system trust:** Placeholder/default IDs and reused source IDs weaken one-to-one correlation between execution record and emitted artifact, reducing observability integrity.
- **Realistic failure scenario:** Multiple executions against one source artifact attach under same ID, making trace artifact lineage ambiguous and difficult to reconcile during incident replay.
- **Minimal fix direction:** Require explicit non-placeholder correlation keys for governed result emission; use unique execution-result artifact IDs and prevent attachment under source artifact IDs.

### P2 — Run-bundle validation path still uses silent fallback and time-derived decision identity
- **Severity:** P2
- **File + function:** `spectrum_systems/modules/runtime/run_bundle_validator.py` → `_resolve_trace_id`, `_decision_id`, `build_artifact_validation_decision`
- **Exact issue:** On trace runtime import failure, fallback generates random UUID trace ID; decision ID is hash of `run_id:timestamp` (time-dependent).
- **Why it matters to system trust:** This introduces silent downgrade and non-deterministic identity in a governed validation boundary that feeds replay/control paths.
- **Realistic failure scenario:** Intermittent runtime import issue causes random trace IDs for structurally identical bundles; audit replay cannot deterministically relate validator decisions across environments.
- **Minimal fix direction:** Fail closed when trace runtime unavailable; derive decision identity from canonical manifest/report content only (no wall-clock seed).

### P3 — Replay governance auto-extraction introduces implicit linkage behavior
- **Severity:** P3
- **File + function:** `spectrum_systems/modules/runtime/replay_governance.py` → main governance flow (effective trace/replay run ID extraction)
- **Exact issue:** Missing explicit `trace_id`/`replay_run_id` are auto-extracted from analysis payload.
- **Why it matters to system trust:** Implicit extraction obscures provenance authority and can mask caller-side linkage omissions.
- **Realistic failure scenario:** Upstream caller omits explicit IDs; governance artifact still emits linkage based on embedded analysis values, reducing detection of boundary contract violations.
- **Minimal fix direction:** Require explicit governed correlation keys at boundary; keep extraction only for legacy adapter entrypoints with explicit deprecation fences.

## Repeated Failure Patterns
- **Wall-clock/random identity generation** for governed artifacts expected to support replay reproducibility.
- **Canonical + legacy dual acceptance** in runtime replay validation surfaces.
- **Branch-dependent artifact shape drift** (schema-valid normal path vs alternate blocked-path shapes).
- **Placeholder/default correlation IDs** in fail/error branches rather than hard rejection.
- **Silent fallback** where hard fail-closed is expected for trust boundaries.

## Modules Most at Risk
1. `spectrum_systems/modules/runtime/replay_engine.py`
2. `spectrum_systems/modules/runtime/validator_engine.py`
3. `spectrum_systems/modules/runtime/enforcement_engine.py`
4. `spectrum_systems/modules/runtime/control_executor.py`
5. `spectrum_systems/modules/runtime/run_bundle_validator.py`

## What Is Safe To Build On
- Deterministic drift ID preimage design in `drift_detection_engine` (canonical JSON hash payload).
- Fail-closed rejection of unknown governed artifact types in BAG `run_replay`.
- Canonical BAF action/status mapping constraints (`allow/deny/require_review` ↔ enforcement action enums).
- Explicit test coverage for several canonical-path fail-closed behaviors (unsupported artifact types, malformed inputs, legacy enforcement caller restrictions).

## What Must Be Fixed Before Advancing
1. Canonicalize validator execution artifact shape across all branches and enforce schema on every return path.
2. Remove dual-schema acceptance from governed replay validation surface.
3. Harden deterministic identity strategy for governed control/replay artifacts and references.
4. Enforce strict correlation-key requirements (no `unknown-*` placeholder emissions).
5. Eliminate silent fallback in run-bundle validation trace/linkage path.

## Recommended Fix Order
1. **P1 schema/shape integrity:** `validator_engine.run_validators` unified canonical output contract.
2. **P1 replay contract purity:** canonical-only replay validation in governed BAG paths.
3. **P1 deterministic identity:** enforcement/control decision reference stabilization.
4. **P2 correlation key hardening:** control executor/result artifact linkage strictness.
5. **P2 fallback elimination:** run-bundle validator fail-closed behavior for trace/linkage dependencies.
6. **P3 cleanup:** replay governance explicit-ID boundary enforcement.
