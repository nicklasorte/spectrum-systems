"""Tests for Phase N: Alert Management."""

import pytest
from spectrum_systems.alerts.alert_engine import AlertEngine


class TestAlertEngine:
    """Test custom alert engine."""

    def test_add_alert(self):
        """N1: Can add custom alert."""
        engine = AlertEngine()
        alert = {
            'alert_id': 'alert_1',
            'name': 'High Divergence',
            'condition': 'decision_divergence',
            'threshold': 0.10,
            'channel': 'slack',
            'severity': 'warning'
        }
        engine.add_alert(alert)
        assert len(engine.alerts) == 1

    def test_add_alert_missing_fields(self):
        """N1: Alert validation checks required fields."""
        engine = AlertEngine()

        with pytest.raises(ValueError):
            engine.add_alert({'name': 'Test'})

    def test_evaluate_alerts(self):
        """N2: Can evaluate alerts against metrics."""
        store = {
            'snapshot': {
                'metrics': {
                    'decision_divergence': {'current': 0.15},
                    'exception_rate': {'current': 0.02}
                }
            }
        }
        engine = AlertEngine(store)
        engine.add_alert({
            'alert_id': 'alert_1',
            'name': 'High Divergence',
            'condition': 'decision_divergence',
            'threshold': 0.10,
            'channel': 'slack',
            'severity': 'critical',
            'active': True
        })

        fired = engine.evaluate_all_alerts()
        assert len(fired) == 1
        assert fired[0]['alert_id'] == 'alert_1'
        assert fired[0]['metric_value'] == 0.15

    def test_alert_below_threshold(self):
        """N2: Alert doesn't fire below threshold."""
        store = {
            'snapshot': {
                'metrics': {
                    'decision_divergence': {'current': 0.05}
                }
            }
        }
        engine = AlertEngine(store)
        engine.add_alert({
            'alert_id': 'alert_1',
            'name': 'High Divergence',
            'condition': 'decision_divergence',
            'threshold': 0.10,
            'channel': 'slack',
            'severity': 'warning',
            'active': True
        })

        fired = engine.evaluate_all_alerts()
        assert len(fired) == 0

    def test_inactive_alert_not_evaluated(self):
        """N2: Inactive alerts don't fire."""
        store = {
            'snapshot': {
                'metrics': {
                    'decision_divergence': {'current': 0.15}
                }
            }
        }
        engine = AlertEngine(store)
        engine.add_alert({
            'alert_id': 'alert_1',
            'name': 'High Divergence',
            'condition': 'decision_divergence',
            'threshold': 0.10,
            'channel': 'slack',
            'severity': 'critical',
            'active': False
        })

        fired = engine.evaluate_all_alerts()
        assert len(fired) == 0

    def test_false_positive_tracking(self):
        """N.5: Track false positives for tuning."""
        engine = AlertEngine()
        engine.record_false_positive()
        engine.record_false_positive()
        engine.record_true_positive()

        assert engine.false_positive_count == 2
        assert engine.true_positive_count == 1
        assert engine.get_false_positive_rate() == pytest.approx(2/3)

    def test_alert_stats(self):
        """N.5: Get alert engine statistics."""
        engine = AlertEngine()
        engine.add_alert({
            'alert_id': 'alert_1',
            'name': 'Test',
            'condition': 'decision_divergence',
            'threshold': 0.1,
            'channel': 'slack',
            'severity': 'warning',
            'active': True
        })
        engine.record_false_positive()
        engine.record_false_positive()
        engine.record_true_positive()

        stats = engine.get_alert_stats()
        assert stats['total_alerts_configured'] == 1
        assert stats['active_alerts'] == 1
        assert stats['false_positives'] == 2
        assert stats['true_positives'] == 1

    def test_disable_alert(self):
        """N2: Can disable specific alert."""
        engine = AlertEngine()
        engine.add_alert({
            'alert_id': 'alert_1',
            'name': 'Test',
            'condition': 'decision_divergence',
            'threshold': 0.1,
            'channel': 'slack',
            'severity': 'warning',
            'active': True
        })

        engine.disable_alert('alert_1')
        assert engine.alerts[0]['active'] is False

    def test_update_alert_threshold(self):
        """N.5: Can adjust alert threshold for tuning."""
        engine = AlertEngine()
        engine.add_alert({
            'alert_id': 'alert_1',
            'name': 'Test',
            'condition': 'decision_divergence',
            'threshold': 0.10,
            'channel': 'slack',
            'severity': 'warning'
        })

        engine.update_alert_threshold('alert_1', 0.15)
        assert engine.alerts[0]['threshold'] == 0.15

    def test_recent_alerts(self):
        """N2: Can retrieve recent fired alerts."""
        store = {
            'snapshot': {
                'metrics': {
                    'decision_divergence': {'current': 0.15}
                }
            }
        }
        engine = AlertEngine(store)
        engine.add_alert({
            'alert_id': 'alert_1',
            'name': 'High Divergence',
            'condition': 'decision_divergence',
            'threshold': 0.10,
            'channel': 'slack',
            'severity': 'critical',
            'active': True
        })

        engine.evaluate_all_alerts()
        recent = engine.get_recent_alerts(5)
        assert len(recent) == 1
        assert recent[0]['alert_id'] == 'alert_1'

    def test_multiple_alerts_evaluation(self):
        """N2: Can evaluate multiple alerts simultaneously."""
        store = {
            'snapshot': {
                'metrics': {
                    'decision_divergence': {'current': 0.15},
                    'exception_rate': {'current': 0.08}
                }
            }
        }
        engine = AlertEngine(store)
        engine.add_alert({
            'alert_id': 'alert_1',
            'name': 'High Divergence',
            'condition': 'decision_divergence',
            'threshold': 0.10,
            'channel': 'slack',
            'severity': 'warning',
            'active': True
        })
        engine.add_alert({
            'alert_id': 'alert_2',
            'name': 'High Exception Rate',
            'condition': 'exception_rate',
            'threshold': 0.05,
            'channel': 'pagerduty',
            'severity': 'critical',
            'active': True
        })

        fired = engine.evaluate_all_alerts()
        assert len(fired) == 2
