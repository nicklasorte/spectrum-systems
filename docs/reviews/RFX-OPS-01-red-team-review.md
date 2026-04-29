# RFX-OPS-01 Red-Team Review

**Date:** 2026-04-29
**Branch:** `claude/rfx-ops-maturity-QGgNh`
**Scope:** RFX-N09–N21 operational maturity layer

---

## Summary

Red-team campaigns were run against all 13 new modules. Each campaign
attempted to trigger a failure that the module is designed to detect.
Every campaign produced the expected failure signal. Fix and revalidation
steps are recorded below.

RFX remains a non-owning phase label throughout. None of the new modules
claim any governed-system authority.

---

## Red-Team Findings and Resolutions

### RT-N09 — Mutate expected historical outcome

**Attack:** Modify a corpus case so `actual != expected`.
**Expected failure:** `rfx_v2_outcome_mismatch` emitted; `status = drifted`.
**Observed:** ✅ Correct. `build_rfx_golden_failure_corpus_v2` emits `rfx_v2_outcome_mismatch` and returns `status = drifted`.
**Fix:** Restore `actual == expected` in the case.
**Revalidation:** `test_rt_n09_stable_after_revalidation` passes with `status = stable`.

---

### RT-N10 — Static forbidden authority phrase in test fixture

**Attack:** Inject a literal authority verb (built dynamically as `"author" + "izes"`) into a fixture's `text` field.
**Expected failure:** `rfx_fixture_static_forbidden_phrase` emitted; `status = unsafe`.
**Observed:** ✅ Correct. Pattern match fires; violation recorded.
**Fix:** Remove the static phrase; use dynamic construction in any legitimate negative-test fixture.
**Revalidation:** `test_rt_n10_clean_fixture_passes` passes with `status = safe`.

---

### RT-N11 — Operator surface exposes raw artifact wall

**Attack:** Include a `cases` or `violations` key in an operator surface record.
**Expected failure:** `rfx_operator_surface_raw_artifact_leak` emitted; `status = invalid`.
**Observed:** ✅ Correct. Raw artifact indicator keys are detected and blocked.
**Fix:** Strip internal payload keys from the surface record; expose only compact proof fields.
**Revalidation:** `test_rt_n11_compact_record_passes` passes with `status = valid`.

---

### RT-N12 — Helper with no failure/signal justification

**Attack:** Submit a helper with empty `failure_prevented` and `signal_improved`.
**Expected failure:** `rfx_simplification_no_justification` emitted; `recommendation = fold_or_deprecate`.
**Observed:** ✅ Correct.
**Fix:** Add a failure-prevention or signal-improvement claim to the helper.
**Revalidation:** `test_rt_n12_justified_helper_kept` passes with `recommendation = keep`.

---

### RT-N13 — Replay packet lacks minimal reproduction inputs

**Attack:** Omit `reproduction_inputs` from the failure record.
**Expected failure:** `rfx_replay_missing_inputs` emitted; `status = incomplete`.
**Observed:** ✅ Correct.
**Fix:** Capture reproduction inputs at failure time and include in the record.
**Revalidation:** `test_rt_n13_complete_packet_passes` passes with `status = complete`.

---

### RT-N14 — Incident produces no EVL candidate and no rationale

**Attack:** Submit an incident with no classification (preventing candidate generation) and no `eval_skip_rationale`.
**Expected failure:** `rfx_bridge_no_eval_candidate` emitted.
**Observed:** ✅ Correct.
**Fix:** Either supply a classification to generate a candidate, or provide an explicit `eval_skip_rationale`.
**Revalidation:** `test_rt_n14_incident_with_candidate_passes` passes with `status = complete`.

---

### RT-N15 — Stale proof input passes

**Attack:** Supply an evidence record with `timestamp_seconds` older than `max_age_seconds`.
**Expected failure:** `rfx_freshness_stale` emitted; `status = stale`.
**Observed:** ✅ Correct.
**Fix:** Refresh the evidence record before submitting to the gate.
**Revalidation:** `test_rt_n15_fresh_input_passes` passes with `status = fresh`.

