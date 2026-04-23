"""Batch load all data hourly."""

import time
from pathlib import Path
from datetime import datetime
import logging
from typing import Dict, Any

from .artifact_parser import ArtifactParser
from .health_calculator import HealthCalculator
from .lineage_validator import LineageValidator


class DataRefreshPipeline:
    """Refresh all dashboard data hourly."""

    def __init__(self, artifacts_root: Path):
        self.artifacts_root = artifacts_root
        self.logger = logging.getLogger(__name__)

    def refresh_all(self) -> Dict[str, Any]:
        """Run full data refresh."""
        start_time = time.time()

        try:
            self.logger.info('Parsing artifacts...')
            parser = ArtifactParser(self.artifacts_root)
            artifacts = parser.parse_all_artifacts()

            self.logger.info('Calculating health scores...')
            calculator = HealthCalculator(artifacts)
            health_scores = calculator.calculate_all()

            self.logger.info('Validating lineage...')
            validator = LineageValidator(artifacts)
            lineage_status = validator.validate_all_chains()

            elapsed = time.time() - start_time

            return {
                'refreshed_at': datetime.utcnow().isoformat(),
                'duration_seconds': elapsed,
                'status': 'success',
                'health_scores': {
                    system_id: {
                        'system_id': m.system_id,
                        'system_name': m.system_name,
                        'system_type': m.system_type,
                        'health_score': m.health_score,
                        'status': m.status,
                        'incidents_week': m.incidents_week,
                        'contract_violations': m.contract_violations,
                    }
                    for system_id, m in health_scores.items()
                },
                'lineage_status': lineage_status,
                'artifact_count': len(artifacts),
                'errors': parser.get_errors(),
            }

        except Exception as e:
            self.logger.error(f'Refresh failed: {str(e)}')
            return {
                'status': 'error',
                'error': str(e),
            }
