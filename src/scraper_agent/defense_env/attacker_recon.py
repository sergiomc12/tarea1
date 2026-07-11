"""Identificación pasiva del atacante — al detectarse una IP de origen de
un ataque (ej. fuerza bruta SSH vía `defense_env/auth_log_parser.py` +
regla `ssh_brute_force`), corre recon PASIVO (whois, resolución DNS) contra
esa IP para ayudar a identificarla, reusando el catálogo de `security_env/`
(mismo patrón que `self_scan.py`, pero autorizando la IP del atacante en
vez de la propia infraestructura).

Deliberadamente solo `passive_recon` — nunca escaneo activo, fuzzing, ni
nada más agresivo contra la IP del atacante: eso sería, en la práctica,
contraatacar sin autorización legal sobre un objetivo que no es nuestro
(fuera de alcance a propósito, ver `docs/alcance-seguridad.md`). El
objetivo es identificar, no responder ofensivamente.
"""

from __future__ import annotations

from datetime import date

from scraper_agent.security_env.authorization_guard import AuthorizationGuard
from scraper_agent.security_env.exceptions import SecurityEnvError
from scraper_agent.security_env.models import AuthorizedTarget, ToolExecutionRequest
from scraper_agent.security_env.tool_runner import ToolRunner

DEFAULT_RECON_TOOLS = ["whois", "dig_a"]


def build_attacker_recon_guard(attacker_ip: str) -> AuthorizationGuard:
    """Autorización efímera en memoria, solo para esta IP puntual y solo
    para categoría `passive_recon`. Nunca toca
    `config/authorized_targets.yaml`."""
    entry = AuthorizedTarget(
        target=attacker_ip,
        type="ip",
        authorized_by="defense_env.attacker_recon",
        authorization_date=date.today(),
        evidence="recon pasivo sobre IP de origen de un ataque detectado -- identificación, no contraataque",
        allowed_categories=["passive_recon"],
    )
    return AuthorizationGuard([entry])


async def identify_attacker(
    tool_runner: ToolRunner,
    attacker_ip: str,
    *,
    tool_ids: list[str] = DEFAULT_RECON_TOOLS,
    session_id: str = "attacker-recon",
) -> list[dict]:
    """Corre cada `tool_id` de `tool_ids` (recon pasivo) contra
    `attacker_ip`. Una herramienta que falla no aborta el resto."""
    results: list[dict] = []
    for tool_id in tool_ids:
        try:
            result = await tool_runner.execute(
                ToolExecutionRequest(
                    tool_id=tool_id, host=attacker_ip, requested_by="attacker_recon", session_id=session_id
                )
            )
            results.append(
                {
                    "tool_id": tool_id,
                    "exit_code": result.exit_code,
                    "stdout": result.stdout[:2000],
                    "stderr": result.stderr[:500],
                }
            )
        except SecurityEnvError as exc:
            results.append({"tool_id": tool_id, "error": str(exc)})
    return results
