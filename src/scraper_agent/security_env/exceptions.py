"""Excepciones de la capa security_env."""

from __future__ import annotations


class SecurityEnvError(Exception):
    """Base para errores de security_env."""


class AuthorizationDenied(SecurityEnvError):
    """Objetivo o categoría no autorizados."""


class ToolNotFound(SecurityEnvError):
    """Herramienta ausente del catálogo cerrado."""


class InvalidToolParams(SecurityEnvError):
    """Parámetros inválidos para una herramienta del catálogo."""


class PolicyViolation(SecurityEnvError):
    """Violación de política del runtime Kali (egress, filesystem)."""
