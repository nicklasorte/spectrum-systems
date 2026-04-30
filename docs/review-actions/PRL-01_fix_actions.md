# PRL-01 Fix Actions

- must_fix: attempt 3 allowed
  - file changed: contracts/schemas/pr_repair_attempt_summary_record.schema.json; spectrum_systems/modules/runtime/pr_repair_loop.py
  - test: tests/test_pr_repair_loop.py::test_attempt_3_fails_validation
  - command: python -m pytest tests/test_pr_repair_loop.py -q
  - disposition: fixed

- must_fix: unknown failure auto-repaired
  - file changed: spectrum_systems/modules/runtime/pr_repair_loop.py
  - test: tests/test_pr_repair_loop.py::test_unknown_failure_requires_human_review
  - command: python -m pytest tests/test_pr_repair_loop.py -q
  - disposition: fixed
