"""Tests for Phase J: Production Data Wiring."""

import pytest
from spectrum_systems.deployment.canary_controller import CanaryRolloutController


class TestPhaseJProduction:
    """Verify production data integration."""

    def test_canary_rollout_deterministic(self):
        """J2: Canary rollout is deterministic per user."""
        controller = CanaryRolloutController(current_percentage=10)

        result1 = controller.should_use_production_data('user_123')
        result2 = controller.should_use_production_data('user_123')

        assert result1 == result2

    def test_canary_rollout_all_phases(self):
        """J2: Test all canary rollout phases."""
        for percentage in [1, 10, 50, 100]:
            controller = CanaryRolloutController(current_percentage=percentage)
            status = controller.get_rollout_status()

            assert status['current_percentage'] == percentage
            assert status['status'] == 'rolling_out'
            assert 'duration_minutes' in status

    def test_canary_percentage_distribution(self):
        """J1: Canary rollout respects percentage."""
        controller = CanaryRolloutController(current_percentage=10)

        users_in_canary = sum(
            1 for i in range(100)
            if controller.should_use_production_data(f'user_{i}')
        )

        assert 5 <= users_in_canary <= 20, f"Expected ~10% of users, got {users_in_canary}%"

    def test_canary_increase_rollout(self):
        """J2: Can increase rollout percentage."""
        controller = CanaryRolloutController(current_percentage=1)
        controller.increase_rollout(10)
        assert controller.current_percentage == 10

    def test_canary_max_percentage_capped(self):
        """J2: Rollout percentage capped at 100."""
        controller = CanaryRolloutController(current_percentage=1)
        controller.increase_rollout(150)
        assert controller.current_percentage == 100

    def test_canary_record_metric(self, capsys):
        """J2: Record metrics at different phases."""
        controller = CanaryRolloutController(current_percentage=10)
        controller.record_metric('latency', 42.5)

        captured = capsys.readouterr()
        assert 'canary_10pct_latency: 42.5' in captured.out

    def test_rollout_status_timing(self):
        """J3: Rollout status includes timing information."""
        controller = CanaryRolloutController(current_percentage=1)
        status = controller.get_rollout_status()

        assert status['duration_minutes'] >= 0
        assert 'next_increase_at_pct' in status

    def test_next_increase_calculation(self):
        """J2: Next increase calculated correctly."""
        for current, expected_next in [(1, 10), (10, 100), (50, 100), (100, 100)]:
            controller = CanaryRolloutController(current_percentage=current)
            status = controller.get_rollout_status()
            assert status['next_increase_at_pct'] == expected_next

    def test_canary_same_user_always_same_result(self):
        """CANARY-FIX-01: Repeated calls for the same user_id are stable
        across many iterations (regression for non-deterministic hash())."""
        controller = CanaryRolloutController(current_percentage=10)
        baseline = controller.should_use_production_data('user_42')
        for _ in range(50):
            assert controller.should_use_production_data('user_42') == baseline

    def test_canary_zero_percent_selects_no_users(self):
        """CANARY-FIX-01: 0% rollout must include zero users."""
        controller = CanaryRolloutController(current_percentage=0)
        for i in range(100):
            assert controller.should_use_production_data(f'user_{i}') is False

    def test_canary_full_percent_selects_all_users(self):
        """CANARY-FIX-01: 100% rollout must include every user."""
        controller = CanaryRolloutController(current_percentage=100)
        for i in range(100):
            assert controller.should_use_production_data(f'user_{i}') is True

    def test_canary_distribution_stable_across_repeated_calls(self):
        """CANARY-FIX-01: Two independently-constructed controllers at the
        same percentage must agree on every user assignment."""
        a = CanaryRolloutController(current_percentage=10)
        b = CanaryRolloutController(current_percentage=10)
        for i in range(100):
            uid = f'user_{i}'
            assert a.should_use_production_data(uid) == b.should_use_production_data(uid)
