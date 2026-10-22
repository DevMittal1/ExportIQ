"""Rate limiting and retry policy middleware."""

import asyncio
import time
from typing import Callable, Dict


class RateLimitRetryMiddleware:
    """Token bucket rate limiter and backoff manager for API clients."""
    
    def __init__(self, requests_per_second: float = 2.0):
        self.interval = 1.0 / requests_per_second
        self.last_time = 0.0
        self._lock = asyncio.Lock()
        
    async def acquire(self):
        """Acquire permission to make an outbound request."""
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self.last_time
            if elapsed < self.interval:
                await asyncio.sleep(self.interval - elapsed)
            self.last_time = time.monotonic()
