# TST-01 CI / TEST SURFACE INVENTORY

## 1. Summary
- Total workflow count: **17**.
- Total pytest test count (static `def test_` inventory): **9573** across **814** files.
- Total Jest test count (static `it/test` inventory): **207** across **39** files.
- Total scripts used in CI workflows: **29** (from `scripts/`).
- Overlapping compliance_observation surfaces identified: **7**.
- Components not clearly mapped to a single gate: **8**.

## 2. Workflow Inventory
### 3LS Registry Compliance Gate
- file_path: `.github/workflows/3ls-registry-gate.yml`
- triggers: pull_request
- jobs: registry-compliance
- gate/validation steps:
  - Run registry drift validator: `python3 spectrum_systems/governance/registry_drift_validator.py \ > /tmp/drift_report.json 2>&1 || true`
  - Verify new schemas have corresponding test coverage: `python3 - <<'EOF' import json from pathlib import Path`
  - Run 3LS contract enforcer audit: `python3 - <<'EOF' import sys try: from spectrum_systems.governance.contract_enforcer import ContractEnforcer enforcer = ContractEnforcer() print("ContractEnforcer instantiated succ`

### artifact-boundary
- file_path: `.github/workflows/artifact-boundary.yml`
- triggers: push, pull_request
- jobs: `enforce-artifact-boundary`, validate-module-architecture, validate-orchestration-boundaries, system-registry-guard, governed-contract-preflight, run-pytest
- gate/validation steps:
  - Validate artifact boundary: `python scripts/check_artifact_boundary.py`
  - Install dependencies: `python -m pip install -r requirements-dev.txt`
  - Validate module architecture: `python scripts/validate_module_architecture.py`
  - Install dependencies: `python -m pip install -r requirements-dev.txt`
  - Validate orchestration boundaries and artifact-bus schema: `python scripts/validate_orchestration_boundaries.py`
  - Scan authority-shape preflight diagnostics (AGS-001): `python scripts/run_authority_shape_preflight.py \ --base-ref "${{ steps.srg-refs.outputs.base_ref }}" \ --head-ref "${{ steps.srg-refs.outputs.head_ref }}" \ --suggest-only \ --out`
  - Run authority drift guard (shift-left): `python scripts/run_authority_drift_guard.py \ --base-ref "${{ steps.srg-refs.outputs.base_ref }}" \ --head-ref "${{ steps.srg-refs.outputs.head_ref }}" \ --output outputs/authority`
  - Run system registry guard: `python scripts/run_system_registry_guard.py \ --base-ref "${{ steps.srg-refs.outputs.base_ref }}" \ --head-ref "${{ steps.srg-refs.outputs.head_ref }}" \ --output outputs/system_re`
  - Run authority leak guard: `python scripts/run_authority_leak_guard.py \ --base-ref "${{ steps.srg-refs.outputs.base_ref }}" \ --head-ref "${{ steps.srg-refs.outputs.head_ref }}" \ --output outputs/authority_`
  - Install test dependencies: `python -m pip install -r requirements-dev.txt`
  - Resolve preflight refs: `set -euo pipefail if [[ "${GITHUB_EVENT_NAME}" == "pull_request" ]]; then base_ref="${{ github.event.pull_request.base.sha }}" head_ref="${{ github.event.pull_request.head.sha }}" `
  - Run authoritative governed preflight gate: `set -euo pipefail python scripts/build_preflight_pqx_wrapper.py \ --base-ref "${{ steps.preflight-refs.outputs.base_ref }}" \ --head-ref "${{ steps.preflight-refs.outputs.head_ref `
  - Install test dependencies: `python -m pip install -r requirements-dev.txt`
  - Run pytest: `pytest`

### claude-review-ingest
- file_path: `.github/workflows/claude-review-ingest.yml`
- triggers: push
- jobs: ingest-claude-review
- gate/validation steps:
  - Validate action files: `node scripts/ingest-claude-review.js --mode validate --schema design-reviews/claude-review.schema.json ${{ steps.changed.outputs.files }}`
  - Ingest review findings: `node scripts/ingest-claude-review.js --mode ingest --schema design-reviews/claude-review.schema.json ${{ steps.changed.outputs.files }}`

### closure-continuation-pipeline
- file_path: `.github/workflows/closure_continuation_pipeline.yml`
- triggers: workflow_run, workflow_dispatch
- jobs: closure-continuation
- gate/validation steps:
  - Install dependencies: `python -m pip install -r requirements-dev.txt`
  - Inspect ingestion command marker: `set -euo pipefail python - <<'PY'`
  - Validate terminal state and branch-update policy guardrails: `set -euo pipefail python - <<'PY'`
  - Build PR feedback comment payload: `set -euo pipefail python - <<'PY'`
  - Write workflow summary: `set -euo pipefail python - <<'PY'`

### Cross Repo Governance Compliance
- file_path: `.github/workflows/cross-repo-compliance.yml`
- triggers: workflow_dispatch, schedule, schedule(cron), push
- jobs: governance-manifest-validation, cross-repo-compliance, policy-engine, dependency-graph, `contract-enforcement`, observability-reports
- gate/validation steps:
  - Install dependencies: `python -m pip install -r requirements-dev.txt`
  - Run pytest: `python -m pytest`
  - Validate governance manifests: `set -euo pipefail for manifest in governance/examples/manifests/*.spectrum-governance.json; do python scripts/validate_governance_manifest.py "$manifest"; done`
  - Run cross-repo compliance scanner: `node governance/compliance-scans/run-cross-repo-compliance.js \ --config governance/compliance-scans/scan-config.example.json \ --standards-manifest contracts/standards-manifest.js`
  - Summarize compliance results: `node -e " const fs = require('fs'); const report = JSON.parse(fs.readFileSync('compliance-report.json', 'utf-8')); const byStatus = { pass: [], fail: [], warning: [], not_yet_enfor`
  - Fail on compliance violations: `node -e " const fs = require('fs'); const report = JSON.parse(fs.readFileSync('compliance-report.json', 'utf-8')); const failed = report.repos.filter(r => r.status === 'fail'); if `
  - Install dependencies: `python -m pip install -r requirements-dev.txt`
  - Run governance policy engine: `python governance/policies/run-policy-engine.py`
  - Print policy engine findings: `python - <<'PYCODE' import json from pathlib import Path`
  - Fail on error-severity policy failures: `python - <<'PYCODE' import json from pathlib import Path`
  - Install dependencies: `python -m pip install -r requirements-dev.txt`
  - Generate ecosystem dependency graph: `python scripts/generate_dependency_graph.py`
  - Install dependencies: `python -m pip install -r requirements-dev.txt`
  - Run cross-repo contract policy_observation: `python scripts/run_contract_enforcement.py`
  - Print compliance_observation summary: `python - <<'PYCODE' import json from pathlib import Path`
  - Fail on real contract policy_observation violations: `python - <<'PYCODE' import json from pathlib import Path`
  - Install dependencies: `python -m pip install -r requirements-dev.txt`
  - Regenerate contract policy_observation graph (prerequisite): `python scripts/run_contract_enforcement.py`
  - Run governance policy engine (prerequisite): `python governance/policies/run-policy-engine.py`
  - Generate ecosystem health report: `python scripts/generate_ecosystem_health_report.py`
  - Generate ecosystem architecture graph: `python scripts/generate_ecosystem_architecture_graph.py`
  - Print observability summary: `python - <<'PYCODE' import json from pathlib import Path`
  - Fail only on true governance health failures: `python - <<'PYCODE' import json from pathlib import Path`

### dashboard-deploy-gate
- file_path: `.github/workflows/dashboard-deploy-gate.yml`
- triggers: pull_request
- jobs: dashboard-gate
- gate/validation steps:
  - Run RQ-MASTER-01 artifact build: `python scripts/run_rq_master_01.py`
  - Refresh dashboard artifacts: `bash scripts/refresh_dashboard.sh`
  - Validate dashboard public artifact contract: `python scripts/validate_dashboard_public_artifacts.py`

### Design Review Scanner
- file_path: `.github/workflows/design-review-scan.yml`
- triggers: push
- jobs: scan-review

### Ecosystem Registry Validation
- file_path: `.github/workflows/ecosystem-registry-validation.yml`
- triggers: push, pull_request, workflow_dispatch
- jobs: validate-ecosystem-registry
- gate/validation steps:
  - Install dependencies: `python -m pip install -r requirements-dev.txt`
  - Run ecosystem registry validation script: `python scripts/validate_ecosystem_registry.py`
  - Run ecosystem registry pytest suite: `python -m pytest tests/test_ecosystem_registry.py -v`

### `lifecycle-enforcement`
- file_path: `.github/workflows/lifecycle-enforcement.yml`
- triggers: push, pull_request
- jobs: validate-lifecycle-definitions, run-lifecycle-tests, eval-ci-gate, sel-replay-gate, governed-failure-injection-gate
- gate/validation steps:
  - Install test dependencies: `python -m pip install -r requirements-dev.txt`
  - Verify dependency bootstrap contract: `python scripts/verify_environment.py --python-only`
  - Validate lifecycle definitions and data backbone: `python scripts/validate_lifecycle_data.py`
  - Install test dependencies: `python -m pip install -r requirements-dev.txt`
  - Verify dependency bootstrap contract: `python scripts/verify_environment.py --python-only`
  - Run lifecycle and data backbone tests: `pytest tests/test_lifecycle_enforcer.py -v`
  - Install test dependencies: `python -m pip install -r requirements-dev.txt`
  - Verify dependency bootstrap contract: `python scripts/verify_environment.py --python-only`
  - Run fail-closed eval CI gate: `python - <<'PY' import json from pathlib import Path`
  - Install test dependencies: `python -m pip install -r requirements-dev.txt`
  - Verify dependency bootstrap contract: `python scripts/verify_environment.py --python-only`
  - Build SEL orchestration artifacts from governed CDE examples: `mkdir -p outputs/sel_replay_gate/cde_bundle cp contracts/examples/continuation_decision_record.json outputs/sel_replay_gate/cde_bundle/continuation_decision_record.json cp contract`
  - Enforce SEL replay gate: `python scripts/run_sel_replay_gate.py           --output-dir outputs/sel_replay_gate/sel_output           --decision-record outputs/sel_replay_gate/cde_bundle/continuation_decision`
  - Install test dependencies: `python -m pip install -r requirements-dev.txt`
  - Verify dependency bootstrap contract: `python scripts/verify_environment.py --python-only`
  - Run governed failure injection regression gate: `python scripts/run_governed_failure_injection.py --output-dir outputs/governed_failure_injection`
  - Run governed failure injection isolation tests: `pytest tests/test_governed_failure_injection.py -v`

### pr-autofix-contract-preflight
- file_path: `.github/workflows/pr-autofix-contract-preflight.yml`
- triggers: workflow_run
- jobs: explicit-fork-skip, governed-contract-preflight-autofix
- gate/validation steps:
  - Emit explicit fork skip: `echo "governed contract-preflight autofix skipped: fork PR outside trusted mutation boundary"`
  - Install dependencies: `python -m pip install -r requirements-dev.txt`
  - Build preflight wrapper and run preflight: `set -euo pipefail python scripts/build_preflight_pqx_wrapper.py \ --base-ref "${{ steps.refs.outputs.base_sha }}" \ --head-ref "${{ steps.refs.outputs.head_sha }}" \ --output outpu`
  - Run governed preflight BLOCK autorepair: `set -euo pipefail set +e python scripts/run_github_pr_autofix_contract_preflight.py \ --output-dir outputs/contract_preflight \ --base-ref "${{ steps.refs.outputs.base_sha }}" \ --`
  - Publish preflight BLOCK bundle summary: `set -euo pipefail python - <<'PY' import json from pathlib import Path out = Path("outputs/contract_preflight") summary = Path(__import__("os").environ["GITHUB_STEP_SUMMARY"]) line`
  - Validate final governed preflight decision_signal: `set -euo pipefail python - <<'PY' import json from pathlib import Path out = Path("outputs/contract_preflight") result = out / "contract_preflight_result_artifact.json" if not resu`

### pr-autofix-review-artifact-validation
- file_path: `.github/workflows/pr-autofix-review-artifact-validation.yml`
- triggers: workflow_run
- jobs: explicit-fork-skip, governed-pr-autofix
- gate/validation steps:
  - Emit explicit fork skip: `echo "governed autofix skipped: fork PR is outside trusted mutation boundary"`
  - Install dependencies: `python -m pip install -r requirements-dev.txt`
  - Retrieve failed workflow logs: `set -euo pipefail mkdir -p .autofix/input curl -sSL \ -H "Authorization: Bearer ${GITHUB_TOKEN}" \ -H "Accept: application/vnd.github+json" \ "https://api.github.com/repos/${REPO}/`
  - Run governed repo-native autofix entrypoint: `set -euo pipefail mkdir -p .autofix/output set +e python -m spectrum_systems.modules.runtime.github_pr_autofix_review_artifact_validation \ --event-payload .autofix/input/workflow_`
  - Validate fail-closed terminal condition: `set -euo pipefail code="${{ steps.governed_autofix.outputs.exit_code }}" if [[ "$code" != "0" ]]; then echo "governed autofix blocked (fail-closed) with exit code $code" >&2 exit 1`

