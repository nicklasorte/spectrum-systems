"""Safety features: validation, refresh control, audit logging."""

from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import logging


logger = logging.getLogger(__name__)


class EmergencyRefreshController:
    """Manual refresh with safety limits."""

    def __init__(self, min_interval_minutes: int = 5, max_daily_refreshes: int = 50):
        self.min_interval_minutes = min_interval_minutes
        self.max_daily_refreshes = max_daily_refreshes
        self.last_refresh: Optional[datetime] = None
        self.manual_refresh_count = 0
        self.daily_refresh_count = 0
        self.daily_reset_time = datetime.utcnow()

    def can_refresh_now(self) -> Dict[str, Any]:
        """Check if refresh is allowed."""
        now = datetime.utcnow()

        # Reset daily counter if needed
        if now.date() > self.daily_reset_time.date():
            self.daily_refresh_count = 0
            self.daily_reset_time = now

        # Check daily limit
        if self.daily_refresh_count >= self.max_daily_refreshes:
            return {
                'allowed': False,
                'reason': 'Daily limit exceeded',
                'current': self.daily_refresh_count,
                'limit': self.max_daily_refreshes,
            }

        # Check interval
        if self.last_refresh is None:
            return {'allowed': True}

        elapsed = now - self.last_refresh
        elapsed_minutes = elapsed.total_seconds() / 60

        if elapsed_minutes < self.min_interval_minutes:
            minutes_until_next = self.min_interval_minutes - elapsed_minutes
            return {
                'allowed': False,
                'reason': 'Rate limited',
                'minutes_until_next': round(minutes_until_next, 1),
            }

        return {'allowed': True}

    def request_refresh(self) -> Dict[str, Any]:
        """Request manual emergency refresh."""
        check = self.can_refresh_now()

        if not check['allowed']:
            return {
                'status': 'denied',
                'reason': check['reason'],
                'details': check,
            }

        self.last_refresh = datetime.utcnow()
        self.manual_refresh_count += 1
        self.daily_refresh_count += 1

        return {
            'status': 'allowed',
            'message': 'Emergency refresh triggered',
            'manual_refreshes': self.manual_refresh_count,
            'daily_refreshes': self.daily_refresh_count,
        }


class AuditLogger:
    """Log all dashboard access and changes."""

    def __init__(self, max_logs: int = 10000):
        self.logs: List[Dict[str, Any]] = []
        self.max_logs = max_logs

    def log_view(
        self,
        user_id: str,
        view: str,
        system_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Log a user viewing the dashboard."""
        self._add_log({
            'user_id': user_id,
            'action': 'view',
            'view': view,
            'system_id': system_id,
            'details': details or {},
        })

    def log_refresh(
        self,
        manual: bool,
        duration_seconds: float,
        artifact_count: int = 0,
    ) -> None:
        """Log a data refresh."""
        self._add_log({
            'action': 'refresh',
            'manual': manual,
            'duration_seconds': duration_seconds,
            'artifact_count': artifact_count,
        })

    def log_alert(
        self,
        system_id: str,
        alert_type: str,
        severity: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Log an alert being triggered."""
        self._add_log({
            'action': 'alert',
            'system_id': system_id,
            'alert_type': alert_type,
            'severity': severity,
            'details': details or {},
        })

    def log_error(self, error_msg: str, source: str = 'unknown') -> None:
        """Log an error."""
        self._add_log({
            'action': 'error',
            'error': error_msg,
            'source': source,
        })

    def _add_log(self, entry: Dict[str, Any]) -> None:
        """Add a log entry with timestamp."""
        log_entry = {
            'timestamp': datetime.utcnow().isoformat(),
            **entry,
        }
        self.logs.append(log_entry)

        if len(self.logs) > self.max_logs:
            self.logs = self.logs[-self.max_logs :]
            logger.warning('Audit log size exceeded, pruned old entries')

    def get_logs(
        self,
        hours: int = 24,
        action: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get recent logs with optional filtering."""
        cutoff = datetime.utcnow() - timedelta(hours=hours)

        filtered = []
        for log in self.logs:
            log_time = datetime.fromisoformat(log['timestamp'])
            if log_time < cutoff:
                continue

            if action and log.get('action') != action:
                continue

            if user_id and log.get('user_id') != user_id:
                continue

            filtered.append(log)

        return filtered

    def get_stats(self, hours: int = 24) -> Dict[str, Any]:
        """Get statistics about logged activity."""
        logs = self.get_logs(hours=hours)

        actions = {}
        users = set()

        for log in logs:
            action = log.get('action', 'unknown')
            actions[action] = actions.get(action, 0) + 1

            if 'user_id' in log:
                users.add(log['user_id'])

        return {
            'total_logs': len(logs),
            'actions': actions,
            'unique_users': len(users),
            'period_hours': hours,
        }

    def clear_old_logs(self, hours: int = 168) -> int:
        """Remove logs older than specified hours."""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        original_count = len(self.logs)

        self.logs = [
            log for log in self.logs
            if datetime.fromisoformat(log['timestamp']) > cutoff
        ]

        removed = original_count - len(self.logs)
        if removed > 0:
            logger.info(f'Pruned {removed} old audit logs')

        return removed
