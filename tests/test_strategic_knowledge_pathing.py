from pathlib import Path

import pytest

from spectrum_systems.modules.strategic_knowledge.pathing import (
    artifact_absolute_path,
    required_data_lake_dirs,
    source_absolute_path,
)


def test_source_path_resolution() -> None:
    root = Path('/lake')
    resolved = source_absolute_path(root, 'book_pdf', 'book-a.pdf')
    assert resolved == Path('/lake/strategic_knowledge/raw/books/book-a.pdf')


def test_artifact_path_resolution() -> None:
    root = Path('/lake')
    resolved = artifact_absolute_path(
        root,
        'story_bank_entry',
        'SRC-001',
        'STORY-01',
        '1.0.0',
    )
    assert resolved == Path('/lake/strategic_knowledge/processed/story_bank/SRC-001__STORY-01__v1.0.0.json')


def test_invalid_types_fail_closed() -> None:
    with pytest.raises(ValueError):
        source_absolute_path(Path('/lake'), 'audio', 'x.wav')
    with pytest.raises(ValueError):
        artifact_absolute_path(Path('/lake'), 'unknown_artifact', 'a', 'b', '1.0.0')


def test_required_directories_include_contract_targets() -> None:
    dirs = set(required_data_lake_dirs())
    assert Path('strategic_knowledge/raw/books') in dirs
    assert Path('strategic_knowledge/raw/transcripts') in dirs
    assert Path('strategic_knowledge/raw/slides') in dirs
    assert Path('strategic_knowledge/processed/book_intelligence') in dirs
    assert Path('strategic_knowledge/processed/transcript_intelligence') in dirs
    assert Path('strategic_knowledge/processed/evidence_maps') in dirs
