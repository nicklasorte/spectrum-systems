# NT-ALL-01 — Operational Trust Compression Delivery Report

## 1. Intent

Compress the operational trust loop introduced by NS-ALL-01 / NX-ALL-01:
make the existing trust system smaller, fresher, easier to debug, and
harder to misuse — without adding any new top-level 3-letter system.
Every change strengthens an existing seam (PQX, EVL, TPA/CDE, SEL, REP,
LIN, OBS, SLO, CTX, GOV/PRA, MAP) or the canonical loop. Each new
module justifies itself by preventing a concrete failure mode or
improving a measurable signal.

## 2. Systems strengthened

| System | Strengthening |
| --- | --- |
| OBS | trust artifact freshness audit (digest + timestamp + unknown), tier drift monitor, transitive tier validation, reason-code lifecycle/coverage audit, prefix coverage extended to `TRUST_FRESHNESS_*` and `PROOF_SIZE_*` |
| GOV | proof bundle size budget, certification delta proof, all keep GOV strictly to packaging/audit (no policy authority) |
| CDE | control signal minimality audit (only hard trust signals can drive freeze/block; observations may only warn) |
| SLO | hard trust signal set extended with freshness; observation-only signals catalogued explicitly |
| REP / LIN | covered by the trust regression pack so any seam regression is caught |
| CTX | covered by minimality audit (`context_admissibility_status` is a hard signal) |

## 3. Files changed

### New modules

- `spectrum_systems/modules/observability/trust_artifact_freshness.py` — NT-01..03
- `spectrum_systems/modules/governance/proof_bundle_size_budget.py` — NT-04..06
- `spectrum_systems/modules/governance/certification_delta.py` — NT-19..21
- `spectrum_systems/modules/runtime/control_signal_minimality.py` — NT-16..18

### Updated modules

- `spectrum_systems/modules/observability/artifact_tier_audit.py` — NT-07..09 tier drift + transitive validation
- `spectrum_systems/modules/observability/reason_code_canonicalizer.py` — NT-10..12 lifecycle states + coverage audit + new prefixes

### New CLI

- `scripts/print_loop_proof.py` — NT-13..15 operator triage CLI

### New / updated policies and schemas

- `contracts/governance/trust_artifact_freshness_policy.json` (new) — NT-03
- `contracts/governance/proof_bundle_size_policy.json` (new) — NT-04
- `contracts/governance/reason_code_aliases.json` (updated) — alias additions for `trust_freshness_*`, `proof_size_*`, `tier_*`, `cert_delta_*` plus the NT-12 `alias_lifecycle` block
- `contracts/governance/authority_registry.json` (updated) — new modules listed in `forbidden_contexts.excluded_path_prefixes` and `observational_path_entries`
- `contracts/governance/authority_shape_vocabulary.json` (updated) — guard path prefixes extended to the new modules, CLI, and policy files

### New tests

- `tests/test_nt_trust_freshness.py`
- `tests/test_nt_proof_size_budget.py`
- `tests/test_nt_artifact_tier_drift.py`
- `tests/test_nt_reason_code_lifecycle.py`
- `tests/test_nt_operator_triage_cli.py`
- `tests/test_nt_control_signal_minimality.py`
- `tests/test_nt_certification_delta.py`
- `tests/test_nt_trust_regression_pack.py`
- `tests/test_nt_operator_proof_review.py`
- `tests/fixtures/trust_regression_pack/README.md` (rationale per fixture)

## 4. New or updated policies / schemas

| File | Purpose |
| --- | --- |
| `trust_artifact_freshness_policy.json` | per-kind digest/timestamp budgets for the seven gating trust artifacts. Stale or unknown freshness fails closed. |
| `proof_bundle_size_policy.json` | size + complexity caps for `loop_proof_bundle`, `certification_evidence_index`, and the one-page trace; forbids inline evidence. |
| `reason_code_aliases.json` (1.1.0) | adds `alias_lifecycle` (active/deprecated/merged/forbidden) and aliases for `trust_freshness_*`, `proof_size_*`, `tier_drift_*`, `cert_delta_*`. |
| `authority_registry.json` | new modules registered as observational seams (non-owners). |
| `authority_shape_vocabulary.json` | new modules and policies registered under `guard_path_prefixes`. |

## 5. Failure modes prevented

