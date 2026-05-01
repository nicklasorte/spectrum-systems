# APU-3LS-01 fix actions

## Admission (AEX-style)
- Request type and intended outcome: BUILD; harden agent PR update readiness so repo-mutating work is not marked ready without artifact-backed CLP+AGL/3LS evidence.
- Changed surfaces (planned): `scripts/check_agent_pr_update_ready.py`, runtime policy module, schema/example/manifest entries for `agent_pr_update_ready_result`, governance policy, focused tests, and review docs.
- Authority-shape risks: accidental authority leakage in wording or readiness logic crossing APU observation boundary.
- Required tests/evals: targeted pytest for APU/update readiness + contracts validation tests.
- Required schema/artifact updates: add/update `agent_pr_update_ready_result` contract + example and wire into standards manifest.
- Required governance mappings: update `docs/governance/agent_pr_update_policy.json` for allowed warn codes and optional out-of-scope legs.
- Required replay/observability updates: include deterministic evidence/source refs and optional hash field in result.
- Scope split check: bounded to APU readiness guard, schema/example/policy/tests/review docs only.

## Planned fix checklist
- [ ] FIND-01: Implement APU repo-mutating fail-closed evidence checks in script/module.
- [ ] FIND-02: Add/extend `agent_pr_update_ready_result` schema and examples.
- [ ] FIND-03: Add governance policy for allowed CLP warn reason codes and leg scope rules.
- [ ] FIND-04: Add tests for required failure/readiness modes and evidence validation constraints.
- [ ] FIND-05: Add red-team review report and record dispositions here.

## Finding resolution log
| finding_id | file_changed | test_added_or_updated | command_run | disposition |
|---|---|---|---|---|
| MF-01..MF-04 | scripts/check_agent_pr_update_ready.py; spectrum_systems/modules/runtime/agent_pr_update_policy.py; contracts/schemas/agent_pr_update_ready_result.schema.json; contracts/examples/agent_pr_update_ready_result.example.json; docs/governance/agent_pr_update_policy.json; tests/test_agent_pr_update_ready.py; docs/reviews/APU-3LS-01_redteam.md | tests/test_agent_pr_update_ready.py | pytest tests/test_agent_pr_update_ready.py -q | resolved |