### PR
- file_path: `.github/workflows/pr-pytest.yml`
- triggers: pull_request
- jobs: pytest
- gate/validation steps:
  - Install test dependencies: `python -m pip install -r requirements-dev.txt`
  - Run governed pytest preflight gate: `set -euo pipefail python scripts/build_preflight_pqx_wrapper.py \ --base-ref "${{ steps.preflight-refs.outputs.base_ref }}" \ --head-ref "${{ steps.preflight-refs.outputs.head_ref `

### release-canary
- file_path: `.github/workflows/release-canary.yml`
- triggers: push, pull_request, workflow_dispatch
- jobs: smoke-release-canary
- gate/validation steps:
  - Install dependencies: `python -m pip install -r requirements-dev.txt`
  - Verify dependency bootstrap contract: `python scripts/verify_environment.py --python-only`

### review-artifact-validation
- file_path: `.github/workflows/review-artifact-validation.yml`
- triggers: push, pull_request
- jobs: validate-review-artifacts
- gate/validation steps:
  - Run canonical review artifact validation: `python scripts/run_review_artifact_validation.py --repo-root . --allow-full-pytest`

### review-trigger-pipeline
- file_path: `.github/workflows/review_trigger_pipeline.yml`
- triggers: pull_request_review, issue_comment, workflow_dispatch
- jobs: ingest-and-run-ril
- gate/validation steps:
  - Install dependencies: `python -m pip install -r requirements-dev.txt`
  - Build roadmap draft PR feedback comment: `set -euo pipefail python - <<'PY'`
  - Write workflow summary: `set -euo pipefail python - <<'PY'`

### SSOS Project Automation
- file_path: `.github/workflows/ssos-project-automation.yml`
- triggers: issues
- jobs: sync-project

### strategy-compliance
- file_path: `.github/workflows/strategy-compliance.yml`
- triggers: pull_request
- jobs: strategy-compliance
- gate/validation steps:
  - Run strategy compliance checker: `python scripts/check_strategy_compliance.py`

