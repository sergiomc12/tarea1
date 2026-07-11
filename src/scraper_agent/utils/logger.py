"""Configuración de logging estructurado."""

import logging
import sys
from typing import Any

import structlog


def setup_logging(level: str = "INFO") -> None:
    """Configura structlog + logging estándar."""
    log_level = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=log_level)

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
    )


def get_logger(name: str) -> Any:
    """Retorna un logger estructurado."""
    return structlog.get_logger(name)
