"""HOP-005 regression test: HOP module surface stays authority-safe.

This test runs the AGS-001 authority-shape preflight against the entire
HOP scope and asserts zero violations. If a future change reintroduces
a forbidden artifact_type, schema_ref, field name, or enum value, this
test fails before the violations reach CI.

Scope: every file under
- ``spectrum_systems/modules/hop/``
- ``spectrum_systems/cli/hop_cli.py``
- ``contracts/schemas/hop/``
- ``contracts/evals/hop/``
- ``contracts/evals/hop_heldout/``
- ``docs/hop/``
- ``scripts/hop_run_controlled_trial.py``
- ``artifacts/hop_trial_run/``

The test does not mutate files; it only reads the live preflight result.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from spectrum_systems.governance.authority_shape_preflight import (
    evaluate_preflight,
    load_vocabulary,
)


REPO_ROOT = Path(__file__).resolve().parents[2]


def _hop_files() -> list[str]:
    roots = [
        "spectrum_systems/modules/hop",
        "contracts/schemas/hop",
        "contracts/evals/hop",
        "contracts/evals/hop_heldout",
        "docs/hop",
        "artifacts/hop_trial_run",
    ]
    files: list[str] = []
    for root in roots:
        for path in (REPO_ROOT / root).rglob("*"):
            if path.is_file() and path.suffix in {".py", ".json", ".md"}:
                files.append(str(path.relative_to(REPO_ROOT)))
    files.append("spectrum_systems/cli/hop_cli.py")
    files.append("scripts/hop_run_controlled_trial.py")
    return sorted(files)


@pytest.fixture(scope="module")
def vocab():
    return load_vocabulary(
        REPO_ROOT / "contracts" / "governance" / "authority_shape_vocabulary.json"
    )


def test_hop_scope_passes_authority_shape_preflight(vocab) -> None:
    """No HOP-scoped file may contain authority-shaped identifiers.

    The preflight scans the same vocabulary used by CI's AGS-001 guard.
    A failure here means a contributor reintroduced a forbidden term
    (promotion_decision, rollback_record, blocks_promotion, etc.) into
    a HOP file. Use ``signal``/``observation``/``input``-suffixed names
    instead, or move the symbol into a canonical owner path.
    """
    files = _hop_files()
    result = evaluate_preflight(
        repo_root=REPO_ROOT, changed_files=files, vocab=vocab, mode="suggest-only"
    )
    if result.violations:
        formatted = "\n".join(
            f"  {v.file}:{v.line} [{v.cluster}] {v.symbol} -> "
            f"{v.suggested_replacements[0] if v.suggested_replacements else '?'}"
            for v in result.violations[:50]
        )
        pytest.fail(
            f"HOP scope produced {len(result.violations)} authority-shape "
            f"violations:\n{formatted}"
        )