## 3. Script Inventory
| script_name | role | inputs (CLI args detected) | outputs (artifact paths detected) | workflows that call it | classification |
|---|---|---|---|---|---|
| `__init__.py` | orchestration | n/a | n/a | — | orchestration |
| `authority_leak_rules.py` | orchestration | n/a | n/a | — | orchestration |
| `authority_shape_detector.py` | orchestration | n/a | n/a | — | orchestration |
| `build_control_surface_gap_packet.py` | artifact generator | --done-certification, --enforcement, --generated-at, --governing-ref, --manifest, --obedience | n/a | — | artifact generator |
| `build_control_surface_manifest.py` | artifact generator | --output-dir | n/a | — | artifact generator |
| `build_d3l_maturity_report.py` | artifact generator | --output | n/a | — | artifact generator |
| `build_d3l_mvp_graph.py` | artifact generator | --output | n/a | — | artifact generator |
| `build_d3l_priority_freshness_gate.py` | artifact generator | --candidates, --now, --output, --stale-hours | n/a | — | artifact generator |
| `build_d3l_rank_maturity_alignment.py` | artifact generator | --output | n/a | — | artifact generator |
| `build_d3l_ranking_report.py` | artifact generator | --output | n/a | — | artifact generator |
| `build_d3l_registry_contract.py` | artifact generator | --output, --source | n/a | — | artifact generator |
| `build_dashboard_3ls_with_tls.py` | artifact generator | --candidates, --fail-if-missing, --skip-next-build | n/a | — | artifact generator |
| `build_dependency_graph.py` | artifact generator | n/a | n/a | — | artifact generator |
| `build_eval_registry_snapshot.py` | artifact generator | --canonicalization-policy, --datasets, --output, --policy, --run-id, --snapshot-id | n/a | — | artifact generator |
| `build_failure_diagnosis_artifact.py` | artifact generator | --emitted-at, --governing-ref, --input, --output, --policy-id, --run-id | n/a | — | artifact generator |
| `build_preflight_pqx_wrapper.py` | artifact generator | --base-ref, --changed-path, --event-name, --head-ref, --output, --template | outputs/contract_preflight/preflight_pqx_task_wrapper.json | artifact-boundary.yml, pr-autofix-contract-preflight.yml, pr-pytest.yml | artifact generator |
| `build_review_pack.py` | artifact generator | --json, --scope-id | n/a | — | artifact generator |
| `build_source_indexes.py` | artifact generator | n/a | n/a | — | artifact generator |
| `build_system_registry_artifact.py` | artifact generator | --input, --output | n/a | — | artifact generator |
| `build_tls_dependency_priority.py` | artifact generator | --candidates, --fail-if-missing, --out, --top-level-out | n/a | — | artifact generator |
| `check_artifact_boundary.py` | artifact generator | n/a | n/a | artifact-boundary.yml | artifact generator |
| `check_governance_compliance.py` | policy/control | --file, --json, --text | n/a | — | policy/control |
| `check_protected_files.py` | policy/control | --base-ref, --head-ref, --name-only, --output | n/a | — | policy/control |
| `check_review_registry.py` | contract validation | --emit-signal-artifact, --fail-on-overdue, --registry, --schema | n/a | — | contract validation |
| `check_roadmap_authority.py` | policy/control | n/a | n/a | — | policy/control |
| `check_strategy_compliance.py` | policy/control | --prompt, --report, --roadmap | n/a | strategy-compliance.yml | policy/control |
| `cross_run_intelligence.py` | orchestration | --dir, --input, --output-dir | n/a | — | orchestration |
| `dashboard_refresh_publish_loop.py` | orchestration | --inject-failure, --mode, --now, --repo-root | n/a | — | orchestration |
| `deploy-3ls-dashboard.sh` | orchestration | n/a | n/a | — | orchestration |
| `generate_artifact_cleanup_candidates.py` | artifact generator | --audit-timestamp, --candidates, --out, --report-id | n/a | — | artifact generator |
| `generate_dashboard_truth_projection.py` | artifact generator | --audit-timestamp, --dashboard-view, --freshness-audit, --out, --projection-id, --repo-truth | n/a | — | artifact generator |
| `generate_dependency_graph.py` | artifact generator | n/a | n/a | cross-repo-compliance.yml | artifact generator |
| `generate_ecosystem_architecture_graph.py` | artifact generator | n/a | n/a | cross-repo-compliance.yml | artifact generator |
| `generate_ecosystem_health_report.py` | artifact generator | n/a | n/a | cross-repo-compliance.yml | artifact generator |
| `generate_operator_runbook.py` | artifact generator | --audit-timestamp, --bottleneck, --closure-bundle, --closure-packet, --dashboard-projection, --entry-id | n/a | — | artifact generator |
| `generate_repo_dashboard_snapshot.py` | artifact generator | --output | n/a | — | artifact generator |
| `generate_work_items.py` | artifact generator | ---, --dry-run | n/a | — | artifact generator |
| `hop_run_controlled_trial.py` | orchestration | --iterations, --manifest, --report-path, --store-root | n/a | — | orchestration |
| `ingest-claude-review.js` | orchestration | --mode, --schema | n/a | claude-review-ingest.yml | orchestration |
| `install_hooks.sh` | orchestration | n/a | n/a | — | orchestration |
| `load_test.py` | test runner | n/a | n/a | — | test runner |
| `new_design_review.py` | orchestration | n/a | n/a | — | orchestration |
| `pqx_runner.py` | orchestration | --authority-evidence-ref, --build-admission-record-path, --changed-contract-path, --changed-example-path, --changed-file, --changed-path | n/a | — | orchestration |
| `preflight_3ls_authority.sh` | policy/control | n/a | outputs/3ls_authority_preflight/3ls_authority_preflight_result.json | — | policy/control |
| `preflight_hop.sh` | policy/control | n/a | outputs/authority_leak_guard/authority_leak_guard_result.json, outputs/authority_shape_preflight/authority_shape_preflight_result.json, outputs/system_registry_guard/system_registry_guard_result.json | — | policy/control |
| `preflight_tls_priority.sh` | policy/control | n/a | outputs/authority_leak_guard/authority_leak_guard_result.json, outputs/authority_shape_preflight/authority_shape_preflight_result.json | — | policy/control |
| `print_loop_proof.py` | orchestration | --bundle, --delta, --evidence-index, --freshness | n/a | — | orchestration |
| `print_operational_closure.py` | orchestration | --audit-timestamp, --bottleneck, --bundle-id, --closure-packet, --dashboard-projection, --emit-json | n/a | — | orchestration |
| `refresh_dashboard.sh` | orchestration | n/a | n/a | dashboard-deploy-gate.yml | orchestration |
| `refresh_tpa_source_authority_digests.py` | orchestration | --policy-path, --refresh-id, --refreshed-at | n/a | — | orchestration |
| `register_strategic_source.py` | orchestration | --data-lake-root, --metadata-json, --source-id, --source-path, --source-type, --status | n/a | — | orchestration |
| `render_claude_review_prompt.py` | orchestration | --output, --scope-id | n/a | — | orchestration |
| `roadmap_realization_runner.py` | orchestration | --contract-dir, --result-path | n/a | — | orchestration |
| `run_3ls_authority_preflight.py` | policy/control | --base-ref, --changed-files, --head-ref, --neutral-vocabulary, --output, --registry | outputs/3ls_authority_preflight/3ls_authority_preflight_result.json | — | policy/control |
| `run_agent_golden_path.py` | orchestration | --context-config-json, --emit-invalid-eval-summary, --emit-invalid-structured-output, --fail-agent-execution, --fail-context-assembly, --fail-control-decision | n/a | — | orchestration |
| `run_alert_triggers.py` | orchestration | --output, --policy, --replay, --trace-id | n/a | — | orchestration |
| `run_authenticity_hardgate_24_01.py` | orchestration | n/a | n/a | — | orchestration |
| `run_authority_drift_guard.py` | policy/control | --base-ref, --changed-files, --head-ref, --matrix, --output | outputs/authority_drift_guard/authority_drift_guard_result.json | artifact-boundary.yml | policy/control |
| `run_authority_leak_guard.py` | policy/control | --base-ref, --changed-files, --head-ref, --output, --registry | outputs/authority_leak_guard/authority_leak_guard_result.json | artifact-boundary.yml | policy/control |
| `run_authority_shape_preflight.py` | policy/control | --apply-safe-renames, --base-ref, --changed-files, --head-ref, --output, --suggest-only | outputs/authority_shape_preflight/authority_shape_preflight_result.json | artifact-boundary.yml | policy/control |
| `run_autonomous_validation_run.py` | orchestration | n/a | n/a | — | orchestration |
| `run_aw0_summary.py` | orchestration | n/a | outputs/aw0_validation_summary.json | — | orchestration |
| `run_aw1_summary.py` | orchestration | n/a | outputs/aw1_remediation_summary.json | — | orchestration |
| `run_ay_adversarial_summary.py` | orchestration | n/a | outputs/ay_adversarial_summary.json | — | orchestration |
| `run_blf_01_baseline_gate.py` | orchestration | --artifact-dir | n/a | — | orchestration |
| `run_bundle_validation.py` | orchestration | --bundle, --bundle-root | n/a | — | orchestration |
| `run_cdx_02_roadmap_guard.py` | policy/control | --output | n/a | — | policy/control |
| `run_certification_integrity_validation.py` | orchestration | --control-decisions, --error-budget-statuses, --failure-injection-results, --output, --policy-ref, --regression-results | n/a | — | orchestration |
| `run_certification_judgment_40_explicit.py` | orchestration | n/a | n/a | — | orchestration |
| `run_cluster_validation.py` | orchestration | --all, --case | outputs/validated_clusters.json | — | orchestration |
| `run_codex_to_pqx_wrapper.py` | orchestration | --authority-evidence-ref, --authority-notes, --changed-path, --contract-preflight-result-artifact-path, --dependency, --execute-pqx | n/a | — | orchestration |
| `run_contract_enforcement.py` | contract validation | n/a | n/a | cross-repo-compliance.yml | contract validation |
| `run_contract_impact_analysis.py` | contract validation | --baseline-ref, --changed-contract-path, --changed-example-path, --output-path | n/a | — | contract validation |
| `run_contract_preflight.py` | contract validation | --authority-evidence-ref, --base-ref, --changed-path, --event-name, --execution-context, --hardening-flow | outputs/control_surface_manifest/control_surface_manifest.json | artifact-boundary.yml, pr-autofix-contract-preflight.yml, pr-pytest.yml | contract validation |
| `run_control_decision_consistency_validation.py` | orchestration | --cross-run-intelligence-decisions, --error-budget-statuses, --eval-summaries, --monitor-records, --output, --policy-ref | n/a | — | orchestration |
| `run_control_loop_certification.py` | orchestration | --abbrev-ref, --chaos-command, --chaos-output, --gate-proof-ref, --hard-gate-falsification-ref, --log-dir | outputs/control_loop_chaos/evaluation_control_chaos_summary.json | — | orchestration |
| `run_control_loop_chaos_tests.py` | test runner | --output, --scenarios | outputs/control_loop_chaos/evaluation_control_chaos_summary.json | — | test runner |
| `run_control_surface_enforcement.py` | policy/control | --manifest, --output-dir | n/a | — | policy/control |
| `run_control_surface_gap_extraction.py` | orchestration | --enforcement, --manifest, --obedience, --output-dir | n/a | — | orchestration |
| `run_control_surface_obedience.py` | orchestration | --done-certification, --enforcement-result, --invariant-result, --manifest, --output-dir, --promotion-decision | n/a | — | orchestration |
| `run_cycle_manifest_validation.py` | artifact generator | n/a | n/a | — | artifact generator |
| `run_cycle_observability.py` | orchestration | --backlog-output, --generated-at, --manifest, --status-output | n/a | — | orchestration |
| `run_dashboard.sh` | orchestration | n/a | n/a | — | orchestration |
| `run_done_certification.py` | orchestration | --certification-pack, --error-budget, --error-output, --failure-injection, --output, --policy | n/a | — | orchestration |
| `run_drift_detection.py` | orchestration | --baseline, --config, --output, --replay | n/a | — | orchestration |
| `run_drift_remediation.py` | orchestration | --decision, --manifest, --output | n/a | — | orchestration |
| `run_drift_response_validation.py` | orchestration | --baseline-gate-policy, --output, --replay-results | n/a | — | orchestration |
| `run_end_to_end_failure_simulation.py` | orchestration | --certification-pack-ref, --context-bundle-ref, --control-decision-ref, --done-certification-ref, --error-budget-status-ref, --eval-summary-ref | n/a | — | orchestration |
| `run_enforced_execution.py` | policy/control | --bundle, --changed-file, --commit-sha, --pr-number, --tests-passed | n/a | — | policy/control |
| `run_error_budget.py` | orchestration | --observability, --output, --policy, --slo, --trace-id | n/a | — | orchestration |
| `run_error_clustering.py` | orchestration | --all, --case, --store-dir | outputs/error_clusters.json | — | orchestration |
| `run_error_taxonomy_report.py` | artifact generator | --all, --artifact, --case | outputs/error_taxonomy_report.json | — | artifact generator |
| `run_eval.py` | test runner | --all, --case, --config, --engine-mode, --no-deterministic, --output | outputs/eval_results.json | — | test runner |
| `run_eval_auto_generation_quality_validation.py` | test runner | --cross-run-intelligence-decisions, --drift-results, --eval-summaries, --expected-outcomes-ref, --failure-injection-results, --monitor-records | n/a | — | test runner |
| `run_eval_case.py` | test runner | --case, --output | n/a | — | test runner |
| `run_eval_ci_gate.py` | test runner | --abbrev-ref, --eval-cases, --eval-run, --output-dir, --policy | n/a | lifecycle-enforcement.yml | test runner |
| `run_eval_coverage_report.py` | artifact generator | --blocking-on-gaps, --coverage-run-id, --dataset, --eval-cases, --eval-results, --output-dir | n/a | — | artifact generator |
| `run_eval_run.py` | test runner | --cases, --output, --run | n/a | — | test runner |
| `run_evaluation_budget_governor.py` | test runner | --input, --output-dir, --thresholds | outputs/evaluation_monitor/evaluation_monitor_summary.json | — | test runner |
| `run_evaluation_control_loop.py` | test runner | --emit-intermediate-dir | n/a | — | test runner |
| `run_evaluation_enforcement_bridge.py` | test runner | --done-certification, --input, --output-dir, --override-authorization, --scope | outputs/evaluation_budget_governor/evaluation_budget_decision.json | — | test runner |
| `run_evaluation_monitor.py` | test runner | --input, --output-dir | n/a | — | test runner |
| `run_execution_change_impact_analysis.py` | orchestration | --baseline-ref, --changed-path, --output-path, --provided-eval-artifact, --provided-review | n/a | — | orchestration |
| `run_fail_closed_exhaustive_test.py` | test runner | --input, --output | n/a | — | test runner |
| `run_failure_enforcement.py` | policy/control | --output, --report-path | outputs/failure_first_report.json | — | policy/control |
| `run_failure_first_report.py` | artifact generator | --no-adversarial, --no-operationalization, --observability-dir, --output | n/a | — | artifact generator |
| `run_fast_trust_gate.py` | orchestration | --manifest, --print-selectors | n/a | — | orchestration |
| `run_feedback_session.py` | orchestration | --artifact, --artifact-file, --artifact-type, --output, --reviewer, --role | n/a | — | orchestration |
| `run_fix_plan.py` | orchestration | --decision, --manifest, --output, --remediation | n/a | — | orchestration |
| `run_fix_simulation.py` | orchestration | --all, --remediation, --strict | outputs/simulation_results.json | — | orchestration |
| `run_generated_artifact_git_guard.py` | artifact generator | --base-ref, --changed-files, --head-ref, --output, --policy, --repo-root | n/a | — | artifact generator |
| `run_github_pr_autofix_contract_preflight.py` | contract validation | --authority-evidence-ref, --base-ref, --event-name, --execution-context, --head-ref, --output-dir | outputs/contract_preflight/preflight_pqx_task_wrapper.json | pr-autofix-contract-preflight.yml, pr-pytest.yml | contract validation |
| `run_governed_failure_injection.py` | orchestration | --cases, --list-cases, --output-dir | n/a | lifecycle-enforcement.yml | orchestration |
| `run_governed_kernel_24_01.py` | orchestration | --output-dir | n/a | — | orchestration |
| `run_harness_integrity_bundle.py` | orchestration | --authority-evidence-ref, --output, --output-dir, --roadmap, --run-id, --runs-root | n/a | — | orchestration |
| `run_historical_pytest_exposure_backtest.py` | test runner | --max-items, --output-dir, --report-path, --scan-root, --window-label | n/a | — | test runner |
| `run_lineage_validation.py` | orchestration | --dir, --output | outputs/lineage_validation.json | — | orchestration |
| `run_map_review_orchestration.py` | orchestration | --control-out, --process-doc-out, --roadmap-out, --sequence-state, --snapshot | n/a | — | orchestration |
| `run_metrics_report.py` | artifact generator | --all, --case, --output, --store | outputs/metrics_report.json | — | artifact generator |
| `run_mg_kernel_24_01.py` | orchestration | --output-dir | n/a | — | orchestration |
| `run_mnt002_platform_reliability.py` | orchestration | --evidence, --now, --output | n/a | — | orchestration |
| `run_next_governed_cycle.py` | orchestration | --authorization-signals, --created-at, --execution-policy, --integration-inputs, --next-cycle-decision, --next-cycle-input-bundle | n/a | — | orchestration |
| `run_next_roadmap_batch.py` | orchestration | --authorization-signals, --created-at, --disallow-continuation, --execution-policy, --integration-inputs, --output-dir | n/a | — | orchestration |
| `run_next_step_decision.py` | orchestration | --manifest, --roadmap-eligibility-artifact | n/a | — | orchestration |
| `run_observability_metrics.py` | orchestration | --output, --slo, --source-artifact, --trace-id | n/a | — | orchestration |
| `run_operationalization.py` | orchestration | --adversarial, --engine-mode | n/a | — | orchestration |
| `run_operator_shakeout.py` | orchestration | --created-at, --output-dir, --pqx-runs-root, --pqx-state-path, --scenario-id | n/a | — | orchestration |
| `run_ops02_scheduled_autonomous_execution.py` | orchestration | n/a | n/a | — | orchestration |
| `run_ops03_adversarial_stress_testing.py` | test runner | --max-cycles, --output | n/a | — | test runner |
| `run_ops_master_01.py` | orchestration | n/a | n/a | — | orchestration |
| `run_output_evaluation.py` | test runner | --bundle-root, --manifest | n/a | — | test runner |
| `run_phase_transition.py` | orchestration | --action, --checkpoint, --redteam-open-high, --registry, --validation-passed | n/a | — | orchestration |
| `run_policy_backtest.py` | test runner | --baseline-policy-ref, --candidate-policy-ref, --cross-run-intelligence-decisions, --error-budget-statuses, --eval-summaries, --output | n/a | — | test runner |
| `run_policy_backtest_accuracy.py` | test runner | --baseline-policy-ref, --candidate-policy-refs, --cross-run-intelligence-decisions, --error-budget-statuses, --eval-summaries, --expected-outcomes-ref | n/a | — | test runner |
| `run_policy_enforcement_integrity_validation.py` | policy/control | --alternate-policy-ref, --certification-pack-ref, --control-decision-ref, --done-certification-ref, --error-budget-status-ref, --eval-summary-ref | n/a | — | policy/control |
| `run_pqx_bundle.py` | orchestration | --bundle-id, --bundle-plan-path, --bundle-state-path, --created-at, --emit-triage-plan, --execute-fixes | n/a | — | orchestration |
| `run_pqx_sequence.py` | orchestration | --authority-evidence-ref, --contract-preflight-result-artifact-path, --execution-context, --initial-context, --output, --roadmap | n/a | — | orchestration |
| `run_pra_nsx_prg_automation.py` | orchestration | --output-dir, --pr-input, --pr-number, --pr-url, --previous-anchor | n/a | — | orchestration |
| `run_promotion_gate_attack.py` | orchestration | --enforcement-input, --failed-done-certification, --invalid-done-certification, --malformed-done-certification, --missing-done-certification, --output | n/a | — | orchestration |
| `run_prompt_queue.py` | orchestration | --manifest, --manifest-path, --output-path, --queue-path, --queue-state-path | n/a | — | orchestration |
| `run_prompt_queue_audit_bundle.py` | orchestration | --certification-ref, --execution-result-ref, --final-queue-state-ref, --manifest-ref, --observability-ref, --output-path | n/a | — | orchestration |
| `run_prompt_queue_blocked_recovery.py` | orchestration | --blocking-reason-code, --prior-state, --queue-state-path, --source-blocking-artifact-path, --work-item-id | n/a | — | orchestration |
| `run_prompt_queue_certification.py` | orchestration | --final-queue-state-ref, --manifest-ref, --observability-ref, --output-path, --replay-checkpoint-ref, --replay-record-ref | n/a | — | orchestration |
| `run_prompt_queue_execution.py` | orchestration | --manifest-path, --output-path, --queue-state-path, --work-item-id | n/a | — | orchestration |
| `run_prompt_queue_execution_gating.py` | orchestration | --approval-present, --approval-required-risk-level, --max-generation-allowed, --queue-state-path, --work-item-id | n/a | — | orchestration |
| `run_prompt_queue_findings_reentry.py` | orchestration | --queue-state-path, --repo-root, --work-item-id | n/a | — | orchestration |
| `run_prompt_queue_live_review_invocation.py` | orchestration | --claude-result, --codex-result, --output-reference, --queue-state-path, --work-item-id | n/a | — | orchestration |
| `run_prompt_queue_loop_continuation.py` | orchestration | --queue-state-path, --repo-root, --work-item-id | n/a | — | orchestration |
| `run_prompt_queue_loop_control.py` | orchestration | --max-generation-allowed, --queue-state-path, --work-item-id | n/a | — | orchestration |
| `run_prompt_queue_next_step.py` | orchestration | --queue-state-path, --work-item-id | n/a | — | orchestration |
| `run_prompt_queue_observability.py` | orchestration | --output-path, --queue-path | n/a | — | orchestration |
| `run_prompt_queue_policy_backtest.py` | test runner | --baseline-policy-id, --baseline-policy-version, --candidate-policy-id, --candidate-policy-version, --output-path, --replay-run-ref | n/a | — | test runner |
| `run_prompt_queue_post_execution.py` | orchestration | --max-generation-allowed, --queue-state-path, --work-item-id | n/a | — | orchestration |
| `run_prompt_queue_repair_child.py` | orchestration | --parent-work-item-id, --queue-state-path, --repair-prompt-artifact-path | n/a | — | orchestration |
| `run_prompt_queue_repair_prompt.py` | orchestration | --findings-artifact-path, --repo-root, --work-item-id, --work-item-path | n/a | — | orchestration |
| `run_prompt_queue_replay.py` | orchestration | --checkpoint-path, --output-path | n/a | — | orchestration |
| `run_prompt_queue_resume.py` | orchestration | --checkpoint-path, --output-path | n/a | — | orchestration |
| `run_prompt_queue_retry.py` | orchestration | --failure-reason-code, --queue-state-path, --work-item-id | n/a | — | orchestration |
| `run_prompt_queue_review_parse.py` | orchestration | --repo-root, --review-artifact-path, --review-provider, --work-item-id, --work-item-path | n/a | — | orchestration |
| `run_prompt_queue_review_parsing_handoff.py` | orchestration | --queue-state-path, --repo-root, --work-item-id | n/a | — | orchestration |
| `run_prompt_queue_review_trigger.py` | orchestration | --queue-state-path, --work-item-id | n/a | — | orchestration |
| `run_prompt_queue_sequence.py` | orchestration | --max-slices, --queue-run-id, --resume, --run-id, --slices-path, --state-path | n/a | — | orchestration |
| `run_prompt_with_governance.py` | orchestration | --execute, --file | n/a | — | orchestration |
| `run_pytest_trust_gap_audit.py` | test runner | --max-artifacts, --output-dir, --scan-root | n/a | — | test runner |
| `run_rax_operational_gate.py` | orchestration | --fail-freeze, --output, --output-dir | outputs/rax_operational_gate_record.json | — | orchestration |
| `run_rax_redteam_arch_01.py` | orchestration | n/a | n/a | — | orchestration |
| `run_rax_redteam_harness_01.py` | orchestration | n/a | n/a | — | orchestration |
| `run_redteam_artifact_intelligence.py` | artifact generator | n/a | n/a | — | artifact generator |
| `run_redteam_checkpoint_policy_maintain.py` | policy/control | n/a | n/a | — | policy/control |
| `run_redteam_cross_run_intelligence.py` | orchestration | n/a | n/a | — | orchestration |
| `run_redteam_eval_coverage.py` | test runner | n/a | n/a | — | test runner |
| `run_redteam_final_bottleneck_wave.py` | orchestration | n/a | n/a | — | orchestration |
| `run_redteam_judgment_override.py` | orchestration | n/a | n/a | — | orchestration |
| `run_redteam_observability.py` | orchestration | n/a | n/a | — | orchestration |
| `run_redteam_readiness_promotion.py` | orchestration | n/a | n/a | — | orchestration |
| `run_redteam_workflow_trust.py` | orchestration | n/a | n/a | — | orchestration |
| `run_regression_check.py` | test runner | --all-cases, --baseline, --baselines-dir, --candidate, --case, --create-baseline | outputs/eval_results.json, outputs/metrics_report.json | — | test runner |
| `run_regression_suite.py` | test runner | --output, --suite | outputs/regression_run_result.json | — | test runner |
| `run_release_canary.py` | orchestration | --artifact-type, --baseline-eval-cases, --baseline-eval-run, --baseline-policy-version-id, --baseline-prompt-version-id, --baseline-route-policy-version-id | n/a | release-canary.yml | orchestration |
| `run_remediation_mapping.py` | orchestration | --all, --case | outputs/remediation_plans.json | — | orchestration |
| `run_repair_latency_24_01.py` | orchestration | n/a | n/a | — | orchestration |
| `run_repair_standardization_24_01.py` | orchestration | n/a | n/a | — | orchestration |
| `run_replay_decision_analysis.py` | orchestration | --analysis-output, --replay-output, --trace-id | outputs/replay_decision_analysis.json, outputs/replay_result.json | — | orchestration |
| `run_replay_execution.py` | orchestration | --bundle | n/a | — | orchestration |
| `run_required_check_alignment_audit.py` | policy/control | --live-github-evidence-path, --local-evidence-path, --output-dir, --policy-path, --workflow-path | n/a | — | policy/control |
| `run_retroactive_pytest_integrity_audit.py` | test runner | --output-dir, --remediation-queue-limit, --scan-root | n/a | — | test runner |
| `run_review_artifact_validation.py` | artifact generator | --allow-full-pytest, --emit-signal-artifact, --fail-on-overdue, --no-package-lock, --no-save, --output-json | n/a | review-artifact-validation.yml | artifact generator |
| `run_review_fix_loop_36_explicit.py` | orchestration | n/a | n/a | — | orchestration |
| `run_rfx_super_check.py` | policy/control | n/a | n/a | — | policy/control |
| `run_rh_kernel_24_01.py` | orchestration | n/a | n/a | — | orchestration |
| `run_rmp_attestation.py` | test runner | n/a | n/a | — | test runner |
| `run_roadmap_eligibility.py` | orchestration | --output, --roadmap | n/a | — | orchestration |
| `run_rq_master_01.py` | orchestration | n/a | n/a | dashboard-deploy-gate.yml | orchestration |
| `run_rq_master_36_01.py` | orchestration | --fail-after-artifacts | n/a | — | orchestration |
| `run_rq_next_24_01.py` | orchestration | n/a | n/a | — | orchestration |
| `run_rqx_redteam_cycle.py` | orchestration | --closure-request, --exploit-bundle, --finding, --review-request, --round-config | n/a | — | orchestration |
| `run_runtime_validation.py` | orchestration | --base-path, --runtime-env | outputs/runtime_validation_decision.json | — | orchestration |
| `run_sel_orchestration.py` | orchestration | --cde-bundle-dir, --observed-outcome, --observed-outcome-ref, --output-dir | n/a | lifecycle-enforcement.yml | orchestration |
| `run_sel_replay_gate.py` | orchestration | --action-record, --decision-record, --output-dir | n/a | lifecycle-enforcement.yml | orchestration |
| `run_shift_left_entrypoint_coverage_audit.py` | orchestration | n/a | n/a | — | orchestration |
| `run_shift_left_hardening_superlayer.py` | orchestration | --base-ref, --changed-files, --created-at, --head-ref, --name-only, --output | outputs/shift_left_hardening/superlayer_result.json | — | orchestration |
| `run_shift_left_memory_24_01.py` | orchestration | n/a | n/a | — | orchestration |
| `run_shift_left_preflight.py` | policy/control | --base-ref, --changed-file, --changed-files, --head-ref, --output, --remediation-output | n/a | — | policy/control |
| `run_shift_left_workflow_coverage_audit.py` | orchestration | n/a | n/a | — | orchestration |
| `run_slo_control_chain.py` | orchestration | --enforce-control, --execute, --input-kind, --output, --policy, --stage | outputs/slo_enforcement_decision.json, outputs/slo_evaluation.json, outputs/slo_gating_decision.json | — | orchestration |
| `run_slo_enforcement.py` | policy/control | --list-policies, --list-stages, --output, --policy, --show-effective-policy, --stage | outputs/slo_evaluation.json | — | policy/control |
| `run_slo_gating.py` | orchestration | --output, --show-stage-posture, --stage | outputs/slo_enforcement_decision.json | — | orchestration |
| `run_system_cycle.py` | orchestration | --authorization-signals, --created-at, --execution-policy, --integration-inputs, --output-dir, --pqx-runs-root | n/a | — | orchestration |
| `run_system_registry_guard.py` | contract validation | --base-ref, --changed-files, --head-ref, --output | outputs/system_registry_guard/system_registry_guard_result.json | artifact-boundary.yml | contract validation |
| `run_three_letter_system_enforcement_audit.py` | policy/control | --base-ref, --changed-files, --head-ref, --output, --policy-path | outputs/three_letter_system_enforcement/three_letter_system_enforcement_audit_result.json | — | policy/control |
| `run_tls_exec_01.py` | orchestration | --out-dir, --priority-report, --top-level-priority-out | n/a | — | orchestration |
| `run_tpa_policy_authority.py` | orchestration | --input, --redteam-round | n/a | — | orchestration |
| `run_trust_spine_evidence_cohesion.py` | orchestration | --contract-preflight, --done-certification, --enforcement, --invariant, --manifest, --obedience | n/a | — | orchestration |
| `run_working_paper_engine.py` | orchestration | --inputs, --output, --pretty-report-out, --provenance-mode | n/a | — | orchestration |
| `run_working_paper_generator.py` | orchestration | --draft, --format, --meeting-title, --minutes, --output, --transcript | n/a | — | orchestration |
| `run_wpg_pipeline.py` | orchestration | --input, --mode, --output-dir, --phase-checkpoint, --phase-registry | n/a | — | orchestration |
| `run_wpg_redteam.py` | orchestration | --output | n/a | — | orchestration |
| `run_xrun_signal_quality_validation.py` | orchestration | --drift-results, --eval-summaries, --expected-outcomes-ref, --monitor-records, --output, --policy-ref | n/a | — | orchestration |
| `scaffold_governed_repo.py` | orchestration | --declared-at, --output-dir, --owner, --repo-name, --repo-type, --system-id | n/a | — | orchestration |
| `setup-labels.sh` | orchestration | n/a | n/a | — | orchestration |
| `setup-project-automation.sh` | orchestration | n/a | n/a | — | orchestration |
| `slo_control.py` | orchestration | --be-input, --bf-input, --bg-input, --lineage-dir, --output-dir, --parent-id | n/a | — | orchestration |
| `srg_check.sh` | policy/control | --last-commit, --staged | outputs/system_registry_guard/local_check_result.json | — | policy/control |
| `strategic_knowledge_init.py` | orchestration | --data-lake-root | n/a | — | orchestration |
| `suggest_3ls_authority_repairs.py` | orchestration | --input, --neutral-vocabulary, --output | outputs/3ls_authority_preflight/3ls_authority_preflight_result.json, outputs/3ls_authority_preflight/3ls_authority_repair_suggestions.json | — | orchestration |
| `sync_project_design_sources.py` | orchestration | --allow-missing-required, --refresh-tpa-digests, --upstream-repo, --upstream-root, --validate-only | n/a | — | orchestration |
| `sync_system_roadmap_markdown.py` | orchestration | --markdown-out, --roadmap-json | n/a | — | orchestration |
| `tls_next_01_integration.py` | orchestration | --artifacts-dir, --generated-at, --registry-path, --repo-root | n/a | — | orchestration |
| `update_readme_mental_map.py` | orchestration | n/a | n/a | — | orchestration |
| `validate-review-artifacts.js` | artifact generator | n/a | n/a | — | artifact generator |
| `validate_dashboard_public_artifacts.py` | artifact generator | n/a | n/a | dashboard-deploy-gate.yml | artifact generator |
| `validate_ecosystem_registry.py` | contract validation | --design-packages, --manifest, --registry | n/a | ecosystem-registry-validation.yml | contract validation |
| `validate_evaluation_contract.py` | test runner | --all | n/a | — | test runner |
| `validate_evaluation_manifest.py` | artifact generator | --bundle | n/a | — | artifact generator |
| `validate_forbidden_authority_vocabulary.py` | policy/control | --owner-path-prefix, --scan-path | n/a | — | policy/control |
| `validate_governance_manifest.py` | artifact generator | n/a | n/a | cross-repo-compliance.yml | artifact generator |
| `validate_lifecycle_data.py` | policy/control | n/a | n/a | lifecycle-enforcement.yml | policy/control |
| `validate_manifest.py` | artifact generator | --manifest | n/a | — | artifact generator |
| `validate_module_architecture.py` | policy/control | n/a | n/a | artifact-boundary.yml | policy/control |
| `validate_orchestration_boundaries.py` | policy/control | n/a | n/a | artifact-boundary.yml | policy/control |
| `validate_review_alignment.py` | policy/control | n/a | n/a | — | policy/control |
| `validate_review_artifact.py` | artifact generator | --markdown | n/a | — | artifact generator |
| `validate_review_artifacts.py` | artifact generator | --dirs | n/a | — | artifact generator |
| `validate_review_output.py` | policy/control | --input, --verbose | n/a | — | policy/control |
| `validate_run_evidence_bundle.py` | policy/control | n/a | n/a | — | policy/control |
| `validate_strategic_knowledge_artifact.py` | artifact generator | --artifact-path, --data-lake-root, --parent-span-id, --run-id, --span-id, --trace-id | n/a | — | artifact generator |
| `validate_system_registry.py` | contract validation | n/a | n/a | — | contract validation |
| `validate_system_registry_boundaries.py` | contract validation | --registry | n/a | — | contract validation |
| `validate_test_imports.py` | test runner | n/a | n/a | — | test runner |
| `verify_environment.py` | orchestration | --python-only, --version | n/a | lifecycle-enforcement.yml, release-canary.yml | orchestration |
| `watch_dashboard.py` | orchestration | --debounce, --interval | n/a | — | orchestration |
| `working_paper_synthesis.py` | orchestration | --be-input, --bf-input, --output-dir | n/a | — | orchestration |

