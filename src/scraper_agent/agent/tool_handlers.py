"""Ejecución de tools invocadas por el agente LLM."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable

from scraper_agent.agent.llm_models import JsonPlanAction
from scraper_agent.cli import load_config
from scraper_agent.crawler.orchestrator import CrawlOrchestrator, _parse_cli_date
from scraper_agent.models.search_target import load_search_target
from scraper_agent.search.persist import write_search_enriched_json
from scraper_agent.security_env.authorization_guard import AuthorizationGuard, load_authorized_targets
from scraper_agent.security_env.executor_factory import resolve_command_executor
from scraper_agent.security_env.kali_runtime import KaliRuntime
from scraper_agent.security_env.models import ToolExecutionRequest
from scraper_agent.security_env.tool_runner import ToolRunner, load_tool_catalog

CrawlHandler = Callable[..., Awaitable[dict[str, Any]]]


@dataclass
class AgentDependencies:
    """Dependencias inyectables (producción vs tests)."""

    authorized_targets_path: Path = Path("config/authorized_targets.yaml")
    session_id: str = "default"
    requested_by: str = "agent"
    crawl_handler: CrawlHandler | None = None
    tool_runner: ToolRunner | None = None


@dataclass
class ToolHandlerRegistry:
    """Mapa nombre de tool → handler async."""

    deps: AgentDependencies
    _tool_runner: ToolRunner | None = field(default=None, repr=False)

    def _resolve_tool_runner(self) -> ToolRunner:
        if self.deps.tool_runner is not None:
            return self.deps.tool_runner
        if self._tool_runner is not None:
            return self._tool_runner
        auth_path = self.deps.authorized_targets_path
        if not auth_path.exists():
            raise FileNotFoundError(
                f"No existe {auth_path}; copie authorized_targets.yaml.example"
            )
        # Fase 3 de defense_env/ (respuesta activa): si hay un lockdown
        # activo (disparado por una alerta critical de FIM/correlación), el
        # guard deniega TODO acá también — el kill-switch cubre tanto la
        # chat API como scripts/run_pentest.py (ambos pasan por este mismo
        # punto de construcción).
        guard = AuthorizationGuard(
            load_authorized_targets(auth_path),
            lockdown_path=Path("output/security/LOCKDOWN.json"),
        )
        self._tool_runner = ToolRunner(
            catalog=load_tool_catalog(),
            guard=guard,
            runtime=KaliRuntime(resolve_command_executor()),
            # Persistencia real del audit log — defense_env/ correlaciona
            # contra este archivo. Antes de esto el audit log se perdía al
            # reiniciar el proceso (gap encontrado 2026-07-09, ver CHANGELOG.md).
            audit_sink_path=Path("output/security/tool_audit.jsonl"),
        )
        return self._tool_runner

    async def dispatch(self, name: str, arguments: dict[str, Any]) -> str:
        handlers: dict[str, Callable[..., Awaitable[str]]] = {
            "run_site_crawl": self.run_site_crawl,
            "search_crawl_output": self.search_crawl_output,
            "list_security_tools": self.list_security_tools,
            "run_security_tool": self.run_security_tool,
        }
        handler = handlers.get(name)
        if handler is None:
            return json.dumps({"error": f"tool desconocida: {name}"})
        return await handler(arguments)

    async def dispatch_json_plan(self, plan: JsonPlanAction) -> str:
        return await self.dispatch(plan.action, plan.arguments)

    async def run_site_crawl(self, arguments: dict[str, Any]) -> str:
        config_path = Path(str(arguments["config_path"]))
        if not config_path.exists():
            return json.dumps({"error": f"config no encontrada: {config_path}"})
        cfg = load_config(config_path)
        from_date = arguments.get("from_date")
        to_date = arguments.get("to_date")
        if self.deps.crawl_handler is not None:
            summary = await self.deps.crawl_handler(
                config_path=config_path,
                from_date=from_date,
                to_date=to_date,
            )
            return json.dumps(summary, ensure_ascii=False)
        orchestrator = CrawlOrchestrator(
            cfg,
            date_from=_parse_cli_date(str(from_date)) if from_date else None,
            date_to=_parse_cli_date(str(to_date)) if to_date else None,
        )
        result = await orchestrator.run()
        return json.dumps(
            {
                "domain": cfg.domain,
                "pages": result.total_pages_visited,
                "articles": result.total_articles_extracted,
                "output": cfg.output.path,
            },
            ensure_ascii=False,
        )

    async def search_crawl_output(self, arguments: dict[str, Any]) -> str:
        input_json = Path(str(arguments["input_json"]))
        target_file = Path(str(arguments["target_file"]))
        if not input_json.exists():
            return json.dumps({"error": f"JSON no encontrado: {input_json}"})
        target = load_search_target(target_file)
        dest = write_search_enriched_json(input_json, target)
        payload = json.loads(dest.read_text(encoding="utf-8"))
        hits = len(payload.get("search_results") or [])
        return json.dumps({"output": str(dest), "hits": hits}, ensure_ascii=False)

    async def list_security_tools(self, _arguments: dict[str, Any]) -> str:
        catalog = load_tool_catalog()
        tools = [
            {"id": entry.id, "category": entry.category, "description": entry.description}
            for entry in catalog.values()
        ]
        return json.dumps({"tools": tools}, ensure_ascii=False)

    async def run_security_tool(self, arguments: dict[str, Any]) -> str:
        runner = self._resolve_tool_runner()
        request = ToolExecutionRequest(
            tool_id=str(arguments["tool_id"]),
            host=str(arguments["host"]),
            session_id=str(arguments.get("session_id") or self.deps.session_id),
            requested_by=self.deps.requested_by,
        )
        result = await runner.execute(request)
        return json.dumps(
            {
                "tool_id": result.tool_id,
                "host": result.host,
                "exit_code": result.exit_code,
                "stdout": result.stdout[:2000],
                "stderr": result.stderr[:500],
            },
            ensure_ascii=False,
        )
