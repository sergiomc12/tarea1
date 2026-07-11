"""Tests fase 6a — escaneo de puertos ampliado (zmap, unicornscan)."""

from datetime import datetime, timezone

import pytest

from scraper_agent.security_env.authorization_guard import AuthorizationGuard, load_authorized_targets
from scraper_agent.security_env.categories import ACTIVE_SCANNING, ALL_CATEGORIES
from scraper_agent.security_env.exceptions import AuthorizationDenied
from scraper_agent.security_env.kali_runtime import KaliRuntime
from scraper_agent.security_env.models import ToolExecutionRequest
from scraper_agent.security_env.tool_runner import ToolRunner, load_tool_catalog
from conftest import FakeExecutor

FIXTURE_AUTH = __import__("pathlib").Path(__file__).parent / "fixtures" / "authorized_targets_test.yaml"

PHASE6A_TOOL_IDS = frozenset({"zmap_safe", "unicornscan_safe"})


def test_phase6a_tools_in_catalog() -> None:
    catalog = load_tool_catalog()
    assert PHASE6A_TOOL_IDS <= set(catalog)
    for tool_id in PHASE6A_TOOL_IDS:
        assert catalog[tool_id].category == ACTIVE_SCANNING
        assert catalog[tool_id].category in ALL_CATEGORIES


@pytest.fixture
def runner() -> tuple[ToolRunner, FakeExecutor]:
    guard = AuthorizationGuard(load_authorized_targets(FIXTURE_AUTH))
    catalog = load_tool_catalog()
    executor = FakeExecutor(stdout="phase6a-ok")
    tool_runner = ToolRunner(
        catalog=catalog,
        guard=guard,
        runtime=KaliRuntime(executor),
        audit_log=[],
    )
    return tool_runner, executor


@pytest.mark.asyncio
async def test_reject_active_scanning_on_passive_only_target(runner: tuple[ToolRunner, FakeExecutor]) -> None:
    tool_runner, executor = runner
    with pytest.raises(AuthorizationDenied, match="categor"):
        await tool_runner.execute(
            ToolExecutionRequest(tool_id="zmap_safe", host="app.allowed.example.com"),
            on=datetime(2026, 7, 6, 12, 0, tzinfo=timezone.utc),
        )
    assert executor.commands == []


@pytest.mark.asyncio
async def test_execute_phase6a_tools_argv(runner: tuple[ToolRunner, FakeExecutor]) -> None:
    tool_runner, executor = runner
    host = "full.example.com"
    cases = [
        ("zmap_safe", ["zmap", "-p", "443", "-N", "1", "-o", "-", host]),
        (
            "unicornscan_safe",
            ["unicornscan", "-mT", "-p", "22,80,443,8080,3000,5432,8000,111", host],
        ),
    ]
    for tool_id, expected_argv in cases:
        executor.commands.clear()
        result = await tool_runner.execute(
            ToolExecutionRequest(tool_id=tool_id, host=host, requested_by="tester"),
            on=datetime(2026, 7, 6, 12, 0, tzinfo=timezone.utc),
        )
        assert result.exit_code == 0
        assert executor.commands[-1] == expected_argv
