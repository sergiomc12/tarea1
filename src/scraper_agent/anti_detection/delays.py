"""Delays aleatorios entre peticiones."""

import asyncio
import random


async def random_delay(min_seconds: float, max_seconds: float) -> None:
    """Espera un intervalo aleatorio uniforme."""
    if max_seconds <= 0:
        return
    delay = random.uniform(min_seconds, max_seconds)
    await asyncio.sleep(delay)
