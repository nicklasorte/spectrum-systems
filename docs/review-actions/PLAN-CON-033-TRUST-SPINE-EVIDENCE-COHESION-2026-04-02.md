# Plan — CON-033 TRUST-SPINE EVIDENCE CHAIN COHESION — 2026-04-02

## Prompt type
PLAN

## Roadmap item
CON-033 — Trust-spine evidence chain cohesion

## Objective
Add a deterministic fail-closed trust-spine evidence cohesion artifact/evaluator and wire it into promotion, done certification, and contract preflight gates so contradictory or missing trust-spine evidence blocks downstream decisions.

## Declared files
| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-CON-033-TRUST-SPINE-EVIDENCE-COHESION-2026-04-02.md | CREATE | Required plan-first artifact for multi-file contract/module/wiring change. |
| PLANS.md | MODIFY | Register CON-033 plan entry. |
| contracts/schemas/trust_spine_evidence_cohesion_result.schema.json | CREATE | New governed contract for machine-readable cohesion proof. |
| contracts/examples/trust_spine_evidence_cohesion_result.json | CREATE | Golden-path example for cohesion artifact. |
| contracts/schemas/done_certification_record.schema.json | MODIFY | Allow additive cohesion check/result + input ref in done certification record. |
| contracts/examples/done_certification_record.json | MODIFY | Keep example aligned with updated done certification schema. |
| contracts/standards-manifest.json | MODIFY | Pin/register new trust_spine_evidence_cohesion_result contract version. |
| spectrum_systems/modules/runtime/trust_spine_evidence_cohesion.py | CREATE | Pure evaluator for deterministic cross-artifact cohesion checks. |
| scripts/run_trust_spine_evidence_cohesion.py | CREATE | Thin CLI wrapper for evaluator input loading, invocation, output writing, and exit-code gating. |
| spectrum_systems/orchestration/sequence_transition_policy.py | MODIFY | Promotion seam consumes cohesion artifact and fails closed on missing/malformed/BLOCK cohesion results when provided. |
| spectrum_systems/modules/governance/done_certification.py | MODIFY | Done certification consumes/evaluates cohesion result, records machine-readable result, and blocks on cohesion failures. |
| scripts/run_contract_preflight.py | MODIFY | Narrow preflight wiring to require/consume cohesion proof on active trust-spine surface changes and propagate deterministic BLOCK. |
| tests/test_trust_spine_evidence_cohesion.py | CREATE | Direct evaluator coverage for pass/block/malformed/determinism cases. |
| tests/test_sequence_transition_policy.py | MODIFY | Regression coverage for promotion behavior with cohesion gating. |
| tests/test_done_certification.py | MODIFY | Regression coverage for done certification cohesion consumption/evaluation behavior. |
| tests/test_contract_preflight.py | MODIFY | Regression coverage for preflight trust-spine cohesion blocking path. |
| tests/test_contracts.py | MODIFY | Ensure new schema/example/manifest registration validation remains covered. |

## Contracts touched
- Create `trust_spine_evidence_cohesion_result` schema and example (`1.0.0`).
- Add additive fields to `done_certification_record` schema (`1.0.0` remains valid with backward-compatible field additions).
- Update `contracts/standards-manifest.json` with new contract registration entry for `trust_spine_evidence_cohesion_result`.

## Tests that must pass after execution
1. `pytest -q tests/test_trust_spine_evidence_cohesion.py tests/test_sequence_transition_policy.py tests/test_done_certification.py tests/test_contract_preflight.py tests/test_contracts.py`
2. `.codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
- Do not redesign existing trust-spine invariant logic beyond additive cohesion checks.
- Do not introduce broad artifact auto-discovery or filesystem crawling.
- Do not modify unrelated roadmap files or non-trust-spine governance flows.
- Do not weaken existing promotion/certification/preflight gating semantics.

## Dependencies
- CON-029 control surface manifest baseline must remain authoritative.
- CON-030 enforcement result semantics must remain authoritative.
- CON-031 obedience result semantics must remain authoritative.
- CON-032 preflight/path hardening must remain authoritative.
