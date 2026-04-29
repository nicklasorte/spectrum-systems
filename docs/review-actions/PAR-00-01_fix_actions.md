# PAR-00-01 Fix Actions

**Batch**: PAR-00-01

## must_fix Dispositions

| Finding | File Changed | Test Added/Updated | Validation Command | Disposition |
|---------|-------------|-------------------|-------------------|-------------|
| RT-01 | scripts/run_pr_gate.py | tests/test_pr_gate_parallel.py | python -m pytest tests/test_pr_gate_parallel.py -k missing_shard | fixed |
| RT-02 | scripts/run_pr_gate.py | tests/test_pr_gate_parallel.py | python -m pytest tests/test_pr_gate_parallel.py -k invalid_shard | fixed |
| RT-03 | spectrum_systems/modules/runtime/pr_test_selection.py | tests/test_pr_test_selection_engine.py | python -m pytest tests/test_pr_test_selection_engine.py -k governed_empty | fixed |
| RT-04 | scripts/run_ci_drift_detector.py | tests/test_ci_drift_detector.py | python -m pytest tests/test_ci_drift_detector.py -k unmapped_test | fixed |
| RT-05 | spectrum_systems/modules/runtime/pr_test_selection.py | tests/test_pr_test_selection_engine.py | python -m pytest tests/test_pr_test_selection_engine.py -k governance_shard | fixed |
| RT-06 | contracts/schemas/pr_test_shard_result.schema.json | tests/test_pr_test_shards.py | python -m pytest tests/test_pr_test_shards.py -k authority_scope | fixed |
| RT-07 | contracts/schemas/pr_test_shard_result.schema.json | tests/test_pr_test_shards.py | python -m pytest tests/test_pr_test_shards.py -k authority_scope | fixed |
| RT-08 | scripts/run_pr_gate.py | tests/test_pr_gate_parallel.py | python -m pytest tests/test_pr_gate_parallel.py -k no_recompute | fixed |

## Unresolved must_fix Findings

None.
