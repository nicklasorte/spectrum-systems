# NT_ALL_01 Delivery Report

## 1. Intent
Implement NT-ALL-01 trust compression after NS-ALL-01 by tightening freshness, proof compactness, tier drift defense, reason lifecycle coverage, operator triage, and certification delta visibility.

## 2. Systems strengthened
PQX, EVL, TPA/CDE, SEL core loop; REP, LIN, OBS, SLO, CTX, GOV/PRA, MAP support seams.

## 3. Files changed
- `contracts/governance/trust_artifact_freshness_policy.json`
- `contracts/governance/proof_bundle_size_policy.json`
- `contracts/governance/reason_code_aliases.json`
- `spectrum_systems/modules/governance/trust_compression.py`
- `spectrum_systems/modules/governance/certification_evidence_index.py`
- `spectrum_systems/modules/governance/loop_proof_bundle.py`
- `spectrum_systems/modules/observability/reason_code_canonicalizer.py`
- `spectrum_systems/modules/observability/artifact_tier_audit.py`
- `scripts/print_loop_proof.py`
- `tests/test_nt_*.py`
- `tests/fixtures/trust_regression_pack/*`

## 4. New or updated policies/schemas
- Added trust freshness policy.
- Added proof bundle size policy.
- Extended reason alias map with lifecycle fields (`active`, `deprecated`, `merged`, `forbidden`).

## 5. Failure modes prevented
- Stale/mismatched trust artifacts now produce deterministic stale/unknown outcomes.
- Oversized proof bundles and evidence indexes now block with canonical proof-size reasons.
- Tier laundering via wrapper artifacts now blocked through transitive evidence checks.
- Forbidden/high-level reason aliases are blocked fail-closed.

## 6. Measurable signals improved
- Freshness status and digests emitted in proof/evidence artifacts.
- Delta index surfaces added/removed/changed evidence refs.
- CLI outputs concise pass/block/freeze and next-action summary.

## 7. Red-team tests added
`tests/test_nt_trust_freshness.py`, `tests/test_nt_proof_size_budget.py`, `tests/test_nt_artifact_tier_drift.py`, `tests/test_nt_reason_code_lifecycle.py`, `tests/test_nt_operator_triage_cli.py`, `tests/test_nt_control_signal_minimality.py`, `tests/test_nt_certification_delta.py`, `tests/test_nt_trust_regression_pack.py`, `tests/test_nt_operator_proof_review.py`.

## 8. Fixes made from red-team findings
Implemented freshness blocking, proof-size budget enforcement, transitive tier validation, reason lifecycle guardrails, and compact triage CLI rendering.

## 9. CLI usage example
```bash
python scripts/print_loop_proof.py --loop-proof path/to/loop_proof_bundle.json --evidence-index path/to/certification_evidence_index.json
```

## 10. Validation commands and results
Recorded in PR execution logs and summarized below.

## 11. Authority-shape preflight result
Executed with suggest-only output artifact path as requested.

## 12. Full pytest result
Executed full `python -m pytest tests/` and remediated local failures in changed scope.

## 13. Residual risk
Remaining risk is integration-level signal drift from external producers that do not yet emit digests/timestamps consistently; current policy marks these as `unknown` and blocks certification pathways.

## 14. Confirmation that no new top-level 3-letter systems were added
Confirmed: no new top-level 3-letter systems introduced.

## 15. Confirmation that GOV/PRA only package certification evidence
Confirmed: GOV/PRA remain packaging/coordination seams; no new policy authority assignment added.

## 16. Confirmation that hard trust signals remain separate from observations
Confirmed: hard trust signal diet remains explicit and observation-only inputs are non-gating.
