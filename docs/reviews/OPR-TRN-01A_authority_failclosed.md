# OPR-TRN-01A — Authority and Fail-Closed Review

## Scope
- `spectrum_systems/modules/transcript_hardening.py` — bounded transcript-domain transform seam
- `spectrum_systems/modules/runtime/downstream_product_substrate.py` — TRN-01 full pipeline (ingestion, extraction, eval, control, certification)
- `working_paper_generator/transcript_parser.py` — line-based transcript parser for WPG
- `spectrum_systems/modules/runtime/review_parsing_engine.py` — review signal artifact parsing
- `spectrum_systems/modules/prompt_queue/review_parser.py` — prompt queue review parsing seam
- `spectrum_systems/modules/review_promotion_gate.py` — promotion gate integration
- `spectrum_systems/modules/runtime/cde_decision_flow.py` — CDE bounded decision foundation
- `spectrum_systems/modules/runtime/trace_engine.py` — trace and correlation layer
- `spectrum_systems/modules/wpg/certification.py` — WPG lifecycle certification
- `contracts/schemas/transcript_hardening_run.schema.json` — transcript hardening run contract
- `contracts/schemas/normalized_transcript_artifact.schema.json`
- `contracts/schemas/transcript_chunk_artifact.schema.json`
- `contracts/schemas/transcript_fact_artifact.schema.json`
- `schemas/data-lake/transcript-output.json` — data-lake transcript issue schema
- `tests/test_transcript_hardening.py` — transcript hardening tests
- `tests/test_downstream_product_substrate.py` — substrate tests
- `docs/architecture/transcript_processing_hardening.md` — TRN-01 architecture spec
- `docs/architecture/system_registry.md` — canonical system ownership
- `docs/reviews/TRN-01_delivery_report.md` — TRN-01 delivery report

## Executive Verdict

**NOT READY FOR NEXT PHASE**

Two S3 authority boundary violations in `downstream_product_substrate.py` create shadow decision and certification paths that directly contradict the canonical ownership model defined in `system_registry.md`. These must be resolved before the transcript-processing subsystem can advance.

## Highest-Risk Findings

1. **S3**: `control_decision()` in downstream_product_substrate.py emits CDE-owned decision authority and SEL-owned enforcement authority from inside the transcript substrate.
2. **S3**: `certify_product_readiness()` in downstream_product_substrate.py emits a shadow certification artifact with `certification_status` outside the governed certification path.
3. **S2**: Handoff signals from `transcript_hardening.py` omit `replay_hash` for control, judgment, and certification downstream consumers — breaking replay-verified fail-closed continuity.

## Findings

### Finding: `control_decision()` issues CDE/SEL authority from transcript substrate
- Category: authority
- Severity: S3
- Confidence: high
- Repo Evidence:
  - `spectrum_systems/modules/runtime/downstream_product_substrate.py:505-515` — function `control_decision()` emits `"decision": "allow"|"block"` and `"enforcement_action": "promote"|"freeze"`
  - `docs/architecture/system_registry.md` — CDE definition: "Sole authoritative owner for closure-state and readiness-to-close decisions"; SEL definition: "Enforces hard gates and fail-closed actions"
  - `docs/architecture/system_registry.md` Anti-Duplication Table: "TPA emits closure decisions → Why invalid: Trust policy gating cannot decide closure lock state → Canonical owner: CDE"
  - `tests/test_downstream_product_substrate.py:138` — test calls `control_decision()` directly, treating it as authorized
- Failure Mode: A transcript processing module emits fields (`decision`, `enforcement_action`) that use the same vocabulary as authoritative CDE/SEL outputs. Any downstream consumer that treats this output as a decision artifact bypasses CDE and SEL entirely. The function has no schema contract, no `validate_artifact()` call, and no trace linkage — making it invisible to governance enforcement.
- Production Manifestation: A transcript run produces a `control_decision` dict with `"decision": "allow"` and `"enforcement_action": "promote"`. A downstream orchestration path consumes it as an authority artifact. Promotion proceeds without CDE closure decision or SEL enforcement. The governed audit trail shows no CDE artifact for this decision.
- Why It Matters: The entire governed runtime depends on CDE being the sole closure decision authority and SEL being the sole enforcement authority. A shadow decision function in the transcript substrate creates an untraced, unvalidated authority leak. The system_registry explicitly prohibits this pattern.
- Concrete Fix: (1) Remove `decision` and `enforcement_action` fields from `control_decision()` output. (2) Rename the function to `build_transcript_control_input()` and have it emit a `transcript_control_input_signal` artifact type (input-only, matching the handoff pattern in `transcript_hardening.py`). (3) Add `validate_artifact()` against a schema that explicitly forbids `decision`, `enforcement_action`, `promote`, and `allow` in its output. (4) Add a `non_authority_assertions` field mirroring the CDE pattern in `cde_decision_flow.py`.
- Required Tests / Evals:
  - Test that `build_transcript_control_input()` output contains no authority-vocabulary fields (`decision`, `enforcement_action`, `promote`, `allow`, `block`, `freeze`).
  - Test that the output validates against a governed schema with `additionalProperties: false`.
  - Governance eval: `system_registry_guard.py` should flag any module outside CDE/SEL that emits `decision` or `enforcement_action` fields.

