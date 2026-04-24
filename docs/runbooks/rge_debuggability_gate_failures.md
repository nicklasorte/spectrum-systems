# Runbook: RGE Debuggability Gate Findings

**System:** RGE
**Gate:** debuggability_gate (Principle 3 - Optimize for Debuggability)
**Artifact:** debuggability_assessment_record (decision=return_for_rewrite)

---

## WHAT

The Debuggability Gate scores a phase on explainability. Unlike Gates 1 and 2,
this gate does not block - it returns a list of gaps and an
`explainability_score` below the threshold (default 0.7).

Five sub-checks: evidence_refs, runbook, stop_reason, failure_prevented length,
numeric signal.

## WHY

A phase that a new engineer cannot explain in five minutes is a phase that
will rot. Principle 3 keeps every phase recoverable without archaeology.

## SYMPTOMS

```
decision: return_for_rewrite
explainability_score: 0.4
gaps:
  - evidence_refs: missing or prose-only - link specific artifact IDs
  - stop_reason: '' not in CANONICAL_STOP_REASONS
  - signal_improved: needs a specific number or threshold
```

## DIAGNOSIS STEPS

1. Read `gaps`. Each gap names exactly one missing or weak field.
2. Cross-check `stop_reason` against
   `spectrum_systems/modules/runtime/roadmap_stop_reasons.CANONICAL_STOP_REASONS`.
3. Verify `evidence_refs` are artifact IDs (contain `:` or `-`), not prose.

## FIX

- Add at least one artifact-ID-shaped `evidence_ref`.
- Add a `runbook` path under `docs/runbooks/`.
- Pick a canonical `stop_reason`.
- Rewrite `failure_prevented` to at least 20 chars with a specific mode.
- Add a number or threshold to `signal_improved`.

Re-submit through the filter.

## PREVENTION

- Templates for phase proposals should pre-fill the five Principle 3 fields.
- Reviewers should read the phase with a new-engineer lens.
- The `glossary` block in every record disambiguates 3LS abbreviations.
