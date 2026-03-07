"""Rate limiter for API calls."""
import time
from collections import defaultdict
from typing import Dict, Optional


class RateLimiter:
    """Simple rate limiter using token bucket algorithm."""

    def __init__(self, max_calls: int, time_window: int):
        """
        Initialize rate limiter.

        Args:
            max_calls: Maximum number of calls allowed
            time_window: Time window in seconds
        """
        self.max_calls = max_calls
        self.time_window = time_window
        self.calls: Dict[str, list] = defaultdict(list)

    def is_allowed(self, key: str) -> bool:
        """
        Check if a call is allowed for the given key.

        Args:
            key: Identifier for rate limiting (e.g., API name, user ID)

        Returns:
            True if call is allowed, False otherwise
        """
        now = time.time()

        # Remove old calls outside the time window
        self.calls[key] = [
            call_time for call_time in self.calls[key]
            if now - call_time < self.time_window
        ]

        # Check if we're under the limit
        if len(self.calls[key]) < self.max_calls:
            self.calls[key].append(now)
            return True

        return False

    def get_wait_time(self, key: str) -> Optional[float]:
        """
        Get time to wait before next call is allowed.

        Args:
            key: Identifier for rate limiting

        Returns:
            Seconds to wait, or None if call is allowed now
        """
        if self.is_allowed(key):
            # Remove the call we just added for checking
            self.calls[key].pop()
            return None

        if not self.calls[key]:
            return None

        # Time until oldest call expires
        now = time.time()
        oldest_call = self.calls[key][0]
        wait_time = self.time_window - (now - oldest_call)

        return max(0, wait_time)
