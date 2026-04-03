# Plan — BATCH-D — 2026-04-03

## Prompt type
PLAN

## Roadmap item
BATCH-D

## Objective
Harden deterministic execution identity and hashing boundaries so identical inputs produce identical IDs, hashes, and validator/control artifacts.

## Declared files
| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-BATCH-D-2026-04-03.md | CREATE | PLAN-first artifact for this multi-file BUILD scope. |
| spectrum_systems/modules/runtime/validator_engine.py | MODIFY | Remove UUID/time drift in validator execution identity and timestamps; derive deterministic IDs from canonical payloads. |
| spectrum_systems/modules/runtime/control_integration.py | MODIFY | Replace random execution_id fallback with deterministic execution_id derived from canonical context payload. |
| spectrum_systems/modules/runtime/pqx_sequence_runner.py | MODIFY | Route artifact/fingerprint hashing through canonical JSON serialization utility. |
| tests/test_validator_engine.py | MODIFY | Update determinism expectations and add 5-run determinism validation with hash/fingerprint/full output checks. |
| tests/test_control_integration.py | MODIFY | Add deterministic execution_id stability test for repeated identical inputs. |

## Scope exclusions
- No contract schema edits.
- No control policy logic changes.
- No runtime feature additions.

## Validation plan
1. `pytest tests/test_validator_engine.py`
2. `pytest tests/test_control_integration.py`
