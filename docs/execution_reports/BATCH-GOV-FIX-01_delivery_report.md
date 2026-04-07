# BATCH-GOV-FIX-01 Delivery Report

## 1. Intent
Repair GOV-NEXT-01-03 so the existing contract preflight gate no longer blocks while preserving fail-closed governance prompt enforcement and without weakening strategy/contract gate behavior.

## 2. Root Cause of BLOCK
`run_contract_preflight.py` classified `scripts/run_prompt_with_governance.py` as a governed evaluation surface (`surface=governance`) and required deterministic evaluation mapping, but no matching test target was resolvable. This produced `missing_required_surface` for `scripts/run_prompt_with_governance.py`, which mapped to `strategy_gate_decision=BLOCK`.

Evidence from generated artifacts:
- `outputs/contract_preflight/contract_preflight_report.json` showed:
  - `missing_required_surface[0].path = scripts/run_prompt_with_governance.py`
  - `recommended_repair_areas` included `required evaluation mapping for changed governance/runtime/test surfaces`
- `outputs/contract_preflight/contract_preflight_result_artifact.json` showed `control_signal.strategy_gate_decision = BLOCK`.

## 3. Files Created
- `docs/review-actions/PLAN-BATCH-GOV-FIX-01-2026-04-07.md`
- `tests/test_run_prompt_with_governance.py`
- `docs/execution_reports/BATCH-GOV-FIX-01_delivery_report.md`
- `docs/roadmaps/NEXT_SLICE.md`
- `docs/roadmaps/SLICE_HISTORY.md`

## 4. Files Updated
- None (all changes in this repair slice were additive).

## 5. Repair Strategy Used
Minimal repo-native integration repair:
1. Preserve all GOV-NEXT-01-03 governance enforcement artifacts and fail-closed behavior.
2. Add deterministic test coverage directly for the new governed script surface (`scripts/run_prompt_with_governance.py`) via `tests/test_run_prompt_with_governance.py`.
3. Re-run preflight using the governed changed-path set from GOV-NEXT-01-03 plus the new test file to confirm `missing_required_surface` is eliminated and strategy gate moves from `BLOCK` to `ALLOW`.

No gate logic was disabled or softened.

## 6. Governance Guarantees Preserved
- Governance checker remains fail-closed: invalid prompt references still fail with non-zero exit.
- Wrapper still blocks prompt execution when preflight fails.
- Required governance references remain mandatory for valid prompts.

## 7. Contract/Preflight Alignment Achieved
- Added deterministic test mapping coverage for the governed script surface that originally triggered `missing_required_surface`.
- Local contract preflight replay over the full GOV-NEXT-01-03 surface now returns:
  - `status = passed`
  - `strategy_gate_decision = ALLOW`

## 8. Remaining Gaps
- `docs/governance/governed_prompt_surfaces.json` still does not exist; this did not block current preflight, but a future slice should establish a single governed prompt-surface registry if required by broader governance architecture.
- Prompt governance checker currently uses path-reference validation (string presence), not semantic include parsing.

## 9. Validation Performed
Commands executed:
1. `python scripts/run_contract_preflight.py --base-ref HEAD~1 --head-ref HEAD`
   - Reproduced original BLOCK with generated reports.
2. `python scripts/check_governance_compliance.py --file docs/governance/prompt_templates/roadmap_prompt_template.md`
   - PASS
3. `python scripts/check_governance_compliance.py --text "# Invalid prompt\nOnly arbitrary content"`
   - FAIL (explicit missing governance references, exit code 1)
4. `python -m pytest tests/test_governance_prompt_enforcement.py tests/test_run_prompt_with_governance.py`
   - PASS (`6 passed`)
5. `python scripts/run_contract_preflight.py --changed-path docs/architecture/strategy_guided_roadmap_prompt.md --changed-path docs/governance/README.md --changed-path docs/governance/governance_manifest.json --changed-path docs/governance/prompt_execution_rules.md --changed-path docs/governance/prompt_includes/ENFORCED_PREAMBLE.md --changed-path docs/governance/prompt_includes/source_input_loading_include.md --changed-path docs/governance/prompt_templates/architecture_review_prompt_template.md --changed-path docs/governance/prompt_templates/implementation_prompt_template.md --changed-path docs/governance/prompt_templates/roadmap_prompt_template.md --changed-path docs/governance/source_inputs_manifest.json --changed-path docs/review-actions/PLAN-BATCH-GOV-NEXT-01-03-2026-04-07.md --changed-path prompts/prompt-template.md --changed-path scripts/check_governance_compliance.py --changed-path scripts/run_prompt_with_governance.py --changed-path templates/review/claude_review_prompt_template.md --changed-path tests/test_governance_prompt_enforcement.py --changed-path tests/test_run_prompt_with_governance.py`
   - PASS with `strategy_gate_decision = ALLOW`

## 10. Next Recommended Slice
Execute **BATCH-GOV-FIX-02 — Governed Prompt Surface Registry Integration**:
- add `docs/governance/governed_prompt_surfaces.json`,
- register prompt includes/templates/seams,
- add deterministic sync test so future governance prompt surfaces cannot drift out of preflight visibility.
