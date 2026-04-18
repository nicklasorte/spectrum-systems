from __future__ import annotations

import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_json(path: str) -> dict:
    return json.loads((REPO_ROOT / path).read_text(encoding="utf-8"))


def test_new_semantic_eval_example_has_no_authority_fields_or_values() -> None:
    payload = _load_json("contracts/examples/semantic_eval_result.json")
    text = json.dumps(payload, sort_keys=True).lower()
    assert '"decision"' not in text
    assert '"allow"' not in text
    assert '"block"' not in text
    assert '"freeze"' not in text


def test_eval_coverage_runtime_module_emits_evidence_only_fields() -> None:
    module_text = (REPO_ROOT / "spectrum_systems/modules/wpg/eval_coverage.py").read_text(encoding="utf-8").lower()
    assert '"decision"' not in module_text
    assert '"allow"' not in module_text
    assert '"block"' not in module_text
    assert '"freeze"' not in module_text


def test_semantic_runtime_module_emits_evidence_only_fields() -> None:
    module_text = (REPO_ROOT / "spectrum_systems/modules/runtime/semantic_eval.py").read_text(encoding="utf-8").lower()
    assert '"decision"' not in module_text
    assert '"allow"' not in module_text
    assert '"block"' not in module_text
    assert '"freeze"' not in module_text
