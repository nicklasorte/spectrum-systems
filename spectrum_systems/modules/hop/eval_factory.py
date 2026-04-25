"""HOP eval factory (Phase 2).

The eval factory mines the experience store for failures and near-miss
scoring breakdowns and proposes new eval cases under a new
``eval_set_version``. It is purely advisory:

- it never mutates an existing eval case;
- it never overwrites a manifest;
- it emits a single ``hop_harness_eval_factory_record`` audit artifact whose
  ``candidate_cases`` list each carries the source failure id and a
  category from the closed enum (``regression``, ``near_miss``,
  ``adversarial``, ``failure_derived``).

A separate process is responsible for materializing the proposed cases on
disk and re-generating the manifest; the factory only produces the
*intent* artifact.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping

from spectrum_systems.modules.hop.artifacts import finalize_artifact, make_trace
from spectrum_systems.modules.hop.experience_store import (
    ExperienceStore,
    HopStoreError,
)
from spectrum_systems.modules.hop.schemas import validate_hop_artifact


class EvalFactoryError(Exception):
    """Raised on infrastructure errors inside the eval factory."""


_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _utcnow() -> str:
    return (
        datetime.now(tz=timezone.utc)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )


def _slugify(value: str) -> str:
    return _SLUG_RE.sub("_", value.lower()).strip("_") or "case"


def _bump_patch(version: str) -> str:
    parts = version.split(".")
    if len(parts) != 3 or not all(p.isdigit() for p in parts):
        raise EvalFactoryError(f"hop_eval_factory_invalid_version:{version}")
    major, minor, patch = (int(p) for p in parts)
    return f"{major}.{minor}.{patch + 1}"


@dataclass(frozen=True)
class EvalFactoryConfig:
    max_cases_per_run: int = 32
    near_miss_score_threshold: float = 0.99
    """Per-case scores at or below this threshold count as near misses."""


@dataclass(frozen=True)
class EvalFactoryInputs:
    source_eval_set_id: str
    source_eval_set_version: str
    failures: tuple[Mapping[str, Any], ...]
    near_miss_scores: tuple[Mapping[str, Any], ...]


def _category_for_failure(failure: Mapping[str, Any]) -> str:
    fc = str(failure.get("failure_class", ""))
    if fc == "regression":
        return "regression"
    if fc in {"hardcoded_answer", "eval_dataset_leakage", "schema_weakening"}:
        return "adversarial"
    return "failure_derived"


def _failure_modes_for_failure(failure: Mapping[str, Any]) -> list[str]:
    fc = str(failure.get("failure_class", "")).strip()
    return [fc] if fc else ["unknown"]


def _candidate_case_id(prefix: str, source_id: str) -> str:
    slug = _slugify(source_id)
    return f"hop_case_{prefix}_{slug}"[:128]


def build_eval_factory_record(
    inputs: EvalFactoryInputs,
    *,
    config: EvalFactoryConfig | None = None,
    trace_id: str = "hop_eval_factory",
) -> dict[str, Any]:
    """Build a finalized eval-factory record from the given inputs."""
    cfg = config or EvalFactoryConfig()
    if not isinstance(inputs.source_eval_set_id, str) or not inputs.source_eval_set_id:
        raise EvalFactoryError("hop_eval_factory_invalid_source_eval_set_id")
    next_version = _bump_patch(inputs.source_eval_set_version)

    seen_case_ids: set[str] = set()
    candidate_cases: list[dict[str, Any]] = []
    input_failure_artifact_ids: list[str] = []

    for failure in inputs.failures:
        if len(candidate_cases) >= cfg.max_cases_per_run:
            break
        if not isinstance(failure, Mapping):
            continue
        artifact_id = failure.get("artifact_id")
        if not isinstance(artifact_id, str) or not artifact_id:
            continue
        input_failure_artifact_ids.append(artifact_id)
        category = _category_for_failure(failure)
        candidate_id = str(failure.get("candidate_id", "unknown"))
        case_id = _candidate_case_id(category, f"{candidate_id}_{artifact_id}")
        if case_id in seen_case_ids:
            continue
        seen_case_ids.add(case_id)
        candidate_cases.append(
            {
                "eval_case_id": case_id,
                "category": category,
                "failure_modes_targeted": _failure_modes_for_failure(failure),
                "source_failure_artifact_id": artifact_id,
                "rationale": (
                    f"derived_from_failure:{failure.get('failure_class', '?')}:"
                    f"severity={failure.get('severity', '?')}"
                ),
            }
        )

    for score in inputs.near_miss_scores:
        if len(candidate_cases) >= cfg.max_cases_per_run:
            break
        if not isinstance(score, Mapping):
            continue
        breakdown = score.get("breakdown") or []
        run_id = str(score.get("run_id", "unknown"))
        for entry in breakdown:
            if len(candidate_cases) >= cfg.max_cases_per_run:
                break
            if not isinstance(entry, Mapping):
                continue
            passed = bool(entry.get("passed"))
            entry_score = float(entry.get("score", 0.0))
            if passed and entry_score >= 1.0:
                continue
            if entry_score > cfg.near_miss_score_threshold and passed:
                continue
            eval_case_id = str(entry.get("eval_case_id", "unknown"))
            case_id = _candidate_case_id("near_miss", f"{run_id}_{eval_case_id}")
            if case_id in seen_case_ids:
                continue
            seen_case_ids.add(case_id)
            candidate_cases.append(
                {
                    "eval_case_id": case_id,
                    "category": "near_miss",
                    "failure_modes_targeted": [
                        str(entry.get("failure_reason") or "near_miss")
                    ],
                    "source_failure_artifact_id": None,
                    "rationale": (
                        f"derived_from_near_miss:run={run_id}:"
                        f"case={eval_case_id}:score={entry_score:.4f}"
                    ),
                }
            )

    payload: dict[str, Any] = {
        "artifact_type": "hop_harness_eval_factory_record",
        "schema_ref": "hop/harness_eval_factory_record.schema.json",
        "schema_version": "1.0.0",
        "trace": make_trace(primary=trace_id, related=[inputs.source_eval_set_id]),
        "factory_run_id": f"evalfactory_{inputs.source_eval_set_id}_{next_version.replace('.', '_')}",
        "source_eval_set_id": inputs.source_eval_set_id,
        "source_eval_set_version": inputs.source_eval_set_version,
        "next_eval_set_version": next_version,
        "input_failure_artifact_ids": input_failure_artifact_ids,
        "candidate_cases": candidate_cases,
        "advisory_only": True,
        "generated_at": _utcnow(),
    }
    finalize_artifact(payload, id_prefix="hop_evalfactory_")
    validate_hop_artifact(payload, "hop_harness_eval_factory_record")
    return payload


def _find_existing_eval_factory_record(
    store: ExperienceStore, factory_run_id: str
) -> dict[str, Any] | None:
    for rec in store.iter_index(artifact_type="hop_harness_eval_factory_record"):
        fields = rec.get("fields", {}) or {}
        if fields.get("factory_run_id") == factory_run_id:
            try:
                return store.read_artifact(
                    "hop_harness_eval_factory_record", rec["artifact_id"]
                )
            except HopStoreError:
                continue
    return None


def emit_eval_factory_record(
    inputs: EvalFactoryInputs,
    *,
    store: ExperienceStore,
    config: EvalFactoryConfig | None = None,
    trace_id: str = "hop_eval_factory",
) -> dict[str, Any]:
    next_version = _bump_patch(inputs.source_eval_set_version)
    logical_id = (
        f"evalfactory_{inputs.source_eval_set_id}_"
        f"{next_version.replace('.', '_')}"
    )
    existing = _find_existing_eval_factory_record(store, logical_id)
    if existing is not None:
        return existing
    record = build_eval_factory_record(inputs, config=config, trace_id=trace_id)
    try:
        store.write_artifact(record)
    except HopStoreError as exc:
        if "duplicate_artifact" in str(exc):
            return record
        raise
    return record


def collect_inputs_from_store(
    store: ExperienceStore,
    *,
    source_eval_set_id: str,
    source_eval_set_version: str,
    candidate_id: str | None = None,
    max_failures: int = 64,
    max_scores: int = 64,
) -> EvalFactoryInputs:
    """Read failures and scores from the store, applying simple bounds."""
    failures: list[Mapping[str, Any]] = []
    for rec in store.list_failures(candidate_id=candidate_id):
        if len(failures) >= max_failures:
            break
        try:
            failures.append(
                store.read_artifact(
                    "hop_harness_failure_hypothesis", rec["artifact_id"]
                )
            )
        except HopStoreError:
            continue

    scores: list[Mapping[str, Any]] = []
    for rec in store.list_scores(candidate_id=candidate_id):
        if len(scores) >= max_scores:
            break
        try:
            scores.append(store.read_artifact("hop_harness_score", rec["artifact_id"]))
        except HopStoreError:
            continue

    return EvalFactoryInputs(
        source_eval_set_id=source_eval_set_id,
        source_eval_set_version=source_eval_set_version,
        failures=tuple(failures),
        near_miss_scores=tuple(scores),
    )


def list_records(store: ExperienceStore) -> Iterable[Mapping[str, Any]]:
    for rec in store.iter_index(artifact_type="hop_harness_eval_factory_record"):
        try:
            yield store.read_artifact(
                "hop_harness_eval_factory_record", rec["artifact_id"]
            )
        except HopStoreError:
            continue
