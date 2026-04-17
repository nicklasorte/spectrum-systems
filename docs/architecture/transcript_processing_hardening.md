# Transcript Processing Hardening Architecture (TRN-01)

## Prompt type
BUILD

## Intent
Transcript processing is a bounded preparation/hardening seam. It produces deterministic transcript artifacts and preparatory handoff inputs; it does **not** own control decisions, enforcement actions, or certification authority.

## Canonical execution path
1. Raw DOCX source is ingested via deterministic parser and normalized into replayable transcript artifacts.
2. Transcript hardening validates trace context at entry, starts a trace span, and records classification/hardening trace events.
3. Transcript observations are produced as deterministic preparatory classifications with confidence values and explicit non-authority assertions.
4. Transcript hardening emits handoff signals for eval/control/judgment/certification, each with required `replay_hash` continuity.
5. Downstream canonical owners (Eval/Judgment/Control/Certification) consume preparatory signals and issue authority artifacts in their own seams.
6. Transcript hardening emits either:
   - `transcript_hardening_run` (`processing_status: processed`), or
   - `transcript_hardening_failure` (`processing_status: failed`).

## Boundary constraints (hard law)
- Transcript outputs are limited to preparatory/observational fields and exclude protected-owner outcome keys (`decision`, `enforcement_action`, `certification_status`, `allow`, `block`, `freeze`, promotion outcomes).
- Transcript preparatory signals include explicit `non_authority_assertions`.
- Promotion gating remains in canonical certification/control owner paths only.

## Observation-layer architecture choice
**Choice B: keep observation layer in place with governance seams.**
- Observation classification remains deterministic and preparatory-only.
- Every classification includes confidence + evidence anchors.
- Classification trace events are recorded.
- Eval hooks are declared (`golden` + `adversarial`) and required in the run artifact.
- Interpretation authority remains downstream (RIL/JDX/CDE owners).

## Fail-closed guarantees
- Missing or invalid trace context at transcript entry is fail-closed.
- Missing replay continuity across required handoff signals is contract-invalid.
- Missing eval/trace/replay/certification prerequisites remain fail-closed at canonical owner seams.
- Transcript hardening failure always emits a governed failure artifact; no silent exception-only path.

## Guard surface
- Transcript authority-vocabulary guard script (`scripts/validate_forbidden_authority_vocabulary.py`) blocks forbidden authority keys in transcript preparation modules.
- Schema strictness (`additionalProperties: false`) enforced for transcript preparatory/failure artifacts.