## 4. Test Inventory
### Pytest surface (tests/)
- contract/schema: 113 files
  - `tests/hop/test_artifacts.py`
  - `tests/hop/test_schemas.py`
  - `tests/metrics/test_met_04_18_contract_selection.py`
  - `tests/metrics/test_met_19_33_contract_selection.py`
  - `tests/test_3ls_registry_guard.py`
  - `tests/test_aex_schema_validation.py`
  - `tests/test_agent_failure_artifacts.py`
  - `tests/test_artifact_boundary_workflow_policy_observation.py`
  - `tests/test_artifact_boundary_workflow_pytest_policy_observation.py`
  - `tests/test_artifact_class_taxonomy_alignment.py`
  - `tests/test_artifact_classification.py`
  - `tests/test_artifact_envelope.py`
  - `tests/test_artifact_envelope_helpers.py`
  - `tests/test_artifact_eval_requirement_profiles.py`
  - `tests/test_artifact_intelligence.py`
  - `tests/test_artifact_intelligence_index.py`
  - `tests/test_artifact_intelligence_regressions.py`
  - `tests/test_artifact_intelligence_reports.py`
  - `tests/test_artifact_lineage.py`
  - `tests/test_artifact_packager_governed_fallbacks.py`
  - `tests/test_artifact_packaging_and_study_state.py`
  - `tests/test_artifact_signing.py`
  - `tests/test_authority_artifact_replay_stability.py`
  - `tests/test_build_eval_registry_snapshot_cli.py`
  - `tests/test_checkpoint_stage_contracts.py`
  - `tests/test_compliance_report_schema.py`
  - `tests/test_contract_bootstrap.py`
  - `tests/test_contract_boundary_audit.py`
  - `tests/test_contract_compatibility_gate.py`
  - `tests/test_contract_enforcement.py`
  - `tests/test_contract_impact_analysis.py`
  - `tests/test_contract_preflight.py`
  - `tests/test_contract_runtime_enforcement.py`
  - `tests/test_contracts.py`
  - `tests/test_control_chain_schema_hardening.py`
  - `tests/test_control_surface_manifest.py`
  - `tests/test_cycle_manifest.py`
  - `tests/test_d3l_registry_contract.py`
  - `tests/test_dashboard_render_gate_contract.py`
  - `tests/test_ecosystem_registry.py`
  - `tests/test_eval_dataset_registry.py`
  - `tests/test_execution_contracts.py`
  - `tests/test_failure_class_registry.py`
  - `tests/test_failure_learning_artifacts.py`
  - `tests/test_generated_artifact_git_guard.py`
  - `tests/test_generated_eval_registry_change_surface_vocabulary.py`
  - `tests/test_github_pr_autofix_contract_preflight.py`
  - `tests/test_github_pr_autofix_review_artifact_validation.py`
  - `tests/test_glossary_registry.py`
  - `tests/test_governance_manifest_schema.py`
  - `tests/test_governance_manifest_validator.py`
  - `tests/test_manifest_completeness.py`
  - `tests/test_meeting_minutes_contract.py`
  - `tests/test_minimalism_automation_contracts.py`
  - `tests/test_next_phase_contracts.py`
  - `tests/test_next_wave_contracts.py`
  - `tests/test_no_network_schema_loading.py`
  - `tests/test_ns_artifact_tiering.py`
  - `tests/test_ns_failure_trace_contract.py`
  - `tests/test_nt_artifact_tier_drift.py`
  - `tests/test_nx_registry_red_team.py`
  - `tests/test_operations_monitoring_contract.py`
  - `tests/test_phase_registry.py`
  - `tests/test_pmh_002_contracts.py`
  - `tests/test_pmh_003_contracts.py`
  - `tests/test_policy_registry.py`
  - `tests/test_pr_autofix_review_artifact_validation_workflow.py`
  - `tests/test_preflight_autofix_contracts.py`
  - `tests/test_prompt_queue_manifest.py`
  - `tests/test_prompt_registry.py`
  - `tests/test_provenance_schema.py`
  - `tests/test_r100_np001_contracts.py`
  - `tests/test_redteam_artifact_intelligence_harness.py`
  - `tests/test_registry_valid.py`
  - `tests/test_regression_policy_schema.py`
  - `tests/test_review_artifact_contract.py`
  - `tests/test_review_artifact_repo_validation.py`
  - `tests/test_review_contract_schema.py`
  - `tests/test_review_registry_json.py`
  - `tests/test_rfx_contract_snapshot.py`
  - `tests/test_rfx_health_contract.py`
  - `tests/test_rfx_reason_code_registry.py`
  - `tests/test_rgp02_contract_surface.py`
  - `tests/test_roadmap_artifact_store.py`
  - `tests/test_roadmap_expansion_contracts.py`
  - `tests/test_roadmap_slice_registry.py`
  - `tests/test_roadmap_step_contract.py`
  - `tests/test_run_github_pr_autofix_contract_preflight.py`
  - `tests/test_run_system_registry_guard_resolution.py`
  - `tests/test_schema_files_exist.py`
  - `tests/test_serial_substrate_contracts.py`
  - `tests/test_slice_registry_execution_contract.py`
  - `tests/test_source_design_extraction_schema.py`
  - `tests/test_stage_contract_runtime.py`
  - `tests/test_strategic_knowledge_schemas.py`
  - `tests/test_strategic_knowledge_validation_decision_schema.py`
  - `tests/test_system_registry.py`
  - `tests/test_system_registry_boundaries.py`
  - `tests/test_system_registry_boundary_enforcement.py`
  - `tests/test_system_registry_guard.py`
  - `tests/test_system_registry_validation.py`
  - `tests/test_task_registry_ai_adapter_eval_slice_runner.py`
  - `tests/test_tax_bax_cax_contracts.py`
  - `tests/test_tlc_handoff_schema_validation.py`
  - `tests/test_tls_roadmap_artifacts.py`
  - `tests/test_validate_dashboard_public_artifacts.py`
  - `tests/test_validate_strategic_knowledge_artifact_cli.py`
  - `tests/test_wpg_contracts.py`
  - `tests/test_wpg_eval_coverage_artifact.py`
  - `tests/test_wpg_meeting_artifact.py`
  - `tests/tls_dependency_graph/test_phase0_registry_parser.py`
  - `tests/transcript_pipeline/test_artifact_store_h02.py`
  - `tests/transcript_pipeline/test_schemas_h01.py`
