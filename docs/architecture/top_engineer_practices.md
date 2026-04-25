# Top Engineer Practices for 3LS Governance

## Purpose
This doctrine converts top-engineer execution practices into explicit 3LS governance requirements with fail-closed checks, schema-bound artifacts, and promotion gates.

## Canonical mapping to 3LS governance

| # | Practice | 3LS governance mapping | Pass condition | Fail condition |
| --- | --- | --- | --- | --- |
| 1 | Kill Complexity Early | Every system declares simplified core loop impact in `loop_strengthened`; duplicate/no-op systems are audited by removable-system audit. | System maps to a core loop strengthening action or explicit bounded justification. | Loop effect missing or vague. |
| 2 | Build Fewer, Stronger Loops | Mapping record must bind each system to at least one strengthened loop and signal. | `loop_strengthened.core_loop_strengthened=true` or non-empty bounded justification. | No loop strengthening and no justification. |
| 3 | Optimize for Debuggability | `debugability_surface`, near-miss capture, and dashboard detection/control fields are required. | Deterministic traces, alerts, replay hooks, and debug entry points are declared. | No debug surface or no detection mechanism. |
| 4 | Treat Unknown States as Bugs | Unknown states must be blocked/escalated, never silently allowed. | `unknown_state_policy.silent_allowed=false` and mode in `{block, escalate}`. | Silent unknown-state acceptance allowed. |
| 5 | Invest in Real Test Data | `test_data_sources` required per system; bad-input and chaos campaign registries are governed artifacts. | Real and adversarial sources are named with ownership/freshness. | Missing or synthetic-only data claims without source artifacts. |
| 6 | Separate System Truth from Intent | Doctrine requires artifact truth (observed) separated from intent (declared) through dashboard + near-miss and campaign records. | Truth artifacts contain observed signal and control response; intent tracked separately in planning docs. | Intent statements used as truth evidence. |
| 7 | Enforce Promotion Discipline | Promotion requirements must include eval/policy/replay evidence in mapping and checker. | `promotion_requirements.eval_required=true`, `policy_required=true`, `replay_required=true`. | Any promotion path missing eval/policy/replay requirement. |
| 8 | Design for Rollback First | Rollback path is required for each system and audited in checker. | Non-empty rollback plan with trigger and execution owner. | Missing rollback path. |
| 9 | Minimize Human Intervention | Human intervention points must be explicit artifacts. | Every required intervention includes a generated artifact record. | Manual step exists without artifact capture. |
| 10 | Design for Scale Failure | Each system must declare scale-failure mode and controls. | `scale_failure_mode` contains trigger, impact, and control response. | Scale-failure mode absent. |

## Immediate recommendation enforcement

| Recommendation | Enforced artifact/check |
| --- | --- |
| Add Chaos Testing | `chaos_campaign_record` schema/example + `docs/testing/chaos_campaigns.md`. |
| Run Bad Input Campaigns | `bad_input_campaign_record` schema/example + `docs/testing/bad_input_campaigns.md`. |
| Track Near Misses | `near_miss_record` schema/example + dashboard signal linkage. |
| Build Failure Mode Dashboard | `failure_mode_dashboard_record` schema/example + `docs/reviews/top_failure_modes.md`. |
| Remove One System audit | `scripts/audit_removable_systems.py` + `docs/reviews/removable_3ls_systems_audit.md`. |

## Enforcement artifacts
- `contracts/schemas/top_engineer_practice_mapping_record.schema.json`
- `contracts/examples/top_engineer_practice_mapping_record.example.json`
- `scripts/check_top_engineer_practices.py`
- `scripts/audit_removable_systems.py`
- `tests/test_top_engineer_practices_enforcement.py`

## Governance pass/fail rubric

### Pass
- All active 3LS systems are present in mapping artifact.
- No silent unknown states.
- Promotion requires eval/policy/replay evidence.
- Every system has rollback path, debug surface, and declared scale-failure mode.
- Human-required interventions are fully artifact-captured.

### Fail
- Any required field absent or blank for an active system.
- Unknown states are silently allowed.
- Promotion path omits eval/policy/replay.
- Missing rollback/scale-failure declarations.
- Uncaptured human intervention exists.
