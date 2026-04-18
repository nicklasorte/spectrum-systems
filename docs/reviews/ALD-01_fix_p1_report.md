# ALD-01 Fix P1 Report

## Prompt Type
`BUILD`

## Scope
Close two P1 bypasses in the ALD-01 authority leak detection layer:
1. boundary-unsafe canonical owner matching,
2. missing preparatory allowlist enforcement.

## Root cause

### 1) Owner-path boundary bypass
- `scripts/authority_leak_rules.py` treated canonical owners as loose prefixes and substring matches.
- `forbidden_contexts.excluded_path_prefixes` used the same loose prefix semantics.
- A non-owner file such as `spectrum_systems/modules/runtime/control_executor.py_shadow.py` could be treated as owner/excluded and bypass vocabulary checks.

### 2) Preparatory allowlist bypass
- `scripts/authority_shape_detector.py` enforced required `non_authority_assertions` and authority-token checks, but did not enforce `preparatory_only.allowed_fields`.
- A preparatory artifact could include undeclared authority-like fields (for example `closure_decision`) and pass when forbidden-token heuristics did not catch it.

## Exact fixes

### A) Boundary-safe owner and scope matching
- Added normalized boundary-safe path matching in `scripts/authority_leak_rules.py`:
  - exact file match by default,
  - directory match only when registry entry explicitly ends with `/`.
- Replaced loose `startswith`/substring behavior in:
  - canonical owner detection,
  - forbidden context include/exclude matching.
- Reused the same boundary-safe matching for shape detector context scoping via `scripts/authority_shape_detector.py`.

### B) Preparatory allowlist enforcement
- Updated `scripts/authority_shape_detector.py` so any artifact declaring `non_authority_assertions` is treated as preparatory and must satisfy:
  1. required assertions present,
  2. all object fields are declared in `preparatory_only.allowed_fields`.
- Added new fail-closed violation rule:
  - `preparatory_fields_not_allowlisted`.

## Regression tests added
- `tests/test_authority_leak_detection.py`
  - `test_filename_prefix_shadow_does_not_inherit_owner_status`
  - `test_preparatory_artifact_undeclared_field_fails_allowlist`

## Validation results
- Targeted authority leak tests: pass.
- Full authority leak guard tests: pass.
- System Registry Guard tests: pass.
- System Registry Guard runner check against changed files: pass.

## Final status
Both P1 bypasses are closed with deterministic, repo-native, fail-closed enforcement.
