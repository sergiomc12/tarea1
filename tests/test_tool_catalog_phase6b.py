"""Tests fase 6b — recon web / fingerprint de tecnologías (whatweb, httpx, wafw00f)."""

from datetime import datetime, timezone

import pytest

from scraper_agent.security_env.authorization_guard import AuthorizationGuard, load_authorized_targets
from scraper_agent.security_env.categories import ALL_CATEGORIES, PASSIVE_RECON
from scraper_agent.security_env.kali_runtime import KaliRuntime
from scraper_agent.security_env.models import ToolExecutionRequest
from scraper_agent.security_env.tool_runner import ToolRunner, load_tool_catalog
from conftest import FakeExecutor

FIXTURE_AUTH = __import__("pathlib").Path(__file__).parent / "fixtures" / "authorized_targets_test.yaml"

PHASE6B_TOOL_IDS = frozenset({"whatweb_safe", "httpx_probe", "wafw00f_safe"})


def test_phase6b_tools_in_catalog() -> None:
    catalog = load_tool_catalog()
    assert PHASE6B_TOOL_IDS <= set(catalog)
    for tool_id in PHASE6B_TOOL_IDS:
        assert catalog[tool_id].category == PASSIVE_RECON
        assert catalog[tool_id].category in ALL_CATEGORIES


@pytest.fixture
def runner() -> tuple[ToolRunner, FakeExecutor]:
    guard = AuthorizationGuard(load_authorized_targets(FIXTURE_AUTH))
    catalog = load_tool_catalog()
    executor = FakeExecutor(stdout="phase6b-ok")
    tool_runner = ToolRunner(
        catalog=catalog,
        guard=guard,
        runtime=KaliRuntime(executor),
        audit_log=[],
    )
    return tool_runner, executor


@pytest.mark.asyncio
async def test_execute_phase6b_tools_argv(runner: tuple[ToolRunner, FakeExecutor]) -> None:
    tool_runner, executor = runner
    host = "app.allowed.example.com"
    cases = [
        ("whatweb_safe", ["whatweb", "-a", "1", "--no-errors", host]),
        (
            "httpx_probe",
            ["httpx-toolkit", "-u", host, "-silent", "-tech-detect", "-no-color"],
        ),
        ("wafw00f_safe", ["wafw00f", f"https://{host}"]),
    ]
    for tool_id, expected_argv in cases:
        executor.commands.clear()
        result = await tool_runner.execute(
            ToolExecutionRequest(tool_id=tool_id, host=host, requested_by="tester"),
            on=datetime(2026, 7, 6, 12, 0, tzinfo=timezone.utc),
        )
        assert result.exit_code == 0
        assert executor.commands[-1] == expected_argv
