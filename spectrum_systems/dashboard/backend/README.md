# Dashboard Backend

Python backend for 3-Letter Systems health monitoring and observability.

## Modules

### artifact_parser.py
Parses spectrum-systems JSON artifacts with robust error handling and caching.

**Classes:**
- `ArtifactCache` - Cached artifact data with freshness check
- `ArtifactParser` - Parses artifacts from filesystem

**Usage:**
```python
from spectrum_systems.dashboard.backend import ArtifactParser
from pathlib import Path

parser = ArtifactParser(Path('artifacts'))
artifacts = parser.parse_all_artifacts()
errors = parser.get_errors()
```

### health_calculator.py
Calculates health scores for all 28+ 3-letter systems (PQX, RDX, TPA, etc).

**Classes:**
- `SystemMetrics` - Dataclass with system metrics
- `HealthCalculator` - Calculates health scores

**Usage:**
```python
from spectrum_systems.dashboard.backend import HealthCalculator

calc = HealthCalculator(artifacts)
health_scores = calc.calculate_all()  # Dict[system_id, SystemMetrics]
```

### lineage_validator.py
Validates artifact lineage chains (parent-child relationships).

**Classes:**
- `LineageValidator` - Validates artifact chains

**Usage:**
```python
from spectrum_systems.dashboard.backend import LineageValidator

validator = LineageValidator(artifacts)
status = validator.validate_all_chains()
```

### github_client.py
Fetches data from GitHub spectrum-systems repository.

**Classes:**
- `GitHubClient` - GitHub API client

**Usage:**
```python
from spectrum_systems.dashboard.backend import GitHubClient
from datetime import datetime

client = GitHubClient('nicklasorte', 'spectrum-systems', token)
prs = client.get_merged_prs(since=datetime.utcnow())
repo_health = client.get_repo_health()
```

### data_refresh.py
Orchestrates full data refresh pipeline (hourly batch).

**Classes:**
- `DataRefreshPipeline` - Coordinates artifact parsing, health calculation, validation

**Usage:**
```python
from spectrum_systems.dashboard.backend import DataRefreshPipeline
from pathlib import Path

pipeline = DataRefreshPipeline(Path('artifacts'), github_token)
result = pipeline.refresh_all()
```

### safety_features.py
Safety controls: rate limiting, audit logging, validation.

**Classes:**
- `EmergencyRefreshController` - Rate-limited manual refresh
- `AuditLogger` - Comprehensive audit trail

**Usage:**
```python
from spectrum_systems.dashboard.backend import AuditLogger, EmergencyRefreshController

logger = AuditLogger()
logger.log_view('user123', 'dashboard', system_id='PQX')
logger.log_alert('TPA', 'health_warning', 'warning')
stats = logger.get_stats(hours=24)

refresh_ctrl = EmergencyRefreshController(min_interval_minutes=5)
result = refresh_ctrl.request_refresh()  # {'status': 'allowed'} or {'status': 'denied', ...}
```

### alerts.py
Alert generation and runbook linking.

**Classes:**
- `AlertEngine` - Generates alerts from health metrics

**Usage:**
```python
from spectrum_systems.dashboard.backend import AlertEngine

engine = AlertEngine()
alerts = engine.generate_alerts(health_scores)
critical_alerts = engine.filter_alerts_by_severity(alerts, 'critical')
deduped = engine.dedup_alerts(alerts)
```

## Architecture

```
ArtifactParser → Artifacts
                    ↓
            HealthCalculator → Health Scores
                    ↓
            LineageValidator → Lineage Status
                    ↓
            AlertEngine → Alerts
                    ↓
            DataRefreshPipeline → Dashboard JSON
```

## Integration

### With Frontend
```python
# Backend API returns this JSON structure
{
  "refreshed_at": "2024-04-23T12:34:56.789Z",
  "status": "success",
  "health_scores": {
    "system_id": {
      "system_id": "PQX",
      "system_name": "Bounded Execution",
      "system_type": "execution",
      "health_score": 95,
      "status": "healthy",
      ...
    }
  },
  "alerts": [...],
  "lineage_status": {...}
}
```

### Refresh Cycle
- Hourly automatic refresh (DataRefreshPipeline)
- Emergency manual refresh (rate-limited to 5min intervals)
- Daily limit: 50 manual refreshes
- All actions logged to AuditLogger

## Testing

```bash
# Unit tests
python -m pytest tests/test_artifact_parser.py
python -m pytest tests/test_health_calculator.py
python -m pytest tests/test_alerts.py

# Integration tests
python -m pytest tests/integration/

# All tests
python -m pytest tests/ -v
```

## Configuration

Environment variables:
- `GITHUB_TOKEN` - GitHub API token for PR fetching
- `ARTIFACTS_ROOT` - Path to artifacts directory (default: `./artifacts`)
- `LOG_LEVEL` - Logging level (default: `INFO`)
