"""Tests de identificación pasiva del atacante (defense_env/attacker_recon.py).

Al detectarse una IP de origen de un ataque (ej. fuerza bruta SSH), corre
recon PASIVO (whois, dig) contra esa IP para ayudar a identificarla.
Deliberadamente solo `passive_recon` -- correr algo más agresivo contra la
IP de un atacante sería, en la práctica, contraatacar sin autorización
legal (fuera de alcance a propósito, ver docs/alcance-seguridad.md).
"""

from __future__ import annotations

import pytest

from conftest import FakeExecutor
from scraper_agent.defense_env.attacker_recon import build_attacker_recon_guard, identify_attacker
from scraper_agent.security_env.kali_runtime import KaliRuntime
from scraper_agent.security_env.tool_runner import ToolRunner, load_tool_catalog


class TestBuildAttackerReconGuard:
    def test_authorizes_only_passive_recon_on_attacker_ip(self) -> None:
        guard = build_attacker_recon_guard("203.0.113.7")

        passive = guard.authorize("203.0.113.7", "passive_recon")
        active = guard.authorize("203.0.113.7", "active_scanning")

        assert passive.allowed is True
        assert active.allowed is False

    def test_does_not_authorize_other_ips(self) -> None:
        guard = build_attacker_recon_guard("203.0.113.7")

        result = guard.authorize("198.51.100.5", "passive_recon")

        assert result.allowed is False


class TestIdentifyAttacker:
    @pytest.mark.asyncio
    async def test_runs_passive_tools_against_attacker_ip(self) -> None:
        attacker_ip = "203.0.113.7"
        guard = build_attacker_recon_guard(attacker_ip)
        executor = FakeExecutor(stdout="whois info here\n")
        tool_runner = ToolRunner(catalog=load_tool_catalog(), guard=guard, runtime=KaliRuntime(executor))

        results = await identify_attacker(tool_runner, attacker_ip, tool_ids=["whois"])

        assert len(results) == 1
        assert results[0]["tool_id"] == "whois"
        assert results[0]["exit_code"] == 0

    @pytest.mark.asyncio
    async def test_continues_after_one_tool_fails(self) -> None:
        attacker_ip = "203.0.113.7"
        guard = build_attacker_recon_guard(attacker_ip)
        executor = FakeExecutor(stdout="ok\n")
        tool_runner = ToolRunner(catalog=load_tool_catalog(), guard=guard, runtime=KaliRuntime(executor))

        results = await identify_attacker(tool_runner, attacker_ip, tool_ids=["tool-que-no-existe", "whois"])

        assert len(results) == 2
        failed = next(r for r in results if r["tool_id"] == "tool-que-no-existe")
        assert "error" in failed