- **Stale proof attack** — a tampered producer payload reusing an old declared digest is detected because the audit recomputes the digest and refuses to trust the timestamp alone when a stronger signal is available.
- **Proof bloat** — a producer cannot inline evidence, repeat references, blow up the one-page trace, or nest payloads to mask weak coverage.
- **Tier escape via wrapper** — a `report` / `test_temp` / `generated_cache` artifact cannot satisfy promotion evidence even when wrapped under a canonical-typed `loop_proof_bundle` reference (single-hop transitive validation).
- **Tier laundering across runs** — an artifact that previously classified as low-trust cannot quietly flip to `evidence` without an explicit override.
- **Reason-code sprawl** — new high-level blocking strings or unknown blocking codes are rejected at the boundary; deprecated aliases are preserved but flagged; forbidden aliases hard-block.
- **Observation hijack** — `dashboard_freshness_seconds`, `report_count`, `advisory_recommendation_count`, and other observation-only metrics cannot drive a freeze/block. Only the finite set of hard trust signals can.
- **Hidden delta** — silent removal of stale evidence, swapping an artifact id under the same ref key, and digest changes all surface and block readiness unless explained.
- **Operator opacity** — the new CLI renders pass / block / freeze proofs in a structured human form so a new maintainer can answer the six required questions without reading raw JSON.

## 6. Measurable signals improved

- **Freshness coverage**: 7 trust artifact kinds now have a per-kind digest budget enforced by a fail-closed audit.
- **Proof compactness**: human-readable rendering, ref counts, nested depth, and one-page lines are all bounded by policy. Compact pass proofs render under 6 KB.
- **Reason-code quality**: alias lifecycle exposes deprecated/forbidden codes; coverage audit detects emitted-but-forbidden, emitted-but-deprecated, unmapped blocking, and missing canonical-category aliases.
- **Control input minimality**: hard trust signal set now includes `trust_artifact_freshness_status` and `artifact_tier_validity_status` alongside the existing 7. Observation-only signal set is finite and named.
- **Delta signal**: certification readiness can detect added / removed / changed-digest / changed-status / changed-reason / changed-owner across two evidence indexes; risk classified `none/low/medium/high`; high-risk unexplained delta blocks readiness.
- **Operator triage time**: CLI exit code (0/1/2/3) maps directly to operator action.

## 7. Red-team tests added

| Roadmap | Adversary scenario | Test file |
| --- | --- | --- |
| NT-02 | stale / mismatched / unknown freshness for each trust artifact kind | `test_nt_trust_freshness.py` |
| NT-05 | oversized refs, inline evidence, duplicate refs, deep nesting, bloated one-page, oversized human_readable, oversized cert detail codes | `test_nt_proof_size_budget.py` |
| NT-08 | indirect laundering via wrapper, test_temp/cache/report wrappers, omitted-tier inferred-as-evidence, tier flipping low → evidence | `test_nt_artifact_tier_drift.py` |
| NT-11 | unknown high-level blocking strings, forbidden alias emit, unknown blocking, unknown reason canonicalization | `test_nt_reason_code_lifecycle.py` |
| NT-14 | pass/block/freeze proofs, corrupt / missing / unknown final_status, stale freshness blocks pass, evidence-index inconsistency | `test_nt_operator_triage_cli.py` |
| NT-17 | block via report_count, freeze via dashboard freshness, advisory hijack, cosmetic hijack, unknown-signal smuggle, missing canonical reason, missing evidence ref | `test_nt_control_signal_minimality.py` |
| NT-20 | swap eval/replay/control refs while keeping status pass, lineage digest change, silent removal, status flip, owner change | `test_nt_certification_delta.py` |
| NT-23 | mutated regression pack covers missing eval, replay mismatch, lineage gap, stale proof, tier escape, unknown reason, observation hijack, missing certification evidence | `test_nt_trust_regression_pack.py` |
| NT-26 | new maintainer reading only CLI output + bundle + index can answer the six required questions | `test_nt_operator_proof_review.py` |

## 8. Fixes made from red-team findings

- Freshness audit was initially treating "no proof + policy.require_digest=false" as current; fixed to fail closed unless `policy.allow_unknown=true` is explicit (closes the no-proof unknown path).
- `canonicalize_reason_code` now surfaces lifecycle metadata even for codes that appear only in the lifecycle bucket (forbidden / deprecated / merged) without an active alias entry, so the boundary guard can refuse forbidden codes regardless of whether they were also added to the active alias map.
- Authority leak guard surfaced legitimate use of `decision`, `allow`, `block`, `freeze` in the new non-owning seams; resolved by registering each new module under `forbidden_contexts.excluded_path_prefixes` and `observational_path_entries` (mirroring the existing `slo_budget_gate.py` and `certification_evidence_index.py` registration pattern).

