"""Ejecuta herramientas dentro del contenedor Kali vía docker exec."""

from __future__ import annotations

import asyncio
import time

from scraper_agent.security_env.models import CommandResult


class DockerCliExecutor:
    """Puerto CommandExecutor que delega en `docker exec` (compose ítem 13)."""

    def __init__(self, container_name: str, *, docker_bin: str = "docker") -> None:
        self._container = container_name
        self._docker_bin = docker_bin

    async def run(
        self,
        argv: list[str],
        *,
        timeout_seconds: int,
        cwd: str | None = None,
    ) -> CommandResult:
        if not argv:
            raise ValueError("argv vacio")
        if cwd:
            await self._ensure_workdir(cwd, timeout_seconds=min(timeout_seconds, 30))
        cmd = [self._docker_bin, "exec"]
        if cwd:
            cmd.extend(["-w", cwd])
        cmd.extend([self._container, *argv])
        started = time.perf_counter()
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout_b, stderr_b = await asyncio.wait_for(
                proc.communicate(),
                timeout=timeout_seconds,
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.communicate()
            return CommandResult(
                argv=argv,
                stdout="",
                stderr="timeout",
                exit_code=124,
                duration_ms=int((time.perf_counter() - started) * 1000),
            )
        duration_ms = int((time.perf_counter() - started) * 1000)
        return CommandResult(
            argv=argv,
            stdout=stdout_b.decode("utf-8", errors="replace"),
            stderr=stderr_b.decode("utf-8", errors="replace"),
            exit_code=proc.returncode or 0,
            duration_ms=duration_ms,
        )

    async def _ensure_workdir(self, cwd: str, *, timeout_seconds: int) -> None:
        proc = await asyncio.create_subprocess_exec(
            self._docker_bin,
            "exec",
            self._container,
            "mkdir",
            "-p",
            cwd,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            _, stderr_b = await asyncio.wait_for(proc.communicate(), timeout=timeout_seconds)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.communicate()
            raise RuntimeError(f"timeout creando workspace en contenedor: {cwd}") from None
        if proc.returncode != 0:
            detail = stderr_b.decode("utf-8", errors="replace").strip()
            raise RuntimeError(f"no se pudo crear workspace {cwd!r}: {detail}")
