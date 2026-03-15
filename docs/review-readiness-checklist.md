# Review Readiness Checklist

Canonical gate for determining whether a review package is ready for a Claude-led design or governance review. Run this checklist before requesting any review.

## Pre-review checks
1. **Ecosystem registry is current** — `ecosystem/ecosystem-registry.json` is updated with all governed repos and intended consumers.
2. **Governance manifest standard exists with example(s)** — the governance manifest pattern is documented and at least one example artifact is present and valid.
3. **Standards manifest references are internally consistent** — `contracts/standards-manifest.json` links and intended_consumers align with referenced contract and schema files.
4. **Review artifacts have matching action trackers** — every entry under `docs/reviews/` has an action tracker in `docs/review-actions/` that shares the date stem.
5. **Prior critical findings reconciled** — all open critical items from the previous review are either closed with linked evidence, explicitly still open, or explicitly deferred with a trigger.
6. **Review registry coverage** — each review artifact has a corresponding entry in `docs/review-registry.md` that links the action tracker and records the follow-up trigger.
7. **Contract examples still validate** — examples referenced by contracts or schemas continue to validate against their schemas.
8. **Boundary violations addressed or noted** — no known boundary violations remain without an explicit note describing the gap and mitigation plan.

## Evidence expectations
- Evidence must follow `docs/review-evidence-standard.md`.
- “Ready” status requires linked proof; statements of completion without evidence do not pass this gate.
- Track evidence links in the action tracker and the review registry so follow-up reviews can verify closure without re-collecting proof.
