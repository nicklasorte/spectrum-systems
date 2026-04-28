# RFX-SUPER-01 — Red-Team Review (RT-13 → RT-24)

**Scope.** Red-team review of RFX-05 → RFX-16, the remaining RFX
self-improvement loop. RFX is a non-owning phase label. Canonical authority
for AEX/TLC/PQX/EVL/TPA/CDE/SEL/GOV/REP/LIN/OBS/SLO/PRA/POL/JDX/JSX/FRE/RIL
remains with the systems recorded in `docs/architecture/system_registry.md`.

Each campaign records the bypass attempt, the finding, the fix action
applied to the relevant module, and the revalidation test that re-runs the
adversarial case after the fix.

## RT-13 — Fix that removes tests or weakens schema

- **Finding.** A fix that drops protected guarantees (schema coverage,
  test coverage, eval coverage, replay match, lineage authenticity, OBS/SLO
  posture, evidence-package gates, registry-recorded ownership) must not pass.
- **Fix action.** `assert_rfx_fix_integrity_proof` aggregates reason codes
  per protected guarantee and requires a complete before/after snapshot.
- **Re-validation.** `tests/test_rfx_fix_integrity_proof.py::test_rt13_*`
  re-runs the schema-weakening and test-removal vectors and confirms each
  blocks before the fix-follow-up snapshot passes.
- **Final status.** Closed.

## RT-14 — Eval generation without trace / lineage

- **Finding.** A failure record without `trace_id` or lineage refs must
  not produce an EVL handoff candidate.
- **Fix action.** `build_rfx_failure_derived_eval_case` requires a
  reason code, trace id, and at least one lineage ref before computing
  the deterministic case id.
- **Re-validation.** `tests/test_rfx_failure_to_eval.py::test_rt14_*`
  blocks the trace-less attempt and revalidates the fixed corpus.
- **Final status.** Closed.

## RT-15 — Splitter hides recurring reason codes

- **Finding.** Renaming a recurring reason code into variants
  (`rfx_x_v1`, `rfx_x_v2`, …) must not silently defeat clustering.
- **Fix action.** `detect_recurring_reason_codes` normalizes reason
  codes through a stable variant-stripping function before counting.
- **Re-validation.** `tests/test_rfx_trend_analysis.py::test_rt15_*`
  proves the variants still cluster, and the post-fix run produces a
  recurring hotspot.
- **Final status.** Closed.

## RT-16 — Roadmap recommendation skipping owner / dep / red-team triad

- **Finding.** A recommendation that omits owners, dependencies, or the
  red-team / fix / revalidation triad must not pass.
- **Fix action.** `build_rfx_roadmap_recommendation` requires explicit
  owners, dependencies (with `no_external_dependencies` sentinel), and
  all three triad fields. Authority-claiming language is rejected.
- **Re-validation.** `tests/test_rfx_roadmap_generator.py::test_rt16_*`
  blocks each missing field and revalidates the complete recommendation.
- **Final status.** Closed.

## RT-17 — Known-bad chaos case passes silently

- **Finding.** A chaos campaign must fail closed when any case fails open
  or raises without a recognized reason code.
- **Fix action.** `run_rfx_chaos_campaign` aggregates per-case reason
  codes and emits `rfx_chaos_case_failed_open`,
  `rfx_chaos_reason_code_missing`, and `rfx_chaos_campaign_incomplete` as
  appropriate.
- **Re-validation.** `tests/test_rfx_chaos_campaign.py::test_rt17_*`
  injects a no-op case, observes campaign failure, and revalidates with
  the full blocking set.
- **Final status.** Closed.

## RT-18 — Hide cross-run inconsistency via non-material metadata

- **Finding.** Two runs with the same material inputs but a different
  CDE / GOV / replay outcome must be flagged regardless of incidental
  metadata.
- **Fix action.** `assert_rfx_cross_run_consistency` fingerprints over a
  closed material-key set so timestamps, tags, and similar non-material
  fields cannot mask divergence.
- **Re-validation.** `tests/test_rfx_cross_run_consistency.py::test_rt18_*`
  re-runs the metadata-only mutation and confirms detection.
- **Final status.** Closed.

## RT-19 — Judgment candidate from a single isolated failure

- **Finding.** A single failure is insufficient evidence for a judgment
  candidate.
- **Fix action.** `build_rfx_judgment_candidate` enforces minimum
  distinct failure refs and minimum total source refs.
- **Re-validation.** `tests/test_rfx_judgment_extraction.py::test_rt19_*`
  blocks the single-failure case and revalidates with the larger corpus.
- **Final status.** Closed.

## RT-20 — Compile directly into active policy

- **Finding.** RFX must not produce a policy artifact in any active or
  advanced lifecycle state. POL retains policy lifecycle authority.
- **Fix action.** `build_rfx_policy_candidate_handoff` restricts
  `activation_state` to candidate-class values and emits
  `rfx_policy_candidate_invalid` when an active state is supplied.
- **Re-validation.** `tests/test_rfx_policy_compilation.py::test_rt20_*`
  blocks the active-state attempt and revalidates the candidate handoff.
- **Final status.** Closed.

## RT-21 — High-confidence claim without evidence refs

- **Finding.** A high-confidence assertion without source evidence must
  not pass calibration.
- **Fix action.** `assert_rfx_calibration` emits
  `rfx_confidence_without_evidence` when evidence refs are absent and
  `rfx_overconfidence_risk` when high confidence pairs with an incorrect
  outcome.
- **Re-validation.** `tests/test_rfx_calibration.py::test_rt21_*`
  blocks the no-evidence high-confidence sample and revalidates with
  evidence refs.
- **Final status.** Closed.

## RT-22 — Misclassify feature work as reliability without evidence

- **Finding.** When the SLO budget is exhausted, only reliability work
  may continue, and reliability work must carry evidence refs.
- **Fix action.** `assert_rfx_error_budget_governance` requires
  `reliability_evidence_refs` for any reliability claim and emits the
  `rfx_new_capability_frozen` reason when feature work is attempted.
- **Re-validation.** `tests/test_rfx_error_budget_governance.py::test_rt22_*`
  blocks the misclassified attempt and revalidates with evidence refs.
- **Final status.** Closed.

## RT-23 — Index unsupported memory without source refs

- **Finding.** Memory index entries must declare lineage refs and a
  supported artifact type.
- **Fix action.** `build_rfx_memory_index_record` requires a known
  `artifact_type`, a derivable id, and lineage refs (chaos campaign
  records aggregate per-case provenance).
- **Re-validation.** `tests/test_rfx_memory_index.py::test_rt23_*`
  blocks the lineage-less artifact and revalidates after lineage refs are
  added.
- **Final status.** Closed.

## RT-24 — System intelligence claiming authorization for execution or advancement

- **Finding.** The advisory layer must not contain language that claims
  execution, advancement, evidence-package issuance, or control-outcome
  authority.
- **Fix action.** `build_rfx_system_intelligence_report` scans narrative
  fields for authority-claiming patterns and validates that the
  next-build slice is supported by an existing roadmap recommendation.
- **Re-validation.** `tests/test_rfx_system_intelligence.py::test_rt24_*`
  blocks the authority-claiming narrative and revalidates with neutral
  text.
- **Final status.** Closed.

## Final Status

All twelve campaigns (RT-13 → RT-24) are closed. Each finding has a
deterministic fix action and a revalidation test exercising the same
adversarial input. RFX remains a non-owning phase label across the
canonical systems recorded in `docs/architecture/system_registry.md`.
