from __future__ import annotations

from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parents[1]


def test_workflows_do_not_embed_promotion_business_logic() -> None:
    workflows_dir = _REPO_ROOT / ".github" / "workflows"
    if not workflows_dir.exists():
        return

    forbidden_tokens = (
        "promotion_allowed == true",
        "promotion_allowed: true",
        "terminal_state == 'ready_for_merge'",
        'terminal_state == "ready_for_merge"',
    )
    for workflow in workflows_dir.glob("*.y*ml"):
        content = workflow.read_text(encoding="utf-8").lower()
        for token in forbidden_tokens:
            assert token not in content, f"workflow contains promotion business logic token '{token}': {workflow}"
