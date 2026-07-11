"""Tests fase 5d — fuzzing web acotado (dirb, ffuf, wpscan enum)."""

from datetime import datetime, timezone

import pytest

from scraper_agent.security_env.authorization_guard import AuthorizationGuard, load_authorized_targets
from scraper_agent.security_env.categories import ALL_CATEGORIES, BOUNDED_FUZZING
from scraper_agent.security_env.exceptions import AuthorizationDenied
from scraper_agent.security_env.kali_runtime import KaliRuntime
from scraper_agent.security_env.models import ToolExecutionRequest
from scraper_agent.security_env.tool_runner import ToolRunner, load_tool_catalog
from conftest import FakeExecutor

FIXTURE_AUTH = __import__("pathlib").Path(__file__).parent / "fixtures" / "authorized_targets_test.yaml"

PHASE5D_TOOL_IDS = frozenset(
    {
        "dirb_small",
        "ffuf_dir",
        "wpscan_enum",
    }
)

FORBIDDEN_ARGV_FRAGMENTS = (
    "--password",
    "--dump",
    "--force",
    "--brute-force",
    "--users",
)


def test_phase5d_tools_in_catalog() -> None:
    catalog = load_tool_catalog()
    assert PHASE5D_TOOL_IDS <= set(catalog)
    for tool_id in PHASE5D_TOOL_IDS:
        assert catalog[tool_id].category == BOUNDED_FUZZING
        assert catalog[tool_id].category in ALL_CATEGORIES


def test_bounded_fuzzing_tools_have_no_offensive_flags() -> None:
    catalog = load_tool_catalog()
    for entry in catalog.values():
        if entry.category != BOUNDED_FUZZING:
            continue
        argv_text = " ".join(entry.argv_template).lower()
        for fragment in FORBIDDEN_ARGV_FRAGMENTS:
            assert fragment not in argv_text, f"{entry.id} contiene flag prohibido: {fragment}"


@pytest.fixture
def runner() -> tuple[ToolRunner, FakeExecutor]:
    guard = AuthorizationGuard(load_authorized_targets(FIXTURE_AUTH))
    catalog = load_tool_catalog()
    executor = FakeExecutor(stdout="phase5d-ok")
    tool_runner = ToolRunner(
        catalog=catalog,
        guard=guard,
        runtime=KaliRuntime(executor),
        audit_log=[],
    )
    return tool_runner, executor


@pytest.mark.asyncio
async def test_reject_fuzzing_on_passive_only_target(runner: tuple[ToolRunner, FakeExecutor]) -> None:
    tool_runner, executor = runner
    with pytest.raises(AuthorizationDenied, match="categor"):
        await tool_runner.execute(
            ToolExecutionRequest(tool_id="ffuf_dir", host="app.allowed.example.com"),
            on=datetime(2026, 7, 6, 12, 0, tzinfo=timezone.utc),
        )
    assert executor.commands == []


@pytest.mark.asyncio
async def test_execute_phase5d_tools_argv(runner: tuple[ToolRunner, FakeExecutor]) -> None:
    tool_runner, executor = runner
    host = "full.example.com"
    cases = [
        (
            "dirb_small",
            [
                "dirb",
                f"https://{host}/",
                "/usr/share/dirb/wordlists/small.txt",
                "-r",
                "-S",
                "-z",
                "10",
            ],
        ),
        (
            "ffuf_dir",
            [
                "ffuf",
                "-u",
                f"https://{host}/FUZZ",
                "-w",
                "/usr/share/seclists/Discovery/Web-Content/DirBuster-2007_directory-list-2.3-small.txt",
                "-ac",
                "-t",
                "5",
                "-rate",
                "10",
                "-mc",
                "301,302,403",
                "-timeout",
                "10",
                "-noninteractive",
            ],
        ),
        (
            "wpscan_enum",
            [
                "wpscan_enum_safe",
                f"https://{host}",
            ],
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
