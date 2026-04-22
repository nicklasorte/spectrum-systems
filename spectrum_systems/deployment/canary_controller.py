"""Canary rollout controller for production data deployment."""

from datetime import datetime
from typing import Dict, Any


class CanaryRolloutController:
    """Gradually roll out production data to percentage of users."""

    def __init__(self, current_percentage: int = 1, max_users: int = 100):
        self.current_percentage = current_percentage
        self.max_users = max_users
        self.rollout_start_time = datetime.utcnow()

    def should_use_production_data(self, user_id: str) -> bool:
        """Determine if this user should see production data."""
        user_hash = hash(user_id) % 100
        return user_hash < self.current_percentage

    def record_metric(self, metric: str, value: float) -> None:
        """Track canary metrics."""
        if self.current_percentage == 1:
            key = f'canary_1pct_{metric}'
        elif self.current_percentage == 10:
            key = f'canary_10pct_{metric}'
        elif self.current_percentage == 50:
            key = f'canary_50pct_{metric}'
        else:
            key = f'canary_100pct_{metric}'

        print(f'{key}: {value}')

    def get_rollout_status(self) -> Dict[str, Any]:
        """Get current rollout status."""
        duration_minutes = (datetime.utcnow() - self.rollout_start_time).total_seconds() / 60
        return {
            'current_percentage': self.current_percentage,
            'duration_minutes': duration_minutes,
            'status': 'rolling_out',
            'next_increase_at_pct': min(self.current_percentage * 10, 100)
        }

    def increase_rollout(self, new_percentage: int) -> None:
        """Increase rollout percentage."""
        if new_percentage > 100:
            new_percentage = 100
        self.current_percentage = new_percentage
        print(f'Increased canary rollout to {new_percentage}%')
