# Plan — WPG-EXEC-C-H — 2026-04-15

## Prompt type
BUILD

## Roadmap item
WPG-EXEC-C-H

## Objective
Implement executable WPG Phases C–H (plus CHK/GOV integration points) with contract-first artifacts, deterministic control decisions, red-team loops, and fail-closed behavior.

## Declared files
| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-WPG-EXEC-C-H-2026-04-15.md | CREATE | Required plan-first declaration for multi-file build |
| spectrum_systems/modules/wpg/critique_memory.py | CREATE | WPG-35..WPG-38 critique memory ingestion/profile/retrieval logic |
| spectrum_systems/modules/wpg/critique_loop.py | CREATE | WPG-39 multi-pass critique loop logic |
| spectrum_systems/modules/wpg/judgment.py | CREATE | JDG-03..JDG-05 judgment + precedent + eval logic |
| spectrum_systems/modules/wpg/policy_ops.py | CREATE | XRI-04/POL-03/SRE-15 cross-run/policy/SLO controls |
| spectrum_systems/modules/wpg/governance_offload.py | CREATE | GOV-12..GOV-21 governance policy profiles + canary/decision |
| spectrum_systems/modules/wpg/certification.py | CREATE | WPG-41/WPG-50 certification + template artifacts |
| spectrum_systems/modules/wpg/redteam.py | MODIFY | RTX-13/14/15/16 findings builders for new phases |
| spectrum_systems/modules/wpg/__init__.py | MODIFY | Export new WPG module entry points |
| spectrum_systems/orchestration/wpg_pipeline.py | MODIFY | Wire critique/judgment/policy/governance/certification stages with control decisions |
| contracts/schemas/*.schema.json (new WPG C-H + GOV artifacts listed in code changes) | CREATE | Contract-first schema surfaces for all new artifacts |
| contracts/examples/*.json (matching new schemas) | CREATE | Golden examples for all new artifacts |
| contracts/examples/wpg_redteam_findings_phase_c.json | CREATE | RTX-13 requested artifact fixture |
| contracts/standards-manifest.json | MODIFY | Register all new contract artifacts |
| tests/test_wpg_contracts.py | MODIFY | Include new contracts in WPG contract validation set |
| tests/test_wpg_comment_matrix_ingestion.py | CREATE | WPG-35 tests |
| tests/test_wpg_agency_profiles.py | CREATE | WPG-36 tests |
| tests/test_wpg_industry_profiles.py | CREATE | WPG-37 tests |
| tests/test_wpg_critique_retrieval.py | CREATE | WPG-38 tests |
| tests/test_wpg_multi_pass_critique.py | CREATE | WPG-39 tests |
| tests/test_wpg_judgment_records.py | CREATE | JDG-03 tests |
| tests/test_wpg_precedent.py | CREATE | JDG-04 tests |
| tests/test_wpg_judgment_eval.py | CREATE | JDG-05 tests |
| tests/test_wpg_cross_run.py | CREATE | XRI-04 tests |
| tests/test_wpg_policy_profiles.py | CREATE | POL-03 tests |
| tests/test_wpg_slo.py | CREATE | SRE-15 tests |
| tests/test_phase_checkpoint.py | CREATE | CHK-01 tests (explicit file requested) |
| tests/test_phase_transition.py | CREATE | CHK-02 tests (explicit file requested) |
| tests/test_phase_transition_cli.py | CREATE | CHK-05 tests (explicit file requested) |
| tests/test_wpg_governance_offload.py | CREATE | GOV-12..21 tests |
| tests/test_wpg_certification.py | CREATE | WPG-41/WPG-50 tests |

## Contracts touched
New contracts for WPG critique/judgment/policy/checkpoint/governance/certification artifacts, plus standards-manifest registration updates.

## Tests that must pass after execution
1. `python -m pytest -q tests/test_wpg_comment_matrix_ingestion.py tests/test_wpg_agency_profiles.py tests/test_wpg_industry_profiles.py tests/test_wpg_critique_retrieval.py tests/test_wpg_multi_pass_critique.py`
2. `python -m pytest -q tests/test_wpg_judgment_records.py tests/test_wpg_precedent.py tests/test_wpg_judgment_eval.py`
3. `python -m pytest -q tests/test_wpg_cross_run.py tests/test_wpg_policy_profiles.py tests/test_wpg_slo.py`
4. `python -m pytest -q tests/test_phase_checkpoint.py tests/test_phase_transition.py tests/test_phase_transition_cli.py`
5. `python -m pytest -q tests/test_wpg_governance_offload.py tests/test_wpg_certification.py tests/test_wpg_contracts.py`
6. `python -m pytest -q`
7. `python scripts/run_contract_enforcement.py`
8. `python scripts/run_wpg_pipeline.py`

## Scope exclusions
- Do not change canonical system ownership definitions in `docs/architecture/system_registry.md`.
- Do not refactor unrelated module families outside WPG + contract/test surfaces.
- Do not alter dashboard front-end surfaces.

## Dependencies
- Phase A and Phase B implementation must remain intact and authoritative.
