"""
Rate Limiting for ADAPT-Agents API

Simple in-memory rate limiter (will be enhanced with Redis support in future)
"""

import time
from collections import defaultdict
from typing import Dict, List


class RateLimiter:
    """Simple in-memory rate limiter"""

    def __init__(self, requests_per_window: int = 100, window_seconds: int = 60):
        self.requests: Dict[str, List[float]] = defaultdict(list)
        self.requests_per_window = requests_per_window
        self.window_seconds = window_seconds

    def is_allowed(self, api_key: str) -> bool:
        """Check if request is allowed under rate limit"""
        now = time.time()

        # Clean old requests
        self.requests[api_key] = [
            req_time for req_time in self.requests[api_key]
            if now - req_time < self.window_seconds
        ]

        # Check limit
        if len(self.requests[api_key]) >= self.requests_per_window:
            return False

        # Add new request
        self.requests[api_key].append(now)
        return True

    def get_remaining(self, api_key: str) -> int:
        """Get remaining requests in current window"""
        now = time.time()
        active_requests = [
            req_time for req_time in self.requests[api_key]
            if now - req_time < self.window_seconds
        ]
        return max(0, self.requests_per_window - len(active_requests))


# Global rate limiter instance
rate_limiter = RateLimiter()

