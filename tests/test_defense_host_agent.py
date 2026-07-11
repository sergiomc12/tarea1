"""Tests del agente continuo de defensa a nivel de SO
(defense_env/host_agent.py) — une host FIM + correlación de fuerza bruta
SSH + bloqueo automático (cierra el gap "solo manual" señalado en el
balance contra Wazuh) + identificación de atacante en un solo ciclo.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from conftest import FakeExecutor
from scraper_agent.defense_env.attacker_recon import build_attacker_recon_guard
from scraper_agent.defense_env.correlation import load_rules
from scraper_agent.defense_env.fim import compute_baseline
from scraper_agent.defense_env.host_agent import run_host_agent_cycle
from scraper_agent.defense_env.host_defense import FirewallTool
from scraper_agent.defense_env.models import FimWatchConfig
from scraper_agent.security_env.kali_runtime import KaliRuntime
from scraper_agent.security_env.tool_runner import ToolRunner, load_tool_catalog

RULES_DIR = Path(__file__).parent.parent / "src" / "scraper_agent" / "defense_env" / "rules" / "builtin"


class _FakeCompletedProcess:
    def __init__(self, returncode: int = 0, stderr: str = "") -> None:
        self.returncode = returncode
        self.stderr = stderr
        self.stdout = ""


def _brute_force_events(ip: str, count: int = 5) -> list[dict]:
    base = datetime(2026, 7, 9, 12, 0, 0, tzinfo=timezone.utc)
    return [
        {
            "timestamp": (base + timedelta(seconds=i * 10)).isoformat(),
            "allowed": False,
            "user": "root",
            "source_ip": ip,
            "port": 22,
        }
        for i in range(count)
    ]


@pytest.fixture
def empty_fim_config(tmp_path: Path) -> FimWatchConfig:
    watched = tmp_path / "watched"
    watched.mkdir()
    return FimWatchConfig(paths=[watched], critical_files=[])


class TestRunHostAgentCycle:
    @pytest.mark.asyncio
    async def test_no_alerts_when_everything_clean(self, tmp_path: Path, empty_fim_config: FimWatchConfig) -> None:
        baseline = compute_baseline(empty_fim_config)
        rules = load_rules(RULES_DIR)

        result = await run_host_agent_cycle(
            fim_config=empty_fim_config,
            fim_baseline=baseline,
            ssh_events=[],
            rules=rules,
            cases_path=tmp_path / "cases.json",
            firewall=FirewallTool(name="none", binary=""),
        )

        assert result["fim_alerts"] == []
        assert result["brute_force_alerts"] == []
        assert result["blocked_ips"] == []
        assert result["cases_opened"] == []

    @pytest.mark.asyncio
    async def test_brute_force_triggers_auto_block(self, tmp_path: Path, empty_fim_config: FimWatchConfig) -> None:
        baseline = compute_baseline(empty_fim_config)
        rules = load_rules(RULES_DIR)
        calls: list[list[str]] = []

        def fake_block_runner(argv):
            calls.append(argv)
            return _FakeCompletedProcess(returncode=0)

        result = await run_host_agent_cycle(
            fim_config=empty_fim_config,
            fim_baseline=baseline,
            ssh_events=_brute_force_events("203.0.113.7"),
            rules=rules,
            cases_path=tmp_path / "cases.json",
            firewall=FirewallTool(name="iptables", binary="iptables"),
            block_runner=fake_block_runner,
            auto_identify=False,
        )

        assert len(result["brute_force_alerts"]) == 1
        assert result["blocked_ips"] == ["203.0.113.7"]
        assert any("203.0.113.7" in " ".join(c) for c in calls)
        assert len(result["cases_opened"]) == 1

    @pytest.mark.asyncio
    async def test_auto_block_disabled_still_reports_alert(self, tmp_path: Path, empty_fim_config: FimWatchConfig) -> None:
        baseline = compute_baseline(empty_fim_config)
        rules = load_rules(RULES_DIR)

        result = await run_host_agent_cycle(
            fim_config=empty_fim_config,
            fim_baseline=baseline,
            ssh_events=_brute_force_events("203.0.113.7"),
            rules=rules,
            cases_path=tmp_path / "cases.json",
            firewall=FirewallTool(name="iptables", binary="iptables"),
            auto_block=False,
            auto_identify=False,
        )

        assert len(result["brute_force_alerts"]) == 1
        assert result["blocked_ips"] == []

    @pytest.mark.asyncio
    async def test_auto_identify_runs_recon_against_attacker(self, tmp_path: Path, empty_fim_config: FimWatchConfig) -> None:
        baseline = compute_baseline(empty_fim_config)
        rules = load_rules(RULES_DIR)

        def recon_tool_runner_factory(ip: str) -> ToolRunner:
            guard = build_attacker_recon_guard(ip)
            return ToolRunner(catalog=load_tool_catalog(), guard=guard, runtime=KaliRuntime(FakeExecutor(stdout="whois info\n")))

        result = await run_host_agent_cycle(
            fim_config=empty_fim_config,
            fim_baseline=baseline,
            ssh_events=_brute_force_events("203.0.113.7"),
            rules=rules,
            cases_path=tmp_path / "cases.json",
            firewall=FirewallTool(name="none", binary=""),
            auto_block=False,
            auto_identify=True,
            recon_tool_runner_factory=recon_tool_runner_factory,
        )

        assert "203.0.113.7" in result["recon_results"]
        assert len(result["recon_results"]["203.0.113.7"]) > 0

    @pytest.mark.asyncio
    async def test_below_threshold_does_not_block(self, tmp_path: Path, empty_fim_config: FimWatchConfig) -> None:
        baseline = compute_baseline(empty_fim_config)
        rules = load_rules(RULES_DIR)

        result = await run_host_agent_cycle(
            fim_config=empty_fim_config,
            fim_baseline=baseline,
            ssh_events=_brute_force_events("203.0.113.7", count=2),
            rules=rules,
            cases_path=tmp_path / "cases.json",
            firewall=FirewallTool(name="iptables", binary="iptables"),
        )

        assert result["brute_force_alerts"] == []
        assert result["blocked_ips"] == []

    @pytest.mark.asyncio
    async def test_host_fim_critical_alert_opens_case(self, tmp_path: Path) -> None:
        watched = tmp_path / "watched"
        watched.mkdir()
        (watched / "passwd").write_text("root:x:0:0::/root:/bin/bash\n", encoding="utf-8")
        config = FimWatchConfig(paths=[watched], critical_files=["passwd"])
        baseline = compute_baseline(config)
        (watched / "passwd").write_text("root:x:0:0::/root:/bin/bash\nevil:x:0:0::/root:/bin/bash\n", encoding="utf-8")
        rules = load_rules(RULES_DIR)

        result = await run_host_agent_cycle(
            fim_config=config,
            fim_baseline=baseline,
            ssh_events=[],
            rules=rules,
            cases_path=tmp_path / "cases.json",
            firewall=FirewallTool(name="none", binary=""),
        )

        assert len(result["fim_alerts"]) == 1
        assert result["fim_alerts"][0].severity == "critical"
        assert len(result["cases_opened"]) == 1
