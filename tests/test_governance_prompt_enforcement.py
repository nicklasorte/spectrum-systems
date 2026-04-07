from __future__ import annotations

from pathlib import Path

from scripts.check_governance_compliance import (
    evaluate_prompt_file,
    evaluate_prompt_text,
    load_governed_prompt_surface_registry,
)

VALID_PROMPT = """
# Prompt
Load docs/governance/strategy_control_doc.md
Load docs/governance/source_inputs_manifest.json
Load docs/governance/prompt_includes/source_input_loading_include.md
Load docs/governance/prompt_includes/roadmap_governance_include.md
"""


def test_valid_prompt_passes() -> None:
    result = evaluate_prompt_text(VALID_PROMPT)
    assert result.passed
    assert result.missing_items == []


def test_missing_strategy_doc_fails() -> None:
    prompt = VALID_PROMPT.replace("docs/governance/strategy_control_doc.md\n", "")
    result = evaluate_prompt_text(prompt)
    assert not result.passed
    assert any("strategy_control_doc.md" in item for item in result.missing_items)


def test_missing_source_inputs_manifest_fails() -> None:
    prompt = VALID_PROMPT.replace("docs/governance/source_inputs_manifest.json\n", "")
    result = evaluate_prompt_text(prompt)
    assert not result.passed
    assert any("source_inputs_manifest.json" in item for item in result.missing_items)


def test_missing_governance_include_fails() -> None:
    prompt = VALID_PROMPT.replace(
        "docs/governance/prompt_includes/roadmap_governance_include.md\n", ""
    )
    result = evaluate_prompt_text(prompt)
    assert not result.passed
    assert any("missing governance include/template reference" in item for item in result.missing_items)


def test_governed_file_is_classified_and_checked() -> None:
    surfaces = load_governed_prompt_surface_registry()
    result = evaluate_prompt_file(Path("docs/governance/prompt_templates/roadmap_prompt_template.md"), surfaces)
    assert result.governed is True
    assert result.surface_id == "roadmap_prompt_template"
    assert result.passed is True


def test_non_governed_file_is_ignored_cleanly() -> None:
    surfaces = load_governed_prompt_surface_registry()
    result = evaluate_prompt_file(Path("docs/governance/README.md"), surfaces)
    assert result.governed is False
    assert result.passed is True
