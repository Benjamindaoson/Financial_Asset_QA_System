"""Tests for rate limiter."""
import time
import pytest
from app.market.rate_limiter import RateLimiter


def test_rate_limiter_allows_calls_under_limit():
    """Test that calls under the limit are allowed."""
    limiter = RateLimiter(max_calls=3, time_window=1)

    assert limiter.is_allowed("test_key") is True
    assert limiter.is_allowed("test_key") is True
    assert limiter.is_allowed("test_key") is True


def test_rate_limiter_blocks_calls_over_limit():
    """Test that calls over the limit are blocked."""
    limiter = RateLimiter(max_calls=2, time_window=1)

    assert limiter.is_allowed("test_key") is True
    assert limiter.is_allowed("test_key") is True
    assert limiter.is_allowed("test_key") is False


def test_rate_limiter_resets_after_time_window():
    """Test that rate limiter resets after time window."""
    limiter = RateLimiter(max_calls=2, time_window=1)

    assert limiter.is_allowed("test_key") is True
    assert limiter.is_allowed("test_key") is True
    assert limiter.is_allowed("test_key") is False

    # Wait for time window to expire
    time.sleep(1.1)

    assert limiter.is_allowed("test_key") is True


def test_rate_limiter_separate_keys():
    """Test that different keys have separate limits."""
    limiter = RateLimiter(max_calls=2, time_window=1)

    assert limiter.is_allowed("key1") is True
    assert limiter.is_allowed("key1") is True
    assert limiter.is_allowed("key1") is False

    # Different key should still be allowed
    assert limiter.is_allowed("key2") is True
    assert limiter.is_allowed("key2") is True


def test_rate_limiter_get_wait_time():
    """Test wait time calculation."""
    limiter = RateLimiter(max_calls=2, time_window=2)

    limiter.is_allowed("test_key")
    limiter.is_allowed("test_key")

    wait_time = limiter.get_wait_time("test_key")
    assert wait_time is not None
    assert 1.5 < wait_time <= 2.0
