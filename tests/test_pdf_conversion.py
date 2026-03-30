from __future__ import annotations

import hashlib
from pathlib import Path

import scripts.convert_pdf_to_md as convert_pdf_to_md


REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLE_PDF = REPO_ROOT / "docs" / "raw" / "system-architecture-source.pdf"
SAMPLE_MD = REPO_ROOT / "docs" / "source" / "system-architecture-source.md"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_converter_creates_output_file_and_non_empty(tmp_path: Path) -> None:
    output_path = tmp_path / "converted.md"

    result = convert_pdf_to_md.convert_pdf_to_markdown(SAMPLE_PDF, output_path)

    assert output_path.exists()
    assert output_path.read_text(encoding="utf-8").strip()
    assert len(result.markdown) > 100


def test_output_contains_expected_section_text() -> None:
    content = SAMPLE_MD.read_text(encoding="utf-8")

    assert "1. Governance Control Plane" in content
    assert "2. Source Authority Layer" in content
    assert "deterministic contracts" in content


def test_output_is_not_tiny_truncation_artifact() -> None:
    content = SAMPLE_MD.read_text(encoding="utf-8")

    assert len(content.strip()) > 200
    assert content.count("\n") >= 8


def test_repeated_conversion_is_deterministic(tmp_path: Path) -> None:
    output_path = tmp_path / "stable.md"

    convert_pdf_to_md.convert_pdf_to_markdown(SAMPLE_PDF, output_path)
    first_hash = _sha256(output_path)

    convert_pdf_to_md.convert_pdf_to_markdown(SAMPLE_PDF, output_path)
    second_hash = _sha256(output_path)

    assert first_hash == second_hash


def test_missing_input_file_fails_clearly(tmp_path: Path, capsys) -> None:
    missing_pdf = tmp_path / "missing.pdf"
    output_path = tmp_path / "out.md"

    code = convert_pdf_to_md.main(["--input", str(missing_pdf), "--output", str(output_path)])

    captured = capsys.readouterr()
    assert code == 2
    assert "input PDF not found" in captured.err
