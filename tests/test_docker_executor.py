"""Tests de DockerCliExecutor."""

import asyncio

import pytest

from scraper_agent.security_env.docker_executor import DockerCliExecutor
from scraper_agent.security_env.executor_factory import resolve_command_executor


@pytest.mark.asyncio
async def test_docker_cli_executor_creates_workdir_before_exec(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple] = []
    real_exec = asyncio.create_subprocess_exec

    async def fake_exec(*cmd, **kwargs):
        calls.append(cmd)
        return await real_exec(
            "python",
            "-c",
            "import sys; sys.stdout.write('ok')",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)
    executor = DockerCliExecutor("kali-tools", docker_bin="docker")
    result = await executor.run(
        ["whois", "example.com"],
        timeout_seconds=30,
        cwd="/tmp/session-abc",
    )
    assert result.stdout == "ok"
    assert len(calls) == 2
    assert calls[0] == ("docker", "exec", "kali-tools", "mkdir", "-p", "/tmp/session-abc")
    assert calls[1][:4] == ("docker", "exec", "-w", "/tmp/session-abc")


@pytest.mark.asyncio
async def test_docker_cli_executor_invokes_docker_exec(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict = {}
    real_exec = asyncio.create_subprocess_exec

    async def fake_exec(*cmd, **kwargs):
        captured["cmd"] = cmd
        return await real_exec(
            "python",
            "-c",
            "import sys; sys.stdout.write('whois-data')",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)
    executor = DockerCliExecutor("kali-tools", docker_bin="docker")
    result = await executor.run(["whois", "example.com"], timeout_seconds=30)
    assert captured["cmd"][0] == "docker"
    assert captured["cmd"][1] == "exec"
    assert captured["cmd"][2] == "kali-tools"
    assert captured["cmd"][3] == "whois"
    assert result.stdout == "whois-data"


def test_resolve_executor_uses_docker_when_env_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KALI_CONTAINER", "kali-tools")
    executor = resolve_command_executor()
    assert executor.__class__.__name__ == "DockerCliExecutor"


def test_resolve_executor_fake_without_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("KALI_CONTAINER", raising=False)
    executor = resolve_command_executor()
    assert executor.__class__.__name__ == "FakeExecutor"
