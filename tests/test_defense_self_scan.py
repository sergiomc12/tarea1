"""Tests de self-scan defensivo (defense_env/self_scan.py) -- Fase exploits.

Reusa el catálogo OFENSIVO de security_env contra la propia infraestructura
en vez de un objetivo externo: mismas herramientas, target distinto. La
autorización es efímera y en memoria (no un archivo YAML estático), porque
el target real es una IP de Docker resuelta dinámicamente.
"""

from __future__ import annotations

import pytest

from conftest import FakeExecutor
from scraper_agent.defense_env.self_scan import (
    build_self_scan_guard,
    resolve_container_ip,
    run_self_scan,
)
from scraper_agent.security_env.kali_runtime import KaliRuntime
from scraper_agent.security_env.tool_runner import ToolRunner, load_tool_catalog


class _FakeCompletedProcess:
    def __init__(self, stdout: str = "", stderr: str = "", returncode: int = 0) -> None:
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode


class TestResolveContainerIp:
    def test_parses_ip_from_docker_inspect_output(self) -> None:
        def fake_runner(argv):
            assert argv[0] == "docker"
            assert argv[1] == "inspect"
            return _FakeCompletedProcess(stdout="192.168.16.3\n")

        ip = resolve_container_ip("scraper_agent", "tarea1_scraper_internal", runner=fake_runner)

        assert ip == "192.168.16.3"

    def test_raises_when_docker_returns_empty(self) -> None:
        def fake_runner(argv):
            return _FakeCompletedProcess(stdout="", stderr="Error: No such object: scraper_agent")

        with pytest.raises(RuntimeError, match="No such object"):
            resolve_container_ip("scraper_agent", "tarea1_scraper_internal", runner=fake_runner)


class TestBuildSelfScanGuard:
    def test_authorizes_only_the_resolved_ip(self) -> None:
        guard = build_self_scan_guard("192.168.16.3")

        allowed = guard.authorize("192.168.16.3", "passive_recon")
        denied = guard.authorize("192.168.16.99", "passive_recon")

        assert allowed.allowed is True
        assert denied.allowed is False

    def test_only_authorizes_light_categories(self) -> None:
        guard = build_self_scan_guard("192.168.16.3")

        result = guard.authorize("192.168.16.3", "bounded_fuzzing")

        assert result.allowed is False


class TestRunSelfScan:
    @pytest.mark.asyncio
    async def test_runs_each_tool_and_collects_results(self) -> None:
        target_ip = "192.168.16.3"
        guard = build_self_scan_guard(target_ip)
        executor = FakeExecutor(stdout="22/tcp open ssh\n")
        tool_runner = ToolRunner(catalog=load_tool_catalog(), guard=guard, runtime=KaliRuntime(executor))

        results = await run_self_scan(tool_runner, target_ip, tool_ids=["curl_headers", "nmap_top100"])

        assert len(results) == 2
        assert {r["tool_id"] for r in results} == {"curl_headers", "nmap_top100"}
        assert all(r["exit_code"] == 0 for r in results)

    @pytest.mark.asyncio
    async def test_continues_after_one_tool_fails(self) -> None:
        """Un self-scan no debe abortar entero porque una herramienta falle
        -- el resto de los resultados siguen siendo útiles."""
        target_ip = "192.168.16.3"
        guard = build_self_scan_guard(target_ip)
        executor = FakeExecutor(stdout="ok\n")
        tool_runner = ToolRunner(catalog=load_tool_catalog(), guard=guard, runtime=KaliRuntime(executor))

        results = await run_self_scan(
            tool_runner, target_ip, tool_ids=["tool-que-no-existe", "curl_headers"]
        )

        assert len(results) == 2
        failed = next(r for r in results if r["tool_id"] == "tool-que-no-existe")
        assert "error" in failed
        ok = next(r for r in results if r["tool_id"] == "curl_headers")
        assert ok["exit_code"] == 0
