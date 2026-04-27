# CPL-03 — Transcript / Context Eval Gate Red-Team Review

- **Review id:** `RVA-CPL03-EVALGATE-001`
- **Reviewer:** `ARA-CPL03`
- **Reviewed batch:** `BATCH-CPL-03`
- **Review signal:** `revision_recommended` (all S2+ findings closed in-batch — see `CPL-03_fix_actions.json`)
- **Authority boundary:** Non-authority review signal. Canonical routing remains with the appropriate canonical owner. Nothing here is a routing or release-readiness ruling. The eval gate produces evidence only.
- **Date:** 2026-04-27

## Scope

Adversarial review of the CPL-03 transcript_artifact + context_bundle eval gate path:

- `contracts/schemas/transcript_pipeline/eval_summary.schema.json`
- `contracts/schemas/transcript_pipeline/gate_evidence.schema.json`
- `spectrum_systems/modules/transcript_pipeline/eval_gate.py`
- `spectrum_systems/modules/orchestration/pqx_step_harness.py` (consumer-side checks only)
- `spectrum_systems/modules/runtime/artifact_store.py` (consumer-side checks only)

## Attack surface

| Vector | What we tried |
|---|---|
| Forged gate_evidence | Hand-craft a `gate_evidence` with a synthesized `eval_summary_id` that points at no registered `eval_summary`. |
| Replay drift | Tamper `manifest_hash` while keeping segments intact. |
| Lineage forgery | Submit segments whose `source_turn_id` does not match any `speaker_turns` entry. |
| Segment drift | Keep `source_turn_id` matching but tamper `text` / `speaker` / `line_index`. |
| Partial coverage | Submit fewer (or more) segments than turns; silent transcript truncation or duplication. |
| Schema bypass | Drop `eval_summary_id`, drop `eval_results`, drop `gate_status`, add unknown fields on summary or evidence. |
| Indeterminate eval status | Submit an `eval_results` entry whose `status` is outside `{pass, fail}`. |
| Unknown gate_status | Submit a `gate_evidence` whose `gate_status` is outside the four canonical values. |
| PQX bypass | Bypass `run_eval_gate_via_pqx` and call `ArtifactStore.register_artifact` on a hand-crafted summary or evidence. |
| Authority leak | Inspect module text and schema descriptions for forbidden authority vocabulary. |

## Findings (severity ladder S0–S4)

| ID | Severity | Description | Recommendation | Blocking |
|---|---|---|---|---|
| F-001 | S3 | Forged `gate_evidence` with a hand-crafted `eval_summary_id` could pass schema validation and surface a `passed_gate` state without a corresponding `eval_summary` artifact. | Two-step PQX wrapper: `eval_gate_summary` registers the `eval_summary`; `eval_gate_evidence` re-derives the id deterministically and halts on `EVAL_SUMMARY_ID_DRIFT`. | yes |
| F-002 | S3 | Replay mismatch: a tampered `context_bundle` with a forged `manifest_hash` could pass referential checks but break replay equivalence. | `replay_consistency` eval re-derives `manifest_hash` over segments using the same canonicalisation as `context_bundle_assembler._compute_manifest_hash`; raises `REPLAY_MANIFEST_HASH_MISMATCH`. | yes |
| F-003 | S3 | Partial transcript coverage (`segments != turns`) could hide silent truncation or duplication. | `coverage` eval rejects `COVERAGE_COUNT_MISMATCH` when `len(segments) != len(speaker_turns)`. | yes |
| F-004 | S3 | PQX bypass: hand-crafted summary or evidence handed to `ArtifactStore.register_artifact` would skip trace propagation and `pqx_execution_record` emission. | Pure evaluator returns payloads WITHOUT `content_hash` so the store rejects them; `run_eval_gate_via_pqx` is the only sanctioned write path. The module text contains no `register_artifact` call. | yes |
| F-005 | S2 | Missing `eval_summary_id` in `gate_evidence` could be admitted if not required. | Schema marks `eval_summary_id` as required, constrains pattern `^EVS-[A-Z0-9_-]+$`, and rejects unknown fields via `additionalProperties: false`. | yes |
| F-006 | S2 | Forged segments with `source_turn_id` values that do not exist in `speaker_turns` could pass schema validation but break lineage. | `referential_integrity` eval rejects `ORPHAN_SEGMENT` and `SEGMENT_TURN_DRIFT`. | yes |
| F-007 | S1 | Indeterminate per-eval status (e.g., `status="indeterminate"`) could surface a gate without a clear pass/fail aggregate. | `eval_result.status` enum constrained to `[pass, fail]`; indeterminate aggregations map to `conditional_gate` (NOT routable). | no |
| F-008 | S0 | Module docstring did not state that the gate produces evidence only and that canonical routing remains with the appropriate canonical owner. | Module docstring states evidence-only role; schema description fields repeat the boundary statement; authority-shape vocabulary tests scan all surfaces. | no |

No S4 findings.

## Outcome

All S2+ findings closed in-batch with code + regression tests. See:

- `contracts/review_actions/CPL-03_fix_actions.json`
- `docs/review-actions/CPL-03_fix_plan.md`
- `tests/transcript_pipeline/test_eval_gate_cpl03.py::TestRedTeamRegressions`
- `tests/transcript_pipeline/test_eval_gate_cpl03.py::TestFailClosedGate`
- `tests/transcript_pipeline/test_eval_gate_cpl03.py::TestPQXIntegration`
- `tests/transcript_pipeline/test_eval_gate_cpl03.py::TestEvalSummarySchemaAudit`
- `tests/transcript_pipeline/test_eval_gate_cpl03.py::TestGateEvidenceSchemaAudit`
- `tests/transcript_pipeline/test_eval_gate_cpl03.py::TestAuthorityShapeVocabulary`

Post-fix run: `pytest tests/transcript_pipeline -q` → all green.

## Remaining risk

- The eval gate evaluates a single `(transcript_artifact, context_bundle)` pair. Bulk evaluation surfaces (e.g., a corpus eval) are out of scope and must come with their own CPL-03 regression suite.
- `conditional_gate` is reachable only from indeterminate aggregations; today the runtime never produces it, but the schema allows it so a future eval extension can populate it without a schema change. The downstream `routable` flag is `false` in that case.
- The eval gate consumes whatever in-memory dicts the caller passes. The PQX wrapper inherits the parent trace and registers both artifacts; callers that assemble dicts outside the governed path bear the responsibility of using `run_eval_gate_via_pqx` and not bypassing it. The artifact store rejects any direct registration attempt because the pure payload carries no `content_hash`.
