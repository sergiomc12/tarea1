"""Tests de kali_runtime — políticas de workspace y egress."""

import pytest

from scraper_agent.security_env.exceptions import PolicyViolation
from scraper_agent.security_env.kali_runtime import KaliRuntime
from scraper_agent.security_env.models import KaliRuntimeSettings
from conftest import FakeExecutor


@pytest.fixture
def runtime() -> KaliRuntime:
    return KaliRuntime(FakeExecutor(), KaliRuntimeSettings(workspace_root="/tmp"))


def test_validate_write_inside_workspace(runtime: KaliRuntime) -> None:
    session = runtime.create_session("sess-1", frozenset({"allowed.example.com"}))
    path = session.validate_write_path("/tmp/sess-1/report.txt")
    assert path == "/tmp/sess-1/report.txt"


def test_reject_write_outside_workspace(runtime: KaliRuntime) -> None:
    session = runtime.create_session("sess-1", frozenset({"allowed.example.com"}))
    with pytest.raises(PolicyViolation, match="escritura fuera"):
        session.validate_write_path("/etc/passwd")


def test_reject_invalid_session_id(runtime: KaliRuntime) -> None:
    with pytest.raises(PolicyViolation, match="session_id"):
        runtime.create_session("../evil", frozenset({"allowed.example.com"}))


@pytest.mark.asyncio
async def test_reject_egress_to_unlisted_host(runtime: KaliRuntime) -> None:
    session = runtime.create_session("sess-1", frozenset({"allowed.example.com"}))
    with pytest.raises(PolicyViolation, match="egress"):
        await session.exec(
            ["whois", "evil.example.com"],
            target_host="evil.example.com",
            timeout_seconds=30,
        )


@pytest.mark.asyncio
async def test_exec_allowed_host_records_command(runtime: KaliRuntime) -> None:
    executor = FakeExecutor(stdout="whois data")
    runtime = KaliRuntime(executor, KaliRuntimeSettings(workspace_root="/tmp"))
    session = runtime.create_session("sess-1", frozenset({"allowed.example.com"}))
    result = await session.exec(
        ["whois", "allowed.example.com"],
        target_host="allowed.example.com",
        timeout_seconds=30,
    )
    assert result.stdout == "whois data"
    assert executor.commands == [["whois", "allowed.example.com"]]
