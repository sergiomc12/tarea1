"""Tests fase 6e — subconjunto seguro de scripts NSE (nmap_vuln_scripts).

No se habilita la categoría `vuln` completa de NSE: solo un allowlist de
scripts no destructivos (banner, ssl-cert, http-security-headers,
ssh2-enum-algos, smb-os-discovery). Ver docs/alcance-seguridad.md.
"""

from datetime import datetime, timezone

import pytest

from scraper_agent.security_env.authorization_guard import AuthorizationGuard, load_authorized_targets
from scraper_agent.security_env.categories import ALL_CATEGORIES, VULN_SCRIPT_SCANNING
from scraper_agent.security_env.exceptions import AuthorizationDenied
from scraper_agent.security_env.kali_runtime import KaliRuntime
from scraper_agent.security_env.models import ToolExecutionRequest
from scraper_agent.security_env.tool_runner import ToolRunner, load_tool_catalog
from conftest import FakeExecutor

FIXTURE_AUTH = __import__("pathlib").Path(__file__).parent / "fixtures" / "authorized_targets_test.yaml"

SAFE_SCRIPTS = "banner,ssl-cert,http-security-headers,ssh2-enum-algos,smb-os-discovery"


def test_nmap_vuln_scripts_in_catalog() -> None:
    catalog = load_tool_catalog()
    entry = catalog["nmap_vuln_scripts"]
    assert entry.category == VULN_SCRIPT_SCANNING
    assert entry.category in ALL_CATEGORIES


def test_nmap_vuln_scripts_does_not_use_full_vuln_category() -> None:
    catalog = load_tool_catalog()
    argv_text = " ".join(catalog["nmap_vuln_scripts"].argv_template)
    assert "--script vuln" not in argv_text
    assert SAFE_SCRIPTS in argv_text


@pytest.fixture
def runner() -> tuple[ToolRunner, FakeExecutor]:
    guard = AuthorizationGuard(load_authorized_targets(FIXTURE_AUTH))
    catalog = load_tool_catalog()
    executor = FakeExecutor(stdout="phase6e-ok")
    tool_runner = ToolRunner(
        catalog=catalog,
        guard=guard,
        runtime=KaliRuntime(executor),
        audit_log=[],
    )
    return tool_runner, executor


@pytest.mark.asyncio
async def test_reject_vuln_script_scanning_on_passive_only_target(
    runner: tuple[ToolRunner, FakeExecutor],
) -> None:
    tool_runner, executor = runner
    with pytest.raises(AuthorizationDenied, match="categor"):
        await tool_runner.execute(
            ToolExecutionRequest(tool_id="nmap_vuln_scripts", host="app.allowed.example.com"),
            on=datetime(2026, 7, 6, 12, 0, tzinfo=timezone.utc),
        )
    assert executor.commands == []


@pytest.mark.asyncio
async def test_execute_nmap_vuln_scripts_argv(runner: tuple[ToolRunner, FakeExecutor]) -> None:
    tool_runner, executor = runner
    host = "full.example.com"
    result = await tool_runner.execute(
        ToolExecutionRequest(tool_id="nmap_vuln_scripts", host=host, requested_by="tester"),
        on=datetime(2026, 7, 6, 12, 0, tzinfo=timezone.utc),
    )
    assert result.exit_code == 0
    assert executor.commands[-1] == [
        "nmap",
        "-sV",
        "--script",
        SAFE_SCRIPTS,
        "--top-ports",
        "50",
        host,
    ]
