"""Ejecutor simulado para desarrollo y tests (sin contenedor Docker)."""

from __future__ import annotations

from dataclasses import dataclass, field

from scraper_agent.security_env.models import CommandResult


@dataclass
class FakeExecutor:
    """Registra argv ejecutados y devuelve salida configurable."""

    stdout: str = "ok"
    stderr: str = ""
    exit_code: int = 0
    commands: list[list[str]] = field(default_factory=list)

    async def run(
        self,
        argv: list[str],
        *,
        timeout_seconds: int,
        cwd: str | None = None,
    ) -> CommandResult:
        self.commands.append(list(argv))
        return CommandResult(
            argv=argv,
            stdout=self.stdout,
            stderr=self.stderr,
            exit_code=self.exit_code,
        )
