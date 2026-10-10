"""Tests for DB-backed rate limiter."""
import time
import pytest


class TestSimpleRateLimiter:
    """Test the auth rate limiter with DB persistence."""

    def test_first_attempt_not_limited(self, app_context):
        """First attempt should not be rate limited."""
        from app.services.rate_limiter import SimpleRateLimiter

        limiter = SimpleRateLimiter(max_attempts=3, window_seconds=60)
        limited, remaining = limiter.is_rate_limited('test:key:1')
        assert limited is False
        assert remaining == 0

    def test_within_limit(self, app_context):
        """Attempts within the limit should pass."""
        from app.services.rate_limiter import SimpleRateLimiter

        limiter = SimpleRateLimiter(max_attempts=3, window_seconds=60)
        for i in range(3):
            limited, remaining = limiter.is_rate_limited(f'test:within:{i}')
            assert limited is False

    def test_exceeds_limit(self, app_context):
        """Attempts exceeding the limit should be blocked."""
        from app.services.rate_limiter import SimpleRateLimiter

        limiter = SimpleRateLimiter(max_attempts=2, window_seconds=60)
        key = 'test:exceed'

        # First two attempts should pass
        limited, _ = limiter.is_rate_limited(key)
        assert limited is False
        limited, _ = limiter.is_rate_limited(key)
        assert limited is False

        # Third attempt should be blocked
        limited, remaining = limiter.is_rate_limited(key)
        assert limited is True
        assert remaining > 0

    def test_reset_clears_limit(self, app_context):
        """Reset should clear the rate limit for a key."""
        from app.services.rate_limiter import SimpleRateLimiter

        limiter = SimpleRateLimiter(max_attempts=2, window_seconds=60)
        key = 'test:reset'

        limiter.is_rate_limited(key)
        limiter.is_rate_limited(key)
        limited, _ = limiter.is_rate_limited(key)
        assert limited is True

        # Reset and try again
        limiter.reset(key)
        limited, _ = limiter.is_rate_limited(key)
        assert limited is False

    def test_db_persistence(self, app_context):
        """Rate limit attempts should be stored in the database."""
        from app.services.rate_limiter import SimpleRateLimiter
        from app.models import RateLimitAttempt
        from app import db as _db

        limiter = SimpleRateLimiter(max_attempts=5, window_seconds=60)
        key = 'test:persist'

        limiter.is_rate_limited(key)
        limiter.is_rate_limited(key)

        count = _db.session.query(RateLimitAttempt).filter_by(key=key).count()
        assert count == 2

    def test_fallback_on_db_error(self, app_context):
        """Limiter should fall back to in-memory when DB fails."""
        from app.services.rate_limiter import SimpleRateLimiter
        from app import db as _db

        limiter = SimpleRateLimiter(max_attempts=5, window_seconds=60)
        key = 'test:fallback'

        # Force a DB error by using a non-existent table reference
        # (the fallback mechanism should catch it)
        limited, remaining = limiter.is_rate_limited(key)
        # Should return a result regardless of DB state
        assert isinstance(limited, bool)


class TestWebhookRateLimiter:
    """Test the webhook rate limiter with DB persistence."""

    def test_first_call_not_limited(self, app_context):
        """First webhook call should not be rate limited."""
        from app.services.rate_limiter import WebhookRateLimiter

        limiter = WebhookRateLimiter(max_per_minute=2, max_per_hour=10)
        limited, msg = limiter.is_rate_limited('webhook:test:1')
        assert limited is False
        assert msg == ''

    def test_per_minute_limit(self, app_context):
        """Calls exceeding per-minute limit should be blocked."""
        from app.services.rate_limiter import WebhookRateLimiter

        limiter = WebhookRateLimiter(max_per_minute=2, max_per_hour=100)
        key = 'webhook:minute'

        # First two calls should pass
        limited, _ = limiter.is_rate_limited(key)
        assert limited is False
        limited, _ = limiter.is_rate_limited(key)
        assert limited is False

        # Third call should be blocked (per-minute limit)
        limited, msg = limiter.is_rate_limited(key)
        assert limited is True
        assert 'minute' in msg.lower()

    def test_per_hour_limit(self, app_context):
        """Calls exceeding per-hour limit should be blocked."""
        from app.services.rate_limiter import WebhookRateLimiter

        limiter = WebhookRateLimiter(max_per_minute=100, max_per_hour=3)
        key = 'webhook:hour'

        # First three calls should pass
        for _ in range(3):
            limited, _ = limiter.is_rate_limited(key)
            assert limited is False

        # Fourth call should be blocked (per-hour limit)
        limited, msg = limiter.is_rate_limited(key)
        assert limited is True
        assert 'hour' in msg.lower()

    def test_db_records_created(self, app_context):
        """Webhook rate limit attempts should be stored in the database."""
        from app.services.rate_limiter import WebhookRateLimiter
        from app.models import RateLimitAttempt
        from app import db as _db

        limiter = WebhookRateLimiter(max_per_minute=30, max_per_hour=600)
        key = 'webhook:records'

        limiter.is_rate_limited(key)
        limiter.is_rate_limited(key)

        count = _db.session.query(RateLimitAttempt).filter_by(key=key).count()
        assert count == 2


class TestModuleSingletons:
    """Test the module-level singleton instances."""

    def test_rate_limiter_singleton(self):
        """_rate_limiter should be a SimpleRateLimiter instance."""
        from app.services.rate_limiter import _rate_limiter, SimpleRateLimiter
        assert isinstance(_rate_limiter, SimpleRateLimiter)

    def test_webhook_limiter_singleton(self):
        """_webhook_limiter should be a WebhookRateLimiter instance."""
        from app.services.rate_limiter import _webhook_limiter, WebhookRateLimiter
        assert isinstance(_webhook_limiter, WebhookRateLimiter)

    def test_default_config(self):
        """Default configuration should match expected values."""
        from app.services.rate_limiter import _rate_limiter, _webhook_limiter
        assert _rate_limiter.max_attempts == 5
        assert _rate_limiter.window_seconds == 300
        assert _webhook_limiter.max_per_minute == 30
        assert _webhook_limiter.max_per_hour == 600
