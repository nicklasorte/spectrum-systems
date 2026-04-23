"""Batch load all data hourly."""

import time
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

from .artifact_parser import ArtifactParser
from .health_calculator import HealthCalculator
from .lineage_validator import LineageValidator
from .github_client import GitHubClient
from .canonical_registry_loader import get_canonical_system_registry


logger = logging.getLogger(__name__)


class DataRefreshPipeline:
    """Refresh all dashboard data hourly."""

    def __init__(
        self,
        artifacts_root: Path,
        github_token: Optional[str] = None,
        repo_root: Optional[Path] = None,
    ):
        self.artifacts_root = artifacts_root
        self.github_token = github_token
        self.repo_root = repo_root
        self.last_refresh: Optional[datetime] = None

    def refresh_all(self) -> Dict[str, Any]:
        """Run full data refresh."""
        start_time = time.time()

        try:
            logger.info('Starting data refresh pipeline')

            # 0. Load canonical system registry
            logger.info('Loading canonical system registry...')
            system_registry = get_canonical_system_registry(self.repo_root)
            if not system_registry:
                logger.warning('No systems loaded from canonical registry, using empty set')

            # 1. Parse all artifacts
            logger.info('Parsing artifacts...')
            parser = ArtifactParser(self.artifacts_root)
            artifacts = parser.parse_all_artifacts()

            # 2. Calculate health scores
            logger.info('Calculating health scores...')
            calculator = HealthCalculator(artifacts, system_registry=system_registry)
            health_scores = calculator.calculate_all()

            # 3. Validate lineage
            logger.info('Validating lineage...')
            validator = LineageValidator(artifacts)
            lineage_status = validator.validate_all_chains()

            # 4. Fetch GitHub data
            github_data = {}
            if self.github_token:
                logger.info('Fetching GitHub data...')
                github = GitHubClient(
                    'nicklasorte',
                    'spectrum-systems',
                    self.github_token
                )
                merged_prs = github.get_merged_prs(datetime.utcnow())
                repo_health = github.get_repo_health()
                github_data = {
                    'prs_merged_today': len(merged_prs),
                    'repo_health': repo_health,
                }

            elapsed = time.time() - start_time
            self.last_refresh = datetime.utcnow()

            result = {
                'refreshed_at': datetime.utcnow().isoformat(),
                'duration_seconds': round(elapsed, 2),
                'status': 'success',
                'health_scores': {
                    sid: {
                        'system_id': m.system_id,
                        'system_name': m.system_name,
                        'system_type': m.system_type,
                        'health_score': m.health_score,
                        'status': m.status,
                        'execution_success': m.execution_success,
                        'contract_adherence': m.contract_adherence,
                        'incident_count': m.incident_count,
                        'avg_latency_ms': m.avg_latency_ms,
                        'incidents_week': m.incidents_week,
                        'contract_violations': m.contract_violations,
                    }
                    for sid, m in health_scores.items()
                },
                'lineage_status': lineage_status,
                'artifact_count': len(artifacts),
                'parse_errors': parser.get_errors(),
            }

            if github_data:
                result.update(github_data)

            logger.info(f'Data refresh completed in {elapsed:.2f}s')
            return result

        except Exception as e:
            logger.error(f'Refresh failed: {str(e)}', exc_info=True)
            return {
                'status': 'error',
                'error': str(e),
                'refreshed_at': datetime.utcnow().isoformat(),
            }

    def should_refresh(self, min_interval_minutes: int = 60) -> bool:
        """Check if enough time has passed for refresh."""
        if self.last_refresh is None:
            return True

        elapsed_minutes = (datetime.utcnow() - self.last_refresh).total_seconds() / 60
        return elapsed_minutes >= min_interval_minutes