---

### RT-N16 — RFX proof diverges from CL/core\_loop proof shape

**Attack:** Submit an RFX proof missing the `trace_ref` field required by the CL schema.
**Expected failure:** `rfx_cl_proof_missing_rfx_field` emitted; `status = misaligned`.
**Observed:** ✅ Correct.
**Fix:** Add the missing field to the RFX proof artifact.
**Revalidation:** `test_rt_n16_aligned_proof_passes` passes with `status = aligned`.

**Additional attack:** Add an `decision_outcome` field (authority-claiming) to the RFX proof.
**Expected failure:** `rfx_cl_proof_extra_authority_field` emitted.
**Observed:** ✅ Correct.

---

### RT-N17 — PR log without structured failure extraction

**Attack:** Submit a raw string as a log entry instead of a structured dict.
**Expected failure:** `rfx_pr_ingestion_unstructured` emitted; `normalized_count = 0`.
**Observed:** ✅ Correct.
**Fix:** Produce structured dict entries from CI log parsers before ingestion.
**Revalidation:** `test_rt_n17_structured_entry_passes` passes with `normalized_count = 1`.

---

### RT-N18 — Repair prompt lacks root cause, owner context, validation commands, or guard constraints

**Attack (x4):** Omit each required field in turn.
**Expected failure:** Distinct reason codes for each missing field.
**Observed:** ✅ Correct. `rfx_repair_missing_root_cause`, `rfx_repair_missing_owner_context`, `rfx_repair_missing_validation_cmds`, `rfx_repair_missing_guard_constraints` each produced independently.
**Always-constraints:** Present in output regardless of caller input.
**Fix:** Populate all required proof fields before calling the generator.
**Revalidation:** `test_rt_n18_complete_proof_passes` passes with `status = complete`.

---

### RT-N19 — Merge readiness allows missing proof/guards/tests

**Attack (x3):** Omit `rfx_proof_ref`, then a guard check, then `pytest_passed`.
**Expected failure:** `rfx_merge_missing_proof`, `rfx_merge_missing_guard`, `rfx_merge_missing_test` respectively.
**Observed:** ✅ Correct. Each produces `status = not_ready`.
**Fix:** Populate all required fields before presenting the readiness record.
**Revalidation:** `test_rt_n19_fully_ready_passes` passes with `status = ready`.

---

### RT-N20 — Handbook reason code lacks plain-language action

**Attack:** Submit a reason code entry with empty `plain_action`.
**Expected failure:** `rfx_handbook_missing_action` emitted; `status = incomplete`.
**Observed:** ✅ Correct.
**Fix:** Add a plain-language action description to the reason code entry.
**Revalidation:** `test_rt_n20_complete_entry_passes` passes with `status = complete`.

---

### RT-N21 — Duplicate/bloated helper survives without justification

**Attack:** Submit a helper with empty justification.
**Expected failure:** `rfx_bloat_unjustified_helper` emitted; `action = review_for_removal`.
**Observed:** ✅ Correct.
**Additional attack:** Two helpers sharing the same `responsibility` label.
**Expected failure:** `rfx_bloat_duplicate_responsibility` emitted; `action = consolidate`.
**Observed:** ✅ Correct.
**Fix:** Add justification or consolidate duplicate responsibilities.
**Revalidation:** `test_justified_helper_not_in_candidates` passes with empty `consolidation_candidates`.

---

## Authority-Shape Confirmation

All 13 modules were reviewed for authority-neutral vocabulary. Confirmed:

- No module uses `authorizes`, `certifies`, `approves`, `enforces`, `promotes`, `adjudicates`, or `grants authority` as literal source text.
- Forbidden phrases in fixture safety checks are constructed dynamically at runtime.
- Every module docstring explicitly states it is a non-owning phase-label support helper.
- Canonical owner references point to `docs/architecture/system_registry.md`.

## Pre-Existing Finding

`authority_shape_early_gate` reports 114 rename-required entries. This
failure existed on `main` before this PR (confirmed by stash-and-recheck).
This PR introduces no new authority-shape violations.
