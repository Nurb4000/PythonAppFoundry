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


_rate_limiter = SimpleRateLimiter(max_attempts=5, window_seconds=300)
