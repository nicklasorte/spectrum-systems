import json
from pathlib import Path

import pytest

from spectrum_systems.modules.strategic_knowledge.catalog import register_source


def test_register_source_appends_entry(tmp_path: Path) -> None:
    catalog_path = tmp_path / 'strategic_knowledge' / 'metadata' / 'source_catalog.json'
    entry = register_source(
        source_catalog_path=catalog_path,
        source_id='SRC-BOOK-001',
        source_type='book_pdf',
        source_path='strategic_knowledge/raw/books/book1.pdf',
        title='Book One',
        tags=['strategy', 'book'],
    )

    assert entry['source_id'] == 'SRC-BOOK-001'
    payload = json.loads(catalog_path.read_text(encoding='utf-8'))
    assert len(payload['sources']) == 1
    assert payload['sources'][0]['source_type'] == 'book_pdf'


def test_duplicate_source_id_fails(tmp_path: Path) -> None:
    catalog_path = tmp_path / 'strategic_knowledge' / 'metadata' / 'source_catalog.json'
    kwargs = {
        'source_catalog_path': catalog_path,
        'source_id': 'SRC-001',
        'source_type': 'transcript',
        'source_path': 'strategic_knowledge/raw/transcripts/meeting.txt',
        'title': 'Meeting transcript',
    }
    register_source(**kwargs)
    with pytest.raises(ValueError, match='Duplicate source_id'):
        register_source(**kwargs)


def test_invalid_source_type_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match='Invalid source_type'):
        register_source(
            source_catalog_path=tmp_path / 'source_catalog.json',
            source_id='SRC-INVALID',
            source_type='podcast',
            source_path='strategic_knowledge/raw/transcripts/podcast.txt',
            title='Bad Source',
        )


def test_invalid_source_path_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match='source_path must be under strategic_knowledge/raw/'):
        register_source(
            source_catalog_path=tmp_path / 'source_catalog.json',
            source_id='SRC-INVALID-PATH',
            source_type='slide_deck',
            source_path='unscoped/raw/slides/deck.pdf',
            title='Invalid path',
        )
