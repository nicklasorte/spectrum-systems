"""Load and cache canonical system registry from docs/architecture/system_registry.md.

This module respects module boundaries by reading from the canonical registry
rather than hardcoding system definitions.
"""

from typing import Dict, Any, Optional
from pathlib import Path
import re


class CanonicalRegistryLoader:
    """Load system registry from canonical documentation source."""

    # System acronym pattern (2-3 uppercase letters or numbers)
    SYSTEM_PATTERN = re.compile(r'^-\s+\*\*([A-Z0-9]{2,8})\*\*\s+—\s+(.+)$')

    @staticmethod
    def load_from_path(registry_path: Path) -> Dict[str, Dict[str, Any]]:
        """Load system registry from markdown file.

        Returns dict with system_id -> {name, description, ...}
        """
        systems = {}

        if not registry_path.exists():
            return systems

        try:
            with open(registry_path, 'r') as f:
                content = f.read()

            # Extract "System Map" section
            in_system_map = False
            for line in content.split('\n'):
                if '## System Map' in line:
                    in_system_map = True
                    continue

                if in_system_map and line.startswith('##'):
                    # New section, stop parsing
                    break

                if in_system_map and line.strip():
                    match = CanonicalRegistryLoader.SYSTEM_PATTERN.match(line)
                    if match:
                        system_id = match.group(1)
                        description = match.group(2)
                        systems[system_id] = {
                            'id': system_id,
                            'description': description,
                            'type': CanonicalRegistryLoader._infer_type(system_id, description),
                        }

        except Exception:
            # If reading fails, return empty dict
            pass

        return systems

    @staticmethod
    def _infer_type(system_id: str, description: str) -> str:
        """Infer system type from description."""
        desc_lower = description.lower()

        if any(w in desc_lower for w in ['execution', 'engine', 'executor', 'bounded']):
            return 'execution'
        elif any(w in desc_lower for w in ['governance', 'policy', 'gate', 'authority']):
            return 'governance'
        elif any(w in desc_lower for w in ['orchestration', 'routing', 'top-level']):
            return 'orchestration'
        elif any(w in desc_lower for w in ['data', 'backbone', 'metadata', 'lineage']):
            return 'data'
        elif any(w in desc_lower for w in ['planning', 'extraction', 'recommendation']):
            return 'planning'
        else:
            return 'support'


def get_canonical_system_registry(repo_root: Optional[Path] = None) -> Dict[str, Dict[str, Any]]:
    """Get canonical system registry from canonical source.

    Args:
        repo_root: Repository root directory. If None, searches relative to this module.

    Returns:
        Dictionary mapping system_id -> {id, description, type}
    """
    if repo_root is None:
        # Search from current file location upward
        current = Path(__file__).parent
        while current != current.parent:
            candidate = current / 'docs' / 'architecture' / 'system_registry.md'
            if candidate.exists():
                repo_root = current
                break
            current = current.parent

    if repo_root is None:
        return {}

    registry_path = repo_root / 'docs' / 'architecture' / 'system_registry.md'
    return CanonicalRegistryLoader.load_from_path(registry_path)