### Finding: `certify_product_readiness()` emits shadow certification artifact
- Category: gate_bypass
- Severity: S3
- Confidence: high
- Repo Evidence:
  - `spectrum_systems/modules/runtime/downstream_product_substrate.py:518-543` — function `certify_product_readiness()` emits `artifact_type: "product_readiness_artifact"` with `certification_status: "certified"|"blocked"`
  - `docs/architecture/system_registry.md` — CDE is the only system allowed to emit `closure_decision_artifact`, `promotion_readiness_decision`, `readiness_to_close`
  - `docs/architecture/transcript_processing_hardening.md:9` — "Certification gate blocks promotion on missing artifact/eval/trace/replay prerequisites" — but this function bypasses that gate
  - `tests/test_downstream_product_substrate.py:139-148` — test calls `certify_product_readiness()` directly
- Failure Mode: The function emits a structured artifact with `artifact_type` and `certification_status` that looks like a governed certification output. It has no `validate_artifact()` call, no schema contract in `contracts/schemas/`, and no trace linkage. Any consumer that checks `certification_status == "certified"` will treat this as a valid certification without CDE involvement.
- Production Manifestation: A transcript pipeline run calls `certify_product_readiness()` and gets `certification_status: "certified"`. An orchestration layer checks this field and triggers promotion. The governed certification gate (which requires CDE closure decision, eval completeness, replay verification, and trace completeness) is never invoked.
- Why It Matters: The CLAUDE.md hard rule states "No promotion without certification." The system_registry states CDE is the sole certification authority. This function creates a parallel certification path that is invisible to CDE, SEL, and the governed audit trail.
- Concrete Fix: (1) Rename to `build_transcript_certification_input()`. (2) Change `certification_status` to `readiness_assessment` with values `"ready_for_certification"|"not_ready"` (preparatory vocabulary, not authority vocabulary). (3) Add `non_authority_assertions: ["preparatory_only", "not_certification_authority", "requires_cde_closure_decision"]`. (4) Create a contract schema with `additionalProperties: false` that forbids `certification_status`, `certified`, and `promoted`. (5) Wire `validate_artifact()`.
- Required Tests / Evals:
  - Test that output never contains `certification_status`, `certified`, or `promoted`.
  - Test that output validates against a new preparatory-only schema.
  - Eval: any artifact with `certification_status` field MUST come from CDE — add to `system_registry_guard.py` enforcement checks.

### Finding: Handoff signals omit replay_hash for control/judgment/certification consumers
- Category: fail_closed
- Severity: S2
- Confidence: high
- Repo Evidence:
  - `spectrum_systems/modules/transcript_hardening.py:114-141` — `build_owner_handoffs()` only includes `replay_hash` in `eval_input`; `control_input`, `judgment_input`, `certification_input` lack it
  - `contracts/schemas/transcript_hardening_run.schema.json:143-153` — `handoff_signal` def has `replay_hash` as optional (not required)
  - `docs/architecture/transcript_processing_hardening.md:8` — "Replay integrity is checked before control and certification decisions"
- Failure Mode: Downstream control, judgment, and certification consumers receive handoff signals without replay_hash. They cannot independently verify that the transcript they are operating on matches the replay-verified state. A tampered or stale transcript could enter the control/certification path without detection.
- Production Manifestation: Transcript normalization produces a replay_hash. The eval layer receives it and can verify replay integrity. The control layer receives a handoff signal WITHOUT replay_hash, makes a control decision on a transcript whose integrity it cannot verify. Certification proceeds on unverified transcript state.
- Why It Matters: The architecture spec explicitly requires "Replay integrity is checked before control and certification decisions." Without replay_hash in the handoff signals, there is no mechanism for downstream consumers to enforce this requirement. This breaks the fail-closed chain at the handoff boundary.
- Concrete Fix: (1) Add `replay_hash` to all four handoff signals in `build_owner_handoffs()`. (2) Change the `handoff_signal` schema def to make `replay_hash` required (move it into the `required` array). (3) Add a test that verifies all handoff signals carry `replay_hash` and it matches the normalization replay_hash.
- Required Tests / Evals:
  - Test that all four handoff signals (`eval_input`, `control_input`, `judgment_input`, `certification_input`) include `replay_hash`.
  - Test that `replay_hash` values match `normalization.replay_hash`.
  - Schema validation test: handoff_signal with missing replay_hash MUST fail validation.

