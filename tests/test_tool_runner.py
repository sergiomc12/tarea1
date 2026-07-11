"""Tests de tool_runner — catálogo cerrado, params y auditoría."""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from scraper_agent.security_env.authorization_guard import AuthorizationGuard, load_authorized_targets
from scraper_agent.security_env.exceptions import (
    AuthorizationDenied,
    InvalidToolParams,
    ToolNotFound,
)
from scraper_agent.security_env.kali_runtime import KaliRuntime
from scraper_agent.security_env.models import ToolExecutionRequest
from scraper_agent.security_env.categories import ALL_CATEGORIES
from scraper_agent.security_env.tool_runner import ToolRunner, load_tool_catalog
from conftest import FakeExecutor

FIXTURE_AUTH = Path(__file__).parent / "fixtures" / "authorized_targets_test.yaml"


@pytest.fixture
def runner() -> tuple[ToolRunner, FakeExecutor]:
    guard = AuthorizationGuard(load_authorized_targets(FIXTURE_AUTH))
    catalog = load_tool_catalog()
    audit: list = []
    executor = FakeExecutor(stdout="whois-output")
    tool_runner = ToolRunner(
        catalog=catalog,
        guard=guard,
        runtime=KaliRuntime(executor),
        audit_log=audit,
    )
    return tool_runner, executor


@pytest.mark.asyncio
async def test_execute_catalog_tool_success(runner: tuple[ToolRunner, FakeExecutor]) -> None:
    tool_runner, _executor = runner
    result = await tool_runner.execute(
        ToolExecutionRequest(
            tool_id="whois",
            host="app.allowed.example.com",
            requested_by="tester",
            session_id="sess-a",
        ),
        on=datetime(2026, 7, 6, 12, 0, tzinfo=timezone.utc),
    )
    assert result.exit_code == 0
    assert result.argv == ["whois", "app.allowed.example.com"]
    assert result.stdout == "whois-output"
    assert len(tool_runner.audit_log) == 1
    assert tool_runner.audit_log[0].allowed is True


@pytest.mark.asyncio
async def test_reject_unknown_tool_before_execution(
    runner: tuple[ToolRunner, FakeExecutor],
) -> None:
    tool_runner, _executor = runner
    with pytest.raises(ToolNotFound):
        await tool_runner.execute(
            ToolExecutionRequest(tool_id="metasploit", host="app.allowed.example.com"),
            on=datetime(2026, 7, 6, 12, 0, tzinfo=timezone.utc),
        )
    assert tool_runner.audit_log[-1].allowed is False


@pytest.mark.asyncio
async def test_reject_invalid_host_characters(runner: tuple[ToolRunner, FakeExecutor]) -> None:
    tool_runner, _executor = runner
    with pytest.raises(InvalidToolParams):
        await tool_runner.execute(
            ToolExecutionRequest(tool_id="whois", host="evil.com; rm -rf /"),
            on=datetime(2026, 7, 6, 12, 0, tzinfo=timezone.utc),
        )
    assert tool_runner.audit_log[-1].allowed is False


@pytest.mark.asyncio
async def test_reject_unauthorized_host_before_tool_runner(
    runner: tuple[ToolRunner, FakeExecutor],
) -> None:
    tool_runner, executor = runner
    with pytest.raises(AuthorizationDenied):
        await tool_runner.execute(
            ToolExecutionRequest(tool_id="whois", host="evil.example.com"),
            on=datetime(2026, 7, 6, 12, 0, tzinfo=timezone.utc),
        )
    assert executor.commands == []
    assert tool_runner.audit_log[-1].allowed is False


@pytest.mark.asyncio
async def test_reject_expired_target_before_execution(
    runner: tuple[ToolRunner, FakeExecutor],
) -> None:
    tool_runner, _executor = runner
    with pytest.raises(AuthorizationDenied, match="expir"):
        await tool_runner.execute(
            ToolExecutionRequest(tool_id="whois", host="expired.example.com"),
            on=datetime(2026, 7, 6, 12, 0, tzinfo=timezone.utc),
        )


@pytest.mark.asyncio
async def test_reject_category_not_allowed(runner: tuple[ToolRunner, FakeExecutor]) -> None:
    tool_runner, _executor = runner
    with pytest.raises(AuthorizationDenied, match="categor"):
        await tool_runner.execute(
            ToolExecutionRequest(tool_id="nmap_top100", host="limited.example.com"),
            on=datetime(2026, 7, 6, 12, 0, tzinfo=timezone.utc),
        )


@pytest.mark.asyncio
async def test_audit_log_records_rejection_reason(runner: tuple[ToolRunner, FakeExecutor]) -> None:
    tool_runner, _executor = runner
    with pytest.raises(AuthorizationDenied):
        await tool_runner.execute(
            ToolExecutionRequest(tool_id="whois", host="evil.example.com"),
            on=datetime(2026, 7, 6, 12, 0, tzinfo=timezone.utc),
        )
    entry = tool_runner.audit_log[0]
    assert entry.allowed is False
    assert entry.tool_id == "whois"
    assert "no autorizado" in entry.reason.lower()


