# TST-01 CI/Test Inventory

## Summary counts
- Total workflow count: **17**
- Total pytest test file count: **816**
- Total pytest collected test count: **10209 tests collected in 20.21s**
- Total Jest test file count: **39**
- Total scripts used in CI workflows: **32**

## Workflow triggers/jobs/scripts
### `3ls-registry-gate.yml`
- Triggers: pull_request, 'docs/architecture/system_registry.md', 'contracts/schemas/**', 'evals/eval_case_library.json', 'spectrum_systems/governance/**'
- Jobs (1): registry-compliance
- Scripts invoked: none

### `artifact-boundary.yml`
- Triggers: push, main, 'release/**', 'codex/**', pull_request
- Jobs (6): enforce-artifact-boundary, validate-module-architecture, validate-orchestration-boundaries, system-registry-guard, governed-contract-preflight, run-pytest
- Scripts invoked: scripts/build_preflight_pqx_wrapper.py, scripts/check_artifact_boundary.py, scripts/run_authority_drift_guard.py, scripts/run_authority_leak_guard.py, scripts/run_authority_shape_preflight.py, scripts/run_contract_preflight.py, scripts/run_system_registry_guard.py, scripts/validate_module_architecture.py, scripts/validate_orchestration_boundaries.py

### `claude-review-ingest.yml`
- Triggers: push, 'design-reviews/*.actions.json'
- Jobs (1): ingest-claude-review
- Scripts invoked: scripts/ingest-claude-review.js

### `closure_continuation_pipeline.yml`
- Triggers: workflow_run, workflow_dispatch
- Jobs (1): closure-continuation
- Scripts invoked: none

### `cross-repo-compliance.yml`
- Triggers: workflow_dispatch, schedule, cron: "0 9 * * 1" # weekly on Mondays at 09:00 UTC, push, main, "governance/**", "contracts/**", "schemas/**", "ecosystem/**", "scripts/**", ".github/workflows/cross-repo-compliance.yml"
- Jobs (6): governance-manifest-validation, cross-repo-compliance, policy-engine, dependency-graph, contract-enforcement, observability-reports
- Scripts invoked: scripts/generate_dependency_graph.py, scripts/generate_ecosystem_architecture_graph.py, scripts/generate_ecosystem_health_report.py, scripts/run_contract_enforcement.py, scripts/validate_governance_manifest.py

### `dashboard-deploy-gate.yml`
- Triggers: pull_request, 'dashboard/**', 'scripts/run_rq_master_01.py', 'scripts/refresh_dashboard.sh', 'scripts/validate_dashboard_public_artifacts.py', 'tests/test_rq_master_01.py', 'tests/test_validate_dashboard_public_artifacts.py', '.github/workflows/dashboard-deploy-gate.yml'
- Jobs (1): dashboard-gate
- Scripts invoked: scripts/refresh_dashboard.sh, scripts/run_rq_master_01.py, scripts/validate_dashboard_public_artifacts.py

### `design-review-scan.yml`
- Triggers: push, "design-reviews/*.md"
- Jobs (1): scan-review
- Scripts invoked: none

### `ecosystem-registry-validation.yml`
- Triggers: push, main, "ecosystem/ecosystem-registry.json", "ecosystem/ecosystem-registry.schema.json", "contracts/standards-manifest.json", "design-packages/**", "scripts/validate_ecosystem_registry.py", "tests/test_ecosystem_registry.py", ".github/workflows/ecosystem-registry-validation.yml", pull_request, "ecosystem/ecosystem-registry.json", "ecosystem/ecosystem-registry.schema.json", "contracts/standards-manifest.json", "design-packages/**", "scripts/validate_ecosystem_registry.py", "tests/test_ecosystem_registry.py", ".github/workflows/ecosystem-registry-validation.yml", workflow_dispatch
- Jobs (1): validate-ecosystem-registry
- Scripts invoked: scripts/validate_ecosystem_registry.py

### `lifecycle-enforcement.yml`
- Triggers: push, main, 'release/**', 'codex/**', pull_request
- Jobs (5): validate-lifecycle-definitions, run-lifecycle-tests, eval-ci-gate, sel-replay-gate, governed-failure-injection-gate
- Scripts invoked: scripts/run_eval_ci_gate.py, scripts/run_governed_failure_injection.py, scripts/run_sel_orchestration.py, scripts/run_sel_replay_gate.py, scripts/validate_lifecycle_data.py, scripts/verify_environment.py

### `pr-autofix-contract-preflight.yml`
- Triggers: workflow_run
- Jobs (2): explicit-fork-skip, governed-contract-preflight-autofix
- Scripts invoked: scripts/build_preflight_pqx_wrapper.py, scripts/run_contract_preflight.py, scripts/run_github_pr_autofix_contract_preflight.py