## 9. CLI usage example

```bash
$ python scripts/print_loop_proof.py \
    --bundle outputs/loop_proof/lpb-FOO.json \
    --evidence-index outputs/cei/cei-FOO.json \
    --delta outputs/cei/cei-delta-FOO.json \
    --freshness outputs/audits/freshness-FOO.json
```

Output is a structured rendering with `LOOP PROOF — SUMMARY`,
`EVIDENCE REFS`, `CERTIFICATION EVIDENCE INDEX`, `CERTIFICATION DELTA`,
`PROOF FRESHNESS`, and `ONE-PAGE TRACE` sections. Exit code:

- `0` — pass
- `1` — block / freeze (or stale freshness)
- `2` — corrupt / missing required evidence (e.g., bundle JSON unreadable, wrong artifact_type, evidence-index inconsistent with bundle)
- `3` — block/freeze with `UNKNOWN` canonical reason category (operator triage required)

## 10. Validation commands and results

### Targeted suite

```
python -m pytest tests/test_nt_*.py tests/test_ns_*.py tests/test_nx_*.py
=> 419 passed in 3.18s
```

### Registry validation

```
python scripts/validate_system_registry.py
=> System registry validation passed.
```

## 11. Authority-shape preflight result

```
python scripts/run_authority_shape_preflight.py \
  --base-ref main --head-ref HEAD --suggest-only \
  --output outputs/authority_shape_preflight/authority_shape_preflight_result.json
=> status: pass  violations: 0
```

## 12. Full pytest result

```
python -m pytest tests/
=> 9729 passed, 2 skipped, 36 warnings in 599.90s
```

The 36 warnings are pre-existing `jsonschema.RefResolver` deprecation notices unrelated to NT-ALL-01.

## 13. Residual risk

- The certification delta validator detects evidence digest changes only when the producer publishes `evidence_digests` in the index. Indexes that omit per-key digests fall back to artifact_id comparison only; this is intentional (no synthetic digesting) but means producers must expose digests if they want sub-id change detection. Recommend producer guidance in a follow-up.
- The transitive tier validator is one hop deep. Deeper laundering chains are out of scope; the loop proof bundle is reference-only by design and a single hop is sufficient when every wrapper is itself reference-only. If a future seam introduces multi-hop reference graphs the validator must be extended.
- The freshness audit's policy file is itself a trust artifact; the audit recomputes per-kind digests but does not re-validate the policy file's own integrity in this pass. This is acceptable because the policy file lives in `contracts/` (canonical tier) and is read only at audit time; integrity of the file is covered by registry / digest infrastructure already in place.

## 14. Confirmation: no new top-level 3-letter systems

Confirmed. All work strengthens existing systems (OBS, GOV, CDE, SLO, REP, LIN, CTX) and the canonical loop. No top-level entries were added to `docs/architecture/system_registry.md`. The new modules live under existing module directories (`observability/`, `governance/`, `runtime/`) and are registered as observational seams in `authority_registry.json`.

## 15. Confirmation: GOV/PRA only package certification evidence

Confirmed. The new GOV-adjacent modules (`proof_bundle_size_budget.py`, `certification_delta.py`) only audit / package / diff existing evidence artifacts. They emit pass-with-reason or block-with-canonical-reason outputs that canonical owners consume; none of them issue a control or certification decision. They are non-owning per `authority_registry.json::observational_path_entries`.

## 16. Confirmation: hard trust signals remain separate from observations

Confirmed. The `control_signal_minimality.py` module enumerates the finite set of hard trust signals (NT-16 list, including the freshness signal added by NT-01..03) and rejects any block/freeze decision that rests on observation-only signals or unknown signals. The existing `slo_budget_gate.HARD_TRUST_SIGNALS` constraint is unchanged and continues to refuse non-hard signals in its hard-signal slot. The `OBSERVATION_ONLY_SIGNAL_NAMES` set explicitly catalogues observations that may only warn, never block.

## Final hard gate

A new maintainer running

```bash
python scripts/print_loop_proof.py --bundle path/to/bundle.json
```

sees:

- `final_status: pass | block | freeze`
- `failed_stage` and `owning_system`
- `canonical_reason_category` (from the canonical 12-category set) and `detail_reason_code`
- every evidence ref by name
- `CERTIFICATION DELTA` section (when supplied) with risk + counts of changed evidence
- `next_recommended_action` line
- a stable exit code mapped to the next operator action

The hard gate passes.
