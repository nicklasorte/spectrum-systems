from __future__ import annotations

import pytest

from spectrum_systems.utils.artifact_envelope import (
    ArtifactEnvelopeError,
    build_artifact_envelope,
    normalize_trace_refs,
    validate_trace_refs,
)


def test_build_artifact_envelope_produces_canonical_shape() -> None:
    envelope = build_artifact_envelope(
        artifact_id="artifact-1",
        timestamp="2026-03-24T00:00:00Z",
        schema_version="1.1.0",
        primary_trace_ref="trace://primary",
        related_trace_refs=["trace://secondary", "trace://primary", ""],
    )

    assert envelope == {
        "id": "artifact-1",
        "timestamp": "2026-03-24T00:00:00Z",
        "schema_version": "1.1.0",
        "trace_refs": {
            "primary": "trace://primary",
            "related": ["trace://secondary"],
        },
    }


def test_validate_trace_refs_rejects_unknown_keys() -> None:
    with pytest.raises(ArtifactEnvelopeError):
        validate_trace_refs({"primary": "trace://x", "related": [], "extra": "nope"})


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"primary": "", "related": []},
        {"primary": "trace://x", "related": "not-a-list"},
    ],
)
def test_validate_trace_refs_rejects_malformed_payload(payload: object) -> None:
    with pytest.raises(ArtifactEnvelopeError):
        validate_trace_refs(payload)  # type: ignore[arg-type]


def test_normalize_trace_refs_requires_primary() -> None:
    with pytest.raises(ArtifactEnvelopeError):
        normalize_trace_refs(primary="", related=[])