### `pr-autofix-review-artifact-validation.yml`
- Triggers: workflow_run
- Jobs (2): explicit-fork-skip, governed-pr-autofix
- Scripts invoked: none

### `pr-pytest.yml`
- Triggers: pull_request
- Jobs (1): pytest
- Scripts invoked: scripts/build_preflight_pqx_wrapper.py, scripts/run_contract_preflight.py, scripts/run_github_pr_autofix_contract_preflight.py

### `release-canary.yml`
- Triggers: push, 'scripts/run_release_canary.py', 'scripts/run_eval_coverage_report.py', 'spectrum_systems/modules/evaluation/eval_coverage_reporting.py', 'spectrum_systems/modules/runtime/release_canary.py', 'spectrum_systems/modules/evaluation/eval_engine.py', 'data/policy/eval_release_policy.json', 'data/policy/eval_coverage_policy.json', 'contracts/examples/eval_run.json', 'contracts/examples/eval_case.json', '.github/workflows/release-canary.yml', 'requirements.txt', 'requirements-dev.txt', pull_request, 'scripts/run_release_canary.py', 'scripts/run_eval_coverage_report.py', 'spectrum_systems/modules/evaluation/eval_coverage_reporting.py', 'spectrum_systems/modules/runtime/release_canary.py', 'spectrum_systems/modules/evaluation/eval_engine.py', 'data/policy/eval_release_policy.json', 'data/policy/eval_coverage_policy.json', 'contracts/examples/eval_run.json', 'contracts/examples/eval_case.json', '.github/workflows/release-canary.yml', 'requirements.txt', 'requirements-dev.txt', workflow_dispatch
- Jobs (1): smoke-release-canary
- Scripts invoked: scripts/run_eval_coverage_report.py, scripts/run_release_canary.py, scripts/verify_environment.py

### `review-artifact-validation.yml`
- Triggers: push, 'design-reviews/**', 'docs/reviews/review-registry.json', 'docs/reviews/review-registry.schema.json', 'docs/review-registry.md', 'scripts/check_review_registry.py', 'tests/test_review_registry_json.py', 'scripts/validate-review-artifacts.js', 'scripts/run_review_artifact_validation.py', '.github/workflows/review-artifact-validation.yml', pull_request, 'design-reviews/**', 'docs/reviews/review-registry.json', 'docs/reviews/review-registry.schema.json', 'docs/review-registry.md', 'scripts/check_review_registry.py', 'tests/test_review_registry_json.py', 'scripts/validate-review-artifacts.js', 'scripts/run_review_artifact_validation.py', '.github/workflows/review-artifact-validation.yml'
- Jobs (1): validate-review-artifacts
- Scripts invoked: scripts/check_review_registry.py, scripts/run_review_artifact_validation.py, scripts/validate-review-artifacts.js

### `review_trigger_pipeline.yml`
- Triggers: pull_request_review, issue_comment, workflow_dispatch
- Jobs (1): ingest-and-run-ril
- Scripts invoked: none

### `ssos-project-automation.yml`
- Triggers: issues
- Jobs (1): sync-project
- Scripts invoked: none

### `strategy-compliance.yml`
- Triggers: pull_request, 'docs/roadmaps/**', 'docs/roadmap/**', 'docs/architecture/**', 'docs/**/prompt*.md', 'scripts/check_strategy_compliance.py', 'contracts/schemas/roadmap_output.schema.json', '.github/workflows/strategy-compliance.yml'
- Jobs (1): strategy-compliance
- Scripts invoked: scripts/check_strategy_compliance.py

## Pytest/Jest surfaces
- Pytest files: `816` under `tests/`.
- Jest files: `39` primarily under `tests/mvp-*`, `tests/governance`, `tests/integration`, and `tests/unit`.

## Generated CI artifacts (observed paths)
- `outputs/contract_preflight/*`
- `outputs/eval_ci_gate/*`
- `outputs/authority_shape_preflight/*`
- `outputs/sel_replay_gate/*`
- `outputs/required_check_alignment_audit/*`

## Duplicated enforcement surfaces
- Contract preflight runs in both `pr-pytest.yml` and `artifact-boundary.yml`.
- Autofix preflight workflow duplicates trust checks from PR workflow.
- Governance/registry checks are split across several workflows without one canonical gate artifact.

## Components without clear gate mapping (pre-consolidation)
- `dashboard-deploy-gate.yml` checks dashboard artifacts but did not map to canonical runtime/certification gate.
- `review_*` workflows enforce review pipelines outside a single governed gate result contract.

## Canonical gate mapping snapshot
- Contract Gate: contract/schema validation workflows and scripts (`run_contract_preflight.py`, `run_contract_enforcement.py`).
- Runtime Test Gate: pytest/jest execution and dashboard runtime tests.
- Governance Gate: required-check alignment, system registry guard, governance manifest checks.
- Certification Gate: replay/lineage/promotion readiness/done certification checks.
