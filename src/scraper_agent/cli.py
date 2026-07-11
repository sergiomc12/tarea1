"""CLI Typer del scraper agent."""

import asyncio
import json
from pathlib import Path
from typing import Optional

import typer
import yaml
from dotenv import load_dotenv

from scraper_agent.crawler.batch_runner import DEFAULT_MANIFEST
from scraper_agent.crawler.orchestrator import CrawlOrchestrator, _parse_cli_date
from scraper_agent.defense_env.active_response import trigger_lockdown
from scraper_agent.defense_env.alert_sink import append_alert
from scraper_agent.defense_env.attacker_recon import DEFAULT_RECON_TOOLS, build_attacker_recon_guard
from scraper_agent.defense_env.auth_log_parser import parse_ssh_auth_log
from scraper_agent.defense_env.canary import check_canaries, deploy_canaries
from scraper_agent.defense_env.cases import auto_create_case_from_alert, close_case, create_case, list_cases
from scraper_agent.defense_env.container_isolation import isolate_container
from scraper_agent.defense_env.correlation import load_events, load_rules, run_correlation
from scraper_agent.defense_env.fim import compute_baseline, missing_watched_paths, scan_for_drift
from scraper_agent.defense_env.host_agent import run_host_agent_cycle
from scraper_agent.defense_env.host_defense import (
    block_ip as host_block_ip,
    close_port as host_close_port,
    detect_firewall_tool,
    detect_os,
    kill_process as host_kill_process,
    list_connections as host_list_connections,
)
from scraper_agent.defense_env.models import FimBaselineEntry, FimWatchConfig
from scraper_agent.defense_env.ransomware_detector import detect_ransomware_pattern
from scraper_agent.defense_env.remediation import apply_remediation, suggest_remediation
from scraper_agent.defense_env.self_scan import (
    DEFAULT_SELF_SCAN_TOOLS,
    build_self_scan_guard,
    resolve_container_ip,
    run_self_scan,
)
from scraper_agent.models.schemas import AppConfig, DateRangeConfig
from scraper_agent.models.search_target import (
    SearchTarget,
    load_search_target,
    merge_search_target,
)
from scraper_agent.search.persist import write_consolidated_search, write_search_enriched_json
from scraper_agent.storage.schema_validator import validate_output
from scraper_agent.utils.logger import get_logger, setup_logging

DEFAULT_LOCKDOWN_PATH = Path("output/security/LOCKDOWN.json")
DEFAULT_CASES_PATH = Path("output/security/cases.json")
DEFAULT_ISOLATION_PATH = Path("output/security/ISOLATED.json")
# Nombre real de la red que crea `docker compose` para este proyecto
# (prefijo del directorio: "tarea1_" + nombre declarado en docker-compose.yml).
DEFAULT_ISOLATION_NETWORK = "tarea1_scraper_internal"
# scraper_agent es el único servicio con puerto expuesto al host (1212) --
# el objetivo más plausible de un atacante externo real, ver CHANGELOG.md.
# Nombre de CONTENEDOR real (no el nombre de servicio de compose): Docker
# Compose v2 nombra los contenedores "<proyecto>-<servicio>-<réplica>", y
# `docker inspect`/`network disconnect` necesitan ese nombre real, no el
# alias DNS interno "scraper_agent" que sí resuelve entre contenedores.
# Bug real encontrado corriendo `defense-self-scan` por primera vez: el
# default anterior ("scraper_agent" a secas) fallaba con "no such object"
# tanto acá como en el aislamiento de ransomware. Asume que nadie corrió
# `docker compose -p <otro-nombre>` (proyecto = nombre del directorio,
# "tarea1"); si se usa un nombre de proyecto distinto, pasar
# --isolation-container/--container explícito. Ver CHANGELOG.md.
DEFAULT_ISOLATION_CONTAINER = "tarea1-scraper_agent-1"
DEFAULT_CANARY_LOCATIONS = [
    Path("output/security/decoys/credentials_backup.yaml"),
    Path("output/security/decoys/authorized_targets_full.yaml"),
]
DEFAULT_CANARY_BASELINE_PATH = Path("output/security/canary_baseline.json")

app = typer.Typer(help="Agente de web scraping profesional")
logger = get_logger(__name__)


def load_config(path: Path, domain_override: str | None = None) -> AppConfig:
    """Carga config YAML y valida con Pydantic."""
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if domain_override:
        raw["domain"] = domain_override
    return AppConfig.model_validate(raw)


def _split_csv(value: str | None) -> list[str] | None:
    if value is None:
        return None
    items = [part.strip() for part in value.split(",") if part.strip()]
    return items or None


def _resolve_search_target(
    *,
    target_file: Path | None,
    label: str | None,
    keywords: str | None,
    exclude_keywords: str | None,
    patterns: str | None,
    match_in: str | None,
    min_score: float | None,
    require_all: bool,
    from_date: str | None,
    to_date: str | None,
) -> SearchTarget:
    base = load_search_target(target_file) if target_file else None
    date_range = None
    if from_date or to_date:
        date_range = DateRangeConfig(from_date=from_date, to_date=to_date)
    return merge_search_target(
        base,
        label=label,
        keywords=_split_csv(keywords),
        exclude_keywords=_split_csv(exclude_keywords),
        patterns=_split_csv(patterns),
        match_in=_split_csv(match_in),
        min_score=min_score,
        require_all=require_all if require_all else None,
        date_range=date_range,
    )


def _resolve_config_for_url(url: str, config: Path) -> Path:
    if config != Path("config/config.yaml"):
        return config
    host = url.replace("https://", "").replace("http://", "").split("/")[0]
    slug = host.replace(".", "_")
    candidate = Path("config/sites") / f"{slug}.yaml"
    if candidate.exists():
        return candidate
    legacy = Path("config") / f"{slug}.yaml"
    if legacy.exists():
        return legacy
    return config


