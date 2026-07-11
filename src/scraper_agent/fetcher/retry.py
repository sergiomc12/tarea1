"""Reintentos con backoff exponencial."""

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)


def is_retryable_status(status_code: int) -> bool:
    """Determina si un código HTTP amerita reintento."""
    return status_code == 429 or 500 <= status_code < 600


def build_retry_decorator(max_attempts: int, backoff_factor: float):
    """Factory del decorador tenacity para fetch."""
    return retry(
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError, httpx.RemoteProtocolError)),
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential_jitter(initial=backoff_factor, max=60),
        reraise=True,
    )
