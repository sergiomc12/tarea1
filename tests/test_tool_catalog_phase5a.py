"""Tests fase 5a — reconocimiento DNS intermedio (nslookup, dnsenum, dnsrecon, sublist3r)."""

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

PHASE5A_TOOL_IDS = frozenset(
    {
        "nslookup_a",
        "dnsenum_safe",
        "dnsrecon_std",
        "sublist3r_safe",
    }
)


def test_phase5a_tools_in_catalog() -> None:
    catalog = load_tool_catalog()
    assert PHASE5A_TOOL_IDS <= set(catalog)
    for tool_id in PHASE5A_TOOL_IDS:
        assert catalog[tool_id].category in ALL_CATEGORIES


def test_dns_enumeration_category_exists() -> None:
    assert DNS_ENUMERATION in ALL_CATEGORIES


@pytest.fixture
def runner() -> tuple[ToolRunner, FakeExecutor]:
    guard = AuthorizationGuard(load_authorized_targets(FIXTURE_AUTH))
    catalog = load_tool_catalog()
    executor = FakeExecutor(stdout="phase5a-ok")
    tool_runner = ToolRunner(
        catalog=catalog,
        guard=guard,
        runtime=KaliRuntime(executor),
        audit_log=[],
    )
    return tool_runner, executor


@pytest.mark.asyncio
async def test_reject_dns_enum_on_passive_only_target(runner: tuple[ToolRunner, FakeExecutor]) -> None:
    tool_runner, executor = runner
    with pytest.raises(AuthorizationDenied, match="categor"):
        await tool_runner.execute(
            ToolExecutionRequest(tool_id="dnsenum_safe", host="app.allowed.example.com"),
            on=datetime(2026, 7, 6, 12, 0, tzinfo=timezone.utc),
        )
    assert executor.commands == []


@pytest.mark.asyncio
async def test_execute_phase5a_tools_argv(runner: tuple[ToolRunner, FakeExecutor]) -> None:
    tool_runner, executor = runner
    host = "full.example.com"
    cases = [
        ("nslookup_a", ["nslookup", "-type=A", host]),
        ("dnsenum_safe", ["dnsenum", "--noreverse", "--timeout", "5", "--threads", "2", host]),
        (
            "dnsrecon_std",
            ["dnsrecon", "-d", host, "-t", "std", "--lifetime", "15"],
        ),
        ("sublist3r_safe", ["sublist3r", "-d", host, "-t", "3", "-n"]),
    ]
    for tool_id, expected_argv in cases:
        executor.commands.clear()
        result = await tool_runner.execute(
            ToolExecutionRequest(tool_id=tool_id, host=host, requested_by="tester"),
            on=datetime(2026, 7, 6, 12, 0, tzinfo=timezone.utc),
        )
        assert result.exit_code == 0
        assert executor.commands[-1] == expected_argv


@pytest.mark.asyncio
async def test_nslookup_allowed_on_passive_target(runner: tuple[ToolRunner, FakeExecutor]) -> None:
    tool_runner, executor = runner
    result = await tool_runner.execute(
        ToolExecutionRequest(tool_id="nslookup_a", host="app.allowed.example.com"),
        on=datetime(2026, 7, 6, 12, 0, tzinfo=timezone.utc),
    )
    assert result.exit_code == 0
    assert executor.commands[-1][0] == "nslookup"