- eval/quality: 53 files
  - `tests/hop/test_eval_factory.py`
  - `tests/hop/test_evaluator.py`
  - `tests/hop/test_heldout_eval.py`
  - `tests/test_3ls_phase2_context_eval.py`
  - `tests/test_decision_quality_control.py`
  - `tests/test_enf01_required_eval_control_loop.py`
  - `tests/test_eval_adoption_gate.py`
  - `tests/test_eval_auto_generation_quality.py`
  - `tests/test_eval_candidate_pipeline.py`
  - `tests/test_eval_ci_gate.py`
  - `tests/test_eval_coverage.py`
  - `tests/test_eval_coverage_enforcement.py`
  - `tests/test_eval_coverage_regressions.py`
  - `tests/test_eval_coverage_report.py`
  - `tests/test_eval_engine.py`
  - `tests/test_eval_regressions.py`
  - `tests/test_eval_requirement_profiles.py`
  - `tests/test_eval_slice_summary.py`
  - `tests/test_eval_slices.py`
  - `tests/test_evaluation_auto_generation.py`
  - `tests/test_evaluation_budget_governor.py`
  - `tests/test_evaluation_control.py`
  - `tests/test_evaluation_control_loop.py`
  - `tests/test_evaluation_enforcement_bridge.py`
  - `tests/test_evaluation_framework.py`
  - `tests/test_evaluation_monitor.py`
  - `tests/test_evaluation_spine.py`
  - `tests/test_failure_derived_eval_case.py`
  - `tests/test_failure_eval_generation.py`
  - `tests/test_failure_to_eval_conversion.py`
  - `tests/test_failure_to_eval_pipeline.py`
  - `tests/test_generated_eval_review_surface_vocabulary.py`
  - `tests/test_grounding_control.py`
  - `tests/test_grounding_factcheck_eval.py`
  - `tests/test_incident_to_eval.py`
  - `tests/test_nx_eval_spine.py`
  - `tests/test_policy_eval_coverage.py`
  - `tests/test_precedent_ranking_eval.py`
  - `tests/test_rax_eval_runner.py`
  - `tests/test_redteam_eval_blind_spots.py`
  - `tests/test_redteam_eval_coverage_harness.py`
  - `tests/test_repo_health_eval.py`
  - `tests/test_required_eval_coverage.py`
  - `tests/test_review_eval_bridge.py`
  - `tests/test_rfx_failure_to_eval.py`
  - `tests/test_run_output_evaluation.py`
  - `tests/test_semantic_eval_classes.py`
  - `tests/test_slo_evaluator.py`
  - `tests/test_wpg_critique_retrieval.py`
  - `tests/test_wpg_judgment_eval.py`
  - `tests/test_xrun_signal_quality.py`
  - `tests/transcript_pipeline/test_eval_gate_cpl03.py`
  - `tests/transcript_pipeline/test_pipeline_eval_runner_h04.py`
- control/policy: 127 files
  - `tests/governance/test_3ls_authority_preflight.py`
  - `tests/governance/test_3ls_authority_repair_suggestions.py`
  - `tests/governance/test_h01_final_authority_shape.py`
  - `tests/governance/test_h08_authority_shape.py`
  - `tests/hop/test_control_integration.py`
  - `tests/hop/test_mutation_policy.py`
  - `tests/test_3ls_phase3_judgment_policy.py`
  - `tests/test_ai_governed_integration.py`
  - `tests/test_authenticity_hardgate_24_01.py`
  - `tests/test_blf_01_baseline_gate.py`
  - `tests/test_checkpoint_policy_maintain_regressions.py`
  - `tests/test_confidence_usage_policy.py`
  - `tests/test_context_governed_foundation.py`
  - `tests/test_control_decision_consistency.py`
  - `tests/test_control_effectiveness.py`
  - `tests/test_control_executor.py`
  - `tests/test_control_integration.py`
  - `tests/test_control_loop.py`
  - `tests/test_control_loop_certification.py`
  - `tests/test_control_loop_chaos.py`
  - `tests/test_control_loop_gates.py`
  - `tests/test_control_loop_hardening.py`
  - `tests/test_control_responses.py`
  - `tests/test_control_signals.py`
  - `tests/test_control_surface_enforcement.py`
  - `tests/test_control_surface_gap_extractor.py`
  - `tests/test_control_surface_gap_to_pqx.py`
  - `tests/test_control_surface_obedience.py`
  - `tests/test_d3l_priority_freshness_gate.py`
  - `tests/test_end_to_end_governed_scenarios.py`
  - `tests/test_enforcement_engine.py`
  - `tests/test_enforcement_gate.py`
  - `tests/test_fail_closed_enforcer.py`
  - `tests/test_failure_enforcement.py`
  - `tests/test_govern_drift_aware.py`
  - `tests/test_governance_chain_guard.py`
  - `tests/test_governance_changed_files.py`
  - `tests/test_governance_import_isolation.py`
  - `tests/test_governance_prompt_enforcement.py`
  - `tests/test_governed_execution_kernel.py`
  - `tests/test_governed_failure_injection.py`
  - `tests/test_governed_preflight_remediation_loop.py`
  - `tests/test_governed_prompt_surface_sync.py`
  - `tests/test_governed_repair_foundation.py`
  - `tests/test_governed_repair_loop_delegation.py`
  - `tests/test_governed_repair_loop_execution.py`
  - `tests/test_hitl_override_enforcement.py`
  - `tests/test_identity_enforcement.py`
  - `tests/test_judgment_enforcement.py`
  - `tests/test_judgment_policy_candidates.py`
  - `tests/test_judgment_policy_lifecycle.py`
  - `tests/test_lifecycle_enforcer.py`
  - `tests/test_meta_governance_kernel.py`
  - `tests/test_next_governed_cycle_runner.py`
  - `tests/test_next_phase_governance.py`
  - `tests/test_next_step_decision_policy.py`
  - `tests/test_nt_control_signal_minimality.py`
  - `tests/test_nx_control_chain.py`
  - `tests/test_nx_governed_intelligence.py`
  - `tests/test_nx_governed_system.py`
  - `tests/test_nx_lineage_enforcement.py`
  - `tests/test_nx_slo_budget_gate.py`
  - `tests/test_oc_fast_trust_gate.py`
  - `tests/test_permission_governance.py`
  - `tests/test_phase_certified_expansion_gate.py`
  - `tests/test_phase_transition_policy.py`
  - `tests/test_policy_backtest_accuracy.py`
  - `tests/test_policy_backtesting.py`
  - `tests/test_policy_canary_rollback.py`
  - `tests/test_policy_enforcement_integrity.py`
  - `tests/test_policy_engine.py`
  - `tests/test_policy_identity_hardening.py`
  - `tests/test_policy_regression_report.py`
  - `tests/test_pqx_closeout_gate.py`
  - `tests/test_pqx_fix_gate.py`
  - `tests/test_pqx_required_context_enforcement.py`
  - `tests/test_pqx_sequence_governance.py`
  - `tests/test_pre_pr_governance_closure.py`
  - `tests/test_promotion_gate.py`
  - `tests/test_promotion_gate_attack.py`
  - `tests/test_promotion_gate_decision.py`
  - `tests/test_prompt_queue_loop_control.py`
  - `tests/test_prompt_queue_policy_backtesting.py`
  - `tests/test_prompt_queue_post_execution_policy.py`
  - `tests/test_pyx_push_and_pr_context_enforcement.py`
  - `tests/test_redteam_checkpoint_policy_maintain_harness.py`
  - `tests/test_release_readiness_policy.py`
  - `tests/test_replay_governance.py`
  - `tests/test_replay_governance_control_loop.py`
  - `tests/test_required_ids_enforced.py`
  - `tests/test_review_control_integration.py`
  - `tests/test_review_convergence_controller.py`
  - `tests/test_review_promotion_gate.py`
  - `tests/test_review_trigger_policy.py`
  - `tests/test_rfx_calibration_policy_handoff.py`
  - `tests/test_rfx_certification_gate.py`
  - `tests/test_rfx_error_budget_governance.py`
  - `tests/test_rfx_policy_compilation.py`
  - `tests/test_rfx_telemetry_slo_gate.py`
  - `tests/test_rge_debuggability_gate.py`
  - `tests/test_rge_phase_justification_gate.py`
  - `tests/test_rge_recursion_governor.py`
  - `tests/test_rgp02_gate.py`
  - `tests/test_rmp_gate_validation.py`
  - `tests/test_routing_policy.py`
  - `tests/test_run_prompt_with_governance.py`
  - `tests/test_run_rax_operational_gate_cli.py`
  - `tests/test_run_three_letter_system_enforcement_audit.py`
  - `tests/test_runtime_legacy_enforcement_isolation.py`
  - `tests/test_scaffold_governed_repo.py`
  - `tests/test_sel_enforcement_foundation.py`
  - `tests/test_sequence_transition_policy.py`
  - `tests/test_slo_control.py`
  - `tests/test_slo_control_chain.py`
  - `tests/test_slo_enforcement.py`
  - `tests/test_slo_enforcer.py`
  - `tests/test_system_end_to_end_governed_loop.py`
  - `tests/test_system_enforcement_layer.py`
  - `tests/test_tax_bax_cax_gates.py`
  - `tests/test_three_letter_system_enforcement.py`
  - `tests/test_tpa_complexity_governance.py`
  - `tests/test_tpa_policy_authority.py`
  - `tests/test_tpa_policy_composition.py`
  - `tests/test_tpa_scope_policy.py`
  - `tests/test_wpg_governance_offload.py`
  - `tests/test_wpg_policy_profiles.py`
  - `tests/transcript_pipeline/test_control_routing_enforcement.py`
