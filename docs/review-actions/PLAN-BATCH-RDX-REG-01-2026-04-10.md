# Plan — BATCH-RDX-REG-01 — 2026-04-10

## Prompt type
VALIDATE

## Scope
Formalize and enforce the canonical governed execution hierarchy (`slice → batch → umbrella → roadmap`) as a registry + contract/validation hardening change with fail-closed behavior and mandatory red-team review.

## Files in scope
| File | Action | Purpose |
| --- | --- | --- |
| `docs/architecture/system_registry.md` | MODIFY | Add canonical execution hierarchy, cardinality constraints, ownership clarifications, and progression-vs-closure authority boundaries. |
| `spectrum_systems/modules/runtime/roadmap_selector.py` | MODIFY | Enforce fail-closed hierarchy cardinality checks for roadmap/system roadmap execution inputs. |
| `spectrum_systems/modules/runtime/roadmap_executor.py` | MODIFY | Enforce hierarchy cardinality checks before batch execution progression. |
| `spectrum_systems/modules/runtime/roadmap_execution_loop_validator.py` | MODIFY | Enforce hierarchy cardinality checks in roadmap loop validation path. |
| `spectrum_systems/modules/runtime/execution_hierarchy.py` | ADD | Minimal shared validation layer for non-degenerate batch/umbrella hierarchy checks. |
| `tests/test_execution_hierarchy.py` | ADD | Surgical tests for invalid/valid batch and umbrella cardinality behavior. |
| `docs/reviews/RVW-RDX-REG-01.md` | ADD | Mandatory red-team review artifact with explicit risk questions and verdict. |

## Constraints
- Preserve existing PQX execution behavior, RQX semantics, TPA gating, and CDE closure authority logic.
- No new systems introduced.
- Fail closed on missing/invalid hierarchy definitions where required.
- Keep changes minimal and deterministic.

## Validation
1. `pytest -q tests/test_execution_hierarchy.py`
2. `pytest -q tests/test_roadmap_selection.py tests/test_roadmap_executor.py tests/test_roadmap_execution_loop_validator.py`
3. `pytest -q tests/test_contracts.py`
