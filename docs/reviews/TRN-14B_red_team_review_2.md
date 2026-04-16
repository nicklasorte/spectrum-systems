# TRN-14B Red Team Review 2 — AI + Eval + Grounding

## Scope
Hallucinated structured outputs, grounding gaps, eval blind spots, replay ambiguity, unbounded AI behavior.

## Findings
- S2: AI extraction outputs were not enforced as bounded pass-wise artifacts with trace metadata.
- S2: Missing explicit evidence/chunk ref checks on semantic output items.
- S2: Eval surface lacked slice reporting and policy trigger integration.

## Fixes applied
- Added deterministic five-pass extraction bundle with per-pass request/response trace structures.
- Added fail-closed evidence and chunk reference validation for extracted facts.
- Added governed eval suite output with slice results and policy-alignment signals.

## Severity counts
- S0: 0
- S1: 0
- S2: 3
- S3: 0
- S4: 0