### Finding: `build_transcript_observations` is an ungoverned classification layer with no trace or eval
- Category: ownership
- Severity: S2
- Confidence: medium
- Repo Evidence:
  - `spectrum_systems/modules/transcript_hardening.py:84-111` — keyword-based classification into topics/claims/actions/ambiguities using hardcoded token lists
  - `spectrum_systems/modules/transcript_hardening.py:96-103` — classification tokens: `("topic", "agenda", "focus")`, `("claim", "because", "indicates", "shows")`, `("action", "will", "follow up", "todo")`, `"?"` for ambiguities
  - `tests/test_transcript_hardening.py` — no test verifies classification accuracy, recall, or boundary behavior
  - `docs/architecture/system_registry.md` — RIL owns `review_interpretation`, `evaluation_interpretation`; JDX owns judgment artifacts between interpreted evidence and control decisions
- Failure Mode: The keyword matching silently classifies transcript segments into semantic categories (topics, claims, actions, ambiguities) without confidence scores, without trace records, and without eval coverage. A segment containing "because" is classified as a "claim" regardless of context. A genuine claim that lacks these keywords is silently missed. These classifications flow into `handoff_artifacts` and become the basis for downstream eval/control/judgment/certification decisions.
- Production Manifestation: A transcript segment "The funding will not continue" is tagged as an "action" (contains "will") and not as a "claim" (lacks "because"/"indicates"/"shows"). Downstream consumers receive an action signal where they should have received a claim signal. The error is invisible because no eval checks classification quality.
- Why It Matters: Classification is a form of interpretation. The system_registry assigns interpretation to RIL, not to the transcript hardening seam. While the architecture note says transcript hardening "prepares deterministic transcript artifacts and handoff input signals only," the observation builder is doing semantic interpretation that should carry confidence, trace, and eval coverage.
- Concrete Fix: (1) Add a `classification_confidence` field to each observation row. (2) Add a trace event record for each classification pass via `trace_engine.record_event()`. (3) Add eval coverage for classification precision/recall against golden cases in `data/golden_cases/`. (4) Document that this is a preparatory-only classification that requires RIL interpretation downstream.
- Required Tests / Evals:
  - Golden-case eval: classification output for `data/golden_cases/case_001/` and `case_002/` against expected topic/claim/action/ambiguity sets.
  - Adversarial eval: classification output for `data/adversarial_cases/` to verify fail-closed on degenerate inputs.
  - Trace integration test: verify trace events are recorded for each classification pass.

### Finding: No trace_id validation against trace engine in transcript processing modules
- Category: fail_closed
- Severity: S2
- Confidence: high
- Repo Evidence:
  - `spectrum_systems/modules/transcript_hardening.py:144-146` — `run_transcript_hardening()` accepts `trace_id` as a bare string with no validation
  - `spectrum_systems/modules/runtime/downstream_product_substrate.py:131-142` — `normalize_docx_transcript()` accepts `trace_id` as a bare string; checks `not trace_id` (empty string) but not trace engine validity
  - `spectrum_systems/modules/runtime/trace_engine.py:441-487` — `validate_trace_context()` exists and is designed for exactly this purpose, but is never called by either transcript module
  - Grep for `validate_trace_context` and `trace_engine` in both files: zero matches
