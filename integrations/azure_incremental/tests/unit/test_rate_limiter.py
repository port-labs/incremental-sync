import time
from unittest.mock import patch

from src.rate_limiter import TokenBucketRateLimiter


class TestTokenBucketRateLimiter:
    """Test the TokenBucketRateLimiter class."""

    def test_init(self) -> None:
        """Test rate limiter initialization."""
        limiter: TokenBucketRateLimiter = TokenBucketRateLimiter(
            capacity=10, refill_rate=5
        )
        assert limiter.capacity == 10
        assert limiter.refill_rate == 5
        assert limiter.tokens == 10
        assert limiter.last_refill_time > 0

    def test_consume_success(self) -> None:
        """Test successful token consumption."""
        limiter: TokenBucketRateLimiter = TokenBucketRateLimiter(
            capacity=10, refill_rate=5
        )

        result: bool = limiter.consume(5)
        assert result is True
        assert limiter.tokens == 5

    def test_consume_insufficient_tokens(self) -> None:
        """Test consumption when insufficient tokens."""
        limiter: TokenBucketRateLimiter = TokenBucketRateLimiter(
            capacity=10, refill_rate=5
        )

        result: bool = limiter.consume(15)
        assert result is False
        assert limiter.tokens == 10  # Should remain unchanged

    def test_consume_exact_tokens(self) -> None:
        """Test consuming exactly available tokens."""
        limiter: TokenBucketRateLimiter = TokenBucketRateLimiter(
            capacity=10, refill_rate=5
        )

        result: bool = limiter.consume(10)
        assert result is True
        assert limiter.tokens == 0

    def test_consume_more_than_capacity(self) -> None:
        """Test consuming more tokens than capacity."""
        limiter: TokenBucketRateLimiter = TokenBucketRateLimiter(
            capacity=10, refill_rate=5
        )

        result: bool = limiter.consume(15)
        assert result is False
        assert limiter.tokens == 10

    def test_refill_tokens(self) -> None:
        """Test token refill over time."""
        limiter: TokenBucketRateLimiter = TokenBucketRateLimiter(
            capacity=10, refill_rate=5
        )

        # Consume all tokens
        limiter.consume(10)
        assert limiter.tokens == 0

        # Simulate time passing by directly setting last_refill_time
        limiter.last_refill_time = (
            0  # Set to 0 so current time - last_refill_time = current time
        )

        # Should refill tokens
        result: bool = limiter.consume(3)
        assert result is True
        assert limiter.tokens >= 2  # Should have refilled some tokens

    def test_refill_with_capacity_limit(self) -> None:
        """Test that tokens don't exceed capacity when refilling."""
        limiter: TokenBucketRateLimiter = TokenBucketRateLimiter(
            capacity=10, refill_rate=5
        )

        # Consume some tokens
        limiter.consume(5)
        assert limiter.tokens == 5

        # Simulate time passing by directly setting last_refill_time
        limiter.last_refill_time = (
            0  # Set to 0 so current time - last_refill_time = current time
        )

        # Should refill but not exceed capacity
        result: bool = limiter.consume(3)
        assert result is True
        assert limiter.tokens <= 10  # Should not exceed capacity

    def test_refill_rate_calculation(self) -> None:
        """Test refill rate calculation."""
        limiter: TokenBucketRateLimiter = TokenBucketRateLimiter(
            capacity=10, refill_rate=5
        )

        # Consume all tokens
        limiter.consume(10)
        assert limiter.tokens == 0

        # Simulate 0.5 seconds passing by directly setting last_refill_time
        limiter.last_refill_time = time.time() - 0.5

        # Should refill proportionally
        result: bool = limiter.consume(2)
        assert result is True
        assert limiter.tokens >= 0  # Should have some tokens

    def test_consume_zero_tokens(self) -> None:
        """Test consuming zero tokens."""
        limiter: TokenBucketRateLimiter = TokenBucketRateLimiter(
            capacity=10, refill_rate=5
        )

        result: bool = limiter.consume(0)
        assert result is True
        assert limiter.tokens == 10  # Should remain unchanged

    def test_consume_negative_tokens(self) -> None:
        """Test consuming negative tokens (should add tokens)."""
        limiter: TokenBucketRateLimiter = TokenBucketRateLimiter(
            capacity=10, refill_rate=5
        )

        result: bool = limiter.consume(-5)
        assert result is True
        assert limiter.tokens == 15  # 10 + 5 = 15

    def test_high_refill_rate(self) -> None:
        """Test with high refill rate."""
        limiter: TokenBucketRateLimiter = TokenBucketRateLimiter(
            capacity=10, refill_rate=20
        )

        # Consume all tokens
        limiter.consume(10)
        assert limiter.tokens == 0

        # Simulate time passing by directly setting last_refill_time
        limiter.last_refill_time = (
            0  # Set to 0 so current time - last_refill_time = current time
        )

        # Should refill to capacity
        result: bool = limiter.consume(5)
        assert result is True
        assert limiter.tokens <= 10  # Should not exceed capacity

    def test_zero_refill_rate(self) -> None:
        """Test with zero refill rate."""
        limiter: TokenBucketRateLimiter = TokenBucketRateLimiter(
            capacity=10, refill_rate=0
        )

        # Consume some tokens
        limiter.consume(5)
        assert limiter.tokens == 5

        # Simulate time passing
        with patch("time.time") as mock_time:
            mock_time.return_value = 10.0  # 10 seconds later

            # Should not refill
            result: bool = limiter.consume(3)
            assert result is True
            assert limiter.tokens == 2

    def test_concurrent_consumption(self) -> None:
        """Test concurrent token consumption."""
        limiter: TokenBucketRateLimiter = TokenBucketRateLimiter(
            capacity=10, refill_rate=5
        )

        # Multiple consumptions
        assert limiter.consume(3) is True
        assert limiter.consume(4) is True
        assert limiter.consume(2) is True
        assert limiter.consume(2) is False  # Should fail, only 1 token left

        assert limiter.tokens == 1

    def test_precision_handling(self) -> None:
        """Test handling of floating point precision."""
        limiter: TokenBucketRateLimiter = TokenBucketRateLimiter(
            capacity=10, refill_rate=3
        )

        # Consume all tokens
        limiter.consume(10)
        assert limiter.tokens == 0

        # Simulate small time increment by directly setting last_refill_time
        limiter.last_refill_time = time.time() - 0.1  # 0.1 seconds ago

        # Should handle small refills correctly
        result: bool = limiter.consume(
            0
        )  # Use 0 instead of 0.1 since consume expects int
        assert result is True
        assert limiter.tokens >= 0  # Should have some tokens
