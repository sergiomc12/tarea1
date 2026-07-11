"""Runtime Kali endurecido (ejecutor inyectable; Docker en integración futura)."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from scraper_agent.security_env.exceptions import PolicyViolation
from scraper_agent.security_env.models import CommandResult, KaliRuntimeSettings


class CommandExecutor(Protocol):
    """Puerto para ejecutar argv en el entorno Kali (real o simulado)."""

    async def run(
        self,
        argv: list[str],
        *,
        timeout_seconds: int,
        cwd: str | None = None,
    ) -> CommandResult: ...


@dataclass
class KaliSession:
    """Sesión acotada con allowlist de hosts y workspace writable."""

    session_id: str
    allowed_hosts: frozenset[str]
    settings: KaliRuntimeSettings
    executor: CommandExecutor
    write_log: list[str] = field(default_factory=list)

    @property
    def workspace_dir(self) -> str:
        return f"{self.settings.workspace_root}/{self.session_id}"

    def validate_write_path(self, path: str) -> str:
        """Solo permite escritura bajo /tmp/<session_id>/."""
        normalized = str(Path(path).as_posix())
        prefix = f"{self.workspace_dir}/"
        if normalized == self.workspace_dir.rstrip("/") or normalized.startswith(prefix):
            self.write_log.append(normalized)
            return normalized
        raise PolicyViolation(f"escritura fuera de workspace permitido: {path}")

    def assert_host_allowed(self, host: str) -> None:
        if host not in self.allowed_hosts:
            raise PolicyViolation(f"egress no permitido hacia host: {host}")

    async def exec(
        self,
        argv: list[str],
        *,
        target_host: str,
        timeout_seconds: int,
    ) -> CommandResult:
        self.assert_host_allowed(target_host)
        effective_timeout = min(timeout_seconds, self.settings.max_runtime_seconds)
        started = time.perf_counter()
        result = await self.executor.run(
            argv,
            timeout_seconds=effective_timeout,
            cwd=self.workspace_dir,
        )
        duration_ms = int((time.perf_counter() - started) * 1000)
        stdout = _truncate(result.stdout, self.settings.max_output_bytes)
        stderr = _truncate(result.stderr, self.settings.max_output_bytes)
        return CommandResult(
            argv=argv,
            stdout=stdout,
            stderr=stderr,
            exit_code=result.exit_code,
            duration_ms=duration_ms,
        )


class KaliRuntime:
    """Gestiona sesiones endurecidas contra un CommandExecutor."""

    def __init__(
        self,
        executor: CommandExecutor,
        settings: KaliRuntimeSettings | None = None,
    ) -> None:
        self._executor = executor
        self._settings = settings or KaliRuntimeSettings()

    def create_session(self, session_id: str, allowed_hosts: frozenset[str]) -> KaliSession:
        if not session_id or "/" in session_id or ".." in session_id:
            raise PolicyViolation("session_id invalido")
        return KaliSession(
            session_id=session_id,
            allowed_hosts=allowed_hosts,
            settings=self._settings,
            executor=self._executor,
        )


def _truncate(text: str, max_bytes: int) -> str:
    encoded = text.encode("utf-8", errors="replace")
    if len(encoded) <= max_bytes:
        return text
    return encoded[:max_bytes].decode("utf-8", errors="ignore")