@app.command("run")
def run_crawl(
    domain: Optional[str] = typer.Option(None, "--domain", "-d", help="URL semilla"),
    config: Path = typer.Option(Path("config/config.yaml"), "--config", "-c"),
    log_level: str = typer.Option("INFO", "--log-level"),
    ignore_robots: bool = typer.Option(False, "--ignore-robots", help="Ignorar robots.txt"),
    from_date: Optional[str] = typer.Option(None, "--from-date", help="ISO 8601 inicio (filtro publicacion)"),
    to_date: Optional[str] = typer.Option(None, "--to-date", help="ISO 8601 fin (filtro publicacion)"),
) -> None:
    """Ejecuta crawl recursivo del dominio."""
    load_dotenv()
    setup_logging(log_level)
    cfg = load_config(config, domain)
    logger.info("crawl_start", domain=cfg.domain)
    orchestrator = CrawlOrchestrator(
        cfg,
        ignore_robots=ignore_robots,
        date_from=_parse_cli_date(from_date),
        date_to=_parse_cli_date(to_date),
    )
    result = asyncio.run(orchestrator.run())
    typer.echo(
        f"Crawl finalizado: {result.total_pages_visited} paginas, "
        f"{result.total_articles_extracted} articulos -> {cfg.output.path}"
    )


@app.command("validate-config")
def validate_config_cmd(
    config: Path = typer.Option(Path("config/config.yaml"), "--config", "-c"),
) -> None:
    """Valida el archivo de configuración."""
    cfg = load_config(config)
    typer.echo(f"Config OK — dominio: {cfg.domain}, max_pages: {cfg.scope.max_pages}")


@app.command("validate-output")
def validate_output_cmd(
    file: Path = typer.Argument(..., help="JSON generado por el scraper"),
) -> None:
    """Valida un archivo de salida contra scraper-schema.json."""
    payload = json.loads(file.read_text(encoding="utf-8"))
    errors = validate_output(payload)
    if errors:
        typer.echo(f"INVALIDO ({len(errors)} errores):")
        for err in errors[:10]:
            typer.echo(f"  - {err}")
        raise typer.Exit(code=1)
    typer.echo("OK — cumple scraper-schema.json")


