"""Parse spectrum-systems artifacts with robust error handling."""

import json
import hashlib
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass
class ArtifactCache:
    """Cache parsed artifacts to avoid re-parsing."""
    data: Dict[str, Any]
    parsed_at: datetime
    checksum: str

    def is_fresh(self, max_age_hours: int = 1) -> bool:
        """Check if cache is still fresh."""
        return datetime.utcnow() - self.parsed_at < timedelta(hours=max_age_hours)


class ArtifactParser:
    """Parse JSON artifacts with fallback strategy."""

    def __init__(self, artifacts_root: Path):
        self.artifacts_root = artifacts_root
        self.cache: Dict[str, ArtifactCache] = {}
        self.errors: List[Dict[str, Any]] = []

    def parse_artifact(self, path: str) -> Optional[Dict[str, Any]]:
        """Parse artifact file with error handling."""
        cache_key = path

        # Check cache
        if cache_key in self.cache and self.cache[cache_key].is_fresh():
            return self.cache[cache_key].data

        try:
            full_path = self.artifacts_root / path

            if not full_path.exists():
                self._log_error(f'Artifact not found: {path}')
                return None

            with open(full_path, 'r') as f:
                data = json.load(f)

            # Validate structure
            if not self._validate_artifact(data):
                self._log_error(f'Invalid artifact structure: {path}')
                return None

            # Cache it
            checksum = hashlib.md5(json.dumps(data).encode()).hexdigest()
            self.cache[cache_key] = ArtifactCache(
                data=data,
                parsed_at=datetime.utcnow(),
                checksum=checksum
            )

            return data

        except json.JSONDecodeError as e:
            self._log_error(f'JSON decode error in {path}: {str(e)}')
            return None
        except Exception as e:
            self._log_error(f'Unexpected error parsing {path}: {str(e)}')
            return None

    def parse_all_artifacts(self) -> Dict[str, Dict[str, Any]]:
        """Parse all artifacts in batch."""
        artifacts = {}

        if not self.artifacts_root.exists():
            self._log_error(f'Artifacts directory not found: {self.artifacts_root}')
            return artifacts

        for json_file in self.artifacts_root.glob('**/*.json'):
            relative_path = json_file.relative_to(self.artifacts_root)
            artifact = self.parse_artifact(str(relative_path))

            if artifact:
                artifacts[str(relative_path)] = artifact

        return artifacts

    def _validate_artifact(self, data: Dict[str, Any]) -> bool:
        """Validate artifact has required fields."""
        if not isinstance(data, dict):
            return False
        required = ['artifact_type']
        return all(field in data for field in required)

    def _log_error(self, error: str) -> None:
        """Log parsing error."""
        self.errors.append({
            'timestamp': datetime.utcnow().isoformat(),
            'error': error
        })

    def get_errors(self) -> List[Dict[str, Any]]:
        """Get all parsing errors."""
        return self.errors

    def clear_errors(self) -> None:
        """Clear error log."""
        self.errors = []
