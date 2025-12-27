"""
Circuit Breaker Pattern Implementation

Prevents cascade failures when external services are down by:
- Failing fast when services are unavailable
- Automatically recovering when services return
- Providing fallback strategies
"""

import time
import logging
import asyncio
from enum import Enum
from typing import Callable, Optional, Any, Dict
from datetime import datetime, timedelta
from collections import deque

logger = logging.getLogger(__name__)


class CircuitState(str, Enum):
    """Circuit breaker states"""
    CLOSED = "closed"      # Normal operation, requests pass through
    OPEN = "open"          # Circuit is open, requests fail immediately
    HALF_OPEN = "half_open"  # Testing if service has recovered


class CircuitOpenError(Exception):
    """Raised when circuit is open and request is blocked"""
    pass


class CircuitBreaker:
    """
    Circuit breaker for protecting external service calls

    States:
    - CLOSED: Normal operation, all requests pass through
    - OPEN: Service is down, fail fast without calling service
    - HALF_OPEN: Testing recovery, limited requests allowed

    Transitions:
    - CLOSED -> OPEN: After failure_threshold consecutive failures
    - OPEN -> HALF_OPEN: After recovery_timeout seconds
    - HALF_OPEN -> CLOSED: After half_open_requests successful calls
    - HALF_OPEN -> OPEN: If any call fails in half-open state
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        half_open_requests: int = 3,
        expected_exception: type = Exception,
        fallback: Optional[Callable] = None
    ):
        """
        Initialize circuit breaker

        Args:
            name: Name of the circuit (e.g., "openai_llm", "slack_api")
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Seconds to wait before attempting recovery
            half_open_requests: Number of successful requests needed to close circuit
            expected_exception: Exception type to catch (default: Exception)
            fallback: Optional fallback function when circuit is open
        """
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_requests = half_open_requests
        self.expected_exception = expected_exception
        self.fallback = fallback

        # State management
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[float] = None
        self.last_state_change: float = time.time()

        # Metrics
        self.total_requests = 0
        self.total_failures = 0
        self.total_successes = 0
        self.total_fallbacks = 0

        # Recent failures for debugging (keep last 10)
        self.recent_failures: deque = deque(maxlen=10)

        logger.info(
            f"Circuit breaker '{name}' initialized: "
            f"threshold={failure_threshold}, timeout={recovery_timeout}s"
        )

    async def execute(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function with circuit breaker protection

        Args:
            func: Async or sync function to execute
            *args, **kwargs: Arguments to pass to function

        Returns:
            Result from function or fallback

        Raises:
            CircuitOpenError: If circuit is open and no fallback provided
        """
        self.total_requests += 1

        # Check if circuit should transition from OPEN to HALF_OPEN
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                logger.info(f"Circuit '{self.name}': Attempting reset (OPEN -> HALF_OPEN)")
                self.state = CircuitState.HALF_OPEN
                self.success_count = 0
                self.last_state_change = time.time()
            else:
                # Circuit is still open, fail fast
                self.total_fallbacks += 1
                time_until_retry = self._time_until_retry()

                logger.warning(
                    f"Circuit '{self.name}': OPEN - failing fast. "
                    f"Retry in {time_until_retry:.1f}s"
                )

                if self.fallback:
                    return await self._execute_fallback(self.fallback, *args, **kwargs)

                raise CircuitOpenError(
                    f"Circuit breaker '{self.name}' is OPEN. "
                    f"Service unavailable. Retry in {time_until_retry:.1f}s"
                )

        # Execute the function
        try:
            # Support both async and sync functions
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)

            # Success - update state
            self._on_success()
            return result

        except self.expected_exception as e:
            # Failure - update state
            self._on_failure(e)

            # If circuit just opened, try fallback
            if self.state == CircuitState.OPEN and self.fallback:
                self.total_fallbacks += 1
                logger.info(f"Circuit '{self.name}': Using fallback after failure")
                return await self._execute_fallback(self.fallback, *args, **kwargs)

            # Re-raise the exception
            raise

    def _on_success(self):
        """Handle successful request"""
        self.total_successes += 1

        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            logger.debug(
                f"Circuit '{self.name}': Success in HALF_OPEN "
                f"({self.success_count}/{self.half_open_requests})"
            )

            # If enough successes, close the circuit
            if self.success_count >= self.half_open_requests:
                logger.info(f"Circuit '{self.name}': Closing circuit (HALF_OPEN -> CLOSED)")
                self.state = CircuitState.CLOSED
                self.failure_count = 0
                self.success_count = 0
                self.last_state_change = time.time()

        elif self.state == CircuitState.CLOSED:
            # Reset failure count on success
            self.failure_count = 0

    def _on_failure(self, exception: Exception):
        """Handle failed request"""
        self.total_failures += 1
        self.failure_count += 1
        self.last_failure_time = time.time()

        # Track recent failures
        self.recent_failures.append({
            "time": datetime.utcnow().isoformat(),
            "exception": str(exception),
            "type": type(exception).__name__
        })

        if self.state == CircuitState.HALF_OPEN:
            # Any failure in half-open state reopens circuit
            logger.warning(
                f"Circuit '{self.name}': Failure in HALF_OPEN, "
                f"reopening circuit (HALF_OPEN -> OPEN)"
            )
            self.state = CircuitState.OPEN
            self.success_count = 0
            self.last_state_change = time.time()

        elif self.state == CircuitState.CLOSED:
            # Check if we've hit the failure threshold
            if self.failure_count >= self.failure_threshold:
                logger.error(
                    f"Circuit '{self.name}': Failure threshold reached "
                    f"({self.failure_count}/{self.failure_threshold}), "
                    f"opening circuit (CLOSED -> OPEN)"
                )
                self.state = CircuitState.OPEN
                self.last_state_change = time.time()

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset"""
        if self.last_failure_time is None:
            return True

        elapsed = time.time() - self.last_failure_time
        return elapsed >= self.recovery_timeout

    def _time_until_retry(self) -> float:
        """Calculate seconds until retry attempt"""
        if self.last_failure_time is None:
            return 0

        elapsed = time.time() - self.last_failure_time
        return max(0, self.recovery_timeout - elapsed)

    async def _execute_fallback(self, fallback: Callable, *args, **kwargs) -> Any:
        """Execute fallback function"""
        try:
            if asyncio.iscoroutinefunction(fallback):
                return await fallback(*args, **kwargs)
            else:
                return fallback(*args, **kwargs)
        except Exception as e:
            logger.error(f"Circuit '{self.name}': Fallback failed: {e}")
            raise

    def get_state(self) -> Dict[str, Any]:
        """Get current circuit breaker state"""
        uptime_seconds = time.time() - self.last_state_change

        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "total_requests": self.total_requests,
            "total_failures": self.total_failures,
            "total_successes": self.total_successes,
            "total_fallbacks": self.total_fallbacks,
            "failure_rate": self.total_failures / self.total_requests if self.total_requests > 0 else 0,
            "state_uptime_seconds": uptime_seconds,
            "time_until_retry": self._time_until_retry() if self.state == CircuitState.OPEN else 0,
            "recent_failures": list(self.recent_failures)
        }

    def reset(self):
        """Manually reset circuit breaker to CLOSED state"""
        logger.info(f"Circuit '{self.name}': Manual reset")
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_state_change = time.time()


class CircuitBreakerRegistry:
    """Global registry for managing multiple circuit breakers"""

    def __init__(self):
        self._breakers: Dict[str, CircuitBreaker] = {}

    def register(self, circuit_breaker: CircuitBreaker):
        """Register a circuit breaker"""
        self._breakers[circuit_breaker.name] = circuit_breaker
        logger.info(f"Registered circuit breaker: {circuit_breaker.name}")

    def get(self, name: str) -> Optional[CircuitBreaker]:
        """Get circuit breaker by name"""
        return self._breakers.get(name)

    def get_or_create(
        self,
        name: str,
        **kwargs
    ) -> CircuitBreaker:
        """Get existing circuit breaker or create new one"""
        if name not in self._breakers:
            breaker = CircuitBreaker(name=name, **kwargs)
            self.register(breaker)
        return self._breakers[name]

    def get_all_states(self) -> Dict[str, Dict[str, Any]]:
        """Get state of all circuit breakers"""
        return {
            name: breaker.get_state()
            for name, breaker in self._breakers.items()
        }

    def reset_all(self):
        """Reset all circuit breakers"""
        for breaker in self._breakers.values():
            breaker.reset()
        logger.info("All circuit breakers reset")


# Global circuit breaker registry
circuit_breaker_registry = CircuitBreakerRegistry()

