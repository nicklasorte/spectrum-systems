"""Validate artifact lineage chains."""

from typing import Dict, Any, List


class LineageValidator:
    """Validate parent-child artifact chains."""

    def __init__(self, artifacts: Dict[str, Dict[str, Any]]):
        self.artifacts = artifacts
        self.errors: List[str] = []

    def validate_all_chains(self) -> Dict[str, Any]:
        """Validate all lineage chains."""
        chains_found = 0
        chains_valid = 0
        broken_chains = []

        for artifact_path, artifact_data in self.artifacts.items():
            if 'parent_ids' in artifact_data or 'parent_id' in artifact_data:
                chains_found += 1

                parent_ids = artifact_data.get('parent_ids', [])
                if not parent_ids and 'parent_id' in artifact_data:
                    parent_ids = [artifact_data['parent_id']]

                parents_exist = all(
                    self._parent_exists(parent_id)
                    for parent_id in parent_ids
                )

                if parents_exist:
                    chains_valid += 1
                else:
                    broken_chains.append(artifact_path)

        completeness = (chains_valid / chains_found * 100) if chains_found > 0 else 100

        return {
            'chains_found': chains_found,
            'chains_valid': chains_valid,
            'broken_chains': broken_chains,
            'completeness_percent': completeness,
        }

    def _parent_exists(self, parent_id: str) -> bool:
        """Check if parent artifact exists."""
        for artifact in self.artifacts.values():
            if artifact.get('artifact_id') == parent_id:
                return True
        return False
