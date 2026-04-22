"""Tests for Phase B: Security"""

import pytest
import json
from unittest.mock import patch


class TestPhaseBSecurity:
    """Test security deliverables."""

    def test_auth_policy_schema_valid(self):
        """B1: Authentication policy conforms to schema."""
        import jsonschema

        with open('contracts/schemas/api-auth-policy.schema.json') as f:
            schema = json.load(f)

        policy = {
            'policy_id': 'auth_1',
            'auth_method': 'oauth2',
            'rate_limit_per_minute': 100,
            'allowed_origins': ['https://spectrum-systems-dashboard.vercel.app'],
            'status': 'active'
        }

        jsonschema.validate(policy, schema)

    def test_auth_policy_invalid_without_required_fields(self):
        """B1: Authentication policy validation fails without required fields."""
        import jsonschema

        with open('contracts/schemas/api-auth-policy.schema.json') as f:
            schema = json.load(f)

        invalid_policy = {
            'policy_id': 'auth_1',
            # Missing auth_method, rate_limit_per_minute, allowed_origins, status
        }

        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(invalid_policy, schema)

    def test_auth_method_enum_validation(self):
        """B2: Only valid auth methods accepted."""
        import jsonschema

        with open('contracts/schemas/api-auth-policy.schema.json') as f:
            schema = json.load(f)

        # Valid methods
        for method in ['oauth2', 'api_key', 'jwt']:
            policy = {
                'policy_id': 'auth_1',
                'auth_method': method,
                'rate_limit_per_minute': 100,
                'allowed_origins': ['https://example.com'],
                'status': 'active'
            }
            jsonschema.validate(policy, schema)

        # Invalid method
        invalid_policy = {
            'policy_id': 'auth_1',
            'auth_method': 'invalid_method',
            'rate_limit_per_minute': 100,
            'allowed_origins': ['https://example.com'],
            'status': 'active'
        }

        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(invalid_policy, schema)

    def test_rate_limit_minimum_enforcement(self):
        """B3: Rate limit must be minimum 10."""
        import jsonschema

        with open('contracts/schemas/api-auth-policy.schema.json') as f:
            schema = json.load(f)

        # Valid rate limit
        valid_policy = {
            'policy_id': 'auth_1',
            'auth_method': 'oauth2',
            'rate_limit_per_minute': 100,
            'allowed_origins': ['https://example.com'],
            'status': 'active'
        }
        jsonschema.validate(valid_policy, schema)

        # Invalid rate limit (too low)
        invalid_policy = {
            'policy_id': 'auth_1',
            'auth_method': 'oauth2',
            'rate_limit_per_minute': 5,
            'allowed_origins': ['https://example.com'],
            'status': 'active'
        }

        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(invalid_policy, schema)

    def test_api_auth_policy_schema_exists(self):
        """Verify API auth policy schema exists and is valid JSON."""
        with open('contracts/schemas/api-auth-policy.schema.json') as f:
            schema = json.load(f)

        assert schema['title'] == 'APIAuthPolicy'
        assert 'properties' in schema
        assert 'auth_method' in schema['required']
        assert 'rate_limit_per_minute' in schema['required']

    def test_security_headers_defined(self):
        """B4: Security headers are defined in middleware config."""
        with open('apps/dashboard/middleware.ts') as f:
            middleware_content = f.read()

        # Check for security headers
        security_headers = [
            'X-Content-Type-Options',
            'X-Frame-Options',
            'X-XSS-Protection',
            'Strict-Transport-Security',
            'Content-Security-Policy'
        ]

        for header in security_headers:
            assert header in middleware_content, f'Missing security header: {header}'

    def test_csp_policy_present(self):
        """B5: Content Security Policy defined."""
        with open('apps/dashboard/middleware.ts') as f:
            middleware_content = f.read()

        assert "Content-Security-Policy" in middleware_content
        assert "default-src 'self'" in middleware_content
