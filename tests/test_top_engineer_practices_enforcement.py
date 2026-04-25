from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts/check_top_engineer_practices.py"
MAPPING_PATH = REPO_ROOT / "contracts/examples/top_engineer_practice_mapping_record.example.json"

sys.path.insert(0, str(REPO_ROOT / "scripts"))
from check_top_engineer_practices import check_mapping  # noqa: E402


def _load_mapping() -> dict:
    return json.loads(MAPPING_PATH.read_text(encoding="utf-8"))


def _required_ids() -> list[str]:
    text = (REPO_ROOT / "docs/architecture/system_registry.md").read_text(encoding="utf-8")
    import re

    body = re.search(
        r"## Active executable systems\n(?P<body>.*?)(\n## Merged or demoted systems)",
        text,
        re.S,
    ).group("body")
    return re.findall(r"^### ([A-Z0-9]{3})$", body, re.M)


def test_checker_fails_on_missing_failure_prevented() -> None:
    mapping = _load_mapping()
    mapping["systems"][0]["failure_prevented"] = ""
    errors = check_mapping(mapping, _required_ids())
    assert any("missing failure_prevented" in e for e in errors)


def test_checker_fails_on_missing_rollback_path() -> None:
    mapping = _load_mapping()
    mapping["systems"][0]["rollback_path"] = {}
    errors = check_mapping(mapping, _required_ids())
    assert any("missing rollback_path" in e for e in errors)


def test_checker_fails_when_unknown_state_policy_absent() -> None:
    mapping = _load_mapping()
    mapping["systems"][0]["unknown_state_policy"] = {}
    errors = check_mapping(mapping, _required_ids())
    assert any("unknown_state_policy" in e for e in errors)


def test_checker_fails_when_promotion_requirements_omit_eval_policy_replay() -> None:
    mapping = _load_mapping()
    mapping["systems"][0]["promotion_requirements"] = {
        "eval_required": True,
        "policy_required": False,
        "replay_required": False,
    }
    errors = check_mapping(mapping, _required_ids())
    assert any("policy validation" in e for e in errors)
    assert any("replay validation" in e for e in errors)


@pytest.mark.parametrize(
    "schema_name,example_name",
    [
        ("near_miss_record", "near_miss_record.example"),
        ("chaos_campaign_record", "chaos_campaign_record.example"),
        ("bad_input_campaign_record", "bad_input_campaign_record.example"),
        ("failure_mode_dashboard_record", "failure_mode_dashboard_record.example"),
    ],
)
def test_examples_validate_against_schemas(schema_name: str, example_name: str) -> None:
    schema = json.loads((REPO_ROOT / "contracts/schemas" / f"{schema_name}.schema.json").read_text(encoding="utf-8"))
    example = json.loads((REPO_ROOT / "contracts/examples" / f"{example_name}.json").read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(example)


def test_checker_script_runs_clean() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
