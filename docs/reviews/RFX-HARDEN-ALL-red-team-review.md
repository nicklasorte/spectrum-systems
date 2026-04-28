# RFX-HARDEN-ALL — Red-Team Review (RT-H01 → RT-H19)

RFX remains a non-owning phase label. This review records attack, expected failure, finding, fix, revalidation, and final status for RT-H01 through RT-H19.

| Campaign | Attack | Expected failure | Finding | Fix | Revalidation | Final status |
| --- | --- | --- | --- | --- | --- | --- |
| RT-H01 | Omit module from health contract | `rfx_health_module_missing` | Missing inventory blocked health completeness | Require module field and inventory validation | `tests/test_rfx_health_contract.py` | Closed |
| RT-H02 | Duplicate/ambiguous reason code | Registry invalid | Duplicate and meaning mismatch surfaced | Require unique, explicit meaning and registry entry | `tests/test_rfx_reason_code_registry.py` | Closed |
| RT-H03 | Missing hint/repro in debug output | Bundle incomplete | Missing repair and repro found | Require repair hint + repro payload | `tests/test_rfx_debug_bundle.py` | Closed |
| RT-H04 | Malformed envelope | Validator rejects | Envelope invalid status and missing fields surfaced | Validation helper blocks malformed payload | `tests/test_rfx_output_envelope.py` | Closed |
| RT-H05 | Remove loop link | Loop incomplete | Missing eval/fix/trend/recommendation surfaced | Link presence checks | `tests/test_rfx_golden_loop.py` | Closed |
| RT-H06 | Hidden dependency | Dependency map invalid | Hidden dependency detected | Require declaration or remove coupling | `tests/test_rfx_dependency_map.py` | Closed |
| RT-H07 | Exceed budget | Budget warning emitted | Runtime over threshold surfaced | Budget checks and signals | `tests/test_rfx_bloat_budget.py` | Closed |
| RT-H08 | Rename reason variants | Cluster or ambiguity record produced | Variant split still visible | Alias map + ambiguity record | `tests/test_rfx_trend_clustering_hardening.py` | Closed |
| RT-H09 | Hardcode threshold | Policy handoff invalid | Hardcoded threshold surfaced | Require policy/eval refs + handoff | `tests/test_rfx_calibration_policy_handoff.py` | Closed |
| RT-H10 | Untraced write | Blocked | Untraced write surfaced | Require trace+lineage+owner handoff | `tests/test_rfx_memory_persistence_handoff.py` | Closed |
| RT-H11 | Bad text passes or neutral blocks | Corpus invalid | Bad-pattern miss surfaced | Corpus validator + neutral checks | `tests/test_rfx_authority_pattern_corpus.py` | Closed |
| RT-H12 | Remove module without evidence | Keep/deprecate/review output | Unjustified module surfaced | Elimination assessment output | `tests/test_rfx_module_elimination.py` | Closed |
| RT-H13 | Missing runbook action | Runbook incomplete | Missing repair action surfaced | Require repair hint + debug ref | `tests/test_rfx_operator_runbook.py` | Closed |
| RT-H14 | Drift expected outcome | Corpus drifted | Outcome mismatch surfaced | Stable expected/actual checks | `tests/test_rfx_golden_failure_corpus.py` | Closed |
| RT-H15 | Remove super-check step | Integrity failure | Step integrity would fail when missing | Required-step list and check coverage | `tests/test_run_rfx_super_check.py` | Closed |
| RT-H16 | Hidden authority assignment | Drift audit invalid | Hidden-authority flag surfaced | Drift audit reason-code checks | `tests/test_rfx_architecture_drift_audit.py` | Closed |
| RT-H17 | Contract change without migration | Snapshot mismatch | Migration note missing surfaced | Snapshot comparator with migration requirement | `tests/test_rfx_contract_snapshot.py` | Closed |
| RT-H18 | Feed unknown state | Block/incomplete | Unknown owner/trace/evidence surfaced | Unknown-state campaign validation | `tests/test_rfx_unknown_state_campaign.py` | Closed |
| RT-H19 | Add forbidden literal | Vocabulary sweep violation | Forbidden wording surfaced | Vocabulary sweep and neutral replacements | `tests/test_rfx_authority_vocabulary_sweep.py` | Closed |
