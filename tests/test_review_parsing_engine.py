from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

from spectrum_systems.contracts import load_example, load_schema  # noqa: E402
from spectrum_systems.modules.runtime.review_parsing_engine import (  # noqa: E402
    ReviewParsingEngineError,
    parse_review_to_signal,
)


VALID_REVIEW = """---
module: tpa
review_date: 2026-04-05
---
# Review

## Overall Assessment
**Overall Verdict: CONDITIONAL PASS**

## Critical Risks
1. Bypass drift risk remains open.
"""

VALID_ACTIONS = """# Action Tracker

## Critical Items
| ID | Risk | Severity | Recommended Action | Status | Notes |
| --- | --- | --- | --- | --- | --- |
| CR-1 | Blocking risk in tpa control path | Critical | Add blocker-safe enforcement (R1) | Open | blocking |

## High-Priority Items
| ID | Risk | Severity | Recommended Action | Status | Notes |
| --- | --- | --- | --- | --- | --- |
| HI-1 | pqx routing gap | High | Add route guard (R2) | Open | |

## Medium-Priority Items
| ID | Risk | Severity | Recommended Action | Status | Notes |
| --- | --- | --- | --- | --- | --- |
| MI-1 | fre observability lag | Medium | Add telemetry review (R3) | Open | |

## Blocking Items
- CR-1 blocks promotion.
"""


MALFORMED_ACTIONS = """# Action Tracker

## Critical Items
| ID | Risk | Severity | Recommended Action | Status |
| --- | --- | --- | --- | --- |
| CR-1 | Missing severity cell | Add fix | Open |

## High-Priority Items
| ID | Risk | Severity | Recommended Action | Status |
| --- | --- | --- | --- | --- |
| HI-1 | Hi risk | High | Do thing | Open |

## Medium-Priority Items
| ID | Risk | Severity | Recommended Action | Status |
| --- | --- | --- | --- | --- |
| MI-1 | Med risk | Medium | Do thing | Open |
"""


def _write_inputs(tmp_path: Path, review_text: str = VALID_REVIEW, actions_text: str = VALID_ACTIONS) -> tuple[Path, Path]:
    review_path = tmp_path / "review.md"
    actions_path = tmp_path / "actions.md"
    review_path.write_text(review_text, encoding="utf-8")
    actions_path.write_text(actions_text, encoding="utf-8")
    return review_path, actions_path


def test_review_signal_contract_example_validates() -> None:
    example = copy.deepcopy(load_example("review_signal_artifact"))
    validator = Draft202012Validator(load_schema("review_signal_artifact"), format_checker=FormatChecker())
    validator.validate(example)


def test_valid_review_and_action_tracker_extracts_expected_fields(tmp_path: Path) -> None:
    review_path, action_path = _write_inputs(tmp_path)
    artifact = parse_review_to_signal(review_path, action_path)

    validator = Draft202012Validator(load_schema("review_signal_artifact"), format_checker=FormatChecker())
    validator.validate(artifact)

    assert artifact["review_date"] == "2026-04-05"
    assert artifact["system_scope"] == "tpa"
    assert artifact["overall_verdict"] == "conditional_pass"
    assert [item["id"] for item in artifact["critical_risks"]] == ["CR-1"]
    assert artifact["severity_counts"] == {"critical": 1, "high": 1, "medium": 1}


def test_missing_action_tracker_fails_closed(tmp_path: Path) -> None:
    review_path, _ = _write_inputs(tmp_path)
    with pytest.raises(ReviewParsingEngineError, match="action tracker file not found"):
        parse_review_to_signal(review_path, tmp_path / "missing-actions.md")


def test_malformed_table_fails_closed(tmp_path: Path) -> None:
    review_path, action_path = _write_inputs(tmp_path, actions_text=MALFORMED_ACTIONS)
    with pytest.raises(ReviewParsingEngineError, match="malformed markdown table"):
        parse_review_to_signal(review_path, action_path)


def test_blocker_detection_and_ids(tmp_path: Path) -> None:
    review_path, action_path = _write_inputs(tmp_path)
    artifact = parse_review_to_signal(review_path, action_path)

    assert artifact["blocker_flags"] is True
    assert artifact["blocker_ids"] == ["CR-1"]


def test_parser_is_deterministic_for_same_inputs(tmp_path: Path) -> None:
    review_path, action_path = _write_inputs(tmp_path)
    first = parse_review_to_signal(review_path, action_path)
    second = parse_review_to_signal(review_path, action_path)

    assert first == second
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


def test_each_action_item_contains_traceability_fields(tmp_path: Path) -> None:
    review_path, action_path = _write_inputs(tmp_path)
    artifact = parse_review_to_signal(review_path, action_path)

    for item in artifact["action_items"]:
        trace = item["trace"]
        assert trace["source_path"].endswith("actions.md")
        assert trace["line_number"] >= 1
        assert item["id"] in trace["source_excerpt"]


def test_runtime_schema_validation_rejects_parser_output(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    review_path, action_path = _write_inputs(tmp_path)

    original = load_schema("review_signal_artifact")
    hardened = copy.deepcopy(original)
    hardened["required"] = [*hardened["required"], "runtime_validation_probe"]

    def _patched_load_schema(name: str) -> dict:
        if name == "review_signal_artifact":
            return hardened
        return load_schema(name)

    monkeypatch.setattr("spectrum_systems.modules.runtime.review_parsing_engine.load_schema", _patched_load_schema)

    with pytest.raises(ReviewParsingEngineError, match="runtime schema validation failed"):
        parse_review_to_signal(review_path, action_path)
