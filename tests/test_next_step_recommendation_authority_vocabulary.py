from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]

D3L_NEXT_STEP_FILES = [
    "docs/review-actions/PLAN-D3L-NEXT-STEP-01-2026-04-27.md",
    "docs/review-actions/PLAN-D3L-NEXT-STEP-01A-2026-04-27.md",
    "docs/review-actions/PLAN-D3L-NEXT-STEP-01B-2026-04-27.md",
    "docs/reviews/D3L-NEXT-STEP-01-DELIVERY-REPORT.md",
    "scripts/build_next_step_recommendation.py",
    "scripts/build_dashboard_3ls_with_tls.py",
    "spectrum_systems/modules/dashboard_3ls/next_step_recommendation/next_step_artifact.py",
    "spectrum_systems/modules/dashboard_3ls/next_step_recommendation/next_step_dependency_rules.py",
    "spectrum_systems/modules/dashboard_3ls/next_step_recommendation/next_step_engine.py",
    "spectrum_systems/modules/dashboard_3ls/next_step_recommendation/next_step_inputs.py",
    "spectrum_systems/modules/dashboard_3ls/next_step_recommendation/next_step_redteam.py",
    "apps/dashboard-3ls/lib/nextStepArtifactLoader.ts",
    "apps/dashboard-3ls/components/NextStepPanel.tsx",
    "apps/dashboard-3ls/app/api/next-step/route.ts",
    "tests/test_next_step_recommendation.py",
]


def _reserved_tokens() -> set[str]:
    chunks = [
        ("de", "cision"),
        ("ap", "proval"),
        ("ap", "proved"),
        ("ap", "prove"),
        ("certifi", "cation"),
        ("certi", "fied"),
        ("enforce", "ment"),
        ("en", "force"),
        ("adjudi", "cation"),
    ]
    return {a + b for a, b in chunks}


def test_d3l_next_step_owned_files_avoid_reserved_authority_tokens() -> None:
    blocked = _reserved_tokens()
    violations: list[str] = []

    for rel_path in D3L_NEXT_STEP_FILES:
        path = REPO_ROOT / rel_path
        assert path.is_file(), f"expected file missing from scan set: {rel_path}"
        text = path.read_text(encoding="utf-8").lower()
        for token in blocked:
            if token in text:
                violations.append(f"{rel_path}: contains reserved token '{token}'")

    assert violations == [], "\n".join(violations)
