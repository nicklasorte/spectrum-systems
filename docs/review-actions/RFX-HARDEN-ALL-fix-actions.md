# RFX-HARDEN-ALL — Fix Actions

| Campaign | Finding | Fix | Revalidation | Status |
| --- | --- | --- | --- | --- |
| RT-H01 | Health contract missing module inventory entry | Added required module validation and deterministic reason code | `tests/test_rfx_health_contract.py` | Closed |
| RT-H02 | Duplicate/ambiguous reason code definitions | Added registry duplicate and ambiguity checks | `tests/test_rfx_reason_code_registry.py` | Closed |
| RT-H03 | Debug bundle allowed missing hint/repro | Added fail-closed fields for hint and repro | `tests/test_rfx_debug_bundle.py` | Closed |
| RT-H04 | Output envelopes had shape drift risk | Added normalized envelope validator | `tests/test_rfx_output_envelope.py` | Closed |
| RT-H05 | Golden loop could skip evidence link | Added mandatory link checks | `tests/test_rfx_golden_loop.py` | Closed |
| RT-H06 | Hidden dependency could remain unseen | Added dependency map validation | `tests/test_rfx_dependency_map.py` | Closed |
| RT-H07 | Bloat risk lacked measurable checks | Added runtime/size/depth budget checks | `tests/test_rfx_bloat_budget.py` | Closed |
| RT-H08 | Renamed variants could hide recurrence | Added clustering + ambiguity record | `tests/test_rfx_trend_clustering_hardening.py` | Closed |
| RT-H09 | Threshold could be embedded in RFX code | Added policy handoff checks | `tests/test_rfx_calibration_policy_handoff.py` | Closed |
| RT-H10 | Persistence write could skip trace/lineage | Added handoff validator for trace/lineage/owner | `tests/test_rfx_memory_persistence_handoff.py` | Closed |
| RT-H11 | Corpus could miss bad or block neutral text | Added bad/neutral corpus validator | `tests/test_rfx_authority_pattern_corpus.py` | Closed |
| RT-H12 | Module value could remain unmeasured | Added elimination assessment and recommendation output | `tests/test_rfx_module_elimination.py` | Closed |
| RT-H13 | Runbook could emit empty action guidance | Added action and debug-ref requirements | `tests/test_rfx_operator_runbook.py` | Closed |
| RT-H14 | Golden expected outputs could drift silently | Added expected/actual drift checks | `tests/test_rfx_golden_failure_corpus.py` | Closed |
| RT-H15 | Super-check could lose critical step | Added required-step integrity list and test | `tests/test_run_rfx_super_check.py` | Closed |
| RT-H16 | Hidden authority drift could remain implicit | Added architecture drift audit checks | `tests/test_rfx_architecture_drift_audit.py` | Closed |
| RT-H17 | Contract drift could bypass migration notes | Added snapshot comparator and migration-note check | `tests/test_rfx_contract_snapshot.py` | Closed |
| RT-H18 | Unknown state could flow through | Added unknown-state campaign blocker | `tests/test_rfx_unknown_state_campaign.py` | Closed |
| RT-H19 | Authority-shaped vocabulary leaks in changed files | Added vocabulary sweep + replacement hints | `tests/test_rfx_authority_vocabulary_sweep.py` | Closed |
