"""Policy observation signals for the artifact-boundary workflow.

These tests are non-authoritative: they observe surface-level policy signals on
the canonical workflow file. They do not redefine ownership and do not replace
canonical SEL/CDE/PQX governance — they only assert that the workflow's
governed-contract-preflight job emits authoritative refs, sufficient checkout
history, and identical base/head signals to wrapper and runner.
"""

from __future__ import annotations

from pathlib import Path

ARTIFACT_BOUNDARY_WORKFLOW = Path('.github/workflows/artifact-boundary.yml')


def _governed_preflight_block() -> str:
    text = ARTIFACT_BOUNDARY_WORKFLOW.read_text(encoding='utf-8')
    assert 'governed-contract-preflight:' in text
    after = text.split('governed-contract-preflight:', 1)[1]
    # Stop at the next top-level job declaration.
    return after.split('\n  run-pytest:', 1)[0]


def test_workflow_pr_branch_does_not_emit_blank_preflight_scope_signal() -> None:
    block = _governed_preflight_block()
    # Blank refs in PR branch were the prior defect; they must not reappear.
    assert 'base_ref=\n' not in block
    assert 'head_ref=\n' not in block
    assert 'base_ref=""' not in block
    assert 'head_ref=""' not in block
    # A guard must explicitly block empty refs from being emitted as outputs.
    assert 'empty base_ref/head_ref' in block


def test_workflow_pr_branch_uses_pull_request_base_and_head_sha() -> None:
    block = _governed_preflight_block()
    pr_clause = block.split('pull_request', 1)[1].split('elif', 1)[0]
    assert 'github.event.pull_request.base.sha' in pr_clause
    assert 'github.event.pull_request.head.sha' in pr_clause


def test_workflow_push_branch_uses_event_before_and_github_sha() -> None:
    block = _governed_preflight_block()
    push_clause = block.split('elif', 1)[1].split('else', 1)[0]
    assert '"push"' in push_clause
    assert 'github.event.before' in push_clause
    assert 'github.sha' in push_clause


def test_workflow_unsupported_event_fails_closed_for_contract_preflight_ref_signal() -> None:
    block = _governed_preflight_block()
    else_clause = block.split('else', 1)[1].split('fi', 1)[0]
    # Unknown event surfaces must halt rather than silently broaden scope.
    assert 'unsupported event' in else_clause
    assert 'exit 2' in else_clause


def test_governed_contract_preflight_runs_for_pull_request_and_push_events() -> None:
    block = _governed_preflight_block()
    # Job-level gate must include both pull_request and push events.
    assert "github.event_name == 'push'" in block
    assert "github.event_name == 'pull_request'" in block


def test_governed_contract_preflight_checkout_depth_is_sufficient_for_pr_base_head_resolution() -> None:
    block = _governed_preflight_block()
    # PR base.sha is generally not a direct ancestor of head — fetch-depth: 2
    # is insufficient. fetch-depth: 0 fetches full history for both PR and push
    # base/head SHAs.
    assert 'fetch-depth: 0' in block
    assert 'fetch-depth: 2' not in block


def test_build_preflight_pqx_wrapper_invocation_uses_shared_base_head_outputs() -> None:
    block = _governed_preflight_block()
    wrapper_invocation_start = block.index('python scripts/build_preflight_pqx_wrapper.py')
    wrapper_invocation_end = block.index('python scripts/run_contract_preflight.py')
    wrapper_block = block[wrapper_invocation_start:wrapper_invocation_end]
    assert '--base-ref "${{ steps.preflight-refs.outputs.base_ref }}"' in wrapper_block
    assert '--head-ref "${{ steps.preflight-refs.outputs.head_ref }}"' in wrapper_block


def test_run_contract_preflight_invocation_uses_shared_base_head_outputs() -> None:
    block = _governed_preflight_block()
    runner_invocation_start = block.index('python scripts/run_contract_preflight.py')
    runner_block = block[runner_invocation_start:]
    assert '--base-ref "${{ steps.preflight-refs.outputs.base_ref }}"' in runner_block
    assert '--head-ref "${{ steps.preflight-refs.outputs.head_ref }}"' in runner_block


def test_wrapper_and_runner_share_identical_preflight_scope_signal() -> None:
    """Wrapper and runner must consume the same preflight-refs step outputs.

    A divergent signal (e.g. wrapper resolving one diff while runner evaluates
    another) would silently broaden scope; this test pins that they share a
    single resolved base/head pair from the same workflow step.
    """
    block = _governed_preflight_block()
    wrapper_start = block.index('python scripts/build_preflight_pqx_wrapper.py')
    runner_start = block.index('python scripts/run_contract_preflight.py')
    assert wrapper_start < runner_start
    shared_base = '--base-ref "${{ steps.preflight-refs.outputs.base_ref }}"'
    shared_head = '--head-ref "${{ steps.preflight-refs.outputs.head_ref }}"'
    wrapper_segment = block[wrapper_start:runner_start]
    runner_segment = block[runner_start:]
    assert wrapper_segment.count(shared_base) == 1
    assert wrapper_segment.count(shared_head) == 1
    assert runner_segment.count(shared_base) == 1
    assert runner_segment.count(shared_head) == 1
