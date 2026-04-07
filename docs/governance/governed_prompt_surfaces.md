# Governed Prompt Surfaces

## Purpose
List the prompt surfaces that are governance-controlled and their authority sources.

## Canonical authority for all governed surfaces
- `README.md`
- `docs/architecture/system_registry.md`
- `docs/governance/strategy_control_doc.md`
- `docs/governance/prompt_contract.md`
- `docs/governance/prompt_execution_rules.md`

## Governed surfaces

| Surface | Scope | Required behavior |
| --- | --- | --- |
| Roadmap prompts | sequencing and prioritization | artifact-first execution, fail-closed, certification-gated promotion |
| Architecture prompts | role boundaries and control behavior | preserve canonical role ownership, fail-closed on conflict |
| Implementation prompts | governed markdown/contracts/schemas updates | follow prompt contract and execution preflight |
| Review prompts | findings, remediation, and promotion decisions | explicit failure statements and certification gate enforcement |

## Out of scope
Pure editorial prompts that do not affect execution behavior or role ownership.

## Terminology rule
Use normalized terms across governed surfaces: execution, artifact, failure, retrieve.
