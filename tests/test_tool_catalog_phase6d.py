"""Tests fase 6d — recon DNS adicional (fierce)."""

from datetime import datetime, timezone

import pytest

from scraper_agent.security_env.authorization_guard import AuthorizationGuard, load_authorized_targets
from scraper_agent.security_env.categories import ALL_CATEGORIES, DNS_ENUMERATION
from scraper_agent.security_env.exceptions import AuthorizationDenied
from scraper_agent.security_env.kali_runtime import KaliRuntime
from scraper_agent.security_env.models import ToolExecutionRequest
from scraper_agent.security_env.tool_runner import ToolRunner, load_tool_catalog
from conftest import FakeExecutor

FIXTURE_AUTH = __import__("pathlib").Path(__file__).parent / "fixtures" / "authorized_targets_test.yaml"


def test_phase6d_tool_in_catalog() -> None:
    catalog = load_tool_catalog()
    assert "fierce_safe" in catalog
    assert catalog["fierce_safe"].category == DNS_ENUMERATION
    assert catalog["fierce_safe"].category in ALL_CATEGORIES


@pytest.fixture
def runner() -> tuple[ToolRunner, FakeExecutor]:
    guard = AuthorizationGuard(load_authorized_targets(FIXTURE_AUTH))
    catalog = load_tool_catalog()
    executor = FakeExecutor(stdout="phase6d-ok")
    tool_runner = ToolRunner(
        catalog=catalog,
        guard=guard,
        runtime=KaliRuntime(executor),
        audit_log=[],
    )
    return tool_runner, executor


@pytest.mark.asyncio
async def test_reject_fierce_on_passive_only_target(runner: tuple[ToolRunner, FakeExecutor]) -> None:
    tool_runner, executor = runner
    with pytest.raises(AuthorizationDenied, match="categor"):
        await tool_runner.execute(
            ToolExecutionRequest(tool_id="fierce_safe", host="app.allowed.example.com"),
            on=datetime(2026, 7, 6, 12, 0, tzinfo=timezone.utc),
        )
    assert executor.commands == []


@pytest.mark.asyncio
async def test_execute_fierce_argv(runner: tuple[ToolRunner, FakeExecutor]) -> None:
    tool_runner, executor = runner
    host = "full.example.com"
    result = await tool_runner.execute(
        ToolExecutionRequest(tool_id="fierce_safe", host=host, requested_by="tester"),
        on=datetime(2026, 7, 6, 12, 0, tzinfo=timezone.utc),
    )
    assert result.exit_code == 0
    assert executor.commands[-1] == ["fierce", "--domain", host]