@app.command("export-html")
def export_html_cmd(
    file: Path = typer.Argument(..., help="JSON generado por el scraper"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Ruta HTML (default: mismo nombre .html)"),
) -> None:
    """Genera HTML legible desde un JSON del scraper."""
    from scraper_agent.storage.html_writer import write_html_report

    dest = write_html_report(file, output)
    typer.echo(f"HTML generado -> {dest}")


@app.command("search")
def search_cmd(
    input_json: Optional[Path] = typer.Option(
        None,
        "--input",
        help="JSON de corrida existente (búsqueda sin re-crawlear)",
    ),
    url: Optional[str] = typer.Option(None, "--url", help="URL semilla del medio (requiere crawl)"),
    config: Path = typer.Option(Path("config/config.yaml"), "--config", "-c"),
    target_file: Optional[Path] = typer.Option(None, "--target-file", help="YAML con objetivo"),
    label: Optional[str] = typer.Option(None, "--label", help="Nombre legible del objetivo"),
    keywords: Optional[str] = typer.Option(None, "--keywords", help="Términos separados por coma"),
    exclude: Optional[str] = typer.Option(None, "--exclude", help="Términos excluyentes"),
    patterns: Optional[str] = typer.Option(None, "--patterns", help="Regex separadas por coma"),
    match_in: Optional[str] = typer.Option(
        None,
        "--match-in",
        help="Campos: headline,excerpt,content_blocks,outbound_links,authors,taxonomy",
    ),
    min_score: float = typer.Option(0.3, "--min-score"),
    require_all: bool = typer.Option(False, "--require-all"),
    from_date: Optional[str] = typer.Option(None, "--from-date"),
    to_date: Optional[str] = typer.Option(None, "--to-date"),
    out: Optional[Path] = typer.Option(None, "--out", help="Ruta JSON de salida"),
    log_level: str = typer.Option("INFO", "--log-level"),
    ignore_robots: bool = typer.Option(False, "--ignore-robots"),
) -> None:
    """Crawl + búsqueda, o búsqueda sobre JSON ya generado con --input."""
    load_dotenv()
    setup_logging(log_level)

    if not input_json and not url:
        typer.echo("Debe indicar --input (JSON existente) o --url (crawl + búsqueda).")
        raise typer.Exit(code=1)

    if not target_file and not keywords and not patterns:
        typer.echo("Debe indicar --target-file o al menos --keywords / --patterns.")
        raise typer.Exit(code=1)

    target = _resolve_search_target(
        target_file=target_file,
        label=label or "busqueda",
        keywords=keywords,
        exclude_keywords=exclude,
        patterns=patterns,
        match_in=match_in,
        min_score=min_score,
        require_all=require_all,
        from_date=from_date,
        to_date=to_date,
    )

    from scraper_agent.storage.html_writer import write_html_report

    if input_json:
        if not input_json.exists():
            typer.echo(f"No existe el archivo: {input_json}")
            raise typer.Exit(code=1)
        json_path = write_search_enriched_json(input_json, target, output_path=out)
        html_path = write_html_report(json_path)
        payload = json.loads(json_path.read_text(encoding="utf-8"))
        hits = len(payload.get("search_results") or [])
        typer.echo(f"Búsqueda sobre JSON existente: {hits} coincidencias -> {json_path}")
        typer.echo(f"HTML -> {html_path}")
        return

    cfg_path = _resolve_config_for_url(url, config)
    cfg = load_config(cfg_path, url)
    if out:
        cfg = cfg.model_copy(update={"output": cfg.output.model_copy(update={"path": str(out)})})

    orchestrator = CrawlOrchestrator(
        cfg,
        ignore_robots=ignore_robots,
        date_from=_parse_cli_date(from_date),
        date_to=_parse_cli_date(to_date),
    )
    asyncio.run(orchestrator.run())

    json_path = Path(cfg.output.path)
    write_search_enriched_json(json_path, target)
    html_path = write_html_report(json_path)
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    hits = len(payload.get("search_results") or [])
    typer.echo(f"Búsqueda finalizada: {hits} coincidencias -> {json_path}")
    typer.echo(f"HTML -> {html_path}")


@app.command("run-all")
def run_all_cmd(
    manifest: Path = typer.Option(DEFAULT_MANIFEST, "--manifest", "-m", help="Manifiesto YAML de medios"),
    log_level: str = typer.Option("INFO", "--log-level"),
    ignore_robots: bool = typer.Option(False, "--ignore-robots", help="Ignorar robots.txt"),
    from_date: Optional[str] = typer.Option(None, "--from-date", help="ISO 8601 inicio (filtro publicacion)"),
    to_date: Optional[str] = typer.Option(None, "--to-date", help="ISO 8601 fin (filtro publicacion)"),
    skip_html: bool = typer.Option(False, "--skip-html", help="No generar HTML tras cada JSON"),
    target_file: Optional[Path] = typer.Option(None, "--target-file", help="Objetivo de búsqueda YAML"),
    keywords: Optional[str] = typer.Option(None, "--keywords", help="Términos para búsqueda cruzada"),
    min_score: float = typer.Option(0.3, "--min-score"),
) -> None:
    """Scrapea todos los medios del manifiesto (JSON + HTML por sitio)."""
    load_dotenv()
    setup_logging(log_level)
    date_from = _parse_cli_date(from_date)
    date_to = _parse_cli_date(to_date)

    from scraper_agent.crawler.batch_runner import load_sites_manifest, run_site_crawl
    import asyncio

    search_target = None
    if target_file or keywords:
        search_target = _resolve_search_target(
            target_file=target_file,
            label=target_file.stem if target_file else "busqueda_cruzada",
            keywords=keywords,
            exclude_keywords=None,
            patterns=None,
            match_in=None,
            min_score=min_score,
            require_all=False,
            from_date=from_date,
            to_date=to_date,
        )

    entries = load_sites_manifest(manifest)
    typer.echo(f"Iniciando crawl de {len(entries)} medios...")
    consolidated_payloads: list[tuple[str, dict]] = []

    async def _run() -> None:
        for entry in entries:
            typer.echo(f"\n--- {entry.name} ({entry.domain}) ---")
            result = await run_site_crawl(
                entry,
                date_from=date_from,
                date_to=date_to,
                ignore_robots=ignore_robots,
                search_target=search_target,
            )
            if result.error:
                typer.echo(f"ERROR: {result.error}")
            else:
                typer.echo(
                    f"{result.pages_visited} paginas, {result.articles_extracted} articulos "
                    f"-> {result.json_path}"
                )
                if search_target:
                    typer.echo(f"Coincidencias: {result.search_hits}")
                if not skip_html and result.html_path:
                    typer.echo(f"HTML -> {result.html_path}")
                status = "OK schema" if result.schema_ok else "schema con advertencias"
                typer.echo(status)
                if result.json_path.exists():
                    payload = json.loads(result.json_path.read_text(encoding="utf-8"))
                    consolidated_payloads.append((entry.domain, payload))

    asyncio.run(_run())

    if search_target and consolidated_payloads:
        consolidated = write_consolidated_search(consolidated_payloads, search_target)
        typer.echo(f"\nConsolidado -> {consolidated}")

    typer.echo("\nCrawl por lotes finalizado.")


@app.command("serve")
def serve_cmd(
    host: str = typer.Option("0.0.0.0", "--host"),
    port: int = typer.Option(8000, "--port", help="Puerto interno (1212 en docker-compose)"),
    log_level: str = typer.Option("INFO", "--log-level"),
) -> None:
    """Levanta el endpoint único de chat (POST /chat, SSE)."""
    import uvicorn

    load_dotenv()
    setup_logging(log_level)
    typer.echo(f"Chat API en http://{host}:{port}/chat (health: /health)")
    uvicorn.run(
        "scraper_agent.api.chat_endpoint:create_app",
        factory=True,
        host=host,
        port=port,
        log_level=log_level.lower(),
    )


def _load_fim_watch_config(path: Path) -> FimWatchConfig:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return FimWatchConfig.model_validate(raw)


@app.command("fim-baseline")
def fim_baseline_cmd(
    config: Path = typer.Option(
        Path("config/defense/fim_watch.yaml"), "--config", "-c", help="Config de paths vigilados"
    ),
    output: Path = typer.Option(
        Path("output/security/fim_baseline.json"), "--output", "-o", help="Ruta del baseline generado"
    ),
) -> None:
    """Calcula (o recalcula) el baseline de integridad de archivos vigilados."""
    watch_config = _load_fim_watch_config(config)

    missing = missing_watched_paths(watch_config)
    for path in missing:
        typer.echo(f"ADVERTENCIA: ruta vigilada no encontrada (¿falta montarla en el contenedor?): {path}")

    baseline = compute_baseline(watch_config)

    output.parent.mkdir(parents=True, exist_ok=True)
    payload = {path: entry.model_dump() for path, entry in baseline.items()}
    output.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    typer.echo(f"Baseline generado: {len(baseline)} archivo(s) -> {output}")


@app.command("fim-scan")
def fim_scan_cmd(
    config: Path = typer.Option(
        Path("config/defense/fim_watch.yaml"), "--config", "-c", help="Config de paths vigilados"
    ),
    baseline: Path = typer.Option(
        Path("output/security/fim_baseline.json"), "--baseline", "-b", help="Baseline generado por fim-baseline"
    ),
    alerts_out: Path = typer.Option(
        Path("output/security/fim_alerts.jsonl"), "--alerts-out", help="Ruta JSONL donde persistir alertas nuevas"
    ),
    auto_lockdown: bool = typer.Option(
        True,
        "--auto-lockdown/--no-auto-lockdown",
        help="Fase 3: disparar lockdown automático (kill-switch) ante alerta critical",
    ),
    lockdown_path: Path = typer.Option(DEFAULT_LOCKDOWN_PATH, "--lockdown-path", hidden=True),
    cases_path: Path = typer.Option(DEFAULT_CASES_PATH, "--cases-path", hidden=True),
    auto_isolate: bool = typer.Option(
        True,
        "--auto-isolate/--no-auto-isolate",
        help="Detector de ransomware: aislar de red el contenedor ante ráfaga de cambios masivos",
    ),
    isolation_path: Path = typer.Option(DEFAULT_ISOLATION_PATH, "--isolation-path", hidden=True),
    isolation_network: str = typer.Option(DEFAULT_ISOLATION_NETWORK, "--isolation-network", hidden=True),
    isolation_container: str = typer.Option(DEFAULT_ISOLATION_CONTAINER, "--isolation-container", hidden=True),
) -> None:
    """Compara el estado actual de los archivos vigilados contra el baseline.

    Exit code 1 si hay alguna alerta high/critical (para uso en cron/CI)."""
    if not baseline.exists():
        typer.echo(f"No existe baseline en {baseline} — corré 'fim-baseline' primero.")
        raise typer.Exit(code=2)

    watch_config = _load_fim_watch_config(config)
    for path in missing_watched_paths(watch_config):
        typer.echo(f"ADVERTENCIA: ruta vigilada no encontrada (¿falta montarla en el contenedor?): {path}")

    raw_baseline = json.loads(baseline.read_text(encoding="utf-8"))
    baseline_entries = {path: FimBaselineEntry.model_validate(entry) for path, entry in raw_baseline.items()}

    alerts = scan_for_drift(baseline_entries, watch_config)

    if not alerts:
        typer.echo("Sin drift — todo coincide con el baseline.")
        return

    has_high_severity = False
    for alert in alerts:
        append_alert(alert, alerts_out)
        typer.echo(f"[{alert.severity}] {alert.drift_type.value}: {alert.description}")
        if alert.severity in ("high", "critical"):
            has_high_severity = True
        if alert.severity == "critical":
            case = auto_create_case_from_alert(cases_path, alert)
            if case is not None:
                typer.echo(f"  -> Caso abierto: {case.id} ({cases_path})")
            if auto_lockdown:
                trigger_lockdown(f"fim-scan: {alert.description}", lockdown_path)
                typer.echo(f"  -> LOCKDOWN activado ({lockdown_path}) — ver 'defense-clear-lockdown' para levantarlo")

    # Patrón ransomware: distinto de las alertas individuales de arriba --
    # esto responde a un atacante EXTERNO comprometiendo la infraestructura,
    # no a que tarea1 mismo haya sido usado de arma, así que la respuesta es
    # aislar de red el contenedor, no el lockdown de la Fase 3. Ver
    # CHANGELOG.md (corrección señalada por el usuario).
    ransomware_alert = detect_ransomware_pattern(alerts)
    if ransomware_alert is not None:
        append_alert(ransomware_alert, alerts_out)
        typer.echo(f"\n[{ransomware_alert.severity}] {ransomware_alert.rule_id}: {ransomware_alert.description}")
        case = auto_create_case_from_alert(cases_path, ransomware_alert)
        if case is not None:
            typer.echo(f"  -> Caso abierto: {case.id} ({cases_path})")
        if auto_isolate:
            record = isolate_container(
                isolation_container,
                network=isolation_network,
                reason=ransomware_alert.description,
                state_path=isolation_path,
            )
            typer.echo(
                f"  -> Contenedor '{isolation_container}' desconectado de '{isolation_network}' "
                f"({isolation_path}) — ver 'defense-clear-lockdown' no aplica acá, usar "
                f"'defense-reconnect --yes' para restaurar tras investigar."
            )
            if record["docker_exit_code"] != 0:
                typer.echo(f"  ADVERTENCIA: docker network disconnect falló: {record['docker_stderr']}")

    typer.echo(f"\n{len(alerts)} alerta(s) -> {alerts_out}")
    if has_high_severity or ransomware_alert is not None:
        raise typer.Exit(code=1)


@app.command("defense-correlate")
def defense_correlate_cmd(
    rules_dir: Path = typer.Option(
        Path("src/scraper_agent/defense_env/rules/builtin"),
        "--rules-dir",
        help="Directorio con reglas *.yaml (ver defense_env/correlation.py)",
    ),
    tool_audit: Path = typer.Option(
        Path("output/security/tool_audit.jsonl"),
        "--tool-audit",
        help="Log de auditoría de tool_runner (logsource 'tool_audit')",
    ),
    alerts_out: Path = typer.Option(
        Path("output/security/correlation_alerts.jsonl"),
        "--alerts-out",
        help="Ruta JSONL donde persistir alertas nuevas",
    ),
    auto_lockdown: bool = typer.Option(
        True,
        "--auto-lockdown/--no-auto-lockdown",
        help="Fase 3: disparar lockdown automático (kill-switch) ante alerta critical",
    ),
    lockdown_path: Path = typer.Option(DEFAULT_LOCKDOWN_PATH, "--lockdown-path", hidden=True),
    cases_path: Path = typer.Option(DEFAULT_CASES_PATH, "--cases-path", hidden=True),
) -> None:
    """Corre las reglas de correlación (Fase 2, defense_env/) contra los logs
    propios. Exit code 1 si hay alguna alerta high/critical."""
    rules = load_rules(rules_dir)
    events_by_logsource = {"tool_audit": load_events(tool_audit)}

    alerts = run_correlation(rules, events_by_logsource)

    if not alerts:
        typer.echo("Sin coincidencias — ninguna regla disparó.")
        return

    has_high_severity = False
    for alert in alerts:
        append_alert(alert, alerts_out)
        typer.echo(f"[{alert.severity}] {alert.rule_id}: {alert.description}")
        if alert.severity in ("high", "critical"):
            has_high_severity = True
        if alert.severity == "critical":
            case = auto_create_case_from_alert(cases_path, alert)
            if case is not None:
                typer.echo(f"  -> Caso abierto: {case.id} ({cases_path})")
            if auto_lockdown:
                trigger_lockdown(f"defense-correlate: {alert.description}", lockdown_path)
                typer.echo(f"  -> LOCKDOWN activado ({lockdown_path}) — ver 'defense-clear-lockdown' para levantarlo")

    typer.echo(f"\n{len(alerts)} alerta(s) -> {alerts_out}")
    if has_high_severity:
        raise typer.Exit(code=1)


@app.command("defense-status")
def defense_status_cmd(
    lockdown_path: Path = typer.Option(DEFAULT_LOCKDOWN_PATH, "--lockdown-path"),
) -> None:
    """Muestra si hay un lockdown activo (Fase 3) y por qué."""
    from scraper_agent.defense_env.active_response import is_locked_down, read_lockdown_reason

    if not is_locked_down(lockdown_path):
        typer.echo("Sin lockdown activo — ejecución ofensiva habilitada normalmente.")
        return
    typer.echo(f"LOCKDOWN ACTIVO: {read_lockdown_reason(lockdown_path)}")
    typer.echo("Toda ejecución de herramientas ofensivas está denegada hasta 'defense-clear-lockdown'.")
    raise typer.Exit(code=1)


@app.command("defense-clear-lockdown")
def defense_clear_lockdown_cmd(
    lockdown_path: Path = typer.Option(DEFAULT_LOCKDOWN_PATH, "--lockdown-path"),
    confirm: bool = typer.Option(
        False, "--yes", help="Confirmación explícita — requerida, no se levanta un lockdown por accidente"
    ),
) -> None:
    """Levanta un lockdown activo. Acción humana explícita, a propósito sin
    auto-recuperación (ver defense_env/active_response.py)."""
    from scraper_agent.defense_env.active_response import clear_lockdown, is_locked_down, read_lockdown_reason

    if not is_locked_down(lockdown_path):
        typer.echo("No hay ningún lockdown activo.")
        return
    if not confirm:
        typer.echo(f"Lockdown activo: {read_lockdown_reason(lockdown_path)}")
        typer.echo("Confirmá con --yes tras investigar la causa antes de levantarlo.")
        raise typer.Exit(code=1)
    clear_lockdown(lockdown_path)
    typer.echo("Lockdown levantado.")


@app.command("defense-isolation-status")
def defense_isolation_status_cmd(
    isolation_path: Path = typer.Option(DEFAULT_ISOLATION_PATH, "--isolation-path"),
) -> None:
    """Muestra si hay un contenedor aislado de red (respuesta ante patrón
    ransomware) y por qué. Distinto de `defense-status` (lockdown de la
    Fase 3, que detiene a `tarea1` mismo, no a un atacante externo)."""
    from scraper_agent.defense_env.container_isolation import is_isolated

    if not is_isolated(isolation_path):
        typer.echo("Sin contenedor aislado — red normal.")
        return
    data = json.loads(isolation_path.read_text(encoding="utf-8"))
    typer.echo(f"CONTENEDOR AISLADO: {data['container']} (red: {data['network']})")
    typer.echo(f"Motivo: {data['reason']}")
    typer.echo("Usar 'defense-reconnect --yes' tras investigar la causa.")
    raise typer.Exit(code=1)


@app.command("defense-reconnect")
def defense_reconnect_cmd(
    isolation_path: Path = typer.Option(DEFAULT_ISOLATION_PATH, "--isolation-path"),
    network: str = typer.Option(DEFAULT_ISOLATION_NETWORK, "--network"),
    confirm: bool = typer.Option(
        False, "--yes", help="Confirmación explícita — requerida, no se reconecta un contenedor por accidente"
    ),
) -> None:
    """Reconecta a la red un contenedor aislado. Acción humana explícita, a
    propósito sin auto-recuperación (ver defense_env/container_isolation.py)."""
    from scraper_agent.defense_env.container_isolation import is_isolated, reconnect_container

    if not is_isolated(isolation_path):
        typer.echo("No hay ningún contenedor aislado.")
        return
    data = json.loads(isolation_path.read_text(encoding="utf-8"))
    if not confirm:
        typer.echo(f"Contenedor aislado: {data['container']} — motivo: {data['reason']}")
        typer.echo("Confirmá con --yes tras investigar la causa antes de reconectarlo.")
        raise typer.Exit(code=1)
    reconnect_container(data["container"], network=network, state_path=isolation_path)
    typer.echo(f"Contenedor '{data['container']}' reconectado a '{network}'.")


@app.command("defense-case-list")
def defense_case_list_cmd(
    status: Optional[str] = typer.Option(
        None, "--status", help="Filtrar por open|investigating|closed (default: todos)"
    ),
    cases_path: Path = typer.Option(DEFAULT_CASES_PATH, "--cases-path"),
) -> None:
    """Lista casos (Fase 4 — gestión de investigaciones)."""
    cases = list_cases(cases_path, status=status)
    if not cases:
        typer.echo("Sin casos" + (f" con status={status}" if status else "") + ".")
        return
    for case in cases:
        typer.echo(f"[{case.status}] {case.id[:8]}  ({case.severity})  {case.title}")


@app.command("defense-case-create")
def defense_case_create_cmd(
    title: str = typer.Argument(..., help="Título del caso"),
    severity: str = typer.Option("medium", "--severity", help="low|medium|high|critical"),
    cases_path: Path = typer.Option(DEFAULT_CASES_PATH, "--cases-path"),
) -> None:
    """Abre un caso manualmente (para lo que las reglas automáticas no cubren todavía)."""
    case = create_case(cases_path, title=title, severity=severity, alert_ids=[])
    typer.echo(f"Caso creado: {case.id}")


@app.command("defense-case-close")
def defense_case_close_cmd(
    case_id: str = typer.Argument(..., help="ID (o prefijo) del caso"),
    note: str = typer.Option("", "--note", help="Nota de cierre (ej. causa raíz, falso positivo)"),
    cases_path: Path = typer.Option(DEFAULT_CASES_PATH, "--cases-path"),
) -> None:
    """Cierra un caso."""
    matches = [c for c in list_cases(cases_path) if c.id == case_id or c.id.startswith(case_id)]
    if not matches:
        typer.echo(f"No existe ningún caso con id/prefijo {case_id!r}.")
        raise typer.Exit(code=1)
    if len(matches) > 1:
        typer.echo(f"Prefijo ambiguo — coincide con {len(matches)} casos, usá el id completo.")
        raise typer.Exit(code=1)
    closed = close_case(cases_path, matches[0].id, note=note)
    typer.echo(f"Caso {closed.id} cerrado.")


@app.command("defense-canary-deploy")
def defense_canary_deploy_cmd(
    baseline_out: Path = typer.Option(DEFAULT_CANARY_BASELINE_PATH, "--baseline-out"),
) -> None:
    """Despliega los archivos señuelo (honeytokens) y guarda su baseline.
    Idempotente — no pisa un canary ya desplegado ni lo que le hayan tocado."""
    watch_config = deploy_canaries(DEFAULT_CANARY_LOCATIONS)
    baseline = compute_baseline(watch_config)

    baseline_out.parent.mkdir(parents=True, exist_ok=True)
    payload = {"paths": [str(p) for p in DEFAULT_CANARY_LOCATIONS], "baseline": {k: v.model_dump() for k, v in baseline.items()}}
    baseline_out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    typer.echo(f"{len(DEFAULT_CANARY_LOCATIONS)} canary(s) desplegado(s) -> {baseline_out}")


@app.command("defense-canary-check")
def defense_canary_check_cmd(
    baseline_in: Path = typer.Option(DEFAULT_CANARY_BASELINE_PATH, "--baseline-in"),
    alerts_out: Path = typer.Option(
        Path("output/security/canary_alerts.jsonl"), "--alerts-out"
    ),
) -> None:
    """Chequea si algún canary fue tocado. Exit code 1 si se disparó alguno."""
    if not baseline_in.exists():
        typer.echo(f"No existe baseline de canaries en {baseline_in} — corré 'defense-canary-deploy' primero.")
        raise typer.Exit(code=2)

    payload = json.loads(baseline_in.read_text(encoding="utf-8"))
    locations = [Path(p) for p in payload["paths"]]
    baseline = {k: FimBaselineEntry.model_validate(v) for k, v in payload["baseline"].items()}
    watch_config = FimWatchConfig(paths=locations, critical_files=[p.name for p in locations])

    alerts = check_canaries(baseline, watch_config)

    if not alerts:
        typer.echo("Ningún canary fue tocado.")
        return

    for alert in alerts:
        append_alert(alert, alerts_out)
        typer.echo(f"[{alert.severity}] {alert.description}")

    typer.echo(f"\n{len(alerts)} canary(s) disparado(s) -> {alerts_out}")
    raise typer.Exit(code=1)


@app.command("defense-self-scan")
def defense_self_scan_cmd(
    target_container: str = typer.Option(
        DEFAULT_ISOLATION_CONTAINER, "--container", help="Contenedor propio a autoescanear"
    ),
    network: str = typer.Option(DEFAULT_ISOLATION_NETWORK, "--network"),
    tools: str = typer.Option(
        ",".join(DEFAULT_SELF_SCAN_TOOLS), "--tools", help="tool_id separados por coma"
    ),
    kali_container: str = typer.Option(
        "kali-tools", "--kali-container", help="Contenedor Kali real que ejecuta las herramientas"
    ),
    results_out: Path = typer.Option(
        Path("output/security/self_scan_results.json"), "--results-out"
    ),
) -> None:
    """Self-scan defensivo (Fase exploits): corre el catálogo OFENSIVO de
    security_env contra la propia infraestructura (resolviendo su IP real
    vía `docker inspect`) en vez de un objetivo externo. Ver
    defense_env/self_scan.py.

    A propósito NO usa `resolve_command_executor()` (que cae en silencio a
    `FakeExecutor` si falta `KALI_CONTAINER` en el entorno) -- bug real
    encontrado corriendo esto por primera vez: sin la variable seteada, el
    comando "funcionaba" pero devolvía resultados de prueba fabricados
    (`stdout: "ok"`), una falsa sensación de seguridad peor que un error
    explícito. Acá siempre se construye `DockerCliExecutor` directo: si
    Kali no está disponible, falla ruidosamente en vez de simular éxito."""
    from scraper_agent.security_env.docker_executor import DockerCliExecutor
    from scraper_agent.security_env.kali_runtime import KaliRuntime
    from scraper_agent.security_env.tool_runner import ToolRunner, load_tool_catalog

    try:
        target_ip = resolve_container_ip(target_container, network)
    except RuntimeError as exc:
        typer.echo(f"No se pudo resolver la IP de '{target_container}': {exc}")
        raise typer.Exit(code=2) from exc

    typer.echo(f"Self-scan contra {target_container} ({target_ip}) en la red {network}...")

    guard = build_self_scan_guard(target_ip)
    tool_runner = ToolRunner(
        catalog=load_tool_catalog(), guard=guard, runtime=KaliRuntime(DockerCliExecutor(kali_container))
    )
    tool_ids = [t.strip() for t in tools.split(",") if t.strip()]

    results = asyncio.run(run_self_scan(tool_runner, target_ip, tool_ids=tool_ids))

    results_out.parent.mkdir(parents=True, exist_ok=True)
    results_out.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")

    for r in results:
        if "error" in r:
            typer.echo(f"  [FALLO] {r['tool_id']}: {r['error']}")
        else:
            typer.echo(f"  [{r['exit_code']}] {r['tool_id']}")

    typer.echo(f"\nResultados -> {results_out} (revisión humana — este comando no interpreta el hallazgo por vos)")


@app.command("defense-host-detect")
def defense_host_detect_cmd() -> None:
    """Detecta el sistema operativo y la herramienta de firewall disponible
    en ESTE host (no un contenedor). Correr esto primero en el servidor
    real antes de usar cualquier otro comando defense-host-*."""
    os_info = detect_os()
    typer.echo(f"Sistema operativo: {'Linux' if os_info.is_linux else 'no-Linux/desconocido'}")
    if os_info.is_linux:
        typer.echo(f"  ID: {os_info.id} (ID_LIKE: {os_info.id_like or '-'})")
        typer.echo(f"  Nombre: {os_info.name}")
        typer.echo(f"  Versión: {os_info.version_id or '-'}")

    firewall = detect_firewall_tool()
    typer.echo(f"Herramienta de firewall detectada: {firewall.name}")
    if firewall.name == "none":
        typer.echo("  ADVERTENCIA: sin firewalld/nftables/iptables disponibles — block_ip/close_port no funcionarán.")

    if not os_info.is_linux:
        typer.echo("\nADVERTENCIA: esto no parece un host Linux — defense-host-* está pensado para servidores Linux reales.")


@app.command("defense-host-block-ip")
def defense_host_block_ip_cmd(
    ip: str = typer.Argument(..., help="IP a bloquear a nivel de sistema operativo"),
    reason: str = typer.Option("", "--reason", help="Motivo (para el registro humano, no se persiste automáticamente)"),
    confirm: bool = typer.Option(
        False, "--yes", help="Confirmación explícita — acción real e IRREVERSIBLE automáticamente sobre el host"
    ),
) -> None:
    """Bloquea TODO el tráfico entrante de `ip` a nivel de sistema
    operativo (firewalld/nftables/iptables, el que esté disponible). Acción
    real sobre el host — no hay reversión automática."""
    if not confirm:
        typer.echo(f"Esto bloquearía {ip} a nivel de SISTEMA OPERATIVO (no un contenedor). Confirmá con --yes.")
        raise typer.Exit(code=1)
    firewall = detect_firewall_tool()
    result = host_block_ip(ip, firewall=firewall)
    typer.echo(f"[{'OK' if result.success else 'FALLO'}] {result.action} {result.target} vía {result.tool_used}")
    if result.detail:
        typer.echo(f"  {result.detail}")
    if reason:
        typer.echo(f"  Motivo: {reason}")
    if not result.success:
        raise typer.Exit(code=1)


@app.command("defense-host-close-port")
def defense_host_close_port_cmd(
    port: int = typer.Argument(..., help="Puerto a cerrar"),
    protocol: str = typer.Option("tcp", "--protocol", help="tcp|udp"),
    confirm: bool = typer.Option(False, "--yes", help="Confirmación explícita"),
) -> None:
    """Cierra `port` a nivel de sistema operativo."""
    if not confirm:
        typer.echo(f"Esto cerraría el puerto {port}/{protocol} a nivel de SISTEMA OPERATIVO. Confirmá con --yes.")
        raise typer.Exit(code=1)
    firewall = detect_firewall_tool()
    result = host_close_port(port, protocol=protocol, firewall=firewall)
    typer.echo(f"[{'OK' if result.success else 'FALLO'}] {result.action} {result.target} vía {result.tool_used}")
    if result.detail:
        typer.echo(f"  {result.detail}")
    if not result.success:
        raise typer.Exit(code=1)


@app.command("defense-host-kill-process")
def defense_host_kill_process_cmd(
    pid: Optional[int] = typer.Option(None, "--pid"),
    name: Optional[str] = typer.Option(None, "--name", help="Coincide contra la línea de comando completa (pkill -f)"),
    confirm: bool = typer.Option(False, "--yes", help="Confirmación explícita"),
) -> None:
    """Mata un proceso por --pid o --name (se necesita exactamente uno)."""
    if pid is None and not name:
        typer.echo("Necesitás pasar --pid o --name.")
        raise typer.Exit(code=2)
    if not confirm:
        target = f"pid {pid}" if pid is not None else f"nombre {name!r}"
        typer.echo(f"Esto mataría el proceso ({target}) a nivel de SISTEMA OPERATIVO. Confirmá con --yes.")
        raise typer.Exit(code=1)
    result = host_kill_process(pid=pid, name=name)
    typer.echo(f"[{'OK' if result.success else 'FALLO'}] {result.action} {result.target}")
    if result.detail:
        typer.echo(f"  {result.detail}")
    if not result.success:
        raise typer.Exit(code=1)


@app.command("defense-host-connections")
def defense_host_connections_cmd() -> None:
    """Lista conexiones de red activas del host (`ss`/`netstat`, el que
    esté disponible). Salida cruda para revisión humana — sin parser
    estructurado verificado (ver limitación en defense_env/host_defense.py)."""
    connections = host_list_connections()
    if not connections:
        typer.echo("Sin conexiones listadas (¿ss/netstat no disponibles, o sin conexiones activas?).")
        return
    for conn in connections:
        typer.echo(conn["raw"])


@app.command("defense-host-agent-cycle")
def defense_host_agent_cycle_cmd(
    fim_config_path: Path = typer.Option(Path("config/defense/host_fim_watch.yaml"), "--fim-config"),
    fim_baseline_path: Path = typer.Option(
        Path("output/security/host_fim_baseline.json"), "--fim-baseline"
    ),
    ssh_auth_log: Path = typer.Option(Path("/var/log/secure"), "--ssh-auth-log", help="RHEL/CentOS: /var/log/secure"),
    rules_dir: Path = typer.Option(
        Path("src/scraper_agent/defense_env/rules/builtin"), "--rules-dir"
    ),
    cases_path: Path = typer.Option(DEFAULT_CASES_PATH, "--cases-path"),
    kali_container: str = typer.Option("kali-tools", "--kali-container"),
    auto_block: bool = typer.Option(
        True, "--auto-block/--no-auto-block", help="Bloquear IP automáticamente ante fuerza bruta SSH confirmada"
    ),
    auto_identify: bool = typer.Option(
        True, "--auto-identify/--no-auto-identify", help="Recon pasivo automático sobre la IP del atacante"
    ),
) -> None:
    """Un ciclo del agente continuo de defensa a nivel de sistema operativo:
    FIM del host + correlación de fuerza bruta SSH + bloqueo automático +
    identificación de atacante. Pensado para correr en loop
    (`scripts/host_agent_loop.sh`) en el servidor Linux real — ver
    limitación honesta en defense_env/host_agent.py (no verificado contra
    un CentOS/RHEL real en esta sesión)."""
    from scraper_agent.security_env.docker_executor import DockerCliExecutor
    from scraper_agent.security_env.kali_runtime import KaliRuntime
    from scraper_agent.security_env.tool_runner import ToolRunner, load_tool_catalog

    if not fim_config_path.exists():
        typer.echo(f"No existe {fim_config_path}.")
        raise typer.Exit(code=2)
    fim_config = _load_fim_watch_config(fim_config_path)

    if not fim_baseline_path.exists():
        typer.echo(f"No existe baseline en {fim_baseline_path} — generándolo ahora.")
        fim_baseline = compute_baseline(fim_config)
        fim_baseline_path.parent.mkdir(parents=True, exist_ok=True)
        fim_baseline_path.write_text(
            json.dumps({k: v.model_dump() for k, v in fim_baseline.items()}, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    else:
        raw = json.loads(fim_baseline_path.read_text(encoding="utf-8"))
        fim_baseline = {k: FimBaselineEntry.model_validate(v) for k, v in raw.items()}

    ssh_events = parse_ssh_auth_log(ssh_auth_log)
    rules = load_rules(rules_dir)
    firewall = detect_firewall_tool()

    def recon_tool_runner_factory(ip: str) -> ToolRunner:
        guard = build_attacker_recon_guard(ip)
        return ToolRunner(catalog=load_tool_catalog(), guard=guard, runtime=KaliRuntime(DockerCliExecutor(kali_container)))

    result = asyncio.run(
        run_host_agent_cycle(
            fim_config=fim_config,
            fim_baseline=fim_baseline,
            ssh_events=ssh_events,
            rules=rules,
            cases_path=cases_path,
            firewall=firewall,
            auto_block=auto_block,
            auto_identify=auto_identify,
            recon_tool_runner_factory=recon_tool_runner_factory if auto_identify else None,
            recon_tool_ids=DEFAULT_RECON_TOOLS,
        )
    )

    typer.echo(f"FIM del host: {len(result['fim_alerts'])} alerta(s)")
    typer.echo(f"Fuerza bruta SSH: {len(result['brute_force_alerts'])} alerta(s)")
    for ip in result["blocked_ips"]:
        typer.echo(f"  -> IP bloqueada automáticamente: {ip}")
    for case_id in result["cases_opened"]:
        typer.echo(f"  -> Caso abierto: {case_id}")
    for ip, recon in result["recon_results"].items():
        typer.echo(f"  -> Recon sobre {ip}: {len(recon)} herramienta(s) corrida(s)")

    if result["fim_alerts"] or result["brute_force_alerts"]:
        raise typer.Exit(code=1)


def _build_finding(
    detail: Optional[str],
    package_manager: str,
    setting: Optional[str],
    current_value: Optional[str],
    source: str,
) -> dict:
    finding: dict = {"package_manager": package_manager, "source": source}
    if detail:
        finding["detail"] = detail
    if setting:
        finding["setting"] = setting
    if current_value:
        finding["current_value"] = current_value
    return finding


@app.command("defense-remediate-suggest")
def defense_remediate_suggest_cmd(
    pattern_id: str = typer.Argument(..., help="Ej. outdated_openssh, weak_sshd_config"),
    detail: Optional[str] = typer.Option(None, "--detail", help="Detalle del hallazgo (ej. versión detectada)"),
    package_manager: str = typer.Option("dnf", "--package-manager", help="dnf|yum|apt"),
    setting: Optional[str] = typer.Option(None, "--setting", help="Para weak_sshd_config: nombre de la directiva"),
    current_value: Optional[str] = typer.Option(None, "--current-value"),
    source: str = typer.Option("manual", "--source"),
) -> None:
    """REGLA DURA de defense_env/ (ver CHANGELOG.md): esto SOLO informa y
    sugiere — nunca aplica nada. Para aplicar, `defense-remediate-apply`
    con --yes explícito."""
    finding = _build_finding(detail, package_manager, setting, current_value, source)
    suggestion = suggest_remediation(pattern_id, finding)
    if suggestion is None:
        typer.echo(f"Sin sugerencia conocida para {pattern_id!r} — no se inventa un fix para algo no reconocido.")
        raise typer.Exit(code=1)

    typer.echo(f"PROBLEMA: {suggestion.issue}")
    typer.echo(f"POR QUÉ IMPORTA: {suggestion.explanation}")
    typer.echo(f"RIESGO: {suggestion.risk_level}")
    typer.echo(f"COMANDO SUGERIDO: {' '.join(suggestion.suggested_command)}")
    typer.echo(f"\nEsto NO se aplicó. Para aplicarlo: defense-remediate-apply {pattern_id} ... --yes")


@app.command("defense-remediate-apply")
def defense_remediate_apply_cmd(
    pattern_id: str = typer.Argument(...),
    detail: Optional[str] = typer.Option(None, "--detail"),
    package_manager: str = typer.Option("dnf", "--package-manager"),
    setting: Optional[str] = typer.Option(None, "--setting"),
    current_value: Optional[str] = typer.Option(None, "--current-value"),
    source: str = typer.Option("manual", "--source"),
    confirm: bool = typer.Option(
        False, "--yes", help="Confirmación explícita — sin esto, apply_remediation rechaza aplicar (regla dura)"
    ),
) -> None:
    """Aplica una remediación conocida. Repite la sugerencia primero,
    igual que `defense-remediate-suggest` — informa antes de aplicar,
    siempre, incluso con --yes ya puesto."""
    finding = _build_finding(detail, package_manager, setting, current_value, source)
    suggestion = suggest_remediation(pattern_id, finding)
    if suggestion is None:
        typer.echo(f"Sin sugerencia conocida para {pattern_id!r}.")
        raise typer.Exit(code=1)

    typer.echo(f"PROBLEMA: {suggestion.issue}")
    typer.echo(f"COMANDO A APLICAR: {' '.join(suggestion.suggested_command)}")

    if not confirm:
        typer.echo("\nNo se aplicó — confirmá con --yes tras revisar el comando de arriba.")
        raise typer.Exit(code=1)

    result = apply_remediation(suggestion, confirmed=True)
    typer.echo(f"\n[{'OK' if result['success'] else 'FALLO'}] aplicado — {result['detail'] or '(sin salida)'}")
    if not result["success"]:
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
