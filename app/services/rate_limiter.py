"""DB-backed rate limiter with graceful in-memory fallback.

Replaces the previous pure in-memory implementation so that rate limits are
enforced consistently across multiple Gunicorn workers / Docker replicas.
When the database is temporarily unavailable the limiter falls back to
in-memory tracking (same behaviour as before) and logs a warning.
"""
import logging
import time
from collections import defaultdict

logger = logging.getLogger(__name__)


class SimpleRateLimiter:
    """Rate limiter for auth endpoints with DB persistence.

    Parameters
    ----------
    max_attempts : int
        Maximum number of attempts allowed within the window.
    window_seconds : int
        Time window in seconds.
    """

    def __init__(self, max_attempts=5, window_seconds=300):
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        # In-memory fallback (used when DB is unavailable)
        self._fallback = defaultdict(list)

    def _check_db(self, key):
        """Check rate limit against the database."""
        from app import db as _db
        from app.models import RateLimitAttempt
        from sqlalchemy import text

        now = time.time()
        window_start = now - self.window_seconds

        try:
            # Count attempts within the window
            result = _db.session.execute(
                text(
                    'SELECT COUNT(*) FROM rate_limit_attempts '
                    'WHERE key = :key AND timestamp > :window_start'
                ),
                {'key': key, 'window_start': window_start},
            )
            count = result.scalar()

            # Clean up old attempts (older than window)
            _db.session.execute(
                text(
                    'DELETE FROM rate_limit_attempts '
                    'WHERE key = :key AND timestamp <= :window_start'
                ),
                {'key': key, 'window_start': window_start},
            )

            if count >= self.max_attempts:
                # Get the oldest attempt in the window to calculate remaining time
                oldest_result = _db.session.execute(
                    text(
                        'SELECT MIN(timestamp) FROM rate_limit_attempts '
                        'WHERE key = :key AND timestamp > :window_start'
                    ),
                    {'key': key, 'window_start': window_start},
                )
                oldest = oldest_result.scalar()
                remaining = self.window_seconds - (now - oldest) if oldest else self.window_seconds
                _db.session.commit()
                return True, max(0, remaining)

            # Record this attempt
            attempt = RateLimitAttempt(key=key, timestamp=now)
            _db.session.add(attempt)
            _db.session.commit()
            return False, 0

        except Exception as e:
            logger.warning(f'DB rate limiter fallback for "{key}": {e}')
            try:
                _db.session.rollback()
            except Exception:
                pass
            # Fall through to in-memory fallback
            return None, None

    def is_rate_limited(self, key):
        """Check if the given key is rate limited.

        Returns
        -------
        tuple[bool, float | int]
            (is_limited, remaining_seconds_or_0)
        """
        now = time.time()

        # Try DB first
        limited, remaining = self._check_db(key)
        if limited is not None:
            return limited, remaining

        # In-memory fallback
        self._fallback[key] = [
            t for t in self._fallback[key] if now - t < self.window_seconds
        ]

        if len(self._fallback[key]) >= self.max_attempts:
            return True, self.window_seconds - (now - self._fallback[key][0])

        self._fallback[key].append(now)
        return False, 0

    def reset(self, key):
        """Reset rate limit for a key."""
        # Reset in-memory fallback
        self._fallback[key] = []

        # Reset in DB
        try:
            from app import db as _db
            from sqlalchemy import text
            _db.session.execute(
                text('DELETE FROM rate_limit_attempts WHERE key = :key'),
                {'key': key},
            )
            _db.session.commit()
        except Exception as e:
            logger.debug(f'DB rate limiter reset for "{key}": {e}')


class WebhookRateLimiter:
    """Rate limiter for webhook endpoints with DB persistence.

    Enforces both per-minute and per-hour limits.

    Parameters
    ----------
    max_per_minute : int
        Maximum calls allowed per minute.
    max_per_hour : int
        Maximum calls allowed per hour.
    """

    def __init__(self, max_per_minute=30, max_per_hour=600):
        self.max_per_minute = max_per_minute
        self.max_per_hour = max_per_hour
        # In-memory fallback
        self._fallback_recent = defaultdict(list)
        self._fallback_hourly = defaultdict(list)

    def _check_db(self, key):
        """Check webhook rate limit against the database."""
        from app import db as _db
        from app.models import RateLimitAttempt
        from sqlalchemy import text

        now = time.time()
        minute_start = now - 60
        hour_start = now - 3600

        try:
            # Count attempts in the last minute
            minute_result = _db.session.execute(
                text(
                    'SELECT COUNT(*) FROM rate_limit_attempts '
                    'WHERE key = :key AND timestamp > :minute_start'
                ),
                {'key': key, 'minute_start': minute_start},
            )
            minute_count = minute_result.scalar()

            # Count attempts in the last hour
            hour_result = _db.session.execute(
                text(
                    'SELECT COUNT(*) FROM rate_limit_attempts '
                    'WHERE key = :key AND timestamp > :hour_start'
                ),
                {'key': key, 'hour_start': hour_start},
            )
            hour_count = hour_result.scalar()

            # Clean up old attempts (older than 1 hour)
            _db.session.execute(
                text(
                    'DELETE FROM rate_limit_attempts '
                    'WHERE key = :key AND timestamp <= :hour_start'
                ),
                {'key': key, 'hour_start': hour_start},
            )

            if minute_count >= self.max_per_minute:
                _db.session.commit()
                return True, 'Too many webhook calls per minute. Try again later.'
            if hour_count >= self.max_per_hour:
                _db.session.commit()
                return True, 'Too many webhook calls per hour. Try again later.'

            # Record this attempt
            attempt = RateLimitAttempt(key=key, timestamp=now)
            _db.session.add(attempt)
            _db.session.commit()
            return False, ''

        except Exception as e:
            logger.warning(f'DB webhook rate limiter fallback for "{key}": {e}')
            try:
                _db.session.rollback()
            except Exception:
                pass
            return None, None

    def is_rate_limited(self, key):
        """Check if the given webhook key is rate limited.

        Returns
        -------
        tuple[bool, str]
            (is_limited, message_or_empty_string)
        """
        now = time.time()

        # Try DB first
        limited, msg = self._check_db(key)
        if limited is not None:
            return limited, msg

        # In-memory fallback
        self._fallback_recent[key] = [
            t for t in self._fallback_recent[key] if now - t < 60
        ]
        self._fallback_hourly[key] = [
            t for t in self._fallback_hourly[key] if now - t < 3600
        ]

        if len(self._fallback_recent[key]) >= self.max_per_minute:
            return True, 'Too many webhook calls per minute. Try again later.'
        if len(self._fallback_hourly[key]) >= self.max_per_hour:
            return True, 'Too many webhook calls per hour. Try again later.'

        self._fallback_recent[key].append(now)
        self._fallback_hourly[key].append(now)
        return False, ''


# Module-level singleton instances (backwards-compatible imports)
_rate_limiter = SimpleRateLimiter(max_attempts=5, window_seconds=300)
_webhook_limiter = WebhookRateLimiter(max_per_minute=30, max_per_hour=600)
