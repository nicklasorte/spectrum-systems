from __future__ import annotations

from spectrum_systems.modules.runtime.preflight_ref_normalization import normalize_preflight_ref_context


def test_push_uses_before_and_sha_when_cli_missing() -> None:
    result = normalize_preflight_ref_context(
        event_name="push",
        cli_base_ref="",
        cli_head_ref="",
        env={"GITHUB_BEFORE_SHA": "base123", "GITHUB_SHA": "head456", "GITHUB_BASE_SHA": "", "GITHUB_HEAD_SHA": ""},
    )

    assert result.valid is True
    assert result.base_ref == "base123"
    assert result.head_ref == "head456"
    assert result.normalization_strategy == "push_before_sha_fallback"


def test_pull_request_uses_env_pair_when_cli_missing() -> None:
    result = normalize_preflight_ref_context(
        event_name="pull_request",
        cli_base_ref="",
        cli_head_ref="",
        env={"GITHUB_BASE_SHA": "prbase", "GITHUB_HEAD_SHA": "prhead"},
    )

    assert result.valid is True
    assert result.base_ref == "prbase"
    assert result.head_ref == "prhead"


def test_workflow_dispatch_requires_explicit_refs() -> None:
    result = normalize_preflight_ref_context(event_name="workflow_dispatch", cli_base_ref="", cli_head_ref="", env={})

    assert result.valid is False
    assert result.reason_code == "unsupported_event_context"


def test_cli_pair_overrides_env() -> None:
    result = normalize_preflight_ref_context(
        event_name="push",
        cli_base_ref="cli-base",
        cli_head_ref="cli-head",
        env={"GITHUB_BEFORE_SHA": "env-base", "GITHUB_SHA": "env-head"},
    )

    assert result.valid is True
    assert result.base_ref == "cli-base"
    assert result.head_ref == "cli-head"
    assert result.normalization_strategy == "explicit_cli_pair"


def test_partial_cli_pair_fails_closed() -> None:
    result = normalize_preflight_ref_context(event_name="push", cli_base_ref="only-base", cli_head_ref="", env={"GITHUB_SHA": "x"})

    assert result.valid is False
    assert result.reason_code == "malformed_ref_context"


def test_unknown_event_fails_closed() -> None:
    result = normalize_preflight_ref_context(event_name="schedule", cli_base_ref="", cli_head_ref="", env={})

    assert result.valid is False
    assert result.reason_code == "unsupported_event_context"
