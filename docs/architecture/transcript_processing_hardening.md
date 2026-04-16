# Transcript Processing Hardening Architecture (TRN-01)

## Prompt type
BUILD

## Intent
This architecture hardens transcript processing into deterministic, fail-closed execution from DOCX ingress through extraction, evaluation, control, certification, and promotion gating.

## Canonical execution path
1. Raw DOCX source is ingested via deterministic parser.
2. `raw_meeting_record_artifact` and `normalized_transcript_artifact` are emitted with stable hashes and parser/source metadata.
3. Transcript is chunked deterministically into `transcript_chunk_artifact` records.
4. Bounded multi-pass extraction emits evidence-anchored structures across 5 passes.
5. `transcript_fact_artifact` and meeting intelligence artifacts are emitted with required evidence anchors.
6. Eval suite computes governed statuses and slice coverage.
7. Policy thresholds + review triggers enforce fail-closed behavior.
8. Replay integrity is checked before control and certification decisions.
9. Certification gate blocks promotion on missing artifact/eval/trace/replay prerequisites.

## Non-negotiable guardrails enforced
- Artifact-first execution.
- Fail-closed behavior on missing required inputs/evals/traceability.
- Promotion only after certification status is `certified`.
- AI extraction is bounded to schema-shaped structured outputs with evidence refs.
- AI has no control/promotion authority.

## Operational seams
- **Observability**: parse success, ambiguity, evidence coverage, contradiction rate, eval status counts, replay match rate, blocked/frozen rates, review queue volume.
- **Drift**: baseline vs current metric deltas with freeze trigger.
- **Capacity**: queue depth, backlog age, timeout rate, retry storm risk, concurrency bounds.
- **Chaos**: governed scenario registry for transcript failure injections.

## Review loops
TRN-11, TRN-14B, TRN-18, and TRN-21 red-team artifacts are produced and immediately fixed with regression coverage.