- replay/lineage: 19 files
  - `tests/hop/test_trace_diff.py`
  - `tests/test_failure_replay.py`
  - `tests/test_lineage_graph.py`
  - `tests/test_ns_replay_lineage_join.py`
  - `tests/test_nx_observability_failure_trace.py`
  - `tests/test_nx_replay_support.py`
  - `tests/test_pqx_execution_trace.py`
  - `tests/test_pqx_repo_write_lineage_guard.py`
  - `tests/test_prompt_queue_replay_resume.py`
  - `tests/test_provenance_verification.py`
  - `tests/test_replay_decision_engine.py`
  - `tests/test_replay_engine.py`
  - `tests/test_replay_regression_harness.py`
  - `tests/test_replay_verifier.py`
  - `tests/test_rfx_observability_replay_consistency.py`
  - `tests/test_trace_and_provenance.py`
  - `tests/test_trace_engine.py`
  - `tests/test_trace_store.py`
  - `tests/transcript_pipeline/test_replay_integrity_h01.py`
- governance/registry: 40 files
  - `tests/hop/test_authority_shape_regression.py`
  - `tests/test_authority_drift_regression.py`
  - `tests/test_authority_leak_detection.py`
  - `tests/test_authority_leak_ecv_fix.py`
  - `tests/test_authority_leak_guard_local.py`
  - `tests/test_authority_shape_preflight.py`
  - `tests/test_cdx_02_roadmap_guard.py`
  - `tests/test_fix_roadmap_generator.py`
  - `tests/test_forbidden_authority_vocabulary_guard.py`
  - `tests/test_github_roadmap_builder.py`
  - `tests/test_non_authority_runtime_vocabulary.py`
  - `tests/test_nx_authority_shape_preflight_regression.py`
  - `tests/test_opx_001_full_roadmap.py`
  - `tests/test_opx_002_operator_grade_roadmap.py`
  - `tests/test_refresh_tpa_source_authority_digests.py`
  - `tests/test_review_roadmap_generator.py`
  - `tests/test_rfx_authority_pattern_corpus.py`
  - `tests/test_rfx_authority_vocabulary_sweep.py`
  - `tests/test_rfx_roadmap_generator.py`
  - `tests/test_rge_roadmap_generator.py`
  - `tests/test_rmp_authority.py`
  - `tests/test_roadmap_authority.py`
  - `tests/test_roadmap_authorizer.py`
  - `tests/test_roadmap_draft_and_approval.py`
  - `tests/test_roadmap_eligibility.py`
  - `tests/test_roadmap_execution.py`
  - `tests/test_roadmap_execution_loop_validator.py`
  - `tests/test_roadmap_executor.py`
  - `tests/test_roadmap_generator.py`
  - `tests/test_roadmap_health_coupler.py`
  - `tests/test_roadmap_long_fabric.py`
  - `tests/test_roadmap_multi_batch_executor.py`
  - `tests/test_roadmap_realization_runner.py`
  - `tests/test_roadmap_selector.py`
  - `tests/test_roadmap_signal_generation.py`
  - `tests/test_roadmap_signal_steering.py`
  - `tests/test_roadmap_tracker.py`
  - `tests/test_roadmap_trigger_pipeline.py`
  - `tests/test_run_authority_leak_guard.py`
  - `tests/test_run_authority_shape_preflight.py`
- integration/hop: 71 files
  - `tests/hop/test_admission.py`
  - `tests/hop/test_adversarial_batch2.py`
  - `tests/hop/test_baseline_harness.py`
  - `tests/hop/test_cli.py`
  - `tests/hop/test_experience_store.py`
  - `tests/hop/test_experience_store_concurrency.py`
  - `tests/hop/test_failure_analysis.py`
  - `tests/hop/test_fix_pass.py`
  - `tests/hop/test_frontier.py`
  - `tests/hop/test_frontier_streaming.py`
  - `tests/hop/test_heldout_hardening.py`
  - `tests/hop/test_integration_pipeline.py`
  - `tests/hop/test_optimization_loop.py`
  - `tests/hop/test_patterns.py`
  - `tests/hop/test_phase2_red_team.py`
  - `tests/hop/test_promotion_readiness.py`
  - `tests/hop/test_proposer.py`
  - `tests/hop/test_rollback_signals.py`
  - `tests/hop/test_safety_checks.py`
  - `tests/hop/test_sandbox.py`
  - `tests/hop/test_trend_reports.py`
  - `tests/hop/test_trial_runner.py`
  - `tests/hop/test_validator.py`
  - `tests/test_3ls_phase1_foundation.py`
  - `tests/test_3ls_phase4_observability.py`
  - `tests/test_3ls_phase5_release_budget.py`
  - `tests/test_3ls_phase6_integration.py`
  - `tests/test_3ls_phase7_final_lock.py`
  - `tests/test_3ls_simplification_phases_6_9.py`
  - `tests/test_closure_continuation_pipeline_workflow.py`
  - `tests/test_integration_end_to_end.py`
  - `tests/test_integration_fabric_ifb.py`
  - `tests/test_mnt_trust_integration.py`
  - `tests/test_phase_a_integration.py`
  - `tests/test_phase_b_security.py`
  - `tests/test_phase_c_observability.py`
  - `tests/test_phase_checkpoint.py`
  - `tests/test_phase_d_slos.py`
  - `tests/test_phase_handoff_record.py`
  - `tests/test_phase_j_production.py`
  - `tests/test_phase_l_intelligence.py`
  - `tests/test_phase_m_advanced_queries.py`
  - `tests/test_phase_n_alerts.py`
  - `tests/test_phase_resume_record.py`
  - `tests/test_phase_transition.py`
  - `tests/test_phase_transition_cli.py`
  - `tests/test_phases_23_26_integration.py`
  - `tests/test_phases_29_34_integration.py`
  - `tests/test_phases_35_40_integration.py`
  - `tests/test_prompt_queue_execution_integration.py`
  - `tests/test_prompt_queue_next_step_integration.py`
  - `tests/test_review_trigger_pipeline_workflow.py`
  - `tests/test_rfx_flow_integration.py`
  - `tests/test_run_phase_transition.py`
  - `tests/test_srg_phase2_ownership.py`
  - `tests/test_system_integration_validator.py`
  - `tests/test_tls_next_01_integration.py`
  - `tests/test_wpg_phase_aware_execution.py`
  - `tests/test_wpg_phase_b_regressions.py`
  - `tests/test_wpg_pipeline.py`
  - `tests/tls_dependency_graph/test_phase1_evidence_scanner.py`
  - `tests/tls_dependency_graph/test_phase2_classification.py`
  - `tests/tls_dependency_graph/test_phase3_trust_gaps.py`
  - `tests/tls_dependency_graph/test_phase4_ranking.py`
  - `tests/transcript_pipeline/test_chaos_h07.py`
  - `tests/transcript_pipeline/test_context_bundle_assembler_cpl02.py`
  - `tests/transcript_pipeline/test_h01b_hardening.py`
  - `tests/transcript_pipeline/test_no_unchecked_routing.py`
  - `tests/transcript_pipeline/test_pqx_step_harness_h03.py`
  - `tests/transcript_pipeline/test_tlc_router_h05.py`
  - `tests/transcript_pipeline/test_transcript_ingestor_h08.py`
