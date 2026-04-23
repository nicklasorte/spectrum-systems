"""Tests for artifact parser."""

import pytest
import json
import tempfile
from pathlib import Path
from spectrum_systems.dashboard.backend.artifact_parser import ArtifactParser, ArtifactCache
from datetime import datetime, timedelta


def test_artifact_parser_init():
    """Test artifact parser initialization."""
    with tempfile.TemporaryDirectory() as tmpdir:
        parser = ArtifactParser(Path(tmpdir))
        assert parser.artifacts_root == Path(tmpdir)
        assert len(parser.cache) == 0
        assert len(parser.errors) == 0


def test_parse_artifact_not_found():
    """Test parsing artifact that doesn't exist."""
    with tempfile.TemporaryDirectory() as tmpdir:
        parser = ArtifactParser(Path(tmpdir))
        result = parser.parse_artifact('nonexistent.json')
        assert result is None
        assert len(parser.get_errors()) == 1


def test_parse_valid_artifact():
    """Test parsing a valid artifact."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)

        # Create test artifact
        artifact_data = {'artifact_type': 'test', 'value': 42}
        artifact_file = tmppath / 'test.json'
        with open(artifact_file, 'w') as f:
            json.dump(artifact_data, f)

        parser = ArtifactParser(tmppath)
        result = parser.parse_artifact('test.json')

        assert result is not None
        assert result['artifact_type'] == 'test'
        assert result['value'] == 42


def test_parse_invalid_json():
    """Test parsing invalid JSON."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)

        # Create invalid JSON file
        artifact_file = tmppath / 'invalid.json'
        with open(artifact_file, 'w') as f:
            f.write('{ invalid json }')

        parser = ArtifactParser(tmppath)
        result = parser.parse_artifact('invalid.json')

        assert result is None
        assert len(parser.get_errors()) > 0


def test_artifact_cache_freshness():
    """Test artifact cache freshness check."""
    # Fresh cache
    fresh_cache = ArtifactCache(
        data={'test': 'data'},
        parsed_at=datetime.utcnow(),
        checksum='abc123'
    )
    assert fresh_cache.is_fresh(max_age_hours=1) is True

    # Stale cache
    stale_cache = ArtifactCache(
        data={'test': 'data'},
        parsed_at=datetime.utcnow() - timedelta(hours=2),
        checksum='abc123'
    )
    assert stale_cache.is_fresh(max_age_hours=1) is False


def test_parse_all_artifacts():
    """Test parsing all artifacts in a directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)

        # Create multiple test artifacts
        artifacts = {
            'artifact1.json': {'artifact_type': 'test1'},
            'artifact2.json': {'artifact_type': 'test2'},
            'subdir/artifact3.json': {'artifact_type': 'test3'},
        }

        for filename, data in artifacts.items():
            filepath = tmppath / filename
            filepath.parent.mkdir(parents=True, exist_ok=True)
            with open(filepath, 'w') as f:
                json.dump(data, f)

        parser = ArtifactParser(tmppath)
        result = parser.parse_all_artifacts()

        assert len(result) == 3
        assert all(filepath in result for filepath in artifacts.keys())


def test_error_logging():
    """Test error logging."""
    with tempfile.TemporaryDirectory() as tmpdir:
        parser = ArtifactParser(Path(tmpdir))

        # Trigger some errors
        parser.parse_artifact('nonexistent1.json')
        parser.parse_artifact('nonexistent2.json')

        errors = parser.get_errors()
        assert len(errors) == 2

        # Clear errors
        parser.clear_errors()
        assert len(parser.get_errors()) == 0
