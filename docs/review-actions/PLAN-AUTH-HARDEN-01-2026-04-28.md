# PLAN-AUTH-HARDEN-01-2026-04-28

Primary Prompt Type: BUILD

## Intent
Catch authority-shape drift earlier across 3LS by hardening schema lint coverage, review-language lint coverage, deterministic failure packets, required evals, control mapping, and observability rollups without weakening fail-closed preflight behavior.

## Method
1. Inspect existing authority registries, 3LS preflight, authority-shape detector, eval gate wiring, control mapping, and observability scripts.
2. Extend the authority owner registry with required authority clusters and explicit neutral/disallowed term sets.
3. Add schema-level authority-shape lint coverage for property names, required fields, enum values, artifact_kind, titles, and examples.
4. Add review-language lint coverage for docs/reviews with owner-qualified allow rules and ambiguous-claim blocking.
5. Emit deterministic authority-boundary failure packets from RIL path with required fields.
6. Add/extend eval cases and required-eval gate wiring so missing/failed authority-shape evals block.
7. Map authority-shape failures to CTL/CDE BLOCK outcomes and repeated-violation FREEZE behavior.
8. Add OBS metrics for cluster/owner/file/PR recurrence/suggested replacements and add regression tests for acceptance criteria.

## Guardrails
- Preserve fail-closed semantics.
- No broad allowlists or silent recovery.
- Keep non-owner systems from claiming judgment/compliance/review/advancement authority.
- Keep changes scoped to AUTH-HARDEN-01 behavior.
