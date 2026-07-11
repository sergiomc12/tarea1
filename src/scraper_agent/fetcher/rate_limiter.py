"""Rate limiting por dominio."""

from aiolimiter import AsyncLimiter


class DomainRateLimiter:
    """Token bucket por host."""

    def __init__(self, requests_per_second: float) -> None:
        rate = max(requests_per_second, 0.1)
        self._limiter = AsyncLimiter(max(rate, 1), time_period=1.0 / rate if rate >= 1 else 1.0)

    async def acquire(self) -> None:
        """Espera hasta poder emitir otra petición."""
        await self._limiter.acquire()
