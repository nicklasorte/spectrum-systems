# Implementation Governance Include (Reusable)

> Mandatory include for Codex BUILD/WIRE prompts that affect roadmap, control, eval, governance, promotion, or trust boundaries.

## Required authority inputs
- `docs/governance/strategy_control_doc.md`
- `docs/governance/prompt_contract.md`
- Any workflow-specific governance doc from `docs/governance/governance_manifest.json`

## Implementation obligations
- **Strategy invariants:** changes must preserve artifact-first, schema-first, eval-mandatory, fail-closed, replayable, and certification-gated behavior.
- **No hidden contracts:** every new produced/consumed artifact must map to an explicit schema or declared document contract.
- **Schema/test discipline:** when contracts are touched, add or update tests and validation commands tied to changed scope.
- **Explicit failure modes:** describe expected fail states, stop conditions, and operator-visible outputs.
- **Observability:** emit deterministic evidence or logs required for post-run drift and trust review.
- **Control-loop integration path:** identify Observe/Interpret/Decide/Enforce touchpoints and artifact handoff path.
- **No bypasses:** do not introduce direct or implicit bypasses around eval, trace, policy, certification, or enforcement gates.

## Delivery report requirements
Implementation delivery report must include:
- changed files and declared scope match,
- invariants preserved,
- failure modes introduced/updated,
- observability outputs,
- control-loop integration impact,
- residual risks and blocked follow-ups.
