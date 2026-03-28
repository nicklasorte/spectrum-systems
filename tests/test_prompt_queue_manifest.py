"""Fail-closed tests for prompt queue manifest contract spine."""

from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.contracts import load_example  # noqa: E402
from spectrum_systems.modules.prompt_queue.queue_manifest_validator import validate_queue_manifest  # noqa: E402


def test_valid_manifest():
    manifest = load_example("prompt_queue_manifest")
    normalized = validate_queue_manifest(manifest)
    assert normalized == manifest


def test_missing_fields_fails():
    manifest = load_example("prompt_queue_manifest")
    manifest.pop("execution_policy")
    with pytest.raises(ValueError):
        validate_queue_manifest(manifest)


def test_extra_fields_fail():
    manifest = load_example("prompt_queue_manifest")
    manifest["unexpected"] = "nope"
    with pytest.raises(ValueError):
        validate_queue_manifest(manifest)


def test_invalid_types_fail():
    manifest = load_example("prompt_queue_manifest")
    manifest["steps"][0]["input_refs"] = "prompt_queue_work_item:wi-001"
    with pytest.raises(ValueError):
        validate_queue_manifest(manifest)


def test_deterministic_ids():
    manifest = load_example("prompt_queue_manifest")
    reordered = copy.deepcopy(manifest)
    reordered["steps"][1]["step_id"] = "step-004"
    with pytest.raises(ValueError):
        validate_queue_manifest(reordered)

    valid = validate_queue_manifest(manifest)
    assert [step["step_id"] for step in valid["steps"]] == ["step-001", "step-002", "step-003"]
