from __future__ import annotations

import json
from pathlib import Path

from spectrum_systems.fix_engine.generate_fix_roadmap import generate_fix_roadmap


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "autonomous_cycle"


def test_fix_roadmap_merges_dedupes_and_groups_deterministically(tmp_path: Path) -> None:
    out_json = tmp_path / "fix_roadmap.json"
    out_md = tmp_path / "fix_roadmap.md"

    artifact = generate_fix_roadmap(
        cycle_id="cycle-test",
        review_artifact_paths=[
            str(FIXTURES / "implementation_review_codex.json"),
            str(FIXTURES / "implementation_review_claude.json"),
        ],
        output_json_path=str(out_json),
        output_markdown_path=str(out_md),
        generated_at="2026-03-30T01:00:00Z",
    )

    assert artifact["summary"]["total_unique_findings"] == 3
    assert artifact["summary"]["blocker"] == 1
    assert artifact["summary"]["required_fix"] == 1
    assert artifact["summary"]["optional_improvement"] == 1

    first_bundle = artifact["bundles"][0]
    assert first_bundle["classification"] == "blocker"
    assert "spectrum_systems/orchestration" in first_bundle["target_seams"]

    roundtrip = json.loads(out_json.read_text(encoding="utf-8"))
    assert roundtrip == artifact
    assert "# Fix Roadmap" in out_md.read_text(encoding="utf-8")
