"""Agente continuo de defensa a nivel de SISTEMA OPERATIVO — une host FIM
(archivos críticos del SO), correlación de fuerza bruta SSH, respuesta
activa AUTOMÁTICA (`block_ip`) e identificación de atacante (recon pasivo)
en un solo ciclo. Pensado para correr en loop en el servidor Linux real
(ver `scripts/host_agent_loop.sh`).

Cierra el gap más importante señalado en el balance contra Wazuh: hasta
esta pieza, las acciones de `host_defense.py` (`block_ip`/`close_port`/
`kill_process`) eran 100% manuales — nadie las disparaba sola. Este agente
SÍ dispara `block_ip` automáticamente ante fuerza bruta SSH confirmada
(alerta de la regla `ssh_brute_force`, no cualquier alerta).
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from scraper_agent.defense_env.attacker_recon import DEFAULT_RECON_TOOLS, identify_attacker
from scraper_agent.defense_env.cases import auto_create_case_from_alert
from scraper_agent.defense_env.correlation import CorrelationRule, evaluate_rule
from scraper_agent.defense_env.fim import scan_for_drift
from scraper_agent.defense_env.host_defense import CommandRunner, FirewallTool, block_ip
from scraper_agent.defense_env.models import Alert, FimBaselineEntry, FimWatchConfig
from scraper_agent.security_env.tool_runner import ToolRunner

ReconToolRunnerFactory = Callable[[str], ToolRunner]


async def run_host_agent_cycle(
    *,
    fim_config: FimWatchConfig,
    fim_baseline: dict[str, FimBaselineEntry],
    ssh_events: list[dict],
    rules: list[CorrelationRule],
    cases_path: Path,
    firewall: FirewallTool,
    auto_block: bool = True,
    auto_identify: bool = True,
    block_runner: CommandRunner | None = None,
    recon_tool_runner_factory: ReconToolRunnerFactory | None = None,
    recon_tool_ids: list[str] = DEFAULT_RECON_TOOLS,
) -> dict:
    """Un ciclo completo: FIM del host + correlación (incluida
    `ssh_brute_force` si está en `rules`) + respuesta automática.

    Solo la regla `correlation.ssh_brute_force` dispara `block_ip`
    automático — otras alertas `critical` (ej. FIM) abren caso pero NO
    bloquean nada solas, porque no traen una IP de origen confiable en
    `evidence` para actuar sobre ella."""
    fim_alerts = scan_for_drift(fim_baseline, fim_config)

    brute_force_alerts: list[Alert] = []
    for rule in rules:
        if rule.logsource == "ssh_auth":
            brute_force_alerts.extend(evaluate_rule(rule, ssh_events))

    cases_opened: list[str] = []
    for alert in fim_alerts + brute_force_alerts:
        if alert.severity != "critical":
            continue
        case = auto_create_case_from_alert(cases_path, alert)
        if case is not None:
            cases_opened.append(case.id)

    blocked_ips: list[str] = []
    recon_results: dict[str, list[dict]] = {}
    for alert in brute_force_alerts:
        source_ip = alert.evidence.get("source_ip")
        if not source_ip:
            continue
        if auto_block:
            kwargs = {"runner": block_runner} if block_runner is not None else {}
            result = block_ip(source_ip, firewall=firewall, **kwargs)
            if result.success:
                blocked_ips.append(source_ip)
        if auto_identify and recon_tool_runner_factory is not None:
            tool_runner = recon_tool_runner_factory(source_ip)
            recon_results[source_ip] = await identify_attacker(tool_runner, source_ip, tool_ids=recon_tool_ids)

    return {
        "fim_alerts": fim_alerts,
        "brute_force_alerts": brute_force_alerts,
        "cases_opened": cases_opened,
        "blocked_ips": blocked_ips,
        "recon_results": recon_results,
    }
