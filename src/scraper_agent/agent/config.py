"""Configuración del cliente DeepSeek (variables de entorno)."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class DeepSeekSettings:
    """Credenciales y endpoint — nunca hardcodear en código."""

    api_key: str
    base_url: str = "https://api.deepseek.com"
    model: str = "deepseek-chat"
    timeout_seconds: float = 120.0

    @classmethod
    def from_env(cls) -> DeepSeekSettings:
        api_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
        if not api_key:
            raise ValueError("DEEPSEEK_API_KEY no configurada")
        return cls(
            api_key=api_key,
            base_url=os.environ.get("DEEPSEEK_API_URL", "https://api.deepseek.com").rstrip("/"),
            model=os.environ.get("DEEPSEEK_MODEL", "deepseek-chat"),
            timeout_seconds=float(os.environ.get("DEEPSEEK_TIMEOUT_SECONDS", "120")),
        )

    @classmethod
    def from_env_optional(cls) -> DeepSeekSettings | None:
        api_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
        if not api_key:
            return None
        return cls.from_env()
