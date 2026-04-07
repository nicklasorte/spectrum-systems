# Action Tracker

## Critical Items
| ID | Risk | Severity | Recommended Action | Status | Notes |
| --- | --- | --- | --- | --- | --- |
| CR-1 | Ensure trigger guardrails remain fail-closed | Critical | Preserve event/command/pr guardrails for governed ingestion | Open | governance boundary |

## High-Priority Items
| ID | Risk | Severity | Recommended Action | Status | Notes |
| --- | --- | --- | --- | --- | --- |
| HI-1 | Ingested trigger body must remain deterministic: /roadmap-approve draft_id:RMD-410E97243FCF55B9 | High | Keep deterministic normalization and pathing | Open | command=/roadmap-approve |

## Medium-Priority Items
| ID | Risk | Severity | Recommended Action | Status | Notes |
| --- | --- | --- | --- | --- | --- |
| MI-1 | Preserve RIL-only structuring boundary | Medium | Do not add closure/repair logic to ingestion | Open | role-boundary |

## Blocking Items
- CR-1 blocks governance bypass.