def test_catalog_contains_only_alcance_tools() -> None:
    catalog = load_tool_catalog()
    ids = set(catalog)
    assert ids == {
        "whois",
        "dig_a",
        "curl_headers",
        "nslookup_a",
        "dnsenum_safe",
        "dnsrecon_std",
        "sublist3r_safe",
        "nmap_top100",
        "nmap_services",
        "nikto_safe",
        "gobuster_dir",
        "masscan_top_ports",
        "netdiscover_passive",
        "nuclei_safe",
        "amass_passive",
        "theharvester_safe",
        "spiderfoot_passive",
        "dirb_small",
        "ffuf_dir",
        "wpscan_enum",
        "whatweb_safe",
        "httpx_probe",
        "wafw00f_safe",
        "sslscan_safe",
        "sslyze_safe",
        "testssl_safe",
        "openssl_cert",
        "fierce_safe",
        "zmap_safe",
        "unicornscan_safe",
        "nmap_vuln_scripts",
        "modbus_s7_discover",
    }
    for entry in catalog.values():
        assert entry.category in ALL_CATEGORIES


@pytest.mark.asyncio
async def test_reject_extended_tool_on_basic_target(runner: tuple[ToolRunner, FakeExecutor]) -> None:
    tool_runner, executor = runner
    with pytest.raises(AuthorizationDenied, match="categor"):
        await tool_runner.execute(
            ToolExecutionRequest(tool_id="nmap_services", host="app.allowed.example.com"),
            on=datetime(2026, 7, 6, 12, 0, tzinfo=timezone.utc),
        )
    assert executor.commands == []


@pytest.mark.asyncio
async def test_execute_extended_catalog_tools(runner: tuple[ToolRunner, FakeExecutor]) -> None:
    tool_runner, executor = runner
    cases = [
        ("nmap_services", "full.example.com", ["nmap", "-sT", "-sV", "--top-ports", "50", "full.example.com"]),
        (
            "nikto_safe",
            "full.example.com",
            ["nikto", "-h", "https://full.example.com", "-Tuning", "x", "-maxtime", "120s", "-nointeractive"],
        ),
        (
            "gobuster_dir",
            "full.example.com",
            [
                "gobuster",
                "dir",
                "-u",
                "https://full.example.com/",
                "-w",
                "/usr/share/seclists/Discovery/Web-Content/common.txt",
                "-t",
                "5",
                "-q",
                "-b",
                "403,404,429",
                "--timeout",
                "10s",
                "--no-error",
            ],
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


class TestAuditLogPersistence:
    """Gap real encontrado en el balance contra Wazuh (2026-07-09): el audit
    log solo vivía en memoria (`ToolRunner._audit_log`) y se perdía al
    reiniciar el proceso — sin esto, `defense_env/` no tenía ningún log real
    de ejecuciones/rechazos contra el que correlacionar. Ver CHANGELOG.md."""

    @pytest.mark.asyncio
    async def test_allowed_execution_persisted_to_disk_when_sink_path_given(
        self, tmp_path: Path
    ) -> None:
        sink_path = tmp_path / "tool_audit.jsonl"
        guard = AuthorizationGuard(load_authorized_targets(FIXTURE_AUTH))
        catalog = load_tool_catalog()
        executor = FakeExecutor(stdout="whois-output")
        tool_runner = ToolRunner(
            catalog=catalog,
            guard=guard,
            runtime=KaliRuntime(executor),
            audit_sink_path=sink_path,
        )

        await tool_runner.execute(
            ToolExecutionRequest(tool_id="whois", host="app.allowed.example.com", requested_by="tester"),
            on=datetime(2026, 7, 6, 12, 0, tzinfo=timezone.utc),
        )

        assert sink_path.exists()
        lines = sink_path.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 1
        parsed = json.loads(lines[0])
        assert parsed["allowed"] is True
        assert parsed["tool_id"] == "whois"

    @pytest.mark.asyncio
    async def test_denied_request_also_persisted_to_disk(self, tmp_path: Path) -> None:
        sink_path = tmp_path / "tool_audit.jsonl"
        guard = AuthorizationGuard(load_authorized_targets(FIXTURE_AUTH))
        catalog = load_tool_catalog()
        executor = FakeExecutor(stdout="")
        tool_runner = ToolRunner(
            catalog=catalog,
            guard=guard,
            runtime=KaliRuntime(executor),
            audit_sink_path=sink_path,
        )

        with pytest.raises(AuthorizationDenied):
            await tool_runner.execute(
                ToolExecutionRequest(tool_id="whois", host="evil.example.com", requested_by="tester"),
                on=datetime(2026, 7, 6, 12, 0, tzinfo=timezone.utc),
            )

        lines = sink_path.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 1
        parsed = json.loads(lines[0])
        assert parsed["allowed"] is False

    @pytest.mark.asyncio
    async def test_no_file_written_when_sink_path_omitted(self, tmp_path: Path) -> None:
        guard = AuthorizationGuard(load_authorized_targets(FIXTURE_AUTH))
        catalog = load_tool_catalog()
        executor = FakeExecutor(stdout="whois-output")
        tool_runner = ToolRunner(catalog=catalog, guard=guard, runtime=KaliRuntime(executor))

        await tool_runner.execute(
            ToolExecutionRequest(tool_id="whois", host="app.allowed.example.com", requested_by="tester"),
            on=datetime(2026, 7, 6, 12, 0, tzinfo=timezone.utc),
        )

        assert list(tmp_path.iterdir()) == []
