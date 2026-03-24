from __future__ import annotations

from spectrum_systems.utils.deterministic_id import canonical_json, deterministic_id


def test_canonical_json_is_stable_across_key_order() -> None:
    one = canonical_json({"b": 2, "a": 1, "nested": {"z": 9, "x": 7}})
    two = canonical_json({"nested": {"x": 7, "z": 9}, "a": 1, "b": 2})
    assert one == two


def test_deterministic_id_is_stable_for_same_payload() -> None:
    payload = {"artifact_type": "evaluation_release_record", "candidate_version": "v2", "baseline_version": "v1"}
    first = deterministic_id(prefix="release", namespace="release_canary", payload=payload)
    second = deterministic_id(prefix="release", namespace="release_canary", payload=payload)
    assert first == second


def test_deterministic_id_changes_when_payload_changes() -> None:
    base = deterministic_id(prefix="gate", namespace="evaluation_ci_gate_result", payload={"status": "pass"})
    changed = deterministic_id(prefix="gate", namespace="evaluation_ci_gate_result", payload={"status": "blocked"})
    assert base != changed
