from __future__ import annotations

from pathlib import Path


ARTIFACT_BOUNDARY_WORKFLOW = Path('.github/workflows/artifact-boundary.yml')


def _workflow_text() -> str:
    return ARTIFACT_BOUNDARY_WORKFLOW.read_text(encoding='utf-8')


def test_contract_preflight_ref_signal_pull_request_uses_merge_aware_head_ref() -> None:
    text = _workflow_text()
    assert 'if [[ "${GITHUB_EVENT_NAME}" == "pull_request" ]]; then' in text
    assert 'echo "base_ref=${{ github.event.pull_request.base.sha }}" >> "$GITHUB_OUTPUT"' in text
    assert 'echo "head_ref=${{ github.sha }}" >> "$GITHUB_OUTPUT"' in text


def test_contract_preflight_ref_signal_pull_request_does_not_emit_blank_refs() -> None:
    text = _workflow_text()
    assert 'echo "base_ref=" >> "$GITHUB_OUTPUT"' not in text
    assert 'echo "head_ref=" >> "$GITHUB_OUTPUT"' not in text


def test_contract_preflight_ref_signal_push_uses_before_and_sha() -> None:
    text = _workflow_text()
    assert 'elif [[ "${GITHUB_EVENT_NAME}" == "push" ]]; then' in text
    assert 'echo "base_ref=${{ github.event.before }}" >> "$GITHUB_OUTPUT"' in text
    assert 'echo "head_ref=${{ github.sha }}" >> "$GITHUB_OUTPUT"' in text


def test_preflight_scope_signal_checkout_depth_supports_pr_and_push_ref_resolution() -> None:
    text = _workflow_text()
    governed_block = text.split('governed-contract-preflight:', 1)[1].split('run-pytest:', 1)[0]
    assert 'fetch-depth: 0' in governed_block


def test_preflight_scope_signal_wrapper_and_runner_share_ref_outputs() -> None:
    text = _workflow_text()
    assert 'python scripts/build_preflight_pqx_wrapper.py \\\n            --base-ref "${{ steps.preflight-refs.outputs.base_ref }}" \\\n            --head-ref "${{ steps.preflight-refs.outputs.head_ref }}"' in text
    assert 'python scripts/run_contract_preflight.py \\\n            --base-ref "${{ steps.preflight-refs.outputs.base_ref }}" \\\n            --head-ref "${{ steps.preflight-refs.outputs.head_ref }}"' in text


def test_contract_preflight_ref_signal_unsupported_events_fail_closed() -> None:
    text = _workflow_text()
    assert 'Unsupported event for governed preflight: ${GITHUB_EVENT_NAME}' in text
    assert 'exit 1' in text
