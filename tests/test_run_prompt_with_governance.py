from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "run_prompt_with_governance.py"


VALID_PROMPT = """
Load docs/governance/strategy_control_doc.md
Load docs/governance/source_inputs_manifest.json
Load docs/governance/prompt_includes/source_input_loading_include.md
Load docs/governance/prompt_includes/implementation_governance_include.md
""".strip()

INVALID_PROMPT = """
# missing governance references on purpose
""".strip()


def test_run_prompt_with_governance_passes_for_valid_prompt(tmp_path: Path) -> None:
    prompt_file = tmp_path / "valid_prompt.md"
    prompt_file.write_text(VALID_PROMPT + "\n", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), str(prompt_file)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "PASS: governance compliance checks satisfied." in result.stdout
    assert "PRECHECK PASSED: prompt ready for execution." in result.stdout


def test_run_prompt_with_governance_blocks_invalid_prompt(tmp_path: Path) -> None:
    prompt_file = tmp_path / "invalid_prompt.md"
    prompt_file.write_text(INVALID_PROMPT + "\n", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), str(prompt_file)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "FAIL: governance compliance checks failed." in result.stdout
    assert "BLOCKED: governance preflight failed; prompt execution stopped." in result.stdout
