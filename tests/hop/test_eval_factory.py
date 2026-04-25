"""Tests for eval_factory.py — failure / near-miss -> new eval cases."""

from __future__ import annotations

import pytest

from spectrum_systems.modules.hop.artifacts import finalize_artifact, make_trace
from spectrum_systems.modules.hop.eval_factory import (
    EvalFactoryConfig,
    EvalFactoryError,
    EvalFactoryInputs,
    build_eval_factory_record,
    collect_inputs_from_store,
    emit_eval_factory_record,
)
from spectrum_systems.modules.hop.evaluator import evaluate_candidate
from spectrum_systems.modules.hop.schemas import validate_hop_artifact
from tests.hop.conftest import make_baseline_candidate


def _make_failure(
    *,
    artifact_id_seed: str,
    failure_class: str,
    candidate_id: str = "cand_a",
    severity: str = "reject",
) -> dict:
    payload = {
        "artifact_type": "hop_harness_failure_hypothesis",
        "schema_ref": "hop/harness_failure_hypothesis.schema.json",
        "schema_version": "1.0.0",
        "trace": make_trace(primary="hop_test", related=[candidate_id]),
        "hypothesis_id": f"h_{artifact_id_seed}",
        "candidate_id": candidate_id,
        "run_id": f"run_{artifact_id_seed}",
        "stage": "evaluation",
        "failure_class": failure_class,
        "severity": severity,
        "evidence": [{"kind": "snippet", "detail": "test"}],
        "detected_at": "2026-04-25T00:00:00.000000Z",
        "release_block_signal": severity == "reject",
    }
    finalize_artifact(payload, id_prefix="hop_failure_")
    return payload


def test_build_record_from_failures():
    failures = (
        _make_failure(artifact_id_seed="a", failure_class="regression"),
        _make_failure(artifact_id_seed="b", failure_class="hardcoded_answer"),
        _make_failure(artifact_id_seed="c", failure_class="schema_violation"),
    )
    record = build_eval_factory_record(
        EvalFactoryInputs(
            source_eval_set_id="hop_transcript_to_faq_v1",
            source_eval_set_version="1.0.0",
            failures=failures,
            near_miss_scores=(),
        )
    )
    assert record["next_eval_set_version"] == "1.0.1"
    assert len(record["candidate_cases"]) == 3
    cats = [c["category"] for c in record["candidate_cases"]]
    assert "regression" in cats
    assert "adversarial" in cats
    assert "failure_derived" in cats


def test_build_record_from_near_misses(eval_set):
    candidate = make_baseline_candidate()
    bundle = evaluate_candidate(candidate_payload=candidate, eval_set=eval_set)
    score = bundle["score"]
    # Force a synthetic near-miss row.
    score = dict(score)
    score["breakdown"] = list(score["breakdown"]) + [
        {
            "eval_case_id": "synthetic_near_miss",
            "passed": False,
            "score": 0.5,
            "latency_ms": 1.0,
            "failure_reason": "items_below_min:0<1",
        }
    ]
    record = build_eval_factory_record(
        EvalFactoryInputs(
            source_eval_set_id=eval_set.eval_set_id,
            source_eval_set_version=eval_set.eval_set_version,
            failures=(),
            near_miss_scores=(score,),
        )
    )
    assert any(c["category"] == "near_miss" for c in record["candidate_cases"])


def test_invalid_version_rejected():
    with pytest.raises(EvalFactoryError, match="invalid_version"):
        build_eval_factory_record(
            EvalFactoryInputs(
                source_eval_set_id="x",
                source_eval_set_version="not_a_semver",
                failures=(),
                near_miss_scores=(),
            )
        )


def test_emit_persists_and_validates(store):
    failures = (_make_failure(artifact_id_seed="a", failure_class="regression"),)
    record = emit_eval_factory_record(
        EvalFactoryInputs(
            source_eval_set_id="hop_transcript_to_faq_v1",
            source_eval_set_version="1.0.0",
            failures=failures,
            near_miss_scores=(),
        ),
        store=store,
    )
    validate_hop_artifact(record, "hop_harness_eval_factory_record")
    again = emit_eval_factory_record(
        EvalFactoryInputs(
            source_eval_set_id="hop_transcript_to_faq_v1",
            source_eval_set_version="1.0.0",
            failures=failures,
            near_miss_scores=(),
        ),
        store=store,
    )
    assert again["artifact_id"] == record["artifact_id"]


def test_eval_factory_never_overwrites_source_eval_set():
    """The factory must never name a candidate case identical to a search case."""
    failures = (_make_failure(artifact_id_seed="a", failure_class="regression"),)
    record = build_eval_factory_record(
        EvalFactoryInputs(
            source_eval_set_id="hop_transcript_to_faq_v1",
            source_eval_set_version="1.0.0",
            failures=failures,
            near_miss_scores=(),
        )
    )
    # The candidate_case ids are namespaced by category prefix and hash; they
    # must not collide with the existing search-set ids.
    new_ids = {c["eval_case_id"] for c in record["candidate_cases"]}
    forbidden = {"hop_case_golden_one_qa", "hop_case_adversarial_empty_transcript"}
    assert not (new_ids & forbidden)


def test_max_cases_per_run_caps_output():
    failures = tuple(
        _make_failure(artifact_id_seed=str(i), failure_class="regression")
        for i in range(50)
    )
    record = build_eval_factory_record(
        EvalFactoryInputs(
            source_eval_set_id="x",
            source_eval_set_version="1.0.0",
            failures=failures,
            near_miss_scores=(),
        ),
        config=EvalFactoryConfig(max_cases_per_run=5),
    )
    assert len(record["candidate_cases"]) <= 5


def test_collect_inputs_from_store_reads_existing(store, eval_set):
    candidate = make_baseline_candidate()
    store.write_artifact(candidate)
    evaluate_candidate(
        candidate_payload=candidate, eval_set=eval_set, store=store
    )
    inputs = collect_inputs_from_store(
        store,
        source_eval_set_id=eval_set.eval_set_id,
        source_eval_set_version=eval_set.eval_set_version,
    )
    assert inputs.source_eval_set_id == eval_set.eval_set_id
    # at least one score artifact
    assert len(inputs.near_miss_scores) >= 1