- misc: 391 files
  - `tests/test_3ls_simplification.py`
  - `tests/test_adaptive_execution_observability.py`
  - `tests/test_adr_structure.py`
  - `tests/test_adv_new_systems.py`
  - `tests/test_aex_admission.py`
  - `tests/test_aex_fail_closed.py`
  - `tests/test_aex_hardening.py`
  - `tests/test_aex_repo_write_boundary_structural.py`
  - `tests/test_agent_executor.py`
  - `tests/test_agent_golden_path.py`
  - `tests/test_alert_triggers.py`
  - `tests/test_architecture_frameworks.py`
  - `tests/test_autonomy_guardrails.py`
  - `tests/test_baseline_gating.py`
  - `tests/test_baseline_metrics.py`
  - `tests/test_bax_runtime.py`
  - `tests/test_bottleneck_alerts.py`
  - `tests/test_bottleneck_wave_certification.py`
  - `tests/test_branch_update_global_invariant.py`
  - `tests/test_build_dashboard_3ls_with_tls.py`
  - `tests/test_build_preflight_pqx_wrapper.py`
  - `tests/test_build_tls_dependency_priority.py`
  - `tests/test_canonical_truth.py`
  - `tests/test_cax_runtime.py`
  - `tests/test_cde_decision_flow.py`
  - `tests/test_certification.py`
  - `tests/test_certification_integrity.py`
  - `tests/test_certification_judgment_40_explicit.py`
  - `tests/test_certification_remediation.py`
  - `tests/test_changed_path_resolution.py`
  - `tests/test_chaos_fail_closed.py`
  - `tests/test_closure_decision_engine.py`
  - `tests/test_cluster_validation.py`
  - `tests/test_codex_to_pqx_wrapper.py`
  - `tests/test_compliance_tracker.py`
  - `tests/test_compliance_workflow_docs.py`
  - `tests/test_consistency_checker.py`
  - `tests/test_context_admission.py`
  - `tests/test_context_assembly.py`
  - `tests/test_context_bundle_v2.py`
  - `tests/test_context_injection.py`
  - `tests/test_context_selector.py`
  - `tests/test_context_trust_model.py`
  - `tests/test_crm_comment_ingestion.py`
  - `tests/test_crm_comment_mapping.py`
  - `tests/test_crm_disposition_tracking.py`
  - `tests/test_crm_resolution_matrix.py`
  - `tests/test_crm_revision_application.py`
  - `tests/test_crm_revision_plan.py`
  - `tests/test_cross_repo_compliance_scanner.py`
  - `tests/test_cross_run_bottleneck_mining.py`
  - `tests/test_cross_run_intelligence.py`
  - `tests/test_cross_run_regressions.py`
  - `tests/test_ctrl_loop_closure.py`
  - `tests/test_ctx_tlx_runtime.py`
  - `tests/test_cycle_observability.py`
  - `tests/test_cycle_runner.py`
  - `tests/test_cycle_runner_judgment_handoff.py`
  - `tests/test_d3l_maturity_report.py`
  - `tests/test_d3l_mvp_graph.py`
  - `tests/test_d3l_rank_maturity_alignment.py`
  - `tests/test_d3l_ranking_report.py`
  - `tests/test_dashboard_refresh_publish_loop.py`
  - `tests/test_dashboard_ui.py`
  - `tests/test_dependency_graph.py`
  - `tests/test_deterministic_id.py`
  - `tests/test_devcontainer_spec.py`
  - `tests/test_done_certification.py`
  - `tests/test_downstream_product_substrate.py`
  - `tests/test_drift_detection.py`
  - `tests/test_drift_detection_debuggability.py`
  - `tests/test_drift_detection_engine.py`
  - `tests/test_drift_remediation.py`
  - `tests/test_drift_response_validation.py`
  - `tests/test_drift_signal_detection.py`
  - `tests/test_end_to_end_failure_simulation.py`
  - `tests/test_entropy_dashboard.py`
  - `tests/test_entropy_detection.py`
  - `tests/test_error_budget.py`
  - `tests/test_error_clustering.py`
  - `tests/test_error_taxonomy.py`
  - `tests/test_evidence_binding.py`
  - `tests/test_evidence_gap_hotspot_report.py`
  - `tests/test_exception_lifecycle.py`
  - `tests/test_exception_router.py`
  - `tests/test_execution_change_impact_analysis.py`
  - `tests/test_execution_event_log.py`
  - `tests/test_execution_hierarchy.py`
  - `tests/test_fail_closed_exhaustive_test.py`
  - `tests/test_failure_class_integrity.py`
  - `tests/test_failure_diagnosis_engine.py`
  - `tests/test_failure_first_observability.py`
  - `tests/test_failure_to_learning.py`
  - `tests/test_feedback_system.py`
  - `tests/test_final_bottleneck_wave_regressions.py`
  - `tests/test_fix_plan.py`
  - `tests/test_fix_simulation.py`
  - `tests/test_fre_repair_flow.py`
  - `tests/test_full_autonomy_execution.py`
  - `tests/test_gap_detection.py`
  - `tests/test_generate_repo_dashboard_snapshot.py`
  - `tests/test_github_closure_continuation.py`
  - `tests/test_github_pr_feedback.py`
  - `tests/test_github_review_handoff.py`
  - `tests/test_github_review_ingestion.py`
  - `tests/test_global_fail_closed.py`
  - `tests/test_harness_integrity_bundle.py`
  - `tests/test_hidden_logic_scanner.py`
  - `tests/test_historical_pytest_exposure_backtest.py`
  - `tests/test_hitl_review_queue.py`
  - `tests/test_hnx_execution_state.py`
  - `tests/test_hnx_hardening.py`
  - `tests/test_jobs_daily.py`
  - `tests/test_jsx_drx_runtime.py`
  - `tests/test_judge_calibration.py`
  - `tests/test_judge_disagreement_report.py`
  - `tests/test_judgment_corpus.py`
  - `tests/test_judgment_learning.py`
  - `tests/test_judgment_override_regressions.py`
  - `tests/test_lha_runtime_wiring.py`
  - `tests/test_maintain_drift_reports.py`
  - `tests/test_map_projection_hardening.py`
  - `tests/test_maturity_model_docs.py`
  - `tests/test_maturity_playbook.py`
  - `tests/test_mnt_platform_reliability_ops.py`
  - `tests/test_model_adapter.py`
  - `tests/test_module_architecture.py`
  - `tests/test_multi_model_checker.py`
  - `tests/test_multi_pass_generation.py`
  - `tests/test_multi_pass_reasoning.py`
  - `tests/test_next24_serial_execution.py`
  - `tests/test_next_step_decision.py`
  - `tests/test_next_wave_runtime.py`
  - `tests/test_ns_certification_evidence_index.py`
  - `tests/test_ns_context_failure_categories.py`
  - `tests/test_ns_end_to_end_redteam.py`
  - `tests/test_ns_loop_proof_bundle.py`
  - `tests/test_ns_reason_codes.py`
  - `tests/test_ns_slo_signal_diet.py`
  - `tests/test_ns_system_justification_v2.py`
  - `tests/test_nt_certification_delta.py`
  - `tests/test_nt_operator_proof_review.py`
  - `tests/test_nt_operator_triage_cli.py`
  - `tests/test_nt_proof_size_budget.py`
  - `tests/test_nt_reason_code_lifecycle.py`
  - `tests/test_nt_trust_freshness.py`
  - `tests/test_nt_trust_regression_pack.py`
  - `tests/test_nx_certification_prerequisites.py`
  - `tests/test_nx_context_admission.py`
  - `tests/test_nx_end_to_end_loop.py`
  - `tests/test_observability.py`
  - `tests/test_observability_engine.py`
  - `tests/test_observability_metrics.py`
  - `tests/test_observability_regressions.py`
  - `tests/test_oc_bottleneck_classifier.py`
  - `tests/test_oc_cleanup_candidate_report.py`
  - `tests/test_oc_cli_smoke.py`
  - `tests/test_oc_closure_decision_packet.py`
  - `tests/test_oc_dashboard_truth_projection.py`
  - `tests/test_oc_operational_closure_bundle.py`
  - `tests/test_oc_operator_runbook.py`
  - `tests/test_oc_proof_intake_index.py`
  - `tests/test_oc_work_selection_signal.py`
  - `tests/test_operating_model_docs.py`
  - `tests/test_operator_shakeout.py`
  - `tests/test_operator_trust_bottleneck_view.py`
  - `tests/test_ops_master_01.py`
  - `tests/test_opx_003_full_build.py`
  - `tests/test_opx_004_durability_build.py`
  - `tests/test_opx_005_runtime.py`
  - `tests/test_orchestration_boundaries.py`
  - `tests/test_osx03_serial_substrate.py`
  - `tests/test_override_hotspot_manager.py`
  - `tests/test_override_hotspot_report.py`
  - `tests/test_parallel_dependency_analyzer.py`
  - `tests/test_parallel_execution_engine.py`
  - `tests/test_pqx_backbone.py`
  - `tests/test_pqx_batch_guardrails.py`
  - `tests/test_pqx_bundle_audit.py`
  - `tests/test_pqx_bundle_certification.py`
  - `tests/test_pqx_bundle_orchestrator.py`
  - `tests/test_pqx_bundle_scheduler.py`
  - `tests/test_pqx_bundle_state.py`
  - `tests/test_pqx_canary_rollout.py`
  - `tests/test_pqx_execution_hardening.py`
  - `tests/test_pqx_fix_execution.py`
  - `tests/test_pqx_handoff_adapter.py`
  - `tests/test_pqx_judgment_record.py`
  - `tests/test_pqx_n_slice_validation.py`
  - `tests/test_pqx_preflight_wrapper_compatibility.py`
  - `tests/test_pqx_proof_closure.py`
  - `tests/test_pqx_sequence_runner.py`
  - `tests/test_pqx_sequential_loop.py`
  - `tests/test_pqx_slice_continuation.py`
  - `tests/test_pqx_slice_runner.py`
  - `tests/test_pqx_triage_planner.py`
  - `tests/test_pr_promotion_hardening.py`
  - `tests/test_pra_nsx_prg_loop.py`
  - `tests/test_pre_pr_repair_loop.py`
  - `tests/test_preflight_failure_normalizer.py`
  - `tests/test_preflight_ref_normalization.py`
  - `tests/test_preflight_selection_diagnostic.py`
  - `tests/test_prg_hardening.py`
  - `tests/test_program_layer.py`
  - `tests/test_promotion_and_a2a_guards.py`
  - `tests/test_promotion_requirement_profile.py`
  - `tests/test_prompt_injection_defense.py`
  - `tests/test_prompt_queue_audit_bundle.py`
  - `tests/test_prompt_queue_blocked_recovery.py`
  - `tests/test_prompt_queue_certification.py`
  - `tests/test_prompt_queue_cli_entrypoint.py`
  - `tests/test_prompt_queue_execution.py`
  - `tests/test_prompt_queue_execution_gating.py`
  - `tests/test_prompt_queue_execution_loop.py`
  - `tests/test_prompt_queue_execution_runner.py`
  - `tests/test_prompt_queue_findings_reentry.py`
  - `tests/test_prompt_queue_live_review_invocation.py`
  - `tests/test_prompt_queue_loop_continuation.py`
  - `tests/test_prompt_queue_mvp.py`
  - `tests/test_prompt_queue_next_step.py`
  - `tests/test_prompt_queue_observability.py`
  - `tests/test_prompt_queue_post_execution.py`
  - `tests/test_prompt_queue_repair_child_creation.py`
  - `tests/test_prompt_queue_repair_prompt_generation.py`
  - `tests/test_prompt_queue_retry.py`
  - `tests/test_prompt_queue_review_parsing.py`
  - `tests/test_prompt_queue_review_parsing_handoff.py`
  - `tests/test_prompt_queue_review_trigger.py`
  - `tests/test_prompt_queue_sequence_cli.py`
  - `tests/test_prompt_queue_step_decision.py`
  - `tests/test_prompt_queue_transition_decision.py`
  - `tests/test_pytest_selection_integrity.py`
  - `tests/test_pytest_trust_gap_audit.py`
  - `tests/test_query_surfaces.py`
  - `tests/test_rax_interface_assurance.py`
  - `tests/test_rax_redteam_adversarial_pack.py`
  - `tests/test_rdx_hardening.py`
  - `tests/test_readiness_promotion_regressions.py`
  - `tests/test_recovery_orchestrator.py`
  - `tests/test_redteam_cross_run_intelligence_harness.py`
  - `tests/test_redteam_final_bottleneck_wave_harness.py`
  - `tests/test_redteam_judgment_override_harness.py`
  - `tests/test_redteam_observability_harness.py`
  - `tests/test_redteam_readiness_promotion_harness.py`
  - `tests/test_redteam_workflow_trust_harness.py`
  - `tests/test_refresh_dashboard_publication.py`
  - `tests/test_regression_harness.py`
  - `tests/test_release_canary.py`
  - `tests/test_remediation_mapping.py`
  - `tests/test_repair_latency_24_01.py`
  - `tests/test_repair_prompt_generator.py`
  - `tests/test_repair_standardization_24_01.py`
  - `tests/test_repo_process_flow_doc.py`
  - `tests/test_repo_review_snapshot_store.py`
  - `tests/test_required_check_alignment_audit.py`
  - `tests/test_responsibility_matrix.py`
  - `tests/test_retroactive_pytest_integrity_audit.py`
  - `tests/test_review_consumer_wiring.py`
  - `tests/test_review_cycle_record_runtime.py`
  - `tests/test_review_examples_valid.py`
  - `tests/test_review_fix_execution_loop.py`
  - `tests/test_review_fix_loop_36_explicit.py`
  - `tests/test_review_handoff_disposition.py`
  - `tests/test_review_orchestrator.py`
  - `tests/test_review_parsing_engine.py`
  - `tests/test_review_projection_adapter.py`
  - `tests/test_review_queue_executor.py`
  - `tests/test_review_readiness_docs.py`
  - `tests/test_review_required_gating.py`
  - `tests/test_review_signal_classifier.py`
  - `tests/test_review_signal_consumer.py`
  - `tests/test_review_signal_extractor.py`
  - `tests/test_rfx_adversarial_reliability_guard.py`
  - `tests/test_rfx_architecture_drift_audit.py`
  - `tests/test_rfx_bloat_budget.py`
  - `tests/test_rfx_calibration.py`
  - `tests/test_rfx_chaos_campaign.py`
  - `tests/test_rfx_cross_run_consistency.py`
  - `tests/test_rfx_debug_bundle.py`
  - `tests/test_rfx_decision_bridge_guard.py`
  - `tests/test_rfx_dependency_map.py`
  - `tests/test_rfx_failure_profile.py`
  - `tests/test_rfx_fix_integrity_proof.py`
  - `tests/test_rfx_freeze_propagation.py`
  - `tests/test_rfx_golden_failure_corpus.py`
  - `tests/test_rfx_golden_loop.py`
  - `tests/test_rfx_integrity_bundle.py`
  - `tests/test_rfx_judgment_extraction.py`
  - `tests/test_rfx_loop_04_06_red_team.py`
  - `tests/test_rfx_loop_07_08_chaos.py`
  - `tests/test_rfx_memory_index.py`
  - `tests/test_rfx_memory_persistence_handoff.py`
  - `tests/test_rfx_module_elimination.py`
  - `tests/test_rfx_operator_runbook.py`
  - `tests/test_rfx_output_envelope.py`
  - `tests/test_rfx_reliability_freeze.py`
  - `tests/test_rfx_route_guard.py`
  - `tests/test_rfx_system_intelligence.py`
  - `tests/test_rfx_trend_analysis.py`
  - `tests/test_rfx_trend_clustering_hardening.py`
  - `tests/test_rfx_unknown_state_campaign.py`
  - `tests/test_rge_amender.py`
  - `tests/test_rge_analysis_engine.py`
  - `tests/test_rge_loop_contribution_checker.py`
  - `tests/test_rge_orchestrator.py`
  - `tests/test_rge_red_teamer.py`
  - `tests/test_rge_three_principle_filter.py`
  - `tests/test_rge_trust_bootstrapper.py`
  - `tests/test_rh_kernel_24_01.py`
  - `tests/test_ril_interpretation.py`
  - `tests/test_rmp_dependency.py`
  - `tests/test_rmp_redteam_loops.py`
  - `tests/test_root_cause_analyzer.py`
  - `tests/test_rq_master_01.py`
  - `tests/test_rq_master_36_01.py`
  - `tests/test_rq_next_24_01.py`
  - `tests/test_rqx_redteam_orchestrator.py`
  - `tests/test_rsm_runtime.py`
  - `tests/test_run_autonomous_validation_run.py`
  - `tests/test_run_bundle_validation.py`
  - `tests/test_run_bundle_validator.py`
  - `tests/test_run_evidence_correlation.py`
  - `tests/test_run_ops02_scheduled_autonomous_execution.py`
  - `tests/test_run_ops03_adversarial_stress_testing.py`
  - `tests/test_run_pqx_bundle_cli.py`
  - `tests/test_run_pqx_sequence_cli.py`
  - `tests/test_run_rfx_super_check.py`
  - `tests/test_runtime_compatibility.py`
  - `tests/test_rwa_runtime_wiring.py`
  - `tests/test_script_module_boundaries.py`
  - `tests/test_sel_orchestration_runner.py`
  - `tests/test_shift_left_hardening_superlayer.py`
  - `tests/test_shift_left_memory_24_01.py`
  - `tests/test_shift_left_preflight.py`
  - `tests/test_signal_bus.py`
  - `tests/test_signal_definitions.py`
  - `tests/test_slide_intelligence.py`
  - `tests/test_slo_definitions.py`
  - `tests/test_slo_gating.py`
  - `tests/test_source_indexes_build.py`
  - `tests/test_source_structured_files_validate.py`
  - `tests/test_strategic_knowledge_catalog.py`
  - `tests/test_strategic_knowledge_pathing.py`
  - `tests/test_strategic_knowledge_validator.py`
  - `tests/test_sync_project_design_sources.py`
  - `tests/test_system_consolidation.py`
  - `tests/test_system_cycle_operator.py`
  - `tests/test_system_elimination.py`
  - `tests/test_system_handoff_integrity.py`
  - `tests/test_system_justification.py`
  - `tests/test_system_lifecycle.py`
  - `tests/test_system_mvp_validation.py`
  - `tests/test_tax_runtime.py`
  - `tests/test_terminal_state_coverage.py`
  - `tests/test_test_inventory_integrity.py`
  - `tests/test_threshold_calibration.py`
  - `tests/test_tlc_handoff_flow.py`
  - `tests/test_tlc_hardening.py`
  - `tests/test_tlc_requires_admission_for_repo_write.py`
  - `tests/test_tls_boundary_map.py`
  - `tests/test_tls_exec_01.py`
  - `tests/test_top_level_conductor.py`
  - `tests/test_tpa_sequence_runner.py`
  - `tests/test_transcript_hardening.py`
  - `tests/test_trust_spine_evidence_cohesion.py`
  - `tests/test_validation.py`
  - `tests/test_validator_engine.py`
  - `tests/test_validator_engine_no_stubs.py`
  - `tests/test_verify_environment.py`
  - `tests/test_work_items.py`
  - `tests/test_workflow_pytest_selection_mapping.py`
  - `tests/test_workflow_semantic_audit.py`
  - `tests/test_workflow_trust_regressions.py`
  - `tests/test_working_paper_engine.py`
  - `tests/test_working_paper_generator.py`
  - `tests/test_working_paper_generator_module.py`
  - `tests/test_working_paper_synthesis.py`
  - `tests/test_wpg_action_items.py`
  - `tests/test_wpg_action_linkage.py`
  - `tests/test_wpg_agency_profiles.py`
  - `tests/test_wpg_certification.py`
  - `tests/test_wpg_comment_matrix_ingestion.py`
  - `tests/test_wpg_cross_run.py`
  - `tests/test_wpg_industry_profiles.py`
  - `tests/test_wpg_judgment_persistence.py`
  - `tests/test_wpg_judgment_records.py`
  - `tests/test_wpg_minutes_generation.py`
  - `tests/test_wpg_multi_pass_critique.py`
  - `tests/test_wpg_precedent.py`
  - `tests/test_wpg_release_readiness_blocking.py`
  - `tests/test_wpg_slo.py`

