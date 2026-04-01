from __future__ import annotations

from pathlib import Path

import pytest

from spectrum_systems.contracts import validate_artifact
from spectrum_systems.modules.runtime.review_signal_extractor import (
    ReviewSignalExtractionError,
    extract_review_signal,
)


def _write(tmp_path: Path, name: str, content: str) -> Path:
    path = tmp_path / name
    path.write_text(content, encoding="utf-8")
    return path


def test_extract_review_signal_from_repo_native_markdown(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "review.md",
        """---
review_id: REV-TEST-001
review_type: trust_boundary_surgical
review_date: 2026-04-01
decision: FAIL
trust_assessment: medium
---

## Critical Findings
- F-001 control seam mismatch
- F-002 expansion safety bypass
""",
    )
    artifact = extract_review_signal(path)
    validate_artifact(artifact, "review_control_signal")
    assert artifact["review_id"] == "REV-TEST-001"
    assert artifact["gate_assessment"] == "FAIL"
    assert artifact["scale_recommendation"] == "NO"
    assert artifact["critical_findings"] == [
        "F-001 control seam mismatch",
        "F-002 expansion safety bypass",
    ]


def test_malformed_review_fails_closed(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "bad.md",
        """# Missing frontmatter
## Critical Findings
- not parseable
""",
    )
    with pytest.raises(ReviewSignalExtractionError):
        extract_review_signal(path)


def test_extractor_is_deterministic(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "review.md",
        """---
review_type: trust_boundary_surgical
review_date: 2026-04-01
decision: CONDITIONAL
trust_assessment: high
---

## Critical Findings
- F-001 deterministic finding
""",
    )
    first = extract_review_signal(path)
    second = extract_review_signal(path)
    assert first == second
