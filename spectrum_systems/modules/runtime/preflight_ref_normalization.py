"""Canonical event-aware ref normalization for governed preflight execution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class PreflightRefResolution:
    valid: bool
    base_ref: str
    head_ref: str
    normalization_strategy: str
    fallback_used: bool
    event_name: str
    invalid_reason: str | None
    reason_code: str | None
    raw_inputs: dict[str, str]

    def as_dict(self) -> dict[str, object]:
        return {
            "valid": self.valid,
            "base_ref": self.base_ref,
            "head_ref": self.head_ref,
            "normalization_strategy": self.normalization_strategy,
            "fallback_used": self.fallback_used,
            "event_name": self.event_name,
            "invalid_reason": self.invalid_reason,
            "reason_code": self.reason_code,
            "raw_inputs": dict(self.raw_inputs),
        }


def _clean(value: str | None) -> str:
    if value is None:
        return ""
    return str(value).strip()


def normalize_preflight_ref_context(
    *,
    event_name: str | None,
    cli_base_ref: str | None,
    cli_head_ref: str | None,
    env: Mapping[str, str] | None,
) -> PreflightRefResolution:
    env_map = {k: _clean(v) for k, v in dict(env or {}).items()}
    normalized_event = _clean(event_name).lower() or _clean(env_map.get("GITHUB_EVENT_NAME")).lower() or "local"

    cli_base = _clean(cli_base_ref)
    cli_head = _clean(cli_head_ref)
    has_cli_pair = bool(cli_base and cli_head)
    partial_cli = bool(cli_base or cli_head) and not has_cli_pair

    raw_inputs = {
        "event_name": normalized_event,
        "cli_base_ref": cli_base,
        "cli_head_ref": cli_head,
        "github_base_sha": _clean(env_map.get("GITHUB_BASE_SHA")),
        "github_head_sha": _clean(env_map.get("GITHUB_HEAD_SHA")),
        "github_before_sha": _clean(env_map.get("GITHUB_BEFORE_SHA")),
        "github_sha": _clean(env_map.get("GITHUB_SHA")),
    }

    if partial_cli:
        return PreflightRefResolution(
            valid=False,
            base_ref="",
            head_ref="",
            normalization_strategy="rejected_partial_cli_pair",
            fallback_used=False,
            event_name=normalized_event,
            invalid_reason="explicit CLI refs must provide both base and head",
            reason_code="malformed_ref_context",
            raw_inputs=raw_inputs,
        )

    if has_cli_pair:
        return PreflightRefResolution(
            valid=True,
            base_ref=cli_base,
            head_ref=cli_head,
            normalization_strategy="explicit_cli_pair",
            fallback_used=False,
            event_name=normalized_event,
            invalid_reason=None,
            reason_code=None,
            raw_inputs=raw_inputs,
        )

    if normalized_event == "pull_request":
        env_base = _clean(env_map.get("GITHUB_BASE_SHA"))
        env_head = _clean(env_map.get("GITHUB_HEAD_SHA"))
        if env_base and env_head:
            return PreflightRefResolution(
                valid=True,
                base_ref=env_base,
                head_ref=env_head,
                normalization_strategy="pull_request_env_pair",
                fallback_used=True,
                event_name=normalized_event,
                invalid_reason=None,
                reason_code=None,
                raw_inputs=raw_inputs,
            )
        return PreflightRefResolution(
            valid=False,
            base_ref="",
            head_ref="",
            normalization_strategy="pull_request_env_missing",
            fallback_used=True,
            event_name=normalized_event,
            invalid_reason="pull_request context requires GITHUB_BASE_SHA and GITHUB_HEAD_SHA when CLI refs are absent",
            reason_code="missing_refs",
            raw_inputs=raw_inputs,
        )

    if normalized_event == "push":
        env_base = _clean(env_map.get("GITHUB_BEFORE_SHA"))
        env_head = _clean(env_map.get("GITHUB_SHA"))
        if env_base and env_head:
            return PreflightRefResolution(
                valid=True,
                base_ref=env_base,
                head_ref=env_head,
                normalization_strategy="push_before_sha_fallback",
                fallback_used=True,
                event_name=normalized_event,
                invalid_reason=None,
                reason_code=None,
                raw_inputs=raw_inputs,
            )
        return PreflightRefResolution(
            valid=False,
            base_ref="",
            head_ref="",
            normalization_strategy="push_env_missing",
            fallback_used=True,
            event_name=normalized_event,
            invalid_reason="push context requires GITHUB_BEFORE_SHA and GITHUB_SHA when CLI refs are absent",
            reason_code="missing_refs",
            raw_inputs=raw_inputs,
        )

    if normalized_event in {"workflow_dispatch", "local", "unspecified", ""}:
        return PreflightRefResolution(
            valid=False,
            base_ref="",
            head_ref="",
            normalization_strategy="dispatch_or_local_requires_explicit_refs",
            fallback_used=False,
            event_name=normalized_event,
            invalid_reason="workflow_dispatch/local execution requires explicit --base-ref and --head-ref",
            reason_code="unsupported_event_context",
            raw_inputs=raw_inputs,
        )

    return PreflightRefResolution(
        valid=False,
        base_ref="",
        head_ref="",
        normalization_strategy="unsupported_event_type",
        fallback_used=False,
        event_name=normalized_event,
        invalid_reason=f"unsupported event context: {normalized_event}",
        reason_code="unsupported_event_context",
        raw_inputs=raw_inputs,
    )


__all__ = ["PreflightRefResolution", "normalize_preflight_ref_context"]