### Jest surface
- UI/routing/artifact checks: 17 files
  - `tests/artifact-store/postgres-backend.test.ts`
  - `tests/artifact-store/provenance.test.ts`
  - `tests/artifact-store/store.test.ts`
  - `tests/mvp-1/transcript-ingestor.test.ts`
  - `tests/mvp-1/transcript-parser.test.ts`
  - `tests/mvp-10/human-review-gate.test.ts`
  - `tests/mvp-12/publication-formatting.test.ts`
  - `tests/mvp-13/gov10-certification.test.ts`
  - `tests/mvp-2/context-bundle-assembler.test.ts`
  - `tests/mvp-3/ingestion-eval-gate.test.ts`
  - `tests/mvp-4/minutes-extraction.test.ts`
  - `tests/mvp-5/issue-extraction.test.ts`
  - `tests/mvp-6/extraction-eval-gate.test.ts`
  - `tests/mvp-7/issue-structuring.test.ts`
  - `tests/mvp-8/paper-draft-generation.test.ts`
  - `tests/mvp-9/draft-eval-gate.test.ts`
  - `tests/replay/replay-infrastructure.test.ts`
- integration/e2e: 5 files
  - `tests/e2e/real-transcript-e2e.test.ts`
  - `tests/integration/e2e-pipeline.test.ts`
  - `tests/integration/incident-response.test.ts`
  - `tests/integration/pipeline-integration.test.ts`
  - `tests/mvp-11/revision-integration.test.ts`
- governance/policy: 16 files
  - `tests/governance/artifact-intelligence.test.ts`
  - `tests/governance/burn-rate-detector.test.ts`
  - `tests/governance/drift-detector.test.ts`
  - `tests/governance/escalation-engine.test.ts`
  - `tests/governance/exception-governance.test.ts`
  - `tests/governance/fixes-slice-3.test.ts`
  - `tests/governance/fixes-slice-4.test.ts`
  - `tests/governance/fixes-slice-5.test.ts`
  - `tests/governance/fixes-slice-6.test.ts`
  - `tests/governance/fixes-slice-7.test.ts`
  - `tests/governance/fixes-slice-8.test.ts`
  - `tests/governance/lineage-graph.test.ts`
  - `tests/governance/playbook-registry.test.ts`
  - `tests/governance/policy-engine.test.ts`
  - `tests/governance/sli-backend.test.ts`
  - `tests/governance/slo-baseline-tuner.test.ts`
- unit/runtime: 1 files
  - `tests/unit/tlc/protected-file-registry.test.ts`

### Jest configs and package surfaces
- Root package: `package.json` (`test: jest`).
- App packages inspected: `apps/dashboard-3ls/package.json`, `apps/dashboard/package.json`, `dashboard/package.json`.
- Jest configs: `jest.config.js`, `apps/dashboard-3ls/jest.config.js`.

## 5. Governance Policy Surface
- `docs/governance/pytest_pr_selection_integrity_policy.json`
  - minimum_selection_threshold: `1`
  - allow_bounded_equivalence: `True`
  - governed_surface_prefixes: contracts/, scripts/, spectrum_systems/, tests/, .github/workflows/, docs/governance/
  - required test targets by path_prefix:
    - `scripts/run_contract_preflight.py` -> tests/test_contract_preflight.py
    - `spectrum_systems/modules/runtime/github_pr_autofix_contract_preflight.py` -> tests/test_github_pr_autofix_contract_preflight.py
    - `spectrum_systems/modules/runtime/test_inventory_integrity.py` -> tests/test_test_inventory_integrity.py
    - `contracts/` -> tests/test_contracts.py
    - `.github/workflows/artifact-boundary.yml` -> tests/test_artifact_boundary_workflow_pytest_policy_observation.py, tests/test_artifact_boundary_workflow_policy_observation.py
    - `artifacts/dashboard_metrics/` -> tests/metrics/test_met_04_18_contract_selection.py
    - `artifacts/dashboard_cases/` -> tests/metrics/test_met_04_18_contract_selection.py
    - `apps/dashboard-3ls/app/api/intelligence/` -> tests/metrics/test_met_04_18_contract_selection.py
    - `apps/dashboard-3ls/app/page.tsx` -> tests/metrics/test_met_04_18_contract_selection.py
    - `docs/reviews/MET-` -> tests/metrics/test_met_04_18_contract_selection.py
  - fallback/exception behavior: bounded_equivalence entries=1, allowed_exceptions entries=0.
- `docs/governance/pytest_pr_inventory_baseline.json`
  - suite_name: `pr_default`
  - suite_targets: tests/test_eval_dataset_registry.py
  - expected_count: `19`
  - fallback behavior: fail-closed expectation validated via static `expected_nodeids` list of 19 items.

## 6. Duplication Findings
- Script scripts/build_preflight_pqx_wrapper.py reused by artifact-boundary.yml, pr-pytest.yml, pr-autofix-contract-preflight.yml
- Script scripts/run_contract_preflight.py reused by artifact-boundary.yml, pr-pytest.yml, pr-autofix-contract-preflight.yml
- Script scripts/run_github_pr_autofix_contract_preflight.py reused by pr-pytest.yml, pr-autofix-contract-preflight.yml
- Script `scripts/verify_environment.py` reused by `lifecycle-enforcement.yml`, `release-canary.yml`
- Contract preflight validated in artifact-boundary.yml, pr-pytest.yml, and pr-autofix-contract-preflight.yml.
- Review artifact validation checked in review-artifact-validation.yml and pr-autofix-review-artifact-validation.yml.
- Registry/boundary compliance_observation overlaps across artifact-boundary.yml and ecosystem-registry-validation.yml.

## 7. Gate Mapping
| component | primary gate | ambiguity |
|---|---|---|
| `.github/workflows/3ls-registry-gate.yml` | Governance Gate | none |
| `.github/workflows/artifact-boundary.yml` | Contract Gate | spans multiple |
| `.github/workflows/claude-review-ingest.yml` | Governance Gate | none |
| `.github/workflows/closure_continuation_pipeline.yml` | Governance Gate | none |
| `.github/workflows/cross-repo-compliance.yml` | Governance Gate | spans multiple |
| `.github/workflows/dashboard-deploy-gate.yml` | Governance Gate | none |
| `.github/workflows/design-review-scan.yml` | Governance Gate | none |
| `.github/workflows/ecosystem-registry-validation.yml` | Contract Gate | none |
| `.github/workflows/lifecycle-enforcement.yml` | Runtime Test Gate | none |
| `.github/workflows/pr-autofix-contract-preflight.yml` | Contract Gate | none |
| `.github/workflows/pr-autofix-review-artifact-validation.yml` | Governance Gate | none |
| `.github/workflows/pr-pytest.yml` | Governance Gate | none |
| `.github/workflows/release-canary.yml` | Certification Gate | none |
| `.github/workflows/review-artifact-validation.yml` | Governance Gate | none |
| `.github/workflows/review_trigger_pipeline.yml` | Governance Gate | none |
| `.github/workflows/ssos-project-automation.yml` | Governance Gate | none |
| `.github/workflows/strategy-compliance.yml` | Governance Gate | none |
| `scripts/build_preflight_pqx_wrapper.py` | Contract Gate | spans multiple |
| `scripts/check_artifact_boundary.py` | Contract Gate | none |
| `scripts/check_strategy_compliance.py` | Governance Gate | none |
| `scripts/generate_dependency_graph.py` | Governance Gate | none |
| `scripts/generate_ecosystem_architecture_graph.py` | Governance Gate | none |
| `scripts/generate_ecosystem_health_report.py` | Governance Gate | none |
| `scripts/ingest-claude-review.js` | Governance Gate | spans multiple |
| `scripts/refresh_dashboard.sh` | Governance Gate | none |
| `scripts/run_authority_drift_guard.py` | Governance Gate | none |
| `scripts/run_authority_leak_guard.py` | Governance Gate | none |
| `scripts/run_authority_shape_preflight.py` | Governance Gate | spans multiple |
| `scripts/run_contract_enforcement.py` | Contract Gate | none |
| `scripts/run_contract_preflight.py` | Contract Gate | spans multiple |
| `scripts/run_eval_ci_gate.py` | Runtime Test Gate | none |
| `scripts/run_github_pr_autofix_contract_preflight.py` | Contract Gate | spans multiple |
| `scripts/run_governed_failure_injection.py` | Runtime Test Gate | none |
| `scripts/run_release_canary.py` | Certification Gate | none |
| `scripts/run_review_artifact_validation.py` | Governance Gate | spans multiple |
| `scripts/run_rq_master_01.py` | Governance Gate | none |
| `scripts/run_sel_orchestration.py` | Runtime Test Gate | none |
| `scripts/run_sel_replay_gate.py` | Runtime Test Gate | none |
| `scripts/run_system_registry_guard.py` | Contract Gate | none |
| `scripts/validate_dashboard_public_artifacts.py` | Governance Gate | none |
| `scripts/validate_ecosystem_registry.py` | Contract Gate | none |
| `scripts/validate_governance_manifest.py` | Governance Gate | none |
| `scripts/validate_lifecycle_data.py` | Governance Gate | none |
| `scripts/validate_module_architecture.py` | Governance Gate | none |
| `scripts/validate_orchestration_boundaries.py` | Governance Gate | none |
| `scripts/verify_environment.py` | Governance Gate | none |

## 8. Top 5 Risks
- Workflow fragmentation: many workflows validate related invariants with partial overlap, raising drift risk.
- Multi-workflow preflight duplication can produce inconsistent pass/fail semantics across PR and workflow_run contexts.
- Script surface size (252 files) exceeds CI-invoked subset (29), increasing hidden/unvalidated pathway risk.
- Static pytest inventory is very large; selective execution integrity depends on policy artifacts remaining synchronized.
- Some components span multiple gates (contract + governance + certification_signal), creating ownership ambiguity.
