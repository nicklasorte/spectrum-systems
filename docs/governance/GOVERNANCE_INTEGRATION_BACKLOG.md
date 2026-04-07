# Governance Integration Backlog

Purpose: prioritize next governance-activation slices after BATCH-GOV-01.

## Ranking method
- Priority P0 blocks trustworthy expansion.
- Priority P1 materially improves enforcement confidence.
- Priority P2 improves operational ergonomics and auditability.

## Backlog (dependency-aware)

| Rank | ID | Priority | Depends on | Work item | Outcome |
| --- | --- | --- | --- | --- | --- |
| 1 | GOV-NEXT-01 | P0 | BATCH-GOV-01 | Wire roadmap generators/prompts to always include `docs/governance/strategy_control_doc.md` + roadmap include. | Prevent authority omission and sequencing drift at generation time. |
| 2 | GOV-NEXT-02 | P0 | GOV-NEXT-01 | Add review artifact template fields for invariant checks, drift severity, and fix-before-expand decisions. | Make architecture and roadmap reviews governance-complete by default. |
| 3 | GOV-NEXT-03 | P0 | GOV-NEXT-02 | Add preflight check that governance-critical prompts reference required governance inputs. | Fail closed when prompt authority loading is missing. |
| 4 | GOV-NEXT-04 | P1 | GOV-NEXT-02 | Link governance checklist outputs to certification/promotion gate inputs. | Ensure promotion decisions consume governance evidence. |
| 5 | GOV-NEXT-05 | P1 | GOV-NEXT-03 | Add control decision schema linkage for drift severity outcomes (`warning/freeze/block`). | Convert drift results into enforceable control-loop decisions. |
| 6 | GOV-NEXT-06 | P1 | GOV-NEXT-03 | Implement ADR/supersession workflow for authority-order or invariant reinterpretation changes. | Eliminate silent policy rewrites and preserve authority history. |
| 7 | GOV-NEXT-07 | P2 | GOV-NEXT-03 | Add CI lint checks for mandatory governance references in prompt templates and roadmap-generation docs. | Automated baseline compliance signal in PRs. |
| 8 | GOV-NEXT-08 | P2 | GOV-NEXT-04, GOV-NEXT-05 | Build governance observability dashboard slice for drift trends and unresolved blocking signals. | Improves measurability and operator trust in governance posture. |

## Immediate recommended next slice
Execute **GOV-NEXT-01 + GOV-NEXT-03** as a paired enforcement cut:
1. hard-wire required governance includes into roadmap-generation templates,
2. add fail-closed preflight check for missing governance references.

This yields the highest near-term reduction in governance drift risk with minimal framework overhead.
