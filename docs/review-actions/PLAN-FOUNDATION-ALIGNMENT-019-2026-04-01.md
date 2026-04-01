# Plan — FOUNDATION-ALIGNMENT-019 (RE18 Core Bundle via PQX) — 2026-04-01

## Prompt type
PLAN

## Roadmap item
RE18-01/02/04/05/06/07/08/09/10/11/15/16/17/18/19/20

## Objective
Harden the control loop so decision authority is singular and non-bypassable, failure-binding and recurrence-prevention are mandatory, proof artifacts are deterministic, and promotion/readiness gates fail closed unless complete CL evidence is present.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| contracts/schemas/control_loop_closure_evidence_bundle.schema.json | CREATE | RE18 proof-spine canonical artifact contract for eval→control→enforcement→replay→prevention lineage. |
| contracts/schemas/recurrence_prevention_closure.schema.json | CREATE | RE18 mandatory recurrence-prevention closure contract binding failure class, remediation, regression fixture, and policy update. |
| contracts/schemas/control_loop_certification_pack.schema.json | MODIFY | Encode explicit CL hard-gate conditions and machine-checkable completeness constraints. |
| contracts/examples/control_loop_closure_evidence_bundle.json | CREATE | Golden-path example for RE18 proof bundle. |
| contracts/examples/recurrence_prevention_closure.json | CREATE | Golden-path recurrence-prevention closure example. |
| contracts/examples/control_loop_certification_pack.json | MODIFY | Align certification example with expanded mandatory CL conditions. |
| contracts/standards-manifest.json | MODIFY | Register new contracts and bump changed schema publication versions. |
| spectrum_systems/modules/runtime/control_loop_closure.py | CREATE | Deterministic authority/checking helpers for evidence closure, replay parity, trace completeness, and artifact_release_readiness gating. |
| spectrum_systems/orchestration/sequence_transition_policy.py | MODIFY | Fail closed promotion when RE18 evidence bundle / recurrence closure / readiness checks are missing. |
| tests/test_control_loop_closure.py | CREATE | Regression and falsification tests for closure checks and hard-gate fail-closed semantics. |
| tests/test_sequence_transition_policy.py | MODIFY | Validate promotion gating requires RE18 closure artifacts and blocks on malformed evidence. |
| tests/test_contracts.py | MODIFY | Validate new contracts/examples and updated certification pack example. |

## Contracts touched
- `control_loop_closure_evidence_bundle` (new)
- `recurrence_prevention_closure` (new)
- `control_loop_certification_pack` (updated hard-gate shape)
- `standards-manifest` publication update

## Tests that must pass after execution
1. `pytest tests/test_control_loop_closure.py tests/test_sequence_transition_policy.py`
2. `pytest tests/test_contracts.py tests/test_contract_enforcement.py`
3. `python scripts/run_contract_enforcement.py`
4. `python scripts/run_contract_preflight.py --paths contracts/schemas/control_loop_closure_evidence_bundle.schema.json contracts/schemas/recurrence_prevention_closure.schema.json contracts/schemas/control_loop_certification_pack.schema.json`
5. `.codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
- No roadmap table rewrites.
- No redesign of PQX execution orchestrators.
- No feature expansion beyond RE18 hardening surfaces.

## Dependencies
- Existing canonical `evaluation_control_decision` and enforcement runtime path.
- Existing PQX/transition/certification artifacts and tests.
- Authority order in `docs/architecture/strategy-control.md` and `docs/architecture/foundation_pqx_eval_control.md`.
