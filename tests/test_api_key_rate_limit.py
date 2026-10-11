"""Tests for per-key API rate limiting."""
import json
import pytest


class TestApiKeyRateLimiting:
    """Test per-key API rate limiting."""

    def test_default_rate_limits(self, app_context, clean_db):
        """New API keys should have default rate limits."""
        from app.services.api_key import create_api_key
        from app.models import User

        user = User(username='rate_test', password_hash='$2b$12$dummy',
                    role='admin', is_active=True, is_approved=True)
        from app import db as _db
        _db.session.add(user)
        _db.session.commit()

        key, token = create_api_key('Rate Test', user.id)
        assert key.max_requests_per_minute == 60
        assert key.max_requests_per_hour == 1000

    def test_custom_rate_limits(self, app_context, clean_db):
        """API keys can be created with custom rate limits."""
        from app.services.api_key import create_api_key
        from app.models import User, ApiKey

        user = User(username='rate_test', password_hash='$2b$12$dummy',
                    role='admin', is_active=True, is_approved=True)
        from app import db as _db
        _db.session.add(user)
        _db.session.commit()

        key, token = create_api_key('Rate Test', user.id)
        # Update rate limits
        key.max_requests_per_minute = 10
        key.max_requests_per_hour = 100
        _db.session.commit()

        stored = _db.session.get(ApiKey, key.id)
        assert stored.max_requests_per_minute == 10
        assert stored.max_requests_per_hour == 100

    def test_unlimited_rate_limit(self, app_context, clean_db):
        """Setting rate limit to 0 means unlimited."""
        from app.services.api_key import create_api_key
        from app.models import User, ApiKey

        user = User(username='rate_test', password_hash='$2b$12$dummy',
                    role='admin', is_active=True, is_approved=True)
        from app import db as _db
        _db.session.add(user)
        _db.session.commit()

        key, token = create_api_key('Unlimited Test', user.id)
        key.max_requests_per_minute = 0
        key.max_requests_per_hour = 0
        _db.session.commit()

        stored = _db.session.get(ApiKey, key.id)
        assert stored.max_requests_per_minute == 0
        assert stored.max_requests_per_hour == 0

    def test_rate_limit_enforcement(self, app_context, clean_db):
        """API key should be rate limited after exceeding per-minute limit."""
        from app.services.api_key import create_api_key, validate_api_key
        from app.models import User, ApiKey, RateLimitAttempt
        from datetime import timedelta

        user = User(username='rate_test', password_hash='$2b$12$dummy',
                    role='admin', is_active=True, is_approved=True)
        from app import db as _db
        _db.session.add(user)
        _db.session.commit()

        key, token = create_api_key('Limited Test', user.id)
        # Set a very low per-minute limit
        key.max_requests_per_minute = 2
        _db.session.commit()

        # First two requests should succeed
        result1 = validate_api_key(token)
        assert result1 is not None
        result2 = validate_api_key(token)
        assert result2 is not None

        # Third request should be rate limited
        result3 = validate_api_key(token)
        assert result3 is None

    def test_rate_limit_attempt_recorded(self, app_context, clean_db):
        """Rate limit attempts should be recorded in the database."""
        from app.services.api_key import create_api_key, validate_api_key
        from app.models import User, RateLimitAttempt

        user = User(username='rate_test', password_hash='$2b$12$dummy',
                    role='admin', is_active=True, is_approved=True)
        from app import db as _db
        _db.session.add(user)
        _db.session.commit()

        key, token = create_api_key('Record Test', user.id)
        validate_api_key(token)

        attempts = _db.session.query(RateLimitAttempt).filter_by(
            key=f'apikey:{key.id}'
        ).all()
        assert len(attempts) >= 1

    def test_per_hour_limit_enforcement(self, app_context, clean_db):
        """API key should be rate limited after exceeding per-hour limit."""
        from app.services.api_key import create_api_key, validate_api_key
        from app.models import User, ApiKey, RateLimitAttempt
        from datetime import timedelta

        user = User(username='rate_test', password_hash='$2b$12$dummy',
                    role='admin', is_active=True, is_approved=True)
        from app import db as _db
        _db.session.add(user)
        _db.session.commit()

        key, token = create_api_key('Hourly Test', user.id)
        # Set a very low per-hour limit but high per-minute limit
        key.max_requests_per_minute = 100
        key.max_requests_per_hour = 2
        _db.session.commit()

        # First two requests should succeed
        result1 = validate_api_key(token)
        assert result1 is not None
        result2 = validate_api_key(token)
        assert result2 is not None

        # Third request should be rate limited (per-hour)
        result3 = validate_api_key(token)
        assert result3 is None
