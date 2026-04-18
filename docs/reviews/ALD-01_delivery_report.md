# ALD-01 Delivery Report

## 1) Problem statement
Shadow authority paths were possible when non-owner files emitted authority vocabulary (`decision`, `enforcement_action`, `certification_status`) or produced authority-shaped artifacts that looked like control/enforcement/certification/promotion outcomes.

## 2) Mechanisms built
- Added machine-readable canonical authority registry:
  - `contracts/governance/authority_registry.json`
- Added forbidden vocabulary rules module:
  - `scripts/authority_leak_rules.py`
- Added structural authority-shape detector:
  - `scripts/authority_shape_detector.py`
- Added fail-closed CLI guard runner with artifact emission:
  - `scripts/run_authority_leak_guard.py`

## 3) Guard integration
- Guard follows existing SRG runner pattern:
  - resolves changed files from explicit list or git diff,
  - emits deterministic JSON result artifact,
  - exits non-zero on violation.
- Output artifact:
  - `outputs/authority_leak_guard/authority_leak_guard_result.json`

## 4) Examples caught
- Non-owner file emitting `decision: allow` is blocked.
- Filename-prefix shadow files (for example `control_executor.py_shadow.py`) do not inherit canonical-owner status.
- Non-owner object combining `decision` + `enforcement_action` is blocked.
- Preparatory artifact with required non-authority assertions but hidden authority field is blocked (FXA-1100 style regression shape).
- Preparatory artifact fields are allowlist-enforced: undeclared fields (for example `closure_decision`) fail unless explicitly allowlisted by policy/registry.

## 5) Tests added
- `tests/test_authority_leak_detection.py`
  - canonical owner positive pass
  - non-owner forbidden field fail
  - disguised authority shape fail
  - FXA-1100 transcript regression fail
  - CLI fail-closed behavior
- Extended `tests/test_forbidden_authority_vocabulary_guard.py`
  - authority leak guard pass check for transcript architecture boundary doc.

## 6) Limitations
- Structural shape detection is intentionally minimal/precise and currently targets JSON/Python dictionary-like payloads.
- Non-JSON/YAML rich structures are evaluated primarily via vocabulary checks.

## 7) Future extensions
- Add optional AST flow analysis to detect computed authority fields before serialization.
- Integrate authority leak guard invocation into preflight orchestration runner once adoption matures.
