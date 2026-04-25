"""Red-team tests for HOP Phase 2.

Each test below is an attack against a specific advisory-only invariant:

- readiness bypass via fabricated readiness-signal artifact;
- eval gaming via in-memory score artifact never admitted to the store;
- regression leakage via case-id collision with the search set;
- rollback failure via re-promotion of a quarantined candidate;
- control bypass via ``advisory_only=False`` smuggled into the payload;
- eval-data read leakage via the sandbox.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from spectrum_systems.modules.hop.evaluator import evaluate_candidate
from spectrum_systems.modules.hop.promotion_readiness import (
    ReadinessSignalInputs,
    evaluate_release_readiness,
)
from spectrum_systems.modules.hop.rollback_signals import (
    RollbackSignalRequest,
    emit_rollback_signal,
)
from spectrum_systems.modules.hop.sandbox import SandboxConfig, execute_candidate
from spectrum_systems.modules.hop.schemas import HopSchemaError, validate_hop_artifact
from tests.hop.conftest import make_baseline_candidate


@pytest.fixture()
def saturated_pair_persisted(eval_set, heldout_eval_set, store):
    candidate = make_baseline_candidate()
    store.write_artifact(candidate)
    search = evaluate_candidate(
        candidate_payload=candidate, eval_set=eval_set, store=store
    )
    heldout = evaluate_candidate(
        candidate_payload=candidate, eval_set=heldout_eval_set, store=store
    )
    return candidate, search["score"], heldout["score"]


# ---------- Attack 1: readiness bypass via fabricated artifact ----------------

def test_attack_fabricated_ready_artifact_rejected_by_schema():
    """A handcrafted ready_signal with a failed rationale must fail schema."""
    forged = {
        "artifact_type": "hop_harness_release_readiness_signal",
        "schema_ref": "hop/harness_release_readiness_signal.schema.json",
        "schema_version": "1.0.0",
        "trace": {"primary": "attacker", "related": []},
        "signal_id": "fake_signal",
        "candidate_id": "cand_x",
        "search_score_artifact_id": "any",
        "heldout_score_artifact_id": "any",
        "search_score": 0.0,
        "heldout_score": 0.0,
        "search_eval_set_id": "a",
        "heldout_eval_set_id": "b",
        "trace_completeness": 0.0,
        "risk_failure_count": 0,
        "readiness_signal": "ready_signal",
        "rationale": [
            {"check": "search_score_threshold", "passed": False, "detail": "x"},
        ],
        "advisory_only": True,
        "delegates_to": "REL",
        "evaluated_at": "2026-04-25T00:00:00.000000Z",
        "content_hash": "sha256:" + "0" * 64,
        "artifact_id": "hop_rs_signal_fake",
    }
    with pytest.raises(HopSchemaError):
        validate_hop_artifact(forged, "hop_harness_release_readiness_signal")


# ---------- Attack 2: in-memory score never admitted to the store ------------

def test_attack_unadmitted_score_yields_risk_signal(eval_set, heldout_eval_set, store):
    candidate = make_baseline_candidate()
    store.write_artifact(candidate)
    # Compute scores OUTSIDE the store; they are valid schema, but never written.
    search = evaluate_candidate(candidate_payload=candidate, eval_set=eval_set)
    heldout = evaluate_candidate(
        candidate_payload=candidate, eval_set=heldout_eval_set
    )
    signal = evaluate_release_readiness(
        inputs=ReadinessSignalInputs(
            candidate_id=candidate["candidate_id"],
            search_score=search["score"],
            heldout_score=heldout["score"],
        ),
        store=store,
    )
    assert signal["readiness_signal"] == "risk_signal"
    failed = {r["check"] for r in signal["rationale"] if not r["passed"]}
    assert "scores_admitted" in failed


# ---------- Attack 3: case-id collision in eval factory -----------------------

def test_attack_eval_factory_does_not_collide_with_search_set(
    saturated_pair_persisted, store, eval_cases
):
    """Generated case_ids must not collide with existing search-set ids."""
    from spectrum_systems.modules.hop.eval_factory import (
        EvalFactoryInputs,
        build_eval_factory_record,
    )
    from spectrum_systems.modules.hop.artifacts import finalize_artifact, make_trace

    fake_failure = {
        "artifact_type": "hop_harness_failure_hypothesis",
        "schema_ref": "hop/harness_failure_hypothesis.schema.json",
        "schema_version": "1.0.0",
        "trace": make_trace(primary="hop_test", related=["x"]),
        "hypothesis_id": "h_collide",
        "candidate_id": "cand_x",
        "run_id": "run_x",
        "stage": "evaluation",
        "failure_class": "regression",
        "severity": "reject",
        "evidence": [{"kind": "snippet", "detail": "x"}],
        "detected_at": "2026-04-25T00:00:00.000000Z",
        "blocks_promotion": True,
    }
    finalize_artifact(fake_failure, id_prefix="hop_failure_")
    record = build_eval_factory_record(
        EvalFactoryInputs(
            source_eval_set_id="hop_transcript_to_faq_v1",
            source_eval_set_version="1.0.0",
            failures=(fake_failure,),
            near_miss_scores=(),
        )
    )
    existing_ids = {c["eval_case_id"] for c in eval_cases}
    new_ids = {c["eval_case_id"] for c in record["candidate_cases"]}
    assert not (new_ids & existing_ids)


# ---------- Attack 4: re-promotion of a quarantined candidate -----------------

def test_attack_quarantined_candidate_yields_risk_signal(
    saturated_pair_persisted, store
):
    candidate, search_score, heldout_score = saturated_pair_persisted
    emit_rollback_signal(
        RollbackSignalRequest(
            subject_candidate_id=candidate["candidate_id"],
            recommended_action="quarantine",
            reason="blocking_failure_detected",
            evidence=({"kind": "snippet", "detail": "synthetic"},),
        ),
        store=store,
    )
    signal = evaluate_release_readiness(
        inputs=ReadinessSignalInputs(
            candidate_id=candidate["candidate_id"],
            search_score=search_score,
            heldout_score=heldout_score,
        ),
        store=store,
    )
    assert signal["readiness_signal"] == "risk_signal"
    failed = {r["check"] for r in signal["rationale"] if not r["passed"]}
    assert "candidate_not_quarantined" in failed


# ---------- Attack 5: smuggled advisory_only=False ----------------------------

def test_attack_advisory_only_false_rejected_by_schema():
    payload = {
        "artifact_type": "hop_harness_release_readiness_signal",
        "schema_ref": "hop/harness_release_readiness_signal.schema.json",
        "schema_version": "1.0.0",
        "trace": {"primary": "attacker", "related": []},
        "signal_id": "fake",
        "candidate_id": "cand_x",
        "search_score_artifact_id": "a",
        "heldout_score_artifact_id": "b",
        "search_score": 1.0,
        "heldout_score": 1.0,
        "search_eval_set_id": "x",
        "heldout_eval_set_id": "y",
        "trace_completeness": 1.0,
        "risk_failure_count": 0,
        "readiness_signal": "ready_signal",
        "rationale": [
            {"check": "search_score_threshold", "passed": True, "detail": "ok"}
        ],
        "advisory_only": False,
        "delegates_to": "REL",
        "evaluated_at": "2026-04-25T00:00:00.000000Z",
        "content_hash": "sha256:" + "0" * 64,
        "artifact_id": "hop_rs_signal_fake",
    }
    with pytest.raises(HopSchemaError):
        validate_hop_artifact(payload, "hop_harness_release_readiness_signal")


# ---------- Attack 6: eval-data read leakage from sandbox ---------------------

def test_attack_sandbox_blocks_eval_data_reads(tmp_path):
    """A malicious harness that reads contracts/evals/* must be blocked."""
    repo_root = Path(__file__).resolve().parents[2]
    eval_dir = repo_root / "contracts" / "evals"
    target = next(eval_dir.glob("hop/cases/*.json"))
    code = (
        f"def run(t):\n"
        f"    with open({str(target)!r}, 'r') as fh:\n"
        f"        fh.read()\n"
        f"    return {{}}\n"
    )
    candidate = make_baseline_candidate(code_source=code)
    candidate["code_module"] = "attacker_payload"
    candidate["code_entrypoint"] = "run"
    result = execute_candidate(
        candidate_payload=candidate,
        harness_input={"transcript_id": "t", "turns": []},
        config=SandboxConfig(
            denied_read_path_prefixes=(str(eval_dir),),
        ),
    )
    assert result.ok is False
    assert result.violation_type == "sandbox_violation"
    assert "read_denied_eval_data" in (result.detail or "")


def test_sandbox_default_config_unchanged_for_writes(tmp_path):
    """Default config without denied_read_path_prefixes must not break baseline."""
    candidate = make_baseline_candidate()
    result = execute_candidate(
        candidate_payload=candidate,
        harness_input={"transcript_id": "t", "turns": [
            {"speaker": "user", "text": "Why?"},
            {"speaker": "assistant", "text": "Because."},
        ]},
    )
    assert result.ok is True
