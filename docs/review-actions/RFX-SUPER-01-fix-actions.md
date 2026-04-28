# RFX-SUPER-01 — Fix Actions

This document records the fix actions applied for each red-team finding
RT-13 → RT-24, paired with the revalidation step. Companion review:
`docs/reviews/RFX-SUPER-01-red-team-review.md`.

| Campaign | Finding | Fix Action | Revalidation Test | Status |
| --- | --- | --- | --- | --- |
| RT-13 | Fix removes tests / weakens schema | `assert_rfx_fix_integrity_proof` aggregates reason codes per protected guarantee and demands complete before/after snapshots. | `tests/test_rfx_fix_integrity_proof.py::test_rt13_red_team_remove_tests_blocks_then_revalidates` and `::test_rt13_red_team_weaken_schema_blocks_then_revalidates` | Closed |
| RT-14 | Eval generation without trace / lineage | `build_rfx_failure_derived_eval_case` requires `reason_code`, `trace_id`, and ≥1 lineage ref. | `tests/test_rfx_failure_to_eval.py::test_rt14_red_team_no_trace_or_lineage_blocks_then_revalidates` | Closed |
| RT-15 | Reason-code variants hide recurrence | `_normalize_reason_code` collapses variants to a stable cluster key before counting. | `tests/test_rfx_trend_analysis.py::test_rt15_split_reason_code_variants_still_clusters` and `::test_rt15_fix_follow_up_revalidation` | Closed |
| RT-16 | Roadmap recommendation skipping owner / dep / red-team triad | `build_rfx_roadmap_recommendation` enforces owners, dependencies, the red-team / fix / revalidation triad, and rejects authority-claiming language. | `tests/test_rfx_roadmap_generator.py::test_rt16_*` | Closed |
| RT-17 | Known-bad chaos case passes silently | `run_rfx_chaos_campaign` emits `rfx_chaos_case_failed_open` / `rfx_chaos_reason_code_missing` / `rfx_chaos_campaign_incomplete` and validates the canonical scenario set. | `tests/test_rfx_chaos_campaign.py::test_rt17_red_team_known_bad_case_that_passes_fails_campaign` and `::test_rt17_fix_follow_up_revalidation` | Closed |
| RT-18 | Hide inconsistency via non-material metadata | `assert_rfx_cross_run_consistency` fingerprints over a closed material-key set. | `tests/test_rfx_cross_run_consistency.py::test_rt18_*` | Closed |
| RT-19 | Judgment candidate from a single isolated failure | `build_rfx_judgment_candidate` enforces minimum distinct failures and minimum total refs. | `tests/test_rfx_judgment_extraction.py::test_rt19_red_team_isolated_failure_blocks_then_revalidates` | Closed |
| RT-20 | Compile directly into active policy | `build_rfx_policy_candidate_handoff` restricts `activation_state` to candidate-class values. | `tests/test_rfx_policy_compilation.py::test_rt20_red_team_active_policy_blocks_then_revalidates` | Closed |
| RT-21 | High-confidence claim without evidence refs | `assert_rfx_calibration` emits `rfx_confidence_without_evidence` and `rfx_overconfidence_risk`. | `tests/test_rfx_calibration.py::test_rt21_red_team_high_confidence_no_evidence_blocks_then_revalidates` | Closed |
| RT-22 | Misclassify feature work as reliability without evidence | `assert_rfx_error_budget_governance` requires `reliability_evidence_refs` for reliability claims. | `tests/test_rfx_error_budget_governance.py::test_rt22_red_team_reliability_without_evidence_blocks_then_revalidates` | Closed |
| RT-23 | Index unsupported memory without source refs | `build_rfx_memory_index_record` requires supported `artifact_type`, derivable id, and lineage refs. | `tests/test_rfx_memory_index.py::test_rt23_red_team_no_source_refs_blocks_then_revalidates` | Closed |
| RT-24 | System intelligence authorizing execution / promotion | `build_rfx_system_intelligence_report` scans narrative chunks for authority-claiming patterns and validates supported next-build slice. | `tests/test_rfx_system_intelligence.py::test_rt24_red_team_authority_violation_blocks_then_revalidates` | Closed |

Every campaign produced a fix step and a revalidation step. RFX remains a
non-owning phase label across the canonical systems recorded in
`docs/architecture/system_registry.md`.
