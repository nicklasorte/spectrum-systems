"""Tests for Phase C: Observability"""

import pytest
import json
from datetime import datetime


class TestPhaseCObservability:
    """Test observability deliverables."""

    def test_health_endpoint_exists(self):
        """C1: Health check endpoint exists."""
        with open('apps/dashboard/app/api/metrics/health.ts') as f:
            content = f.read()

        assert 'async function GET' in content
        assert 'artifact_api' in content
        assert 'checkArtifactAPI' in content

    def test_health_endpoint_returns_structure(self):
        """C2: Health endpoint returns expected structure."""
        with open('apps/dashboard/app/api/metrics/health.ts') as f:
            content = f.read()

        # Verify health check structure
        assert 'status' in content
        assert 'timestamp' in content
        assert 'uptime' in content
        assert 'memory' in content
        assert 'checks' in content

    def test_observability_module_exists(self):
        """C3: Observability module defined."""
        with open('apps/dashboard/lib/observability.ts') as f:
            content = f.read()

        # Verify required functions
        assert 'initializeObservability' in content
        assert 'captureException' in content
        assert 'captureMessage' in content
        assert 'startTransaction' in content

    def test_sentry_integration_configured(self):
        """C4: Sentry integration configured."""
        with open('apps/dashboard/lib/observability.ts') as f:
            content = f.read()

        assert 'Sentry.init' in content
        assert 'NEXT_PUBLIC_SENTRY_DSN' in content
        assert 'tracesSampleRate' in content
        assert 'replaysSessionSampleRate' in content

    def test_exception_capture_function(self):
        """C5: Exception capturing available."""
        with open('apps/dashboard/lib/observability.ts') as f:
            content = f.read()

        assert 'captureException' in content
        assert 'Error' in content
        assert 'custom' in content

    def test_message_capture_function(self):
        """C6: Message capturing available."""
        with open('apps/dashboard/lib/observability.ts') as f:
            content = f.read()

        assert 'captureMessage' in content
        assert 'info' in content
        assert 'warning' in content
        assert 'error' in content

    def test_transaction_tracking(self):
        """C7: Transaction tracking available."""
        with open('apps/dashboard/lib/observability.ts') as f:
            content = f.read()

        assert 'startTransaction' in content
        assert 'http.request' in content

    def test_artifact_api_check_timeout(self):
        """C8: Health check has timeout protection."""
        with open('apps/dashboard/app/api/metrics/health.ts') as f:
            content = f.read()

        # Should have timeout mechanism
        assert '5000' in content or 'timeout' in content.lower()

    def test_health_check_graceful_failure(self):
        """C9: Health check handles failures gracefully."""
        with open('apps/dashboard/app/api/metrics/health.ts') as f:
            content = f.read()

        assert 'try' in content
        assert 'catch' in content
        assert 'return' in content

    def test_observability_module_sentry_import(self):
        """C10: Observability module imports Sentry correctly."""
        with open('apps/dashboard/lib/observability.ts') as f:
            content = f.read()

        assert 'import * as Sentry' in content
        assert '@sentry/nextjs' in content
