"""Shared fixtures for HOP tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from spectrum_systems.modules.hop.artifacts import finalize_artifact, make_trace
from spectrum_systems.modules.hop.evaluator import EvalSet
from spectrum_systems.modules.hop.experience_store import ExperienceStore
from spectrum_systems.modules.hop.schemas import validate_hop_artifact

REPO_ROOT = Path(__file__).resolve().parents[2]
EVAL_DIR = REPO_ROOT / "contracts" / "evals" / "hop"
HELDOUT_EVAL_DIR = REPO_ROOT / "contracts" / "evals" / "hop_heldout"


def _load_eval_cases() -> list[dict[str, Any]]:
    manifest = json.loads((EVAL_DIR / "manifest.json").read_text(encoding="utf-8"))
    cases: list[dict[str, Any]] = []
    for entry in manifest["cases"]:
        cases.append(json.loads((EVAL_DIR / entry["path"]).read_text(encoding="utf-8")))
    return cases


@pytest.fixture(scope="session")
def eval_cases() -> list[dict[str, Any]]:
    cases = _load_eval_cases()
    for c in cases:
        validate_hop_artifact(c, "hop_harness_eval_case")
    return cases


@pytest.fixture(scope="session")
def eval_manifest() -> dict[str, Any]:
    return json.loads((EVAL_DIR / "manifest.json").read_text(encoding="utf-8"))


@pytest.fixture()
def eval_set(eval_cases) -> EvalSet:
    return EvalSet(
        eval_set_id="hop_transcript_to_faq_v1",
        eval_set_version="1.0.0",
        cases=tuple(eval_cases),
    )


@pytest.fixture()
def store(tmp_path: Path) -> ExperienceStore:
    return ExperienceStore(tmp_path / "store")


@pytest.fixture(scope="session")
def heldout_eval_cases() -> list[dict[str, Any]]:
    manifest = json.loads((HELDOUT_EVAL_DIR / "manifest.json").read_text(encoding="utf-8"))
    cases: list[dict[str, Any]] = []
    for entry in manifest["cases"]:
        cases.append(json.loads((HELDOUT_EVAL_DIR / entry["path"]).read_text(encoding="utf-8")))
    for c in cases:
        validate_hop_artifact(c, "hop_harness_eval_case")
    return cases


@pytest.fixture()
def heldout_eval_set(heldout_eval_cases) -> EvalSet:
    return EvalSet(
        eval_set_id="hop_transcript_to_faq_heldout_v1",
        eval_set_version="1.0.0",
        cases=tuple(heldout_eval_cases),
    )


def make_baseline_candidate(*, code_source: str | None = None) -> dict[str, Any]:
    """Build a HOP harness candidate envelope around the baseline harness.

    Tests use this rather than reading the source from disk so they can also
    construct adversarial mutated copies (e.g. with hardcoded answers).
    """
    if code_source is None:
        from spectrum_systems.modules.hop import baseline_harness as _baseline

        code_source = Path(_baseline.__file__).read_text(encoding="utf-8")
    payload: dict[str, Any] = {
        "artifact_type": "hop_harness_candidate",
        "schema_ref": "hop/harness_candidate.schema.json",
        "schema_version": "1.0.0",
        "trace": make_trace(primary="hop_test_baseline"),
        "candidate_id": "baseline_v1",
        "harness_type": "transcript_to_faq",
        "code_module": "spectrum_systems.modules.hop.baseline_harness",
        "code_entrypoint": "run",
        "code_source": code_source,
        "declared_methods": ["run"],
        "parent_candidate_id": None,
        "tags": ["baseline"],
        "created_at": "2026-04-25T00:00:00.000000Z",
    }
    finalize_artifact(payload, id_prefix="hop_candidate_")
    return payload
