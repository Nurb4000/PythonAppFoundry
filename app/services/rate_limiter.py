import time
from collections import defaultdict


class SimpleRateLimiter:
    """In-memory rate limiter for auth endpoints."""
    
    def __init__(self, max_attempts=5, window_seconds=300):
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self.attempts = defaultdict(list)
    
    def is_rate_limited(self, key):
        now = time.time()
        # Clean old attempts outside the window
        self.attempts[key] = [t for t in self.attempts[key] if now - t < self.window_seconds]
        
        if len(self.attempts[key]) >= self.max_attempts:
            return True, self.window_seconds - (now - self.attempts[key][0])
        
        self.attempts[key].append(now)
        return False, 0
    
    def reset(self, key):
        self.attempts[key] = []


class WebhookRateLimiter:
    """Rate limiter for webhook endpoints — stricter limits per slug."""
    
    def __init__(self, max_per_minute=30, max_per_hour=600):
        self.max_per_minute = max_per_minute
        self.max_per_hour = max_per_hour
        self.recent = defaultdict(list)
        self.hourly = defaultdict(list)
    
    def is_rate_limited(self, key):
        now = time.time()
        # Clean old entries
        self.recent[key] = [t for t in self.recent[key] if now - t < 60]
        self.hourly[key] = [t for t in self.hourly[key] if now - t < 3600]
        
        if len(self.recent[key]) >= self.max_per_minute:
            return True, 'Too many webhook calls per minute. Try again later.'
        if len(self.hourly[key]) >= self.max_per_hour:
            return True, 'Too many webhook calls per hour. Try again later.'
        
        self.recent[key].append(now)
        self.hourly[key].append(now)
        return False, ''


_rate_limiter = SimpleRateLimiter(max_attempts=5, window_seconds=300)
_webhook_limiter = WebhookRateLimiter(max_per_minute=30, max_per_hour=600)
