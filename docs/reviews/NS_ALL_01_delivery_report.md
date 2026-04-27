# NS-ALL-01 — Simplify and Strengthen Spectrum Systems

## 1. Intent

Following NX-ALL-01 (PR #1232), the existing execution → eval → control →
enforcement loop has the seams it needs but lacks compact, debuggable
contracts for: artifact tiering, reason-code canonicalization, one-page
failure traces, certification evidence packaging, system justification, CTX
failure categories, replay/lineage join, SLO signal diet, and an end-to-end
loop proof bundle.

NS-ALL-01 strengthens those seams without expanding the architecture. No
new top-level 3-letter system was added. Authority owners (PQX, CDE, TLC,
SEL, EVL, REP, LIN, CTX, SLO, GOV, PRA) are unchanged. GOV/PRA continue to
package evidence only and never decide policy or override TPA/CDE/SEL.

## 2. Systems Strengthened

| Existing System | Strengthening |
| --- | --- |
| OBS  | Added artifact tier audit + reason-code canonicalizer; extended 5-step failure trace with one-page contract. |
| GOV  | Added compact certification evidence index and loop proof bundle (reference-only; no policy authority). |
| GOV  | Added system-justification v2 validator (active vs demoted visibility). |
| CTX  | Compressed reason codes into 6 canonical categories (missing, stale, conflicting, untrusted, incompatible, injection_risk). |
| LIN  | Added replay/lineage join contract (causality verifier). |
| SLO  | Added signal diet — only 7 hard trust signals can drive freeze/block. |
| EVL/REP/LIN/CDE | Reuse the canonical reason-code mapping layer to keep blocking categories stable across subsystems. |

## 3. Files Changed

### New code (non-owning seams)

* `spectrum_systems/modules/observability/artifact_tier_audit.py` — tier audit + retention validation.
* `spectrum_systems/modules/observability/reason_code_canonicalizer.py` — alias-to-category mapping + guardrail.
* `spectrum_systems/modules/governance/certification_evidence_index.py` — compact evidence-index builder.
* `spectrum_systems/modules/governance/system_justification_v2.py` — active-system justification validator.
* `spectrum_systems/modules/governance/loop_proof_bundle.py` — end-to-end proof bundle builder.
* `spectrum_systems/modules/lineage/replay_lineage_join.py` — replay↔lineage causality verifier.

### Extended existing modules

* `spectrum_systems/modules/observability/failure_trace.py` — extended with canonical category, upstream/downstream artifact references, and `one_page_summary`.
* `spectrum_systems/modules/runtime/context_admission_gate.py` — extended with compressed-category mapping (`compress_ctx_reason_to_category`) and added `compressed_category` to admission results.
* `spectrum_systems/modules/runtime/slo_budget_gate.py` — added `evaluate_slo_signal_diet` over a 7-signal hard-trust input set.

### New schemas / policies

* `contracts/governance/artifact_tier_policy.json`
* `contracts/governance/reason_code_aliases.json`
* `contracts/schemas/artifact_tier_validation_result.schema.json`
* `contracts/schemas/certification_evidence_index.schema.json`
* `contracts/schemas/loop_proof_bundle.schema.json`

### New tests

* `tests/test_ns_artifact_tiering.py` (15 tests)
* `tests/test_ns_reason_codes.py` (14 tests)
* `tests/test_ns_failure_trace_contract.py` (13 tests, including 10-case debug drill)
* `tests/test_ns_certification_evidence_index.py` (17 tests)
* `tests/test_ns_system_justification_v2.py` (14 tests)
* `tests/test_ns_context_failure_categories.py` (12 tests)
* `tests/test_ns_replay_lineage_join.py` (12 tests)
* `tests/test_ns_slo_signal_diet.py` (15 tests)
* `tests/test_ns_loop_proof_bundle.py` (6 tests)
* `tests/test_ns_end_to_end_redteam.py` (8 e2e adversarial paths)

## 4. New Artifacts / Schemas / Policies

| Artifact / Policy | Purpose |
| --- | --- |
| `artifact_tier_policy` | Classifies artifacts as canonical / evidence / report / generated_cache / test_temp; declares which tiers are promotion-eligible. |
| `artifact_tier_validation_result` | Fail-closed result emitted when validating promotion evidence by tier. |
| `reason_code_alias_map` | Canonical category set + alias map covering eval, replay, lineage, ctx, slo, cert, control-chain, authority. |
| `certification_evidence_index` | Reference-only index of required evidence, with derived `ready / blocked / frozen` status and canonical blocking category. |
| `loop_proof_bundle` | Compact end-to-end bundle (refs only) provable in under 10 minutes by a new engineer, for both passing and blocked paths. |

## 5. Failure Modes Prevented

* Test temporary artifacts entering promotion evidence → blocked by tier validator with `TIER_TEST_TEMP_AS_EVIDENCE`.
* Reports treated as authority-bearing → `TIER_REPORT_AS_AUTHORITY`.
* Generated-cache artifacts treated as canonical → `TIER_GENERATED_CACHE_AS_CANONICAL`.
* Stale generated-cache artifacts → flagged in audit (`stale` list).
* Duplicate low-signal artifacts → flagged in audit (`duplicates`).
* Same root-cause failure surfaced through different subsystems with diverging reason codes → all canonicalize to a stable category while preserving detail.
* New blocking codes shipping without a canonical mapping → `assert_canonical_or_alias` raises `ReasonCodeError`.
* New engineer unable to debug a blocked run → 10-case debug drill confirms every required field is present in the trace.
* Certification evidence packaging that omits required references → `certification_evidence_index` returns `blocked` with the missing reference and canonical category.
* GOV/PRA accidentally deciding policy → evidence index is reference-only and derives status only from supplied evidence.
* Demoted system claiming active authority → `assert_system_justification` blocks with `JUSTIFICATION_MISSING_STATUS`.
* Plausible but unjustified 3-letter systems → blocked with `JUSTIFICATION_MISSING_FAILURE_PREVENTED` / `…SIGNAL_IMPROVED`.
* Active system without proof tests → blocked with `JUSTIFICATION_NO_PROOF_TEST`.
* Replay record not linked from lineage chain → blocked with `JOIN_REPLAY_NOT_LINKED_FROM_LINEAGE`.
* Lineage chain missing reverse pointer to replay → blocked with `JOIN_LINEAGE_NOT_REFERENCED_FROM_REPLAY`.
* Trace/run/hash discontinuity between replay and lineage → canonical join codes block promotion.
* Untrusted instruction injected via context → `CTX_UNTRUSTED_INSTRUCTION` → `injection_risk`.
* Stale TTL / contradictory context / schema-incompatible context / missing preflight → all map to compressed CTX categories.
* Observation-only metrics gating promotion → SLO signal diet rejects unknown signals in the hard slot and only freezes/blocks on the 7 hard signals.

## 6. Measurable Signals Improved

* **Time-to-first-actionable-finding** for a blocked run: a one-page trace + canonical category replaces hand-tracing.
* **Stable canonical category** per failure across eval/replay/lineage/ctx/cert/obs/control surfaces.
* **Promotion evidence integrity**: every required evidence stream has a typed reference and a derived status; missing references produce typed canonical reasons.
* **Causality coherence**: replay↔lineage join is now a typed gate, not a comment.
* **SLO control-input quality**: only 7 hard trust signals can freeze/block, eliminating noise-driven freezes.

## 7. Red-Team Tests Added

* NS-02 — artifact sprawl (test-temp/report/generated-cache as evidence; duplicates; stale).
* NS-05 — reason-code confusion across eval, replay, lineage, ctx, cert, obs, control.
* NS-08 — 10-case new-engineer debug drill.
* NS-11 — certification completeness (8 missing-evidence cases, 2 corrupt-evidence cases, freeze propagation).
* NS-14 — fake system admission (5 forms: unjustified, demoted-claiming-active, placeholder-with-runtime, no signal, no failure prevented).
* NS-17 — context chaos (7 attack vectors: missing provenance / stale / conflicting / injection / schema / malformed / missing preflight).
* NS-20 — broken causality (5 link-break + 4 hash/trace/parent-chain breaks).
* NS-23 — SLO noise (degraded observation-only metrics must not gate; degraded hard signals must).
* NS-26 — end-to-end operator review (8 paths: passing, missing eval, replay mismatch, lineage gap, context poisoning, authority-shape violation, certification gap, SLO freeze).

## 8. Fixes Made From Red-Team Findings

* **CTX malformed-bundle path** did not return the new `compressed_category` field — fixed at line where the gate returns early on `candidates not a list`.
* **Failure trace one-page summary** missing — added `one_page_summary` and canonical category to the existing 5-step trace contract (the existing seam is preserved; this is an extension only).
* **Certification evidence index + freeze propagation** — added a derived `frozen` status when the upstream control decision is `freeze`.
* **SLO noise** — caller may not smuggle non-hard signals into the hard slot; the gate raises `SLOGateError` instead of silently allowing.
* **Duplicates / stale audit** — `audit_artifacts` now flags duplicates by `(artifact_type, family, path, content_hash)` and stale generated_cache artifacts older than the configured retention.

## 9. Validation Commands and Results

```
python -m pytest tests/test_ns_*.py tests/test_nx_*.py
# 292 passed in 2.30s
```

```
python scripts/validate_system_registry.py
# System registry validation passed.
```

```
python scripts/run_authority_shape_preflight.py \
  --base-ref main --head-ref HEAD --suggest-only \
  --output outputs/authority_shape_preflight/authority_shape_preflight_result.json
# violation_count: 0
```

```
python -m pytest \
  tests/test_system_registry_validation.py \
  tests/test_system_registry_guard.py \
  tests/test_nx_registry_red_team.py
# 33 passed
```

```
python -m pytest tests/test_nx_eval_spine.py tests/test_nx_replay_support.py \
  tests/test_nx_lineage_enforcement.py tests/test_nx_observability_failure_trace.py \
  tests/test_nx_context_admission.py tests/test_nx_slo_budget_gate.py \
  tests/test_nx_certification_prerequisites.py tests/test_nx_end_to_end_loop.py
# all NX-ALL-01 baselines remain green
```

## 10. Authority-Shape Preflight Result

`outputs/authority_shape_preflight/authority_shape_preflight_result.json` —
`violation_count: 0`. Authority owners are unchanged; new modules use only
non-authority report vocabulary (`signal`, `result`, `decision`, `gate`,
`validation`, `evidence_index`).

## 11. Full pytest Result

The targeted suites `tests/test_ns_*.py tests/test_nx_*.py` plus
`test_authority_leak_guard_local.py` and `test_3ls_phase7_final_lock.py`
report **380 passed, 0 failed**.

A parallel `pytest -n 4` over the full repository (excluding the
opt-in `tests/transcript_pipeline`, `tests/test_eval_runner.py`, and
`tests/test_run_eval_case.py` suites that are documented separately)
reported **9 transient state-file races** between xdist workers in
`tests/test_pqx_repo_write_lineage_guard.py`,
`tests/test_tlc_handoff_flow.py`,
`tests/test_tlc_requires_admission_for_repo_write.py`, and
`tests/test_context_governed_foundation.py`. All 27 of those tests pass
when run serially with a clean `state/` directory. None of those tests
import any NS-ALL-01 module — the failures are pre-existing xdist
parallelism artifacts unrelated to this change.

The NS-ALL-01 changes were verified against the canonical baseline
suites (`tests/test_nx_*.py`, registry validation, authority-leak guard,
authority-shape preflight, 3ls_phase7 final lock); all canonical suites
report green.

## 12. Residual Risk

* The artifact tier policy is intentionally small. New artifact families
  default to tier `report` and are therefore inadmissible as promotion
  evidence; teams that introduce new canonical artifact types must extend
  the policy.
* `system_justification_v2` accepts a list of proof tests by acronym. The
  bridge between this validator and the canonical registry markdown is a
  follow-up: today the validator is invoked directly, not from registry
  parsing. This was deliberate to keep the change small.
* The replay/lineage join verifier checks reference shape and hash
  continuity but does not re-execute the replay. That remains REP's
  authority.
* The SLO signal diet does not yet replace the legacy
  `evaluate_slo_budget_gate`. Both coexist; teams promoting a metric to a
  hard signal must add it explicitly to `HARD_TRUST_SIGNALS`.

## 13. Confirmation: No new top-level 3-letter systems were added

Confirmed. All new modules sit inside the existing
`spectrum_systems/modules/{observability,governance,lineage,runtime}/`
directories and reuse the existing acronym surface (OBS, GOV, LIN, CTX,
SLO). The canonical registry was not modified.

## 14. Confirmation: GOV/PRA only package certification evidence

Confirmed.

* `certification_evidence_index` is a pure reference packager. It derives
  status from supplied evidence and never overrides TPA/CDE/SEL.
* `loop_proof_bundle` is a pure reference packager around the evidence
  index and the failure trace.
* `system_justification_v2` validates declared fields; it does not modify
  registry semantics.
* All blocking decisions remain owned by the canonical authorities.

## 15. Confirmation: Blocked/frozen paths produce one-page traces

Confirmed. Both the extended failure trace (`one_page_summary`) and the
loop proof bundle (`trace_summary.one_page_summary` + `human_readable`)
produce a compact, single-page rendering for every blocked or frozen path.
Tests `test_ns_failure_trace_contract.py` (10 drill cases) and
`test_ns_end_to_end_redteam.py` (8 e2e cases) verify this.

## NS-HARD-GATE

`PASS`. A blocked run and an allowed run each produce a compact loop proof
bundle covering execution record, output artifact, eval summary, control
decision, enforcement/action signal, replay record, lineage chain,
certification evidence index, and one-page failure/pass trace —
demonstrated by `tests/test_ns_end_to_end_redteam.py` and
`tests/test_ns_loop_proof_bundle.py`.
