from pathlib import Path
import re


REPO_ROOT = Path(__file__).resolve().parents[1]
ADR_DIR = REPO_ROOT / "docs" / "adr"
ADR_TEMPLATE = ADR_DIR / "ADR-TEMPLATE.md"
ADR_INDEX = ADR_DIR / "README.md"


def _adr_files() -> list[Path]:
    return [
        path
        for path in ADR_DIR.glob("ADR-*.md")
        if path.name not in {"ADR-TEMPLATE.md"}
    ]


def test_adr_directory_exists() -> None:
    assert ADR_DIR.is_dir(), "docs/adr directory must exist"


def test_adr_template_exists() -> None:
    assert ADR_TEMPLATE.is_file(), "ADR template must exist at docs/adr/ADR-TEMPLATE.md"


def test_adr_index_exists() -> None:
    assert ADR_INDEX.is_file(), "ADR index must exist at docs/adr/README.md"


def test_at_least_three_adrs_present() -> None:
    adrs = _adr_files()
    assert len(adrs) >= 3, "At least three ADRs must exist in docs/adr"


def test_adr_filenames_follow_pattern() -> None:
    pattern = re.compile(r"ADR-\d{3}-[a-z0-9-]+\.md$")
    for adr in _adr_files():
        assert pattern.match(adr.name), f"Invalid ADR filename: {adr.name}"
