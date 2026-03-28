"""Validation entrypoint for prompt queue manifests."""

from __future__ import annotations

from spectrum_systems.modules.prompt_queue.queue_models import PromptQueueManifest, validate_queue_manifest_dict


def validate_queue_manifest(manifest: dict) -> dict:
    """Validate and return a normalized prompt queue manifest.

    Validation is fail-closed: any schema or deterministic-ordering violation raises ValueError.
    """

    normalized = validate_queue_manifest_dict(manifest)
    model = PromptQueueManifest(
        queue_id=normalized["queue_id"],
        created_at=normalized["created_at"],
        version=normalized["version"],
        steps=normalized["steps"],
        execution_policy=normalized["execution_policy"],
    )
    return model.to_dict()
