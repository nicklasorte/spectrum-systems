"""Shared fixtures for TLS dependency-graph tests.

These fixtures mirror what the production driver builds, but are kept tiny
so each phase can be exercised in isolation.
"""

from __future__ import annotations

from pathlib import Path

import pytest


REGISTRY_FIXTURE = """\
# System Registry (Canonical)

## Canonical loop

`AEX → PQX → EVL`

`REP + LIN`

## Active executable systems

### AEX
- **Status:** active
- **Purpose:** admission boundary.
- **Canonical Artifacts Owned:** `build_admission_record`.
- **Upstream Dependencies:** prompt requests.
- **Downstream Dependencies:** PQX.
- **Primary Code Paths:**
  - `spectrum_systems/modules/runtime/agent_golden_path.py`

### PQX
- **Status:** active
- **Purpose:** bounded execution.
- **Canonical Artifacts Owned:** `pqx_slice_execution_record`.
- **Upstream Dependencies:** AEX.
- **Downstream Dependencies:** EVL.
- **Primary Code Paths:**
  - `spectrum_systems/modules/runtime/pqx_execution_authority.py`

### EVL
- **Status:** active
- **Purpose:** evaluation gate.
- **Canonical Artifacts Owned:** `required_eval_coverage`,
  `eval_slice_summary`.
- **Upstream Dependencies:** PQX.
- **Downstream Dependencies:** TPA, CDE.
- **Primary Code Paths:**
  - `spectrum_systems/modules/runtime/eval_registry.py`

### REP
- **Status:** active
- **Purpose:** replay integrity.
- **Canonical Artifacts Owned:** `replay_run_record`.
- **Upstream Dependencies:** PQX.
- **Downstream Dependencies:** EVL.
- **Primary Code Paths:**
  - `spectrum_systems/modules/runtime/replay_engine.py`

### LIN
- **Status:** active
- **Purpose:** lineage authority.
- **Canonical Artifacts Owned:** `artifact_lineage_record`.
- **Upstream Dependencies:** all artifact producers.
- **Downstream Dependencies:** EVL.
- **Primary Code Paths:**
  - `spectrum_systems/modules/runtime/artifact_lineage.py`

## Merged or demoted systems

| System | Status | Merged/Demoted Into | Rationale |
| --- | --- | --- | --- |
| SUP | merged | JSX | Active-set governance. |
| HNX | deprecated | Artifact family | Stage harness retained. |

## Future / placeholder systems

| System | Status | Rationale |
| --- | --- | --- |
| ABX | future | Placeholder seam. |
"""


@pytest.fixture
def registry_fixture_path(tmp_path: Path) -> Path:
    path = tmp_path / "system_registry.md"
    path.write_text(REGISTRY_FIXTURE, encoding="utf-8")
    return path


@pytest.fixture
def repo_fixture(tmp_path: Path) -> Path:
    """Create a tiny fake repo with evidence for AEX/PQX/EVL/REP/LIN."""

    root = tmp_path / "repo"
    (root / "spectrum_systems" / "modules" / "runtime").mkdir(parents=True)
    (root / "spectrum_systems" / "modules" / "runtime" / "agent_golden_path.py").write_text(
        "# AEX admission boundary\nclass Aex:\n    pass\n", encoding="utf-8"
    )
    (root / "spectrum_systems" / "modules" / "runtime" / "pqx_execution_authority.py").write_text(
        "# PQX bounded executor\nclass Pqx:\n    pass\n", encoding="utf-8"
    )
    (root / "spectrum_systems" / "modules" / "runtime" / "eval_registry.py").write_text(
        "# EVL eval registry\nrequired_eval_coverage = True\n", encoding="utf-8"
    )
    (root / "spectrum_systems" / "modules" / "runtime" / "replay_engine.py").write_text(
        "# REP replay engine\nreplay_run_record = {}\n", encoding="utf-8"
    )
    (root / "spectrum_systems" / "modules" / "runtime" / "artifact_lineage.py").write_text(
        "# LIN lineage authority\nartifact_lineage_record = {}\n", encoding="utf-8"
    )

    (root / "tests").mkdir()
    (root / "tests" / "test_aex.py").write_text("def test_aex(): assert True\n", encoding="utf-8")
    (root / "tests" / "test_evl_eval.py").write_text("def test_evl(): assert True\n", encoding="utf-8")

    (root / "schemas").mkdir()
    (root / "schemas" / "eval_summary.schema.json").write_text(
        '{"title": "eval_summary", "evl_field": true}\n', encoding="utf-8"
    )

    (root / "docs").mkdir()
    (root / "docs" / "aex_overview.md").write_text(
        "# AEX overview\nAEX admits work.\n", encoding="utf-8"
    )
    (root / "reviews").mkdir()
    (root / "reviews" / "lin_review.md").write_text("# LIN review\nLIN is healthy.\n", encoding="utf-8")
    (root / "scripts").mkdir()
    (root / "scripts" / "run_pqx.py").write_text("# Run PQX slice\n", encoding="utf-8")
    (root / "artifacts").mkdir()
    (root / "artifacts" / "lineage_record.json").write_text(
        '{"artifact_lineage_record": "x"}\n', encoding="utf-8"
    )

    return root
