"""Tests fase 6f — recon ICS/SCADA solo-lectura (modbus_s7_discover).

Categoría `ics_scada_recon` deliberadamente separada de `full.example.com`
(fixture dedicada `ics.example.com`) porque escanear PLCs/SCADA reales sin
autorización explícita del responsable industrial puede afectar la
estabilidad del activo. Ver docs/alcance-seguridad.md.
"""

from datetime import datetime, timezone

import pytest

from scraper_agent.security_env.authorization_guard import AuthorizationGuard, load_authorized_targets
from scraper_agent.security_env.categories import ALL_CATEGORIES, ICS_SCADA_RECON
from scraper_agent.security_env.exceptions import AuthorizationDenied
from scraper_agent.security_env.kali_runtime import KaliRuntime
from scraper_agent.security_env.models import ToolExecutionRequest
from scraper_agent.security_env.tool_runner import ToolRunner, load_tool_catalog
from conftest import FakeExecutor

FIXTURE_AUTH = __import__("pathlib").Path(__file__).parent / "fixtures" / "authorized_targets_test.yaml"


def test_modbus_s7_discover_in_catalog() -> None:
    catalog = load_tool_catalog()
    entry = catalog["modbus_s7_discover"]
    assert entry.category == ICS_SCADA_RECON
    assert entry.category in ALL_CATEGORIES


def test_modbus_s7_discover_is_read_only() -> None:
    catalog = load_tool_catalog()
    argv_text = " ".join(catalog["modbus_s7_discover"].argv_template)
    assert "modbus-discover" in argv_text
    assert "s7-info" in argv_text
    assert "write" not in argv_text.lower()


@pytest.fixture
def runner() -> tuple[ToolRunner, FakeExecutor]:
    guard = AuthorizationGuard(load_authorized_targets(FIXTURE_AUTH))
    catalog = load_tool_catalog()
    executor = FakeExecutor(stdout="phase6f-ok")
    tool_runner = ToolRunner(
        catalog=catalog,
        guard=guard,
        runtime=KaliRuntime(executor),
        audit_log=[],
    )
    return tool_runner, executor


@pytest.mark.asyncio
async def test_reject_modbus_s7_discover_without_ics_category(
    runner: tuple[ToolRunner, FakeExecutor],
) -> None:
    tool_runner, executor = runner
    with pytest.raises(AuthorizationDenied, match="categor"):
        await tool_runner.execute(
            ToolExecutionRequest(tool_id="modbus_s7_discover", host="full.example.com"),
            on=datetime(2026, 7, 6, 12, 0, tzinfo=timezone.utc),
        )
    assert executor.commands == []


@pytest.mark.asyncio
async def test_execute_modbus_s7_discover_argv(runner: tuple[ToolRunner, FakeExecutor]) -> None:
    tool_runner, executor = runner
    host = "ics.example.com"
    result = await tool_runner.execute(
        ToolExecutionRequest(tool_id="modbus_s7_discover", host=host, requested_by="tester"),
        on=datetime(2026, 7, 6, 12, 0, tzinfo=timezone.utc),
    )
    assert result.exit_code == 0
    assert executor.commands[-1] == [
        "nmap",
        "--script",
        "modbus-discover,s7-info",
        "-p",
        "502,102",
        host,
    ]
