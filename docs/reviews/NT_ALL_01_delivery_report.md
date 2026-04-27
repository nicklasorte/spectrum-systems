# NT-ALL-01 — Operational Trust Compression After NS-ALL-01

## 1. Intent

Following NS-ALL-01 (PR #1236), the trust system already had compact
contracts for tiering, reason-code canonicalization, one-page failure
traces, certification evidence packaging, replay/lineage join, SLO signal
diet, and an end-to-end loop proof bundle.

NT-ALL-01 makes that surface **smaller, fresher, easier to debug, and
harder to misuse**. It strengthens the existing 3-letter systems and the
core loop instead of expanding the architecture. **No new top-level
3-letter systems are added.** Authority owners (PQX, CDE, TLC, SEL, EVL,
REP, LIN, CTX, SLO, GOV, PRA) are unchanged. GOV/PRA continue to package
evidence only and never decide policy or override TPA/CDE/SEL.

The hard gate of NT-ALL-01: a new maintainer can run **one command**
against a pass / block / freeze loop proof bundle and identify final
status, failed-or-passed stage, canonical reason category, owning system,
evidence refs, changed evidence since last proof, and next recommended
action — all without reading raw JSON first.

## 2. Systems Strengthened

| Existing System | Strengthening |
| --- | --- |
| OBS  | Added trust artifact freshness audit (digest-dominant, timestamp secondary, no silent fallback). |
| OBS  | Added artifact tier drift monitor — transitive evidence validation + tier-change-between-runs detection + missing-metadata fail-closed. |
| OBS  | Added reason-code lifecycle layer (active / deprecated / merged / forbidden) and coverage audit. |
| GOV  | Added proof-bundle size budget validator + deterministic compressor (reference-only, summary-first). |
| GOV  | Added certification delta index (added/removed/changed evidence detection across two cert runs). |
| SLO/CDE | Added control signal minimality audit — observation-only signals never gate promotion; hard-trust signals do. |
| OBS / Operator | Added read-only operator triage CLI (`scripts/print_loop_proof.py`) — render-only, no business logic. |
| EVL/REP/LIN/CDE | Continue to consume the canonical reason-code mapping layer; new lifecycle states extend it without changing existing emit contracts. |

## 3. Files Changed

### New observational seams (non-owning)

- `spectrum_systems/modules/observability/trust_artifact_freshness.py` — freshness audit (NT-01..03).
- `spectrum_systems/modules/observability/artifact_tier_drift.py` — transitive tier validation + drift detection (NT-07..09).
- `spectrum_systems/modules/observability/reason_code_lifecycle.py` — lifecycle classifier + coverage audit (NT-10..12).
- `spectrum_systems/modules/governance/proof_bundle_size.py` — size-budget validator + deterministic compressor (NT-04..06).
- `spectrum_systems/modules/governance/certification_delta.py` — certification delta index builder (NT-19..21).
- `spectrum_systems/modules/runtime/control_signal_minimality.py` — control-input minimality audit (NT-16..18).
- `scripts/print_loop_proof.py` — read-only operator triage CLI (NT-13..15).

### New policies

- `contracts/governance/trust_artifact_freshness_policy.json`
- `contracts/governance/proof_bundle_size_policy.json`

### Extended existing contracts

- `contracts/governance/reason_code_aliases.json` — adds NT-ALL-01 alias families (trust freshness, proof bundle size, tier drift, reason-code lifecycle, control signal minimality, certification delta) and the new `alias_lifecycle` block (default/deprecated/merged/forbidden).
- `contracts/governance/authority_registry.json` — adds the new NT-ALL-01 modules and the read-only CLI to `forbidden_contexts.excluded_path_prefixes` and `observational_path_entries` (each entry: `authority_scope: observational`, `may_authorize: false`, `canonical_owner: null`).
- `contracts/governance/authority_shape_vocabulary.json` — adds the new files to `scope.guard_path_prefixes` so the preflight skips them as observational seams.

### New tests

- `tests/test_nt_trust_freshness.py` (12 tests)
- `tests/test_nt_proof_size_budget.py` (13 tests)
- `tests/test_nt_artifact_tier_drift.py` (9 tests)
- `tests/test_nt_reason_code_lifecycle.py` (15 tests)
- `tests/test_nt_operator_triage_cli.py` (12 tests)
- `tests/test_nt_control_signal_minimality.py` (13 tests)
- `tests/test_nt_certification_delta.py` (12 tests)
- `tests/test_nt_trust_regression_pack.py` (14 tests, incl. red-team mutations)
- `tests/test_nt_operator_proof_review.py` (5 tests, final maintainer drill)

### New fixtures

- `tests/fixtures/trust_regression_pack/README.md`
- `tests/fixtures/trust_regression_pack/pass.json`
- `tests/fixtures/trust_regression_pack/block.json`
- `tests/fixtures/trust_regression_pack/freeze.json`
- `tests/fixtures/trust_regression_pack/stale_proof.json`
- `tests/fixtures/trust_regression_pack/tier_violation.json`
- `tests/fixtures/trust_regression_pack/reason_code_violation.json`
- `tests/fixtures/trust_regression_pack/replay_lineage_mismatch.json`
- `tests/fixtures/trust_regression_pack/context_admission_failure.json`

## 4. New or Updated Policies / Schemas

- `trust_artifact_freshness_policy.json` (new): tracks 9 trust artifact types; rules use producer/source digest first, timestamp second; missing freshness signal is `unknown` (never silently `current`); `fail_closed: true`.
- `proof_bundle_size_policy.json` (new): per-artifact-type budgets (max top-level evidence refs, max one-page summary chars, max human-readable chars, max blocking detail codes, max nested depth, forbidden inline evidence keys); deterministic stable ordering for evidence refs; overflow defaults to `block`, alternative is deterministic `compress_to_references`.
- `reason_code_aliases.json` (extended): adds ~50 NT-ALL-01 aliases mapped to existing canonical categories (CERTIFICATION_GAP, POLICY_MISMATCH); adds `alias_lifecycle` block with `forbidden` registry.

No new schemas were strictly required — every NT-ALL-01 module returns reference-only dicts whose shape is verified by tests, not by a JSON schema authority. Existing schemas (`loop_proof_bundle.schema.json`, `certification_evidence_index.schema.json`, `artifact_tier_validation_result.schema.json`) are unchanged; the new modules consume and decorate them.

## 5. Failure Modes Prevented

- **Stale proof masquerading as fresh.** Source-digest mismatch is `stale` even when timestamp is fresh; missing source-digest verification yields `unknown`, never `current`.
- **Bloated proof bundles obscuring failure.** Bundles exceeding evidence-ref / one-page / human-readable / nesting / detail-code budgets are blocked or compressed deterministically; inline evidence is suppressed and listed.
- **Repeated evidence refs creating false coverage.** Repeated ref values across slots are detected and blocked.
- **Tier escape through canonical wrapper.** A loop_proof_bundle reference cannot launder a `report` / `test_temp` / `generated_cache` artifact into promotion evidence; transitive tier validation blocks it.
- **Missing tier metadata silently inferred as evidence.** Bare artifacts without tier / path / type are blocked rather than defaulted.
- **Unmapped or forbidden reason codes shipping.** Lifecycle classifier raises on `forbidden`; `assert_emittable_reason_code` raises on unknown high-level codes; coverage audit detects unused aliases, deprecated emissions, and aliases pointing to missing canonical category.
- **Observation hijack of control.** Dashboard freshness, report counts, advisory recommendations, cosmetic proof formatting — none can drive `freeze` / `block`. Hard trust signals remain the only freeze/block drivers.
- **Hidden delta swap.** Eval/replay/lineage ref swapped while keeping status `pass`? Certification delta index detects digest change; status / reason / owner changes raise delta_risk to `high`. Silent removal without explanation blocks.
- **Operator forced to read raw JSON.** `scripts/print_loop_proof.py` produces structured triage output covering all seven required maintainer signals.

## 6. Measurable Signals Improved

- One-page summary cap enforced (≤4000 chars).
- Loop proof bundle size cap enforced (≤6000 chars human_readable; ≤12 top-level evidence refs).
- Stable evidence-ref ordering across compressed bundles → byte-deterministic outputs.
- Operator CLI exit-code grammar: `0=pass`, `2=block`, `3=freeze`, `4=corrupt/missing`, `5=unknown` — programmable triage.
- Reason-code coverage audit produces `unmapped_blocking`, `forbidden_emitted`, `deprecated_emitted`, `unused_aliases`, `aliases_pointing_to_missing_canonical`, `duplicate_aliases` lists for governance review.
- Certification delta produces explicit `delta_risk` levels (`none / low / medium / high`) tied to specific change classes, replacing prose comparison.

## 7. Red-Team Tests Added

| File | Red-team coverage |
| --- | --- |
| `test_nt_trust_freshness.py` | source-digest mismatch with fresh timestamp; input-digest mismatch with fresh timestamp; missing expected source digest with verified input only (must be `unknown`); stale timestamp with matching digests; unknown artifact type. |
| `test_nt_proof_size_budget.py` | too-many top-level refs; inline evidence forbidden; oversized one-page; oversized human-readable; repeated evidence refs; too many blocking detail codes; unknown artifact type → policy unavailable; deterministic + stable compressor output. |
| `test_nt_artifact_tier_drift.py` | report-as-top-evidence; test_temp-through-canonical-wrapper laundering; generated_cache-through-wrapper; missing tier metadata; tier change between runs; missing baseline yields `unknown_baseline` (not pass). |
| `test_nt_reason_code_lifecycle.py` | forbidden alias raises; high-level unmapped (`blocked`) raises; unknown invented code raises; alias pointing to missing canonical detected; forbidden emitted in audit blocks. |
| `test_nt_operator_triage_cli.py` | corrupt JSON → exit 4; missing required field → exit 4; missing file → exit 4; wrong artifact_type → exit 4; bloated bundle renders size warning; unknown reason renders without crashing. |
| `test_nt_control_signal_minimality.py` | dashboard freshness used as block driver blocks audit; report count used as block driver blocks; advisory recommendation blocks; cosmetic_proof_formatting blocks; non-hard-signal in hard-signal slot rejected; real hard signal still freezes/blocks via SLO diet. |
| `test_nt_certification_delta.py` | eval ref swap with status=pass detected; replay ref swap detected; status change detected; canonical reason change detected; owner system change detected; silent removal blocks unless explained; addition without explanation blocks; unknown baseline = high risk. |
| `test_nt_trust_regression_pack.py` | mutated pass → block; mutated block reason → still canonicalizes; mutated stale with bumped timestamp → still stale via digest; mutated tier through wrapper still blocks; mutated cert delta swap still detected. |

## 8. Fixes Applied From Red-Team Findings

- **NT-03 freshness fix.** Source-digest fields recorded on the artifact but not verified by the caller now yield `unknown` instead of falling through to a timestamp-only `current`. The dominant signal can never be silently bypassed.
- **NT-09 tier boundary fix.** `validate_transitive_promotion_evidence_tiers` independently classifies referenced evidence at depth `transitive`; missing tier metadata is a hard `TIER_DRIFT_METADATA_MISSING` block.
- **NT-12 lifecycle fix.** `assert_emittable_reason_code` raises on `forbidden`; deprecated codes warn but pass; unknown high-level codes raise via `assert_canonical_or_alias`.
- **NT-15 CLI fix.** CLI rejects corrupt / missing-required JSON with exit code 4 before rendering; freshness and size validation surfaces are advisory in the rendered output but the body of the CLI carries no business logic.
- **NT-18 signal boundary fix.** `validate_control_signal_minimality` blocks any caller that proposes an observation-only signal as a block/freeze driver; non-hard signals injected into the hard-signal slot are explicitly rejected.
- **NT-21 delta fix.** Certification delta builder treats unexplained add/remove as `medium` risk and status / reason / owner changes as `high`. Hidden swaps (same status, swapped ref) surface as `CERTIFICATION_DELTA_CHANGED_DIGEST`.

## 9. CLI Usage Example

```bash
python scripts/print_loop_proof.py path/to/loop_proof_bundle.json
# exit 0 → pass

python scripts/print_loop_proof.py path/to/blocked_bundle.json \
    --certification-evidence-index path/to/cei.json \
    --previous path/to/last_bundle.json
# exit 2 → block; output renders failed_or_passed_stage, owning_system,
# canonical_reason_category, evidence_refs, changed_evidence_since_previous,
# next_recommended_action, and the one-page failure trace.
```

Sample block output:

```
LOOP PROOF — bundle_id=lpb-block trace_id=tBLOCK
----------------------------------------------------------------
final_status:               block
overall_trace_status:       failed
failed_or_passed_stage:     eval
owning_system:              EVL
canonical_reason_category:  EVAL_FAILURE
detail_reason_code:         missing_required_eval_result
freshness_status:           unknown
size_validation:            allow
cert_index_status:          blocked
cert_index_block_canonical: EVAL_FAILURE

evidence_refs:
  execution_record_ref: exec-2
  output_artifact_ref: out-2
  eval_summary_ref: evl-bad
  control_decision_ref: cde-blk
  enforcement_action_ref: sel-blk
  replay_record_ref: rpl-2
  lineage_chain_ref: lin-2
  certification_evidence_index_ref: cei-lpb-block
  failure_trace_ref: tBLOCK

changed_evidence_since_previous:
  (no previous bundle supplied)

next_recommended_action: Inspect failing stage 'eval' (EVL) and remediate root cause.

--- one-page trace ---
FAILURE TRACE — trace_id=tBLOCK
overall_status: failed
failed_stage: eval
owning_system: EVL
canonical_category: EVAL_FAILURE
...
```

## 10. Validation Commands and Results

```bash
# 1. NT + NS + NX targeted suites
$ python -m pytest tests/test_nt_*.py tests/test_ns_*.py tests/test_nx_*.py -q
397 passed in 3.82s

# 2. System registry validation
$ python scripts/validate_system_registry.py
System registry validation passed.

# 3. Authority-shape preflight
$ python scripts/run_authority_shape_preflight.py \
    --base-ref main --head-ref HEAD --suggest-only \
    --output outputs/authority_shape_preflight/authority_shape_preflight_result.json
violation_count: 0

# 4. Authority leak guard regression
$ python -m pytest tests/test_authority_leak_guard_local.py \
    tests/test_nx_authority_shape_preflight_regression.py -q
21 passed

# 5. Full pytest
$ python -m pytest tests/ -q
9702 passed, 2 skipped, 36 warnings in 597.11s
```

## 11. Authority-Shape Preflight Result

```
violation_count:        0
applied_rename_count:   0
refused_rename_count:   0
output:                 outputs/authority_shape_preflight/authority_shape_preflight_result.json
```

The new NT-ALL-01 modules are registered in
`authority_shape_vocabulary.json` `scope.guard_path_prefixes` and in
`authority_registry.json` `forbidden_contexts.excluded_path_prefixes` and
`observational_path_entries`, identical to the pattern already used for
`slo_budget_gate.py`, `certification_evidence_index.py`,
`loop_proof_bundle.py`, etc.

## 12. Full Pytest Result

```
9702 passed, 2 skipped, 36 warnings in 597.11s (≈9 minutes 57 seconds)
```

No tests skipped, deleted, or `xfail`-marked by NT-ALL-01. The two
pre-existing skips are unrelated to this work.

## 13. Residual Risk

- **Freshness expectation is caller-supplied.** The freshness audit
  needs the caller to pass `expected_input_digest` / `expected_source_digest`
  to make a strong claim. Without expected digests, the audit reports
  `unknown` (correctly fail-closed). Future work: a freshness-orchestrator
  seam that derives expected digests from canonical producers, removing
  the burden from callers.
- **Compressor stops at the policy budget.** If a future proof-artifact
  type carries a structurally different size axis (e.g., per-step token
  counts) the size policy must be extended; today the policy is
  per-artifact-type and indexed by `artifact_type`.
- **Lifecycle table starts conservative.** The `forbidden` list seeds with
  five tokens (`approved_silently`, `auto_overridden`, `decision_implied`,
  `warning_only_block`, `control_decision_silent`); the `deprecated` /
  `merged` lists are intentionally empty — they exist as ready slots for
  governed alias retirement.

## 14. Confirmation: No New Top-Level 3-Letter Systems

NT-ALL-01 introduced **zero** new 3-letter systems. Every new module is
declared as observational (`authority_scope: observational`,
`may_authorize: false`, `canonical_owner: null`) under existing systems
(OBS / GOV / SLO+CDE / Operator-CLI). The system registry
(`docs/architecture/system_registry.md`) is unchanged.

## 15. Confirmation: GOV/PRA Only Package Certification Evidence

`proof_bundle_size.py`, `certification_delta.py`, and the certification
evidence index it consumes all hold references and never decide policy.
Each NT-ALL-01 module returns a `decision: allow|block` value as a
typed validation result — exactly the pattern used by
`certification_prerequisites.py`, `slo_budget_gate.py`, and
`replay_lineage_join.py`. None of them override TPA / CDE / SEL.

## 16. Confirmation: Hard Trust Signals Remain Separate From Observations

`spectrum_systems/modules/runtime/control_signal_minimality.py` makes
the boundary explicit:

- `HARD_TRUST_SIGNALS_NT` extends the existing NS-22 hard set (eval pass,
  replay match, lineage completeness, context admissibility,
  authority-shape preflight, registry validation, certification evidence
  index status) with two NT-ALL-01 hard signals: `artifact_tier_validity_status`
  and `trust_artifact_freshness_status`.
- `OBSERVATION_ONLY_SIGNALS` lists `dashboard_freshness`, `report_count`,
  `report_volume`, `non_critical_trend_note`, `advisory_recommendation`,
  `cosmetic_proof_formatting`, `ui_render_time`, `metric_count_drift`.
- `validate_control_signal_minimality(...)` blocks any caller that
  proposes an observation-only signal as a `block` / `freeze` driver and
  rejects non-hard signals injected into the hard-signal slot.

The existing `evaluate_slo_signal_diet` in `slo_budget_gate.py` continues
to be the canonical hard-signal aggregator; NT-16 only audits the
boundary, never weakens it.

## 17. Final Hard Gate

The roadmap's hard gate: **a new maintainer must be able to run one
command against a pass / block / freeze loop proof bundle and understand
final status, failed-or-passed stage, canonical reason category, owning
system, evidence refs, changed evidence since last proof, and next
recommended action.**

This gate is enforced by `tests/test_nt_operator_proof_review.py`,
specifically `test_one_command_renders_seven_diagnostic_signals_for_block`,
which scrapes CLI output for the seven required diagnostic substrings and
fails if any are missing. The companion tests
(`test_pass_proof_passes_new_maintainer_drill`,
`test_block_proof_passes_new_maintainer_drill`,
`test_freeze_proof_passes_new_maintainer_drill`,
`test_changed_evidence_section_renders_with_previous`) enforce the same
gate for each terminal status. All pass. Gate cleared.
