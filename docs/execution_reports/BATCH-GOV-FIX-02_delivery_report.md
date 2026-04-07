# BATCH-GOV-FIX-02 Delivery Report

## 1. Intent
Implement a canonical, repo-native governed prompt surface registry and synchronize governance checker + contract preflight visibility so prompt surface drift fails closed.

## 2. Files Created
- `docs/review-actions/PLAN-BATCH-GOV-FIX-02-2026-04-07.md`
- `docs/governance/governed_prompt_surfaces.json`
- `docs/governance/governed_prompt_surfaces.md`
- `docs/governance/ci_enforcement.md`
- `tests/test_governed_prompt_surface_sync.py`

## 3. Files Updated
- `scripts/check_governance_compliance.py`
- `scripts/run_contract_preflight.py`
- `tests/test_governance_prompt_enforcement.py`
- `docs/governance/README.md`
- `docs/roadmaps/NEXT_SLICE.md`
- `docs/roadmaps/SLICE_HISTORY.md`

## 4. Canonical Registry Established
- Canonical registry path: `docs/governance/governed_prompt_surfaces.json`.
- Registry includes explicit surface metadata (`surface_id`, `prompt_class`, `path_globs`, `requires_governance_check`, `required_references`, `required_includes_or_templates`, `checked_by`, `notes`).
- Surfaces covered: roadmap prompts, implementation prompts, architecture review prompts, reusable prompt templates, governance prompt includes.

## 5. Enforcement Alignment Achieved
- Governance checker now loads and classifies prompt files via canonical registry.
- Contract preflight now recognizes registry-covered prompt files as `governed_prompt_surface` required evaluation paths.
- Added deterministic sync test to ensure checker and preflight stay aligned.

## 6. Drift Risks Reduced
- New governed prompt candidates in known prompt/include/template seams are required to map to the registry.
- Mismatch between checker and preflight surface taxonomy is now test-blocking.
- Structural incoherence in registry-required references/includes is now test-blocking.

## 7. Remaining Gaps
- Registry currently focuses on markdown prompt artifacts and known prompt seams; if new prompt-bearing file types are introduced, the registry must be explicitly expanded.

## 8. Validation Performed
1. `python -m json.tool docs/governance/governed_prompt_surfaces.json`
2. `python scripts/check_governance_compliance.py --file docs/governance/prompt_templates/roadmap_prompt_template.md`
3. `python scripts/check_governance_compliance.py --text "# Invalid prompt\nOnly arbitrary content"`
4. `python -m pytest tests/test_governance_prompt_enforcement.py tests/test_governed_prompt_surface_sync.py`
5. `python scripts/run_contract_preflight.py --changed-path docs/governance/governed_prompt_surfaces.json --changed-path docs/governance/prompt_templates/roadmap_prompt_template.md --changed-path scripts/check_governance_compliance.py --changed-path scripts/run_contract_preflight.py --changed-path tests/test_governance_prompt_enforcement.py --changed-path tests/test_governed_prompt_surface_sync.py`

## 9. Next Recommended Slice
Tighten CI integration by adding a dedicated governance prompt-surface drift gate job that runs `tests/test_governed_prompt_surface_sync.py` and checker validation on changed governed prompt files only.
