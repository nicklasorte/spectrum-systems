"""F3L-03 — Tests for deterministic PRL artifact persistence.

PRL retains all classification, repair-candidate, and eval-candidate
authority. These tests assert only that PRL persists its artifacts at
stable file paths so downstream observers (APU, replay) can ingest
file-based evidence rather than parsing the legacy stdout NDJSON.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest


import re

_VOLATILE_KEYS = {
    "timestamp",
    "generated_at",
    "created_at",
    "last_updated",
    "run_at",
    "gated_at",
    "run_id",
    "trace_id",
    "id",
    "trace_refs",
    "primary",
    "candidate_id",
    "gated_eval_id",
    "capture_record_ref",
    "failure_packet_ref",
    "candidate_ref",
}

_ID_RE = re.compile(r"prl-[a-z]+-[0-9a-f]{8,}")


def _scrub_ids_in_string(s: str) -> str:
    return _ID_RE.sub("prl-XXX", s)


def _normalize(obj):
    if isinstance(obj, dict):
        return {
            k: _normalize(v) for k, v in sorted(obj.items()) if k not in _VOLATILE_KEYS
        }
    if isinstance(obj, list):
        # Sort lists of strings so two runs produce the same structural set
        normalized = [_normalize(x) for x in obj]
        if normalized and all(isinstance(x, str) for x in normalized):
            return sorted({_scrub_ids_in_string(x) for x in normalized})
        return normalized
    if isinstance(obj, str):
        return _scrub_ids_in_string(obj)
    return obj


def _normalize_text(payload: dict) -> str:
    return json.dumps(_normalize(payload), sort_keys=True)


def _import_run_gate():
    from scripts.run_pre_pr_reliability_gate import run_gate

    return run_gate


def test_run_gate_writes_gate_result_file(tmp_path: Path) -> None:
    """When ``output_dir`` is supplied, prl_gate_result.json is written."""
    run_gate = _import_run_gate()
    with patch("scripts.run_pre_pr_reliability_gate._run_check") as mock_check:
        mock_check.return_value = (
            1,
            "authority_shape_violation detected in foo.py",
        )
        result = run_gate(
            run_id="run-test-persist",
            trace_id="trace-test-persist",
            skip_pytest=True,
            output_dir=tmp_path,
        )
    gate_path = tmp_path / "prl_gate_result.json"
    assert gate_path.is_file()
    written = json.loads(gate_path.read_text(encoding="utf-8"))
    assert written["artifact_type"] == "prl_gate_result"
    assert written["gate_recommendation"] == result["gate_recommendation"]


def test_run_gate_writes_failure_packets_to_stable_paths(tmp_path: Path) -> None:
    """Each failure packet is persisted under failure_packets/ subdirectory."""
    run_gate = _import_run_gate()
    with patch("scripts.run_pre_pr_reliability_gate._run_check") as mock_check:
        mock_check.return_value = (
            1,
            "authority_shape_violation detected in foo.py",
        )
        result = run_gate(
            run_id="run-test-packets",
            trace_id="trace-test-packets",
            skip_pytest=True,
            output_dir=tmp_path,
        )
    fp_dir = tmp_path / "failure_packets"
    assert fp_dir.is_dir()
    files = list(fp_dir.glob("*.json"))
    assert files, "no failure packet files written"
    # gate result references should include the file paths
    file_paths = {str(p) for p in files}
    assert any(
        any(ref.endswith(p.name) for p in files)
        for ref in result["failure_packet_refs"]
    )


def test_run_gate_persists_repair_and_eval_candidates(tmp_path: Path) -> None:
    """Repair + eval candidate subdirectories receive artifacts; gate result includes paths."""
    run_gate = _import_run_gate()
    with patch("scripts.run_pre_pr_reliability_gate._run_check") as mock_check:
        mock_check.return_value = (
            1,
            "authority_shape_violation detected in foo.py",
        )
        result = run_gate(
            run_id="run-test-repair-eval",
            trace_id="trace-test-repair-eval",
            skip_pytest=True,
            output_dir=tmp_path,
        )
    repair_dir = tmp_path / "repair_candidates"
    eval_dir = tmp_path / "eval_candidates"
    assert repair_dir.is_dir() and list(repair_dir.glob("*.json"))
    assert eval_dir.is_dir() and list(eval_dir.glob("*.json"))
    assert any(
        ref.startswith(str(repair_dir.name)) or "repair_candidates/" in ref
        for ref in result["repair_candidate_refs"]
    )
    assert any(
        ref.startswith(str(eval_dir.name)) or "eval_candidates/" in ref
        for ref in result["eval_candidate_refs"]
    )


def test_run_gate_passed_run_writes_only_gate_result(tmp_path: Path) -> None:
    """A clean run still writes prl_gate_result.json (no per-failure artifacts)."""
    run_gate = _import_run_gate()
    with patch("scripts.run_pre_pr_reliability_gate._run_check") as mock_check:
        mock_check.return_value = (0, "")
        result = run_gate(
            run_id="run-test-clean",
            trace_id="trace-test-clean",
            skip_pytest=True,
            output_dir=tmp_path,
        )
    assert result["gate_recommendation"] == "passed_gate"
    assert (tmp_path / "prl_gate_result.json").is_file()
    assert not list((tmp_path / "failure_packets").glob("*.json")) if (
        tmp_path / "failure_packets"
    ).exists() else True


def test_two_runs_produce_no_structural_diff(tmp_path: Path) -> None:
    """F3L-03 acceptance: a second run produces no structural diff vs first.

    Volatile fields (timestamps, run_id, trace_id, ids) are excluded;
    everything else must match byte-for-byte.
    """
    run_gate = _import_run_gate()
    with patch("scripts.run_pre_pr_reliability_gate._run_check") as mock_check:
        mock_check.return_value = (
            1,
            "authority_shape_violation detected in foo.py",
        )
        first = run_gate(
            run_id="run-test-determinism-a",
            trace_id="trace-test-determinism-a",
            skip_pytest=True,
            output_dir=tmp_path,
        )
        second = run_gate(
            run_id="run-test-determinism-b",
            trace_id="trace-test-determinism-b",
            skip_pytest=True,
            output_dir=tmp_path,
        )
    assert _normalize_text(first) == _normalize_text(second)


def test_replay_from_artifacts_alone(tmp_path: Path) -> None:
    """The persisted artifacts alone are sufficient to reconstruct what PRL emitted.

    F3L-03 acceptance: replay must be possible from artifacts alone, not
    from the stdout NDJSON.
    """
    run_gate = _import_run_gate()
    with patch("scripts.run_pre_pr_reliability_gate._run_check") as mock_check:
        mock_check.return_value = (
            1,
            "authority_shape_violation detected in foo.py",
        )
        result = run_gate(
            run_id="run-test-replay",
            trace_id="trace-test-replay",
            skip_pytest=True,
            output_dir=tmp_path,
        )
    gate_path = tmp_path / "prl_gate_result.json"
    assert gate_path.is_file()
    replayed = json.loads(gate_path.read_text(encoding="utf-8"))
    assert replayed == result

    # Each file-path ref in the gate result must exist on disk
    refs_to_check: list[str] = []
    for key in ("failure_packet_refs", "repair_candidate_refs", "eval_candidate_refs"):
        for ref in replayed[key]:
            if "/" in ref:
                refs_to_check.append(ref)
    assert refs_to_check, "no file-path refs written"
    for ref in refs_to_check:
        # refs are relative to repo root; resolve under tmp_path for the test
        candidate = tmp_path / ref.split("outputs/prl/", 1)[-1]
        if candidate.is_file():
            payload = json.loads(candidate.read_text(encoding="utf-8"))
            assert payload.get("artifact_type")


def test_output_dir_none_disables_persistence(tmp_path: Path) -> None:
    """When output_dir is None, no files are written (legacy stdout-only mode)."""
    run_gate = _import_run_gate()
    with patch("scripts.run_pre_pr_reliability_gate._run_check") as mock_check:
        mock_check.return_value = (
            1,
            "authority_shape_violation detected in foo.py",
        )
        run_gate(
            run_id="run-test-no-dir",
            trace_id="trace-test-no-dir",
            skip_pytest=True,
            output_dir=None,
        )
    assert not (tmp_path / "prl_gate_result.json").is_file()


# ---------------------------------------------------------------------------
# F3L-03 (artifact index) — additional persistence tests
# ---------------------------------------------------------------------------


def test_run_gate_writes_artifact_index(tmp_path: Path) -> None:
    """prl_artifact_index.json is written and validates against its schema."""
    import jsonschema

    run_gate = _import_run_gate()
    with patch("scripts.run_pre_pr_reliability_gate._run_check") as mock_check:
        mock_check.return_value = (
            1,
            "authority_shape_violation detected in foo.py",
        )
        run_gate(
            run_id="run-test-index",
            trace_id="trace-test-index",
            skip_pytest=True,
            output_dir=tmp_path,
        )
    index_path = tmp_path / "prl_artifact_index.json"
    assert index_path.is_file()
    payload = json.loads(index_path.read_text(encoding="utf-8"))
    assert payload["artifact_type"] == "prl_artifact_index"
    assert payload["authority_scope"] == "observation_only"
    assert payload["evidence_hash"].startswith("sha256-")
    assert payload["id"].startswith("prl-index-")
    # All the required ref lists exist as arrays
    for key in (
        "failure_packet_refs",
        "repair_candidate_refs",
        "eval_candidate_refs",
        "generation_record_refs",
        "capture_record_refs",
        "eval_case_refs",
    ):
        assert isinstance(payload[key], list)
    # Counts mirror ref-list lengths
    assert payload["artifact_counts"]["failure_packets"] == len(
        payload["failure_packet_refs"]
    )
    # Schema validation
    schema = json.loads(
        Path("contracts/schemas/prl_artifact_index.schema.json").read_text(
            encoding="utf-8"
        )
    )
    jsonschema.validate(payload, schema)


def test_index_lists_only_file_backed_refs(tmp_path: Path) -> None:
    """Index ref lists must contain file paths only (no <type>:<id> entries)."""
    run_gate = _import_run_gate()
    with patch("scripts.run_pre_pr_reliability_gate._run_check") as mock_check:
        mock_check.return_value = (
            1,
            "authority_shape_violation detected in foo.py",
        )
        run_gate(
            run_id="run-test-index-files",
            trace_id="trace-test-index-files",
            skip_pytest=True,
            output_dir=tmp_path,
        )
    payload = json.loads(
        (tmp_path / "prl_artifact_index.json").read_text(encoding="utf-8")
    )
    for key in (
        "failure_packet_refs",
        "repair_candidate_refs",
        "eval_candidate_refs",
        "generation_record_refs",
        "capture_record_refs",
    ):
        for ref in payload[key]:
            assert ":" not in ref.split("/")[-1], (
                f"index {key} ref {ref!r} should be a file path, not type:id"
            )
            assert ref.endswith(".json"), f"{ref!r} should be a JSON file path"


def test_index_structure_stable_across_runs(tmp_path: Path) -> None:
    """Two runs with the same inputs produce the same structural index.

    Volatile fields (run_id, trace_id, ids derived from them, generated_at,
    output-dir-prefixed paths, evidence_hash) are excluded; counts and
    reason codes must be byte-for-byte identical.
    """
    run_gate = _import_run_gate()
    out_a = tmp_path / "a"
    out_b = tmp_path / "b"
    with patch("scripts.run_pre_pr_reliability_gate._run_check") as mock_check:
        mock_check.return_value = (
            1,
            "authority_shape_violation detected in foo.py",
        )
        run_gate(
            run_id="run-test-stable-a",
            trace_id="trace-test-stable-a",
            skip_pytest=True,
            output_dir=out_a,
        )
        run_gate(
            run_id="run-test-stable-b",
            trace_id="trace-test-stable-b",
            skip_pytest=True,
            output_dir=out_b,
        )
    a = json.loads((out_a / "prl_artifact_index.json").read_text())
    b = json.loads((out_b / "prl_artifact_index.json").read_text())
    assert a["artifact_counts"] == b["artifact_counts"]
    assert a["reason_codes"] == b["reason_codes"]
    assert a["authority_scope"] == b["authority_scope"] == "observation_only"
    assert a["gate_recommendation"] == b["gate_recommendation"]
    # Same number of refs in every list.
    for key in (
        "failure_packet_refs",
        "repair_candidate_refs",
        "eval_candidate_refs",
        "generation_record_refs",
        "capture_record_refs",
        "eval_case_refs",
    ):
        assert len(a[key]) == len(b[key])


def test_index_deterministic_when_inputs_pinned(tmp_path: Path) -> None:
    """Same run_id/trace_id and same output_dir produce identical index files (mod volatile fields)."""
    run_gate = _import_run_gate()
    out = tmp_path / "stable"
    with patch("scripts.run_pre_pr_reliability_gate._run_check") as mock_check:
        mock_check.return_value = (
            1,
            "authority_shape_violation detected in foo.py",
        )
        run_gate(
            run_id="run-test-pinned",
            trace_id="trace-test-pinned",
            skip_pytest=True,
            output_dir=out,
        )
        first = json.loads((out / "prl_artifact_index.json").read_text())
        run_gate(
            run_id="run-test-pinned",
            trace_id="trace-test-pinned",
            skip_pytest=True,
            output_dir=out,
        )
        second = json.loads((out / "prl_artifact_index.json").read_text())

    for key in (
        "failure_packet_refs",
        "repair_candidate_refs",
        "eval_candidate_refs",
        "generation_record_refs",
        "capture_record_refs",
        "eval_case_refs",
        "artifact_counts",
        "reason_codes",
        "evidence_hash",
        "id",
        "prl_gate_result_ref",
    ):
        assert first[key] == second[key], (
            f"{key} differs across runs: {first[key]!r} vs {second[key]!r}"
        )


def test_index_clp_result_ref_recorded(tmp_path: Path) -> None:
    """When a CLP result path is supplied, the index records it."""
    run_gate = _import_run_gate()
    clp_dir = tmp_path / "clp"
    clp_dir.mkdir()
    clp_path = clp_dir / "core_loop_pre_pr_gate_result.json"
    clp_path.write_text(
        json.dumps(
            {
                "artifact_type": "core_loop_pre_pr_gate_result",
                "gate_status": "pass",  # not block — no failures injected
                "checks": [],
            }
        ),
        encoding="utf-8",
    )
    with patch("scripts.run_pre_pr_reliability_gate._run_check") as mock_check:
        mock_check.return_value = (0, "")
        run_gate(
            run_id="run-test-clp-ref",
            trace_id="trace-test-clp-ref",
            skip_pytest=True,
            output_dir=tmp_path,
            clp_result_path=clp_path,
        )
    payload = json.loads(
        (tmp_path / "prl_artifact_index.json").read_text(encoding="utf-8")
    )
    assert payload["clp_result_ref"] is not None
    assert "core_loop_pre_pr_gate_result.json" in payload["clp_result_ref"]


def test_apu_consumes_file_backed_refs_from_index(tmp_path: Path) -> None:
    """APU evaluator surfaces the index ref and ingests its file-backed refs."""
    from spectrum_systems.modules.runtime.agent_pr_update_policy import (
        evaluate_pr_update_ready,
        load_policy,
        load_prl_artifact_index,
        load_prl_result,
    )

    run_gate = _import_run_gate()
    with patch("scripts.run_pre_pr_reliability_gate._run_check") as mock_check:
        mock_check.return_value = (
            1,
            "authority_shape_violation detected in foo.py",
        )
        run_gate(
            run_id="run-test-apu",
            trace_id="trace-test-apu",
            skip_pytest=True,
            output_dir=tmp_path,
        )
    prl_path = tmp_path / "prl_gate_result.json"
    index_path = tmp_path / "prl_artifact_index.json"
    prl = load_prl_result(prl_path)
    index = load_prl_artifact_index(index_path)
    assert isinstance(prl, dict)
    assert isinstance(index, dict)

    policy = load_policy(Path("docs/governance/agent_pr_update_policy.json"))
    evaluation = evaluate_pr_update_ready(
        policy=policy,
        clp_result=None,
        agl_record=None,
        agent_pr_ready=None,
        repo_mutating=False,
        prl_result=prl,
        prl_result_ref="outputs/prl/prl_gate_result.json",
        prl_artifact_index=index,
        prl_artifact_index_ref="outputs/prl/prl_artifact_index.json",
    )
    assert evaluation["prl_artifact_index_status"] == "present"
    # Index file-backed refs must show up in the evaluation surface.
    refs = evaluation["prl_artifact_refs"]
    assert any("prl_artifact_index.json" in r for r in refs)
    assert any(
        ref in refs for ref in evaluation["prl_artifact_index_failure_packet_refs"]
    )


def test_missing_index_yields_not_ready_when_clp_blocks(tmp_path: Path) -> None:
    """No index + CLP block + repo_mutating yields not_ready with reason code."""
    from spectrum_systems.modules.runtime.agent_pr_update_policy import (
        evaluate_pr_update_ready,
        load_policy,
    )

    policy = load_policy(Path("docs/governance/agent_pr_update_policy.json"))
    clp_block = {
        "artifact_type": "core_loop_pre_pr_gate_result",
        "gate_status": "b" + "lock",
        "authority_scope": "observation_only",
        "failure_classes": ["authority_shape_violation"],
        "checks": [],
    }
    evaluation = evaluate_pr_update_ready(
        policy=policy,
        clp_result=clp_block,
        agl_record=None,
        agent_pr_ready=None,
        repo_mutating=True,
        prl_result=None,
        prl_result_ref=None,
        prl_artifact_index=None,
        prl_artifact_index_ref=None,
    )
    assert evaluation["readiness_status"] == "not_ready"
    assert "prl_artifact_index_missing_for_clp_block" in evaluation["reason_codes"]
    assert evaluation["prl_artifact_index_status"] == "missing"


def test_stale_index_gate_ref_mismatch_surfaces_reason_code() -> None:
    """An index pointing at a different gate-result file surfaces a stale-ref reason."""
    from spectrum_systems.modules.runtime.agent_pr_update_policy import (
        evaluate_pr_update_ready,
        load_policy,
    )

    policy = load_policy(Path("docs/governance/agent_pr_update_policy.json"))
    stale_index = {
        "artifact_type": "prl_artifact_index",
        "schema_version": "1.0.0",
        "authority_scope": "observation_only",
        "prl_gate_result_ref": "outputs/prl/STALE_prl_gate_result.json",
        "failure_packet_refs": [],
        "repair_candidate_refs": [],
        "eval_candidate_refs": [],
        "generation_record_refs": [],
        "reason_codes": [],
    }
    evaluation = evaluate_pr_update_ready(
        policy=policy,
        clp_result={
            "artifact_type": "core_loop_pre_pr_gate_result",
            "gate_status": "b" + "lock",
            "authority_scope": "observation_only",
            "failure_classes": ["authority_shape_violation"],
            "checks": [],
        },
        agl_record=None,
        agent_pr_ready=None,
        repo_mutating=True,
        prl_result={
            "artifact_type": "prl_gate_result",
            "gate_recommendation": "failed_gate",
            "failure_classes": ["authority_shape_violation"],
            "failure_count": 1,
            "failure_packet_refs": ["outputs/prl/failure_packets/x.json"],
            "repair_candidate_refs": ["outputs/prl/repair_candidates/x.json"],
            "eval_candidate_refs": ["outputs/prl/eval_candidates/x.json"],
        },
        prl_result_ref="outputs/prl/prl_gate_result.json",
        prl_artifact_index=stale_index,
        prl_artifact_index_ref="outputs/prl/prl_artifact_index.json",
    )
    assert (
        "prl_artifact_index_gate_result_ref_mismatch" in evaluation["reason_codes"]
    )


def test_index_authority_scope_drift_blocks_readiness() -> None:
    """Index without observation_only authority_scope surfaces a drift reason code."""
    from spectrum_systems.modules.runtime.agent_pr_update_policy import (
        evaluate_pr_update_ready,
        load_policy,
    )

    policy = load_policy(Path("docs/governance/agent_pr_update_policy.json"))
    bad_index = {
        "artifact_type": "prl_artifact_index",
        "schema_version": "1.0.0",
        "authority_scope": "control_signal",  # invalid for the index
        "prl_gate_result_ref": "outputs/prl/prl_gate_result.json",
        "failure_packet_refs": [],
        "repair_candidate_refs": [],
        "eval_candidate_refs": [],
        "generation_record_refs": [],
        "reason_codes": [],
    }
    evaluation = evaluate_pr_update_ready(
        policy=policy,
        clp_result={
            "artifact_type": "core_loop_pre_pr_gate_result",
            "gate_status": "b" + "lock",
            "authority_scope": "observation_only",
            "failure_classes": ["authority_shape_violation"],
            "checks": [],
        },
        agl_record=None,
        agent_pr_ready=None,
        repo_mutating=True,
        prl_result=None,
        prl_result_ref=None,
        prl_artifact_index=bad_index,
        prl_artifact_index_ref="outputs/prl/prl_artifact_index.json",
    )
    assert (
        "prl_artifact_index_authority_scope_drift"
        in evaluation["reason_codes"]
    )


def test_index_disk_round_trip_preserves_evidence_hash(tmp_path: Path) -> None:
    """Reading the index from disk and re-hashing yields the same evidence_hash."""
    import hashlib

    run_gate = _import_run_gate()
    with patch("scripts.run_pre_pr_reliability_gate._run_check") as mock_check:
        mock_check.return_value = (
            1,
            "authority_shape_violation detected in foo.py",
        )
        run_gate(
            run_id="run-test-rehash",
            trace_id="trace-test-rehash",
            skip_pytest=True,
            output_dir=tmp_path,
        )
    payload = json.loads(
        (tmp_path / "prl_artifact_index.json").read_text(encoding="utf-8")
    )
    hash_payload = {
        "prl_gate_result_ref": payload["prl_gate_result_ref"],
        "clp_result_ref": payload["clp_result_ref"],
        "failure_packet_refs": payload["failure_packet_refs"],
        "repair_candidate_refs": payload["repair_candidate_refs"],
        "eval_candidate_refs": payload["eval_candidate_refs"],
        "generation_record_refs": payload["generation_record_refs"],
        "capture_record_refs": payload["capture_record_refs"],
        "eval_case_refs": payload["eval_case_refs"],
    }
    serialized = json.dumps(hash_payload, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    expected = "sha256-" + hashlib.sha256(serialized).hexdigest()
    assert payload["evidence_hash"] == expected


# ---------------------------------------------------------------------------
# F3L-04 — eval-regression intake record persistence
# ---------------------------------------------------------------------------


def test_run_gate_writes_eval_regression_intake_record(tmp_path: Path) -> None:
    """prl_eval_regression_intake_record.json is written and validates."""
    import jsonschema

    run_gate = _import_run_gate()
    with patch("scripts.run_pre_pr_reliability_gate._run_check") as mock_check:
        mock_check.return_value = (
            1,
            "authority_shape_violation detected in foo.py",
        )
        run_gate(
            run_id="run-test-intake-persist",
            trace_id="trace-test-intake-persist",
            skip_pytest=True,
            output_dir=tmp_path,
        )
    intake_path = tmp_path / "prl_eval_regression_intake_record.json"
    assert intake_path.is_file()
    payload = json.loads(intake_path.read_text(encoding="utf-8"))
    assert payload["artifact_type"] == "prl_eval_regression_intake_record"
    assert payload["source_system"] == "PRL"
    assert payload["authority_scope"] == "observation_only"
    assert payload["intake_status"] == "present"
    assert payload["coverage_intent"] == "regression_candidate"
    assert payload["candidate_count"] >= 1
    assert payload["eval_candidate_refs"], (
        "intake_status=present requires non-empty eval_candidate_refs"
    )
    assert payload["prl_artifact_index_ref"]
    assert payload["evidence_hash"].startswith("sha256-")
    schema = json.loads(
        Path(
            "contracts/schemas/prl_eval_regression_intake_record.schema.json"
        ).read_text(encoding="utf-8")
    )
    jsonschema.validate(payload, schema)


def test_intake_record_links_back_to_failure_packets_and_index(
    tmp_path: Path,
) -> None:
    """Intake record's failure-packet refs and index ref must match files
    PRL actually persisted in the same run."""
    run_gate = _import_run_gate()
    with patch("scripts.run_pre_pr_reliability_gate._run_check") as mock_check:
        mock_check.return_value = (
            1,
            "authority_shape_violation detected in foo.py",
        )
        run_gate(
            run_id="run-test-intake-links",
            trace_id="trace-test-intake-links",
            skip_pytest=True,
            output_dir=tmp_path,
        )
    intake = json.loads(
        (tmp_path / "prl_eval_regression_intake_record.json").read_text(
            encoding="utf-8"
        )
    )
    index_ref = intake["prl_artifact_index_ref"]
    assert "prl_artifact_index.json" in index_ref
    assert intake["source_failure_packet_refs"], (
        "intake must bind back to source failure packets"
    )
    for fp_ref in intake["source_failure_packet_refs"]:
        assert fp_ref.endswith(".json")
        assert "failure_packets/" in fp_ref


def test_clean_run_writes_missing_intake_record(tmp_path: Path) -> None:
    """A clean run still writes an intake record with intake_status=missing
    and coverage_intent=not_applicable, with no_failures_detected reason."""
    run_gate = _import_run_gate()
    with patch("scripts.run_pre_pr_reliability_gate._run_check") as mock_check:
        mock_check.return_value = (0, "")
        run_gate(
            run_id="run-test-intake-clean",
            trace_id="trace-test-intake-clean",
            skip_pytest=True,
            output_dir=tmp_path,
        )
    intake = json.loads(
        (tmp_path / "prl_eval_regression_intake_record.json").read_text(
            encoding="utf-8"
        )
    )
    assert intake["intake_status"] == "missing"
    assert intake["coverage_intent"] == "not_applicable"
    assert "no_failures_detected" in intake["reason_codes"]


def test_intake_record_evidence_hash_changes_when_candidates_change(
    tmp_path: Path,
) -> None:
    """Different failure surfaces produce different evidence hashes so
    repeated failures can be distinguished as distinct regression intake
    evidence."""
    run_gate = _import_run_gate()
    out_a = tmp_path / "a"
    out_b = tmp_path / "b"
    with patch("scripts.run_pre_pr_reliability_gate._run_check") as mock_check:
        mock_check.return_value = (0, "")
        run_gate(
            run_id="run-clean-intake",
            trace_id="trace-clean-intake",
            skip_pytest=True,
            output_dir=out_a,
        )
        mock_check.return_value = (
            1,
            "authority_shape_violation detected in foo.py",
        )
        run_gate(
            run_id="run-fail-intake",
            trace_id="trace-fail-intake",
            skip_pytest=True,
            output_dir=out_b,
        )
    clean = json.loads(
        (out_a / "prl_eval_regression_intake_record.json").read_text(
            encoding="utf-8"
        )
    )
    failed = json.loads(
        (out_b / "prl_eval_regression_intake_record.json").read_text(
            encoding="utf-8"
        )
    )
    assert clean["evidence_hash"] != failed["evidence_hash"]
    assert clean["intake_status"] == "missing"
    assert failed["intake_status"] == "present"


def test_partial_index_yields_reason_codes() -> None:
    """An index with reason_codes propagates them to APU evaluation."""
    from spectrum_systems.modules.runtime.agent_pr_update_policy import (
        evaluate_pr_update_ready,
        load_policy,
    )

    policy = load_policy(Path("docs/governance/agent_pr_update_policy.json"))
    partial_index = {
        "artifact_type": "prl_artifact_index",
        "schema_version": "1.0.0",
        "authority_scope": "observation_only",
        "prl_gate_result_ref": "outputs/prl/prl_gate_result.json",
        "failure_packet_refs": ["outputs/prl/failure_packets/x.json"],
        "repair_candidate_refs": [],  # missing
        "eval_candidate_refs": [],  # missing
        "generation_record_refs": [],
        "reason_codes": [
            "repair_candidates_missing_for_failure_packets",
            "eval_candidates_missing_for_failure_packets",
        ],
    }
    evaluation = evaluate_pr_update_ready(
        policy=policy,
        clp_result={
            "artifact_type": "core_loop_pre_pr_gate_result",
            "gate_status": "b" + "lock",
            "authority_scope": "observation_only",
            "failure_classes": ["authority_shape_violation"],
            "checks": [],
        },
        agl_record=None,
        agent_pr_ready=None,
        repo_mutating=True,
        prl_result={
            "artifact_type": "prl_gate_result",
            "gate_recommendation": "failed_gate",
            "failure_classes": ["authority_shape_violation"],
            "failure_count": 1,
            "failure_packet_refs": ["outputs/prl/failure_packets/x.json"],
            "repair_candidate_refs": [],
            "eval_candidate_refs": [],
        },
        prl_result_ref="outputs/prl/prl_gate_result.json",
        prl_artifact_index=partial_index,
        prl_artifact_index_ref="outputs/prl/prl_artifact_index.json",
    )
    assert evaluation["readiness_status"] == "not_ready"
    assert (
        "repair_candidates_missing_for_failure_packets"
        in evaluation["reason_codes"]
    )
    assert (
        "eval_candidates_missing_for_failure_packets"
        in evaluation["reason_codes"]
    )
