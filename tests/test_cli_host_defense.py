"""Tests del cableado CLI de defense-host-* -- confirmación requerida
(--yes) y validación de argumentos. La lógica de detección/acción ya está
cubierta en tests/test_defense_host_defense.py con runners falsos; acá se
mockea a nivel de módulo `scraper_agent.cli` para no ejecutar `which`/
`firewall-cmd`/etc. reales en esta máquina de desarrollo (Windows, sin
firewalld/iptables reales)."""

from __future__ import annotations

from typer.testing import CliRunner

import scraper_agent.cli as cli_module
from scraper_agent.cli import app
from scraper_agent.defense_env.host_defense import ActionResult, FirewallTool

runner = CliRunner()


def test_block_ip_requires_confirmation() -> None:
    result = runner.invoke(app, ["defense-host-block-ip", "203.0.113.7"])

    assert result.exit_code == 1
    assert "--yes" in result.output


def test_block_ip_with_confirmation_calls_host_defense(monkeypatch) -> None:
    monkeypatch.setattr(cli_module, "detect_firewall_tool", lambda: FirewallTool(name="iptables", binary="iptables"))
    monkeypatch.setattr(
        cli_module,
        "host_block_ip",
        lambda ip, firewall: ActionResult(
            action="block_ip", target=ip, tool_used=firewall.name, success=True, detail=""
        ),
    )

    result = runner.invoke(app, ["defense-host-block-ip", "203.0.113.7", "--yes"])

    assert result.exit_code == 0, result.output
    assert "OK" in result.output


def test_close_port_requires_confirmation() -> None:
    result = runner.invoke(app, ["defense-host-close-port", "8080"])

    assert result.exit_code == 1
    assert "--yes" in result.output


def test_kill_process_requires_pid_or_name() -> None:
    result = runner.invoke(app, ["defense-host-kill-process", "--yes"])

    assert result.exit_code == 2


def test_kill_process_requires_confirmation() -> None:
    result = runner.invoke(app, ["defense-host-kill-process", "--pid", "1234"])

    assert result.exit_code == 1
    assert "--yes" in result.output


def test_kill_process_with_confirmation_calls_host_defense(monkeypatch) -> None:
    monkeypatch.setattr(
        cli_module,
        "host_kill_process",
        lambda pid=None, name=None: ActionResult(
            action="kill_process", target=f"pid:{pid}", tool_used="kill/pkill", success=True, detail=""
        ),
    )

    result = runner.invoke(app, ["defense-host-kill-process", "--pid", "1234", "--yes"])

    assert result.exit_code == 0, result.output


def test_host_detect_reports_non_linux(monkeypatch) -> None:
    from scraper_agent.defense_env.host_defense import OSInfo

    monkeypatch.setattr(cli_module, "detect_os", lambda: OSInfo(is_linux=False))
    monkeypatch.setattr(cli_module, "detect_firewall_tool", lambda: FirewallTool(name="none", binary=""))

    result = runner.invoke(app, ["defense-host-detect"])

    assert result.exit_code == 0
    assert "no parece un host Linux" in result.output


def test_host_connections_reports_none_when_empty(monkeypatch) -> None:
    monkeypatch.setattr(cli_module, "host_list_connections", lambda: [])

    result = runner.invoke(app, ["defense-host-connections"])

    assert result.exit_code == 0
    assert "Sin conexiones" in result.output
