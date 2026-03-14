# Text Quality Rubric (Example)

Use this rubric to score outputs from fixtures in `evals/fixtures/`. Mark criteria as **blocking** when failures should prevent promotion; otherwise mark as **warning** for triage.

| Criterion | Guidance | Blocking Threshold |
| --- | --- | --- |
| Fidelity to source | Accurately reflects stated facts and constraints; no fabrication. | Any fabricated fact or omitted required element is blocking. |
| Instruction compliance | Honors required structure/formatting (e.g., bullets, max length, required fields). | Any structural deviation is blocking. |
| Tone and safety | Uses neutral, professional tone; respects stated safety/guardrail boundaries. | Boundary violation or inflammatory language is blocking. |
| Specificity | Provides concrete statements tied to the input; avoids vague filler. | If two or more sentences are filler or generic, flag as warning. |
| Completeness | Covers all requested points and enumerated items. | Missing a requested point is blocking; minor phrasing gaps are warning. |

## Scoring template
- **Pass**: All blocking criteria satisfied; warnings documented.
- **Warning**: One or more warning-level issues; review before promotion.
- **Fail**: Any blocking criterion violated; fix before merging or deploying.

## Notes
- Customize thresholds per dataset if a criterion requires tighter bounds (e.g., exact token length).
- Keep rubric versions in commit messages or headers so run manifests can pin the scoring rules used.
