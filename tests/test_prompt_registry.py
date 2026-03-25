from __future__ import annotations

import json
from pathlib import Path

import pytest

from spectrum_systems.modules.runtime.prompt_registry import (
    PromptRegistryError,
    assert_prompt_registered,
    load_prompt_alias_map,
    load_prompt_registry_entries,
    resolve_prompt_version,
)


def _write_json(path: Path, payload: dict) -> Path:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def _entry(*, version: str = "v1.0.0", status: str = "approved") -> dict:
    text = "You are the AG runtime control prompt. Execute only declared bounded steps."
    # Precomputed sha256 for text above.
    immutability_hash = "sha256:babde641d72a7df123f15ce11e89c00738f9592eb649ee6bf8afd6c14d4b4d02"
    return {
        "artifact_type": "prompt_registry_entry",
        "schema_version": "1.0.0",
        "prompt_id": "ag.runtime.default",
        "prompt_version": version,
        "created_at": "2026-03-24T00:00:00Z",
        "status": status,
        "owner": {"team": "runtime-governance", "contact": "runtime-governance@spectrum-systems.test"},
        "risk_class": "high",
        "prompt_text": text,
        "prompt_purpose": "Deterministic AG runtime execution guidance.",
        "linked_eval_set_ids": ["ag-runtime-golden-path-v1"],
        "runtime_metadata": {
            "immutability_hash": immutability_hash,
            "selection_key": f"ag.runtime.default@{version}",
        },
    }


def _alias_map(*, version: str = "v1.0.0", allow_deprecated: bool = False) -> dict:
    return {
        "artifact_type": "prompt_alias_map",
        "schema_version": "1.0.0",
        "created_at": "2026-03-24T00:00:00Z",
        "alias_scope": "ag_runtime",
        "aliases": [
            {
                "prompt_id": "ag.runtime.default",
                "alias": "prod",
                "prompt_version": version,
                "allow_deprecated": allow_deprecated,
            }
        ],
    }


def test_deterministic_alias_resolution(tmp_path: Path) -> None:
    entry_path = _write_json(tmp_path / "entry.json", _entry())
    alias_path = _write_json(tmp_path / "aliases.json", _alias_map())

    entries = load_prompt_registry_entries([entry_path])
    alias_map = load_prompt_alias_map(alias_path)

    first = resolve_prompt_version(
        prompt_id="ag.runtime.default",
        alias="prod",
        entries=entries,
        alias_map=alias_map,
    )
    second = resolve_prompt_version(
        prompt_id="ag.runtime.default",
        alias="prod",
        entries=entries,
        alias_map=alias_map,
    )

    assert first == second
    assert first["prompt_version"] == "v1.0.0"


def test_ambiguous_alias_resolution_rejected(tmp_path: Path) -> None:
    entry_path = _write_json(tmp_path / "entry.json", _entry())
    alias_payload = _alias_map()
    alias_payload["aliases"].append(dict(alias_payload["aliases"][0]))
    alias_path = _write_json(tmp_path / "aliases.json", alias_payload)

    entries = load_prompt_registry_entries([entry_path])
    alias_map = load_prompt_alias_map(alias_path)

    with pytest.raises(PromptRegistryError, match="ambiguous alias resolution"):
        resolve_prompt_version(
            prompt_id="ag.runtime.default",
            alias="prod",
            entries=entries,
            alias_map=alias_map,
        )


def test_missing_alias_resolution_rejected(tmp_path: Path) -> None:
    entry_path = _write_json(tmp_path / "entry.json", _entry())
    alias_path = _write_json(tmp_path / "aliases.json", _alias_map())

    entries = load_prompt_registry_entries([entry_path])
    alias_map = load_prompt_alias_map(alias_path)

    with pytest.raises(PromptRegistryError, match="no alias resolution"):
        resolve_prompt_version(
            prompt_id="ag.runtime.default",
            alias="staging",
            entries=entries,
            alias_map=alias_map,
        )


def test_deprecated_status_handling(tmp_path: Path) -> None:
    entry_path = _write_json(tmp_path / "entry.json", _entry(status="deprecated"))
    alias_path = _write_json(tmp_path / "aliases.json", _alias_map(allow_deprecated=False))

    entries = load_prompt_registry_entries([entry_path])
    alias_map = load_prompt_alias_map(alias_path)

    with pytest.raises(PromptRegistryError, match="deprecated"):
        resolve_prompt_version(
            prompt_id="ag.runtime.default",
            alias="prod",
            entries=entries,
            alias_map=alias_map,
        )


def test_no_fallback_to_latest_behavior(tmp_path: Path) -> None:
    entry_v1 = _write_json(tmp_path / "entry-v1.json", _entry(version="v1.0.0"))
    _write_json(tmp_path / "entry-v2.json", _entry(version="v2.0.0"))
    alias_path = _write_json(tmp_path / "aliases.json", _alias_map(version="v3.0.0"))

    entries = load_prompt_registry_entries([entry_v1, tmp_path / "entry-v2.json"])
    alias_map = load_prompt_alias_map(alias_path)

    with pytest.raises(PromptRegistryError, match="missing or ambiguous immutable entry"):
        resolve_prompt_version(
            prompt_id="ag.runtime.default",
            alias="prod",
            entries=entries,
            alias_map=alias_map,
        )


def test_assert_prompt_registered_returns_entry(tmp_path: Path) -> None:
    entry_path = _write_json(tmp_path / "entry.json", _entry(version="v1.2.3"))
    entries = load_prompt_registry_entries([entry_path])

    selected = assert_prompt_registered(
        prompt_id="ag.runtime.default",
        prompt_version="v1.2.3",
        entries=entries,
    )

    assert selected["prompt_id"] == "ag.runtime.default"
    assert selected["prompt_version"] == "v1.2.3"


def test_assert_prompt_registered_rejects_missing_or_draft(tmp_path: Path) -> None:
    approved_path = _write_json(tmp_path / "entry-approved.json", _entry(version="v1.0.0"))
    draft_path = _write_json(tmp_path / "entry-draft.json", _entry(version="v2.0.0", status="draft"))
    entries = load_prompt_registry_entries([approved_path, draft_path])

    with pytest.raises(PromptRegistryError, match="not found or ambiguous"):
        assert_prompt_registered(
            prompt_id="ag.runtime.default",
            prompt_version="v9.9.9",
            entries=entries,
        )

    with pytest.raises(PromptRegistryError, match="draft"):
        assert_prompt_registered(
            prompt_id="ag.runtime.default",
            prompt_version="v2.0.0",
            entries=entries,
        )
