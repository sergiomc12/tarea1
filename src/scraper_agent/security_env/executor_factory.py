"""Selección de ejecutor Kali según entorno (local vs Docker)."""

from __future__ import annotations

import os

from scraper_agent.security_env.docker_executor import DockerCliExecutor
from scraper_agent.security_env.fake_executor import FakeExecutor
from scraper_agent.security_env.kali_runtime import CommandExecutor


def resolve_command_executor() -> CommandExecutor:
    container = os.environ.get("KALI_CONTAINER", "").strip()
    if container:
        docker_bin = os.environ.get("DOCKER_BIN", "docker")
        return DockerCliExecutor(container, docker_bin=docker_bin)
    return FakeExecutor()
