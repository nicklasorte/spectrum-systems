# CPL-02 — Context Bundle Assembly Red-Team Review

- **Review id:** `RVA-CPL02-CONTEXT-001`
- **Reviewer:** `ARA-CPL02`
- **Reviewed batch:** `BATCH-CPL02`
- **Review signal:** `revision_recommended` (all S2+ findings closed in-batch — see `CPL-02_fix_actions.json`)
- **Authority boundary:** Non-authority review signal. Control authority remains with CDE; compliance authority remains with SEL; release authority remains with REL/GOV. Nothing here is a routing or release ruling.
- **Date:** 2026-04-27

## Scope

Adversarial review of the CPL-02 transcript → context_bundle assembly path:

- `contracts/schemas/transcript_pipeline/context_bundle.schema.json`
- `spectrum_systems/modules/transcript_pipeline/context_bundle_assembler.py`
- `spectrum_systems/modules/orchestration/pqx_step_harness.py` (consumer-side checks only)
- `spectrum_systems/modules/runtime/artifact_store.py` (consumer-side checks only)

## Attack surface

| Vector | What we tried |
|---|---|
| Schema bypass | Drop `segments`, drop `manifest_hash`, drop `source_turn_id`, add unknown fields on the bundle and on individual segments. |
| Source linkage forgery | Submit segments whose `source_turn_id` does not match any `speaker_turns` entry. |
| Segment drift | Keep `source_turn_id` matching but tamper with `text` / `speaker` / `line_index`. |
| Reorder | Permute segments to break replay equivalence and lineage order. |
| Duplicates | Duplicate `segment_id` or duplicate `turn_id` in the source. |
| Partial coverage | Submit fewer segments than turns (or more) — silent transcript truncation. |
| Direct artifact write | Bypass PQX and hand the bundle to `ArtifactStore.register_artifact`. |
| Trace gaps | Call assembler with malformed `trace_id` / `span_id` outside the harness. |
| Replay non-determinism | Vary trace, run_id, clock — must not change `manifest_hash` or `content_hash`. |
| LLM contamination | Confirm zero LLM imports / calls in the assembler module. |

## Findings (severity ladder S0–S4)

| ID | Severity | Description | Recommendation | Blocking |
|---|---|---|---|---|
| F-001 | S3 | Missing `speaker_turns` on the input transcript could silently produce an empty bundle. | Raise `MISSING_SPEAKER_TURNS`; schema requires `segments` with `minItems: 1`. | yes |
| F-002 | S3 | A forged segment with a `source_turn_id` that does not exist in the transcript could pass schema validation but break lineage. | Validate inside `_validate_referential_integrity`: reject `ORPHAN_SEGMENT`. | yes |
| F-003 | S3 | Segment text could be tampered while keeping the matching `source_turn_id`, breaking trace fidelity. | Compare `(speaker, text, line_index)` against the source turn at the same index; reject `SEGMENT_TURN_DRIFT`. | yes |
| F-004 | S3 | Reordering segments would change the manifest but still pass schema; replay equivalence would silently break. | Compute `manifest_hash` over the ordered manifest; pin `artifact_id` derivation to that hash. | yes |
| F-005 | S2 | Partial transcript coverage (e.g., assembler emits N-1 segments) would lose information silently. | Reject `SEGMENT_TURN_COUNT_MISMATCH` when `len(segments) != len(turns)`. | yes |
| F-006 | S2 | Duplicate `segment_id` could collide downstream lookup tables. | Reject `DUPLICATE_SEGMENT_ID`; derive ids deterministically as `SEG-NNNN`. | yes |
| F-007 | S2 | Duplicate `turn_id` in the source transcript could produce an ambiguous bundle. | Reject `DUPLICATE_TURN_ID` at validation time. | yes |
| F-008 | S2 | Direct call to `ArtifactStore.register_artifact` could bypass PQX trace propagation. | The pure assembler returns a payload **without** `content_hash` so the store rejects it; PQX is the only path that mints the hash. Test `test_assembler_cannot_write_artifact_directly` locks the contract. | yes |
| F-009 | S2 | Replay non-determinism: different `trace_id`, `run_id`, or `created_at` could perturb `manifest_hash` / `content_hash` if the canonicalization were sloppy. | `manifest_hash` is computed over `segments` only; `content_hash` excludes `trace`/`created_at` per `hash_utils`. Locked by `TestReplayDeterminism::test_manifest_hash_independent_of_envelope`. | yes |
| F-010 | S1 | `trace_id` / `span_id` are validated only by schema; calling the assembler outside PQX could produce a malformed trace silently. | Validate trace at the assembler boundary with `INVALID_TRACE_ID` / `INVALID_SPAN_ID`. | no |
| F-011 | S1 | A non-`transcript_artifact` input could be admitted (e.g., normalized_transcript) and silently produce a bundle. | Reject `INVALID_SOURCE_ARTIFACT_TYPE` and `INVALID_SOURCE_ARTIFACT_ID`. | no |
| F-012 | S0 | Module docstring did not state that `content_hash` is owned by the artifact store and `manifest_hash` is owned by the assembler. | Document the split in module docstring and `assemble_context_bundle` return value. | no |

No S4 findings.

## Outcome

All S2+ findings closed in-batch with code + regression tests. See:

- `contracts/review_actions/CPL-02_fix_actions.json`
- `docs/review-actions/CPL-02_fix_plan.md`
- `tests/transcript_pipeline/test_context_bundle_assembler_cpl02.py::TestRedTeamRegressions`
- `tests/transcript_pipeline/test_context_bundle_assembler_cpl02.py::TestReferentialIntegrity`
- `tests/transcript_pipeline/test_context_bundle_assembler_cpl02.py::TestReplayDeterminism`

Post-fix run: `pytest tests/transcript_pipeline -q` → all green (334 tests).

## Remaining risk

- Source formats other than `txt` flow through the H08 ingestor unchanged — non-txt parsers are out of scope and must come with their own CPL-02 regression suite once H08 supports them.
- The assembler requires strict 1:1 alignment with `speaker_turns`. A future "windowed" or "selective" `assembly_strategy` would need an extension to the integrity rules and is intentionally rejected by the schema enum (`enum: ["full"]`).
- Eval gate (CPL-03) is the next step. The assembler is **not** an eval substitute. CDE remains the sole canonical owner over whether a context_bundle is admissible to downstream steps.