- Failure Mode: Both transcript processing modules accept any non-empty string as `trace_id`. They produce artifacts carrying this trace_id without verifying it exists in the trace store. Downstream consumers that check trace integrity will find no matching trace, or the artifact will carry a fabricated trace_id that passes string-format checks but has no actual trace backing.
- Production Manifestation: A transcript hardening run is invoked with `trace_id="arbitrary-string"`. The artifact is produced with this trace_id. A downstream trace audit finds no matching trace in the trace store. The artifact's lineage cannot be reconstructed. If the artifact passes other checks, promotion could proceed with broken traceability.
- Why It Matters: The trace engine docstring states "Fail closed: missing trace_id, missing span context, or malformed trace structures block execution rather than silently passing." But this fail-closed guarantee is only enforceable if callers actually invoke `validate_trace_context()`. The transcript modules bypass this check entirely.
- Concrete Fix: (1) At the top of `run_transcript_hardening()`, call `validate_trace_context(trace_id)` and raise `TranscriptHardeningError` if it returns errors. (2) At the top of `normalize_docx_transcript()`, call `validate_trace_context(trace_id)` and raise `DownstreamFailClosedError` if it returns errors. (3) Start a span in each function for trace completeness.
- Required Tests / Evals:
  - Test that `run_transcript_hardening()` with an invalid/missing trace_id raises `TranscriptHardeningError`.
  - Test that `normalize_docx_transcript()` with an invalid trace_id raises `DownstreamFailClosedError`.
  - Test that a valid trace_id produces a span in the trace store after processing.

### Finding: Transcript hardening run schema has no governed failure state
- Category: fail_closed
- Severity: S1
- Confidence: medium
- Repo Evidence:
  - `contracts/schemas/transcript_hardening_run.schema.json:112` — `"processing_status": { "type": "string", "enum": ["processed"] }` — only success state
  - `spectrum_systems/modules/runtime/downstream_product_substrate.py:117-128` — `build_failure_artifact()` exists for the ingestion stage (emits `transcript_ingest_failure_artifact`)
  - `spectrum_systems/modules/transcript_hardening.py` — no equivalent failure artifact; errors raise exceptions with no governed artifact
- Failure Mode: When transcript hardening fails, an exception is raised but no governed failure artifact is emitted. A caller that catches the exception has no machine-readable record of the failure. The governed audit trail has a gap — neither a success artifact nor a failure artifact exists for the run.
- Production Manifestation: Transcript hardening fails on malformed input. The exception is caught by an orchestration layer. No artifact is written. The trace has no record of the attempt. A later audit cannot distinguish "never attempted" from "attempted and failed."
- Why It Matters: The downstream substrate has `build_failure_artifact()` for exactly this scenario at the ingestion stage. The hardening stage lacks an equivalent, creating an asymmetry in failure observability. This is a minor weakness because exceptions do block forward progress (fail-closed behavior is maintained), but the governed record is incomplete.
- Concrete Fix: (1) Create a `transcript_hardening_failure.schema.json` with required fields: `artifact_type`, `trace_id`, `run_id`, `failure_reason`, `failed_at`, `processing_status: "failed"`. (2) Add a `build_hardening_failure_artifact()` function. (3) Document that callers MUST emit either a success or failure artifact.
- Required Tests / Evals:
  - Test that `build_hardening_failure_artifact()` produces a schema-valid artifact.
  - Test that the failure artifact carries the correct trace_id and failure_reason.

## Coverage Gaps

1. **No classification accuracy eval** — `build_transcript_observations` has zero eval coverage for precision/recall of keyword-based classification against golden or adversarial cases.
2. **No trace integration test for transcript hardening** — neither transcript module creates spans or records events in the trace engine.
3. **No authority vocabulary enforcement test** — no test verifies that transcript processing outputs are free of authority-vocabulary fields (`decision`, `enforcement_action`, `certification_status`, `promote`, `allow`).
4. **No cross-module handoff validation test** — no test verifies that handoff signals from `transcript_hardening.py` are consumable by the actual downstream eval/control/judgment/certification modules.
5. **No replay_hash propagation test** — no test verifies that replay_hash from normalization reaches all four handoff signals.

## Recommended Fix Order

1. **S3 — `control_decision()` authority violation** — highest blast radius; any consumer treating its output as authority bypasses CDE/SEL entirely.
2. **S3 — `certify_product_readiness()` shadow certification** — creates a parallel promotion path that is invisible to the governed audit trail.
3. **S2 — Handoff replay_hash gap** — breaks the replay-verified fail-closed chain at the most critical boundary (transcript → control/certification).
4. **S2 — Trace_id validation** — without this, all transcript artifacts have unverified trace linkage.
5. **S2 — Observation classification governance** — requires eval coverage and trace records to close the interpretation gap.
6. **S1 — Failure artifact schema** — minor; exceptions maintain fail-closed behavior but governed record is incomplete.

## Hard Gate Recommendation

**BLOCK promotion of the transcript-processing subsystem until:**
1. `control_decision()` and `certify_product_readiness()` are refactored to emit preparatory-only artifacts with non-authority vocabulary and governed schema validation.
2. All four handoff signals carry `replay_hash` as a required field.
3. `validate_trace_context()` is called at the entry point of both transcript processing modules.
4. Authority vocabulary enforcement tests are added and passing.
