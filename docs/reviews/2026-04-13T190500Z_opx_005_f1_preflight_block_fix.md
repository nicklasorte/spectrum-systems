# OPX-005-F1 Preflight Block Fix — 2026-04-13T190500Z

## 1. Exact blocker found
- Preflight block category: `MALFORMED_PQX_TASK_WRAPPER` in governed PQX required-context enforcement.
- Report evidence showed wrapper load failure (`No such file or directory`) while wrapper path was supplied.
- Concurrent contract surface failure existed: schema/example mismatch for `opx_005_integration_artifact` (`artifact_class` rejected by schema).

## 2. Root cause
1. Wrapper resolution/load path gap in `scripts/run_contract_preflight.py`:
   - wrapper path was read directly from CLI value without canonical repo-relative normalization and without auto-build recovery when missing.
   - missing wrapper was classified as malformed late in decision flow, causing broad BLOCK.
2. Contract schema mismatch:
   - OPX-005 example included `artifact_class`, but schema had `additionalProperties: false` and no `artifact_class` property.

## 3. Files changed
- `scripts/run_contract_preflight.py`
- `contracts/schemas/opx_005_integration_artifact.schema.json`
- `tests/test_contract_preflight.py`

## 4. Canonical fix applied
- Added canonical wrapper path normalization (`_resolve_wrapper_path`) and automatic governed wrapper build attempt (`_attempt_build_missing_wrapper`) before required-context evaluation.
- Added explicit blocker classifier enhancement for auto-build failure (`MISSING_PQX_TASK_WRAPPER_AUTO_BUILD_FAILED`) while preserving fail-closed behavior.
- Updated OPX-005 schema to accept canonical `artifact_class: coordination` used by the example contract payload.

## 5. Earlier/automatic prevention added
- Preflight now attempts deterministic wrapper regeneration via `scripts/build_preflight_pqx_wrapper.py` when wrapper path is provided but file is missing.
- Preflight report now includes `changed_path_detection.pqx_wrapper_resolution` so wrapper build attempts and outcomes are visible early.
- Added regression tests to verify path normalization and automatic missing-wrapper recovery behavior.

## 6. Tests and validation run
- `pytest -q tests/test_contract_preflight.py`
- `python scripts/run_contract_preflight.py --base-ref e192cb19f063117b428b7ff0d1bf5155e948b1cc --head-ref 54b953e1bdec2a7db4347aa75fed7d4e35df1459 --output-dir outputs/contract_preflight --execution-context pqx_governed --pqx-wrapper-path outputs/contract_preflight/preflight_pqx_task_wrapper.json --authority-evidence-ref artifacts/pqx_runs/preflight.pqx_slice_execution_record.json`
- `pytest tests/test_contract_bootstrap.py -q`
- `pytest tests/test_contracts.py tests/test_contract_enforcement.py -q`

## 7. Remaining seams
- Preflight still degrades to fallback changed-path resolution when base/head SHAs are unavailable in local-only runs; this remains fail-closed and explicitly surfaced via detection metadata.
