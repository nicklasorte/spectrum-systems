# Plan — REVIEW-INTEGRATION-023 — 2026-04-01

## Prompt type
PLAN

## Roadmap item
REVIEW-INTEGRATION-023 — Review-as-Control-Signal Integration

## Objective
Convert repo-native review markdown artifacts into a governed control signal artifact that is consumed by control, promotion, PQX, and roadmap eligibility seams with fail-closed behavior.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-REVIEW-INTEGRATION-023-2026-04-01.md | CREATE | Required plan-first artifact for multi-file governance + contract work. |
| spectrum_systems/modules/runtime/review_signal_extractor.py | CREATE | Deterministic review markdown → review_control_signal producer. |
| spectrum_systems/modules/runtime/evaluation_control.py | MODIFY | Integrate review signal as additive fail-closed control signal source. |
| spectrum_systems/orchestration/sequence_transition_policy.py | MODIFY | Promotion/transition fail-closed gating on review_control_signal and scale recommendation. |
| spectrum_systems/orchestration/roadmap_eligibility.py | MODIFY | Consume review signals in roadmap eligibility and block expansion when review scale recommendation is NO. |
| contracts/schemas/review_control_signal.schema.json | CREATE | Governed schema for new review-derived control artifact. |
| contracts/examples/review_control_signal.json | CREATE | Golden-path example for review_control_signal contract. |
| contracts/standards-manifest.json | MODIFY | Register review_control_signal contract with existing taxonomy (`review`). |
| tests/test_review_signal_extractor.py | CREATE | Validate deterministic extraction + malformed-review fail-closed behavior. |
| tests/test_review_control_integration.py | CREATE | Validate evaluation-control integration and non-bypass semantics. |
| tests/test_sequence_transition_policy.py | MODIFY | Add promotion gating coverage for review_control_signal and required-missing-signal fail-closed rules. |
| tests/test_roadmap_eligibility.py | MODIFY | Add roadmap feedback-loop tests for review signals and expansion constraints. |

## Contracts touched
- `contracts/schemas/review_control_signal.schema.json` (new, version 1.0.0)
- `contracts/standards-manifest.json` (register new artifact contract entry)

## Tests that must pass after execution
1. `pytest tests/test_review_signal_extractor.py tests/test_review_control_integration.py tests/test_sequence_transition_policy.py tests/test_roadmap_eligibility.py`
2. `python scripts/run_contract_enforcement.py`
3. `python scripts/run_contract_preflight.py --base-ref HEAD~1 --head-ref HEAD --output-dir outputs/contract_preflight`
4. `.codex/skills/verify-changed-scope/run.sh`
5. `pytest`

## Scope exclusions
- Do not redesign PQX architecture or add a parallel decision authority.
- Do not weaken fail-closed schema or policy gates to achieve green checks.
- Do not modify unrelated roadmap execution documents beyond consumed seams.
- Do not introduce a new artifact_class taxonomy value.

## Dependencies
- Existing `review_artifact` markdown frontmatter conventions and `docs/reviews/*` structure remain authoritative review input shape.
- Existing promotion authority chain in `spectrum_systems/orchestration/sequence_transition_policy.py` must remain stronger-precedence with additive review blocking only.
