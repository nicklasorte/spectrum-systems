# PLAN — AFX-02 Artifact Spine (Admission / Validation / Repair)

## Prompt type
BUILD

## Scope
Implement a thin, repo-native artifact spine for the existing PR autofix path so every attempt emits governed, replayable evidence without introducing a new subsystem.

## Files in scope
| File | Action | Purpose |
| --- | --- | --- |
| `spectrum_systems/modules/runtime/github_pr_autofix_review_artifact_validation.py` | MODIFY | Emit and enforce required `build_admission_record`, `validation_result_record`, and `repair_attempt_record` artifacts with fail-closed linkage checks. |
| `contracts/schemas/build_admission_record.schema.json` | MODIFY | Extend AEX admission record shape with optional source workflow/repo/PR/mutation-classification/lineage fields for autofix admission evidence. |
| `contracts/examples/build_admission_record.example.json` | MODIFY | Show canonical admission evidence fields in a thin example. |
| `contracts/schemas/validation_result_record.schema.json` | CREATE | Define minimal governed pre-push replay result artifact schema. |
| `contracts/examples/validation_result_record.example.json` | CREATE | Provide a minimal valid replay result example. |
| `contracts/schemas/repair_attempt_record.schema.json` | CREATE | Define minimal FRE-linked bounded repair attempt artifact schema. |
| `contracts/examples/repair_attempt_record.example.json` | CREATE | Provide a minimal valid repair attempt example. |
| `contracts/standards-manifest.json` | MODIFY | Register new contracts and bump manifest versions consistent with contract updates. |
| `tests/test_github_pr_autofix_review_artifact_validation.py` | MODIFY | Validate artifact emission/linkage and fail-closed behavior for missing artifact/link conditions. |
| `docs/architecture/pr_autofix_review_artifact_validation.md` | MODIFY | Concise operational note for AFX-02 artifact ownership, emission points, and fail-closed rules. |

## Validation plan
1. `pytest tests/test_github_pr_autofix_review_artifact_validation.py`
2. `pytest tests/test_contracts.py tests/test_contract_enforcement.py`
3. `python scripts/run_contract_enforcement.py`
