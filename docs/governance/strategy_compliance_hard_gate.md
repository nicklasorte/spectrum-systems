# Strategy Compliance Hard Gate

Fail-closed progression gate for roadmap/review/progression artifacts.

## Gate Inputs
- strategy reference
- source grounding references
- schema validation evidence
- eval coverage evidence
- replayability evidence
- observability/drift evidence
- control decision evidence
- certification evidence (when promotion is requested)
- judgment artifact (when required by policy)

## Hard Gate Checklist (YES/NO)
| Gate | Required evidence | Critical |
| --- | --- | --- |
| Strategy alignment verified? | Explicit strategy ref + invariant checks | YES |
| Source grounding verified? | At least one valid source ref + enforcement purpose | YES |
| Schema discipline satisfied? | Contract/schema validation pass | YES |
| Replayability satisfied? | Replay or equivalent deterministic rerun evidence | YES |
| Eval coverage satisfied? | Eval results or validation evidence for changed scope | YES |
| Observability present? | Drift/health summary or equivalent governed observability artifact | YES |
| Control enforcement present? | Explicit allow/block/remediate decision artifact | YES |
| Certification ready (if applicable)? | GOV-10/done certification evidence | YES |
| Judgment present (if required)? | Judgment artifact linked to progression decision | YES |
| Drift detection run? | Drift report covering strategy/source/control bypass checks | YES |

## Stop Rule
If **any critical item = NO**, progression **MUST STOP**.

## Required Recorded Fields
For each gate decision record:
- `strategy_ref`
- `source_refs`
- `failed_checks`
- `blocking_reason`
- `next_required_artifact`
