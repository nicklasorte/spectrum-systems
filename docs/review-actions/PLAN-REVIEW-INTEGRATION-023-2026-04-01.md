# Plan — REVIEW-INTEGRATION-023 — 2026-04-01

## Prompt type
PLAN

## Roadmap item
REVIEW-INTEGRATION-023 (Review-as-Control-Signal Integration)

## Objective
Convert repo-native markdown review outputs into a governed `review_control_signal` artifact that is consumed by runtime control, promotion gating, PQX roadmap eligibility, and fail-closed sequencing without introducing parallel authority paths.

## Declared files
| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-REVIEW-INTEGRATION-023-2026-04-01.md | CREATE | Required plan-first governance artifact for this multi-file wiring slice. |
| contracts/schemas/review_control_signal.schema.json | CREATE | New governed contract for machine-readable review control signal output. |
| contracts/examples/review_control_signal.json | CREATE | Golden-path example for contract and downstream tests. |
| contracts/standards-manifest.json | MODIFY | Register new governed artifact under existing review taxonomy with schema/example metadata. |
| spectrum_systems/modules/runtime/review_signal_extractor.py | CREATE | Deterministic fail-closed markdown review parser and review control signal producer. |
| spectrum_systems/modules/runtime/evaluation_control.py | MODIFY | Consume optional review control signal in canonical control decision while preserving stronger existing blocks. |
| spectrum_systems/orchestration/sequence_transition_policy.py | MODIFY | Fail-closed promotion gating on required/missing/failing review control signals and scale recommendation NO expansion blocking. |
| spectrum_systems/orchestration/roadmap_eligibility.py | MODIFY | Integrate review control signal into strategy/eligibility seams for expansion constraints and finding propagation. |
| tests/test_review_signal_extractor.py | CREATE | Unit tests for markdown parsing, malformed fail-closed behavior, determinism, and schema-valid signal output. |
| tests/test_sequence_transition_policy.py | MODIFY | Add promotion gate tests for review FAIL, scale NO, missing required signal, and non-bypass precedence. |
| tests/test_roadmap_eligibility.py | MODIFY | Add planning/eligibility tests showing review signal influence and expansion blocking behavior. |
| tests/test_contracts.py | MODIFY | Add review_control_signal example/schema validation coverage. |
| tests/test_evaluation_control.py | MODIFY | Add review signal consumption tests proving additive blocking/no-bypass/missing-required fail-closed behavior. |

## Seams impacted
- Runtime observe/interpret seam (`review markdown -> review_control_signal`).
- Runtime decide seam (`evaluation_control_decision` additive review signal logic).
- Promotion enforcement seam (`sequence_transition_policy` promotion authority checks).
- PQX roadmap planning seam (`roadmap_eligibility` strategy status and blocked reasons).

## Contract surfaces impacted
- New contract: `review_control_signal` schema + example.
- Standards registry entry in `contracts/standards-manifest.json`.
- Existing `evaluation_control_decision` consumption logic only (no schema weakening).

## Validation steps
1. `pytest tests/test_review_signal_extractor.py tests/test_evaluation_control.py tests/test_sequence_transition_policy.py tests/test_roadmap_eligibility.py tests/test_contracts.py -q`
2. `python scripts/run_contract_enforcement.py`
3. `python scripts/run_contract_preflight.py --output-dir outputs/contract_preflight --changed-path contracts/schemas/review_control_signal.schema.json --changed-path contracts/examples/review_control_signal.json --changed-path contracts/standards-manifest.json --changed-path spectrum_systems/modules/runtime/review_signal_extractor.py --changed-path spectrum_systems/modules/runtime/evaluation_control.py --changed-path spectrum_systems/orchestration/sequence_transition_policy.py --changed-path spectrum_systems/orchestration/roadmap_eligibility.py --changed-path tests/test_review_signal_extractor.py --changed-path tests/test_evaluation_control.py --changed-path tests/test_sequence_transition_policy.py --changed-path tests/test_roadmap_eligibility.py --changed-path tests/test_contracts.py`
4. `PLAN_FILES='docs/review-actions/PLAN-REVIEW-INTEGRATION-023-2026-04-01.md contracts/schemas/review_control_signal.schema.json contracts/examples/review_control_signal.json contracts/standards-manifest.json spectrum_systems/modules/runtime/review_signal_extractor.py spectrum_systems/modules/runtime/evaluation_control.py spectrum_systems/orchestration/sequence_transition_policy.py spectrum_systems/orchestration/roadmap_eligibility.py tests/test_review_signal_extractor.py tests/test_evaluation_control.py tests/test_sequence_transition_policy.py tests/test_roadmap_eligibility.py tests/test_contracts.py' .codex/skills/verify-changed-scope/run.sh`
5. `pytest -q`

## Expected blocking/fail-closed behavior
- Malformed/ambiguous markdown reviews fail closed in extractor.
- Promotion blocks when review signal is required but missing/unreadable/invalid.
- Promotion blocks on `gate_assessment=FAIL` and expansion transitions block on `scale_recommendation=NO`.
- Review PASS cannot override stronger existing block/freeze/deny/require_review signals.
- Roadmap eligibility blocks expansion slices when trusted review signal forbids scaling.

## Known risks before implementation
- Historical `docs/reviews/*.md` have mixed formats; extractor must explicitly support only canonical frontmatter shape and reject ambiguous artifacts.
- Standards manifest insertion must preserve formatting/order expected by contract/manifest validators.
- Any additive blocked reason in roadmap eligibility must be reflected in schema enum to avoid contract-preflight BLOCK.
