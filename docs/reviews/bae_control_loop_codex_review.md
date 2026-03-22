# BAE Control-Loop Decision Path — Surgical Implementation Review (Codex)

**Date:** 2026-03-22  
**Scope reviewed:**
- `spectrum_systems/modules/runtime/evaluation_control.py`
- `spectrum_systems/modules/runtime/evaluation_budget_governor.py`
- `spectrum_systems/modules/runtime/evaluation_control_loop.py` (not present in repository)
- `contracts/schemas/evaluation_budget_decision.schema.json`

## Decision
FAIL

## Critical Findings (max 5)

1. **Decision translation logic is duplicated with divergent response vocabularies.**
   - **What is wrong:** `evaluation_control.py` defines canonical status→response mapping (`healthy/warning/exhausted/blocked` → `allow/warn/freeze/block`) via `STATUS_RESPONSE_MAP` + `map_status_to_response`, while `evaluation_budget_governor.py` also defines a separate status→response mapper (`determine_system_response`) that returns a different response set (`allow_with_warning`, `freeze_changes`, `block_release`, `require_review`).
   - **Why it is dangerous:** This is “same concept, slightly different implementation” drift. Two mappers can evolve independently, reintroducing contradictory actions for the same status and creating ambiguity in enforcement behavior.
   - **Location:** `evaluation_control.py` (`STATUS_RESPONSE_MAP`, `map_status_to_response`) and `evaluation_budget_governor.py` (`determine_system_response`).
   - **Realistic failure scenario:** A status of `warning` produces `warn` in control-loop path but `allow_with_warning` in legacy governor path. A downstream consumer wired to one vocabulary interprets the other incorrectly or treats it as unknown, yielding inconsistent gating.

2. **Schema permits two incompatible decision dialects under the same contract (`oneOf`), preserving ambiguity at integration boundaries.**
   - **What is wrong:** `evaluation_budget_decision.schema.json` validates both legacy and control-loop forms, each with different `system_response` enums and field sets.
   - **Why it is dangerous:** A payload can be schema-valid while still being semantically incompatible with consumers expecting the canonical control-loop response vocabulary. This weakens single-source determinism and can lead to ambiguous or downgraded enforcement when adapters normalize loosely.
   - **Location:** `contracts/schemas/evaluation_budget_decision.schema.json` (`oneOf` with `$defs.legacy_budget_decision` and `$defs.control_loop_budget_decision`).
   - **Realistic failure scenario:** An integration expecting `warn/freeze/block` receives a valid legacy `allow_with_warning` artifact and maps unknown responses to permissive handling or non-blocking defaults.

3. **Control-loop module path in scope does not exist, creating an unverified adapter boundary in the decision path.**
   - **What is wrong:** `spectrum_systems/modules/runtime/evaluation_control_loop.py` is absent; operational control-loop wiring appears in `scripts/run_evaluation_control_loop.py` instead.
   - **Why it is dangerous:** Missing expected module-level integration surface increases the chance of unnoticed adapter drift and duplicate mapping logic being introduced outside the reviewed path.
   - **Location:** Requested file path missing; active orchestration seen in `scripts/run_evaluation_control_loop.py`.
   - **Realistic failure scenario:** Future changes implement another loop adapter at module level with different status/response conversions, producing conflicting enforcement results for identical monitor summaries.

## Required Fixes

1. **Unify status→system_response mapping to one runtime source of truth for budget decisions.**
   - Make `evaluation_budget_governor.determine_system_response` delegate to canonical mapping (or remove it in control-loop path), and explicitly separate any legacy translation layer.

2. **Remove ambiguity from the budget-decision contract at the control-loop boundary.**
   - Split legacy and control-loop schemas (or introduce a required explicit discriminator) so control-loop consumers validate only canonical control-loop response values.

3. **Create/restore explicit module-level control-loop integration surface or update references.**
   - Either add `spectrum_systems/modules/runtime/evaluation_control_loop.py` as the canonical adapter or update all references/tests to a single known path and enforce no duplicate adapters.

## Optional Improvements

- In `build_validation_budget_decision`, pin and emit an explicit constant schema version field for provenance parity with other decisions.
- Add a narrow contract test that rejects legacy `system_response` values (`allow_with_warning`, `freeze_changes`, `block_release`, `require_review`) in control-loop-only ingestion paths.

## Trust Assessment
NO.

BAE is close to fail-closed in direct malformed/unknown-status handling, but the current slice still allows **decision-model ambiguity and duplicated translation logic** across runtime + schema boundaries. Until the mapping and contract dialects are unified or explicitly discriminated, this path cannot be fully trusted to avoid ambiguous behavior.

## Failure Mode Summary
The worst realistic failure is **cross-path semantic drift**: two schema-valid budget decisions representing the same status produce different `system_response` vocabularies, and a downstream adapter interprets the non-canonical value permissively or inconsistently. This yields non-deterministic release gating outcomes across environments for equivalent input signals.
