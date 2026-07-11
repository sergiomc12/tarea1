"""Tests fase 5b — escaneo intermedio (masscan, netdiscover, nuclei)."""

from datetime import datetime, timezone

import pytest

from scraper_agent.security_env.authorization_guard import AuthorizationGuard, load_authorized_targets
from scraper_agent.security_env.categories import ALL_CATEGORIES, NETWORK_DISCOVERY
from scraper_agent.security_env.exceptions import InvalidToolParams
from scraper_agent.security_env.kali_runtime import KaliRuntime
from scraper_agent.security_env.models import ToolExecutionRequest
from scraper_agent.security_env.param_validation import validate_cidr
from scraper_agent.security_env.tool_runner import ToolRunner, load_tool_catalog
from conftest import FakeExecutor

FIXTURE_AUTH = __import__("pathlib").Path(__file__).parent / "fixtures" / "authorized_targets_test.yaml"

PHASE5B_TOOL_IDS = frozenset(
    {
        "masscan_top_ports",
        "netdiscover_passive",
        "nuclei_safe",
    }
)


def test_phase5b_tools_in_catalog() -> None:
    catalog = load_tool_catalog()
    assert PHASE5B_TOOL_IDS <= set(catalog)
    for tool_id in PHASE5B_TOOL_IDS:
        assert catalog[tool_id].category in ALL_CATEGORIES


def test_network_discovery_category_exists() -> None:
    assert NETWORK_DISCOVERY in ALL_CATEGORIES


def test_validate_cidr_accepts_network() -> None:
    assert validate_cidr("203.0.113.0/28") == "203.0.113.0/28"


def test_validate_cidr_rejects_shell_injection() -> None:
    with pytest.raises(InvalidToolParams):
        validate_cidr("203.0.113.0/28; rm -rf /")


@pytest.fixture
def guard() -> AuthorizationGuard:
    return AuthorizationGuard(load_authorized_targets(FIXTURE_AUTH))


def test_authorize_network_discovery_on_cidr_target(guard: AuthorizationGuard) -> None:
    result = guard.authorize("203.0.113.0/28", "network_discovery", on=__import__("datetime").date(2026, 7, 6))
    assert result.allowed is True


def test_authorize_ip_inside_cidr_target(guard: AuthorizationGuard) -> None:
    result = guard.authorize("203.0.113.5", "network_discovery", on=__import__("datetime").date(2026, 7, 6))
    assert result.allowed is True


@pytest.fixture
def runner() -> tuple[ToolRunner, FakeExecutor]:
    guard = AuthorizationGuard(load_authorized_targets(FIXTURE_AUTH))
    catalog = load_tool_catalog()
    executor = FakeExecutor(stdout="phase5b-ok")
    tool_runner = ToolRunner(
        catalog=catalog,
        guard=guard,
        runtime=KaliRuntime(executor),
        audit_log=[],
    )
    return tool_runner, executor


@pytest.mark.asyncio
async def test_reject_netdiscover_on_domain_host(runner: tuple[ToolRunner, FakeExecutor]) -> None:
    tool_runner, executor = runner
    with pytest.raises(InvalidToolParams, match="cidr invalido|host invalido"):
        await tool_runner.execute(
            ToolExecutionRequest(tool_id="netdiscover_passive", host="full.example.com"),
            on=datetime(2026, 7, 6, 12, 0, tzinfo=timezone.utc),
        )
    assert executor.commands == []


@pytest.mark.asyncio
async def test_execute_phase5b_tools_argv(runner: tuple[ToolRunner, FakeExecutor]) -> None:
    tool_runner, executor = runner
    cases = [
        (
            "masscan_top_ports",
            "203.0.113.50",
            [
                "masscan",
                "203.0.113.50",
                "-p22,80,443,8080,3000,5432,8000,111",
                "--rate",
                "50",
                "--wait",
                "1",
                "--open",
            ],
        ),
        (
            "nuclei_safe",
            "full.example.com",
            [
                "nuclei",
                "-u",
                "https://full.example.com",
                "-severity",
                "info,low,medium",
                "-tags",
                "misconfig,exposure,tech",
                "-max-host-error",
                "10",
                "-rate-limit",
                "15",
                "-timeout",
                "10",
                "-no-color",
                "-silent",
                "-disable-update-check",
            ],
        ),
        (
            "netdiscover_passive",
            "203.0.113.0/28",
            ["netdiscover", "-r", "203.0.113.0/28", "-s", "2", "-c", "5"],
        ),
    ]
    for tool_id, host, expected_argv in cases:
        executor.commands.clear()
        result = await tool_runner.execute(
            ToolExecutionRequest(tool_id=tool_id, host=host, requested_by="tester"),
            on=datetime(2026, 7, 6, 12, 0, tzinfo=timezone.utc),
        )
        assert result.exit_code == 0
        assert executor.commands[-1] == expected_argv
