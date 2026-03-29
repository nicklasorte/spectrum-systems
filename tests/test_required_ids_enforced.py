from __future__ import annotations

import pytest

from spectrum_systems.contracts import load_example, validate_artifact
from tests.helpers.required_ids import add_required_ids


def test_meeting_minutes_record_missing_trace_id_fails_closed() -> None:
    payload = add_required_ids(load_example("meeting_minutes_record"))
    payload.pop("trace_id", None)

    with pytest.raises(Exception):
        validate_artifact(payload, "meeting_minutes_record")


def test_observability_record_missing_run_and_trace_ids_fail_closed() -> None:
    payload = add_required_ids(load_example("observability_record"))
    payload.pop("run_id", None)
    payload.pop("trace_id", None)

    with pytest.raises(Exception):
        validate_artifact(payload, "observability_record")


def test_required_ids_restore_contract_validity() -> None:
    mmr = load_example("meeting_minutes_record")
    mmr.pop("trace_id", None)
    validate_artifact(add_required_ids(mmr), "meeting_minutes_record")

    observability = load_example("observability_record")
    observability.pop("run_id", None)
    observability.pop("trace_id", None)
    validate_artifact(add_required_ids(observability), "observability_record")
