"""Tests fase 6c — análisis TLS/SSL (sslscan, sslyze, testssl.sh, openssl)."""

from datetime import datetime, timezone

import pytest

from scraper_agent.security_env.authorization_guard import AuthorizationGuard, load_authorized_targets
from scraper_agent.security_env.categories import ALL_CATEGORIES, TLS_ANALYSIS
from scraper_agent.security_env.exceptions import AuthorizationDenied
from scraper_agent.security_env.kali_runtime import KaliRuntime
from scraper_agent.security_env.models import ToolExecutionRequest
from scraper_agent.security_env.tool_runner import ToolRunner, load_tool_catalog
from conftest import FakeExecutor

FIXTURE_AUTH = __import__("pathlib").Path(__file__).parent / "fixtures" / "authorized_targets_test.yaml"

PHASE6C_TOOL_IDS = frozenset({"sslscan_safe", "sslyze_safe", "testssl_safe", "openssl_cert"})


def test_phase6c_tools_in_catalog() -> None:
    catalog = load_tool_catalog()
    assert PHASE6C_TOOL_IDS <= set(catalog)
    for tool_id in PHASE6C_TOOL_IDS:
        assert catalog[tool_id].category == TLS_ANALYSIS
        assert catalog[tool_id].category in ALL_CATEGORIES


@pytest.fixture
def runner() -> tuple[ToolRunner, FakeExecutor]:
    guard = AuthorizationGuard(load_authorized_targets(FIXTURE_AUTH))
    catalog = load_tool_catalog()
    executor = FakeExecutor(stdout="phase6c-ok")
    tool_runner = ToolRunner(
        catalog=catalog,
        guard=guard,
        runtime=KaliRuntime(executor),
        audit_log=[],
    )
    return tool_runner, executor


@pytest.mark.asyncio
async def test_reject_tls_analysis_on_passive_only_target(runner: tuple[ToolRunner, FakeExecutor]) -> None:
    tool_runner, executor = runner
    with pytest.raises(AuthorizationDenied, match="categor"):
        await tool_runner.execute(
            ToolExecutionRequest(tool_id="sslscan_safe", host="app.allowed.example.com"),
            on=datetime(2026, 7, 6, 12, 0, tzinfo=timezone.utc),
        )
    assert executor.commands == []


@pytest.mark.asyncio
async def test_execute_phase6c_tools_argv(runner: tuple[ToolRunner, FakeExecutor]) -> None:
    tool_runner, executor = runner
    host = "full.example.com"
    cases = [
        ("sslscan_safe", ["sslscan", "--no-colour", host]),
        ("sslyze_safe", ["sslyze", "--json_out", "-", host]),
        ("testssl_safe", ["testssl", "--fast", "--quiet", "--color", "0", host]),
        ("openssl_cert", ["openssl_cert_check", host]),
    ]
    for tool_id, expected_argv in cases:
        executor.commands.clear()
        result = await tool_runner.execute(
            ToolExecutionRequest(tool_id=tool_id, host=host, requested_by="tester"),
            on=datetime(2026, 7, 6, 12, 0, tzinfo=timezone.utc),
        )
        assert result.exit_code == 0
        assert executor.commands[-1] == expected_argv
