# ENF-04A Contract Preflight Repair Review

## What broke
After ENF-04, contract preflight was blocking because impacted producer/consumer tests were still aligned to legacy closure semantics:
- tests expected promotion behavior from non-lock CDE decisions in some paths
- tests expected older promotion-block reason text
- GitHub continuation tests/scenarios did not supply the new governed evidence inputs required for evidence-complete outcomes

This produced producer/consumer failure clusters in preflight and resulted in `strategy_gate_decision=BLOCK`.

## How compatibility was repaired
- Updated impacted tests to align with ENF-04 fail-closed semantics and current reason text.
- Added deterministic test-only evidence attachment helpers for GitHub ingestion summaries so continuation paths can provide complete governed evidence (`eval_summary`, `done_certification_record`, `promotion_consistency_record`, and required eval completeness payload).
- Extended GitHub continuation optional ingestion keys for governed evidence artifacts and normalized `eval_summary_ref` and certification status extraction to consume canonical example artifacts safely.
- Kept CDE/sequence fail-closed policy intact; no backslide to artifact-exists promotion.

## How ENF-04 evidence completeness was preserved
- No relaxation of missing eval/trace/certification handling on promotable paths.
- CDE evidence reason-code semantics remain authoritative for blocking incomplete evidence.
- Sequence transition still requires lock + evidence-complete CDE artifact for canonical promotion.
- GitHub promotion gating remains evidence-complete and non-promotable-state aware; it now supports valid governed evidence inputs rather than silently permitting incomplete inputs.

## Follow-up cleanup
- Add first-class governed ingestion contracts for `cde_evidence_inputs` summary payload to reduce test-only wiring.
- Add a dedicated artifact contract for required eval completeness rollup to avoid relying on summary-side bridge data.
