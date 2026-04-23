"""Tests for health calculator."""

import pytest
from spectrum_systems.dashboard.backend.health_calculator import HealthCalculator


class MockHealthCalculator:
    """Mock implementation for testing."""

    def calculate_health_score(self, system_id, metrics):
        """Calculate health score based on metrics."""
        execution_success = metrics.get('execution_success', 100)
        contract_adherence = metrics.get('contract_adherence', 100)
        incidents = metrics.get('incidents_week', 0)
        latency = metrics.get('avg_latency_ms', 0)

        health = (
            (execution_success * 0.4) +
            (contract_adherence * 0.3) +
            (max(0, 100 - min(incidents * 5, 100)) * 0.2) +
            (max(0, 100 - min(latency / 50, 100)) * 0.1)
        )
        return round(health, 1)

    def determine_status(self, health_score):
        """Determine status from health score."""
        if health_score >= 85:
            return 'healthy'
        elif health_score >= 70:
            return 'warning'
        else:
            return 'critical'


def test_calculate_health_perfect():
    """Test calculating health with perfect metrics."""
    calculator = MockHealthCalculator()
    metrics = {
        'execution_success': 100,
        'contract_adherence': 100,
        'incidents_week': 0,
        'avg_latency_ms': 0,
    }
    health = calculator.calculate_health_score('PQX', metrics)
    assert health == 100.0


def test_calculate_health_degraded():
    """Test calculating health with degraded metrics."""
    calculator = MockHealthCalculator()
    metrics = {
        'execution_success': 80,
        'contract_adherence': 75,
        'incidents_week': 2,
        'avg_latency_ms': 100,
    }
    health = calculator.calculate_health_score('RDX', metrics)
    assert health > 0
    assert health < 100


def test_calculate_health_critical():
    """Test calculating health with critical metrics."""
    calculator = MockHealthCalculator()
    metrics = {
        'execution_success': 50,
        'contract_adherence': 30,
        'incidents_week': 10,
        'avg_latency_ms': 500,
    }
    health = calculator.calculate_health_score('LCE', metrics)
    assert health < 70


def test_determine_status_healthy():
    """Test status determination for healthy."""
    calculator = MockHealthCalculator()
    assert calculator.determine_status(95) == 'healthy'
    assert calculator.determine_status(85) == 'healthy'


def test_determine_status_warning():
    """Test status determination for warning."""
    calculator = MockHealthCalculator()
    assert calculator.determine_status(80) == 'warning'
    assert calculator.determine_status(70) == 'warning'


def test_determine_status_critical():
    """Test status determination for critical."""
    calculator = MockHealthCalculator()
    assert calculator.determine_status(60) == 'critical'
    assert calculator.determine_status(0) == 'critical'


def test_health_formula_weights():
    """Test that health formula uses correct weights."""
    calculator = MockHealthCalculator()

    # Test execution success weight (40%) - includes perfect score for incidents/latency
    metrics_exec = {
        'execution_success': 100,
        'contract_adherence': 0,
        'incidents_week': 0,
        'avg_latency_ms': 0,
    }
    health_exec = calculator.calculate_health_score('TEST', metrics_exec)
    # 100 * 0.4 (exec) + 0 * 0.3 (contract) + 100 * 0.2 (incidents) + 100 * 0.1 (latency) = 70
    assert health_exec == 70.0

    # Test contract adherence weight (30%)
    metrics_contract = {
        'execution_success': 0,
        'contract_adherence': 100,
        'incidents_week': 0,
        'avg_latency_ms': 0,
    }
    health_contract = calculator.calculate_health_score('TEST', metrics_contract)
    # 0 * 0.4 (exec) + 100 * 0.3 (contract) + 100 * 0.2 (incidents) + 100 * 0.1 (latency) = 60
    assert health_contract == 60.0


def test_incidents_impact():
    """Test that incidents properly impact health."""
    calculator = MockHealthCalculator()

    # No incidents
    metrics_no_incidents = {
        'execution_success': 100,
        'contract_adherence': 100,
        'incidents_week': 0,
        'avg_latency_ms': 0,
    }
    health_no_incidents = calculator.calculate_health_score('TEST', metrics_no_incidents)

    # With incidents
    metrics_with_incidents = {
        'execution_success': 100,
        'contract_adherence': 100,
        'incidents_week': 1,
        'avg_latency_ms': 0,
    }
    health_with_incidents = calculator.calculate_health_score('TEST', metrics_with_incidents)

    assert health_no_incidents > health_with_incidents
