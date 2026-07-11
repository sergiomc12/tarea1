"""Tests de defensa activa a nivel de sistema operativo Linux
(defense_env/host_defense.py) — servidor de producción real (CentOS/RHEL),
no contenedores Docker.

LIMITACIÓN HONESTA (ver CHANGELOG.md): este entorno de desarrollo es
Windows, sin acceso a un CentOS/RHEL real para probar contra
infraestructura real. Todos los tests usan runners falsos (mismo patrón
que el resto de defense_env/) — validan la LÓGICA (qué comando se arma,
cómo se interpreta el resultado, qué herramienta se prioriza), no que el
comando real funcione en un RHEL de verdad.
"""

from __future__ import annotations

from pathlib import Path

from scraper_agent.defense_env.host_defense import (
    FirewallTool,
    block_ip,
    close_port,
    detect_firewall_tool,
    detect_os,
    kill_process,
    list_connections,
)


class _FakeCompletedProcess:
    def __init__(self, stdout: str = "", stderr: str = "", returncode: int = 0) -> None:
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode


def _runner_for(available: set[str]):
    def _runner(argv: list[str]):
        if argv[0] == "which":
            binary = argv[1]
            if binary in available:
                return _FakeCompletedProcess(stdout=f"/usr/bin/{binary}\n", returncode=0)
            return _FakeCompletedProcess(stdout="", returncode=1)
        return _FakeCompletedProcess(returncode=0)

    return _runner


class TestDetectOs:
    def test_parses_centos_style_os_release(self, tmp_path: Path) -> None:
        os_release = tmp_path / "os-release"
        os_release.write_text(
            'NAME="CentOS Linux"\nID="centos"\nID_LIKE="rhel fedora"\nVERSION_ID="9"\n',
            encoding="utf-8",
        )

        info = detect_os(os_release_path=os_release)

        assert info.is_linux is True
        assert info.id == "centos"
        assert info.id_like == "rhel fedora"
        assert info.version_id == "9"

    def test_parses_rhel_style_os_release(self, tmp_path: Path) -> None:
        os_release = tmp_path / "os-release"
        os_release.write_text(
            'NAME="Red Hat Enterprise Linux"\nID="rhel"\nID_LIKE="fedora"\nVERSION_ID="9.3"\n',
            encoding="utf-8",
        )

        info = detect_os(os_release_path=os_release)

        assert info.id == "rhel"

    def test_missing_os_release_means_not_linux(self, tmp_path: Path) -> None:
        info = detect_os(os_release_path=tmp_path / "no_existe")

        assert info.is_linux is False


class TestDetectFirewallTool:
    def test_prefers_firewalld_when_available(self) -> None:
        tool = detect_firewall_tool(runner=_runner_for({"firewall-cmd", "iptables", "nft"}))

        assert tool.name == "firewalld"

    def test_falls_back_to_nftables_when_no_firewalld(self) -> None:
        tool = detect_firewall_tool(runner=_runner_for({"nft", "iptables"}))

        assert tool.name == "nftables"

    def test_falls_back_to_iptables_when_only_that_available(self) -> None:
        tool = detect_firewall_tool(runner=_runner_for({"iptables"}))

        assert tool.name == "iptables"

    def test_none_when_nothing_available(self) -> None:
        tool = detect_firewall_tool(runner=_runner_for(set()))

        assert tool.name == "none"


class TestBlockIp:
    def test_uses_firewalld_when_that_is_the_tool(self) -> None:
        calls: list[list[str]] = []

        def runner(argv):
            calls.append(argv)
            return _FakeCompletedProcess(returncode=0)

        result = block_ip("203.0.113.7", firewall=FirewallTool(name="firewalld", binary="firewall-cmd"), runner=runner)

        assert result.success is True
        assert result.tool_used == "firewalld"
        assert any("203.0.113.7" in " ".join(c) for c in calls)

    def test_uses_iptables_when_that_is_the_tool(self) -> None:
        calls: list[list[str]] = []

        def runner(argv):
            calls.append(argv)
            return _FakeCompletedProcess(returncode=0)

        block_ip("203.0.113.7", firewall=FirewallTool(name="iptables", binary="iptables"), runner=runner)

        assert calls[0][0] == "iptables"
        assert "203.0.113.7" in calls[0]

    def test_fails_gracefully_when_no_firewall_tool(self) -> None:
        result = block_ip("203.0.113.7", firewall=FirewallTool(name="none", binary=""), runner=lambda argv: _FakeCompletedProcess())

        assert result.success is False
        assert "no se detect" in result.detail.lower()

    def test_reports_failure_from_command(self) -> None:
        def runner(argv):
            return _FakeCompletedProcess(returncode=1, stderr="permission denied")

        result = block_ip("203.0.113.7", firewall=FirewallTool(name="iptables", binary="iptables"), runner=runner)

        assert result.success is False
        assert "permission denied" in result.detail


class TestClosePort:
    def test_uses_firewalld(self) -> None:
        calls: list[list[str]] = []

        def runner(argv):
            calls.append(argv)
            return _FakeCompletedProcess(returncode=0)

        result = close_port(8080, firewall=FirewallTool(name="firewalld", binary="firewall-cmd"), runner=runner)

        assert result.success is True
        assert any("8080" in " ".join(c) for c in calls)

    def test_target_includes_protocol(self) -> None:
        result = close_port(
            53, protocol="udp", firewall=FirewallTool(name="iptables", binary="iptables"), runner=lambda a: _FakeCompletedProcess()
        )

        assert "53/udp" == result.target


class TestKillProcess:
    def test_kill_by_pid(self) -> None:
        calls: list[list[str]] = []

        def runner(argv):
            calls.append(argv)
            return _FakeCompletedProcess(returncode=0)

        result = kill_process(pid=1234, runner=runner)

        assert result.success is True
        assert calls[0] == ["kill", "-9", "1234"]

    def test_kill_by_name(self) -> None:
        calls: list[list[str]] = []

        def runner(argv):
            calls.append(argv)
            return _FakeCompletedProcess(returncode=0)

        kill_process(name="malicious_proc", runner=runner)

        assert calls[0] == ["pkill", "-9", "-f", "malicious_proc"]

    def test_raises_when_neither_pid_nor_name(self) -> None:
        import pytest

        with pytest.raises(ValueError):
            kill_process(runner=lambda a: _FakeCompletedProcess())


class TestListConnections:
    def test_prefers_ss_over_netstat(self) -> None:
        calls: list[list[str]] = []

        def runner(argv):
            calls.append(argv)
            if argv[0] == "which":
                return _FakeCompletedProcess(stdout="/usr/bin/ss\n", returncode=0)
            return _FakeCompletedProcess(stdout="header\nline1\nline2\n", returncode=0)

        list_connections(runner=runner)

        assert any(c[0] == "ss" for c in calls)

    def test_empty_when_neither_tool_available(self) -> None:
        assert list_connections(runner=_runner_for(set())) == []
